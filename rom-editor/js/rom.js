// ROM writer — turns a content pack back into a complete ROM.
//
// The build is deliberately boring and total:
//   1. copy the base ROM;
//   2. apply the explicit raw patches (verifying the expected original bytes);
//   3. write every structure record back at its own ROM offset;
//   4. rebuild every text table: encode the texts, lay the blob out either
//      where the original text lived or in free space, and rewrite the
//      pointers that reference it.
//
// With an untouched pack the output is byte-identical to the base ROM; that
// property is the acceptance test for the whole editor (see
// rom-editor/tools/verify_pack.mjs).

import { bytesToHex, hexToBytes, offsetToPointer, isRomPointer } from './bytes.js';

export class BuildError extends Error {}

export class RomBuilder {
  /**
   * @param {Uint8Array} baseBytes  the original ROM
   * @param {ContentPack} pack
   */
  constructor(baseBytes, pack) {
    this.base = baseBytes;
    this.pack = pack;
    this.bytes = new Uint8Array(baseBytes);
    this.report = {
      structures: 0,
      records: 0,
      recordsChanged: 0,
      texts: 0,
      textsChanged: 0,
      patches: 0,
      freeRegionsUsed: [],
      warnings: [],
      errors: [],
    };
    /** Ranges this build has already claimed for a relocated text blob. */
    this.allocated = [];
  }

  build() {
    this.applyPatches();
    this.applyStructures();
    this.applyTextTables();
    if (this.report.errors.length) {
      throw new BuildError(this.report.errors.join('\n'));
    }
    return this;
  }

  applyPatches() {
    for (const patch of this.pack.patches || []) {
      const offset = patch.offset;
      const after = hexToBytes(patch.after_hex || '');
      if (offset + after.length > this.bytes.length) {
        this.report.errors.push(
          `补丁 ${patch.id} 超出 ROM 末尾 (0x${offset.toString(16)})`
        );
        continue;
      }
      if (patch.before_hex) {
        const before = hexToBytes(patch.before_hex);
        const actual = this.bytes.subarray(offset, offset + before.length);
        if (bytesToHex(actual) !== bytesToHex(before)) {
          this.report.warnings.push(
            `补丁 ${patch.id} 的原始字节不匹配（已跳过）`
          );
          continue;
        }
      }
      this.bytes.set(after, offset);
      this.report.patches += 1;
    }
  }

  applyStructures() {
    for (const structure of this.pack.structures || []) {
      this.report.structures += 1;
      for (const record of structure.records || []) {
        const bytes = this.pack.recordBytes(structure, record);
        const offset = record.rom_offset;
        if (offset < 0 || offset + bytes.length > this.bytes.length) {
          this.report.errors.push(
            `${structure.id}#${record.id} 超出 ROM 范围 0x${offset.toString(16)}`
          );
          continue;
        }
        const original = this.bytes.subarray(offset, offset + bytes.length);
        const changed = bytesToHex(original) !== bytesToHex(bytes);
        this.bytes.set(bytes, offset);
        this.report.records += 1;
        if (changed) this.report.recordsChanged += 1;
      }
    }
  }

  applyTextTables() {
    for (const table of this.pack.texts || []) {
      const result = this.rebuildTextTable(table);
      if (result) this.report.textsChanged += 1;
      this.report.texts += 1;
    }
  }

  /**
   * Rebuild one text table.
   *
   * `relocatable` tables (their text is reached through a pointer table) can
   * move: the blob is written to the original location when the records are
   * contiguous and still fit, otherwise into free space, and the pointers are
   * rewritten.  Non-relocatable tables (text addressed by an absolute literal
   * in code) are written in place and an over-long edit is reported as an
   * error.
   *
   * A table whose texts are all unchanged is skipped completely — that is what
   * keeps an untouched pack byte-identical to the original ROM.
   */
  rebuildTextTable(table) {
    const codec = this.pack.font;
    const records = table.records || [];
    if (!records.length) return false;

    const encoded = records.map((record) => {
      const text = record.text ?? '';
      const bytes = codec.encode(text);
      return { record, bytes, text };
    });

    const changed = encoded.some(
      (e) => (e.record.original_text ?? '') !== e.text
    );
    if (!changed) return false;

    const nulTerminated = table.nul_terminated !== false;
    const sizes = encoded.map((e) => e.bytes.length + (nulTerminated ? 1 : 0));
    const total = sizes.reduce((a, b) => a + b, 0);

    if (!table.relocatable) {
      for (let i = 0; i < encoded.length; i++) {
        const e = encoded[i];
        const capacity = e.record.capacity ?? 0;
        if (e.record.text_offset === null || e.record.text_offset === undefined) {
          if (e.bytes.length) {
            this.report.errors.push(
              `${table.id}#${e.record.id} 没有可写位置（text_offset 为空）`
            );
          }
          continue;
        }
        if (e.bytes.length + (nulTerminated ? 1 : 0) > capacity) {
          this.report.errors.push(
            `${table.id}#${e.record.id} 文本超长：` +
              `${e.bytes.length} 字节 > 槽位 ${capacity} 字节（该表不可重定位）`
          );
          continue;
        }
        this.bytes.set(e.bytes, e.record.text_offset);
        if (nulTerminated) this.bytes[e.record.text_offset + e.bytes.length] = 0;
      }
      return true;
    }

    // --- relocatable: lay the whole table out as one blob ---------------
    const blobOffset = this.placeTextBlob(table, encoded, sizes, total, nulTerminated);

    let cursor = blobOffset;
    for (let i = 0; i < encoded.length; i++) {
      const e = encoded[i];
      const rec = e.record;
      this.bytes.set(e.bytes, cursor);
      if (nulTerminated) this.bytes[cursor + e.bytes.length] = 0;
      const pointer = e.bytes.length ? offsetToPointer(cursor) : 0;
      if (rec.pointer_offset !== null && rec.pointer_offset !== undefined) {
        this.writeU32(rec.pointer_offset, pointer);
      } else {
        rec.pointer = pointer;
      }
      rec.text_offset = cursor;
      cursor += sizes[i];
    }
    return true;
  }

  /**
   * Decide where a text table's blob goes.
   *
   * In place is only allowed when the original records are *contiguous* — the
   * bytes between two records would otherwise be data that is not ours.
   * Otherwise the blob is allocated in free space.
   */
  placeTextBlob(table, encoded, sizes, total, nulTerminated) {
    const placed = encoded
      .map((e, i) => ({
        start: e.record.text_offset,
        end: e.record.text_offset +
          (e.record.capacity ?? 0) - (nulTerminated ? 1 : 0),
        size: sizes[i],
      }))
      .filter((p) => p.start !== null && p.start !== undefined)
      .sort((a, b) => a.start - b.start);

    if (placed.length) {
      const contiguous = placed.every(
        (p, i) => i === 0 || placed[i - 1].end + (nulTerminated ? 1 : 0) === p.start
      );
      const spanStart = placed[0].start;
      const spanEnd = placed[placed.length - 1].end + (nulTerminated ? 1 : 0);
      if (contiguous && total <= spanEnd - spanStart) {
        return spanStart;
      }
    }

    const offset = this.allocate(total);
    if (offset === null) {
      this.report.errors.push(
        `${table.id} 需要 ${total} 字节空闲空间，但 ROM 中找不到足够大的空闲区`
      );
      return null;
    }
    this.report.freeRegionsUsed.push({ table: table.id, offset, length: total });
    return offset;
  }

  writeU32(offset, value) {
    this.bytes[offset] = value & 0xff;
    this.bytes[offset + 1] = (value >>> 8) & 0xff;
    this.bytes[offset + 2] = (value >>> 16) & 0xff;
    this.bytes[offset + 3] = (value >>> 24) & 0xff;
  }

  /**
   * Find a free region big enough for `size` bytes.
   *
   * Only 0xFF runs are considered free, and a run is skipped when the pack
   * claims any of its bytes — or when this build already allocated part of
   * it — so a build can never overwrite live data or its own earlier blobs.
   */
  allocate(size) {
    const claimed = this.claimedRanges().concat(this.allocated);
    const MIN_RUN = 0x1000;
    const runs = [];
    let i = 0;
    while (i < this.bytes.length) {
      if (this.bytes[i] === 0xff) {
        let j = i;
        while (j < this.bytes.length && this.bytes[j] === 0xff) j++;
        if (j - i >= MIN_RUN) runs.push({ start: i, end: j });
        i = j;
      } else {
        i += 1;
      }
    }
    runs.sort((a, b) => (b.end - b.start) - (a.end - a.start));
    for (const run of runs) {
      let cursor = run.start;
      for (const range of claimed) {
        if (range.end <= cursor || range.start >= run.end) continue;
        if (range.start > cursor) {
          const gap = range.start - cursor;
          if (gap >= size) return this.reserve(cursor, size);
        }
        cursor = Math.max(cursor, range.end);
      }
      if (run.end - cursor >= size) return this.reserve(cursor, size);
    }
    return null;
  }

  /** Mark a freshly allocated range as used for the rest of this build. */
  reserve(offset, size) {
    this.allocated.push({ start: offset, end: offset + size });
    return offset;
  }

  /** Byte ranges the pack owns; the allocator must not touch them. */
  claimedRanges() {
    const ranges = [];
    for (const structure of this.pack.structures || []) {
      for (const record of structure.records || []) {
        const size = structure.entry_size || 0;
        ranges.push({ start: record.rom_offset, end: record.rom_offset + size });
      }
    }
    for (const table of this.pack.texts || []) {
      for (const record of table.records || []) {
        if (record.text_offset === null || record.text_offset === undefined) continue;
        ranges.push({
          start: record.text_offset,
          end: record.text_offset + (record.capacity || 0),
        });
      }
    }
    for (const patch of this.pack.patches || []) {
      ranges.push({
        start: patch.offset,
        end: patch.offset + hexToBytes(patch.after_hex || '').length,
      });
    }
    return ranges;
  }
}

/** Convenience: build and return { bytes, report }. */
export function buildRom(pack, baseBytes) {
  const builder = new RomBuilder(baseBytes, pack).build();
  return { bytes: builder.bytes, report: builder.report };
}

export { isRomPointer };
