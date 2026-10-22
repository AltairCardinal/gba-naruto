// 字段标签自检：界面上给作者看的名字，必须说清那格是什么。
//
// 用户反馈：**「存在没有关联为用户能看懂的说明的情况，例如角色属性的编辑，
// 有属性A~F，却不说明这些是什么。核对这些属性并改为使用游戏语义的说明，
// 并核查一遍这类情况。」**
//
// 三条断言：
//   1. 每个字段都有说明（desc 不为空）—— 点开也看不懂等于没写；
//   2. 没有「占位名」标签（属性A / 未知00 / 字节00 / frames_ptr 这种）；
//   3. 角色那六项属性与七项成长，用的是游戏里的名字。
//
// 用法：node rom-editor/tools/verify_labels.mjs
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const repoRoot = join(here, '..', '..');
const pack = JSON.parse(readFileSync(join(repoRoot, 'rom-editor', 'content', 'pack.json'), 'utf8'));

let failures = 0;
function check(name, ok, detail = '') {
  if (!ok) failures += 1;
  console.log(`  [${ok ? 'PASS' : 'FAIL'}] ${name}${detail ? ' — ' + detail : ''}`);
}

// 占位名：界面上出现这些词，说明作者还是看不懂那格是什么。
// （「未解字节 +0xNN」「未使用」「填充」「保留」「标志」是**诚实的**说法，不算占位。）
const PLACEHOLDER = [
  /属性\s*[A-F]\b/,
  /^未知[0-9A-F]*$/,
  /^字节[0-9A-F]*$/,
  /^(stat_[a-f]|unknown|raw)\w*$/i,
  /^[a-z]+_ptr$/i,
  /^(tilemap|frames_ptr|animations_ptr|gfx_ptr|palette_ptr)$/i,
  /^指针\d+$/,
  /^[XY]$/,
  /^保留\d+$/,
];

console.log('\n1) 每个字段都有说明');
const noDesc = [];
for (const s of pack.structures) {
  for (const f of s.fields) {
    if (!String(f.desc || '').trim()) noDesc.push(`${s.id}.${f.key}`);
  }
}
check('没有「点开也看不懂」的字段', noDesc.length === 0,
  noDesc.length ? `${noDesc.length} 个：${noDesc.slice(0, 8).join('、')}` : '全部有说明');

console.log('\n2) 没有占位名标签');
const placeholders = [];
for (const s of pack.structures) {
  for (const f of s.fields) {
    const label = String(f.label || '');
    if (PLACEHOLDER.some((re) => re.test(label))) {
      placeholders.push(`${s.id}.${f.key} = ${label}`);
    }
  }
}
check('没有占位名标签', placeholders.length === 0,
  placeholders.length ? `${placeholders.length} 个：${placeholders.slice(0, 8).join('、')}` : '全部是人话');

console.log('\n3) 角色的属性用游戏里的名字');
const template = pack.structures.find((s) => s.id === 'character_template');
const statNames = ['攻击力', '防御力', '敏捷度', '移动力', '忍具数', '查克拉'];
const labels = (template.fields || [])
  .filter((f) => /^stat_[a-f]$/.test(f.key))
  .map((f) => f.label);
check('角色定义表的六项属性有名字', statNames.every((n) => labels.includes(n)),
  labels.join('、'));

const growth = pack.structures.find((s) => s.id === 'per_character_stats');
const growthLabels = (growth.fields || [])
  .filter((f) => /_(gain)$/.test(f.key))
  .map((f) => f.label);
check('逐角色成长表的成长项也跟着改名',
  ['体力每级成长', '攻击力每级成长', '查克拉每级成长'].every((n) => growthLabels.includes(n)),
  growthLabels.join('、'));

console.log('\n4) 属性名标了出处（第三方逆向 ≠ 本仓库指令级证据）');
const statA = (template.fields || []).find((f) => f.key === 'stat_a');
check('属性 A 的说明写了「第三方逆向」与运行时偏移',
  !!statA && String(statA.desc).includes('第三方逆向') && String(statA.desc).includes('+0x02'),
  statA ? String(statA.desc).slice(0, 60) : '没有这个字段');

console.log('\n5) 未解码的字节说得诚实');
const rawLabels = [];
const keepLabels = [];
for (const s of pack.structures) {
  for (const f of s.fields) {
    // 「保留」是第三种说法：**已证明原生代码不读**（读者普查 + 恒为 0），
    // 与「未解」不同 —— 它不需要叫「未解字节」，但必须标成只读。
    if (/^保留/.test(String(f.label || ''))) {
      if (!f.not_read) keepLabels.push(`${s.id}.${f.key} = ${f.label}（没标 not_read）`);
      continue;
    }
    if (f.type !== 'hex') continue;
    if (!/未解|原始字节/.test(String(f.label || ''))) {
      rawLabels.push(`${s.id}.${f.key} = ${f.label}`);
    }
  }
}
check('未解码的字节统一叫「未解字节 +0xNN」', rawLabels.length === 0,
  rawLabels.length ? `${rawLabels.length} 个：${rawLabels.slice(0, 6).join('、')}` : '全部统一');
check('标「保留」的字段都标了 not_read（界面只读）', keepLabels.length === 0,
  keepLabels.length ? `${keepLabels.length} 个：${keepLabels.slice(0, 6).join('、')}` : '全部只读');

console.log('\n6) 记录级标签也说得清');
const hexLabels = [];
for (const t of pack.texts) {
  for (const r of t.records || []) {
    if (/^0x[0-9A-F]{8}$/.test(String(r.label || ''))) {
      hexLabels.push(`${t.id}#${r.id}`);
    }
  }
}
check('没有用裸地址当记录标签', hexLabels.length === 0,
  hexLabels.length ? `${hexLabels.length} 个：${hexLabels.slice(0, 6).join('、')}` : '全部是人话');

const objectives = pack.texts.find((t) => t.id === 'battle_objectives');
const objectiveLabel = (objectives.records || [])[0]?.label || '';
check('战斗目标说明文字的标签写的是「第几关的哪条条件」',
  /第\d+关.*条件/.test(objectiveLabel), objectiveLabel);

const titles = pack.texts.find((t) => t.id === 'mission_titles');
check('任务文本三表的标签各是标题 / 说明 / 提示',
  String(titles.records?.[0]?.label || '').startsWith('标题'),
  `${titles.records?.[0]?.label} / ` +
  `${pack.texts.find((t) => t.id === 'mission_descriptions')?.records?.[0]?.label} / ` +
  `${pack.texts.find((t) => t.id === 'mission_hints')?.records?.[0]?.label}`);

console.log(`\n${failures === 0 ? '全部通过' : failures + ' 项失败'}`);
process.exit(failures === 0 ? 0 : 1);
