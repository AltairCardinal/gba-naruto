// 探针：`0x20` 是什么 —— 它是消息框的**名字行**，与后面那条 `0x01` 是**同一条消息**。
//
// 用法：
//   node tools\probe_dialogue_name_row.mjs              # 全 ROM 扫描 + 场景 54 第 1 条消息
//   node tools\probe_dialogue_name_row.mjs 1 54         # 第 1 场
//   node tools\probe_dialogue_name_row.mjs --shot notes\evidence\scene54-first-message-20261024.png
//
// 依据：notes/evidence/dialogue-name-row-20261024.md
import { readFileSync } from 'node:fs';
import { gunzipSync } from 'node:zlib';
import { dirname, join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const repo = join(dirname(fileURLToPath(import.meta.url)), '..');
const imp = (rel) => import(pathToFileURL(join(repo, rel)).href);
const { ContentPack } = await imp('rom-editor/js/pack.js');
const { scanScript, ROM_BASE } = await imp('rom-editor/js/storyvm.js');
const { scanRun } = await imp('rom-editor/js/scripttext.js');

const pack = ContentPack.fromJSON(JSON.parse(gunzipSync(
  readFileSync(join(repo, 'rom-editor', 'content', 'pack.min.json.gz'))).toString('utf8')));
const rom = new Uint8Array(readFileSync(join(repo, 'rom', 'base.gba')));
const font = pack.font;

const TEXT_OPS = new Set([0x01, 0x05, 0x13, 0x20]);
const ROOTS = ['story_before_root', 'story_after_root', 'story_logic_root', 'story_events_root'];

// --- 1) 全 ROM 扫一遍 `0x20` 的用法 --------------------------------------
console.log('=== 1) 全 ROM 的 0x20：下一条**文本**指令是什么 ===');
const tally = new Map();
const between = new Map();
let total = 0;
for (const rootId of ROOTS) {
  const root = pack.structure(rootId);
  for (let scene = 1; scene < root.records.length; scene++) {
    const ptr = root.records[scene].values.ptr >>> 0;
    if (!ptr) continue;
    const instructions = scanScript(rom, ptr - ROM_BASE);
    for (let i = 0; i < instructions.length; i++) {
      if (instructions[i].op !== 0x20) continue;
      total += 1;
      let j = i + 1;
      const middle = [];
      while (j < instructions.length && !TEXT_OPS.has(instructions[j].op)) {
        middle.push(instructions[j].op);
        j += 1;
      }
      const nextOp = instructions[j] ? instructions[j].op : -1;
      tally.set(nextOp, (tally.get(nextOp) || 0) + 1);
      for (const op of middle) between.set(op, (between.get(op) || 0) + 1);
    }
  }
}
console.log(`0x20 共 ${total} 处；下一条文本指令：`);
for (const [op, n] of [...tally.entries()].sort((a, b) => b[1] - a[1])) {
  console.log(`  op=0x${op.toString(16).padStart(2, '0')}  ${n} 处`);
}
console.log('中间夹的指令：');
for (const [op, n] of [...between.entries()].sort((a, b) => b[1] - a[1])) {
  console.log(`  op=0x${op.toString(16).padStart(2, '0')}  ${n} 处`);
}

// --- 2) 某一场的第一条消息：两条指令摊开 ----------------------------------
const args = process.argv.slice(2).filter((a) => !a.startsWith('--'));
const scene = Number(args[1] || 54);
console.log(`\n=== 2) 场景 ${scene} 的开头两条文本指令 ===`);
const ptr = pack.structure('story_before_root').records[scene].values.ptr >>> 0;
const instructions = scanScript(rom, ptr - ROM_BASE);
let shown = 0;
for (const ins of instructions) {
  if (ins.op !== 0x20 && ins.op !== 0x01) continue;
  if (shown >= 2) break;
  shown += 1;
  console.log(`\n0x${(ins.offset + ROM_BASE).toString(16).toUpperCase()} op=0x${ins.op.toString(16).padStart(2, '0')} len=${ins.length}`);
  console.log(`  bytes: ${[...rom.slice(ins.offset, ins.offset + ins.length)].map((b) => b.toString(16).padStart(2, '0')).join(' ')}`);
  const start = ins.op === 0x20 ? ins.offset + 2 : ins.offset + 1;
  const run = rom.slice(start, ins.offset + ins.length - 1);
  const tokens = scanRun(run);
  console.log(`  token 流（${tokens.length} 个）：`);
  for (const t of tokens) {
    if (t.k === 'c') { console.log(`    控制码 ${t.b.map((b) => b.toString(16)).join(' ')}`); continue; }
    const ch = font.codeToChar.get(t.c);
    const label = t.c === 10 ? '↵' : t.c === 0x8140 ? '　' : (ch || `?${t.c.toString(16)}`);
    console.log(`    0x${t.c.toString(16).toUpperCase().padStart(4, '0')} ${label}`);
  }
}

// --- 3) 真机截图：量名字行 / 正文行的范围与颜色 ----------------------------
const shotIndex = process.argv.indexOf('--shot');
if (shotIndex >= 0 && process.argv[shotIndex + 1]) {
  const { decodePng } = await imp('rom-editor/tools/png.mjs');
  const file = process.argv[shotIndex + 1];
  const png = decodePng(readFileSync(join(repo, file)));
  const W = png.width;
  const FILL = [0xe7, 0xf7, 0xd6];
  const isFill = (r, g, b) => Math.abs(r - FILL[0]) < 6 && Math.abs(g - FILL[1]) < 6 && Math.abs(b - FILL[2]) < 6;
  console.log(`\n=== 3) 真机截图 ${file} 的框内两行 ===`);
  for (const [label, y0, y1] of [['名字行', 103, 120], ['正文行', 120, 136]]) {
    let minX = 1e9;
    let maxX = -1;
    let minY = 1e9;
    let maxY = -1;
    const colors = new Map();
    for (let y = y0; y < y1; y++) {
      for (let x = 12; x < W - 12; x++) {
        const at = (y * W + x) * 4;
        const r = png.pixels[at];
        const g = png.pixels[at + 1];
        const b = png.pixels[at + 2];
        if (isFill(r, g, b)) continue;
        if (x < minX) minX = x;
        if (x > maxX) maxX = x;
        if (y < minY) minY = y;
        if (y > maxY) maxY = y;
        const key = `#${[r, g, b].map((v) => v.toString(16).padStart(2, '0')).join('')}`;
        colors.set(key, (colors.get(key) || 0) + 1);
      }
    }
    const top = [...colors.entries()].sort((a, b) => b[1] - a[1]).slice(0, 4)
      .map(([k, n]) => `${k}(${n})`).join(' ');
    console.log(`  ${label}: x=${minX}..${maxX}  y=${minY}..${maxY}   ${top}`);
  }
}
