// 探针：剧情剧本区里的「孤儿字节」—— 不属于任何剧本片段、也不属于四张根表的字节。
//
// 用法：node tools/probe_orphan_bytes.mjs
//
// 这不是猜，是**量**：
//   * 四张根表逐槽展开（槽 0 也看），找出没被用上的槽；
//   * 剧本指令字节的**并集**覆盖了哪些区间；
//   * 剧本区跨度里还剩多少字节没人认领，切成几个连续区间；
//   * 每个区间的上下文（前后是哪条指令、属于哪个剧本）、字形文本、是否别处已有；
//   * 全 ROM 里有没有指向这些区间的 u32 指针（= 有没有漏掉的入口）；
//   * 内容包（编辑器的数据）里是否已经登记了这些地址；
//   * 场景流程表（每个剧本的「下一场景」参数）+ 占位文本普查。
//
// 地址口径：文件偏移 = ROM 字节流里的下标；ROM 地址 = 文件偏移 + 0x08000000。
// 依据：notes/evidence/story-script-relocation-20261022.md、tools/table_registry.py
import { readFileSync, writeFileSync, readdirSync } from 'node:fs';
import { gunzipSync } from 'node:zlib';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const repo = join(here, '..');

const {
  scanScript, instructionLength, branchTargets, textEnd, OPCODE_NAMES, ROM_BASE,
} = await import('../rom-editor/js/storyvm.js');
const { FontCodec } = await import('../rom-editor/js/textcodec.js');

const rom = new Uint8Array(readFileSync(join(repo, 'rom', 'base.gba')));
const pack = JSON.parse(gunzipSync(
  readFileSync(join(repo, 'rom-editor', 'content', 'pack.min.json.gz'))).toString('utf8'));
const font = new FontCodec(pack.font.code_to_char, pack.font.char_to_code);

/** 四张剧情根表（**文件偏移**）；槽号 = 场景号。 */
const ROOTS = {
  before: { base: 0x060c74, scenes: 55 },
  after: { base: 0x060d54, scenes: 55 },
  logic: { base: 0x060e34, scenes: 46 },
  events: { base: 0x060ef0, scenes: 46 },
};

const out = [];
function say(text) {
  out.push(text);
  console.log(text);
}
const hex = (v, n = 6) => `0x${v.toString(16).toUpperCase().padStart(n, '0')}`;
const opName = (op) => OPCODE_NAMES[op] || `未知操作码 ${op}`;
const read32 = (p) => (rom[p] | (rom[p + 1] << 8) | (rom[p + 2] << 16) | (rom[p + 3] << 24)) >>> 0;

// --- 1. 四张根表逐槽展开 ---------------------------------------------------
say('## 0. 四张根表逐槽');
say('');
const slots = [];
for (const [name, info] of Object.entries(ROOTS)) {
  for (let scene = 0; scene <= info.scenes; scene++) {
    const at = info.base + scene * 4;
    const value = read32(at);
    const offset = (value - ROM_BASE) >>> 0;
    let state = '空槽（0）';
    if (value !== 0) {
      const ok = offset < rom.length && scanScript(rom, offset).length > 0;
      state = ok ? `-> 文件偏移 ${hex(offset)}` : `-> ${hex(value)}（越界或解不出剧本）`;
    }
    slots.push({ name, scene, at, value, offset, state });
  }
}
const emptySlots = slots.filter((s) => s.value === 0);
say(`* 槽总数 ${slots.length}（含每张表的槽 0）`);
say(`* 空槽（值为 0）${emptySlots.length} 个：`
  + emptySlots.map((s) => `${s.name}.${s.scene}`).join('、'));
say(`* 指向解不出剧本的槽：${slots.filter((s) => s.value !== 0
  && !(s.offset < rom.length && scanScript(rom, s.offset).length > 0)).length} 个`);
say('* 逐槽清单：');
for (const s of slots) {
  if (s.value === 0) continue;
  say(`  * ${s.name}.${s.scene} @${hex(s.at)} -> 0x${s.value.toString(16).toUpperCase()} ${s.state}`);
}
say('');

// --- 2. 收集所有剧本的指令字节 + 归属 -------------------------------------
const scripts = [];
for (const [root, info] of Object.entries(ROOTS)) {
  for (let scene = 1; scene <= info.scenes; scene++) {
    const pointer = read32(info.base + scene * 4);
    if (!pointer) continue;
    const offset = (pointer - ROM_BASE) >>> 0;
    if (offset >= rom.length) continue;
    if (!scanScript(rom, offset).length) continue;
    scripts.push({ id: `${root}.${scene}`, root, scene, offset });
  }
}

const covered = new Uint8Array(rom.length);
const byteOwner = new Int32Array(rom.length).fill(-1);
const instrAt = new Map();
let spanStart = Infinity;
let spanEnd = 0;
let instrBytes = 0;
scripts.forEach((script, si) => {
  for (const ins of scanScript(rom, script.offset)) {
    instrAt.set(ins.offset, { ins, script });
    for (let i = 0; i < ins.length; i++) {
      if (!covered[ins.offset + i]) { covered[ins.offset + i] = 1; instrBytes++; }
      if (byteOwner[ins.offset + i] < 0) byteOwner[ins.offset + i] = si;
    }
    spanStart = Math.min(spanStart, ins.offset);
    spanEnd = Math.max(spanEnd, ins.offset + ins.length);
  }
});
const scriptById = new Map(scripts.map((s) => [s.id, s]));

// --- 3. 剧本区跨度内的「孤儿字节」 ----------------------------------------
const orphanMask = new Uint8Array(rom.length);
let orphanBytes = 0;
for (let p = spanStart; p < spanEnd; p++) {
  if (!covered[p]) { orphanMask[p] = 1; orphanBytes++; }
}
const runs = [];
for (let p = spanStart; p < spanEnd; p++) {
  if (!orphanMask[p]) continue;
  const start = p;
  while (p < spanEnd && orphanMask[p]) p++;
  runs.push({ start, end: p, size: p - start });
}
const bigRuns = runs.filter((r) => r.size >= 5);
const bigBytes = bigRuns.reduce((n, r) => n + r.size, 0);

// --- 4. 已知表（登记册 + content bank） ----------------------------------
const registryText = readFileSync(join(repo, 'tools', 'table_registry.py'), 'utf8');
const registry = [...registryText.matchAll(
  /"([A-Za-z0-9_]+)":\s*\(\s*0x([0-9A-Fa-f]+)\s*,\s*(True|False)/g,
)].map((m) => ({
  name: m[1], base: parseInt(m[2], 16), verified: m[3] === 'True',
}));
const banks = [];
const contentRoot = join(repo, 'sequel', 'content');
for (const dir of readdirSync(contentRoot, { withFileTypes: true })) {
  if (!dir.isDirectory()) continue;
  let data;
  try {
    data = JSON.parse(readFileSync(join(contentRoot, dir.name, 'bank.json'), 'utf8'));
  } catch { continue; }
  if (typeof data.table_offset !== 'number') continue;
  banks.push({
    bank: dir.name, offset: data.table_offset,
    count: data.entry_count || 1, size: data.entry_size || 4,
  });
}
const knownTables = registry.map((t) => {
  const bank = banks.find((b) => b.offset === t.base);
  return {
    name: t.name, base: t.base, verified: t.verified,
    length: bank ? bank.count * bank.size : null,
    bank: bank ? bank.bank : null,
  };
});

// --- 5. 工具函数 -----------------------------------------------------------
function hexDump(start, end, max = 48) {
  const rows = [];
  const stop = Math.min(end, start + max);
  for (let p = start; p < stop; p += 16) {
    const n = Math.min(16, stop - p);
    const bytes = [...rom.subarray(p, p + n)].map((b) => b.toString(16).padStart(2, '0'));
    rows.push(`${hex(p)}  ${bytes.join(' ')}`);
  }
  return rows;
}

function walkLinear(start, end) {
  const list = [];
  let p = start;
  while (p < end) {
    const len = instructionLength(rom, p);
    if (!len || p + len > end) {
      list.push({ offset: p, op: rom[p], length: len, truncated: true });
      break;
    }
    list.push({ offset: p, op: rom[p], length: len });
    p += len;
  }
  return list;
}

function textOf(ins) {
  const TEXT_OPS = { 1: 1, 5: 2, 32: 2 };
  const d = TEXT_OPS[ins.op];
  if (d !== undefined) {
    const stop = textEnd(rom, ins.offset + d);
    return font.decode(rom.subarray(ins.offset + d, stop - 1));
  }
  if (ins.op === 19) {
    const stop = textEnd(rom, ins.offset + 4);
    const t1 = font.decode(rom.subarray(ins.offset + 4, stop - 1));
    if (rom[ins.offset + 2]) {
      const stop2 = textEnd(rom, stop + 1);
      return `${t1} || ${font.decode(rom.subarray(stop + 1, stop2 - 1))}`;
    }
    return t1;
  }
  return null;
}

function owningInstruction(p) {
  for (let q = p; q >= 0 && q >= p - 16; q--) {
    const hit = instrAt.get(q);
    if (hit && hit.ins.offset + hit.ins.length > p) return hit;
  }
  const si = byteOwner[p];
  return si >= 0 ? { ins: { offset: p, op: rom[p], length: 0 }, script: scripts[si] } : null;
}

function describeNeighbour(p) {
  const hit = owningInstruction(p);
  if (!hit) return null;
  const { ins, script } = hit;
  const bytes = [...rom.subarray(ins.offset, Math.min(ins.offset + 8, rom.length))]
    .map((b) => b.toString(16).padStart(2, '0')).join(' ');
  return {
    offset: ins.offset,
    op: ins.op,
    name: opName(ins.op),
    script: script ? script.id : '?',
    bytes,
    covers: `${hex(ins.offset)}..${hex(ins.offset + ins.length)}`,
  };
}

function describeInstruction(ins) {
  const t = textOf(ins);
  const targets = branchTargets(rom, ins.offset, ins.length);
  let line = `${hex(ins.offset)} op=0x${ins.op.toString(16).toUpperCase()}`
    + `「${opName(ins.op)}」${ins.length} 字节`;
  if (targets.length) line += ` 目标 ${targets.map((x) => hex(x)).join('、')}`;
  if (t !== null) line += ` 文本「${t.replace(/\n/g, '⏎')}」`;
  return line;
}

// --- 6. 全 ROM 指针扫描 ----------------------------------------------------
const runIndex = new Map();
for (let i = 0; i < runs.length; i++) {
  for (let p = runs[i].start; p < runs[i].end; p++) runIndex.set(p, i);
}
const ptrHits = runs.map(() => []);
for (let p = 0; p + 4 <= rom.length; p++) {
  const v = read32(p);
  const file = (v - ROM_BASE) >>> 0;
  if (file >= spanStart && file < spanEnd) {
    const idx = runIndex.get(file);
    if (idx !== undefined) ptrHits[idx].push({ at: p, value: v, file });
  }
}

// --- 7. 全 ROM 所有剧本的文本（用来查重复） -------------------------------
const allScriptTexts = new Set();
for (const script of scripts) {
  for (const ins of scanScript(rom, script.offset)) {
    if (![1, 5, 32, 19].includes(ins.op)) continue;
    const t = textOf(ins);
    if (t && t.trim()) allScriptTexts.add(t.trim());
  }
}

// --- 8. 输出 ---------------------------------------------------------------
say('# 剧本区「孤儿字节」探针');
say('');
say(`ROM ${rom.length} 字节；ROM 地址 = 文件偏移 + 0x${ROM_BASE.toString(16).toUpperCase()}`);
say(`剧本 ${scripts.length} 个（不同起始地址 ${new Set(scripts.map((s) => s.offset)).size} 个）`);
say(`剧本指令字节并集：${instrBytes} 字节`);
say(`剧本区跨度：${hex(spanStart)}..${hex(spanEnd)} —— ${spanEnd - spanStart} 字节`);
say('四张根表在 0x060C74..0x060FAC，**在跨度之外**，标记它们不影响跨度内的孤儿计数');
say(`跨度内既不属于剧本片段、也不属于根表的字节：**${orphanBytes} 字节**，`
  + `切成 ${runs.length} 个连续区间`);
say(`其中 >=5 字节的区间：${bigRuns.length} 个，合计 **${bigBytes} 字节**`);
say(`其中 <5 字节的区间：${runs.length - bigRuns.length} 个，`
  + `合计 ${orphanBytes - bigBytes} 字节`);
say('');

say('## 1. 孤儿字节区间清单');
say('');
say('| # | 文件偏移区间 | 字节数 | ROM 地址区间 | 落在登记册的表里？ | 全 ROM 指针命中 |');
say('|---|---|---|---|---|---|');
for (let i = 0; i < runs.length; i++) {
  const r = runs[i];
  const inTable = knownTables.filter((t) => {
    const hi = t.length !== null ? t.base + t.length : t.base + 0x2000;
    return t.base < r.end && r.start < hi;
  }).map((t) => t.name).join('、') || '否';
  const hits = ptrHits[i];
  const hitText = hits.length
    ? `${hits.length} 处（${hits.slice(0, 3).map((h) => hex(h.at)).join('、')}${hits.length > 3 ? '…' : ''}）`
    : '0';
  say(`| ${i + 1} | ${hex(r.start)}..${hex(r.end)} | ${r.size} | `
    + `${hex(r.start + ROM_BASE, 8)}..${hex(r.end + ROM_BASE, 8)} | ${inTable} | ${hitText} |`);
}
say('');

say('## 2. >=5 字节的孤儿区间：上下文 / 内容 / 文本');
say('');
for (const r of bigRuns) {
  const idx = runs.indexOf(r);
  say(`### ${hex(r.start)}..${hex(r.end)} —— ${r.size} 字节`);
  const prev = describeNeighbour(r.start - 1);
  const next = describeNeighbour(r.end);
  if (prev) {
    say(`* 前一条有主指令：${prev.covers} op=0x${prev.op.toString(16).toUpperCase()}`
      + `「${prev.name}」属于 ${prev.script} —— ${prev.bytes}`);
  }
  if (next) {
    say(`* 后一条有主指令：${next.covers} op=0x${next.op.toString(16).toUpperCase()}`
      + `「${next.name}」属于 ${next.script} —— ${next.bytes}`);
  }
  const hits = ptrHits[idx];
  say(`* 全 ROM 指向本区间的 u32 常量：${hits.length} 处`);
  for (const h of hits) {
    const around = [...rom.subarray(Math.max(0, h.at - 8), h.at + 12)]
      .map((b) => b.toString(16).padStart(2, '0')).join(' ');
    say(`  * 文件偏移 ${hex(h.at)} -> 0x${h.value.toString(16).toUpperCase()}`
      + `（文件偏移 ${hex(h.file)}）周边字节 ${around}`);
  }
  const self = scanScript(rom, r.start);
  const selfBytes = self.reduce((n, i) => n + i.length, 0);
  const selfEnd = self.length ? Math.max(...self.map((i) => i.offset + i.length)) : 0;
  say(`* 自洽性：把它当剧本入口扫一遍 -> ${self.length} 条指令、覆盖 ${selfBytes} 字节、`
    + `扫到 ${hex(selfEnd)}（块尾 ${hex(r.end)}）`
    + `${selfEnd === r.end ? ' -> **正好整块**' : ' -> 与块尾差 1 字节（末尾多一个 0x00）'}`);
  const ins = walkLinear(r.start, r.end);
  say(`* 指令流（线性）：${ins.length} 条`);
  for (const i of ins) {
    let line = `  ${describeInstruction(i)}`;
    if (i.truncated) line += ' !!! 指令长度超出区间';
    say(line);
  }
  say('* 十六进制（头 48 字节）：');
  for (const line of hexDump(r.start, r.end, 48)) say(`  ${line}`);
  say('* 十六进制（尾 48 字节）：');
  for (const line of hexDump(Math.max(r.start, r.end - 48), r.end, 48)) say(`  ${line}`);
  const dup = [];
  for (const i of ins) {
    const t = textOf(i);
    if (t && t.trim()) dup.push(`${allScriptTexts.has(t.trim()) ? '重复' : '★独有'}「${t.replace(/\n/g, '⏎')}」`);
  }
  say(`* 文本是否在 202 个剧本里出现过：${dup.length ? dup.join('；') : '（本区间没有文本指令）'}`);
  const packText = JSON.stringify(pack);
  const packHits = [];
  for (const form of [hex(r.start + ROM_BASE, 8).slice(2), hex(r.start, 8).slice(2),
    hex(r.end + ROM_BASE, 8).slice(2), hex(r.end, 8).slice(2)]) {
    if (packText.toLowerCase().includes(form.toLowerCase())) packHits.push(form);
  }
  say(`* 内容包 pack.min.json.gz 里出现过的本区间地址：`
    + `${packHits.length ? packHits.join('、') : '（无）'}`);
  say('');
}

say('## 3. <5 字节的孤儿区间（汇总）');
say('');
const tiny = runs.filter((r) => r.size < 5);
const tinyHist = new Map();
for (const r of tiny) {
  for (let p = r.start; p < r.end; p++) {
    const key = rom[p].toString(16).padStart(2, '0');
    tinyHist.set(key, (tinyHist.get(key) || 0) + 1);
  }
}
say(`* ${tiny.length} 个区间，${tiny.reduce((n, r) => n + r.size, 0)} 字节`);
say(`* 字节分布：${[...tinyHist.entries()].sort((a, b) => b[1] - a[1])
  .map(([b, n]) => `0x${b.toUpperCase()}×${n}`).join(' ')}`);
say('* 每个都紧跟在一个分支/跳转之后 —— 是被跳过的「结束脚本」终止符。');
say('');

say('## 4. 登记册里落在剧本区跨度内的表（确认它们已被剧本覆盖，不是孤儿）');
say('');
say(`* 剧本区跨度 = 文件偏移 ${hex(spanStart)}..${hex(spanEnd)}`
  + `（= ${spanStart}..${spanEnd} 字节）`);
say(`* 登记册里基址 **小于** 剧本区末端的表（= 有可能落在区内的）：`);
const below = knownTables.filter((t) => t.base < spanEnd).sort((a, b) => a.base - b.base);
for (const t of below) {
  const inside = t.base >= spanStart;
  say(`  * ${hex(t.base)} ${t.name}（verified=${t.verified}）`
    + ` —— ${inside ? '**落在剧本区内**' : '在剧本区之前（不属于剧本区）'}`);
}
if (!below.some((t) => t.base >= spanStart)) {
  say('  * ⇒ **剧本区里没有任何一张登记在册的表**'
    + '（四张剧情根表在 0x060C74..0x060FAC，落在剧本区**之后**）。');
}
say(`* 任务书里提到的表在哪儿：`);
for (const name of ['portrait_table', 'palette_source_table', 'character_names']) {
  const t = knownTables.find((x) => x.name === name);
  if (!t) continue;
  say(`  * ${name} = 文件偏移 ${hex(t.base)}（ROM ${hex(t.base + ROM_BASE, 8)}）`
    + ` —— ${t.base < spanStart ? '在剧本区之前' : t.base >= spanEnd ? '**在剧本区之后**（剧本区末尾才 0x'
        + hex(spanEnd).slice(2) + '）' : '在剧本区内'}`);
}
say('');

say('## 5. 根表邻域（根表前后各 64 字节）');
say('');
for (const line of hexDump(0x060c40, 0x061020, 0x400)) say(line);
say('');

say('## 6. 大孤儿块两侧剧本的正文（首 6 / 末 6 条指令）');
say('');
for (const r of bigRuns) {
  const prev = describeNeighbour(r.start - 1);
  const next = describeNeighbour(r.end);
  say(`### 孤儿块 ${hex(r.start)}..${hex(r.end)}`);
  for (const side of [prev, next]) {
    if (!side) continue;
    const entry = scriptById.get(side.script);
    if (!entry) continue;
    const list = scanScript(rom, entry.offset);
    say(`* ${side.script}（入口 ${hex(entry.offset)}，${list.length} 条指令）的`
      + `${side.script.startsWith('after') ? '前' : '后'} 6 条：`);
    const pick = side.script.startsWith('after') ? list.slice(-6) : list.slice(0, 6);
    for (const i of pick) say(`  ${describeInstruction(i)}`);
  }
  say('');
}

say('## 7. 场景流程表（每个剧本里的「下一场景」参数）');
say('');
say('| 场景 | before 入口 | before 的下一场景 | after 入口 | after 的下一场景 | 备注 |');
say('|---|---|---|---|---|---|');
function nextSceneParams(entry) {
  if (!entry) return '—';
  const list = scanScript(rom, entry.offset);
  const params = [];
  for (const ins of list) {
    if (ins.op === 26 || ins.op === 22) {
      params.push(`${ins.op === 26 ? '带相位' : '下一场景'}(${rom[ins.offset + 1]},${rom[ins.offset + 2] ?? 0})`);
    }
  }
  return params.length ? params.join(' ') : '（无）';
}
for (let scene = 1; scene <= 55; scene++) {
  const b = scriptById.get(`before.${scene}`);
  const a = scriptById.get(`after.${scene}`);
  const note = b && a && b.offset === a.offset ? 'before/after 同一份' : '';
  say(`| ${scene} | ${b ? hex(b.offset) : '—'} | ${nextSceneParams(b)} | `
    + `${a ? hex(a.offset) : '—'} | ${nextSceneParams(a)} | ${note} |`);
}
say('');

say('## 8. 剧本里出现的「占位/不可进入」类文本');
say('');
const placeholder = [];
for (const script of scripts) {
  for (const ins of scanScript(rom, script.offset)) {
    if (![1, 5, 32, 19].includes(ins.op)) continue;
    const t = textOf(ins);
    if (!t) continue;
    if (t.includes('无法进入') || t.includes('此处') || t.includes('未使用')) {
      placeholder.push(`${script.id} @${hex(ins.offset)} 「${t.replace(/\n/g, '⏎')}」`);
    }
  }
}
say(placeholder.length ? placeholder.map((x) => `* ${x}`).join('\n') : '* （没有）');
say('');

function scriptFragmentsInfo(root) {
  const list = scanScript(rom, root);
  const parts = [];
  let start = null;
  let prev = null;
  for (const ins of list) {
    if (prev === null || ins.offset !== prev) {
      if (start !== null) parts.push(`${hex(start)}..${hex(prev)}`);
      start = ins.offset;
    }
    prev = ins.offset + ins.length;
  }
  if (start !== null) parts.push(`${hex(start)}..${hex(prev)}`);
  return parts.join(' / ');
}
say('## 9. 4 字节孤儿区间（0x031068）的指针上下文');
say('');
for (const r of runs.filter((x) => x.size === 4)) {
  say(`* 区间 ${hex(r.start)}..${hex(r.end)}：${[...rom.subarray(r.start, r.end)]
    .map((b) => `0x${b.toString(16).toUpperCase().padStart(2, '0')}`).join(' ')}`);
  for (const h of ptrHits[runs.indexOf(r)]) {
    say(`* 指向它的 u32 在文件偏移 ${hex(h.at)}（ROM ${hex(h.value, 8)}）`);
    for (const line of hexDump(h.at - 32, h.at + 32, 64)) say(`  ${line}`);
    // 这一段里有多少个 u32 落在 ROM 内（= 是不是一张指针表）
    let inRom = 0;
    let total = 0;
    for (let p = h.at - 32; p < h.at + 32; p += 4) {
      total++;
      const v = read32(p);
      if (v >= ROM_BASE && v < ROM_BASE + rom.length) inRom++;
    }
    say(`* 周边 64 字节里 ${total} 个 u32 有 ${inRom} 个落在 ROM 范围内`
      + `（>60% 才算指针表）`);
  }
}
say('');

say('## 10. ORPHAN A 与「场景 54」的文本对照（忽略尾部空格）');
say('');
{
  const strip = (s) => s.replace(/[\s　]+/g, '').trim();
  const orphan = bigRuns.find((x) => x.size > 1000);
  const mine = walkLinear(orphan.start, orphan.end)
    .map((i) => textOf(i)).filter((t) => t && t.trim());
  const theirs = scanScript(rom, 0x049e76)
    .map((i) => textOf(i)).filter((t) => t && t.trim());
  const theirSet = new Set(theirs.map(strip));
  let hit = 0;
  for (const t of mine) if (theirSet.has(strip(t))) hit++;
  say(`* 孤儿块 ${hex(orphan.start)} 有 ${mine.length} 段文本；`
    + `场景 54（0x049E76）有 ${theirs.length} 段文本`);
  say(`* 忽略空格后完全相同的行：${hit} / ${mine.length}`);
  say('* 孤儿块里在场景 54 **找不到**的行：');
  for (const t of mine) if (!theirSet.has(strip(t))) say(`  * 「${t.replace(/\n/g, '⏎')}」`);
}
say('');

say('## 11. 各剧本的「剧情进度」值（op 0x14）');
say('');
for (const script of scripts) {
  const list = scanScript(rom, script.offset);
  const vals = list.filter((i) => i.op === 20).map((i) => rom[i.offset + 1]);
  if (vals.length) say(`* ${script.id}：剧情进度 = ${vals.join(', ')}`);
}
say('');
say('## 12. 小孤儿区间的前一条指令（是「结束脚本」还是「跳转」）');
say('');
const tinyOpHist = new Map();
for (const r of runs.filter((x) => x.size < 5)) {
  const hit = owningInstruction(r.start - 1);
  const key = hit ? `0x${hit.ins.op.toString(16).toUpperCase()}` : '?';
  tinyOpHist.set(key, (tinyOpHist.get(key) || 0) + 1);
}
say(`* 前一条有主指令的操作码分布：${[...tinyOpHist.entries()].sort((a, b) => b[1] - a[1])
  .map(([k, v]) => `${k}(${opName(parseInt(k, 16))})×${v}`).join(' ')}`);
say('* 0x0 = 结束脚本（扫到它就停，后面那个 0x00 永远不会被扫到）；');
say('  0x6 = 二选一分支、0x7 = 无条件跳转（这两类也不往下走）。');
say('');

say('## 13. 4 字节孤儿（0x031068）与 before.39 的关系');
say('');
{
  const b39 = scriptById.get('before.39');
  const list = scanScript(rom, b39.offset);
  const same = list.filter((i) => i.op === 26 && rom[i.offset + 1] === 0x29
    && rom[i.offset + 2] === 0x02);
  say(`* before.39 入口 ${hex(b39.offset)}，${list.length} 条指令，`
    + `片段边界 ${scriptFragmentsInfo(b39.offset)}`);
  say(`* 其中「下一场景(41, 2)」指令（0x1A 0x29 0x02）出现 ${same.length} 次：`
    + `${same.map((i) => hex(i.offset)).join('、') || '（无）'}`);
  say(`* 孤儿块 0x031068 的内容 = 0x1A 0x29 0x02 0x00 = 同样的「下一场景(41,2)」+ 结束符`);
}
say('');
writeFileSync(join(repo, 'build', 'story-orphan-bytes.txt'), out.join('\n') + '\n', 'utf8');
console.log('已写入 build/story-orphan-bytes.txt');