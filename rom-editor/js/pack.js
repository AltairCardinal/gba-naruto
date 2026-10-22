// Content pack model.
//
// The pack is the editor's *initial data*: a complete, self-describing dump of
// every editable structure in the original ROM.  Two invariants hold:
//
//   1. Every record keeps its original bytes (`raw`) next to the decoded
//      `values`.  The builder re-encodes the known fields and keeps the
//      unknown bytes verbatim — the repo's established write-back model
//      ("copy the native record, overwrite only known fields, keep the rest").
//   2. The field list of every structure TILES its record exactly: known
//      fields plus `hex` filler fields for every byte nobody has decoded yet.
//      So an untouched pack rebuilds the original ROM byte for byte.

import { bytesToBase64, base64ToBytes, bytesToHex, hexToBytes, readUint, readInt, writeUint } from './bytes.js';
import { FontCodec, scanTokens, encodeTokens, mergeTokens } from './textcodec.js';

export const FIELD_TYPES = {
  u8: { size: 1, label: 'u8' },
  u16: { size: 2, label: 'u16' },
  s16: { size: 2, label: 'i16' },
  u32: { size: 4, label: 'u32' },
  s32: { size: 4, label: 'i32' },
  ptr: { size: 4, label: 'ROM指针' },
  hex: { size: null, label: '原始字节' },
};

export class ContentPack {
  constructor(data) {
    this.format = data.format || 'naruto-konoha-content-pack';
    this.version = data.version || 1;
    this.generated = data.generated || null;
    this.rom = data.rom || {};
    this.structures = data.structures || [];
    this.texts = data.texts || [];
    this.scripts = data.scripts || [];
    this.patches = data.patches || [];
    this.font = new FontCodec(
      (data.font && data.font.code_to_char) || {},
      (data.font && data.font.char_to_code) || null
    );
    this.dirty = new Set();
    /**
     * The undo stack (this session only — it is not part of the exported pack).
     *
     * One entry per change, holding the *previous* value, so undo restores
     * exactly what was there before.  The stack is bounded so a long session
     * cannot grow without limit.
     */
    this.undoStack = [];
    this.notes = data.notes || [];
    /**
     * Derived facts the exporter worked out about the ROM (pointer payload
     * kinds, shared bytes, …).  They are **read-only** facts, not records:
     * anything the builder would have to write back must live in
     * `structures` / `texts` / `patches`, because `rom.js` only writes those.
     */
    this.derived = data.derived || null;
    /**
     * Battle-map asset descriptors (cell size, tile counts, block offsets …).
     *
     * Like `derived`, these are **read-only** facts about the ROM's map
     * graphics — the pixels themselves live in a separate binary
     * (`content/maps/maps.bin.gz`) that the map view fetches on demand, so
     * that the editor still works without loading the ROM.  Nothing here is
     * written back: `rom.js` only writes `structures` / `texts` / `patches`.
     */
    this.map_assets = data.map_assets || null;
    /**
     * 谁关心「内容包变了」。
     *
     * `onChange()`（app.js 那个）只标脏，**不重绘** —— 所以靠它刷新界面是不行的。
     * 页签的角标（「这一类改了几处」）需要在每次写入后立刻跟上，
     * 这里给一条通知通路：写完就通知，界面自己决定要不要重画。
     */
    this.changeListeners = [];
  }

  /**
   * 订阅「内容包变了」。
   *
   * @param {() => void} fn
   * @returns {() => void} 退订函数
   */
  onChange(fn) {
    if (typeof fn !== 'function') return () => {};
    this.changeListeners.push(fn);
    return () => {
      const at = this.changeListeners.indexOf(fn);
      if (at >= 0) this.changeListeners.splice(at, 1);
    };
  }

  /** 通知所有订阅者（写完之后调）。 */
  notifyChanged() {
    for (const fn of this.changeListeners.slice()) {
      try {
        fn();
      } catch (err) {
        /* 订阅者出错不许影响写回 */
      }
    }
  }

  /**
   * What does this ROM address point at?
   *
   * @param {number} address  a ROM address (0x08xxxxxx)
   * @returns {?{kind: string, label: string, size: ?number}}
   */
  pointerTarget(address) {
    if (!this.derived || !this.derived.pointer_targets) return null;
    if (!address) return null;
    const key = '0x' + (address >>> 0).toString(16).toUpperCase().padStart(8, '0');
    return this.derived.pointer_targets[key] || null;
  }

  /** Undo stack limit. */
  static UNDO_LIMIT = 100;

  /** Remember the previous value of one change so it can be undone. */
  pushUndo(entry) {
    this.undoStack.push(entry);
    if (this.undoStack.length > ContentPack.UNDO_LIMIT) {
      this.undoStack.shift();
    }
  }

  get canUndo() {
    return this.undoStack.length > 0;
  }

  get undoDepth() {
    return this.undoStack.length;
  }

  /**
   * Undo the most recent change.
   *
   * @returns {boolean} whether something was undone
   */
  undo() {
    const entry = this.undoStack.pop();
    if (!entry) return false;
    if (entry.kind === 'value') {
      entry.record.values[entry.key] = entry.before;
      this.dirty.add(`${entry.structure.id}#${entry.record.id}`);
    } else if (entry.kind === 'text') {
      entry.record.tokens = entry.before.tokens;
      entry.record.text = entry.before.text;
      if (entry.before.original !== undefined) {
        entry.record.original_text = entry.before.original;
      }
      delete entry.record.text_changed;
      this.dirty.add(`${entry.table.id}#${entry.record.id}`);
    } else if (entry.kind === 'operand') {
      // 剧情脚本里的定宽操作数：操作数本身与补丁的 after_hex 都要回去，
      // 否则撤销之后 ROM 里还是新值。
      entry.operand.value = entry.before;
      if (entry.patch) {
        if (entry.previousAfter === null) {
          this.removePatch(entry.patch);
        } else {
          entry.patch.after_hex = entry.previousAfter;
        }
      }
      this.dirty.delete(`operand.${entry.operand.rom_offset.toString(16)}`);
    } else if (entry.kind === 'patch') {
      // 显式补丁的撤销：把 after_hex 恢复回去（补丁仍在，但不再算改动）。
      if (entry.patch) {
        if (entry.previousAfter === null || entry.previousAfter === undefined) {
          this.removePatch(entry.patch);
        } else {
          entry.patch.after_hex = entry.previousAfter;
        }
      }
      if (entry.offset !== undefined) {
        this.dirty.delete(`patch.${entry.offset.toString(16)}`);
      }
    }
    this.notifyChanged();
    return true;
  }

  static fromJSON(data) {
    return new ContentPack(data);
  }

  toJSON() {
    return {
      format: this.format,
      version: this.version,
      generated: this.generated,
      rom: this.rom,
      font: {
        code_to_char: Object.fromEntries(this.font.codeToChar),
        char_to_code: Object.fromEntries(this.font.charToCode),
      },
      structures: this.structures,
      texts: this.texts,
      scripts: this.scripts,
      patches: this.patches,
      notes: this.notes,
    };
  }

  structure(id) {
    return this.structures.find((s) => s.id === id) || null;
  }

  textTable(id) {
    return this.texts.find((t) => t.id === id) || null;
  }

  structuresForModule(module) {
    return this.structures.filter((s) => s.module === module);
  }

  textsForModule(module) {
    return this.texts.filter((t) => t.module === module);
  }

  // --- record helpers -------------------------------------------------

  /**
   * Re-encode one record: start from the original bytes, overlay every field
   * the author changed.  Bytes nobody decoded keep their original value.
   */
  recordBytes(structure, record) {
    const size = structure.entry_size || record.raw_bytes || 0;
    const bytes = new Uint8Array(size);
    const raw = record.raw ? base64ToBytes(record.raw) : new Uint8Array(size);
    bytes.set(raw.subarray(0, size), 0);

    for (const field of structure.fields || []) {
      if (!(field.key in (record.values || {}))) continue;
      const value = record.values[field.key];
      writeField(bytes, field, value);
    }
    return bytes;
  }

  setValue(structure, record, key, value) {
    if (!record.values) record.values = {};
    const before = record.values[key];
    if (before === value) return;
    this.pushUndo({
      kind: 'value',
      structure,
      record,
      key,
      before,
      after: value,
    });
    record.values[key] = value;
    this.dirty.add(`${structure.id}#${record.id}`);
    this.notifyChanged();
  }

  /**
   * Rewrite one text record.
   *
   * The write-back goes through the **token stream**, never through the
   * decoded string: the control codes 0x01/0x02 carry layout meaning
   * (line breaks, page breaks) and the decoded string does not contain them,
   * so a plain string encode would silently destroy the layout.  The original
   * bytes are kept in `record.raw`, so the control codes can be re-scanned
   * and re-inserted at their original positions.
   *
   * When several records of the same table point at the **same bytes** (the
   * task-title table has 27 slots sharing one blank string), they are really
   * one string: editing one of them edits all of them, otherwise the build
   * would write the same address twice and one of the two changes would
   * vanish.
   */
  setText(table, record, text) {
    const tokens = this.textTokens(record);
    const newTokens = this.font.encodeTokens(text);
    this.pushUndo({
      kind: 'text',
      table,
      record,
      before: {
        text: record.text,
        tokens: tokens.slice(),
        original: record.original_text,
      },
      after: { text, tokens: newTokens },
    });
    record.tokens = mergeTokens(tokens, newTokens);
    record.text = text;
    record.text_changed = true;
    this.dirty.add(`${table.id}#${record.id}`);
    for (const other of this.sharingBytes(table, record)) {
      other.tokens = mergeTokens(this.textTokens(other), this.font.encodeTokens(text));
      other.text = text;
      other.text_changed = true;
      this.dirty.add(`${table.id}#${other.id}`);
    }
    this.notifyChanged();
  }

  /** The other records of `table` that live at the same ROM address. */
  sharingBytes(table, record) {
    if (!table || !record || record.text_offset === null ||
        record.text_offset === undefined) {
      return [];
    }
    return (table.records || []).filter(
      (r) => r !== record && r.text_offset === record.text_offset
    );
  }

  /**
   * Restore a text record to its original **bytes**.
   *
   * Merging the original string back into an already-modified token stream
   * would move the control codes (the text comes back, the bytes do not),
   * so the original bytes are re-scanned instead.
   */
  resetText(table, record) {
    const raw = record.raw ? base64ToBytes(record.raw) : new Uint8Array(0);
    this.pushUndo({
      kind: 'text',
      table,
      record,
      before: {
        text: record.text,
        tokens: this.textTokens(record).slice(),
        original: record.original_text,
      },
      after: { text: record.text, tokens: scanTokens(raw) },
    });
    record.tokens = scanTokens(raw);
    record.text = this.font.decode(raw);
    record.original_text = record.text;
    delete record.text_changed;
    this.dirty.add(`${table.id}#${record.id}`);
    for (const other of this.sharingBytes(table, record)) {
      other.tokens = scanTokens(raw);
      other.text = record.text;
      other.original_text = record.text;
      delete other.text_changed;
      this.dirty.add(`${table.id}#${other.id}`);
    }
    this.notifyChanged();
  }

  /** The original token stream of a text record (control codes included). */
  textTokens(record) {
    if (record.tokens) return record.tokens;
    const raw = record.raw ? base64ToBytes(record.raw) : new Uint8Array(0);
    record.tokens = scanTokens(raw);
    return record.tokens;
  }

  /**
   * The bytes a text record currently encodes to.
   *
   * Fixed-slot records (the inline speaker-name table) carry zero padding
   * after the string; the padding is restored so the record keeps its shape.
   */
  textBytes(record) {
    const bytes = encodeTokens(this.textTokens(record));
    const original = record.raw ? base64ToBytes(record.raw) : new Uint8Array(0);
    if (bytes.length < original.length) {
      const padded = new Uint8Array(original.length);
      padded.set(bytes, 0);
      return padded;
    }
    return bytes;
  }

  /**
   * The bytes a text record encodes to, **without** the slot padding.
   *
   * The capacity check has to use this: a 4-byte name in a 12-byte slot
   * writes 12 bytes but only *needs* 5 (4 + NUL); comparing the padded
   * length against the slot would report every such record as too long.
   */
  textContentBytes(record) {
    return encodeTokens(this.textTokens(record));
  }

  /**
   * Rewrite one story-VM operand.
   *
   * The operand is a proved fixed-width field inside a script, so writing it
   * in place cannot move a byte and cannot invalidate the script's branch
   * targets.  The change is recorded as an explicit patch (same mechanism the
   * raw hex editor uses), so the builder verifies the original bytes before
   * writing.
   */
  setScriptOperand(operand, value) {
    let after;
    if (operand.size === 1) {
      after = new Uint8Array([Number(value) & 0xff]);
    } else if (operand.size === 2) {
      const v = Number(value) & 0xffff;
      after = new Uint8Array([v & 0xff, (v >> 8) & 0xff]);
    } else {
      after = hexToBytes(String(value));
    }
    const before = hexToBytes(operand.before_hex || '');
    // 撤销要知道「改之前补丁长什么样」：改之前没有这条补丁，就把它删回去。
    const existed = (this.patches || []).some((p) => p.offset === operand.rom_offset);
    const patch = this.ensurePatch(operand.rom_offset, before);
    const previousAfter = existed ? (patch.after_hex || '') : null;
    // 补丁清单里要看得懂这是什么改动 —— 以前一律写「手动修改 0x…」。
    patch.label = operand.label
      ? `${operand.label}（0x${operand.rom_offset.toString(16).toUpperCase()}）`
      : `剧情脚本操作数 0x${operand.rom_offset.toString(16).toUpperCase()}`;
    patch.after_hex = bytesToHex(after);
    this.dirty.add(`operand.${operand.rom_offset.toString(16)}`);
    // 撤销：操作数本身与补丁的 after_hex 都要回去，
    // 否则按 Ctrl+Z 之后 ROM 里还是新值、改动计数也不回落。
    if (operand.value !== undefined && Number(operand.value) !== Number(value)) {
      this.pushUndo({
        kind: 'operand',
        operand,
        before: operand.value,
        patch,
        previousAfter,
      });
    }
    operand.value = value;
    this.notifyChanged();
    return patch;
  }

  /**
   * Write bytes at an address as an explicit patch (with undo).
   *
   * 剧情脚本里的对白是**内联在脚本字节流里**的：改它就是改那一段字节。
   * 脚本里的分支目标是**绝对地址**，所以改长改短都会让后面的指令移位、
   * 分支全部失效 —— 调用方必须保证新旧字节数**一样**（原地写）。
   *
   * @param {number} offset      文件偏移
   * @param {string} beforeHex   改之前的字节（十六进制）
   * @param {string} afterHex    改之后的字节（十六进制），长度必须与 before 相同
   * @param {string} label       补丁清单上显示的名字
   */
  setBytesAt(offset, beforeHex, afterHex, label) {
    const patch = this.ensurePatch(offset, hexToBytes(beforeHex || ''));
    const previousAfter = patch.after_hex;
    patch.after_hex = afterHex;
    if (label) patch.label = label;
    this.dirty.add(`patch.${offset.toString(16)}`);
    this.pushUndo({
      kind: 'patch',
      patch,
      previousAfter,
      offset,
    });
    this.notifyChanged();
    return patch;
  }

  /** Find or create the explicit patch covering `offset`. */
  ensurePatch(offset, beforeBytes) {    for (const patch of this.patches) {
      const after = hexToBytes(patch.after_hex || '');
      if (offset >= patch.offset && offset < patch.offset + after.length) return patch;
    }
    const patch = {
      id: `raw.${offset.toString(16)}`,
      offset,
      before_hex: bytesToHex(beforeBytes || new Uint8Array(0)),
      after_hex: bytesToHex(beforeBytes || new Uint8Array(0)),
      label: `手动修改 0x${offset.toString(16).toUpperCase()}`,
    };
    this.patches.push(patch);
    return patch;
  }

  /** How many records differ from the original bytes. */
  changedCount() {
    let n = 0;
    for (const structure of this.structures) {
      for (const record of structure.records || []) {
        const bytes = this.recordBytes(structure, record);
        const raw = base64ToBytes(record.raw || '');
        if (bytesToBase64(bytes) !== bytesToBase64(raw)) n += 1;
      }
    }
    for (const table of this.texts) {
      for (const record of table.records || []) {
        if (record.text !== undefined && record.text !== record.original_text) n += 1;
      }
    }
    // 显式补丁（原始字节 / 剧情操作数）也是改动 —— 以前它们不进计数，
    // 顶栏徽标对这类改动完全不响应，改了等于隐形。
    n += this.changedPatchCount();
    return n;
  }

  /** How many patches actually change something. */
  changedPatchCount() {
    let n = 0;
    for (const patch of this.patches || []) {
      if ((patch.after_hex || '') !== (patch.before_hex || '')) n += 1;
    }
    return n;
  }

  /** Drop a patch (the author changed his mind). */
  removePatch(patch) {
    const at = (this.patches || []).indexOf(patch);
    if (at >= 0) this.patches.splice(at, 1);
  }

  /**
   * The structure records that differ from the original bytes.
   *
   * The judgement is made by comparing the *bytes*, not by the `dirty` set:
   * `dirty` only records "this record was touched", so a change that was
   * later undone would still count as a change.
   */
  changedStructureRecords(structure) {
    const out = [];
    for (const record of (structure && structure.records) || []) {
      const bytes = this.recordBytes(structure, record);
      const raw = base64ToBytes(record.raw || '');
      if (bytesToBase64(bytes) !== bytesToBase64(raw)) out.push(record);
    }
    return out;
  }

  /** The text records that differ from the original text. */
  changedTextRecords(table) {
    const out = [];
    for (const record of (table && table.records) || []) {
      if (record.text !== undefined && record.text !== record.original_text) {
        out.push(record);
      }
    }
    return out;
  }

  /** How many records of a structure were changed. */
  changedCountIn(structure) {
    return this.changedStructureRecords(structure).length;
  }

  /** How many records of a text table were changed. */
  changedCountInTable(table) {
    return this.changedTextRecords(table).length;
  }
}

export function writeField(bytes, field, value) {
  switch (field.type) {
    case 'u8':
      writeUint(bytes, field.offset, 1, Number(value) & 0xff);
      break;
    case 'u16':
      writeUint(bytes, field.offset, 2, Number(value) & 0xffff);
      break;
    case 's16':
      writeUint(bytes, field.offset, 2, Number(value) & 0xffff);
      break;
    case 'u32':
    case 'ptr':
      writeUint(bytes, field.offset, 4, Number(value) >>> 0);
      break;
    case 's32':
      writeUint(bytes, field.offset, 4, Number(value) >>> 0);
      break;
    case 'hex': {
      const clean = String(value).replace(/[^0-9a-fA-F]/g, '');
      const count = field.size ?? clean.length / 2;
      for (let i = 0; i < count; i++) {
        bytes[field.offset + i] = parseInt(clean.substr(i * 2, 2), 16) || 0;
      }
      break;
    }
    default:
      throw new Error(`未知字段类型: ${field.type}`);
  }
}

export function readField(bytes, field) {
  switch (field.type) {
    case 'u8':
      return readUint(bytes, field.offset, 1);
    case 'u16':
      return readUint(bytes, field.offset, 2);
    case 's16':
      // 有符号必须按有符号读：导出器写进内容包的就是带符号值
      // （unit_delta_table.delta = -4），按无符号读会变成 65532，
      // 于是「原值」永远对不上、每条记录都被标成「已改」。
      return readInt(bytes, field.offset, 2);
    case 'u32':
    case 'ptr':
      return readUint(bytes, field.offset, 4);
    case 's32':
      return readInt(bytes, field.offset, 4);
    case 'hex': {
      const count = field.size ?? 0;
      let out = '';
      for (let i = 0; i < count; i++) {
        out += bytes[field.offset + i].toString(16).padStart(2, '0');
      }
      return out;
    }
    default:
      return null;
  }
}
