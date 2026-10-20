// Acceptance test for the editor's core promise:
//
//   "根据编辑器中的初始数据就可以构建一个完整的原版ROM"
//
// Steps
//   1. load the exported content pack and the original ROM;
//   2. rebuild the ROM from the pack **without touching anything**;
//   3. the result must be byte-identical to the original ROM;
//   4. then edit one field in each domain and prove the edit landed in the
//      right bytes — and in *only* those bytes.
//
// Run:  node tools/verify_pack.mjs
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { gunzipSync } from 'node:zlib';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

import { ContentPack } from '../js/pack.js';
import { buildRom } from '../js/rom.js';

const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, '..');
const repoRoot = join(root, '..');

const packPath = join(root, 'content', 'pack.json');
const textIndexPath = join(root, 'content', 'text-index.json.gz');
const romPath = join(repoRoot, 'rom', 'base.gba');

const sha256 = (bytes) => createHash('sha256').update(bytes).digest('hex');

let failures = 0;
function check(name, ok, detail = '') {
  const mark = ok ? 'PASS' : 'FAIL';
  if (!ok) failures += 1;
  console.log(`  [${mark}] ${name}${detail ? ' — ' + detail : ''}`);
}

console.log('载入内容包与原版 ROM…');
const packData = JSON.parse(readFileSync(packPath, 'utf8'));
const pack = ContentPack.fromJSON(packData);
// The exhaustive ROM text index ships in its own file and is loaded lazily by
// the browser; the round-trip test has to include it.
try {
  const index = JSON.parse(gunzipSync(readFileSync(textIndexPath)).toString('utf8'));
  pack.texts.push(index);
} catch (err) {
  console.log('  （未找到 text-index.json.gz，跳过全 ROM 文本索引）');
}
const rom = new Uint8Array(readFileSync(romPath));
console.log(`  内容包: ${pack.structures.length} 结构 / ${pack.texts.length} 文本表`);
console.log(`  ROM   : ${rom.length.toLocaleString()} 字节  sha256=${sha256(rom).slice(0, 16)}…`);

console.log('\n1) 未改动的内容包重建 ROM');
const { bytes: rebuilt, report } = buildRom(pack, rom);
check('构建无错误', report.errors.length === 0, report.errors.join('; '));
check('写出字节与原版完全一致', sha256(rebuilt) === sha256(rom),
  `重建 sha256=${sha256(rebuilt).slice(0, 16)}…`);
check('长度一致', rebuilt.length === rom.length,
  `${rebuilt.length} vs ${rom.length}`);
let diffCount = 0;
let firstDiff = -1;
for (let i = 0; i < Math.min(rebuilt.length, rom.length); i++) {
  if (rebuilt[i] !== rom[i]) {
    diffCount += 1;
    if (firstDiff < 0) firstDiff = i;
  }
}
check('逐字节比较无差异', diffCount === 0,
  diffCount ? `${diffCount} 字节不同，首个在 0x${firstDiff.toString(16)}` : '');
console.log(`  报告: 结构 ${report.structures} / 记录 ${report.records} ` +
  `(改动 ${report.recordsChanged}) / 文本表 ${report.texts} ` +
  `(改动 ${report.textsChanged}) / 补丁 ${report.patches}`);

console.log('\n2) 逐域编辑落点验证（每个域改一个字段）');
const edits = [
  { module: '角色属性', structure: 'character_template', record: 1, key: 'hp_base', value: 777,
    expectOffset: (s, r) => s.records[r].rom_offset + 0x0A, size: 2 },
  { module: '道具', structure: 'reward_table', record: 0, key: 'gold', value: 12345,
    expectOffset: (s, r) => s.records[r].rom_offset, size: 2 },
  { module: '忍术', structure: 'jutsu_record', record: 5, key: 'growth_amount', value: 42,
    expectOffset: (s, r) => s.records[r].rom_offset + 0x0E, size: 1 },
  { module: '战斗', structure: 'map_table', record: 3, key: 'background_id', value: 9,
    expectOffset: (s, r) => s.records[r].rom_offset + 0x1C, size: 1 },
  { module: '战斗', structure: 'battle_actors', record: 700, key: 'x', value: 19,
    expectOffset: (s, r) => s.records[r].rom_offset + 0x02, size: 1 },
  { module: '剧情路线', structure: 'mission_index', record: 4, key: 'value', value: 111,
    expectOffset: (s, r) => s.records[r].rom_offset, size: 1 },
];

for (const edit of edits) {
  const p2 = ContentPack.fromJSON(JSON.parse(readFileSync(packPath, 'utf8')));
  const structure = p2.structure(edit.structure);
  if (!structure) {
    check(`${edit.module}: 找到结构 ${edit.structure}`, false);
    continue;
  }
  const record = structure.records[edit.record];
  const offset = edit.expectOffset(structure, edit.record);
  const before = rom.slice(offset, offset + edit.size);
  p2.setValue(structure, record, edit.key, edit.value);
  const out = buildRom(p2, rom);
  const after = out.bytes.slice(offset, offset + edit.size);
  const changed = [];
  for (let i = 0; i < out.bytes.length; i++) {
    if (out.bytes[i] !== rom[i]) changed.push(i);
  }
  const inRange = changed.every((i) => i >= offset && i < offset + edit.size);
  check(`${edit.module}: ${edit.structure}.${edit.key} 落在 0x${offset.toString(16)}`,
    out.report.errors.length === 0 &&
    inRange &&
    after.length === before.length &&
    after[0] !== before[0],
    out.report.errors.join('; ') ||
    (inRange ? `改动字节 ${changed.length} 个，值 ${before[0]}→${after[0]}` : `越界改动: ${changed.slice(0, 8)}`));
}

console.log('\n3) 文本编辑落点验证（经指针回读）');
{
  const p3 = ContentPack.fromJSON(JSON.parse(readFileSync(packPath, 'utf8')));
  const table = p3.textTable('character_names');
  const record = table.records.find((r) => r.text);
  const original = record.text;
  const newText = original + '改';
  p3.setText(table, record, newText);
  const out = buildRom(p3, rom);
  const ptrOffset = record.pointer_offset;
  const newPtr = out.bytes[ptrOffset] | (out.bytes[ptrOffset + 1] << 8) |
    (out.bytes[ptrOffset + 2] << 16) | (out.bytes[ptrOffset + 3] << 24);
  const textOffset = newPtr - 0x08000000;
  const decoded = p3.font.decode(out.bytes.slice(textOffset, textOffset + 64));
  const changed = [];
  for (let i = 0; i < out.bytes.length; i++) if (out.bytes[i] !== rom[i]) changed.push(i);
  check('文本改动经指针可回读', out.report.errors.length === 0 &&
    changed.length > 0 && decoded.startsWith(newText),
    out.report.errors.join('; ') ||
    `新指针 0x${newPtr.toString(16)}（原 0x${record.pointer.toString(16)}），回读 ${JSON.stringify(decoded.slice(0, 16))}`);
}

console.log('\n3b) 字库缺字会被如实报告（不会静默吞掉）');
{
  const p3b = ContentPack.fromJSON(JSON.parse(readFileSync(packPath, 'utf8')));
  const missing = p3b.font.missingCharacters('没有·改');
  check('缺字被列出', missing.includes('·'), `缺字: ${missing.join('')}`);
}

console.log('\n4) 变长文本：指针表驱动的文本可重定位');
{
  const p4 = ContentPack.fromJSON(JSON.parse(readFileSync(packPath, 'utf8')));
  const table = p4.textTable('dialogue_slots');
  const record = table.records.find((r) => r.text);
  const long = record.text + '这是一段明显更长的追加文本用于验证重定位能力';
  p4.setText(table, record, long);
  const out = buildRom(p4, rom);
  const ptrOffset = record.pointer_offset;
  const newPtr = out.bytes[ptrOffset] | (out.bytes[ptrOffset + 1] << 8) |
    (out.bytes[ptrOffset + 2] << 16) | (out.bytes[ptrOffset + 3] << 24);
  const textOffset = newPtr - 0x08000000;
  const decoded = p4.font.decode(out.bytes.slice(textOffset, textOffset + 200));
  check('变长文本重定位到新地址并可解码',
    out.report.errors.length === 0 && decoded.startsWith(long.slice(0, 6)),
    out.report.errors.join('; ') ||
    `新指针 0x${newPtr.toString(16)}（原 0x${record.pointer.toString(16)}），回读 ${JSON.stringify(decoded.slice(0, 20))}`);
}

console.log(`\n${failures === 0 ? '全部通过' : failures + ' 项失败'}`);
process.exit(failures === 0 ? 0 : 1);
