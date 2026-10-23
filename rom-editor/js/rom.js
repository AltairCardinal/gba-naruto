// ROM writer — turns a content pack back into a complete ROM.
//
// The build is deliberately boring and total:
//   1. copy the base ROM;
//   2. apply the explicit raw patches (verifying the expected original bytes);
//   3. write every structure record back at its own ROM offset;
//   4. rebuild every text table: encode the texts, lay the blob out either
//      where the original text lived or in free space, and rewrite the
//      pointers that reference it;
//   5. relocate the story scripts whose dialogue no longer fits in place.
//
// With an untouched pack the output is byte-identical to the base ROM; that
// property is the acceptance test for the whole editor (see
// rom-editor/tools/verify_pack.mjs).

import { bytesToHex, hexToBytes, base64ToBytes, offsetToPointer, isRomPointer } from './bytes.js';
import { scanTokens, encodeTokens, countControlCodes } from './textcodec.js';
import { scriptComponents, planRelocation, ROM_BASE } from './storyvm.js';
import { patchOriginalExtent } from './pack.js';

/**
 * 空闲区的上界（**不含**）。
 *
 * `notes/free-space.md` 记的空闲区是 `0x5DFBEC..0x5FFFFF`，实测那段 0xFF
 * 一直连到 ROM 末尾 `0x600000`（多 1KB）。这里按**笔记里的**边界收口 ——
 * 免得编辑器与 `tools/import_dialogue_var.py` 那条老链路的边界不一致。
 *
 * ⚠️ **两条链路共用这一段空闲区**，谁先谁后都会踩到对方。详见
 * `notes/free-space.md` 的「与编辑器的关系」一节。
 */
export const FREE_SPACE_END = 0x5fffff;

/** 四张剧情根表（内容包里的结构 id）：槽号 = 场景号，值是剧本首地址。 */
const ROOT_STRUCTURES = new Set([
  'story_before_root',
  'story_after_root',
  'story_logic_root',
  'story_events_root',
]);

/**
 * 一条文本记录被**哪些槽**指向。
 *
 * 绝大多数表一条记录一个槽（`pointer_offset`）；
 * 但战斗目标说明表里一句说明可能被**好几条战斗目标共用**
 * （`pointer_offsets` 是全部的槽）—— 漏改一个，共用它的那条战斗目标
 * 就还指着旧地址，界面上看到的和游戏里跑的就对不上了。
 *
 * @returns {?number[]} 槽的文件偏移；没有指针槽时返回 null
 */
function pointerSlotsOf(record) {
  if (Array.isArray(record.pointer_offsets) && record.pointer_offsets.length) {
    return record.pointer_offsets;
  }
  if (record.pointer_offset !== null && record.pointer_offset !== undefined) {
    return [record.pointer_offset];
  }
  return null;
}

/** 一组剧本的人话描述（错误信息里用）。 */
function describeComponent(component) {
  const list = component.roots
    .map((r) => '0x' + r.toString(16).toUpperCase())
    .join(' + ');
  return component.roots.length > 1 ? `${list}（互相重叠的一组）` : list;
}

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
      movedScripts: [],
      conversions: [],
      warnings: [],
      errors: [],
    };
    /** Ranges this build has already claimed for a relocated text blob. */
    this.allocated = [];
    /** Ranges freed by a text record that moved elsewhere. */
    this.released = [];
  }

  build() {
    // 写回顺序：**补丁最后写**。
    //
    // 早先的顺序是「补丁 → 结构 → 文本」，于是**落在结构表或文本表写回范围内
    // 的补丁会被整段覆盖回去** —— 作者在编辑器里看到新值，ROM 里却没有，
    // 而且构建报告一个错都不报（实测：改 battle_actors 记录里的一个字节，
    // 构建后该字节仍是原值，warnings=[]、errors=[]）。
    //
    // 现在结构与文本先写回，补丁最后写；补丁的「原字节必须匹配」校验改成
    // 对着**当前**字节做，于是：
    //   * 那个字节没被结构化编辑器改过 → 补丁生效（兜底通道真的兜得住）；
    //   * 那个字节被结构化编辑器改过 → 字节已变，补丁被跳过并报告
    //     （结构化改动优先，而且用户看得见）。
    //
    // **剧本搬迁**夹在文本与补丁之间：它要把剧本内部的补丁**折进**搬走的那份
    // 字节里（补丁的 offset 是**原版**里的位置，搬完就失效了），
    // 所以必须排在 `applyPatches` 前面。
    this.applyStructures();
    this.applyTextTables();
    const relocation = this.applyScriptRelocations();
    this.applyPatches(relocation);
    if (this.report.errors.length) {
      throw new BuildError(this.report.errors.join('\n'));
    }
    return this;
  }

  applyPatches(relocation) {
    const consumed = (relocation && relocation.consumed) || new Set();
    const failed = (relocation && relocation.failed) || new Set();
    for (const patch of this.pack.patches || []) {
      // 已经被搬迁吃掉的补丁：它的内容已经折进搬走的那份字节里了。
      if (consumed.has(patch.id)) continue;
      // 搬迁失败的那条：已经报过错了，不要再报一遍。
      if (failed.has(patch.id)) continue;
      const offset = patch.offset;
      const after = hexToBytes(patch.after_hex || '');
      if (offset + after.length > this.bytes.length) {
        this.report.errors.push(
          `补丁 ${patch.id} 超出 ROM 末尾 (0x${offset.toString(16)})`
        );
        continue;
      }
      const before = hexToBytes(patch.before_hex || '');
      if (before.length && after.length !== before.length) {
        // 变长的补丁只有在剧本搬迁里才安全（`applyScriptRelocations`）。
        // 到这里还没被吃掉 ⇒ 它不在任何能搬迁的剧本里 ⇒ 后面没有东西能给它让位。
        this.report.errors.push(
          `补丁 ${patch.id} 把 ${before.length} 字节改成了 ${after.length} 字节，` +
          '但它不在任何能搬迁的剧本里 —— 这么改会让后面的字节全部移位。' +
          '（对白正文可以变长：构建时整个剧本会搬到空闲区并重基地址。）'
        );
        continue;
      }
      if (patch.before_hex) {
        const actual = this.bytes.subarray(offset, offset + before.length);
        if (bytesToHex(actual) !== bytesToHex(before)) {
          this.report.warnings.push(
            `补丁 ${patch.id} 的原始字节不匹配（已跳过）——` +
            '这个地址可能已经被结构化编辑器改过，请确认两处改动谁生效'
          );
          continue;
        }
      }
      this.bytes.set(after, offset);
      this.report.patches += 1;
    }
  }

  /**
   * 搬迁「因为对白变长 / 变短而不能原地改」的剧本。
   *
   * 剧情脚本的正文是**内联在字节流里**的，而脚本里的分支目标是**绝对地址** ——
   * 改长改短都会让后面的指令移位、分支全部失效。
   *
   * 所以「变长」只有一条安全的路：
   *
   *   1. 把**整个剧本**搬到空闲区（它的字节可能不连续 —— `before` / `after`
   *      是物理交错的 ⇒ 按段搬，段与段之间靠分支相连，终止符还在）；
   *   2. 把剧本内部的绝对地址**全部重基**（`storyvm.js::planRelocation`，
   *      按「操作码 + 槽偏移」白名单，一个都不许漏）；
   *   3. 改根表里**指向它**的指针（`before` / `after` 可能指向同一个剧本，
   *      那就两个槽都要改）。
   *
   * ⚠️ **互相重叠的剧本要整组一起搬**：有些剧本是另一个的**后缀**
   * （`after.53` = `before.53` 去掉第一条指令），共享的那段里有几百段对白 ——
   * 搬两份的话两个剧本各留一份同一段对白，改了其中一个另一个不变。
   * 所以这里先按字节重叠把剧本**分组**（`storyvm.js::scriptComponents`），
   * 每一组当作一个整体搬。
   *
   * 搬迁时，剧本内部的**所有补丁**（对白改动、操作数改动）都要**折进**搬走的那
   * 份字节里 —— 补丁的 `offset` 说的是**原版**里的位置，搬完就失效了。
   * 折进去的补丁由 `applyPatches` 跳过（不重复写）。
   *
   * 旧位置**不回收**（回收会把「未改动也能重建出同一个 ROM」这条不变量弄丢）；
   * 回收是后面的事。
   *
   * @returns {{consumed:Set<string>, failed:Set<string>}}
   */
  applyScriptRelocations() {
    const consumed = new Set();
    const failed = new Set();

    // 剧本表：按**起始地址**去重 —— `before` 与 `after` 可能指向同一个剧本。
    const roots = [];
    const seen = new Set();
    for (const script of this.pack.scripts || []) {
      const offset = script.script_offset;
      if (offset === null || offset === undefined) continue;
      if (seen.has(offset)) continue;
      seen.add(offset);
      roots.push(offset);
    }
    if (!roots.length) return { consumed, failed };

    const components = scriptComponents(this.bytes, roots);
    for (const component of components) {
      const fragments = component.fragments;
      if (!fragments.length) continue;

      // 这一组里的补丁。
      const inside = [];
      for (const patch of this.pack.patches || []) {
        if (consumed.has(patch.id) || failed.has(patch.id)) continue;
        const extent = patchOriginalExtent(patch);
        const hit = fragments.some(
          (f) => extent.start < f.end && extent.end > f.start
        );
        if (hit) inside.push(patch);
      }
      if (!inside.length) continue;

      // 改成「替换成什么字节」。
      const edits = [];
      let lengthChanged = false;
      for (const patch of inside) {
        const before = hexToBytes(patch.before_hex || '');
        const after = hexToBytes(patch.after_hex || '');
        const original = before.length || after.length;
        edits.push({ offset: patch.offset, length: original, bytes: after });
        if (after.length !== original) lengthChanged = true;
      }
      // 全是等长改动 → 原地写就够，不必搬。
      if (!lengthChanged) continue;

      // 搬迁后的大小：原来那些字节 + 每处改动的增减。
      const originalSize = fragments.reduce((n, f) => n + (f.end - f.start), 0);
      let size = originalSize;
      for (const edit of edits) size += edit.bytes.length - edit.length;

      const newStart = this.allocate(size);
      if (newStart === null) {
        for (const patch of inside) failed.add(patch.id);
        this.report.errors.push(
          `剧本 ${describeComponent(component)} 的对白变长了，`
          + `需要 ${size} 字节空闲空间，但 ROM 里找不到足够大的空闲区。`
        );
        continue;
      }

      const plan = planRelocation(this.bytes, component.roots, newStart, edits);
      if (!plan || plan.errors.length) {
        for (const patch of inside) failed.add(patch.id);
        this.report.errors.push(
          `剧本 ${describeComponent(component)} 搬迁失败：`
          + (plan && plan.errors.length ? plan.errors.join('；') : '规划不出新地址')
        );
        continue;
      }

      this.bytes.set(plan.bytes, newStart);

      // 改根表里指向它们的指针 —— 这一组里**每一个**入口都要改。
      let slots = 0;
      for (const move of plan.roots) {
        const pointer = offsetToPointer(move.new);
        for (const structure of this.pack.structures || []) {
          if (!ROOT_STRUCTURES.has(structure.id)) continue;
          for (const record of structure.records || []) {
            const value = record.values ? record.values.ptr : 0;
            if ((value >>> 0) !== (ROM_BASE + move.old)) continue;
            this.writeU32(record.rom_offset, pointer);
            slots += 1;
          }
        }
      }
      if (!slots) {
        for (const patch of inside) failed.add(patch.id);
        this.report.errors.push(
          `剧本 ${describeComponent(component)} 搬迁了，但根表里没有槽指向它 —— `
          + '搬完就没有人能走到它了。'
        );
        continue;
      }

      for (const patch of inside) consumed.add(patch.id);
      this.report.movedScripts.push({
        id: describeComponent(component),
        from: component.roots[0],
        to: newStart,
        bytes: plan.bytes.length,
        segments: plan.fragments.length,
        rebased: plan.rebase.length,
        slots,
        roots: plan.roots.map((move) => ({
          from: move.old,
          to: move.new,
        })),
        delta: plan.bytes.length - originalSize,
      });
    }
    return { consumed, failed };
  }

  /**
   * 把一张「定长内联槽」的文本表转换成**指针表 + 变长串池**。
   *
   * 目前只有说话人名表（`0x085A57C4`，每条 12 字节）。它「结构上改不了长度」：
   * 槽的大小写死在表里，没有指针可以改。
   *
   * 事实依据：`notes/evidence/speaker-name-table-20261023.md`
   * —— 12 个原生读者**全是取名读者**（不是取色），而且**全都按「读到 0x00
   * 为止」消费** ⇒ **变长在读者层面本来就支持**，缺的只是「槽的定长结构」。
   *
   * 转换做三件事：
   *   1. **改 ROM 里的 12 个读者**：它们按 `基址 + id*12` 取名字（步长 12 是
   *      `(id*2+id)*4` 三条指令算出来的），改成 `基址 + id*4` 再解引用。
   *      **指令数与字节数都不变** ⇒ 不挪动任何后续代码。
   *   2. 在**原表自己的位置**上放那张指针表（64 × 4 字节）——
   *      读者的基址常量一个字都不用改。
   *   3. 把 64 条名字搬到空闲区（一个「串池」），指针表指向它们。
   *
   * ⚠️ 指针表会盖住原表的前 256 字节 ⇒ 名字**必须全部搬走**。
   * ⚠️ `基址 + 63*12 = 0x085A5AB8` 是**说话人全名表**的第 0 条（另有 3 个读者）
   * —— 指针表只占 `0x085A57C4..0x085A58C3`，**碰不到它** ✓。
   *
   * @param {object} table      内容包里的文本表
   * @param {Array} encoded     `rebuildTextTable` 算好的每条记录
   * @param {object} conversion 内容包 `conversions[table.convert]`
   * @returns {boolean} 是否成功
   */
  applyInlineToPointer(table, encoded, conversion) {
    const pack = this.pack;

    // 1. 读者补丁：原始字节必须与 ROM 对得上，否则会打歪。
    for (const patch of conversion.code_patches || []) {
      const before = hexToBytes(patch.before_hex || '');
      const actual = this.bytes.subarray(patch.offset, patch.offset + before.length);
      if (bytesToHex(actual) !== bytesToHex(before)) {
        this.report.errors.push(
          `${table.id}：转换补丁「${patch.label || patch.offset}」的原始字节不匹配`
          + '（ROM 与内容包对不上）');
        return false;
      }
      const after = hexToBytes(patch.after_hex || '');
      if (after.length !== before.length) {
        this.report.errors.push(
          `${table.id}：转换补丁「${patch.label || patch.offset}」长度变了`
          + '（那会挪动后续代码）');
        return false;
      }
      this.bytes.set(after, patch.offset);
    }

    // 2. 串池：64 条名字一次性分配（指针表要指向它们）。
    const contents = encoded.map((e) => pack.textContentBytes(e.record));
    let size = 0;
    for (const content of contents) size += content.length + 1;
    const pool = this.allocate(size);
    if (pool === null) {
      this.report.errors.push(
        `${table.id}：转换需要 ${size} 字节空闲空间，但 ROM 里找不到足够大的空闲区`);
      return false;
    }

    // 3. 写串池 + 写指针表。
    const base = conversion.base;
    let cursor = pool;
    for (let i = 0; i < encoded.length; i++) {
      const e = encoded[i];
      const content = contents[i];
      this.bytes.set(content, cursor);
      this.bytes[cursor + content.length] = 0;
      this.writeU32(base + i * 4, offsetToPointer(cursor));
      this.report.movedTexts.push({
        table: table.id,
        id: e.record.id,
        from: e.record.text_offset,
        to: cursor,
        bytes: content.length,
        slots: 1,
      });
      cursor += content.length + 1;
    }
    return true;
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

    // --- 可选的结构转换（说话人名表：定长内联槽 → 指针表） -------------------
    // 「结构上改不了长度」的表可以在**作者改了它之后**转成能改的形态。
    // 没改过 ⇒ 上面的 `return false` 已经先走了 ⇒ 重建仍与原版逐字节相同。
    if (table.convert) {
      const conversion = (this.pack.conversions || {})[table.convert];
      if (!conversion) {
        this.report.errors.push(
          `${table.id} 要转换成「${table.convert}」，但内容包里没有这个转换的描述`);
        return false;
      }
      const ok = this.applyInlineToPointer(table, encoded, conversion);
      if (ok) {
        this.report.conversions.push({
          table: table.id,
          kind: conversion.kind,
          base: conversion.base,
          records: encoded.length,
        });
      }
      return ok;
    }

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
        if (e.record.owned_by) {
          // 这段字节属于另一张表（内容包已标明归属）。
          // 在这里再写一次会覆盖那边的改动，所以跳过并说明。
          if (e.changed) {
            this.report.warnings.push(
              `${table.id}#${e.record.id} 的这段文字属于 ${e.record.owned_by}，` +
              '请在归属它的表里改'
            );
          }
          continue;
        }
        // 容量判定必须用**内容长度**：写回时字节会被补齐到槽位大小，
        // 拿补齐后的长度去比容量，会把「4 字节的字 + 12 字节的槽」误判成超长。
        const content = pack.textContentBytes(e.record);
        if (content.length + (nulTerminated ? 1 : 0) > capacity) {
          this.report.errors.push(
            `${table.id}#${e.record.id} 文本超长：` +
              `写回需要 ${content.length + (nulTerminated ? 1 : 0)} 字节，` +
              `槽位只有 ${capacity} 字节（该表不可重定位，只能等长改写）`
          );
          continue;
        }
        if (!e.changed) continue;
        this.bytes.set(content, e.record.text_offset);
        if (nulTerminated) this.bytes[e.record.text_offset + content.length] = 0;
        // 把旧文本多出来的尾巴清零：字符串以 NUL 结束，后面的残字节不该留着。
        for (let k = content.length + (nulTerminated ? 1 : 0); k < e.original.length; k++) {
          this.bytes[e.record.text_offset + k] = 0;
        }
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

    // 共用同一段字节的记录其实是**同一段字符串**：只搬一次，
    // 所有指向它的指针改到同一个新地址（否则会搬出 27 份一样的副本）。
    const movedByOffset = new Map();
    for (const e of moved) {
      const key = e.record.text_offset;
      if (!movedByOffset.has(key)) movedByOffset.set(key, []);
      movedByOffset.get(key).push(e);
    }

    for (const [from, group] of movedByOffset) {
      const e = group[0];
      const need = e.bytes.length + (nulTerminated ? 1 : 0);
      const offset = this.allocate(need);
      if (offset === null) {
        for (const item of group) {
          this.report.errors.push(
            `${table.id}#${item.record.id} 需要 ${need} 字节空闲空间，但 ROM 中找不到足够大的空闲区`);
        }
        continue;
      }
      this.bytes.set(e.bytes, offset);
      if (nulTerminated) this.bytes[offset + e.bytes.length] = 0;
      const pointer = offsetToPointer(offset);
      for (const item of group) {
        // 一条文字可能被**好几个槽**指向（战斗目标说明：一句被多条战斗目标共用）。
        // 槽都要改 —— 漏一个，共用它的那条战斗目标就还指着旧地址。
        const slots = pointerSlotsOf(item.record);
        if (slots) {
          for (const slot of slots) this.writeU32(slot, pointer);
        } else {
          item.record.pointer = pointer;
        }
        // 摆放结果只记在构建报告里：**不改动内容包**，
        // 否则「导出 → 导入 → 再构建」会得到不同的 ROM。
        this.report.movedTexts.push({
          table: table.id,
          id: item.record.id,
          from: item.record.text_offset,
          to: offset,
          bytes: e.bytes.length,
          slots: slots ? slots.length : 0,
        });
      }
      // 旧槽位空出来了，可以给别的记录用
      this.released.push({
        start: from,
        end: from + e.original.length,
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
    // 只在**文档记的空闲区**里找：`notes/free-space.md` 的上界是 0x5FFFFF，
    // 实测那段 0xFF 一直连到 ROM 末尾 —— 这里按笔记收口，两条链路边界一致。
    const limit = Math.min(this.bytes.length, FREE_SPACE_END);
    const runs = [];
    let i = 0;
    while (i < limit) {
      if (this.bytes[i] === 0xff) {
        let j = i;
        while (j < limit && this.bytes[j] === 0xff) j++;
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
