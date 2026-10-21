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
  fieldControl, fieldHint, groupFields, idRelationName, isRawOnly, originalValue,
  resolveRelation, resolveByCategory, enumLabel,
} from './fields.js';
import { arraysIn, renderArrayTable, columnLabel, arrayFields } from './slots.js';
import { backReferences } from './xref.js';

const MAX_COLUMNS = 6;

/**
 * The pack's notes are written with markdown emphasis; the editor does not
 * render markdown, so the asterisks would show up literally.
 */
export function plainText(text) {
  return String(text || '').replace(/\*\*/g, '');
}

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
    const query = this.query.toLowerCase();
    // 搜索时**不受 200 行上限与「已归属」过滤**的限制：
    // 作者明确搜了一个词，就该看到全部命中，而不是前 200 条或空结果。
    const searching = !!this.query;
    const filtered = !query ? all : all.filter((r) => {
      if (String(r.id).toLowerCase().includes(query)) return true;
      if (r.label && String(r.label).toLowerCase().includes(query)) return true;
      // 记录名（id_relation）也要能搜到 —— 搜「分身术」应该找得到忍术 id 3。
      const name = idRelationName(this.pack, this.structure, r);
      if (name && name.toLowerCase().includes(query)) return true;
      return (r.values ? Object.values(r.values) : []).some(
        (v) => String(v).toLowerCase().includes(query)
      );
    });
    if (!searching) {
      return filtered;
    }
    return filtered;
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
    // 内容包里写好的表说明（分组规则、内联槽、同址另一种读法…）以前界面上
    // 一个字都看不到 —— 现在摆在面板头上。
    if (structure.note) {
      container.appendChild(el('div', { class: 'rule-note' }, [
        el('span', { class: 'rule-title', text: '这张表' }),
        el('span', { text: plainText(structure.note) }),
      ]));
    }
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
    const named = !!this.structure.id_relation;
    for (const record of records) {
      const dirty = this.isDirty(record);
      const name = idRelationName(this.pack, this.structure, record);
      const row = el('tr', {
        onclick: () => this.openDetail(record),
        class: (this.selected === record ? 'selected' : '') + (dirty ? ' changed' : ''),
      }, [
        el('td', { class: 'col-id', text: String(record.label ?? record.id) }),
        // 有 id_relation 的表，第一列之后多一列**名字** —— 列表里不再只有数字。
        named ? el('td', { class: 'name-cell', text: name || '（无名字）' }) : null,
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

    // 谁引用了这条记录 —— 改了它会动到谁。
    const refs = backReferences(this.pack, {
      kind: 'structure', id: structure.id, recordId: record.id,
    });
    if (refs.length) {
      this.detail.appendChild(el('div', { class: 'xref-block' }, [
        el('div', { class: 'xref-title', text: `被谁引用（${refs.length} 处）` }),
        el('div', { class: 'xref-hint', text: '改这条会同时影响下面这些地方。' }),
        ...refs.slice(0, 12).map((ref) => el('div', { class: 'xref-row' }, [
          el('span', { text: ref.label }),
          el('button', {
            class: 'btn btn-tiny',
            text: '跳过去',
            onclick: () => this.options.onJump
              ? this.options.onJump({
                module: ref.structure.module,
                kind: 'structure',
                id: ref.structure.id,
                recordId: ref.record.id,
                label: ref.structure.label,
              })
              : null,
          }),
        ])),
        refs.length > 12
          ? el('div', { class: 'xref-hint', text: `…还有 ${refs.length - 12} 处` })
          : null,
      ]));
    }

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
      onJump: this.options.onJump,
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
    const restore = el('button', {
      class: 'btn btn-tiny',
      text: '↺',
      title: '把这个字段恢复成原值',
      onclick: () => {
        const original = originalValue(structure, record, field);
        this.pack.setValue(structure, record, field.key, original);
        this.onChange();
        refresh();
        this.renderTable();
        toast(`已恢复「${field.label || field.key}」的原值 ${original}`);
      },
    });
    const offset = el('span', { class: 'field-offset', text: `+${formatOffset(field.offset)}` });
    label.appendChild(marker);
    label.appendChild(restore);
    label.appendChild(offset);

    const { node, link } = fieldControl(
      this.fieldContext(), structure, record, field);
    const hintLine = el('div', { class: 'field-hint' });

    const refresh = () => {
      const original = originalValue(structure, record, field);
      const current = record.values ? record.values[field.key] : undefined;
      const changed = JSON.stringify(original) !== JSON.stringify(current);
      wrapper.classList.toggle('field-changed', changed);
      marker.classList.toggle('hidden', !changed);
      restore.classList.toggle('hidden', !changed);
      const lines = fieldHint(this.pack, structure, record, field);
      if (changed) lines.push(`原值 ${original}`);
      hintLine.textContent = lines.join(' · ');
    };
    this.registerRefresh(refresh);
    refresh();

    wrapper.appendChild(label);
    wrapper.appendChild(node);
    wrapper.appendChild(hintLine);
    if (link) wrapper.appendChild(el('div', { class: 'field-link' }, [link]));
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
    this.limit = 200;          // 大表默认只渲染前 200 行
    this.showOwned = false;     // 是否显示「已被其它表拥有」的条目
    this.grouped = false;      // 是否按「空指针分隔」分组显示
  }

  /**
   * The groups of this table, split by the NULL separator slots.
   *
   * The dialogue pointer table is 1,524 slots = 305 groups of
   * 「one question + three options」, separated by a NULL pointer.  Showing the
   * slots flat forces the author to compute `5g + 2` by hand.
   */
  get groups() {
    const records = this.table.records || [];
    const groups = [];
    let current = [];
    for (const record of records) {
      if (record.text_offset === null || record.text_offset === undefined) {
        if (current.length) groups.push(current);
        current = [];
        continue;
      }
      current.push(record);
    }
    if (current.length) groups.push(current);
    return groups;
  }

  /** The table has separator slots → it is worth showing it as groups. */
  get hasGroups() {
    return this.groups.length > 1 && this.groups.length < (this.table.records || []).length;
  }

  get records() {
    const all = this.table.records || [];
    let list = all;
    // 搜索时**不套「已归属」过滤**：作者明确搜了一个词，就该看到全部命中
    // （否则搜「漩涡鸣人」在人物名表里明明有，却一条都不显示）。
    if (!this.showOwned && !this.query) {
      list = list.filter((r) => !r.owned_by);
    }
    if (this.query) {
      const q = this.query.toLowerCase();
      list = list.filter((r) => {
        if (String(r.id).toLowerCase().includes(q)) return true;
        if (r.label && String(r.label).toLowerCase().includes(q)) return true;
        return String(r.text ?? '').toLowerCase().includes(q);
      });
    }
    return list;
  }

  render(container) {
    clear(container);
    const table = this.table;
    container.appendChild(el('div', { class: 'panel-head' }, [
      el('div', {}, [
        el('h2', { text: table.label || table.id }),
        el('div', { class: 'panel-sub' }, [
          el('span', { text: `${(table.records || []).length} 条` }),
          el('span', { text: table.relocatable ? '可重定位' : '原地改写' }),
          table.pointer_table_offset !== undefined && table.pointer_table_offset !== null
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

    // 写回规则：这条文本改了会怎样，必须在动手前就说清楚。
    container.appendChild(el('div', { class: 'rule-note' }, [
      el('span', { class: 'rule-title', text: '写回规则' }),
      el('span', {
        text: this.table.relocatable
          ? '这条文本被指针表指向，长度可变。改短原地不动（指针不变）；改长会搬到 ROM 空闲区，并只改写它自己的指针。'
          : '这条文本被代码用绝对地址引用，长度不能变。改长了构建会拒绝，不会静默截断。',
      }),
    ]));
    // 表说明（分组规则、内联槽、同址另一种读法…）以前界面上一个字都看不到。
    if (this.table.note) {
      container.appendChild(el('div', { class: 'rule-note' }, [
        el('span', { class: 'rule-title', text: '这张表' }),
        el('span', { text: plainText(this.table.note) }),
      ]));
    }

    const wrap = el('div', { class: 'table-wrap' });
    const detail = el('div', { class: 'detail-panel hidden' });
    container.appendChild(el('div', { class: 'split' }, [wrap, detail]));
    this.wrap = wrap;
    this.detail = detail;
    this.renderTable();
  }

  /** The grouped view: one row per group of texts. */
  renderGroups() {
    clear(this.wrap);
    const groups = this.groups;
    const shown = groups.slice(0, this.limit);
    const grid = el('table', { class: 'grid grid-text' });
    grid.appendChild(el('thead', {}, [
      el('tr', {}, [
        el('th', { class: 'col-id', text: '组' }),
        el('th', { text: '内容' }),
        el('th', { class: 'col-num', text: '条数' }),
        el('th', { class: 'col-num', text: '写回字节' }),
        el('th', { text: '标记' }),
      ]),
    ]));
    const body = el('tbody');
    shown.forEach((group, index) => {
      const preview = group.map((r) => (r.text || '').replace(/\n/g, '↵')).join(' / ');
      const changed = group.some((r) => r.original_text !== undefined && r.original_text !== r.text);
      const bytes = group.reduce((n, r) => n + this.writeBackBytes(r), 0);
      const marks = group.flatMap((r) => this.marksFor(r));
      body.appendChild(el('tr', {
        class: changed ? 'changed' : '',
        onclick: () => this.openGroup(group, index),
      }, [
        el('td', { class: 'col-id', text: String(index + 1) }),
        el('td', { class: 'text-cell', text: preview || '（空）' }),
        el('td', { class: 'col-num', text: String(group.length) }),
        el('td', { class: 'col-num', text: String(bytes) }),
        el('td', { class: 'mark-cell' }, marks.map((m) =>
          el('span', { class: 'mark-chip ' + m.cls, title: m.title, text: m.text }))),
      ]));
    });
    grid.appendChild(body);
    this.wrap.appendChild(grid);
    this.wrap.appendChild(el('div', { class: 'table-foot' }, [
      el('span', { text: `显示 ${shown.length} / ${groups.length} 组（每组若干条，空指针分隔）` }),
    ]));
  }

  /** Open a group: the detail shows each text of the group in order. */
  openGroup(group, index) {
    this.selected = group[0];
    clear(this.detail);
    this.detail.classList.remove('hidden');
    this.detail.appendChild(el('div', { class: 'detail-head' }, [
      el('h3', { text: `${this.table.label || this.table.id} · 第 ${index + 1} 组` }),
      el('div', { class: 'detail-nav' }, [
        el('button', {
          class: 'btn btn-tiny', text: '← 上一组',
          onclick: () => this.openGroup(this.groups[index - 1], index - 1),
        }),
        el('button', {
          class: 'btn btn-tiny', text: '下一组 →',
          onclick: () => this.openGroup(this.groups[index + 1], index + 1),
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
      el('span', { text: `第 ${index + 1} / ${this.groups.length} 组` }),
      el('span', { text: `槽 ${group[0].id}..${group[group.length - 1].id}` }),
    ]));

    const form = el('div', { class: 'field-list' });
    group.forEach((record, i) => {
      form.appendChild(this.renderGroupEntry(record, i, group.length));
    });
    this.detail.appendChild(form);
  }

  /** One text of a group: 题干 / 选项 1..3。 */
  renderGroupEntry(record, index, total) {
    const label = total === 4
      ? (index === 0 ? '题干' : `选项 ${index}`)
      : `第 ${index + 1} 条`;
    const text = record.text ?? '';
    const changed = record.original_text !== undefined && record.original_text !== text;
    const counter = el('div', { class: 'text-counter' });
    const area = el('textarea', {
      class: 'text-input',
      rows: total === 4 ? 3 : 6,
      spellcheck: 'false',
      value: text,
      oninput: (e) => this.updateCount(record, counter, e.target.value),
      onchange: (e) => this.commit(record, area, e.target.value, counter),
    });
    this.updateCount(record, counter);
    return el('div', { class: 'field' + (changed ? ' field-changed' : '') }, [
      el('label', { class: 'field-label' }, [
        el('span', { text: label }),
        changed ? el('span', { class: 'tag tag-warn', text: '已改' }) : null,
        el('span', { class: 'field-offset', text: `槽 ${record.id}` }),
      ]),
      area,
      counter,
    ]);
  }

  renderTable() {
    clear(this.wrap);
    // 搜索时优先用平铺视图（作者在找某一条），没搜索且表本身有分隔槽时
    // 按组显示 —— 「一道题 + 三个选项」才是作者心里的单位。
    if (this.hasGroups && !this.query) return this.renderGroups();
    const all = this.records;
    // 搜索时把行数上限放宽（作者明确搜了词，就该看到全部命中）。
    const limit = this.query ? 2000 : this.limit;
    const shown = all.slice(0, limit);
    const grid = el('table', { class: 'grid grid-text' });
    grid.appendChild(el('thead', {}, [
      el('tr', {}, [
        el('th', { class: 'col-id', text: '#' }),
        el('th', { text: '文本' }),
        el('th', { class: 'col-num', text: '写回字节' }),
        el('th', { text: '标记' }),
      ]),
    ]));
    const body = el('tbody');
    for (const record of shown) {
      const text = record.text ?? '';
      const changed = record.original_text !== undefined && record.original_text !== text;
      const marks = this.marksFor(record);
      body.appendChild(el('tr', {
        class: changed ? 'changed' : '',
        onclick: () => this.openDetail(record),
      }, [
        el('td', { class: 'col-id', text: String(record.label ?? record.id) }),
        el('td', { class: 'text-cell', text: text.replace(/\n/g, '↵') || '（空）' }),
        el('td', { class: 'col-num', text: this.writeBackBytes(record) }),
        el('td', { class: 'mark-cell' }, marks.map((m) =>
          el('span', { class: 'mark-chip ' + m.cls, title: m.title, text: m.text }))),
      ]));
    }
    grid.appendChild(body);
    this.wrap.appendChild(grid);
    if (!all.length) {
      this.wrap.appendChild(el('div', { class: 'empty', text: '没有匹配的记录' }));
    }
    const foot = el('div', { class: 'table-foot' }, [
      el('span', { text: `显示 ${shown.length} / ${all.length} 条` }),
      all.length > shown.length
        ? el('button', {
          class: 'btn btn-tiny', text: '显示全部',
          onclick: () => { this.limit = all.length; this.renderTable(); },
        })
        : null,
      el('span', { class: 'mark-cell' }, [
        el('label', { class: 'check' }, [
          el('input', {
            type: 'checkbox',
            checked: this.showOwned,
            onchange: (e) => { this.showOwned = e.target.checked; this.renderTable(); },
          }),
          el('span', { text: '显示已被其它表拥有的条目' }),
        ]),
      ]),
    ]);
    this.wrap.appendChild(foot);
  }

  /** The markers that explain a record's state at a glance. */
  marksFor(record) {
    const marks = [];
    if (record.text_offset === null || record.text_offset === undefined) {
      marks.push({ cls: 'mark-none', text: '⊘ 无位置', title: '这个槽位在 ROM 里没有文字（分组用的空指针），写不进去。' });
    }
    if (record.owned_by) {
      marks.push({
        cls: 'mark-owned',
        text: `已归属 ${record.owned_by}`,
        title: '这段字节属于另一张表，在那里改才不会互相覆盖。',
      });
    }
    if (record.shared_with && record.shared_with.length) {
      marks.push({
        cls: 'mark-shared',
        text: `共享 ${record.shared_with.length + 1} 处`,
        title: `这段字有 ${record.shared_with.length + 1} 个位置共用（同一个字符串），改一处会一起变。`,
      });
    }
    const ctrl = this.controlCodeCount(record);
    if (ctrl > 0) {
      marks.push({ cls: 'mark-ctrl', text: `控制码 ×${ctrl}`, title: '控制码带着换行/分页的排版含义，写回时按原位保留。' });
    }
    if (record.original_text !== undefined && record.original_text !== record.text) {
      marks.push({ cls: 'mark-dirty', text: '已改', title: '这条文本被改过。' });
    }
    return marks;
  }

  /** The bytes this record would be written as (same source as the builder). */
  writeBackBytes(record) {
    if (record.text_offset === null || record.text_offset === undefined) return '—';
    return String(this.pack.textBytes(record).length);
  }

  openDetail(record) {
    this.selected = record;
    clear(this.detail);
    this.detail.classList.remove('hidden');
    const table = this.table;

    this.detail.appendChild(el('div', { class: 'detail-head' }, [
      el('h3', { text: `${table.label || table.id} · ${record.label ?? record.id}` }),
      el('div', { class: 'detail-nav' }, [
        el('button', { class: 'btn btn-tiny', text: '← 上一条', onclick: () => this.step(-1) }),
        el('button', { class: 'btn btn-tiny', text: '下一条 →', onclick: () => this.step(1) }),
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

    const meta = el('div', { class: 'detail-sub' });
    if (record.text_offset !== null && record.text_offset !== undefined) {
      meta.appendChild(el('span', { text: `文本 ROM ${formatOffset(record.text_offset)}` }));
    }
    if (record.pointer_offset !== null && record.pointer_offset !== undefined) {
      meta.appendChild(el('span', { text: `指针槽 ${formatOffset(record.pointer_offset)}` }));
    }
    if (record.capacity) meta.appendChild(el('span', { text: `槽位 ${record.capacity} 字节` }));
    this.detail.appendChild(meta);

    if (record.owned_by) {
      this.detail.appendChild(el('div', { class: 'rule-note rule-warn' }, [
        el('span', { class: 'rule-title', text: '归属' }),
        el('span', { text: `这段字节属于 ${record.owned_by}。在那边改才不会互相覆盖。` }),
      ]));
    }
    if (record.shared_with && record.shared_with.length) {
      this.detail.appendChild(el('div', { class: 'rule-note rule-warn' }, [
        el('span', { class: 'rule-title', text: '共用' }),
        el('span', {
          text: `这段字有 ${record.shared_with.length + 1} 个位置共用（同一个字符串）：` +
            `本表 #${record.shared_with.slice(0, 8).join(' #')}` +
            `${record.shared_with.length > 8 ? ' …' : ''}。改这里会一起变。`,
        }),
      ]));
    }

    // 控制码分段条：文本框里看不见控制码，但它们决定新文字落在哪。
    this.detail.appendChild(this.renderSegments(record));

    const writable = record.text_offset !== null && record.text_offset !== undefined;
    const area = el('textarea', {
      class: 'text-input',
      rows: 8,
      spellcheck: 'false',
      value: record.text ?? '',
      disabled: !writable,
      oninput: (e) => this.updateCount(record, counter, e.target.value),
      onchange: (e) => this.commit(record, area, e.target.value, counter),
    });

    const counter = el('div', { class: 'text-counter' });
    this.detail.appendChild(el('div', { class: 'field' }, [
      el('label', { class: 'field-label' }, [
        el('span', { text: '文本' }),
        el('span', { class: 'field-offset', text: '改完失焦即保存（Ctrl+Enter 也可以）' }),
      ]),
      area,
      counter,
    ]));
    this.updateCount(record, counter);

    if (record.original_text !== undefined) {
      this.detail.appendChild(el('div', { class: 'field' }, [
        el('label', { class: 'field-label' }, [el('span', { text: '原版文本' })]),
        el('div', { class: 'text-original', text: record.original_text || '（空）' }),
      ]));
    }

    this.detail.appendChild(el('div', { class: 'field-hint' }, [
      '文本在 ROM 里是字形码流；控制码 0x01/0x02 带着换行/分页的排版含义，',
      '文本框里看不到它们，但写回时会按原位置保留（走 token 流，不用纯字符串编码）。',
      '要改控制码本身，请用「原始字节」模块。',
    ]));

    this.detail.appendChild(el('div', { class: 'detail-actions' }, [
      el('button', {
        class: 'btn btn-ghost',
        text: '恢复原文',
        onclick: () => {
          // 字节级还原：从原始字节重新扫 token，而不是把原文字符串
          // 合并回**已经被改过**的 token 流（那会把控制码挪到句中）。
          this.pack.resetText(this.table, record);
          this.openDetail(record);
          this.renderTable();
          this.options.onChange && this.options.onChange();
          toast('已恢复原文（逐字节一致）');
        },
      }),
    ]));
  }

  /** Move to the previous / next record. */
  step(delta) {
    const records = this.records;
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

  /**
   * The control-code segmentation bar.
   *
   * The text box cannot show the control codes, but they decide where a new
   * character lands: the writer splits the new text across the original runs,
   * so the segments are shown as chips between the text runs.
   */
  renderSegments(record) {
    const tokens = this.pack.textTokens(record);
    const bar = el('div', { class: 'text-segments' });
    let run = [];
    const flush = () => {
      if (!run.length) return;
      const text = run.map((t) => (t.c === 10 ? '⏎' : String.fromCharCode(t.c))).join('');
      bar.appendChild(el('span', { class: 'seg-text', text }));
      run = [];
    };
    for (const token of tokens) {
      if (token.k === 'c') {
        flush();
        bar.appendChild(el('span', {
          class: 'seg-ctrl',
          title: '控制码 0x' + token.b.map((b) => b.toString(16).padStart(2, '0')).join(' ') +
            '：原文就在这里，写回时按原位保留。要改它请用「原始字节」模块。',
          text: '⟦控制码 ' + token.b.map((b) => b.toString(16).padStart(2, '0')).join(' ') + '⟧',
        }));
      } else {
        run.push(token);
      }
    }
    flush();
    if (!bar.children.length) {
      bar.appendChild(el('span', { class: 'seg-text', text: '（没有控制码）' }));
    }
    return el('div', { class: 'field' }, [
      el('label', { class: 'field-label' }, [
        el('span', { text: '控制码分段' }),
        el('span', { class: 'field-offset', text: '新文字按原分段切分，控制码不动' }),
      ]),
      bar,
    ]);
  }

  /** Write the edited text into the pack. */
  commit(record, area, value, counter) {
    if (record.text_offset === null || record.text_offset === undefined) {
      toast('这个槽位在 ROM 里没有文字（分组用的空指针），写不进去', 'error');
      area.value = record.text ?? '';
      return;
    }
    const missing = this.pack.font.missingCharacters(value);
    if (missing.length) {
      toast(`字库里没有这些字：${missing.join(' ')}`, 'error');
      area.value = record.text ?? '';
      return;
    }
    // 等长表超长**当场拦**：以前只在构建时才炸，界面上照样说「已保存」。
    if (!this.table.relocatable && record.capacity) {
      const nul = this.table.nul_terminated === false ? 0 : 1;
      const bytes = this.pack.font.encodedLength(value);
      if (bytes + nul > record.capacity) {
        toast(
          `这条只有 ${record.capacity} 字节的定长槽，放不下（需要 ${bytes + nul} 字节）。` +
          '请改成短一点的文字。',
          'error'
        );
        area.value = record.text ?? '';
        return;
      }
    }
    this.pack.setText(this.table, record, value);
    this.updateCount(record, counter);
    this.renderTable();
    this.options.onChange && this.options.onChange();
    toast('已保存');
  }

  updateCount(record, counter, draft) {
    if (!counter) return;
    const value = draft === undefined ? (record.text ?? '') : draft;
    // 字节数必须与**写回路径**同源：pack.textBytes（token 编码），
    // 而不是字符串编码器 —— 两者对 ASCII 与控制码给出的数不一样。
    const bytes = this.pack.font.encodedLength(value);
    clear(counter);
    counter.appendChild(el('span', { text: `编码后 ${bytes} 字节` }));
    if (record.capacity && record.text_offset !== null && record.text_offset !== undefined) {
      const nul = this.table.nul_terminated === false ? 0 : 1;
      const over = bytes + nul > record.capacity;
      counter.appendChild(el('span', {
        class: over ? 'bad' : 'ok',
        // 可重定位的表**写得进去**（超长会搬到空闲区并改写指针），
        // 以前这里一律说「放不下」，作者于是白白把字删短。
        text: over
          ? (this.table.relocatable
            ? ` · 变长 ${bytes + nul} 字节（槽位 ${record.capacity}）：写得进去，` +
              '构建时会搬到空闲区并改写指针'
            : ` · 放不下：写回需要 ${bytes + nul} 字节，槽位只有 ${record.capacity} 字节` +
              '（只能等长改写，请删掉几个字）')
          : ` · 槽位 ${record.capacity} 字节` +
            (this.table.relocatable ? '（放得下，变长会重定位）' : '（放得下）'),
      }));
    }
    const missing = this.pack.font.missingCharacters(value);
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
