// 探针：场景 32..38 的 events 根在 logic 剧本内部 —— scanScript(logicRoot) 会不会把 events 也吸进来？
import { readFileSync, writeFileSync } from 'node:fs';
import { gunzipSync } from 'node:zlib';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const repo = join(here, '..');
const pack = JSON.parse(gunzipSync(
  readFileSync(join(repo, 'rom-editor', 'content', 'pack.min.json.gz'))).toString('utf8'));
const rom = new Uint8Array(readFileSync(join(repo, 'rom', 'base.gba')));
const { scanScript, ROM_BASE } = await import('../rom-editor/js/storyvm.js');

const out = [];
for (const scene of [32, 33, 34, 35, 36, 37, 38, 40, 5]) {
  const lg = pack.structures.find((x) => x.id === 'story_logic_root').records[scene];
  const ev = pack.structures.find((x) => x.id === 'story_events_root').records[scene];
  const lRoot = lg.values.ptr;
  const eRoot = ev.values.ptr;
  const lIns = scanScript(rom, lRoot - ROM_BASE);
  const eIns = scanScript(rom, eRoot - ROM_BASE);
  const lOps = lIns.map((i) => i.op);
  const eOps = eIns.map((i) => i.op);
  const first32 = lOps.indexOf(0x32);
  const chainInLogic = first32 >= 0 ? lOps.slice(first32).filter((o) => o === 0x32).length : 0;
  out.push(`--- 场景 ${scene} ---`);
  out.push(`  logic 根 = 0x${lRoot.toString(16).toUpperCase()}  指令 ${lIns.length} 条  首个 0x32 在第 ${first32} 条`);
  out.push(`  events 根 = 0x${eRoot.toString(16).toUpperCase()}  指令 ${eIns.length} 条  链长 ${eOps.filter((o) => o === 0x32).length}`);
  out.push(`  events 根 - logic 根 = ${eRoot - lRoot} 字节`);
  out.push(`  logic 扫描里含 0x32 共 ${chainInLogic} 条；events 扫描里含 0x32 共 ${eOps.filter((o) => o === 0x32).length} 条`);
  out.push(`  logic 前 ${first32} 条的 opcode：${lOps.slice(0, first32).map((o) => '0x' + o.toString(16)).join(' ')}`);
  // 压入值
  const pushes = lIns.filter((i) => i.op === 0x33).map((i) => rom[i.offset + 1]);
  out.push(`  logic 压入的值：${pushes.join(',')}`);
  out.push('');
}
const text = out.join('\n');
writeFileSync(join(repo, 'build', 'battle-story-overlap.txt'), text, 'utf8');
console.log(text);
