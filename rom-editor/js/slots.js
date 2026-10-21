// Repeated slots → one table.
//
// The pack marks repeated fields with `array` / `index` / `item`:
//   jutsu_7_id      → array=jutsu,  index=7, item=id
//   slot0_category  → array=slots, index=0, item=category
//   g1_2_type       → array=rules, index=6, item=type
//
// A group whose fields all belong to one array is therefore not "N×M input
// boxes" but **one table with N rows** — which is what the author actually
// wants to see (which slots are empty, which jutsu a character has).

import { el } from './ui.js';
import { fieldControl, fieldHint } from './fields.js';

/** What a repeated array is called, and what its columns mean. */
const ARRAY_NOUNS = {
  jutsu: '忍术',
  training: '技能',
  items: '忍具',
  slots: '道具位',
  rules: '条件',
  expr: '表情',
};

const ITEM_LABELS = {
  id: 'ID',
  value: '档位',
  unlock: '解锁等级',
  unlock_level: '解锁等级',
  pad: '填充',
  type: '类型',
  a: '参数A',
  b: '参数B',
  c: '参数C',
  text_ptr: '说明文字',
  category: '类别',
  item_id: '物品',
  gfx: '图像',
  palette: '配色',
};

/**
 * Split a group of fields into its repeated arrays.
 *
 * @returns {Array<{name: string, items: string[], rows: Map<number, object>}>}
 */
export function arraysIn(fields) {
  const byArray = new Map();
  for (const field of fields || []) {
    if (!field.array) continue;
    if (!byArray.has(field.array)) {
      byArray.set(field.array, { name: field.array, fields: new Map() });
    }
    const bucket = byArray.get(field.array);
    if (!bucket.fields.has(field.index)) bucket.fields.set(field.index, {});
    bucket.fields.get(field.index)[field.item] = field;
  }
  const out = [];
  for (const bucket of byArray.values()) {
    const indexes = [...bucket.fields.keys()].sort((a, b) => a - b);
    if (indexes.length < 2) continue;
    const itemNames = [];
    for (const index of indexes) {
      for (const item of Object.keys(bucket.fields.get(index))) {
        if (!itemNames.includes(item)) itemNames.push(item);
      }
    }
    // A "table" only makes sense when every row has the same columns.
    const uniform = indexes.every((index) => {
      const row = bucket.fields.get(index);
      return itemNames.every((item) => row[item]);
    });
    if (!uniform) continue;
    const rows = new Map();
    for (const index of indexes) {
      rows.set(index, bucket.fields.get(index));
    }
    out.push({ name: bucket.name, items: itemNames, rows, base: indexes[0] });
  }
  return out;
}

/**
 * The field objects that belong to a set of repeated arrays.
 *
 * @param {Array} arrays  from arraysIn()
 * @returns {Set<object>}
 */
export function arrayFields(arrays) {
  const out = new Set();
  for (const array of arrays || []) {
    for (const row of array.rows.values()) {
      for (const field of Object.values(row)) out.add(field);
    }
  }
  return out;
}

/** The column header of one item column. */
export function columnLabel(arrayName, item) {
  if (item === 'id') {
    const noun = ARRAY_NOUNS[arrayName];
    return noun ? noun : 'ID';
  }
  return ITEM_LABELS[item] || item;
}

/**
 * Render one repeated array as a table.
 *
 * @param {object} ctx      { pack, onChange }
 * @param {object} structure
 * @param {object} record
 * @param {object} array    from arraysIn()
 */
export function renderArrayTable(ctx, structure, record, array) {
  const table = el('table', { class: 'grid grid-slots' });
  table.appendChild(el('thead', {}, [
    el('tr', {}, [
      el('th', { class: 'col-id', text: '槽' }),
      ...array.items.map((item) =>
        el('th', { text: columnLabel(array.name, item) })),
    ]),
  ]));
  const body = el('tbody');
  for (const [index, row] of array.rows) {
    const tr = el('tr', {});
    tr.appendChild(el('td', { class: 'col-id', text: String(index - array.base + 1) }));
    for (const item of array.items) {
      const field = row[item];
      const { node, link } = fieldControl(ctx, structure, record, field);
      const cell = el('td', { class: 'slot-cell' }, [node]);
      const hintLine = el('div', { class: 'field-hint' });
      const refresh = () => {
        hintLine.textContent = fieldHint(ctx.pack, structure, record, field).join(' · ');
      };
      refresh();
      if (ctx.registerRefresh) ctx.registerRefresh(refresh);
      cell.appendChild(hintLine);
      if (link) cell.appendChild(el('div', { class: 'field-link' }, [link]));
      tr.appendChild(cell);
    }
    body.appendChild(tr);
  }
  table.appendChild(body);
  return el('div', { class: 'slot-table' }, [table]);
}
