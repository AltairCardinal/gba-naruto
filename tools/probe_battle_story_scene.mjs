// 探针：把一关的 events 剧本按指令列出来，看 0x32 事件项与对白是怎么排的。
import { readFileSync, writeFileSync } from 'node:fs';
import { gunzipSync } from 'node:zlib';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const repo = join(here, '..');
const pack = JSON.parse(gunzipSync(
  readFileSync(join(repo, 'rom-editor', 'content', 'pack.min.json.gz'))).toString('utf8'));
const rom = new Uint8Array(readFileSync(join(repo, 'rom', 'base.gba')));
const { scanScript, ROM_BASE, OPCODE_NAMES } = await import('../rom-editor/js/storyvm.js');

const NAMES = {
  0x32: '事件表项', 0x33: '压入队列值', 0x34: '回合/相位条件', 0x35: '复合条件',
  0x36: '指定人物在场', 0x37: '置/清战斗标志', 0x38: '测战斗标志', 0x39: '子配置匹配',
  0x13: '调用子脚本', 0x01: '显示文本', 0x20: '带说话人的对话', 0x08: '设置头像与说话人',
};

const scene = Number(process.argv[2] || 5);
const out = [];
for (const [root, structId] of [['logic', 'story_logic_root'], ['events', 'story_events_root']]) {
  const struct = pack.structures.find((x) => x.id === structId);
  const rec = struct.records[scene];
  const ptr = rec.values.ptr;
  out.push(`=== ${root} 第 ${scene} 场 · 指针 0x${(ptr || 0).toString(16).toUpperCase()} ===`);
  if (!ptr) { out.push('（没有指针）'); continue; }
  const ins = scanScript(rom, ptr - ROM_BASE);
  for (const i of ins) {
    const name = NAMES[i.op] || OPCODE_NAMES[i.op] || `?`;
    const ops = [];
    for (let k = 1; k < i.length; k += 1) ops.push(`+${k}=${rom[i.offset + k]}`);
    out.push(`  0x${(i.offset + ROM_BASE).toString(16).toUpperCase()}  0x${i.op.toString(16).toUpperCase().padStart(2, '0')} ${name.padEnd(16, '　')} ${ops.join(' ')}`);
  }
  out.push('');
}
const text = out.join('\n');
writeFileSync(join(repo, 'build', `battle-story-scene${scene}.txt`), text, 'utf8');
console.log(`写到 build/battle-story-scene${scene}.txt（${out.length} 行）`);
