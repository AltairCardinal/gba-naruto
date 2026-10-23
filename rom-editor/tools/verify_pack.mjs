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

import { ContentPack, textSlotKind } from '../js/pack.js';
import { buildRom, RomBuilder } from '../js/rom.js';
import { scanTokens, encodeTokens } from '../js/textcodec.js';
import { base64ToBytes, hexToBytes } from '../js/bytes.js';

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

/**
 * `buildRom` 在构建有 error 时会**抛异常**（`rom.js` 的 `BuildError`）。
 * 门禁要**干净地红**，不能崩在半路 —— 这里把异常变成一条普通的失败。
 */
function safeBuild(pack, baseBytes) {
  try {
    const out = buildRom(pack, baseBytes);
    return { ok: true, bytes: out.bytes, report: out.report };
  } catch (err) {
    return { ok: false, bytes: null, report: { errors: [String((err && err.message) || err)] } };
  }
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
  const table = p4.textTable('quiz_questions');
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

console.log('\n8) 战斗目标说明文字：指针能解析成原文，且能就地改写');
{
  const p10 = ContentPack.fromJSON(JSON.parse(readFileSync(packPath, 'utf8')));
  const objectives = p10.textTable('battle_objectives');
  check('内容包带战斗目标说明文字表', !!objectives,
    objectives ? `${objectives.count} 条` : '没有这张表');

  let index = null;
  try {
    index = JSON.parse(gunzipSync(readFileSync(textIndexPath)).toString('utf8'));
    p10.texts.push(index);
  } catch (err) {
    index = null;
  }

  if (!objectives || !index) {
    check('全 ROM 文本索引可用', false, 'text-index.json.gz 缺失');
  } else {
    const byOffset = new Map();
    for (const record of index.records) {
      if (record.text_offset !== null && record.text_offset !== undefined) {
        byOffset.set(record.text_offset, record);
      }
    }

    // 8a. 战斗目标表里每条说明文字的指针都必须指向一条已知文本
    const rules = p10.structure('battle_rules');
    const pointers = [];
    for (const record of rules.records) {
      for (let g = 0; g < 2; g++) {
        for (let k = 0; k < 4; k++) {
          const ptr = record.values[`g${g}_${k}_text_ptr`];
          if (ptr) pointers.push({ ptr, offset: ptr - 0x08000000 });
        }
      }
    }
    const byPointer = new Map();
    for (const record of objectives.records) byPointer.set(record.pointer, record);
    const resolved = pointers.filter((p) => byPointer.has(p.ptr));
    check('战斗目标的说明文字指针全部解析得到原文',
      pointers.length > 0 && resolved.length === pointers.length,
      `${resolved.length}/${pointers.length} 条解析成功`);

    // 8b. 每条说明文字都不能同时出现在全 ROM 文本索引里（一个字节一个归属）
    const overlap = objectives.records.filter((r) => byOffset.has(r.text_offset));
    check('说明文字不在全 ROM 文本索引里重复出现', overlap.length === 0,
      overlap.length ? `${overlap.length} 条重复` : `${objectives.count} 条均唯一`);

    // 8c. 全 ROM 文本索引里的每条文本都必须能 token→字节 逐字节还原
    let broken = 0;
    let firstBroken = null;
    for (const record of index.records) {
      const raw = base64ToBytes(record.raw || '');
      const back = encodeTokens(scanTokens(raw));
      if (back.length !== raw.length || back.some((b, i) => b !== raw[i])) {
        broken += 1;
        if (!firstBroken) firstBroken = record;
      }
    }
    check('全 ROM 文本索引逐字节可还原', broken === 0,
      broken ? `${broken} 条还原失败，第一条 0x${firstBroken.text_offset.toString(16)}` :
        `${index.records.length} 条全部一致`);

    // 8d. 改一条战斗目标说明文字，只允许动那一条
    let target = null;
    for (const candidate of objectives.records) {
      const chars = [...(candidate.text || '')];
      const at = chars.findIndex((ch) => ch !== '打');
      if (at < 0) continue;
      const changedText = chars.map((ch, i) => (i === at ? '打' : ch)).join('');
      if (p10.font.encodedLength(changedText) !== p10.font.encodedLength(candidate.text || '')) continue;
      target = candidate;
      break;
    }
    if (target) {
      const original = target.text;
      const chars = [...original];
      const at = chars.findIndex((ch) => ch !== '打');
      const replacement = chars.map((ch, i) => (i === at ? '打' : ch)).join('');
      const sameLength = p10.font.encodedLength(replacement) === p10.font.encodedLength(original);
      p10.setText(objectives, target, replacement);
      const out10 = buildRom(p10, rom);
      const changed = [];
      for (let i = 0; i < out10.bytes.length; i++) if (out10.bytes[i] !== rom[i]) changed.push(i);
      const start = target.text_offset;
      const end = start + base64ToBytes(target.raw || '').length;
      const onlyThis = changed.every((i) => i >= start && i < end);
      check('改写战斗目标说明文字只动那一条',
        out10.report.errors.length === 0 && sameLength && changed.length > 0 && onlyThis,
        out10.report.errors.join('; ') ||
        `${JSON.stringify(original)} → ${JSON.stringify(replacement)}，` +
        `改动 ${changed.length} 字节 @0x${start.toString(16)}–0x${end.toString(16)}`);
    } else {
      check('改写战斗目标说明文字只动那一条', false, '没有可改的说明文字');
    }
  }
}

console.log('\n9) 文本表的数据完整性：容量判定 / 共用字节 / 跨表归属 / 字节级恢复');
{
  const p11 = ContentPack.fromJSON(JSON.parse(readFileSync(packPath, 'utf8')));
  let index11 = null;
  try {
    index11 = JSON.parse(gunzipSync(readFileSync(textIndexPath)).toString('utf8'));
    p11.texts.push(index11);
  } catch (err) { index11 = null; }

  // 9a. 改一条说话人名 ⇒ 整张表**转换**成「指针表 + 变长串池」。
  //     「只动那一处」是**定长内联槽**时代的世界；现在「一处」是
  //     **一整张表的转换 footprint**，断言也跟着改成 footprint：
  //       · 构建无错误（容量判定要用**内容长度**：拿补齐后的长度比槽位
  //         会把「4 字节的字 + 12 字节的槽」误判成超长）；
  //       · 指针表写在**原表的位置**上，64 个槽都是 ROM 内的合法指针；
  //       · 64 条名字都搬到了**原表范围之外**（串池），逐字节等于新文本；
  //       · 保护区（说话人全名表）一个字节都没动；
  //       · 14 处「取名读者」的代码补丁逐字节落地；
  //       · **除这些之外没有任何字节被改动**。
  {
    const table = p11.textTable('speaker_names');
    const record = table.records.find((r) => r.id === 1);
    p11.setText(table, record, `${record.text}测试`);
    const out = safeBuild(p11, rom);
    const buildOk = out.ok && out.report.errors.length === 0;
    // 构建失败时用原 ROM 占位 —— 每条断言都带 buildOk 门槛，不会误判成通过
    const bytes = out.bytes || rom;

    const conversion = (p11.conversions || {})[table.convert] || {};
    const base = conversion.base;                 // 0x5A57C4：原表的位置
    const pointerEnd = base + 64 * 4;             // 0x5A58C4
    const fullnameBase = base + 63 * 12;          // 0x5A5AB8：说话人全名表第 0 条（保护区）
    const ROM_BASE = 0x08000000;
    const moved = (out.report.movedTexts || []).filter((m) => m.table === table.id);
    const changed = [];
    for (let i = 0; i < rom.length; i++) if (bytes[i] !== rom[i]) changed.push(i);

    check('改说话人名能构建（转换不报错）',
      buildOk && (out.report.conversions || []).some((c) => c.table === table.id),
      out.report.errors.join('; ') ||
      `转换 ${(out.report.conversions || []).length} 次，共改 ${changed.length} 字节`);

    // 指针表：写在原表的位置上，64 个槽都是 ROM 内的合法指针，
    // 而且指针表本身**没有超出原表的范围**（不能碰到保护区）。
    const pointers = [];
    for (let id = 0; id < 64; id++) {
      const at = base + id * 4;
      pointers.push((bytes[at] | (bytes[at + 1] << 8) |
        (bytes[at + 2] << 16) | (bytes[at + 3] << 24)) >>> 0);
    }
    check('指针表写在原表位置，64 个槽都是合法指针',
      buildOk &&
      pointers.every((v) => v >= ROM_BASE && v < ROM_BASE + rom.length) &&
      pointerEnd <= fullnameBase,
      `指针表 0x${base.toString(16)}–0x${pointerEnd.toString(16)}，` +
      `保护区起点 0x${fullnameBase.toString(16)}`);

    // 64 条名字：正文都搬到了原表范围之外（串池），逐字节等于新文本，后面跟一个 NUL。
    let namesOk = moved.length === 64;
    let namesDetail = `${moved.length} 条进了串池`;
    for (const r of table.records) {
      const m = moved.find((x) => x.id === r.id);
      if (!m) { namesOk = false; namesDetail = `id ${r.id} 没有进串池`; break; }
      const at = m.to;
      const expected = p11.textContentBytes(r);
      const written = bytes.subarray(at, at + expected.length);
      if (written.length !== expected.length ||
          !written.every((b, i) => b === expected[i])) {
        namesOk = false; namesDetail = `id ${r.id} @0x${at.toString(16)} 内容不符`; break;
      }
      if (bytes[at + expected.length] !== 0) {
        namesOk = false; namesDetail = `id ${r.id} @0x${at.toString(16)} 后面缺 NUL`; break;
      }
      if (at >= base && at < fullnameBase) {
        namesOk = false; namesDetail = `id ${r.id} 还留在原表里（0x${at.toString(16)}）`; break;
      }
    }
    check('64 条名字都搬到了原表范围之外，内容逐字节等于新文本', buildOk && namesOk, namesDetail);

    // 指针表必须**指着**串池里的那一条名字（光「是合法指针」不够 ——
    // 指针指回旧内联槽的话，游戏读到的还是原地那份，转换等于没做）。
    let bound = true;
    let boundDetail = `${moved.length} 条都对上了`;
    for (const m of moved) {
      const target = pointers[m.id] - ROM_BASE;
      if (target !== m.to) {
        bound = false;
        boundDetail = `id ${m.id} 的指针指向 0x${target.toString(16)}，名字却在 0x${m.to.toString(16)}`;
        break;
      }
    }
    check('指针表指着串池里的那一条名字', buildOk && bound && moved.length === 64, boundDetail);

    // 保护区：说话人全名表（0x085A5AB8 起 512 字节）一个字节都没动。
    const protectSize = 0x200;
    let protectSame = true;
    for (let i = 0; i < protectSize; i++) {
      if (rom[fullnameBase + i] !== bytes[fullnameBase + i]) { protectSame = false; break; }
    }
    check('保护区（说话人全名表）逐字节未动', buildOk && protectSame,
      `0x${fullnameBase.toString(16)} 起 ${protectSize} 字节`);

    // 14 处「取名读者」的代码补丁逐字节落地（不落地的话游戏读的还是旧内联槽）。
    const codePatches = conversion.code_patches || [];
    const badPatches = [];
    for (const cp of codePatches) {
      const after = hexToBytes(cp.after_hex || '');
      const actual = bytes.subarray(cp.offset, cp.offset + after.length);
      if (actual.length !== after.length || !actual.every((b, i) => b === after[i])) {
        badPatches.push(cp.label || `0x${cp.offset.toString(16)}`);
      }
    }
    check(`${codePatches.length} 处取名读者的代码补丁逐字节落地`,
      buildOk && codePatches.length > 0 && badPatches.length === 0, badPatches.join('、'));

    // 除「指针表 + 串池 + 读者补丁」这个 footprint 之外，**没有任何字节被改动**。
    const allowed = [];
    allowed.push([base, pointerEnd]);
    for (const m of moved) allowed.push([m.to, m.to + m.bytes + 1]);
    for (const cp of codePatches) {
      allowed.push([cp.offset, cp.offset + (cp.before_hex || '').length / 2]);
    }
    const unexpected = changed.filter((i) => !allowed.some(([s, e]) => i >= s && i < e));
    check('除转换 footprint 外没有别的改动', buildOk && unexpected.length === 0,
      unexpected.length
        ? `${unexpected.length} 个意外字节 @ ${unexpected.slice(0, 8).map((i) => '0x' + i.toString(16)).join(',')}`
        : `共改 ${changed.length} 字节：指针表 ${pointerEnd - base} + 串池 ${moved.length} 条 + 读者补丁 ${codePatches.length} 处`);

    p11.resetText(table, record);
  }

  // 9b. 同表内共用同一段字节的记录：改一处必须一起改，
  //     否则构建时后写的覆盖先写的、改动凭空消失
  {
    const table = p11.textTable('mission_titles');
    const shared = table.records.find((r) => (r.shared_with || []).length > 0);
    if (!shared) {
      check('存在共用同一段字节的记录', false, '没有找到');
    } else {
      const expected = p11.font.encode('甲');
      p11.setText(table, shared, '甲');
      const updated = table.records.filter(
        (r) => (r.shared_with || []).length > 0 && r.text === '甲').length;
      const out = buildRom(p11, rom);
      const at = shared.text_offset;
      const written = out.bytes.slice(at, at + expected.length);
      check('共用同一段字节的记录一起改',
        updated === 1 + shared.shared_with.length && out.report.errors.length === 0 &&
        written.length === expected.length && written.every((b, i) => b === expected[i]),
        `${shared.shared_with.length + 1} 处一起改，写回 ${written.length} 字节`);
      p11.resetText(table, shared);
    }
  }

  // 9c. 跨表重复：具名表改的字不能被「全 ROM 文本索引」覆盖
  {
    if (!index11) {
      check('跨表重复不互相覆盖', false, '没有文本索引');
    } else {
      const names = p11.textTable('character_names');
      const record = names.records.find((r) => r.text && r.text.includes('鸣人'));
      // 等长替换：变长的话这条可重定位的文本会搬到空闲区，指针也跟着改，
      // 读旧地址自然还是旧字 —— 那样测的就不是「有没有被覆盖」了。
      const replaced = record.text.replace('鸣', '人');
      p11.setText(names, record, replaced);
      const out = buildRom(p11, rom);
      const at = record.text_offset;
      const decoded = p11.font.decode(out.bytes.slice(at, at + 16));
      check('具名表的改动不被文本索引覆盖',
        out.report.errors.length === 0 && decoded.startsWith(replaced),
        `回读 ${JSON.stringify(decoded.slice(0, 8))}`);
      p11.resetText(names, record);
    }
  }

  // 9d. 「恢复原文」必须字节级还原（控制码不能跑到句中）
  {
    const table = p11.textTable('mission_descriptions');
    const record = table.records.find((r) => r.text && r.raw && r.raw.includes('AQ'));
    if (!record) {
      check('恢复原文是字节级', false, '没有找到带控制码的记录');
    } else {
      const original = record.raw;
      p11.setText(table, record, record.text + '改');
      p11.resetText(table, record);
      const now = Buffer.from(p11.textBytes(record)).toString('base64');
      check('恢复原文是字节级还原', now === original,
        now === original ? '逐字节一致' : `还原后与原文不同`);
    }
  }
}

console.log('\n10) 原始字节补丁：能落在结构表里生效，被结构化改过才跳过');
{
  const p12 = ContentPack.fromJSON(JSON.parse(readFileSync(packPath, 'utf8')));
  // 补丁落在 battle_actors 第 0 条记录内（0x5461C8 起）
  const actors = p12.structure('battle_actors');
  const first = actors.records.find((r) => r.rom_offset === 0x5461c8);
  const at = first.rom_offset + 0x02;          // 记录里的 x 字段
  const original = rom[at];
  p12.patches.push({
    id: 'raw.test',
    offset: at,
    before_hex: original.toString(16).padStart(2, '0'),
    after_hex: 'ff',
  });
  const out = buildRom(p12, rom);
  check('落在结构表记录里的补丁能真正进 ROM',
    out.report.errors.length === 0 && out.bytes[at] === 0xff,
    out.report.errors.join('; ') ||
    `@0x${at.toString(16)} = 0x${out.bytes[at].toString(16)}（原 0x${original.toString(16)}）`);

  // 同一地址如果被结构化编辑器改过，补丁必须被跳过并**报告**
  const p13 = ContentPack.fromJSON(JSON.parse(readFileSync(packPath, 'utf8')));
  const actors2 = p13.structure('battle_actors');
  const first2 = actors2.records.find((r) => r.rom_offset === 0x5461c8);
  p13.setValue(actors2, first2, 'x', 7);
  p13.patches.push({
    id: 'raw.conflict',
    offset: first2.rom_offset + 0x02,
    before_hex: rom[first2.rom_offset + 0x02].toString(16).padStart(2, '0'),
    after_hex: 'ff',
  });
  const out2 = buildRom(p13, rom);
  check('与结构化改动冲突的补丁被跳过并报告',
    out2.report.warnings.some((w) => w.includes('raw.conflict')),
    out2.report.warnings.join('; ') || '没有警告');
  check('结构化改动本身仍然生效',
    out2.bytes[first2.rom_offset + 0x02] === 7,
    `x = ${out2.bytes[first2.rom_offset + 0x02]}`);
}

console.log('\n11) 定长内联槽：两张新表进包后的写回规则（整槽原样 / 放不下就拒 / 别名不抢字节）');
{
  // 「定长内联槽」这条形态的分支在产品里**从来没被真实表格走到过**
  // （2026-10-23 之前 11 张文本表里没有一张是 `fixed`）。
  // 说话人全名表（19 字节/条）与地点名表（18 字节/条）进包之后，
  // 这条分支第一次被**真实数据**覆盖 —— 而且这三张表之间还有
  // **地址别名**（三处「没有」共用同一批字节），所以这一节验的是：
  //   11a 两张表在包里，形态 / 步长 / 条数对得上；
  //   11b 地址别名已**如实建模**（不是假装它们互不相干）；
  //   11c 写回是「**整槽原样**」：不是我们的字节（填充、别的表的内容）一个都不动；
  //   11d 放不下的改动必须**被拒**（不能悄悄截断、也不能写坏别处）；
  //   11e 两处别名改成**不同的**字必须**报错**（不能悄悄丢一处）；
  //   11f 变异对照：把写回改回「清零尾巴」的旧行为，11c 必须能发现。
  const p13 = ContentPack.fromJSON(JSON.parse(readFileSync(packPath, 'utf8')));
  const full = p13.textTable('speaker_full_names');
  const loc = p13.textTable('location_names');

  // 11a. 两张表在包里，形态对得上
  check('说话人全名表在包里（64 条 × 19 字节定长内联槽）',
    !!full && full.records.length === 64 &&
    full.records.every((r) => r.capacity === 19 && r.pointer_offset === null) &&
    textSlotKind(full, full.records[0]) === 'fixed',
    full ? `${full.records.length} 条，capacity=${full.records[0].capacity}` : '没有这张表');
  check('地点名表在包里（55 条 × 18 字节定长内联槽）',
    !!loc && loc.records.length === 55 &&
    loc.records.every((r) => r.capacity === 18 && r.pointer_offset === null) &&
    textSlotKind(loc, loc.records[0]) === 'fixed',
    loc ? `${loc.records.length} 条，capacity=${loc.records[0].capacity}` : '没有这张表');

  // 11b. 地址别名如实建模
  const aliasPairs = [
    ['speaker_names', 63, 'speaker_full_names', 0],
    ['speaker_full_names', 63, 'location_names', 0],
  ];
  let aliasOk = true;
  let aliasDetail = '';
  for (const [ta, ia, tb, ib] of aliasPairs) {
    const a = p13.textTable(ta).records.find((r) => r.id === ia);
    const b = p13.textTable(tb).records.find((r) => r.id === ib);
    const want = `${tb}#${ib}`;
    if (!a || !b || a.text_offset !== b.text_offset ||
        !(a.aliased_with || []).includes(want) || !(b.aliased_with || []).includes(`${ta}#${ia}`)) {
      aliasOk = false;
      aliasDetail = `${ta}#${ia} ↔ ${tb}#${ib}`;
      break;
    }
  }
  check('三处「没有」的地址别名已如实建模（aliased_with）', aliasOk,
    aliasOk ? '简称表#63 ≡ 全名表#0，全名表#63 ≡ 地点名表#0' : aliasDetail);

  // 11c. 全名表 id 63 的槽（19 字节）最后一个字节是地点名表 id 1 的第一个字形码
  const f63 = full.records.find((r) => r.id === 63);
  const l1 = loc.records.find((r) => r.id === 1);
  const foreignAt = f63.text_offset + 18;          // 0x5A5F77
  check('全名表 id 63 的第 19 字节是地点名表 id 1 的第一个字形码',
    foreignAt === l1.text_offset && rom[foreignAt] === 0x8a && f63.writable_bytes === 18,
    `0x${foreignAt.toString(16)} = 0x${rom[foreignAt].toString(16)}，可写长度 ${f63.writable_bytes}/19`);

  // 11d. 写回是「整槽原样」：改一个字，别人的字节一个都不动
  const p14 = ContentPack.fromJSON(JSON.parse(readFileSync(packPath, 'utf8')));
  const f63b = p14.textTable('speaker_full_names').records.find((r) => r.id === 63);
  p14.setText(p14.textTable('speaker_full_names'), f63b, '鸣人');
  const out14 = safeBuild(p14, rom);
  const bytes14 = out14.bytes || rom;
  let tailSame = true;
  for (let i = 5; i < 19; i++) {                   // 正文 + NUL 之后是槽的填充
    if (bytes14[f63b.text_offset + i] !== rom[f63b.text_offset + i]) { tailSame = false; break; }
  }
  const loc1After = p14.font.decode(bytes14.slice(l1.text_offset, l1.text_offset + 16));
  check('定长槽写回是「整槽原样」（填充与别人的字节一个都没动）',
    out14.ok && out14.report.errors.length === 0 && tailSame && bytes14[foreignAt] === 0x8a,
    out14.report.errors.join('; ') ||
    `0x${foreignAt.toString(16)} = 0x${bytes14[foreignAt].toString(16)}（原 0x${rom[foreignAt].toString(16)}）`);
  check('地点名表 id 1 仍读得出「村边的森林」（没被邻居的改动踩坏）',
    loc1After.startsWith('村边的森林'), JSON.stringify(loc1After.slice(0, 10)));
  check('共用同一段字节的两张表确实一起变了（改一处会影响另一处）',
    p14.font.decode(bytes14.slice(f63b.text_offset, f63b.text_offset + 19)).startsWith('鸣人') &&
    loc.records.find((r) => r.id === 0).text === '没有',
    '全名表 id 63 改了 ⇒ 地点名表 id 0 读到的那批字节也变了'
    + '（包里那一格的值会过期 —— ROM 的存储别名，改一处就是改两处）');

  // 11e. 放不下的改动必须被拒
  {
    const p15 = ContentPack.fromJSON(JSON.parse(readFileSync(packPath, 'utf8')));
    const table = p15.textTable('speaker_full_names');
    const record = table.records.find((r) => r.id === 63);
    let long = '';
    while (p15.font.encodedLength(long) + 1 <= record.writable_bytes) long += '涡';
    p15.setText(table, record, long);
    // 直接用 builder：构建报错时也能拿到它写了一半的字节，验证「一个字节都没动」。
    const builder = new RomBuilder(rom, p15);
    let error15 = null;
    try {
      builder.build();
    } catch (err) {
      error15 = err;
    }
    const message15 = error15 ? String(error15.message || error15) : '';
    let unchanged = true;
    for (let i = 0; i < rom.length; i++) {
      if (builder.bytes[i] !== rom[i]) { unchanged = false; break; }
    }
    check('超过可写长度的改动被构建器拒绝（ROM 一个字节都没动）',
      !!error15 && /超长|放不下/.test(message15) && unchanged,
      message15.slice(0, 90) ||
      `可写 ${record.writable_bytes} 字节，写了 ${p15.font.encodedLength(long) + 1} 字节`);
  }

  // 11f. 两处别名改成不同的字 ⇒ 必须报错（不能悄悄丢一处）
  {
    const p16 = ContentPack.fromJSON(JSON.parse(readFileSync(packPath, 'utf8')));
    const fa = p16.textTable('speaker_full_names');
    const la = p16.textTable('location_names');
    p16.setText(fa, fa.records.find((r) => r.id === 63), '鸣人');
    p16.setText(la, la.records.find((r) => r.id === 0), '森林');
    const out16 = safeBuild(p16, rom);
    check('两处别名改成不同的字时构建器报错（不悄悄丢一处）',
      !out16.ok && /同一段字节/.test(out16.report.errors.join(';')),
      out16.report.errors.join('; ').slice(0, 110) || '没有报错');
  }

  // 11g. 变异对照：把写回改回「清零尾巴」的旧行为，11d 必须能发现
  {
    const p17 = ContentPack.fromJSON(JSON.parse(readFileSync(packPath, 'utf8')));
    const table = p17.textTable('speaker_full_names');
    const record = table.records.find((r) => r.id === 63);
    p17.setText(table, record, '鸣人');
    const original = RomBuilder.prototype.inlineWriteClaims;
    // 旧行为：把旧正文之后的尾巴**一律清零**（那是「绝对地址引用」的老做法）。
    RomBuilder.prototype.inlineWriteClaims = function (tbl, rec) {
      const offset = rec.text_offset;
      const raw = rec.raw ? base64ToBytes(rec.raw) : new Uint8Array(0);
      const content = this.pack.textContentBytes(rec);
      const claims = [];
      for (let i = 0; i < content.length; i++) claims.push([offset + i, content[i]]);
      claims.push([offset + content.length, 0]);
      for (let k = content.length + 1; k < raw.length; k++) claims.push([offset + k, 0]);
      return claims;
    };
    let mutated;
    try {
      mutated = safeBuild(p17, rom);
    } finally {
      RomBuilder.prototype.inlineWriteClaims = original;
    }
    const mutatedBytes = mutated.bytes || rom;
    check('变异对照：旧写法（清零尾巴）会抹掉别人的字节 —— 11d 的断言不是空转',
      mutatedBytes[foreignAt] === 0x00 && mutatedBytes[foreignAt] !== rom[foreignAt],
      `变异后 0x${foreignAt.toString(16)} = 0x${mutatedBytes[foreignAt].toString(16)}（原 0x${rom[foreignAt].toString(16)}）`);
  }
}

console.log(`\n${failures === 0 ? '全部通过' : failures + ' 项失败'}`);
process.exit(failures === 0 ? 0 : 1);
