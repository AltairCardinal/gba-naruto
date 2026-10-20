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
import { scanTokens } from '../js/textcodec.js';
import { base64ToBytes } from '../js/bytes.js';

/** How many control codes (0x01 / 0x02) a byte run carries. */
function countCtrl(bytes) {
  let n = 0;
  for (const token of scanTokens(bytes)) if (token.k === 'c') n += 1;
  return n;
}

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

console.log('\n5) 原始字节补丁：任意字节都能改');
{
  // 5a. 一个单字节补丁落点正确
  const p5 = ContentPack.fromJSON(JSON.parse(readFileSync(packPath, 'utf8')));
  const offset = 0x00076d;            // 标题画面文本区
  const before = rom[offset];
  const value = (before ^ 0xff) & 0xff;
  p5.patches.push({
    id: 'raw.test',
    offset,
    before_hex: before.toString(16).padStart(2, '0'),
    after_hex: value.toString(16).padStart(2, '0'),
  });
  const out5 = buildRom(p5, rom);
  const changed = [];
  for (let i = 0; i < out5.bytes.length; i++) if (out5.bytes[i] !== rom[i]) changed.push(i);
  check('单字节补丁落在指定地址',
    out5.report.errors.length === 0 && changed.length === 1 && changed[0] === offset &&
    out5.bytes[offset] === value,
    out5.report.errors.join('; ') || `改动 ${changed.length} 字节 @0x${offset.toString(16)}`);

  // 5b. 原字节不匹配时必须跳过并报告，而不是改坏别处
  const p6 = ContentPack.fromJSON(JSON.parse(readFileSync(packPath, 'utf8')));
  p6.patches.push({
    id: 'raw.stale',
    offset: 0x00076d,
    before_hex: '00',               // 与真实原字节不符
    after_hex: 'aa',
  });
  const out6 = buildRom(p6, rom);
  check('原字节不匹配的补丁被跳过并报告',
    out6.report.warnings.length > 0 && out6.report.warnings.some((w) => w.includes('raw.stale')) &&
    out6.bytes[0x00076d] === rom[0x00076d],
    out6.report.warnings.join('; ') || '没有产生警告');

  // 5c. 多个补丁同时生效
  const p7 = ContentPack.fromJSON(JSON.parse(readFileSync(packPath, 'utf8')));
  const spots = [0x00076d, 0x00076e, 0x5461c4];
  for (const at of spots) {
    p7.patches.push({
      id: `raw.${at.toString(16)}`,
      offset: at,
      before_hex: rom[at].toString(16).padStart(2, '0'),
      after_hex: ((rom[at] ^ 0x5a) & 0xff).toString(16).padStart(2, '0'),
    });
  }
  const out7 = buildRom(p7, rom);
  const changed7 = [];
  for (let i = 0; i < out7.bytes.length; i++) if (out7.bytes[i] !== rom[i]) changed7.push(i);
  check('多个补丁同时生效且互不干扰',
    changed7.length === spots.length && spots.every((at) => changed7.includes(at)),
    `改动 ${changed7.length} 字节`);
}

console.log('\n6) 剧情 VM：脚本里的「下一场景」与定宽操作数');
{
  const p8 = ContentPack.fromJSON(JSON.parse(readFileSync(packPath, 'utf8')));
  const scripts = p8.scripts || [];
  check('内容包带剧情脚本的路线边', scripts.length > 0 &&
    scripts.some((s) => s.route && s.route.length),
    `${scripts.length} 个剧本`);

  const withRoute = scripts.find((s) => s.route && s.route.length);
  const operand = withRoute && withRoute.operands.find((o) => o.name === 'scene');
  check('找到可改的「下一场景」操作数', !!operand,
    operand ? `0x${operand.rom_offset.toString(16)}（原值 ${operand.value}）` : '没有');

  if (operand) {
    const wanted = (operand.value + 1) & 0xff;
    // 走和界面一样的路径：写进包的显式补丁
    p8.patches.push({
      id: 'story.operand',
      offset: operand.rom_offset,
      before_hex: operand.before_hex,
      after_hex: wanted.toString(16).padStart(2, '0'),
    });
    const out8 = buildRom(p8, rom);
    const changed8 = [];
    for (let i = 0; i < out8.bytes.length; i++) if (out8.bytes[i] !== rom[i]) changed8.push(i);
    check('「下一场景」改写落在脚本字节上',
      out8.report.errors.length === 0 && changed8.length === 1 &&
      changed8[0] === operand.rom_offset && out8.bytes[operand.rom_offset] === wanted,
      out8.report.errors.join('; ') ||
      `改动 @0x${operand.rom_offset.toString(16)}（期望 0x${wanted.toString(16)}）`);
  }
}

console.log('\n7) 控制码：改写文本不得破坏排版');
{
  const p9 = ContentPack.fromJSON(JSON.parse(readFileSync(packPath, 'utf8')));
  const table = p9.textTable('mission_descriptions');
  // 找一条带控制码的记录
  const target = table.records.find((r) => {
    const bytes = base64ToBytes(r.raw || '');
    return countCtrl(bytes) > 0;
  });
  check('找到带控制码的记录', !!target,
    target ? `${target.id}（${target.text.length} 字，${countCtrl(base64ToBytes(target.raw))} 个控制码）` : '没有');

  if (target) {
    const before = base64ToBytes(target.raw);
    const beforeCtrl = countCtrl(before);
    const newText = target.text + '改';
    p9.setText(table, target, newText);
    const out9 = buildRom(p9, rom);
    check('构建无错误', out9.report.errors.length === 0, out9.report.errors.join('; '));

    // 控制码必须还在，而且位置不变
    const movedNow = out9.report.movedTexts.find((m) => m.table === table.id && m.id === target.id);
    const home = movedNow ? movedNow.to : target.text_offset;
    const newLen = p9.textBytes(target).length;
    const after = out9.bytes.slice(home, home + newLen);
    const afterCtrl = countCtrl(after);
    check('编辑后控制码一个不少', afterCtrl === beforeCtrl,
      `${beforeCtrl} → ${afterCtrl}${movedNow ? `（记录搬到 0x${movedNow.to.toString(16)}）` : ''}`);

    // 别的记录不能被牵连
    const changed = [];
    for (let i = 0; i < out9.bytes.length; i++) if (out9.bytes[i] !== rom[i]) changed.push(i);
    const tableStart = Math.min(...table.records.map((r) => r.text_offset).filter((v) => v !== null));
    const tableEnd = Math.max(...table.records.map((r) => r.text_offset + (r.raw ? base64ToBytes(r.raw).length : 0)));
    const pointerSlots = table.records
      .map((r) => r.pointer_offset)
      .filter((v) => v !== null && v !== undefined);
    const pointerStart = Math.min(...pointerSlots);
    const pointerEnd = Math.max(...pointerSlots) + 4;
    // 变长的那条记录被搬到空闲区，它的新副本也算「表外改动」
    const newHome = home;
    const newHomeEnd = newHome + newLen + 1;   // +1 = NUL 结束符
    const outside = changed.filter((i) => i < tableStart || i >= tableEnd);
    const onlyExpected = outside.every(
      (i) => (i >= pointerStart && i < pointerEnd) || (i >= newHome && i < newHomeEnd));
    const others = table.records.filter((r) => r.id !== target.id);
    let othersChanged = 0;
    for (const r of others) {
      const original = base64ToBytes(r.raw || '');
      const now = out9.bytes.slice(r.text_offset, r.text_offset + original.length);
      if (now.some((b, i) => b !== original[i])) othersChanged += 1;
    }
    check('同表其它记录逐字节未变', othersChanged === 0,
      `${othersChanged} 条被牵连`);
    check('表外只改了指针与搬走那条记录的新副本', onlyExpected,
      onlyExpected
        ? `共改 ${changed.length} 字节（表内 ${changed.length - outside.length}，表外 ${outside.length}）`
        : `表外改了 ${outside.length} 字节 @ ${outside.map((i) => '0x' + i.toString(16)).join(',')}` +
          `；指针表 0x${pointerStart.toString(16)}–0x${pointerEnd.toString(16)}，` +
          `新副本 0x${newHome.toString(16)}–0x${newHomeEnd.toString(16)}`);

    // 导出 → 导入 后，改动必须还在（内容包是编辑器的存档格式）
    const reloaded = ContentPack.fromJSON(JSON.parse(JSON.stringify(p9.toJSON())));
    const out9b = buildRom(reloaded, rom);
    let same = out9b.bytes.length === out9.bytes.length;
    if (same) {
      for (let i = 0; i < out9.bytes.length; i++) {
        if (out9b.bytes[i] !== out9.bytes[i]) { same = false; break; }
      }
    }
    check('导出内容包再导入，构建结果不变', same && out9b.report.errors.length === 0,
      out9b.report.errors.join('; ') || '一致');
  }
}

console.log(`\n${failures === 0 ? '全部通过' : failures + ' 项失败'}`);
process.exit(failures === 0 ? 0 : 1);
