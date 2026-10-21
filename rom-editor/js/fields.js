// Field rendering: one place that knows what a field *means*.
//
// The content pack carries the semantics that used to live only in prose:
//   * `field.group`   — which section of the record this field belongs to
//   * `field.enum`    — the value domain, so a bare 0/1 can become 我方/敌方
//   * `field.relation`— this field is an id into another table, so the editor
//                       can show the *name* and offer a jump
//   * structure.raw_only — the whole record is undecoded bytes
//
// Everything here is driven by that metadata, so a new table gets sensible
// controls the moment the exporter describes it.

import { el, toast } from './ui.js';
import { readField } from './pack.js';
import { base64ToBytes, ROM_BASE } from './bytes.js';

/** The sibling field of the same array slot, e.g. slot0_category for slot0_item. */
export function siblingField(structure, field, item) {
  if (!structure || !field || !field.array) return null;
  return (structure.fields || []).find(
    (f) => f.array === field.array && f.index === field.index && f.item === item
  ) || null;
}

/**
 * Resolve a relation to a human name.
 *
 * @returns {{name: string, table: string}|null}
 */
export function resolveRelation(pack, relation, value) {
  if (!relation || value === null || value === undefined) return null;
  if (relation.kind === 'by_category') {
    return null;   // 需要先知道类别，见 resolveByCategory
  }
  const tableId = relation.table;
  if (!tableId) return null;
  if (relation.kind === 'text') {
    const table = pack.textTable(tableId);
    if (!table) return null;
    // 有些字段存的是**绝对地址**（如战斗目标的说明文字指针），
    // 有些存的是**槽位下标**（如角色 id）。按地址查要先按 pointer 找记录，
    // 拿地址当下标用只会阴差阳错地命中第 0 条。
    if (value >= ROM_BASE) {
      const hit = (table.records || []).find((r) => r.pointer === value);
      if (!hit || !hit.text) return null;
      return { name: hit.text, table: tableId, record: hit };
    }
    const record = table.records[value];
    if (!record || !record.text) return null;
    return { name: record.text, table: tableId, record };
  }
  if (relation.kind === 'structure') {
    const structure = pack.structure(tableId);
    if (!structure) return null;
    const record = structure.records[value];
    if (!record) return null;
    return { name: record.label ?? `#${record.id}`, table: tableId, record };
  }
  if (relation.kind === 'pointer') {
    // 指针型关系：字段存的是**地址**，要按记录所在的 ROM 地址去找
    // （音效描述符、乐曲头都是这种）。
    const structure = pack.structure(tableId);
    if (!structure) return null;
    const record = (structure.records || []).find((r) => r.rom_offset === value);
    if (!record) return null;
    return { name: record.label ?? `#${record.id}`, table: tableId, record };
  }
  if (relation.kind === 'row_range') {
    // 连续段基址：值是一段行的起点（每一关占 3 个子项那种）。
    const tables = relation.tables || [];
    for (const id of tables) {
      const structure = pack.structure(id);
      const textTable = pack.textTable(id);
      const list = structure ? structure.records : (textTable ? textTable.records : null);
      if (!list) continue;
      const record = list[value];
      if (!record) continue;
      const label = structure ? structure.label : textTable.label;
      return { name: `${label} #${value} 起 ${relation.count || 1} 条`, table: id, record };
    }
    return null;
  }
  return null;
}

/** The name of an item id whose table depends on a sibling category field. */
export function resolveByCategory(pack, structure, field, record) {
  const relation = field.relation;
  if (!relation || relation.kind !== 'by_category') return null;
  const catField = siblingField(structure, field, 'category');
  if (!catField) return null;
  const values = record.values || {};
  const cat = values[catField.key];
  if (cat === undefined || cat === null) return null;
  const tableId = (relation.categories || {})[String(cat)];
  if (!tableId) return null;
  const table = pack.textTable(tableId);
  if (!table) return null;
  const hit = table.records[values[field.key]];
  if (!hit || !hit.text) return null;
  return { name: hit.text, table: tableId };
}

/** The label for one enum value, or null when the value is outside the domain. */
export function enumLabel(field, value) {
  if (!field || !field.enum) return null;
  const hit = field.enum[String(value)];
  return hit === undefined ? null : hit;
}

/** Group the fields of a record by their `group`, keeping the original order. */
export function groupFields(fields) {
  const groups = [];
  const index = new Map();
  for (const field of fields || []) {
    const name = field.group || '其它';
    if (!index.has(name)) {
      index.set(name, { name, fields: [] });
      groups.push(index.get(name));
    }
    index.get(name).fields.push(field);
  }
  return groups;
}

/** True when every field of the structure is undecoded raw bytes. */
export function isRawOnly(structure) {
  if (!structure) return false;
  if (structure.raw_only) return true;
  const fields = structure.fields || [];
  return fields.length > 0 && fields.every((f) => f.type === 'hex');
}

/** The original value of a field, straight from the record's raw bytes. */
export function originalValue(structure, record, field) {
  if (!structure || !record || !field) return undefined;
  const raw = record.raw ? base64ToBytes(record.raw) : new Uint8Array(0);
  return readField(raw, field);
}

/**
 * A small, readable rendering of a pointer: the address plus what it points at.
 *
 * The pack does not know the meaning of every pointer, so this only reports
 * what can be proven: the file offset, and whether the target lands inside a
 * table the pack knows about.
 */
export function describePointer(pack, value) {
  if (!value) return { text: 'NULL', fileOffset: null, inside: null, target: null, payload: null };
  const offset = value - ROM_BASE;
  const inside = [];
  for (const structure of pack.structures || []) {
    const end = structure.rom_offset + (structure.entry_size || 0) * (structure.entry_count || 0);
    if (offset >= structure.rom_offset && offset < end) {
      inside.push(structure.label);
    }
  }
  for (const table of pack.texts || []) {
    if (!table.pointer_table_offset) continue;
    const end = table.pointer_table_offset + 4 * (table.count || 0);
    if (offset >= table.pointer_table_offset && offset < end) {
      inside.push(table.label);
    }
  }
  // 指针也可以指向一段文本的**数据区**（如战斗目标的说明文字），
  // 那时它不在任何指针表区间里，只能逐条记录比对。
  let target = null;
  for (const table of pack.texts || []) {
    for (const record of table.records || []) {
      if (record.text_offset === null || record.text_offset === undefined) continue;
      const end = record.text_offset + (record.capacity || 0);
      if (offset >= record.text_offset && offset < end) {
        target = { table: table.label, tableId: table.id, text: record.text, record };
        inside.push(table.label);
        break;
      }
    }
    if (target) break;
  }
  // 指针指向的**载荷是什么**，由导出时判定的事实给出（见 pack.derived）。
  // 没有载入原版 ROM 时也要能回答，所以这个判定不能只存在于运行时。
  const payload = pack.pointerTarget ? pack.pointerTarget(value) : null;
  return {
    text: '0x' + (value >>> 0).toString(16).toUpperCase(),
    fileOffset: offset >= 0 ? offset : null,
    inside: inside.length ? inside : null,
    target,
    payload,
  };
}

/**
 * One line that says what a pointer points at.
 *
 * The list shows `0x0859F988`; the author needs to know *what* that is.
 * The answer comes from the pack (a known structure's record, a text record,
 * or the payload kind the exporter worked out).
 */
export function pointerSummary(pack, value, field) {
  const described = describePointer(pack, value);
  if (!value) return '空指针（原版就是空的）';
  const parts = [];
  if (described.target) {
    parts.push(`${described.target.table} ·「${described.target.text}」`);
  } else if (described.inside) {
    parts.push(described.inside.join('、'));
  }
  if (field && field.ptr_kind === 'code') {
    // 代码指针：说「载荷是什么」是错的 —— 那是数据指针的说法。
    parts.push('代码地址');
  } else if (described.payload && described.payload.label) {
    parts.push(described.payload.label);
  }
  const where = described.fileOffset === null
    ? '不在 ROM 范围内'
    : 'ROM 0x' + described.fileOffset.toString(16).toUpperCase();
  return [where, ...parts].join(' · ');
}

/**
 * The legal value range of a numeric field.
 *
 * Without this check the write-back masks the value (`value & 0xff`), so
 * typing 999 into a u8 field would silently write 231 — the author would
 * believe their number is in the ROM.
 */
export function valueRange(field) {
  switch (field.type) {
    case 'u8': return { min: 0, max: 0xff, label: '0–255' };
    case 'u16': return { min: 0, max: 0xffff, label: '0–65535' };
    case 's16': return { min: -0x8000, max: 0x7fff, label: '−32768–32767' };
    case 'u32':
    case 'ptr': return { min: 0, max: 0xffffffff, label: '0–4294967295' };
    case 's32': return { min: -0x80000000, max: 0x7fffffff, label: '−2147483648–2147483647' };
    default: return null;
  }
}

/**
 * The lines shown under a field: what the value means, where it points, and
 * (when it is an id) the name it points at.
 */
export function fieldHint(pack, structure, record, field) {
  const hint = [];
  const value = record.values ? record.values[field.key] : undefined;
  if (field.type === 'ptr' && value) {
    const described = describePointer(pack, value);
    hint.push(`文件偏移 ${described.fileOffset === null ? '—' : '0x' + described.fileOffset.toString(16).toUpperCase()}`);
    if (described.target) {
      hint.push(`目标：${described.target.table} ·「${described.target.text}」`);
    } else if (described.inside) {
      hint.push(`落在：${described.inside.join('、')}`);
    }
    if (described.payload && described.payload.label && field.ptr_kind !== 'code') {
      // 载荷是什么（压缩块 / 原始数据 / 空哨兵）—— 导出时判定的事实。
      // 代码指针不能说「载荷」：那是数据指针的说法。
      hint.push(`载荷：${described.payload.label}`);
    } else if (field.ptr_kind === 'code') {
      hint.push('代码地址');
    }
  }
  if (field.relation) {
    const hit = resolveByCategory(pack, structure, field, record) ||
      resolveRelation(pack, field.relation, value);
    if (hit) hint.push(`${field.relation.label || '名称'}：${hit.name}`);
  }
  if (field.desc) hint.push(field.desc);
  if (field.not_read) {
    // 原生代码不读这一字节 —— 说清楚，免得作者白改。
    hint.unshift('原生代码不读这一字节：改它没有任何效果');
  }
  return hint;
}

/**
 * The name of a record, when the structure says its id *is* an id elsewhere.
 *
 * `structure.id_relation` means "the record index is an id in that other
 * table" — e.g. 忍术记录表 #5 is 忍术名表 #5.  The list then shows
 * 「忍者组合拳」instead of a bare number.
 */
export function idRelationName(pack, structure, record) {
  const relation = structure && structure.id_relation;
  if (!relation || !record) return null;
  if (relation.kind === 'text') {
    const table = pack.textTable(relation.table);
    if (!table) return null;
    const hit = table.records[record.id];
    return hit && hit.text ? hit.text : null;
  }
  if (relation.kind === 'structure') {
    const target = pack.structure(relation.table);
    if (!target) return null;
    const hit = target.records[record.id];
    return hit ? (hit.label ?? `#${hit.id}`) : null;
  }
  return null;
}

/**
 * The options of a relation field: [{ value, label }].
 *
 * A field that is an id into another table is shown as a **list with names**,
 * not as a bare number box — and an id that is outside the target table is
 * marked as such instead of silently showing nothing.
 */
export function relationOptions(pack, structure, record, field) {
  const relation = field && field.relation;
  if (!relation) return null;
  const values = record.values || {};
  const value = values[field.key];

  if (relation.kind === 'by_category') {
    const catField = siblingField(structure, field, 'category');
    if (!catField) return null;
    const cat = values[catField.key];
    const tableId = (relation.categories || {})[String(cat)];
    if (!tableId) return null;
    const table = pack.textTable(tableId);
    if (!table) return null;
    return table.records.map((r, i) => ({
      value: i,
      label: r.text || `（空 ${i}）`,
      outOfRange: false,
    }));
  }

  if (relation.kind === 'text') {
    const table = pack.textTable(relation.table);
    if (!table) return null;
    const options = table.records.map((r, i) => ({
      value: i,
      label: r.text || `（空 ${i}）`,
      outOfRange: false,
    }));
    if (value !== undefined && value !== null && value >= table.records.length) {
      options.push({
        value,
        label: `（越界：id ${value} > 表长 ${table.records.length}）`,
        outOfRange: true,
      });
    }
    return options;
  }

  if (relation.kind === 'pointer') {
    // 指针型关系：选项是「目标表的每条记录」，值是它所在的 ROM 地址。
    const structure = pack.structure(relation.table);
    if (!structure) return null;
    return (structure.records || []).map((r) => ({
      value: r.rom_offset,
      label: `${r.label ?? `#${r.id}`} · ROM 0x${(r.rom_offset >>> 0).toString(16).toUpperCase()}`,
      outOfRange: false,
    }));
  }
  return null;
}

/**
 * The control for one field.
 *
 * Returns { node, hint, link } — `node` is the input, `hint` the lines under
 * it, `link` a clickable jump to the record this field points at.
 */
export function fieldControl(ctx, structure, record, field) {
  const pack = ctx.pack;
  const values = record.values || {};
  const value = values[field.key];
  let node;

  const commit = (raw) => {
    let parsed = raw;
    if (field.type === 'ptr') {
      // 指针按**十六进制**输入。列表里显示的就是 `0x0859F988`，
      // 以前详情给的是十进制框（140114312）——同一屏两种写法，抄地址必然抄错。
      const text = String(raw).trim();
      const looksHex = /^0x/i.test(text) ||
        (/^[0-9a-fA-F]+$/.test(text) && /[a-fA-F]/.test(text));
      parsed = looksHex ? parseInt(text.replace(/^0x/i, ''), 16) : Number(text);
      if (!Number.isFinite(parsed)) {
        toast('请输入地址', 'error');
        return false;
      }
      if (parsed !== 0 && (parsed < ROM_BASE || parsed >= ROM_BASE + 0x600000)) {
        toast('指针必须为 0 或落在 0x08000000–0x085FFFFF 内', 'error');
        return false;
      }
    } else if (['u8', 'u16', 's16', 'u32', 's32'].includes(field.type)) {
      parsed = Number(raw);
      if (!Number.isFinite(parsed)) {
        toast('请输入数字', 'error');
        return false;
      }
      const range = valueRange(field);
      if (range && (parsed < range.min || parsed > range.max)) {
        // 越界必须**拒绝**，不能落到写回时的掩码里被悄悄截断。
        toast(`请输入 ${range.label} 的整数`, 'error');
        return false;
      }
    } else if (field.type === 'hex') {
      const clean = String(raw).replace(/[^0-9a-fA-F]/g, '');
      if (clean.length % 2) {
        toast('十六进制长度必须是偶数', 'error');
        return false;
      }
      if (field.size !== undefined && clean.length !== field.size * 2) {
        toast(`该字段固定 ${field.size} 字节（${field.size * 2} 个十六进制字符）`, 'error');
        return false;
      }
      parsed = clean;
    }
    ctx.pack.setValue(structure, record, field.key, parsed);
    ctx.onChange();
    if (ctx.onCommit) ctx.onCommit(structure, record, field);
    return true;
  };

  if (field.not_read) {
    // 原生代码**不读**这个字节：给出只读显示 + 说明，
    // 否则作者会白改一个没人读的字段（战场物件/阵营那一格就是这样）。
    node = el('input', {
      class: 'num-input not-read',
      type: 'text',
      disabled: true,
      value: value === undefined ? '' : String(value),
    });
  } else if (field.bits && field.bits.length) {
    // 位域：已知的位给下拉，其余位原样保留（只读显示）。
    const bits = field.bits;
    const wrap = el('div', { class: 'bit-field' });
    for (const bit of bits) {
      const current = (Number(value) & bit.mask) ? 1 : 0;
      const select = el('select', {
        class: 'num-input',
        onchange: (e) => {
          const next = Number(e.target.value) ? (Number(value) | bit.mask) : (Number(value) & ~bit.mask);
          if (!commit(next)) e.target.value = String(current);
        },
      });
      for (const [raw, label] of Object.entries(bit.enum || {})) {
        select.appendChild(el('option', {
          value: raw, text: label, selected: String(current) === raw,
        }));
      }
      wrap.appendChild(el('div', { class: 'bit-row' }, [
        el('span', { class: 'operand-label', text: bit.label }),
        select,
      ]));
    }
    const rest = Number(value) & ~bits.reduce((m, b) => m | b.mask, 0);
    wrap.appendChild(el('div', { class: 'bit-row' }, [
      el('span', { class: 'operand-label', text: '其余位' }),
      el('code', { class: 'bit-rest', text: '0x' + (rest >>> 0).toString(16).toUpperCase() }),
    ]));
    node = wrap;
  } else if (field.enum) {
    // 取值域已知 → 用下拉，标签直接是人话。
    const select = el('select', {
      class: 'num-input',
      onchange: (e) => {
        if (!commit(e.target.value)) e.target.value = String(value);
      },
    });
    for (const [raw, label] of Object.entries(field.enum)) {
      select.appendChild(el('option', {
        value: raw,
        text: `${label}`,
        selected: String(value) === raw,
      }));
    }
    // 值不在取值域里（ROM 里可能有未列出的取值）时，补一个原始值选项。
    if (value !== undefined && field.enum[String(value)] === undefined) {
      select.appendChild(el('option', {
        value: String(value), text: `${value}（取值域外）`, selected: true,
      }));
    }
    node = select;
  } else if (field.relation) {
    // 这个字段是另一张表的 id → 用「id · 名字」的下拉，而不是裸数字框。
    const options = relationOptions(pack, structure, record, field);
    if (options && options.length) {
      const select = el('select', {
        class: 'num-input',
        onchange: (e) => {
          if (!commit(e.target.value)) e.target.value = String(value ?? '');
        },
      });
      for (const option of options) {
        select.appendChild(el('option', {
          value: String(option.value),
          text: `${option.value} · ${option.label}`,
          selected: String(value) === String(option.value),
        }));
      }
      if (value !== undefined && !options.some((o) => String(o.value) === String(value))) {
        select.appendChild(el('option', {
          value: String(value),
          text: `${value}（越界）`,
          selected: true,
        }));
      }
      node = select;
    } else {
      node = el('input', {
        class: 'num-input',
        type: 'text',
        spellcheck: 'false',
        value: value === undefined ? '' : String(value),
        onchange: (e) => { if (!commit(e.target.value)) e.target.value = String(value ?? ''); },
      });
    }
  } else if (field.type === 'ptr') {
    // 指针：十六进制输入框 + 目标说明。列表与详情现在用同一种写法了。
    const hexText = value === undefined || value === null
      ? ''
      : '0x' + (value >>> 0).toString(16).toUpperCase().padStart(8, '0');
    node = el('input', {
      class: 'num-input ptr-box',
      type: 'text',
      spellcheck: 'false',
      value: hexText,
      onchange: (e) => {
        if (!commit(e.target.value)) {
          e.target.value = hexText;
          return;
        }
        const next = (record.values || {})[field.key];
        e.target.value = next === undefined || next === null
          ? ''
          : '0x' + (next >>> 0).toString(16).toUpperCase().padStart(8, '0');
      },
    });
  } else if (field.type === 'hex') {
    node = el('textarea', {
      class: 'hex-input',
      rows: 2,
      spellcheck: 'false',
      value: value === undefined ? '' : String(value),
      onchange: (e) => { if (!commit(e.target.value)) e.target.value = String(value ?? ''); },
    });
  } else {
    node = el('input', {
      class: 'num-input',
      type: 'text',
      spellcheck: 'false',
      value: value === undefined ? '' : String(value),
      onchange: (e) => { if (!commit(e.target.value)) e.target.value = String(value ?? ''); },
    });
  }

  return {
    node,
    hint: fieldHint(pack, structure, record, field),
    link: relationLink(ctx, structure, record, field),
  };
}
/**
 * A clickable link to the record this field points at.
 *
 * The pack knows the relation (「忍术 id 37 → 忍术名表第 37 条」), so the
 * author can jump straight to it instead of hunting for the id by hand.
 */
function relationLink(ctx, structure, record, field) {
  if (!field.relation || !ctx.onJump) return null;
  const value = record.values ? record.values[field.key] : undefined;
  const hit = resolveByCategory(ctx.pack, structure, field, record) ||
    resolveRelation(ctx.pack, field.relation, value);
  if (!hit) return null;
  const target = findTarget(ctx.pack, hit);
  if (!target) return null;
  return el('span', {
    class: 'xref-link',
    title: `跳到 ${target.label} · 记录 ${target.recordId}`,
    text: `跳到「${hit.name}」→`,
    onclick: () => ctx.onJump(target),
  });
}

/** Where a relation points: module + table + record. */
export function findTarget(pack, hit) {
  if (!hit || !hit.table) return null;
  const textTable = pack.textTable(hit.table);
  if (textTable) {
    const record = hit.record || (textTable.records || [])[0];
    return {
      module: textTable.module,
      kind: 'text',
      id: hit.table,
      recordId: record ? record.id : null,
      label: textTable.label || hit.table,
    };
  }
  const structure = pack.structure(hit.table);
  if (structure) {
    const record = hit.record || (structure.records || [])[0];
    return {
      module: structure.module,
      kind: 'structure',
      id: hit.table,
      recordId: record ? record.id : null,
      label: structure.label || hit.table,
    };
  }
  return null;
}