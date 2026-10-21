// Generic, data-driven editors.
//
// Every structure and every text table in the pack is rendered by these two
// components, so a new ROM structure becomes editable the moment the exporter
// describes it — no new UI code.  The per-domain modules (剧情 / 道具 /
// 角色 / 忍术 / 战斗 / 路线) are curated views that pick the structures they
// care about and add domain-specific framing.
//
// The editors are driven by the *semantics the pack carries*:
//   * `field.group`    → the record is presented as collapsible sections
//   * `field.enum`     → a bare 0/1 becomes 我方/敌方
//   * `field.relation` → an id is shown with the name it points at
//   * `structure.raw_only` → a table nobody decoded is one hex box, not 16
// (see js/fields.js for the metadata layer itself.)

import { el, clear, formatHex32, formatOffset, toast } from './ui.js';
import { readField } from './pack.js';
import { bytesToBase64, base64ToBytes, bytesToHex } from './bytes.js';
import {
  fieldControl, fieldHint, groupFields, isRawOnly, originalValue, resolveRelation,
  resolveByCategory, enumLabel,
} from './fields.js';
import { arraysIn, renderArrayTable, columnLabel, arrayFields } from './slots.js';

const MAX_COLUMNS = 6;

export class StructureEditor {
  /**
   * @param {ContentPack} pack
   * @param {object} structure  pack structure descriptor
   * @param {object} options   { columns, onChange, title }
   */
  constructor(pack, structure, options = {}) {
    this.pack = pack;
    this.structure = structure;
    this.options = options;
    this.query = '';
    this.selected = null;
    this.columns = options.columns || defaultColumns(structure);
    this.onChange = options.onChange || (() => {});
    /** 分组折叠状态：默认展开「有主列的分组」与「第一张槽位表」。 */
    this.collapsed = new Set();
    this.groups = groupFields(structure.fields);
    this.refreshers = [];
    this.openDefaultGroups(structure);
    this.jumpTo = '';
  }

  /**
   * Which groups are open when a record is first shown.
   *
   * Opening *everything* would put the author back into the 175-row form, and
   * opening *nothing* would show an empty panel.  The rule: open the groups
   * that carry the structure's primary columns (the author comes here to
   * change those); everything else stays collapsed, with its size in the
   * section header so nothing is hidden invisibly.
   */
  openDefaultGroups(structure) {
    const primary = new Set(structure.primary_columns || []);
    const withPrimary = this.groups.filter((g) =>
      g.fields.some((f) => primary.has(f.key)));
    const open = new Set();
    for (const group of withPrimary) open.add(group.name);
    if (!open.size && this.groups.length) open.add(this.groups[0].name);
    for (const group of this.groups) {
      if (!open.has(group.name)) this.collapsed.add(group.name);
    }
  }

  get records() {
    const all = this.structure.records || [];
    if (!this.query) return all;
    const q = this.query.toLowerCase();
    return all.filter((r) => {
      if (String(r.id).toLowerCase().includes(q)) return true;
      if (r.label && String(r.label).includes(q)) return true;
      return (r.values ? Object.values(r.values) : []).some(
        (v) => String(v).toLowerCase().includes(q)
      );
    });
  }

  /** 这条记录相对原版是否被改过。 */
  isDirty(record) {
    const bytes = this.pack.recordBytes(this.structure, record);
    const raw = base64ToBytes(record.raw || '');
    return bytesToBase64(bytes) !== bytesToBase64(raw);
  }

  render(container) {
    clear(container);
    const structure = this.structure;

    const head = el('div', { class: 'panel-head' }, [
      el('div', {}, [
        el('h2', { text: structure.label || structure.id }),
        el('div', { class: 'panel-sub' }, [
          el('span', { text: `ROM ${formatOffset(structure.rom_offset)}` }),
          el('span', { text: `${structure.entry_size || 0} 字节/条` }),
          el('span', { text: `${(structure.records || []).length} 条` }),
          structure.verification ? el('span', { text: structure.verification }) : null,
        ]),
      ]),
      el('div', { class: 'panel-tools' }, [
        el('input', {
          class: 'search',
          type: 'search',
          placeholder: '搜索…',
          value: this.query,
          oninput: (e) => {
            this.query = e.target.value;
            this.renderTable();
          },
        }),
        el('input', {
          class: 'num-input',
          type: 'text',
          style: { width: '86px' },
          placeholder: '跳到 id',
          value: this.jumpTo,
          onchange: (e) => {
            this.jumpTo = e.target.value;
            const id = Number(e.target.value);
            const record = (structure.records || []).find((r) => r.id === id);
            if (!record) {
              toast(`没有 id 为 ${e.target.value} 的记录`, 'error');
              return;
            }
            this.openDetail(record);
          },
        }),
        el('button', {
          class: 'btn btn-ghost',
          text: '列设置',
          onclick: () => this.openColumnPicker(),
        }),
      ]),
    ]);

    const tableWrap = el('div', { class: 'table-wrap' });
    const detail = el('div', { class: 'detail-panel hidden' });

    container.appendChild(head);
    container.appendChild(el('div', { class: 'split' }, [tableWrap, detail]));
    this.tableWrap = tableWrap;
    this.detail = detail;
    this.renderTable();
  }

  renderTable() {
    clear(this.tableWrap);
    const structure = this.structure;
    const fields = this.columns
      .map((key) => (structure.fields || []).find((f) => f.key === key))
      .filter(Boolean);

    const table = el('table', { class: 'grid' });
    table.appendChild(el('thead', {}, [
      el('tr', {}, [
        el('th', { class: 'col-id', text: '#' }),
        ...fields.map((f) => el('th', { text: f.label || f.key })),
        el('th', { class: 'col-actions', text: '' }),
      ]),
    ]));

    const body = el('tbody');
    const records = this.records;
    for (const record of records) {
      const dirty = this.isDirty(record);
      const row = el('tr', {
        onclick: () => this.openDetail(record),
        class: (this.selected === record ? 'selected' : '') + (dirty ? ' changed' : ''),
      }, [
        el('td', { class: 'col-id', text: String(record.label ?? record.id) }),
        ...fields.map((f) => el('td', { text: this.formatCell(record, f) })),
        el('td', { class: 'col-actions' }, [
          el('button', {
            class: 'btn btn-tiny',
            text: dirty ? '已改' : '编辑',
            onclick: (e) => {
              e.stopPropagation();
              this.openDetail(record);
            },
          }),
        ]),
      ]);
      body.appendChild(row);
    }
    table.appendChild(body);
    this.tableWrap.appendChild(table);
    if (!records.length) {
      this.tableWrap.appendChild(el('div', { class: 'empty', text: '没有匹配的记录' }));
    }
    const dirtyCount = (structure.records || []).filter((r) => this.isDirty(r)).length;
    this.tableWrap.appendChild(
      el('div', { class: 'table-foot' }, [
        el('span', { text: `显示 ${records.length} / ${(structure.records || []).length} 条` }),
        dirtyCount ? el('span', { class: 'tag tag-warn', text: `已改 ${dirtyCount} 条` }) : null,
      ])
    );
  }

  /**
   * The cell text: numbers as numbers, pointers as hex, and — when the field
   * points at another table — the *name* it points at, not the raw id.
   */
  formatCell(record, field) {
    const value = record.values ? record.values[field.key] : undefined;
    if (value === undefined || value === null) return '';
    if (field.type === 'ptr') return formatHex32(value);
    if (field.type === 'hex') {
      const text = String(value);
      return text.slice(0, 12) + (text.length > 12 ? '…' : '');
    }
    const label = enumLabel(field, value);
    if (label) return `${value} · ${label}`;
    const hit = resolveByCategory(this.pack, this.structure, field, record) ||
      resolveRelation(this.pack, field.relation, value);
    if (hit) return `${value} · ${hit.name}`;
    return String(value);
  }

  openDetail(record) {
    this.selected = record;
    this.refreshers = [];
    clear(this.detail);
    this.detail.classList.remove('hidden');
    const structure = this.structure;

    this.detail.appendChild(el('div', { class: 'detail-head' }, [
      el('h3', { text: `${structure.label || structure.id} · ${record.label ?? record.id}` }),
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
            this.detail.classList.add('hidden');
            this.selected = null;
            this.renderTable();
          },
        }),
      ]),
    ]));

    this.detail.appendChild(el('div', { class: 'detail-sub' }, [
      el('span', { text: `ROM ${formatOffset(record.rom_offset)}` }),
      el('span', { text: `第 ${record.id + 1} / ${(structure.records || []).length} 条` }),
      this.isDirty(record) ? el('span', { class: 'tag tag-warn', text: '已改动' }) : null,
    ]));

    const form = el('div', { class: 'field-list' });
    if (isRawOnly(structure)) {
      form.appendChild(this.renderRawRecord(record));
    } else {
      for (const group of this.groups) {
        form.appendChild(this.renderGroup(group, record));
      }
    }
    this.detail.appendChild(form);

    this.detail.appendChild(el('div', { class: 'detail-actions' }, [
      el('button', {
        class: 'btn btn-ghost',
        text: '恢复原值',
        onclick: () => {
          const original = base64ToBytes(record.raw || '');
          const values = {};
          for (const field of structure.fields || []) {
            values[field.key] = readField(original, field);
          }
          record.values = values;
          this.pack.dirty.add(`${structure.id}#${record.id}`);
          this.openDetail(record);
          this.renderTable();
          this.onChange();
        },
      }),
      el('button', {
        class: 'btn btn-ghost',
        text: '复制十六进制',
        onclick: () => {
          const bytes = this.pack.recordBytes(structure, record);
          navigator.clipboard?.writeText(bytesToHex(bytes));
          toast('已复制该记录的十六进制字节');
        },
      }),
    ]));
  }

  /** Move to the previous / next record. */
  step(delta) {
    const records = this.structure.records || [];
    if (!this.selected) {
      if (records.length) this.openDetail(records[0]);
      return;
    }
    const at = records.indexOf(this.selected);
    const next = records[at + delta];
    if (!next) {
      toast(delta > 0 ? '已经是最后一条了' : '已经是第一条了', 'error');
      return;
    }
    this.openDetail(next);
  }

  /** One collapsible section: a group of fields. */
  renderGroup(group, record) {
    const collapsed = this.collapsed.has(group.name);
    const section = el('div', { class: 'group' + (collapsed ? ' collapsed' : '') });
    const head = el('button', {
      class: 'group-head',
      onclick: () => {
        if (this.collapsed.has(group.name)) this.collapsed.delete(group.name);
        else this.collapsed.add(group.name);
        this.openDetail(record);
      },
    }, [
      el('span', { class: 'group-caret', text: collapsed ? '▸' : '▾' }),
      el('span', { class: 'group-name', text: group.name }),
      el('span', { class: 'group-count', text: `${group.fields.length} 项` }),
    ]);
    section.appendChild(head);
    if (!collapsed) {
      const body = el('div', { class: 'group-body' });
      // 重复槽位（忍术 15 / 技能 24 / 奖励 8 / 条件 4 …）渲染成一张表，
      // 而不是 N×M 个输入框。
      const arrays = arraysIn(group.fields);
      const inArray = arrayFields(arrays);
      for (const array of arrays) {
        body.appendChild(el('div', { class: 'slot-block' }, [
          el('div', { class: 'slot-caption', text: `${columnLabel(array.name, 'id')}列表（${array.rows.size} 项）` }),
          renderArrayTable(this.fieldContext(), this.structure, record, array),
        ]));
      }
      for (const field of group.fields) {
        if (inArray.has(field)) continue;
        body.appendChild(this.renderField(record, field));
      }
      section.appendChild(body);
    }
    return section;
  }

  /**
   * The context handed to the shared field controls.
   *
   * `onCommit` runs after a value is written: it refreshes the *local*
   * markers (the 「已改」 tag, the 原值 line, the slot table hints) and the
   * record list, without rebuilding the whole detail panel — rebuilding it
   * would throw away the author's focus and scroll position.
   */
  fieldContext() {
    return {
      pack: this.pack,
      onChange: this.onChange,
      onCommit: () => {
        for (const refresh of this.refreshers) refresh();
        this.renderTable();
      },
      registerRefresh: (fn) => this.refreshers.push(fn),
    };
  }

  /** Register a local refresher (called after every commit). */
  registerRefresh(fn) {
    this.refreshers.push(fn);
  }

  renderField(record, field) {
    const structure = this.structure;
    const wrapper = el('div', { class: 'field' });
    const label = el('label', { class: 'field-label' }, [
      el('span', { text: field.label || field.key }),
    ]);
    const marker = el('span', { class: 'tag tag-warn', text: '已改' });
    const offset = el('span', { class: 'field-offset', text: `+${formatOffset(field.offset)}` });
    label.appendChild(marker);
    label.appendChild(offset);

    const { node } = fieldControl(
      this.fieldContext(), structure, record, field);
    const hintLine = el('div', { class: 'field-hint' });

    const refresh = () => {
      const original = originalValue(structure, record, field);
      const current = record.values ? record.values[field.key] : undefined;
      const changed = JSON.stringify(original) !== JSON.stringify(current);
      wrapper.classList.toggle('field-changed', changed);
      marker.classList.toggle('hidden', !changed);
      const lines = fieldHint(this.pack, structure, record, field);
      if (changed) lines.push(`原值 ${original}`);
      hintLine.textContent = lines.join(' · ');
    };
    this.registerRefresh(refresh);
    refresh();

    wrapper.appendChild(label);
    wrapper.appendChild(node);
    wrapper.appendChild(hintLine);
    return wrapper;
  }

  /**
   * A record whose fields nobody decoded: one hex box for the whole record
   * instead of sixteen one-byte boxes.
   */
  renderRawRecord(record) {
    const structure = this.structure;
    const fields = structure.fields || [];
    const bytes = base64ToBytes(record.raw || '');
    const hex = bytesToHex(bytes);
    const area = el('textarea', {
      class: 'hex-input',
      rows: 4,
      spellcheck: 'false',
      value: hex,
      onchange: (e) => {
        const clean = String(e.target.value).replace(/[^0-9a-fA-F]/g, '');
        if (clean.length !== hex.length) {
          toast(`这条记录固定 ${hex.length / 2} 字节（${hex.length} 个十六进制字符）`, 'error');
          e.target.value = hex;
          return;
        }
        const next = base64ToBytes(clean);
        for (let i = 0; i < fields.length; i++) {
          const field = fields[i];
          const value = readField(next, field);
          this.pack.setValue(structure, record, field.key, value);
        }
        this.openDetail(record);
        this.renderTable();
        this.onChange();
      },
    });
    return el('div', { class: 'field field-raw' }, [
      el('label', { class: 'field-label' }, [
        el('span', { text: '整条记录的字节' }),
        el('span', { class: 'field-offset', text: `${bytes.length} 字节` }),
      ]),
      area,
      el('div', { class: 'field-hint' }, [
        '这张表的字段语义**尚未证明**，所以整条记录按原始字节编辑；',
        '改这里等于直接改 ROM 里的这串字节。',
      ]),
    ]);
  }

  openColumnPicker() {
    const structure = this.structure;
    const checks = (structure.fields || []).map((field) =>
      el('label', { class: 'check' }, [
        el('input', {
          type: 'checkbox',
          checked: this.columns.includes(field.key),
          onchange: (e) => {
            const set = new Set(this.columns);
            if (e.target.checked) set.add(field.key);
            else set.delete(field.key);
            this.columns = [...set].slice(0, MAX_COLUMNS);
            this.renderTable();
          },
        }),
        el('span', { text: field.label || field.key }),
      ])
    );
    const body = el('div', { class: 'column-picker' }, checks);
    const overlay = el('div', { class: 'modal-overlay' }, [
      el('div', { class: 'modal' }, [
        el('div', { class: 'modal-title', text: '选择显示列（最多 6 列）' }),
        el('div', { class: 'modal-body' }, [body]),
        el('div', { class: 'modal-actions' }, [
          el('button', { class: 'btn btn-primary', text: '完成', onclick: () => overlay.remove() }),
        ]),
      ]),
    ]);
    document.body.appendChild(overlay);
  }
}

export class TextTableEditor {
  /**
   * @param {ContentPack} pack
   * @param {object} table  pack text-table descriptor
   * @param {object} options { onChange, showIds }
   */
  constructor(pack, table, options = {}) {
    this.pack = pack;
    this.table = table;
    this.options = options;
    this.query = '';
    this.selected = null;
  }

  get records() {
    const all = this.table.records || [];
    if (!this.query) return all;
    const q = this.query.toLowerCase();
    return all.filter((r) => {
      if (String(r.id).toLowerCase().includes(q)) return true;
      if (r.label && String(r.label).toLowerCase().includes(q)) return true;
      return String(r.text ?? '').toLowerCase().includes(q);
    });
  }

  render(container) {
    clear(container);
    const table = this.table;
    container.appendChild(el('div', { class: 'panel-head' }, [
      el('div', {}, [
        el('h2', { text: table.label || table.id }),
        el('div', { class: 'panel-sub' }, [
          el('span', { text: `${(table.records || []).length} 条` }),
          table.relocatable ? el('span', { text: '可重定位' }) : el('span', { text: '原地改写' }),
          table.pointer_table_offset !== undefined
            ? el('span', { text: `指针表 ${formatOffset(table.pointer_table_offset)}` })
            : null,
        ]),
      ]),
      el('div', { class: 'panel-tools' }, [
        el('input', {
          class: 'search',
          type: 'search',
          placeholder: '搜索文本…',
          value: this.query,
          oninput: (e) => {
            this.query = e.target.value;
            this.renderTable();
          },
        }),
      ]),
    ]));

    const wrap = el('div', { class: 'table-wrap' });
    const detail = el('div', { class: 'detail-panel hidden' });
    container.appendChild(el('div', { class: 'split' }, [wrap, detail]));
    this.wrap = wrap;
    this.detail = detail;
    this.renderTable();
  }

  renderTable() {
    clear(this.wrap);
    const grid = el('table', { class: 'grid grid-text' });
    grid.appendChild(el('thead', {}, [
      el('tr', {}, [
        el('th', { class: 'col-id', text: '#' }),
        el('th', { text: '文本' }),
        el('th', { class: 'col-num', text: '字节' }),
      ]),
    ]));
    const body = el('tbody');
    for (const record of this.records) {
      const text = record.text ?? '';
      const changed = record.original_text !== undefined && record.original_text !== text;
      body.appendChild(el('tr', {
        class: changed ? 'changed' : '',
        onclick: () => this.openDetail(record),
      }, [
        el('td', { class: 'col-id', text: String(record.label ?? record.id) }),
        el('td', { class: 'text-cell', text: text.replace(/\n/g, '↵') || '（空）' }),
        el('td', { class: 'col-num', text: String(this.pack.font.encodedLength(text)) }),
      ]));
    }
    grid.appendChild(body);
    this.wrap.appendChild(grid);
    if (!this.records.length) {
      this.wrap.appendChild(el('div', { class: 'empty', text: '没有匹配的记录' }));
    }
    this.wrap.appendChild(
      el('div', { class: 'table-foot', text: `显示 ${this.records.length} / ${(this.table.records || []).length} 条` })
    );
  }

  openDetail(record) {
    this.selected = record;
    clear(this.detail);
    this.detail.classList.remove('hidden');

    this.detail.appendChild(el('div', { class: 'detail-head' }, [
      el('h3', { text: `${this.table.label || this.table.id} · ${record.label ?? record.id}` }),
      el('button', {
        class: 'btn btn-ghost', text: '✕',
        onclick: () => {
          this.detail.classList.add('hidden');
          this.selected = null;
          this.renderTable();
        },
      }),
    ]));

    const meta = el('div', { class: 'detail-sub' });
    if (record.text_offset !== null && record.text_offset !== undefined) {
      meta.appendChild(el('span', { text: `文本 ROM ${formatOffset(record.text_offset)}` }));
    }
    if (record.pointer_offset !== null && record.pointer_offset !== undefined) {
      meta.appendChild(el('span', { text: `指针槽 ${formatOffset(record.pointer_offset)}` }));
    }
    if (record.capacity) meta.appendChild(el('span', { text: `槽位 ${record.capacity} 字节` }));
    this.detail.appendChild(meta);

    const area = el('textarea', {
      class: 'text-input',
      rows: 8,
      spellcheck: 'false',
      value: record.text ?? '',
      oninput: (e) => {
        this.pack.setText(this.table, record, e.target.value);
        this.updateCount(record, area);
        this.renderTable();
        this.options.onChange && this.options.onChange();
      },
    });

    const counter = el('div', { class: 'text-counter' });
    this.detail.appendChild(el('div', { class: 'field' }, [
      el('label', { class: 'field-label' }, [el('span', { text: '文本' })]),
      area,
      counter,
    ]));
    this.updateCount(record, area);

    if (record.original_text !== undefined) {
      this.detail.appendChild(el('div', { class: 'field' }, [
        el('label', { class: 'field-label' }, [el('span', { text: '原版文本' })]),
        el('div', { class: 'text-original', text: record.original_text || '（空）' }),
      ]));
    }

    this.detail.appendChild(el('div', { class: 'field-hint' }, [
      '文本在 ROM 里是**字形码流**；控制码 0x01/0x02 带着换行/分页的排版含义，',
      '文本框里看不到它们，但写回时会按原位置保留（走 token 流，不用纯字符串编码）。',
      '要改控制码本身，请用「原始字节」模块。',
    ]));

    this.detail.appendChild(el('div', { class: 'detail-actions' }, [
      el('button', {
        class: 'btn btn-ghost',
        text: '恢复原文',
        onclick: () => {
          this.pack.setText(this.table, record, record.original_text ?? '');
          this.openDetail(record);
          this.renderTable();
          this.options.onChange && this.options.onChange();
        },
      }),
    ]));
  }

  updateCount(record, area) {
    const counter = area.parentElement.querySelector('.text-counter');
    if (!counter) return;
    const bytes = this.pack.font.encodedLength(record.text ?? '');
    const missing = this.pack.font.missingCharacters(record.text ?? '');
    clear(counter);
    counter.appendChild(el('span', { text: `编码后 ${bytes} 字节` }));
    if (record.capacity) {
      const over = bytes + (this.table.nul_terminated === false ? 0 : 1) > record.capacity;
      counter.appendChild(el('span', {
        class: over ? 'bad' : 'ok',
        text: over ? ` · 超出槽位 ${record.capacity} 字节` : ` · 槽位 ${record.capacity} 字节`,
      }));
    }
    if (missing.length) {
      counter.appendChild(el('span', {
        class: 'bad',
        text: ` · 字库缺字: ${missing.join('')}`,
      }));
    }
    // 控制码：文本框里看不到，但它们带着换行/分页的排版含义，
    // 写回时会被原样保留（走 token 流，不走纯字符串编码）。
    const ctrl = this.controlCodeCount(record);
    if (ctrl > 0) {
      counter.appendChild(el('span', {
        class: 'ok',
        title: '控制码 0x01/0x02 带着换行/分页的排版含义，编辑文本时按原位置保留',
        text: ` · 含 ${ctrl} 个控制码（已保留）`,
      }));
    }
  }

  /** 这条文本里有多少个控制码。 */
  controlCodeCount(record) {
    const tokens = this.pack.textTokens(record);
    let n = 0;
    for (const token of tokens) if (token.k === 'c') n += 1;
    return n;
  }
}

export function defaultColumns(structure) {
  const fields = structure.fields || [];
  const preferred = structure.primary_columns || [];
  const picked = preferred.filter((key) => fields.some((f) => f.key === key));
  if (picked.length) return picked.slice(0, MAX_COLUMNS);
  return fields.slice(0, 5).map((f) => f.key);
}
