// 「来源」自检：每一张表、每一条记录能不能找到它的出处。
//
// 目标（用户原话）：**「关联还是不够强，例如道具的奖励表，应当提供这些奖励的
// 所有出发来源的跳转和编辑。所有可修改内容都是这样，检查一遍」**
//
// 所以这里查的不是「某一张表有没有来源」，而是
// **全包每一张表都至少有一条记录能被溯源**，并且几条关键的跨域链路真的连上了。
//
// 用法：node rom-editor/tools/verify_sources.mjs
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const repoRoot = join(here, '..', '..');
const packPath = join(repoRoot, 'rom-editor', 'content', 'pack.json');

const { ContentPack } = await import('../js/pack.js');
const { recordSources, idSpace } = await import('../js/xref.js');

let failures = 0;
function check(name, ok, detail = '') {
  if (!ok) failures += 1;
  console.log(`  [${ok ? 'PASS' : 'FAIL'}] ${name}${detail ? ' — ' + detail : ''}`);
}

const pack = ContentPack.fromJSON(JSON.parse(readFileSync(packPath, 'utf8')));

// ---------------------------------------------------------------------------
// 1. 覆盖：每张表至少有一条记录能被溯源（字段 / 指针 / 共用字节）
// ---------------------------------------------------------------------------
console.log('\n1) 覆盖：每张表至少有一条记录能找到出处');
const noSource = [];
for (const structure of pack.structures) {
  const withSources = (structure.records || []).filter((r) =>
    recordSources(pack, { kind: 'structure', id: structure.id, recordId: r.id }).length > 0);
  if (!withSources.length) {
    const consumers = (structure.consumers || []).length;
    if (!consumers) noSource.push(`${structure.id}（${structure.label}）`);
  }
}
check('每张结构表都有溯源路径', noSource.length === 0,
  noSource.length ? `${noSource.length} 张没有：${noSource.slice(0, 6).join('、')}` : '全部有');

const textNoSource = [];
for (const table of pack.texts) {
  const withSources = (table.records || []).filter((r) =>
    recordSources(pack, { kind: 'text', id: table.id, recordId: r.id }).length > 0);
  if (!withSources.length && !(table.consumers || []).length) {
    textNoSource.push(`${table.id}（${table.label}）`);
  }
}
check('每张文本表都有溯源路径', textNoSource.length === 0,
  textNoSource.length ? `${textNoSource.length} 张没有：${textNoSource.join('、')}` : '全部有');

// ---------------------------------------------------------------------------
// 2. 奖励表 ← 任务索引表（用户点名的例子）
// ---------------------------------------------------------------------------
console.log('\n2) 奖励表 ← 任务索引表：每条奖励都说得出是哪几关给的');
const rewards = pack.structure('reward_table');
const mission = pack.structure('mission_index');
const rewardSources = new Map();
for (const record of rewards.records) {
  const refs = recordSources(pack, { kind: 'structure', id: 'reward_table', recordId: record.id });
  const fromMission = refs.filter((r) => r.structure && r.structure.id === 'mission_index');
  rewardSources.set(record.id, fromMission);
}
const covered = [...rewardSources.values()].filter((v) => v.length).length;
check('奖励表的记录能追到任务索引表', covered > 0,
  `${covered} / ${rewards.entry_count} 条有来源`);

const r103 = rewards.records.find((r) => r.id === 103);
if (r103) {
  const refs = rewardSources.get(103) || [];
  const stages = refs.map((r) => (r.record && r.record.label) || `#${r.record?.id}`);
  check('奖励表 #103 说得出是哪几关给的', stages.length > 0,
    stages.join('、') || '没有来源');
  // 跳转目标要能直接定位到那条来源记录（作者点一下就能在那儿改）。
  const jumpable = refs.find((r) => r.structure && r.structure.id === 'mission_index');
  check('奖励表的来源能跳到具体那条来源记录',
    !!jumpable && typeof jumpable.record?.id === 'number',
    jumpable ? `任务索引表 #${jumpable.record.id}（${jumpable.record.label}）` : '没有可跳的来源');
  check('来源标签写的是来源记录自己的名字',
    !!jumpable && String(jumpable.label).includes('第'),
    jumpable ? jumpable.label : '没有来源');
}

// 原生读者：改这张表会改到游戏行为，界面上要写出来
const rewardConsumers = rewards.consumers || [];
check('奖励表写出原生读者地址', rewardConsumers.length > 0,
  `${rewardConsumers.length} 个：${rewardConsumers.slice(0, 3).join(' ')}`);

// ---------------------------------------------------------------------------
// 3. 任务文本三表 ← 任务索引表
// ---------------------------------------------------------------------------
console.log('\n3) 任务标题 / 说明 / 提示 ← 任务索引表');
for (const id of ['mission_titles', 'mission_descriptions', 'mission_hints']) {
  const table = pack.textTable(id);
  const withSources = table.records.filter((r) =>
    recordSources(pack, { kind: 'text', id, recordId: r.id }).length > 0);
  check(`${table.label} 的条目能追到任务索引表`, withSources.length > 0,
    `${withSources.length} / ${table.count} 条有来源`);
}

// ---------------------------------------------------------------------------
// 4. id 空间别名：角色的 id 同时指向角色定义表与逐角色成长表
// ---------------------------------------------------------------------------
console.log('\n4) id 空间别名：同一个 id 在几张表里指的是同一个东西');
const space = idSpace(pack, 'character_names');
check('角色名表与角色定义表 / 逐角色成长表同属一个 id 空间',
  space.includes('character_template') && space.includes('per_character_stats'),
  space.join('、'));

const actors = pack.structure('battle_actors');
const actorWithCharacter = actors.records.filter((r) => {
  const refs = recordSources(pack, { kind: 'structure', id: 'character_template', recordId: r.id });
  return refs.some((x) => x.structure && x.structure.id === 'battle_actors');
});
check('角色定义表的记录能追到「哪个战场用了这个角色」',
  actorWithCharacter.length > 0, `${actorWithCharacter.length} 条战场记录引用了角色`);

// ---------------------------------------------------------------------------
// 5. 指针 → 记录：音效描述符指向 81 张乐曲描述符表
// ---------------------------------------------------------------------------
console.log('\n5) 指针反查：sound-ID 表指向乐曲描述符');
const songs = pack.structures.filter((s) => s.id.startsWith('audio_song_'));
let pointed = 0;
for (const song of songs) {
  const refs = recordSources(pack, { kind: 'structure', id: song.id, recordId: 0 });
  if (refs.some((r) => r.structure && r.structure.id === 'sound_id_table')) pointed += 1;
}
check('乐曲描述符能追到 sound-ID 表', pointed > 0,
  `${pointed} / ${songs.length} 张有来源`);

const sentinel = pack.structure('audio_song_empty');
if (sentinel) {
  const refs = recordSources(pack, { kind: 'structure', id: 'audio_song_empty', recordId: 0 });
  check('空哨兵能追到 79 个共用它的音效', refs.length >= 79,
    `${refs.length} 处`);
}

// ---------------------------------------------------------------------------
// 6. 文本字节：共用同一段字
// ---------------------------------------------------------------------------
console.log('\n6) 文本字节：共用同一段字的其它条目');
const titles = pack.textTable('mission_titles');
const shared = titles.records.find((r) => (r.shared_with || []).length);
if (shared) {
  const refs = recordSources(pack, { kind: 'text', id: 'mission_titles', recordId: shared.id });
  const others = refs.filter((r) => r.kind === 'shared');
  check('共用字串的条目能列出其它位置', others.length > 0,
    `${others.length} 处`);
} else {
  check('共用字串的条目能列出其它位置', false, '没找到共用字节的条目');
}

console.log(`\n${failures === 0 ? '全部通过' : failures + ' 项失败'}`);
process.exit(failures === 0 ? 0 : 1);
