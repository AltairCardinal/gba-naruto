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

import { bytesToHex, hexToBytes, base64ToBytes, offsetToPointer, isRomPointer } from './bytes.js';
import { scanTokens, encodeTokens, countControlCodes } from './textcodec.js';

/** Do two byte runs match? */
function bytesEqual(a, b) {
  if (a.length !== b.length) return false;
  for (let i = 0; i < a.length; i++) if (a[i] !== b[i]) return false;
  return true;
}

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
      movedTexts: [],
      warnings: [],
      errors: [],
    };
    /** Ranges this build has already claimed for a relocated text blob. */
    this.allocated = [];
    /** Ranges freed by a text record that moved elsewhere. */
    this.released = [];
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
   *
   * Text is re-encoded from its **token stream**, so the control codes
   * (0x01 / 0x02, which carry line-break and page-break meaning) survive a
   * rewrite.  A table is only re-laid-out when a record's length actually
   * changed; otherwise every record is written back in place and only the
   * edited record's bytes differ.
   */
  rebuildTextTable(table) {
    const pack = this.pack;
    const records = table.records || [];
    if (!records.length) return false;

    const nulTerminated = table.nul_terminated !== false;
    const encoded = records.map((record) => {
      const bytes = pack.textBytes(record);
      const original = record.raw ? base64ToBytes(record.raw) : new Uint8Array(0);
      const changed = bytes.length !== original.length || !bytesEqual(bytes, original);
      return { record, bytes, original, changed };
    });

    if (!encoded.some((e) => e.changed)) return false;

    // Control codes must never be lost.
    for (const e of encoded) {
      const before = countControlCodes(scanTokens(e.original));
      const after = countControlCodes(scanTokens(e.bytes));
      if (after < before) {
        this.report.errors.push(
          `${table.id}#${e.record.id} 的控制码会丢失（${before} → ${after}），已拒绝写回`);
        return false;
      }
    }

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
        if (!e.changed) continue;
        this.bytes.set(e.bytes, e.record.text_offset);
        if (nulTerminated) this.bytes[e.record.text_offset + e.bytes.length] = 0;
      }
      return true;
    }

    // --- relocatable ---------------------------------------------------
    // 每条记录单独处理：能原地放下就原地放（指针不动），放不下才搬到
    // 空闲区并改写它自己的指针。改一条文本通常只动那一条记录，
    // 而不会把整张表连同指针表一起重排。
    const moved = [];
    for (const e of encoded) {
      if (e.record.text_offset === null || e.record.text_offset === undefined) {
        if (e.bytes.length) {
          this.report.errors.push(
            `${table.id}#${e.record.id} 没有可写位置（text_offset 为空）`);
        }
        continue;
      }
      if (e.bytes.length <= e.original.length) {
        this.bytes.set(e.bytes, e.record.text_offset);
        if (nulTerminated) this.bytes[e.record.text_offset + e.bytes.length] = 0;
        continue;
      }
      moved.push(e);
    }

    for (const e of moved) {
      const need = e.bytes.length + (nulTerminated ? 1 : 0);
      const offset = this.allocate(need);
      if (offset === null) {
        this.report.errors.push(
          `${table.id}#${e.record.id} 需要 ${need} 字节空闲空间，但 ROM 中找不到足够大的空闲区`);
        continue;
      }
      this.bytes.set(e.bytes, offset);
      if (nulTerminated) this.bytes[offset + e.bytes.length] = 0;
      const pointer = offsetToPointer(offset);
      if (e.record.pointer_offset !== null && e.record.pointer_offset !== undefined) {
        this.writeU32(e.record.pointer_offset, pointer);
      } else {
        e.record.pointer = pointer;
      }
      // 旧槽位空出来了，可以给别的记录用
      this.released.push({
        start: e.record.text_offset,
        end: e.record.text_offset + e.original.length,
      });
      // 摆放结果只记在构建报告里：**不改动内容包**，
      // 否则「导出 → 导入 → 再构建」会得到不同的 ROM。
      this.report.movedTexts.push({
        table: table.id,
        id: e.record.id,
        from: e.record.text_offset,
        to: offset,
        bytes: e.bytes.length,
      });
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
    const released = this.released || [];
    const isReleased = (start, end) => released.some((r) => start >= r.start && end <= r.end);
    for (const structure of this.pack.structures || []) {
      for (const record of structure.records || []) {
        const size = structure.entry_size || 0;
        const range = { start: record.rom_offset, end: record.rom_offset + size };
        if (!isReleased(range.start, range.end)) ranges.push(range);
      }
    }
    for (const table of this.pack.texts || []) {
      for (const record of table.records || []) {
        if (record.text_offset === null || record.text_offset === undefined) continue;
        const range = {
          start: record.text_offset,
          end: record.text_offset + (record.capacity || 0),
        };
        if (!isReleased(range.start, range.end)) ranges.push(range);
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
