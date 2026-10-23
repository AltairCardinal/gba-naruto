// 造一个**对白变长**的 ROM，给无头 mGBA 做真机验收用。
//
// 用法：node tools/build_reloc_test_rom.mjs [--out build/reloc-test.gba]
//
// 做三件事：
//   1. 载入原版 ROM 与内容包；
//   2. 把**场景 54 的第 5 句对白**改长（那正是 L3 证据
//      `notes/evidence/story-scene-l3.png` 里屏幕上显示的那一句，
//      导航序列是 START + A×4）；
//   3. 构建 ROM —— 变长的对白会触发**剧本搬迁**：整个剧本搬到空闲区、
//      内部绝对地址全部重基、根表指针改掉。
//
// 输出：构建报告（搬到了哪里、重基了几处、改了几个根表指针）+ 正文前后字节。
//
// 依据：notes/evidence/story-script-relocation-20261022.md
import { readFileSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const repoRoot = join(here, '..');

const { ContentPack } = await import('../rom-editor/js/pack.js');
const { buildRom } = await import('../rom-editor/js/rom.js');
const { buildDialogueModel } = await import('../rom-editor/js/dialogue.js');
const { textSegments, commitSegment } = await import('../rom-editor/js/scripttext.js');
const { encodeTokens, mergeTokens } = await import('../rom-editor/js/textcodec.js');

const outIndex = process.argv.indexOf('--out');
const outPath = outIndex >= 0 ? process.argv[outIndex + 1] : 'build/reloc-test.gba';

const rom = new Uint8Array(readFileSync(join(repoRoot, 'rom', 'base.gba')));
const pack = ContentPack.fromJSON(
  JSON.parse(readFileSync(join(repoRoot, 'rom-editor', 'content', 'pack.json'), 'utf8')));
pack.patches = [];

// 场景 54 的第 5 句（L3 证据里屏幕上显示的那一句）。
const SCENE = 54;
const LINE = 4;
const model = buildDialogueModel(rom, pack, 'before', SCENE);
const line = model.lines[LINE];
if (!line) {
  console.error(`场景 ${SCENE} 没有第 ${LINE + 1} 句`);
  process.exit(1);
}
const segment = line.segments[0];
const original = segment.text;

const NEW_TEXT = original + '测试测试';
const expected = encodeTokens(
  mergeTokens(segment.tokens, segment.tokens));   // 占位，下面用真实的
const encoded = (() => {
  const plain = NEW_TEXT.split('↵').join('\n');
  const tokens = [];
  for (const ch of plain) {
    const code = ch.charCodeAt(0);
    if (code >= 32 && code < 127) { tokens.push({ k: 't', c: code }); continue; }
    const fontCode = pack.font.charToCode.get(ch);
    if (fontCode === undefined) {
      console.error(`字库里没有「${ch}」`);
      process.exit(1);
    }
    tokens.push({ k: 't', c: fontCode });
  }
  return encodeTokens(mergeTokens(segment.tokens, tokens));
})();

console.log(`场景 ${SCENE} 第 ${LINE + 1} 句`);
console.log(`  原文：${original}`);
console.log(`  改成：${NEW_TEXT}`);
console.log(`  字节：${segment.originalLength} → ${encoded.length}（+${encoded.length - segment.originalLength}）`);

const result = commitSegment(pack, segment, NEW_TEXT);
if (!result.ok) {
  console.error(`改写失败：${result.message}`);
  process.exit(1);
}
console.log(`  会搬动剧本：${result.relocated}`);

const { bytes, report } = buildRom(pack, rom);
if (report.errors.length) {
  console.error('构建失败：');
  for (const e of report.errors) console.error('  ' + e);
  process.exit(1);
}
console.log('构建报告：');
for (const moved of report.movedScripts) {
  console.log(`  搬迁 ${moved.id}`);
  console.log(`    0x${moved.from.toString(16).toUpperCase()} → 0x${moved.to.toString(16).toUpperCase()}`);
  console.log(`    ${moved.bytes} 字节 / ${moved.segments} 段 / 重基 ${moved.rebased} 处 / 改指针 ${moved.slots} 个`);
  for (const move of moved.roots) {
    console.log(`    入口 0x${move.from.toString(16).toUpperCase()} → 0x${move.to.toString(16).toUpperCase()}`);
  }
  // 新正文在新地址上的位置。
  const at = moved.to + (segment.offset - moved.from);
  const written = bytes.subarray(at, at + encoded.length);
  console.log(`    新正文 @0x${at.toString(16).toUpperCase()}：${Buffer.from(written).toString('hex')}`);
}

const outFile = join(repoRoot, outPath);
writeFileSync(outFile, Buffer.from(bytes));
console.log(`已写出 ${outPath}（${bytes.length} 字节）`);

// 顺带写一份 JSON，供真机验收脚本比对。
const movedScript = report.movedScripts[0];
writeFileSync(join(repoRoot, 'build', 'reloc-test-info.json'), JSON.stringify({
  scene: SCENE,
  line: LINE,
  original,
  new_text: NEW_TEXT,
  original_bytes: segment.originalLength,
  new_bytes: encoded.length,
  // 被改的那条指令（0x01）在剧本里的偏移，以及搬迁后的新地址。
  edited_offset: segment.offset - movedScript.from,
  edited_new_address: movedScript.to + (segment.offset - movedScript.from),
  edited_text_offset: segment.offset,
  moved_scripts: report.movedScripts,
  root_slots: (pack.structures.find((s) => s.id === 'story_before_root') || {})
    .records.filter((r) => report.movedScripts.some(
      (m) => m.roots.some((root) => root.from === r.values.ptr - 0x08000000)))
    .map((r) => ({ scene: r.id, slot: r.rom_offset })),
}, null, 2) + '\n', 'utf8');
console.log('已写出 build/reloc-test-info.json');
