// 造一个**说话人名变长**的 ROM，给无头 mGBA 做真机验收用。
//
// 用法：node tools/build_speaker_test_rom.mjs [--out build/speaker-test.gba]
//                                 [--id 1] [--text 测试] [--suffix 测试]
//
// 做三件事：
//   1. 载入原版 ROM 与内容包；
//   2. 把**说话人名表**的一条改长 —— 这会触发**结构转换**：
//      整张表从「定长内联槽」变成「指针表 + 变长串池」，
//      并且 ROM 里的 **12 个取名读者**被改掉（`基址+id*12` → `基址+id*4` 再解引用，
//      **指令数与字节数都不变** ⇒ 不挪动任何后续代码）；
//   3. 构建 ROM 并把转换报告写进 `build/speaker-test-info.json`。
//
// `--id` / `--text` 可以指定改哪一条、改成什么；不给就改 id 1（鸣人）。
// `--suffix` 只在名字后面追加（默认追加「测试」）。
//
// 依据：notes/evidence/speaker-name-table-20261023.md
// 　　　notes/evidence/speaker-name-code-patches-20261023.md
import { readFileSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const repoRoot = join(here, '..');

const { ContentPack } = await import('../rom-editor/js/pack.js');
const { buildRom } = await import('../rom-editor/js/rom.js');

function arg(name, fallback) {
  const i = process.argv.indexOf(`--${name}`);
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : fallback;
}

const outPath = arg('out', 'build/speaker-test.gba');
const targetId = Number(arg('id', '1'));
const suffix = arg('suffix', '测试');

const rom = new Uint8Array(readFileSync(join(repoRoot, 'rom', 'base.gba')));
const pack = ContentPack.fromJSON(
  JSON.parse(readFileSync(join(repoRoot, 'rom-editor', 'content', 'pack.json'), 'utf8')));
pack.patches = [];

const table = pack.textTable('speaker_names');
const record = table.records.find((r) => r.id === targetId);
if (!record) {
  console.error(`说话人名表里没有 id ${targetId}`);
  process.exit(1);
}
const original = record.text;
const NEW_TEXT = arg('text', `${original}${suffix}`);
console.log(`说话人名表 id ${targetId}`);
console.log(`  原文：${original}`);
console.log(`  改成：${NEW_TEXT}`);

pack.setText(table, record, NEW_TEXT);

const { bytes, report } = buildRom(pack, rom);
if (report.errors.length) {
  console.error('构建失败：');
  for (const e of report.errors) console.error('  ' + e);
  process.exit(1);
}
console.log('构建报告：');
for (const conv of report.conversions || []) {
  console.log(`  转换 ${conv.table}（${conv.kind}）：指针表基址 0x${conv.base.toString(16).toUpperCase()}，`
    + `${conv.records} 条名字`);
}
const moved = (report.movedTexts || []).filter((m) => m.table === 'speaker_names');
console.log(`  串池：${moved.length} 条名字，`
  + `0x${Math.min(...moved.map((m) => m.to)).toString(16).toUpperCase()} 起`);
const one = moved.find((m) => m.id === targetId);
console.log(`  id ${targetId} 的新位置：0x${one.to.toString(16).toUpperCase()}`);

writeFileSync(join(repoRoot, outPath), Buffer.from(bytes));
console.log(`已写出 ${outPath}（${bytes.length} 字节）`);

writeFileSync(join(repoRoot, 'build', 'speaker-test-info.json'), JSON.stringify({
  id: targetId,
  original,
  new_text: NEW_TEXT,
  new_address: one.to,
  pointer_table_base: 0x085a57c4,
  conversions: report.conversions,
}, null, 2) + '\n', 'utf8');
console.log('已写出 build/speaker-test-info.json');
