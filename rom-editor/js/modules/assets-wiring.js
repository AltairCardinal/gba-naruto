// 素材与资源域：指针接线表 / 资源记录表 / 指针接线总表。
//
// 这一域能做的只有一件事：换指针。
// 载荷（图块、调色板、脚本的字节）改不了 —— 仓库里没有与原版逐字节一致的
// LZ77 压缩器（只有 tools/lib/lz77.py::compress_literal 纯字面量编码器）。
// 所以这里的每个视图都把三件事摆在明面上：
// 这一格指向哪、全包里有几处指向同一个地址、改它会动到谁。
//
// 写回只走 pack.setValue：原始字节那一侧不碰。

import { el, clear, formatHex32, formatOffset, toast } from '../ui.js';
import { ROM_BASE, base64ToBytes, bytesToBase64 } from '../bytes.js';
import { fieldControl, originalValue, pointerSummary } from '../fields.js';
import { arraysIn, columnLabel } from '../slots.js';
import { backReferencesByPointer } from '../xref.js';
import { valueMatches } from '../editors.js';
import { backButton } from './common.js';

export const PTR_TABLE_A = 'data_pointer_table_a';
export const PTR_TABLE_B = 'data_pointer_table_b';
export const TILE_RECORDS = 'tile_asset_records';
export const WRAM_ALLOCATION = 'wram_allocation';

/** ROM 空间的上界（0x08000000 + 6MB）。超出这个范围的格子不是指针。 */
const ROM_END = ROM_BASE + 0x600000;

/** 重复槽位数组的中文标题。 */
const ARRAY_TITLES = { gfx: '图块指针', script: '脚本指针' };

// --------------------------------------------------------------------------
// 共用 helper
// --------------------------------------------------------------------------

/** 指针值的十六进制写法（与列表、详情一致）。 */
export function hex32(value) {
  return formatHex32(value >>> 0);
}

/**
 * 指针目标摘要：ROM 偏移 + 载荷类型。
 *
 * 载荷类型是导出时判定的事实（内容包 derived.pointer_targets），
 * 不载入原版 ROM 也给得出；判定不了时明说「判定不到」。
 */
export function targetSummary(pack, value) {
  if (!value) return '空指针（原版就是空的）';
  if (value < ROM_BASE || value >= ROM_END) {
    return `${hex32(value)} · 不在 ROM 范围内（0x08000000–0x085FFFFF），这一格可能不是指针`;
  }
  return pointerSummary(pack, value);
}

/**
 * 全包里指向同一个地址的指针。
 *
 * 一次反查要扫过六千多个指针格，所以按地址缓存；
 * 指针一改就清缓存（clearPointerCache）。
 */
const refsCache = new Map();

export function clearPointerCache() {
  refsCache.clear();
}

export function pointerRefs(pack, address) {
  if (!address) return [];
  if (!refsCache.has(address)) {
    refsCache.set(address, backReferencesByPointer(pack, address));
  }
  return refsCache.get(address);
}

/** 这条记录相对原版是否被改过（比字节，不看 dirty 集合）。 */
export function recordChanged(pack, structure, record) {
  const bytes = pack.recordBytes(structure, record);
  const raw = base64ToBytes(record.raw || '');
  return bytesToBase64(bytes) !== bytesToBase64(raw);
}

/** 一张表里的指针字段（两张指针表都只有一个 ptr 字段）。 */
export function pointerField(table) {
  return (table.fields || []).find((f) => f.type === 'ptr') || null;
}

/** 跳到「原始字节」的指定偏移。 */
export function jumpToRaw(ctx, address) {
  if (!address) {
    toast('这一格是空指针，没有可跳的地址', 'error');
    return;
  }
  const offset = address - ROM_BASE;
  if (ctx.goModule) ctx.goModule('raw');
  if (ctx.openPanel) ctx.openPanel('raw-offset', 'raw', { offset });
}

/**
 * 图块组合 / 脚本组合各有几种（内容包里算出来的，不写死）。
 *
 * @returns {{gfxKinds: number, scriptKinds: number}}
 */
export function comboStats(pack) {
  const table = pack.structure(TILE_RECORDS);
  if (!table) return { gfxKinds: 0, scriptKinds: 0 };
  const arrays = arraysIn(table.fields || []);
  const valuesOf = (record, name) => {
    const array = arrays.find((a) => a.name === name);
    if (!array) return [];
    return [...array.rows.values()].map((row) => {
      const field = row.ptr || Object.values(row)[0];
      return record.values[field.key];
    });
  };
  const gfx = new Set();
  const script = new Set();
  for (const record of table.records || []) {
    gfx.add(valuesOf(record, 'gfx').join(','));
    script.add(valuesOf(record, 'script').join(','));
  }
  return { gfxKinds: gfx.size, scriptKinds: script.size };
}

// --------------------------------------------------------------------------
// 视图一：指针接线表（数据指针表 A / B）
// --------------------------------------------------------------------------

export function renderWiring(container, ctx, params = {}) {
  new WiringView(ctx, params).render(container);
}

class WiringView {
  constructor(ctx, params) {
    this.ctx = ctx;
    this.pack = ctx.pack;
    this.tables = [this.pack.structure(PTR_TABLE_A), this.pack.structure(PTR_TABLE_B)]
      .filter(Boolean);
    this.query = '';
    this.selected = null;
    this.refreshers = [];

    const wanted = params && params.recordId !== undefined && params.recordId !== null
      ? Number(params.recordId)
      : null;
    if (this.tables.length) {
      const table = params && params.table === 'b' ? this.tables[1] : this.tables[0];
      const record = wanted === null
        ? (table.records || [])[0]
        : (table.records || []).find((r) => r.id === wanted);
      if (record) this.selected = { table, record };
    }
  }

  render(container) {
    clear(container);
    const ctx = this.ctx;
    container.appendChild(el('div', { style: { marginBottom: '12px' } }, [
      backButton(ctx, '素材与资源'),
    ]));

    const total = this.tables.reduce((n, t) => n + ((t.records || []).length), 0);
    container.appendChild(el('div', { class: 'panel-head' }, [
      el('div', {}, [
        el('h2', { text: '指针接线表' }),
        el('div', { class: 'panel-sub' }, [
          ...this.tables.map((t) => el('span', {
            text: `${t.label} ${(t.records || []).length} 槽`,
          })),
          el('span', { text: `共 ${total} 槽` }),
        ]),
      ]),
      el('div', { class: 'panel-tools' }, [
        el('input', {
          class: 'search',
          type: 'search',
          placeholder: '搜指针：十六进制或十进制都行',
          value: this.query,
          oninput: (e) => {
            this.query = e.target.value;
            this.renderList();
          },
        }),
      ]),
    ]));

    container.appendChild(el('div', { class: 'rule-note' }, [
      el('span', { class: 'rule-title', text: '结论' }),
      el('span', { text: '改指针能换资源，载荷本身动不了。改这一格 = 换一个资源；指向的字节一个都不会变。' }),
    ]));

    this.listWrap = el('div', { class: 'table-wrap' });
    this.detailWrap = el('div', { class: 'detail-panel wide' });
    container.appendChild(el('div', { class: 'split' }, [this.listWrap, this.detailWrap]));
    this.renderList();
    this.renderDetail();
  }

  ptrKey(table) {
    const field = pointerField(table);
    return field ? field.key : 'ptr';
  }

  /** 搜索：指针值（十六进制 / 十进制）、目标文字、下标都吃。 */
  matches(record, table) {
    const query = (this.query || '').trim().toLowerCase();
    if (!query) return true;
    const value = record.values[this.ptrKey(table)];
    if (valueMatches(value, query)) return true;
    if (String(record.id) === query || ('#' + record.id) === query) return true;
    return targetSummary(this.pack, value).toLowerCase().includes(query);
  }

  renderList() {
    clear(this.listWrap);
    for (const table of this.tables) {
      const rows = (table.records || []).filter((r) => this.matches(r, table));
      const body = el('tbody');
      for (const record of rows) {
        const value = record.values[this.ptrKey(table)];
        const changed = recordChanged(this.pack, table, record);
        const selected = this.selected
          && this.selected.table === table
          && this.selected.record === record;
        body.appendChild(el('tr', {
          class: (selected ? 'selected' : '') + (changed ? ' changed' : ''),
          onclick: () => {
            this.selected = { table, record };
            this.renderList();
            this.renderDetail();
          },
        }, [
          el('td', { class: 'col-id', text: '#' + record.id }),
          el('td', { class: 'mono', text: value ? hex32(value) : '空' }),
          el('td', { class: 'text-cell', text: targetSummary(this.pack, value) }),
          el('td', { text: this.sameAddressText(table, record, value) }),
          el('td', { text: changed ? '已改' : '—' }),
        ]));
      }
      this.listWrap.appendChild(el('div', { class: 'wiring-section' }, [
        el('div', {
          class: 'slot-caption',
          text: `${table.label}（${rows.length} / ${(table.records || []).length} 槽）`,
        }),
        el('table', { class: 'grid' }, [
          el('thead', {}, [el('tr', {}, [
            el('th', { class: 'col-id', text: '下标' }),
            el('th', { text: '当前指针' }),
            el('th', { text: '目标' }),
            el('th', { text: '同址' }),
            el('th', { text: '状态' }),
          ])]),
          body,
        ]),
      ]));
    }
    if (!this.listWrap.children.length) {
      this.listWrap.appendChild(el('div', { class: 'empty', text: '没有匹配的指针槽' }));
    }
  }

  /** 全包里有几处指向同一地址；同一张表里还有谁也指着它。 */
  sameAddressText(table, record, value) {
    if (!value) return '—';
    const refs = pointerRefs(this.pack, value);
    if (refs.length <= 1) return '—';
    const sibling = (table.records || []).find(
      (r) => r !== record && r.values[this.ptrKey(table)] === value);
    const where = sibling ? `与 #${sibling.id} 同址` : '本表没有第二处';
    return `${where}（全包 ${refs.length} 处）`;
  }

  renderDetail() {
    clear(this.detailWrap);
    const sel = this.selected;
    if (!sel) {
      this.detailWrap.appendChild(el('div', {
        class: 'empty',
        text: '在左边点一行：这一格指向哪、改它会动到谁',
      }));
      return;
    }
    const table = sel.table;
    const record = sel.record;
    const field = pointerField(table);
    const value = record.values[field.key];
    const consumers = (table.consumers || []).map((c) => String(c).toUpperCase());

    this.detailWrap.appendChild(el('div', { class: 'detail-head' }, [
      el('h3', { text: `${table.label} · #${record.id}` }),
      el('div', { class: 'detail-nav' }, [
        el('button', {
          class: 'btn btn-tiny', text: '← 上一条',
          onclick: () => this.step(-1),
        }),
        el('button', {
          class: 'btn btn-tiny', text: '下一条 →',
          onclick: () => this.step(1),
        }),
        el('button', {
          class: 'btn btn-ghost', text: '✕',
          onclick: () => {
            this.selected = null;
            this.renderList();
            this.renderDetail();
          },
        }),
      ]),
    ]));

    this.detailWrap.appendChild(el('div', { class: 'detail-sub' }, [
      el('span', { text: `ROM ${formatOffset(record.rom_offset)}` }),
      el('span', { text: `第 ${record.id + 1} / ${(table.records || []).length} 条` }),
      consumers.length ? el('span', { text: `原生读者 ${consumers.join(' / ')}` }) : null,
      recordChanged(this.pack, table, record)
        ? el('span', { class: 'tag tag-warn', text: '已改动' })
        : null,
    ]));

    const control = fieldControl(this.fieldCtx(), table, record, field);
    this.input = control.node;
    this.targetLine = el('div', { class: 'field-hint' });
    this.originLine = el('div', { class: 'field-hint' });
    this.detailWrap.appendChild(el('div', { class: 'group' }, [
      el('div', { class: 'group-head' }, [
        el('span', { class: 'group-name', text: '指向哪' }),
      ]),
      el('div', { class: 'group-body' }, [
        el('div', { class: 'field' }, [
          el('label', { class: 'field-label' }, [
            el('span', { text: '指针（十六进制，也可粘贴十进制）' }),
          ]),
          control.node,
        ]),
        this.targetLine,
        this.originLine,
        el('div', { class: 'field-actions' }, [
          el('button', {
            class: 'btn btn-tiny', text: '↺ 恢复原值',
            onclick: () => this.restore(),
          }),
          el('button', {
            class: 'btn btn-tiny', text: '跳到原始字节',
            onclick: () => jumpToRaw(this.ctx, value),
          }),
        ]),
      ]),
    ]));

    this.detailWrap.appendChild(el('div', { class: 'group' }, [
      el('div', { class: 'group-head' }, [
        el('span', { class: 'group-name', text: '改成' }),
      ]),
      el('div', { class: 'group-body' }, [
        el('div', { class: 'copy-row' }, [
          this.copySelect('same'),
          this.copySelect('other'),
          el('button', {
            class: 'btn btn-tiny', text: '手动填地址',
            onclick: () => { if (this.input && this.input.focus) this.input.focus(); },
          }),
        ]),
        el('div', {
          class: 'field-hint',
          text: '复制过来的是「用哪一份资源」；载荷本身仍然动不了。',
        }),
      ]),
    ]));

    this.consequence = el('div', { class: 'consequence' });
    this.detailWrap.appendChild(el('div', { class: 'group' }, [
      el('div', { class: 'group-head' }, [
        el('span', { class: 'group-name', text: '这一项改动的后果' }),
      ]),
      el('div', { class: 'group-body' }, [this.consequence]),
    ]));

    this.refreshDetail();
  }

  /** 改完之后只刷新会变的那几行，不重建整个详情（输入框保持焦点）。 */
  refreshDetail() {
    const sel = this.selected;
    if (!sel) return;
    const table = sel.table;
    const record = sel.record;
    const field = pointerField(table);
    const value = record.values[field.key];
    const original = originalValue(table, record, field);

    if (this.targetLine) {
      this.targetLine.textContent = `目标 ${targetSummary(this.pack, value)}`;
    }
    if (this.originLine) {
      this.originLine.textContent = original === undefined || original === null
        ? ''
        : (original === value
          ? `原值 ${hex32(original)}`
          : `原值 ${hex32(original)} → 现在 ${hex32(value)}`);
    }
    if (this.consequence) {
      this.consequence.textContent = '';
      const lines = [];
      if (value) {
        lines.push(`原来指向 ${hex32(value)}，改它等于换一份资源；载荷本身一个字节都不会变。`);
        const refs = pointerRefs(this.pack, value);
        if (refs.length > 1) {
          lines.push(`全包有 ${refs.length} 处指向这个地址，改一处，那几处会一起变。`);
        }
        const payload = this.pack.pointerTarget ? this.pack.pointerTarget(value) : null;
        if (!payload) {
          lines.push('这个地址不在任何已知资源块的起点上（内容包判定不到载荷），接上去很可能花屏。');
        }
      } else {
        lines.push('这一格原版就是空的，改成任何地址都是新增一个指向。');
      }
      for (const line of lines) {
        this.consequence.appendChild(el('div', { class: 'consequence-line', text: line }));
      }
    }
  }

  /** 指针字段的控件上下文：提交后刷新列表与结论。 */
  fieldCtx() {
    const ctx = this.ctx;
    return {
      pack: ctx.pack,
      onChange: () => { if (ctx.onChange) ctx.onChange(); },
      onJump: ctx.onJump,
      onCommit: () => {
        clearPointerCache();
        this.renderList();
        this.refreshDetail();
      },
      registerRefresh: (fn) => { this.refreshers.push(fn); },
    };
  }

  /** 「从本表其它项复制…」/「从另一张指针表复制…」。 */
  copySelect(scope) {
    const sel = this.selected;
    const table = sel.table;
    const select = el('select', {
      class: 'num-input copy-select',
      onchange: (e) => {
        const raw = e.target.value;
        e.target.value = '';
        if (!raw) return;
        this.commitPtr(Number(raw));
      },
    });
    select.appendChild(el('option', {
      value: '',
      text: scope === 'same' ? '从本表其它项复制…' : '从另一张指针表复制…',
    }));
    for (const other of this.tables) {
      if (scope === 'same' && other !== table) continue;
      if (scope === 'other' && other === table) continue;
      for (const record of other.records || []) {
        const value = record.values[this.ptrKey(other)];
        if (!value) continue;
        const payload = this.pack.pointerTarget ? this.pack.pointerTarget(value) : null;
        const label = payload && payload.label ? payload.label : '未压缩原始数据';
        const prefix = scope === 'same' ? '' : `${other.label} `;
        select.appendChild(el('option', {
          value: String(value),
          text: `${prefix}#${record.id}  ${hex32(value)} · ${label}`,
        }));
      }
    }
    return select;
  }

  /** 写入一个新指针（所有写回都走 pack.setValue）。 */
  commitPtr(next) {
    const sel = this.selected;
    if (!sel) return;
    if (!Number.isFinite(next)) return;
    const table = sel.table;
    const record = sel.record;
    const field = pointerField(table);
    this.pack.setValue(table, record, field.key, next >>> 0);
    if (this.ctx.onChange) this.ctx.onChange();
    clearPointerCache();
    if (this.input) this.input.value = hex32(next);
    this.renderList();
    this.refreshDetail();
    toast(`已改：${table.label} #${record.id} 的指针`);
  }

  restore() {
    const sel = this.selected;
    if (!sel) return;
    const table = sel.table;
    const record = sel.record;
    const field = pointerField(table);
    const original = originalValue(table, record, field);
    this.pack.setValue(table, record, field.key, original);
    if (this.ctx.onChange) this.ctx.onChange();
    clearPointerCache();
    if (this.input) this.input.value = hex32(original);
    this.renderList();
    this.refreshDetail();
    toast(`已恢复 ${table.label} #${record.id} 的原值`);
  }

  step(delta) {
    const sel = this.selected;
    if (!sel) return;
    const records = sel.table.records || [];
    const at = records.indexOf(sel.record);
    const next = records[at + delta];
    if (!next) {
      toast(delta > 0 ? '已经是最后一条了' : '已经是第一条了', 'error');
      return;
    }
    this.selected = { table: sel.table, record: next };
    this.renderList();
    this.renderDetail();
  }
}

// --------------------------------------------------------------------------
// 视图二：图块 / 精灵资源记录表（79 条 × 9 个指针）
// --------------------------------------------------------------------------

export function renderAssetRecords(container, ctx, params = {}) {
  new RecordsView(ctx, params).render(container);
}

class RecordsView {
  constructor(ctx, params) {
    this.ctx = ctx;
    this.pack = ctx.pack;
    this.table = ctx.pack.structure(TILE_RECORDS);
    this.query = '';
    this.groupKey = null;      // 只看共用同一图块组合的记录
    this.selected = null;
    this.refreshers = [];
    this.targetCells = new Map();
    this.groups = this.computeGroups();

    const wanted = params && params.recordId !== undefined && params.recordId !== null
      ? Number(params.recordId)
      : null;
    const records = (this.table && this.table.records) || [];
    const record = wanted === null
      ? records[0]
      : records.find((r) => r.id === wanted);
    if (record) this.selected = record;
  }

  /** 重复槽位数组（gfx 6 行 / script 3 行）。 */
  arrays() {
    if (!this._arrays) this._arrays = arraysIn((this.table && this.table.fields) || []);
    return this._arrays;
  }

  arrayOf(name) {
    return this.arrays().find((a) => a.name === name) || null;
  }

  /** 一条记录在某个数组里的指针（按槽位顺序）。 */
  arrayValues(record, name) {
    const array = this.arrayOf(name);
    if (!array) return [];
    const out = [];
    for (const [index, row] of array.rows) {
      const field = row.ptr || Object.values(row)[0];
      out.push({
        index,
        slot: index - array.base + 1,
        field,
        value: record.values[field.key],
      });
    }
    return out;
  }

  /** 图块组合 / 脚本组合的分组与共用数。 */
  computeGroups() {
    const records = (this.table && this.table.records) || [];
    const info = new Map();
    const gfxIndex = new Map();
    const scriptIndex = new Map();
    for (const record of records) {
      const gfxKey = this.arrayValues(record, 'gfx').map((s) => s.value).join(',');
      const scriptKey = this.arrayValues(record, 'script').map((s) => s.value).join(',');
      if (!gfxIndex.has(gfxKey)) gfxIndex.set(gfxKey, gfxIndex.size);
      if (!scriptIndex.has(scriptKey)) scriptIndex.set(scriptKey, scriptIndex.size);
      info.set(record.id, {
        gfxKey,
        scriptKey,
        gfxGroup: gfxIndex.get(gfxKey),
        scriptGroup: scriptIndex.get(scriptKey),
        gfxShared: 0,
        scriptShared: 0,
      });
    }
    const gfxCount = new Map();
    const scriptCount = new Map();
    for (const record of records) {
      const item = info.get(record.id);
      gfxCount.set(item.gfxKey, (gfxCount.get(item.gfxKey) || 0) + 1);
      scriptCount.set(item.scriptKey, (scriptCount.get(item.scriptKey) || 0) + 1);
    }
    // 把每种组合的记录数写回每一条记录：「这一条被几条记录共用」。
    for (const record of records) {
      const item = info.get(record.id);
      item.gfxShared = gfxCount.get(item.gfxKey);
      item.scriptShared = scriptCount.get(item.scriptKey);
    }
    return {
      info,
      gfxKinds: gfxIndex.size,
      scriptKinds: scriptIndex.size,
    };
  }

  visibleRecords() {
    const records = (this.table && this.table.records) || [];
    const query = (this.query || '').trim().toLowerCase();
    return records.filter((record) => {
      if (this.groupKey) {
        const item = this.groups.info.get(record.id);
        if (!item || item.gfxKey !== this.groupKey) return false;
      }
      if (!query) return true;
      if (String(record.id) === query || ('#' + record.id) === query) return true;
      const item = this.groups.info.get(record.id);
      if (item && (`${item.gfxGroup} ${item.scriptGroup}`).includes(query)) return true;
      return this.arrayValues(record, 'gfx').concat(this.arrayValues(record, 'script'))
        .some((slot) => valueMatches(slot.value, query));
    });
  }

  render(container) {
    clear(container);
    const ctx = this.ctx;
    if (!this.table) {
      container.appendChild(el('div', { class: 'empty', text: '内容包里没有图块/精灵资源记录表' }));
      return;
    }
    container.appendChild(el('div', { style: { marginBottom: '12px' } }, [
      backButton(ctx, '素材与资源'),
    ]));

    const records = this.table.records || [];
    const consumers = (this.table.consumers || []).map((c) => String(c).toUpperCase());
    container.appendChild(el('div', { class: 'panel-head' }, [
      el('div', {}, [
        el('h2', { text: this.table.label || '图块/精灵资源记录表' }),
        el('div', { class: 'panel-sub' }, [
          el('span', { text: `ROM ${formatOffset(this.table.rom_offset)}` }),
          el('span', { text: `${this.table.entry_size || 0} 字节/条` }),
          el('span', { text: `${records.length} 条` }),
          consumers.length ? el('span', { text: `原生读者 ${consumers.join(' / ')}` }) : null,
        ]),
      ]),
      el('div', { class: 'panel-tools' }, [
        el('input', {
          class: 'search',
          type: 'search',
          placeholder: '搜记录或指针',
          value: this.query,
          oninput: (e) => {
            this.query = e.target.value;
            this.renderList();
          },
        }),
      ]),
    ]));

    container.appendChild(el('div', { class: 'rule-note' }, [
      el('span', { class: 'rule-title', text: '结论' }),
      el('span', {
        text: `改指针能换资源，载荷本身动不了。${records.length} 条记录里只有 `
          + `${this.groups.gfxKinds} 种不同的图块组合、${this.groups.scriptKinds} 种不同的脚本组合；`
          + '共用同一组合的记录改一处会一起变。',
      }),
    ]));

    this.listWrap = el('div', { class: 'table-wrap' });
    this.detailWrap = el('div', { class: 'detail-panel wide' });
    container.appendChild(el('div', { class: 'split' }, [this.listWrap, this.detailWrap]));
    this.renderList();
    this.renderDetail();
  }

  renderList() {
    clear(this.listWrap);
    const rows = this.visibleRecords();
    if (this.groupKey) {
      this.listWrap.appendChild(el('div', { class: 'group-filter' }, [
        el('span', { text: `只看共用同一图块组合的记录（${rows.length} 条）` }),
        el('button', {
          class: 'btn btn-tiny', text: '看全部',
          onclick: () => { this.groupKey = null; this.renderList(); },
        }),
      ]));
    }
    const body = el('tbody');
    for (const record of rows) {
      const item = this.groups.info.get(record.id);
      const changed = recordChanged(this.pack, this.table, record);
      const selected = this.selected === record;
      body.appendChild(el('tr', {
        class: (selected ? 'selected' : '') + (changed ? ' changed' : ''),
        onclick: () => {
          this.selected = record;
          this.renderList();
          this.renderDetail();
        },
      }, [
        el('td', { class: 'col-id', text: '#' + record.id }),
        el('td', { text: `#${item.gfxGroup} 组（${item.gfxShared} 条记录共用）` }),
        el('td', { text: `#${item.scriptGroup} 组（${item.scriptShared} 条共用）` }),
        el('td', { text: changed ? '已改' : '—' }),
      ]));
    }
    this.listWrap.appendChild(el('table', { class: 'grid' }, [
      el('thead', {}, [el('tr', {}, [
        el('th', { class: 'col-id', text: '记录' }),
        el('th', { text: '图块组' }),
        el('th', { text: '脚本组' }),
        el('th', { text: '状态' }),
      ])]),
      body,
    ]));
    if (!rows.length) {
      this.listWrap.appendChild(el('div', { class: 'empty', text: '没有匹配的记录' }));
    }
  }

  renderDetail() {
    clear(this.detailWrap);
    const record = this.selected;
    if (!record) {
      this.detailWrap.appendChild(el('div', { class: 'empty', text: '在左边点一条记录' }));
      return;
    }
    const records = this.table.records || [];
    const consumers = (this.table.consumers || []).map((c) => String(c).toUpperCase());
    this.targetCells = new Map();

    this.detailWrap.appendChild(el('div', { class: 'detail-head' }, [
      el('h3', { text: `${this.table.label} · #${record.id}` }),
      el('div', { class: 'detail-nav' }, [
        el('button', {
          class: 'btn btn-tiny', text: '← 上一条',
          onclick: () => this.step(-1),
        }),
        el('button', {
          class: 'btn btn-tiny', text: '下一条 →',
          onclick: () => this.step(1),
        }),
        el('button', {
          class: 'btn btn-ghost', text: '✕',
          onclick: () => {
            this.selected = null;
            this.renderList();
            this.renderDetail();
          },
        }),
      ]),
    ]));

    this.detailWrap.appendChild(el('div', { class: 'detail-sub' }, [
      el('span', { text: `ROM ${formatOffset(record.rom_offset)}` }),
      el('span', { text: `第 ${record.id + 1} / ${records.length} 条` }),
      consumers.length ? el('span', { text: `原生读者 ${consumers.join(' / ')}` }) : null,
      recordChanged(this.pack, this.table, record)
        ? el('span', { class: 'tag tag-warn', text: '已改动' })
        : null,
    ]));

    for (const name of ['gfx', 'script']) {
      const block = this.slotTable(name);
      if (block) this.detailWrap.appendChild(block);
    }

    const raw = this.rawBlock();
    if (raw) this.detailWrap.appendChild(raw);

    this.conclusionBox = el('div', { class: 'group-body' });
    this.consequenceWrap = el('div', { class: 'consequence' });
    this.conclusionBox.appendChild(this.consequenceWrap);
    this.detailWrap.appendChild(el('div', { class: 'group' }, [
      el('div', { class: 'group-head' }, [
        el('span', { class: 'group-name', text: '这条记录的结论' }),
      ]),
      this.conclusionBox,
    ]));
    this.rebuildConclusion();
  }

  /** 结论块的内容（共用数变了就重建，输入框不重建，焦点不丢）。 */
  rebuildConclusion() {
    if (!this.consequenceWrap) return;
    this.consequenceWrap.textContent = '';
    for (const node of this.conclusionNodes()) {
      this.consequenceWrap.appendChild(node);
    }
  }

  /** 指针改过以后，刷新每一行的目标摘要。 */
  refreshTargets() {
    const record = this.selected;
    if (!record || !this.targetCells) return;
    for (const [key, cell] of this.targetCells) {
      cell.textContent = targetSummary(this.pack, record.values[key]);
    }
  }

  /** 一个重复槽位数组 → 一张表（槽 / 指针 / 目标），不是一串竖排输入框。 */
  slotTable(name) {
    const array = this.arrayOf(name);
    if (!array) return null;
    const record = this.selected;
    const title = ARRAY_TITLES[name] || columnLabel(name, 'id');
    const body = el('tbody');
    for (const [index, row] of array.rows) {
      const field = row.ptr || Object.values(row)[0];
      const control = fieldControl(this.fieldCtx(), this.table, record, field);
      const value = record.values[field.key];
      const targetCell = el('td', { class: 'text-cell', text: targetSummary(this.pack, value) });
      this.targetCells.set(field.key, targetCell);
      body.appendChild(el('tr', {}, [
        el('td', { class: 'col-id', text: String(index - array.base + 1) }),
        el('td', { class: 'slot-cell' }, [control.node]),
        targetCell,
      ]));
    }
    return el('div', { class: 'slot-block' }, [
      el('div', { class: 'slot-caption', text: `${title}（${array.rows.size}）` }),
      el('div', { class: 'slot-table' }, [
        el('table', { class: 'grid grid-slots' }, [
          el('thead', {}, [el('tr', {}, [
            el('th', { class: 'col-id', text: '槽' }),
            el('th', { text: '指针' }),
            el('th', { text: '目标' }),
          ])]),
          body,
        ]),
      ]),
    ]);
  }

  /** 未解码的字节：折叠起来，明说原样保留。 */
  rawBlock() {
    const fields = (this.table.fields || []).filter((f) => f.type === 'hex');
    if (!fields.length) return null;
    const record = this.selected;
    const body = el('div', { class: 'group-body' });
    let total = 0;
    for (const field of fields) {
      total += field.size || 0;
      const control = fieldControl(this.fieldCtx(), this.table, record, field);
      body.appendChild(el('div', { class: 'field' }, [
        el('label', { class: 'field-label' }, [
          el('span', { text: `${field.label || field.key}（${field.size || 0} 字节）` }),
        ]),
        control.node,
      ]));
    }
    body.appendChild(el('div', {
      class: 'field-hint',
      text: '这些字节的语义还没证明，原样保留；没改动的部分按原字节写回。',
    }));
    return el('details', { class: 'group raw-bytes' }, [
      el('summary', { text: `未解码字节（${fields.length} 段 / ${total} 字节）· 原样保留` }),
      body,
    ]);
  }

  /** 这条记录被几条记录共用（结论块的节点，父节点由 rebuildConclusion 挂上）。 */
  conclusionNodes() {
    const record = this.selected;
    const item = this.groups.info.get(record.id);
    const records = this.table.records || [];
    const sharing = records.filter((r) => {
      const other = this.groups.info.get(r.id);
      return other && other.gfxKey === item.gfxKey;
    });
    const others = sharing.filter((r) => r !== record);
    const nodes = [];
    nodes.push(el('div', {
      class: 'consequence-line',
      text: `${records.length} 条记录里只有 ${this.groups.gfxKinds} 种不同的图块组合、`
        + `${this.groups.scriptKinds} 种不同的脚本组合。`,
    }));
    nodes.push(el('div', {
      class: 'consequence-line',
      text: `这一条的图块组合被 ${item.gfxShared} 条记录共用`
        + (others.length ? `（${others.map((r) => '#' + r.id).join(' ')}）` : '')
        + '。',
    }));
    nodes.push(el('div', {
      class: 'consequence-line',
      text: `改了它，那 ${item.gfxShared} 条记录会一起变。`
        + '载荷本身动不了 —— 改的只是「用哪一份」。',
    }));
    if (others.length) {
      nodes.push(el('button', {
        class: 'btn btn-tiny',
        text: '跳到共用它的记录',
        onclick: () => {
          this.groupKey = item.gfxKey;
          this.selected = others[0];
          this.renderList();
          this.renderDetail();
        },
      }));
    }
    return nodes;
  }

  fieldCtx() {
    const ctx = this.ctx;
    return {
      pack: ctx.pack,
      onChange: () => { if (ctx.onChange) ctx.onChange(); },
      onJump: ctx.onJump,
      onCommit: () => {
        clearPointerCache();
        // 只刷新会变的那几处：输入框不重建，焦点不丢。
        this.renderList();
        this.refreshTargets();
        this.rebuildConclusion();
      },
      registerRefresh: (fn) => { this.refreshers.push(fn); },
    };
  }

  step(delta) {
    const record = this.selected;
    if (!record) return;
    const records = this.table.records || [];
    const at = records.indexOf(record);
    const next = records[at + delta];
    if (!next) {
      toast(delta > 0 ? '已经是最后一条了' : '已经是第一条了', 'error');
      return;
    }
    this.selected = next;
    this.renderList();
    this.renderDetail();
  }
}

// --------------------------------------------------------------------------
// 视图三：指针接线总表（跨三张表的所有指针槽）
// --------------------------------------------------------------------------

export function renderPointerOverview(container, ctx, params = {}) {
  container.appendChild(pointerOverviewSection(ctx));
}

/** 域首页上的「指针接线总表」区块（可搜索）。 */
export function pointerOverviewSection(ctx) {
  return new PointerOverview(ctx).section();
}

class PointerOverview {
  constructor(ctx) {
    this.ctx = ctx;
    this.pack = ctx.pack;
    this.query = '';
    this._slots = null;
  }

  /** 所有指针槽：两张指针表 + 图块记录的 9 个槽。 */
  slots() {
    if (this._slots) return this._slots;
    const out = [];
    for (const id of [PTR_TABLE_A, PTR_TABLE_B]) {
      const table = this.pack.structure(id);
      if (!table) continue;
      const field = pointerField(table);
      if (!field) continue;
      for (const record of table.records || []) {
        out.push({
          table,
          record,
          key: field.key,
          slot: '#' + record.id,
        });
      }
    }
    const tile = this.pack.structure(TILE_RECORDS);
    if (tile) {
      for (const array of arraysIn(tile.fields || [])) {
        for (const [index, row] of array.rows) {
          const field = row.ptr || Object.values(row)[0];
          for (const record of tile.records || []) {
            out.push({
              table: tile,
              record,
              key: field.key,
              slot: `${ARRAY_TITLES[array.name] || array.name} ${index - array.base + 1}`,
            });
          }
        }
      }
    }
    this._slots = out;
    return out;
  }

  matches(slot) {    const query = (this.query || '').trim().toLowerCase();
    if (!query) return true;
    const value = slot.record.values[slot.key];
    if (valueMatches(value, query)) return true;
    if (String(slot.table.label || '').toLowerCase().includes(query)) return true;
    return slot.slot.toLowerCase().includes(query);
  }

  section() {
    const wrap = el('div', { class: 'section' });
    const slots = this.slots();
    wrap.appendChild(el('h3', { text: `指针接线总表（${slots.length} 个指针槽）` }));
    wrap.appendChild(el('p', {
      class: 'section-note',
      text: '两张指针表 + 图块记录的全部指针槽。搜索同时吃十六进制与十进制写法；'
        + '「同址」是全包里指向同一个地址的指针个数 —— 改一个，另外那些一起变。',
    }));
    const tableWrap = el('div', { class: 'table-wrap' });
    wrap.appendChild(el('div', { class: 'panel-tools' }, [
      el('input', {
        class: 'search',
        type: 'search',
        placeholder: '搜指针（0x0859F988 或 140114312 都行）',
        value: this.query,
        oninput: (e) => {
          this.query = e.target.value;
          this.renderTable(tableWrap);
        },
      }),
    ]));
    wrap.appendChild(tableWrap);
    this.renderTable(tableWrap);
    return wrap;
  }

  renderTable(tableWrap) {
    clear(tableWrap);
    const slots = this.slots().filter((slot) => this.matches(slot));
    const body = el('tbody');
    for (const slot of slots) {
      const value = slot.record.values[slot.key];
      const refs = value ? pointerRefs(this.pack, value) : [];
      const changed = recordChanged(this.pack, slot.table, slot.record);
      body.appendChild(el('tr', { class: changed ? 'changed' : '' }, [
        el('td', { text: slot.table.label || slot.table.id }),
        el('td', { class: 'col-id', text: slot.slot }),
        el('td', { class: 'mono', text: value ? hex32(value) : '空' }),
        el('td', { class: 'text-cell', text: targetSummary(this.pack, value) }),
        el('td', { class: 'col-num', text: refs.length > 1 ? String(refs.length) : '—' }),
        el('td', { text: changed ? '已改' : '—' }),
      ]));
    }
    tableWrap.appendChild(el('table', { class: 'grid' }, [
      el('thead', {}, [el('tr', {}, [
        el('th', { text: '表' }),
        el('th', { class: 'col-id', text: '槽' }),
        el('th', { text: '当前指针' }),
        el('th', { text: '目标' }),
        el('th', { class: 'col-num', text: '同址' }),
        el('th', { text: '改过' }),
      ])]),
      body,
    ]));
    tableWrap.appendChild(el('div', { class: 'table-foot' }, [
      el('span', { text: `显示 ${slots.length} / ${this.slots().length} 个指针槽` }),
    ]));
  }
}
