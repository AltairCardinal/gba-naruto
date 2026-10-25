// 探针：把某一**剧情场景**的剧本开头按 `0x15`（比较器条件跳转）解出来，
// 看它是不是「按剧情进度分支的入口」。
//
// **为什么需要它**：场景号空间里，50 / 51 / 54 这三场不是普通戏 ——
// 它们开头是一串按**剧情进度**（`state[0x10]` = `0x020311E4`）比较的
// `0x15`，把主线分流到不同分支。
// 其中 **54 = 主线入口**：开机 → 标题 → START 之后走的就是它，
// 进度 < 27 时落到开局的过场（鸣人毕业 / 一乐拉面）。
//
// 用法：
//   node tools\probe_scene_branches.mjs 54      # 默认场景 54
//   node tools\probe_scene_branches.mjs 50
//   node tools\probe_scene_branches.mjs 54 30   # 连看 30 条指令
//
// 依据：
//   * `notes/story-vm-opcodes-20261020.md` §3（`0x15` 的语义：比较器 @+1、值 u16 @+2、目标 u32 @+4）
//   * `notes/scene-id-semantics-20261024.md` §1.3（场景 54 是主线入口）
import { readFileSync } from 'node:fs';
import { gunzipSync } from 'node:zlib';
import { dirname, join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const repo = join(dirname(fileURLToPath(import.meta.url)), '..');
const imp = (rel) => import(pathToFileURL(join(repo, rel)).href);
const { ContentPack } = await imp('rom-editor/js/pack.js');
const { scanScript, ROM_BASE, COMPARATOR_NAMES } = await imp('rom-editor/js/storyvm.js');

const pack = ContentPack.fromJSON(JSON.parse(gunzipSync(
  readFileSync(join(repo, 'rom-editor', 'content', 'pack.min.json.gz'))).toString('utf8')));
const rom = new Uint8Array(readFileSync(join(repo, 'rom', 'base.gba')));

const scene = Number(process.argv[2] || 54);
const limit = Number(process.argv[3] || 14);
const root = pack.structure('story_before_root');
const record = root.records[scene];
if (!record) {
  console.error(`场景 ${scene} 不在 before 根表里。`);
  process.exit(1);
}
const ptr = record.values.ptr >>> 0;
console.log(`scene ${scene} -> 0x${ptr.toString(16).toUpperCase()}`);

const instructions = scanScript(rom, ptr - ROM_BASE);
console.log('instructions:', instructions.length);
for (const ins of instructions.slice(0, limit)) {
  const op = ins.op;
  let extra = '';
  if (op === 0x15) {
    const cmp = rom[ins.offset + 1];
    const value = rom[ins.offset + 2] | (rom[ins.offset + 3] << 8);
    const target = (rom[ins.offset + 4] | (rom[ins.offset + 5] << 8) |
      (rom[ins.offset + 6] << 16) | (rom[ins.offset + 7] << 24)) >>> 0;
    extra = `  cmp=${COMPARATOR_NAMES[cmp] || cmp} value=${value} -> 0x${target.toString(16).toUpperCase()}`;
  } else if (op === 0x07 || op === 0x0b || op === 0x0c) {
    const target = (rom[ins.offset + 1] | (rom[ins.offset + 2] << 8) |
      (rom[ins.offset + 3] << 16) | (rom[ins.offset + 4] << 24)) >>> 0;
    extra = `  -> 0x${target.toString(16).toUpperCase()}`;
  }
  console.log(`  0x${(ins.offset + ROM_BASE).toString(16).toUpperCase()} op=0x${op.toString(16).padStart(2, '0')}${extra}`);
}
