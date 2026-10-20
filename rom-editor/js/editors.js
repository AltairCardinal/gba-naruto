// Generic, data-driven editors.
//
// Every structure and every text table in the pack is rendered by these two
// components, so a new ROM structure becomes editable the moment the exporter
// describes it — no new UI code.  The per-domain modules (剧情 / 道具 /
// 角色 / 忍术 / 战斗 / 路线) are curated views that pick the structures they
// care about and add domain-specific framing.

import { el, clear, formatHex32, formatOffset, toast } from './ui.js';
import { readField, writeField } from './pack.js';
import { bytesToBase64, base64ToBytes, bytesToHex, ROM_BASE } from './bytes.js';

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
  }

  get records() {
    const all = this.structure.records || [];
    if (!this.query) return all;
    const q = this.query.toLowerCase();
    return all.filter((r) => {
      if (String(r.id).toLowerCase().includes(q)) return true;
      if (r.label && String(r.label).toLowerCase().includes(q)) return true;
      return (r.values ? Object.values(r.values) : []).some(
        (v) => String(v).toLowerCase().includes(q)
      );
    });
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
      const row = el('tr', {
        onclick: () => this.openDetail(record),
        class: this.selected === record ? 'selected' : '',
      }, [
        el('td', { class: 'col-id', text: String(record.label ?? record.id) }),
        ...fields.map((f) => el('td', { text: formatCell(record, f) })),
        el('td', { class: 'col-actions' }, [
          el('button', {
            class: 'btn btn-tiny',
            text: '编辑',
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
    this.tableWrap.appendChild(
      el('div', { class: 'table-foot', text: `显示 ${records.length} / ${(structure.records || []).length} 条` })
    );
  }

  openDetail(record) {
    this.selected = record;
    clear(this.detail);
    this.detail.classList.remove('hidden');
    const structure = this.structure;

    this.detail.appendChild(el('div', { class: 'detail-head' }, [
      el('h3', { text: `${structure.label || structure.id} · ${record.label ?? record.id}` }),
      el('button', {
        class: 'btn btn-ghost',
        text: '✕',
        onclick: () => {
          this.detail.classList.add('hidden');
          this.selected = null;
          this.renderTable();
        },
      }),
    ]));

    this.detail.appendChild(el('div', { class: 'detail-sub', text: `ROM ${formatOffset(record.rom_offset)}` }));

    const form = el('div', { class: 'field-list' });
    for (const field of structure.fields || []) {
      form.appendChild(this.renderField(record, field));
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

  renderField(record, field) {
    const structure = this.structure;
    const value = record.values ? record.values[field.key] : undefined;
    const wrapper = el('div', { class: 'field' });

    const label = el('label', { class: 'field-label' }, [
      el('span', { text: field.label || field.key }),
      el('span', { class: 'field-offset', text: `+${formatOffset(field.offset)}` }),
    ]);

    let control;
    const commit = (raw) => {
      let parsed = raw;
      if (field.type === 'u8' || field.type === 'u16' || field.type === 's16' ||
          field.type === 'u32' || field.type === 's32') {
        parsed = Number(raw);
        if (!Number.isFinite(parsed)) {
          toast('请输入数字', 'error');
          return;
        }
      } else if (field.type === 'ptr') {
        parsed = Number(raw);
        if (!Number.isFinite(parsed)) {
          toast('请输入数字或 0', 'error');
          return;
        }
        if (parsed !== 0 && (parsed < ROM_BASE || parsed >= ROM_BASE + 0x600000)) {
          toast('指针必须为 0 或落在 0x08000000–0x085FFFFF 内', 'error');
          return;
        }
      } else if (field.type === 'hex') {
        const clean = String(raw).replace(/[^0-9a-fA-F]/g, '');
        if (clean.length % 2) {
          toast('十六进制长度必须是偶数', 'error');
          return;
        }
        if (field.size !== undefined && clean.length !== field.size * 2) {
          toast(`该字段固定 ${field.size} 字节（${field.size * 2} 个十六进制字符）`, 'error');
          return;
        }
        parsed = clean;
      }
      this.pack.setValue(structure, record, field.key, parsed);
      this.renderTable();
      this.onChange();
    };

    if (field.type === 'hex') {
      control = el('textarea', {
        class: 'hex-input',
        rows: 2,
        spellcheck: 'false',
        value: value === undefined ? '' : String(value),
        onchange: (e) => commit(e.target.value),
      });
    } else {
      control = el('input', {
        class: 'num-input',
        type: 'text',
        spellcheck: 'false',
        value: value === undefined ? '' : String(value),
        onchange: (e) => commit(e.target.value),
      });
    }

    const hint = [];
    if (field.type === 'ptr' && value) {
      hint.push(`文件偏移 ${formatOffset(value - ROM_BASE)}`);
    }
    if (field.desc) hint.push(field.desc);

    wrapper.appendChild(label);
    wrapper.appendChild(control);
    if (hint.length) {
      wrapper.appendChild(el('div', { class: 'field-hint', text: hint.join(' · ') }));
    }
    return wrapper;
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
  }
}

export function defaultColumns(structure) {
  const fields = structure.fields || [];
  const preferred = structure.primary_columns || [];
  const picked = preferred.filter((key) => fields.some((f) => f.key === key));
  if (picked.length) return picked.slice(0, MAX_COLUMNS);
  return fields.slice(0, 5).map((f) => f.key);
}

function formatCell(record, field) {
  const value = record.values ? record.values[field.key] : undefined;
  if (value === undefined || value === null) return '';
  if (field.type === 'ptr') return formatHex32(value);
  if (field.type === 'hex') return String(value).slice(0, 12) + (String(value).length > 12 ? '…' : '');
  return String(value);
}
