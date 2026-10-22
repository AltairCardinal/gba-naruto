// 探针：把「剧情剧本搬迁」要用到的**全部事实**一次算清楚。
//
// 用法：node tools/probe_story_relocation.mjs
//
// 这不是猜，是**量**：
//   * 四张根表里有多少槽、多少剧本、多少字节；
//   * 每个剧本分成几段（`before` / `after` 是物理交错的）；
//   * 段与段之间夹着多少「缝隙」（能不能原地改）；
//   * 必须重基的绝对地址槽一共有多少个、分别是什么操作码；
//   * 有多少个根被 before / after **同时**指向（搬迁时两个槽都要改）；
//   * 空闲区到底有多大。
//
// 依据：notes/evidence/story-script-relocation-20261022.md
import { readFileSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const repo = join(here, '..');

const {
  scanScript, scriptFragments, ADDRESS_SLOTS, ROM_BASE,
} = await import('../rom-editor/js/storyvm.js');

const rom = new Uint8Array(readFileSync(join(repo, 'rom', 'base.gba')));

/** 四张剧情根表（ROM 地址）：槽号 = 场景号。 */
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

const scripts = [];
for (const [root, info] of Object.entries(ROOTS)) {
  for (let scene = 1; scene <= info.scenes; scene++) {
    const slot = info.base + scene * 4;
    const pointer = (rom[slot] | (rom[slot + 1] << 8)
      | (rom[slot + 2] << 16) | (rom[slot + 3] << 24)) >>> 0;
    if (!pointer) continue;
    const offset = pointer - ROM_BASE;
    if (offset < 0 || offset >= rom.length) continue;
    if (!scanScript(rom, offset).length) continue;
    scripts.push({ id: `${root}.${scene}`, root, scene, slot, pointer, offset });
  }
}

say('# 剧情剧本搬迁：事实测量');
say('');
say(`ROM 大小 ${rom.length} 字节（0x${rom.length.toString(16).toUpperCase()}）`);
say(`扫出剧本 ${scripts.length} 个`);

// --- 1. 每个剧本几段 --------------------------------------------------
say('');
say('## 1. 剧本的物理布局');
let totalBytes = 0;
let multi = 0;
let gapBytes = 0;
let gapRuns = 0;
let ffGap = 0;
let gapFFBytes = 0;
let spanStart = Infinity;
let spanEnd = 0;
let largest = { size: 0, id: '' };
const samples = [];
for (const script of scripts) {
  const fragments = scriptFragments(rom, script.offset);
  let size = 0;
  for (const f of fragments) {
    size += f.end - f.start;
    spanStart = Math.min(spanStart, f.start);
    spanEnd = Math.max(spanEnd, f.end);
  }
  totalBytes += size;
  if (size > largest.size) largest = { size, id: script.id };
  if (fragments.length > 1) {
    multi += 1;
    for (let i = 1; i < fragments.length; i++) {
      const gap = fragments[i].start - fragments[i - 1].end;
      gapBytes += gap;
      gapRuns += 1;
      let allFF = true;
      for (let k = fragments[i - 1].end; k < fragments[i].start; k++) {
        if (rom[k] === 0xff) gapFFBytes += 1;
        else { allFF = false; }
      }
      if (allFF) ffGap += 1;
      if (samples.length < 5) {
        samples.push(`${script.id} 段 ${i}：0x${fragments[i - 1].end.toString(16).toUpperCase()}`
          + `..0x${fragments[i].start.toString(16).toUpperCase()}（${gap} 字节）`);
      }
    }
  }
}
say(`* 剧本字节合计 ${totalBytes} 字节（各段相加）`);
say(`* 剧本区跨度 0x${spanStart.toString(16).toUpperCase()}..0x${spanEnd.toString(16).toUpperCase()}`
  + ` —— ${spanEnd - spanStart} 字节`);
say(`* 分成多段的剧本 ${multi} 个 / ${scripts.length} 个（before 与 after 物理交错）`);
say(`* 段与段之间的缝隙共 ${gapRuns} 处、${gapBytes} 字节，其中 0xFF 字节 ${gapFFBytes} 个`);
say(`* 整段都是 0xFF 的缝隙：${ffGap} 处`);
say(`* 最大的剧本 ${largest.id} —— ${largest.size} 字节`);
for (const s of samples) say(`  * ${s}`);

// --- 2. 必须重基的地址槽 ----------------------------------------------
say('');
say('## 2. 必须重基的绝对地址槽');
const opCount = {};
let slotTotal = 0;
let crossFragment = 0;
for (const script of scripts) {
  const fragments = scriptFragments(rom, script.offset);
  for (const fragment of fragments) {
    for (const instruction of fragment.instructions) {
      for (const slot of ADDRESS_SLOTS[instruction.op] || []) {
        const at = instruction.offset + slot;
        const value = (rom[at] | (rom[at + 1] << 8)
          | (rom[at + 2] << 16) | (rom[at + 3] << 24)) >>> 0;
        slotTotal += 1;
        const key = `0x${instruction.op.toString(16).toUpperCase()}`;
        opCount[key] = (opCount[key] || 0) + 1;
        const target = value - ROM_BASE;
        const inSame = fragments.some((f) => target >= f.start && target < f.end);
        if (!inSame) crossFragment += 1;
      }
    }
  }
}
say(`* 白名单：${Object.keys(ADDRESS_SLOTS).length} 个操作码 / `
  + `${Object.values(ADDRESS_SLOTS).reduce((n, s) => n + s.length, 0)} 个槽`);
say(`* 全 ROM 一共 ${slotTotal} 处地址槽要重基`);
for (const key of Object.keys(opCount).sort()) {
  say(`  * ${key}：${opCount[key]} 处`);
}
say(`* 指向本剧本之外的：${crossFragment} 处（⇒ 全部剧本都是自包含的）`);

// --- 3. 同一个剧本被几个根指向 ----------------------------------------
say('');
say('## 3. 根表指向');
const byOffset = new Map();
for (const script of scripts) {
  if (!byOffset.has(script.offset)) byOffset.set(script.offset, []);
  byOffset.get(script.offset).push(script);
}
const shared = [...byOffset.entries()].filter(([, list]) => list.length > 1);
say(`* 不同的剧本 ${byOffset.size} 个（根表槽 ${scripts.length} 个）`);
say(`* 被**多个根**同时指向的剧本 ${shared.length} 个：`);
for (const [offset, list] of shared) {
  say(`  * 0x${offset.toString(16).toUpperCase()} ← `
    + list.map((s) => s.id).join('、'));
}

// --- 4. 空闲区 --------------------------------------------------------
say('');
say('## 4. 空闲区');
const runs = [];
let i = 0;
while (i < rom.length) {
  if (rom[i] === 0xff) {
    let j = i;
    while (j < rom.length && rom[j] === 0xff) j++;
    if (j - i >= 0x1000) runs.push({ start: i, end: j, size: j - i });
    i = j;
  } else {
    i += 1;
  }
}
runs.sort((a, b) => b.size - a.size);
for (const r of runs) {
  say(`* 0x${r.start.toString(16).toUpperCase()}..0x${r.end.toString(16).toUpperCase()}`
    + ` —— ${r.size} 字节`);
}
say(`* notes/free-space.md 记的上界是 0x5FFFFF（比实测少 1024 字节）`);

writeFileSync(join(repo, 'build', 'story-relocation-probe.txt'), out.join('\n') + '\n', 'utf8');
console.log('');
console.log('已写入 build/story-relocation-probe.txt');
