// 「对白可以变长」的**写回通路**无头验收（第十七轮）。
//
// 用法：node rom-editor/tools/verify_variable_text.mjs
//
// 这道门禁证明的是**从界面改动到 ROM 落地的整条链**：
//
//   V1 变长的对白**不再被拒收**（以前是「等长才能改」当场回滚）；
//   V2 构建**不报错**，而且报告里说得清「哪个剧本搬到了哪里」；
//   V3 根表里指向它的**指针真的改了**（`before` / `after` 共用同一个剧本时，
//      **两个槽都要改** —— 漏一个就有一场戏走丢了）；
//   V4 搬走的那份字节里**指令条数不变**、每条分支目标**都落在指令边界上**
//      （地址重基一个都不许漏、也不许指歪）；
//   V5 变长后的**正文逐字节**等于新文本的编码；
//   V6 **别的剧本一条都不受影响**；
//   V7 变短也一样能落地；
//   V8 落在剧本外的变长改动**构建时报错**（后面没有东西能给它让位）；
//   V9 **没改过的内容包重建出来逐字节相同**（这条不变量不能被搬迁弄丢）；
//   V10 撤销之后改动计数回落、内容包回到未改状态。
//
// 依据：notes/evidence/story-script-relocation-20261022.md
import { readFileSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const repoRoot = join(here, '..', '..');
const packPath = join(repoRoot, 'rom-editor', 'content', 'pack.json');
const romPath = join(repoRoot, 'rom', 'base.gba');

const { ContentPack, textSlotKind } = await import('../js/pack.js');
const { buildRom } = await import('../js/rom.js');
const { scanScript, ADDRESS_SLOTS, ROM_BASE } = await import('../js/storyvm.js');
const { textSegments, commitSegment } = await import('../js/scripttext.js');
const { encodeTokens, mergeTokens } = await import('../js/textcodec.js');
const { hexToBytes, bytesToHex } = await import('../js/bytes.js');

const lines = [];
let failures = 0;
function check(name, ok, detail = '') {
  if (!ok) failures += 1;
  const line = `  [${ok ? 'PASS' : 'FAIL'}] ${name}${detail ? ' — ' + detail : ''}`;
  lines.push(line);
  console.log(line);
}
function head(text) {
  lines.push(text);
  console.log(text);
}

const packData = JSON.parse(readFileSync(packPath, 'utf8'));
const rom = new Uint8Array(readFileSync(romPath));

/**
 * 一份干净的内容包。
 *
 * ⚠️ 必须**重新读文件**：`ContentPack.fromJSON` 直接持有 `data.texts` 里的
 * 那些对象，`setText` 是**就地改** record —— 共用一份对象图的话，上一段测试
 * 的改动会渗到下一段（实测：改完 speaker_names 之后，battle_objectives 那段
 * 报的错还是 speaker_names 的）。
 */
function freshPack() {
  const pack = ContentPack.fromJSON(JSON.parse(readFileSync(packPath, 'utf8')));
  pack.patches = [];
  return pack;
}

/** 根表里指向某个文件偏移的槽（`before` / `after` 可能同时指向它）。 */
function rootSlotsFor(pack, fileOffset) {
  const out = [];
  for (const id of ['story_before_root', 'story_after_root',
    'story_logic_root', 'story_events_root']) {
    const structure = pack.structure(id);
    for (const record of (structure && structure.records) || []) {
      const value = record.values ? record.values.ptr : 0;
      if ((value >>> 0) === ROM_BASE + fileOffset) {
        out.push({ id, slot: record.rom_offset, scene: record.id });
      }
    }
  }
  return out;
}

/**
 * 找一条带正文的指令。
 *
 * 优先挑**只被一个根槽指向**的剧本（搬迁的对照组）；
 * 另找一条**被 before / after 同时指向**的剧本（V3 的共用槽）。
 */
function findTextInstruction(pack, { shared = false } = {}) {
  for (const script of pack.scripts || []) {
    const slots = rootSlotsFor(pack, script.script_offset);
    if (!slots.length) continue;
    if (shared && slots.length < 2) continue;
    if (!shared && slots.length !== 1) continue;
    const instructions = scanScript(rom, script.script_offset);
    const hit = instructions.find((ins) => ins.op === 0x01 || ins.op === 0x20);
    if (!hit) continue;
    const segments = textSegments(rom, pack, hit);
    if (!segments.length) continue;
    return { script, slots, instruction: hit, segment: segments[0] };
  }
  return null;
}

/** 新文本编码后应当得到的字节（与写回路径同源）。 */
function expectedBytes(segment, text, font) {
  const plain = text.split('↵').join('\n');
  return encodeTokens(mergeTokens(segment.tokens, segment.originalBytes
    ? [] : segment.tokens));
}

head('\n1) 变长的对白不再被拒收');
let longerHit = null;
{
  const pack = freshPack();
  const hit = findTextInstruction(pack);
  check('找得到一条能改的正文', !!hit,
    hit ? `${hit.script.id} @0x${hit.instruction.offset.toString(16).toUpperCase()}` : '');
  longerHit = hit;
  const segment = hit.segment;
  const before = pack.changedPatchCount();

  // 加长 4 个字（字库里有的字）。
  const filler = '测试测试';
  const result = commitSegment(pack, segment, segment.text + filler);
  check('变长改写被接受', result.ok === true, result.ok ? '' : (result.message || ''));
  check('结果里标明「会搬迁」', result.relocated === true, String(result.relocated));
  check('改动计数 +1', pack.changedPatchCount() === before + 1,
    `${before} → ${pack.changedPatchCount()}`);
  const patch = (pack.patches || []).find((p) => p.offset === segment.offset);
  check('补丁落在文本段上', !!patch,
    patch ? `0x${patch.offset.toString(16).toUpperCase()}` : '没有补丁');
  const afterBytes = hexToBytes(patch.after_hex);
  check('补丁变长了', afterBytes.length > segment.originalLength,
    `${segment.originalLength} → ${afterBytes.length} 字节`);
  check('补丁的 before_hex 是**原版**正文',
    patch.before_hex === bytesToHex(segment.originalBytes),
    `${patch.before_hex.length / 2} 字节`);
}

head('\n2) 构建：报告里说得清搬到了哪里');
let built = null;
{
  const pack = freshPack();
  const hit = findTextInstruction(pack);
  const segment = hit.segment;
  commitSegment(pack, segment, segment.text + '测试测试');
  built = buildRom(pack, rom);
  check('构建无错误', built.report.errors.length === 0, built.report.errors.join('; '));
  check('构建报告里有搬迁记录', built.report.movedScripts.length === 1,
    `${built.report.movedScripts.length} 条`);
  const moved = built.report.movedScripts[0] || {};
  check('搬迁记录写着从哪搬到哪',
    moved.from === hit.script.script_offset && moved.to > moved.from,
    `0x${(moved.from || 0).toString(16).toUpperCase()} → 0x${(moved.to || 0).toString(16).toUpperCase()}`);
  check('搬迁落在空闲区里（0x5DFBEC 之后）', moved.to >= 0x5dfbec,
    `0x${(moved.to || 0).toString(16).toUpperCase()}`);
  check('搬迁后大小正好差 +8 字节（4 个汉字 × 2 字节字形码）',
    moved.delta === 8, `${moved.delta} 字节`);
}

head('\n3) 根表指针真的改了（共用同一个剧本的两个槽都要改）');
{
  const pack = freshPack();
  const hit = findTextInstruction(pack);
  const segment = hit.segment;
  const slotsBefore = rootSlotsFor(pack, hit.script.script_offset);
  commitSegment(pack, segment, segment.text + '测试测试');
  const out = buildRom(pack, rom);
  const moved = out.report.movedScripts[0];
  check('构建无错误', out.report.errors.length === 0, out.report.errors.join('; '));
  for (const slot of slotsBefore) {
    const value = (out.bytes[slot.slot] | (out.bytes[slot.slot + 1] << 8)
      | (out.bytes[slot.slot + 2] << 16) | (out.bytes[slot.slot + 3] << 24)) >>> 0;
    check(`槽 ${slot.id} 第 ${slot.scene} 场指向新地址`,
      value === ROM_BASE + moved.to,
      `0x${value.toString(16).toUpperCase()}`);
  }
}
{
  // before / after 共用同一个剧本的情况。
  const pack = freshPack();
  const shared = findTextInstruction(pack, { shared: true });
  check('找得到一个被 before / after 同时指向的剧本', !!shared,
    shared ? `${shared.script.id}（${shared.slots.length} 个槽）` : '');
  if (shared) {
    const segment = shared.segment;
    commitSegment(pack, segment, segment.text + '测试测试');
    const out = buildRom(pack, rom);
    check('构建无错误', out.report.errors.length === 0, out.report.errors.join('; '));
    const moved = out.report.movedScripts[0];
    for (const slot of shared.slots) {
      const value = (out.bytes[slot.slot] | (out.bytes[slot.slot + 1] << 8)
        | (out.bytes[slot.slot + 2] << 16) | (out.bytes[slot.slot + 3] << 24)) >>> 0;
      check(`共用槽 ${slot.id} 第 ${slot.scene} 场也改了`,
        value === ROM_BASE + moved.to, `0x${value.toString(16).toUpperCase()}`);
    }
    check('报告里的槽数与实际一致', moved.slots === shared.slots.length,
      `${moved.slots} / ${shared.slots.length}`);
  }
}

head('\n4) 搬走的那份字节：指令条数不变、分支目标不指歪');
{
  const pack = freshPack();
  const hit = findTextInstruction(pack);
  const segment = hit.segment;
  commitSegment(pack, segment, segment.text + '测试测试');
  const out = buildRom(pack, rom);
  const moved = out.report.movedScripts[0];

  const oldInstructions = scanScript(rom, hit.script.script_offset);
  const newInstructions = scanScript(out.bytes, moved.to);
  check('指令条数不变', newInstructions.length === oldInstructions.length,
    `${oldInstructions.length} → ${newInstructions.length}`);

  const boundaries = new Set(newInstructions.map((i) => i.offset));
  let bad = 0;
  let total = 0;
  const detail = [];
  // 搬迁保持指令的**先后顺序**（片段按地址顺序搬，段内顺序不变），
  // 所以第 i 条旧指令对应第 i 条新指令。
  for (let i = 0; i < oldInstructions.length; i++) {
    const old = oldInstructions[i];
    const now = newInstructions[i];
    if (!now || now.op !== old.op) { bad += 1; continue; }
    for (const slot of ADDRESS_SLOTS[old.op] || []) {
      const oldAt = old.offset + slot;
      const newAt = now.offset + slot;
      const oldValue = (rom[oldAt] | (rom[oldAt + 1] << 8)
        | (rom[oldAt + 2] << 16) | (rom[oldAt + 3] << 24)) >>> 0;
      const newValue = (out.bytes[newAt] | (out.bytes[newAt + 1] << 8)
        | (out.bytes[newAt + 2] << 16) | (out.bytes[newAt + 3] << 24)) >>> 0;
      total += 1;
      const newFile = newValue - ROM_BASE;
      // 目标必须落在**新剧本**的指令边界上。
      if (!boundaries.has(newFile)) {
        bad += 1;
        if (detail.length < 4) {
          detail.push(`0x${old.op.toString(16).toUpperCase()} 目标 0x${newValue.toString(16).toUpperCase()}`);
        }
        continue;
      }
      // 目标必须**跟着搬**了（值变了），否则等于没重基。
      if (oldValue === newValue) {
        bad += 1;
        if (detail.length < 4) detail.push(`0x${old.op.toString(16).toUpperCase()} 目标没跟着搬`);
      }
    }
  }
  check('每个分支目标都落在新剧本的指令边界上', bad === 0,
    bad ? `${bad} / ${total} 个目标指歪了（${detail.join('；')}）` : `${total} 个目标全部正确`);
}

head('\n5) 搬走的那份字节里，正文就是新文本');
{
  const pack = freshPack();
  const hit = findTextInstruction(pack);
  const segment = hit.segment;
  const newText = segment.text + '测试测试';
  commitSegment(pack, segment, newText);
  const out = buildRom(pack, rom);
  const moved = out.report.movedScripts[0];
  const patch = pack.patches.find((p) => p.offset === segment.offset);
  const expected = hexToBytes(patch.after_hex);
  // 新剧本里这段正文的位置：原位置 + 搬迁偏移（这段在第一段里）。
  const at = moved.to + (segment.offset - hit.script.script_offset);
  const written = out.bytes.subarray(at, at + expected.length);
  check('正文逐字节等于新文本的编码',
    bytesToHex(written) === bytesToHex(expected),
    `${expected.length} 字节 @0x${at.toString(16).toUpperCase()}`);
  check('正文后面紧跟 NUL', out.bytes[at + expected.length] === 0,
    `0x${out.bytes[at + expected.length].toString(16)}`);
}

head('\n6) 别的剧本一条都不受影响');
{
  const pack = freshPack();
  const hit = findTextInstruction(pack);
  const segment = hit.segment;
  commitSegment(pack, segment, segment.text + '测试测试');
  const out = buildRom(pack, rom);
  let broken = 0;
  let checked = 0;
  for (const script of pack.scripts || []) {
    if (script.script_offset === hit.script.script_offset) continue;
    const before = scanScript(rom, script.script_offset);
    const after = scanScript(out.bytes, script.script_offset);
    checked += 1;
    if (before.length !== after.length) broken += 1;
  }
  check('所有别的剧本指令条数不变', broken === 0,
    broken ? `${broken} / ${checked} 个剧本变了` : `${checked} 个剧本都没变`);
  // 旧位置不该被动（回收旧位置是以后的事）。
  const oldBytes = rom.subarray(hit.script.script_offset,
    hit.script.script_offset + 64);
  const kept = out.bytes.subarray(hit.script.script_offset,
    hit.script.script_offset + 64);
  check('旧位置的字节一个都没动', bytesToHex(oldBytes) === bytesToHex(kept));
}

head('\n7) 变短也一样能落地');
{
  const pack = freshPack();
  const hit = findTextInstruction(pack);
  const segment = hit.segment;
  const shorter = segment.text.slice(0, Math.max(1, segment.text.length - 2));
  const result = commitSegment(pack, segment, shorter);
  check('变短改写被接受', result.ok === true, result.ok ? '' : (result.message || ''));
  check('结果里标明「会搬迁」', result.relocated === true);
  const out = buildRom(pack, rom);
  check('构建无错误', out.report.errors.length === 0, out.report.errors.join('; '));
  const moved = out.report.movedScripts[0];
  check('搬迁后变小了', moved.delta < 0, `${moved.delta} 字节`);
  const newInstructions = scanScript(out.bytes, moved.to);
  const oldInstructions = scanScript(rom, hit.script.script_offset);
  check('指令条数不变', newInstructions.length === oldInstructions.length,
    `${oldInstructions.length} → ${newInstructions.length}`);
}

head('\n8) 落在剧本外的变长改动：构建时报错');
{
  const pack = freshPack();
  // 在空闲区里造一条变长的补丁 —— 它不在任何剧本里。
  pack.setBytesAt(0x5dfbec, '00', '00010203040506070809', '测试用的变长补丁');
  let error = null;
  try {
    buildRom(pack, rom);
  } catch (err) {
    error = err;
  }
  check('构建抛错了', !!error, error ? '' : '居然构建成功了');
  const message = error ? String(error.message || error) : '';
  check('错误里说清了「不在能搬迁的剧本里」',
    /能搬迁的剧本/.test(message), message.slice(0, 90));
  check('错误里提到了「搬到空闲区」这条出路',
    /搬到空闲区/.test(message), message.slice(0, 120));
}

head('\n9) 没改过的内容包重建出来逐字节相同');
{
  const pack = freshPack();
  const out = buildRom(pack, rom);
  check('构建无错误', out.report.errors.length === 0, out.report.errors.join('; '));
  check('没有任何搬迁', out.report.movedScripts.length === 0);
  let diff = -1;
  for (let i = 0; i < rom.length; i++) {
    if (out.bytes[i] !== rom[i]) { diff = i; break; }
  }
  check('逐字节与原版相同', diff === -1,
    diff === -1 ? `${rom.length} 字节全等` : `0x${diff.toString(16).toUpperCase()} 处不同`);
}

head('\n10) 撤销之后内容包回到未改状态');
{
  const pack = freshPack();
  const hit = findTextInstruction(pack);
  const segment = hit.segment;
  const before = pack.changedPatchCount();
  commitSegment(pack, segment, segment.text + '测试测试');
  check('改动计数 +1', pack.changedPatchCount() === before + 1);
  pack.undo();
  check('撤销后改动计数回落', pack.changedPatchCount() === before,
    `${pack.changedPatchCount()} / ${before}`);
  const out = buildRom(pack, rom);
  check('撤销后构建无错误', out.report.errors.length === 0, out.report.errors.join('; '));
  check('撤销后不再搬迁', out.report.movedScripts.length === 0);
}

head('\n11) 别的文本表：9 张可重定位的都能变长，2 张结构上不行');
{
  // 11 张表逐张过一遍：指针表驱动的 → 变长后搬到空闲区、指针改掉；
  // 定长内联槽 / 绝对地址引用的 → 结构上只能等长。
  const kinds = new Map();
  for (const table of packData.texts) {
    const record = (table.records || [])[0];
    if (!record) continue;
    const kind = textSlotKind(table, record);
    kinds.set(table.id, kind);
  }
  check('11 张文本表都在', kinds.size === 11, `${kinds.size} 张`);
  const pointerTables = [...kinds.entries()].filter(([, k]) => k === 'pointer').map(([id]) => id);
  const fixedTables = [...kinds.entries()].filter(([, k]) => k === 'fixed').map(([id]) => id);
  const absoluteTables = [...kinds.entries()].filter(([, k]) => k === 'absolute').map(([id]) => id);
  check('9 张是指针表驱动（可变长）', pointerTables.length === 9, pointerTables.join('、'));
  check('说话人名表是定长内联槽', fixedTables.join('、') === 'speaker_names', fixedTables.join('、'));
  check('战斗目标说明是绝对地址引用',
    absoluteTables.join('、') === 'battle_objectives', absoluteTables.join('、'));

  // 每一张指针表驱动的表都试一次「变长」。
  for (const id of pointerTables) {
    const pack = freshPack();
    const table = pack.textTable(id);
    const record = (table.records || [])[0];
    const original = record.text ?? '';
    const longer = original + '测试测试';
    pack.setText(table, record, longer);
    const out = buildRom(pack, rom);
    const moved = out.report.movedTexts.find((m) => m.table === id);
    check(`${id}：变长后搬到空闲区并改写指针`,
      out.report.errors.length === 0 && !!moved,
      out.report.errors.join('；') || (moved ? `→ 0x${moved.to.toString(16).toUpperCase()}` : '没有搬迁'));
    if (!moved) continue;
    const at = moved.to;
    // 比**字节**：有些记录开头就带控制码（0x01/0x02），解码后的文本对不上前缀。
    const expected = pack.textBytes(record);
    const written = out.bytes.subarray(at, at + expected.length);
    check(`${id}：新地址上的正文逐字节就是新文本`,
      bytesToHex(written) === bytesToHex(expected),
      `${expected.length} 字节 @0x${at.toString(16).toUpperCase()}`);
  }

  // 两张结构上不行的表：变长必须**被拒**（构建时报错），不能悄悄写坏。
  for (const id of [...fixedTables, ...absoluteTables]) {
    const pack = freshPack();
    const table = pack.textTable(id);
    const record = (table.records || [])[0];
    pack.setText(table, record, `${record.text ?? ''}测试测试`);
    let error = null;
    try {
      buildRom(pack, rom);
    } catch (err) {
      error = err;
    }
    const message = error ? String(error.message || error) : '';
    check(`${id}：变长被构建器拒绝`,
      !!error && /超长|放不下/.test(message),
      message.slice(0, 80) || '没有报错');
  }
}

head('\n12) 互相重叠的剧本必须整组一起搬（改了一边另一边也得变）');
{
  // 有些剧本是另一个的**后缀**（`after.53` = `before.53` 去掉第一条指令），
  // 共享的那段里有几百段对白 —— 只搬一个的话，另一个还指着旧地址，
  // 改了共享段里的对白，另一个剧本看到的还是原文。
  const { scriptComponents } = await import('../js/storyvm.js');
  const roots = [...new Set((packData.scripts || []).map((s) => s.script_offset))];
  const components = scriptComponents(rom, roots);
  const shared = components.filter((c) => c.roots.length > 1);
  check('找得到互相重叠的剧本组', shared.length > 0, `${shared.length} 组`);

  // 挑一组，在**共享区**里找一段正文。
  let target = null;
  for (const component of shared) {
    for (const fragment of component.fragments) {
      for (const instruction of fragment.instructions) {
        if (instruction.op !== 0x01 && instruction.op !== 0x20) continue;
        const segments = textSegments(rom, freshPack(), instruction);
        if (!segments.length || !segments[0].text) continue;
        target = { component, instruction, segment: segments[0] };
        break;
      }
      if (target) break;
    }
    if (target) break;
  }
  check('在共享区里找得到一段正文', !!target,
    target ? `0x${target.instruction.offset.toString(16).toUpperCase()}` : '');

  if (target) {
    const pack = freshPack();
    const segment = textSegments(rom, pack, target.instruction)[0];
    const result = commitSegment(pack, segment, segment.text + '测试测试');
    check('共享区里的正文也能变长', result.ok === true, result.ok ? '' : result.message);
    const out = buildRom(pack, rom);
    check('构建无错误', out.report.errors.length === 0, out.report.errors.join('; '));
    const moved = out.report.movedScripts[0];
    check('搬迁记录里带着这一组的**每一个**入口',
      moved && moved.roots.length === target.component.roots.length,
      moved ? `${moved.roots.length} / ${target.component.roots.length}` : '没有搬迁记录');

    // 每个入口的根表槽都要改。
    for (const move of (moved ? moved.roots : [])) {
      const slots = rootSlotsFor(pack, move.from);
      check(`入口 0x${move.from.toString(16).toUpperCase()} 的根表槽都改了`,
        slots.length > 0 && slots.every((slot) => {
          const value = (out.bytes[slot.slot] | (out.bytes[slot.slot + 1] << 8)
            | (out.bytes[slot.slot + 2] << 16) | (out.bytes[slot.slot + 3] << 24)) >>> 0;
          return value === ROM_BASE + move.to;
        }),
        `${slots.length} 个槽`);
    }

    // 共享的字节只能搬**一份** —— 搬两份的话两个剧本会各留一份，
    // 改了其中一个另一个不变。
    const expected = hexToBytes(pack.patches.find((p) => p.offset === segment.offset).after_hex);
    let hits = 0;
    for (let at = 0; at + expected.length <= out.bytes.length; at++) {
      let same = true;
      for (let i = 0; i < expected.length; i++) {
        if (out.bytes[at + i] !== expected[i]) { same = false; break; }
      }
      if (same) hits += 1;
    }
    check('新正文在 ROM 里只有**一份**（共享字节没有搬成两份）', hits === 1,
      `找到 ${hits} 份`);
  }
}

const summary = failures === 0
  ? `全部通过（${lines.filter((l) => l.includes('[PASS]')).length} 条断言）`
  : `${failures} 项失败`;
lines.push('');
lines.push(summary);
writeFileSync(join(repoRoot, 'build', 'variable-text-verify.txt'), lines.join('\n') + '\n', 'utf8');
console.log('');
console.log(summary);
process.exit(failures === 0 ? 0 : 1);
