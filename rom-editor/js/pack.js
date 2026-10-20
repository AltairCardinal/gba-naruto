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

import { bytesToBase64, base64ToBytes, readUint, writeUint } from './bytes.js';
import { FontCodec } from './textcodec.js';

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
    this.patches = data.patches || [];
    this.font = new FontCodec(
      (data.font && data.font.code_to_char) || {},
      (data.font && data.font.char_to_code) || null
    );
    this.dirty = new Set();
    this.notes = data.notes || [];
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
    record.values[key] = value;
    this.dirty.add(`${structure.id}#${record.id}`);
  }

  setText(table, record, text) {
    record.text = text;
    this.dirty.add(`${table.id}#${record.id}`);
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
    return n;
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
    case 's16':
      return readUint(bytes, field.offset, 2);
    case 'u32':
    case 'ptr':
    case 's32':
      return readUint(bytes, field.offset, 4);
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
