// 探针：数一数每一关的「战场事件表」里有多少条触发项。
// 一次跑完，把结果写到 build/ 里（stdout 会被 PowerShell 的 GBK 编码弄乱）。
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

const NAMES = {
  0x32: '事件表项', 0x33: '压入队列值', 0x34: '回合/相位条件', 0x35: '复合条件',
  0x36: '指定人物在场', 0x37: '置/清战斗标志', 0x38: '测战斗标志', 0x39: '子配置匹配',
  0x0D: '调用子脚本', 0x01: '显示文本', 0x20: '带说话人的对话', 0x08: '设置头像与说话人',
  0x13: '双段文本',
};

const rows = [];
for (const root of ['logic', 'events']) {
  const scripts = (pack.scripts || []).filter((s) => s.root === root);
  for (const s of scripts) {
    const struct = pack.structures.find(
      (x) => x.id === (root === 'logic' ? 'story_logic_root' : 'story_events_root'));
    const record = struct.records[s.scene];
    const ptr = record.values.ptr;
    if (!ptr) continue;
    const ins = scanScript(rom, ptr - ROM_BASE);
    const count = {};
    for (const i of ins) count[i.op] = (count[i.op] || 0) + 1;
    rows.push({
      root, scene: s.scene, n: ins.length,
      chain: count[0x32] || 0, push: count[0x33] || 0,
      cond: (count[0x34] || 0) + (count[0x35] || 0) + (count[0x36] || 0)
        + (count[0x38] || 0) + (count[0x39] || 0),
      flag: count[0x37] || 0, sub: count[0x0D] || 0, dual: count[0x13] || 0,
      text: (count[0x01] || 0) + (count[0x20] || 0),
    });
  }
}

const sum = (arr, k) => arr.reduce((n, r) => n + r[k], 0);
const stat = (arr, k) => {
  const v = arr.map((r) => r[k]).sort((a, b) => a - b);
  return `min=${v[0]} 中位=${v[Math.floor(v.length / 2)]} max=${v[v.length - 1]} 合计=${sum(arr, k)}`;
};

const out = [];
for (const root of ['logic', 'events']) {
  const arr = rows.filter((r) => r.root === root);
  out.push(`=== ${root} （${arr.length} 个场景）===`);
  out.push(`  指令数        ${stat(arr, 'n')}`);
  out.push(`  0x32 事件表项  ${stat(arr, 'chain')}`);
  out.push(`  0x33 压队列值  ${stat(arr, 'push')}`);
  out.push(`  条件(0x34-39) ${stat(arr, 'cond')}`);
  out.push(`  0x37 战斗标志  ${stat(arr, 'flag')}`);
  out.push(`  0x0D 调用子脚本 ${stat(arr, 'sub')}`);
  out.push(`  0x13 双段文本  ${stat(arr, 'dual')}`);
  out.push(`  文本指令      ${stat(arr, 'text')}`);
  out.push('');
}
out.push('=== 逐场景（events）===');
out.push('scene  指令  事件项  压队  条件  文本');
for (const r of rows.filter((x) => x.root === 'events').sort((a, b) => a.scene - b.scene)) {
  out.push(`${String(r.scene).padStart(4)}  ${String(r.n).padStart(4)}  ${String(r.chain).padStart(6)}  ${String(r.push).padStart(4)}  ${String(r.cond).padStart(4)}  ${String(r.text).padStart(4)}`);
}
out.push('');
out.push('=== 逐场景（logic）===');
out.push('scene  指令  压队  条件');
for (const r of rows.filter((x) => x.root === 'logic').sort((a, b) => a.scene - b.scene)) {
  out.push(`${String(r.scene).padStart(4)}  ${String(r.n).padStart(4)}  ${String(r.push).padStart(4)}  ${String(r.cond).padStart(4)}`);
}

const text = out.join('\n');
writeFileSync(join(repo, 'build', 'battle-story-trigger-census.txt'), text, 'utf8');
console.log('写到 build/battle-story-trigger-census.txt');
console.log(text.split('\n').slice(0, 16).join('\n'));
