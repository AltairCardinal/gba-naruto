// 字库往返门禁：内容包里的两张字库表必须是「无 0x 的十六进制字符串」键/值。
//
// 用法：node rom-editor/tools/verify_font_map.mjs
//
// 这个门禁盯的是 2026-10-23 修的那个严重 bug：
// `FontCodec` 内部的 Map 键/值是**数字**（0x8140），而内容包里同样的字形码
// 写成**十六进制字符串**（"8140"）。任何一处把 Map 直接
// `Object.fromEntries` 回去，都会把数字变成**十进制**字符串（"33088"），
// `FontCodec` 再 `parseInt(x, 16)` 就得到另一个数字 ⇒
//   * 解码：每个字都变成 `{字XXXX}`（编辑器里满屏占位符 + 每段一条红字）
//   * 编码：整句写成乱码字节（**不只是丢字，还会损坏数据**）
//
// 所以这里不只断「键集合对不对」，还断「解码得出真对白」「编码逐字节往返」
// 「导出路径不坏」「编辑器不再报红字」，最后用**变异对照**证明这些断言
// 真的有牙（把输出改回数字键 ⇒ 同样的断言必须变红）。
//
// stdout 在 PowerShell 下会被 GBK 弄乱，所以正文写到
// build/font-map-verify.txt。

import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const repoRoot = join(here, '..', '..');
const packPath = join(repoRoot, 'rom-editor', 'content', 'pack.json');
const romPath = join(repoRoot, 'rom', 'base.gba');
const jsDir = join(repoRoot, 'rom-editor', 'js');
const workDir = join(repoRoot, 'build', 'font-map-mutation');

import { installDom, StubNode } from './domstub.mjs';

installDom();

const { ContentPack } = await import('../js/pack.js');
const { parsePackFromRom } = await import('../js/parsepack.js');
const { FontCodec } = await import('../js/textcodec.js');
const { scanScript, ROM_BASE } = await import('../js/storyvm.js');
const { textSegments } = await import('../js/scripttext.js');
const { renderScriptView } = await import('../js/modules/scriptview.js');
const { buildRom } = await import('../js/rom.js');

const lines = [];
let failures = 0;
function check(name, ok, detail = '') {
  if (!ok) failures += 1;
  const line = `  [${ok ? 'PASS' : 'FAIL'}] ${name}${detail ? ' — ' + detail : ''}`;
  lines.push(line);
  console.log(line);
}
function head(text) {
  lines.push(text);
  console.log(text);
}

/** ROM 里的真对白（before.1 场景里 0x08009F3D 那句）的字节。 */
const SENTENCE_AT = 0x9f3d;          // 文件偏移（ROM 地址 0x08009F3D）
const SENTENCE_END = 0x9f6b;         // 结尾 NUL 的位置（不含）
/** 0x08009F3D 那句的**指令**（op=0x01，正文从 +1 开始）。 */
const SENTENCE_INSTRUCTION = 0x9f3d;

const HEX4 = /^[0-9A-F]{4}$/;

function readU32(bytes, at) {
  return (bytes[at] | (bytes[at + 1] << 8) | (bytes[at + 2] << 16)
    | (bytes[at + 3] << 24)) >>> 0;
}
function bytesEqual(a, b) {
  if (a.length !== b.length) return false;
  for (let i = 0; i < a.length; i++) if (a[i] !== b[i]) return false;
  return true;
}
function hexBytes(bytes) {
  return Array.from(bytes).map((b) => b.toString(16).toUpperCase().padStart(2, '0')).join(' ');
}

/** 两张表是否**逐格相同**（键集合 + 每个键对应的字符）。 */
function sameTable(a, b) {
  const ka = Object.keys(a || {});
  const kb = Object.keys(b || {});
  if (ka.length !== kb.length) return false;
  for (const k of ka) {
    if (!Object.prototype.hasOwnProperty.call(b, k)) return false;
    if (a[k] !== b[k]) return false;
  }
  return true;
}

/**
 * 两组文本表是否相同。
 *
 * `record.tokens` 是**运行时按 `raw` 现算的缓存**（`pack.js::textTokens`
 * 惰性写上去的），不是内容包里的一项 —— 比较时要把它去掉。
 * （`ContentPack.fromJSON` 只做浅拷贝，构建 ROM 时写进记录的缓存会漏回
 *  调用方手里那个数据对象，所以这个坑是真实存在的。）
 */
function sameTexts(a, b) {
  const strip = (tables) => (tables || []).map((t) => ({
    ...t,
    records: (t.records || []).map(({ tokens, ...rest }) => rest),
  }));
  return JSON.stringify(strip(a)) === JSON.stringify(strip(b));
}

/**
 * 门禁主体：给定一个内容包**数据**，断它的两张字库表。
 *
 * 真实路径与变异体都走这一个函数 —— 变异对照才有意义。
 */
function auditFontTables(packData) {
  const keys = Object.keys(packData.font.code_to_char);
  const vals = Object.values(packData.font.char_to_code);
  return {
    keys,
    vals,
    keysOk: sameTable(packData.font.code_to_char, refTable.code_to_char),
    valsOk: sameTable(packData.font.char_to_code, refTable.char_to_code),
    hexOk: keys.every((k) => HEX4.test(k)) && vals.every((v) => HEX4.test(v)),
  };
}

/** 门禁主体：给定一个 `FontCodec`，断解码 / 编码。 */
function auditCodec(font) {
  const text = font.decode(SENTENCE);
  const wanted = ['“', '好', '～', '！', '出发啦'];
  const missing = wanted.filter((c) => !text.includes(c));
  const hao = font.encode('好');
  return {
    text,
    missing,
    noPlaceholder: !text.includes('{字'),
    roundTrip: bytesEqual(font.encode(text), SENTENCE),
    haoHex: hexBytes(hao),
    haoOk: bytesEqual(hao, new Uint8Array([0x8d, 0xc0])),
  };
}

/** 把源码里的相对 import 改成绝对 file:// URL（临时副本放在 build/ 下）。 */
function absolutizeImports(src, dir) {
  return src.replace(/from\s+'(\.\/[^']+)'/g,
    (_m, spec) => `from '${pathToFileURL(join(dir, spec)).href}'`);
}

/** 写出一份变异过的源码并 import 它（`?t=` 让每次运行都拿到新模块实例）。 */
async function loadMutant(src, file) {
  writeFileSync(file, absolutizeImports(src, jsDir), 'utf8');
  return import(pathToFileURL(file).href + `?t=${Date.now()}`);
}

const packJson = JSON.parse(readFileSync(packPath, 'utf8'));
const rom = new Uint8Array(readFileSync(romPath));
const SENTENCE = rom.slice(SENTENCE_AT, SENTENCE_END);
const refTable = {
  code_to_char: packJson.font.code_to_char,
  char_to_code: packJson.font.char_to_code,
};

head('\n1) 基准：pack.json 里的两张字库表本来就是「无 0x 的十六进制字符串」');
{
  const refKeys = Object.keys(refTable.code_to_char);
  const refVals = Object.values(refTable.char_to_code);
  check('code_to_char 的键全是 4 位大写十六进制',
    refKeys.every((k) => HEX4.test(k)),
    `${refKeys.length} 个键，示例 ${refKeys.slice(0, 3).join(',')}`);
  check('char_to_code 的值全是 4 位大写十六进制',
    refVals.every((v) => HEX4.test(v)),
    `${refVals.length} 个值，示例 ${refVals.slice(0, 3).join(',')}`);
  check('两张表都有内容（4,261 / 4,253）',
    refKeys.length === 4261 && refVals.length === 4253,
    `code_to_char ${refKeys.length} / char_to_code ${refVals.length}`);
}

head('\n2) 从 ROM 解析出来的内容包：两张字库表与 pack.json 完全一致');
const template = ContentPack.fromJSON(packJson);
let parsedData = null;
{
  const { pack, report } = parsePackFromRom(template, rom, { name: 'base.gba' });
  parsedData = pack;
  const audit = auditFontTables(pack);
  check('解析出来的 code_to_char 与 pack.json 逐格相同',
    audit.keysOk, `${audit.keys.length} 个键`);
  check('解析出来的 char_to_code 与 pack.json 逐格相同',
    audit.valsOk, `${audit.vals.length} 个值`);
  check('键/值全是 4 位大写十六进制（不是十进制）',
    audit.hexOk, `示例 ${audit.keys.slice(0, 3).join(',')}`);
  check('抽查：8140 = 全角空格',
    pack.font.code_to_char['8140'] === '　',
    JSON.stringify(pack.font.code_to_char['8140']));
  check('解析本身没有报错', report.errors.length === 0, report.errors.join('; '));
}

head('\n3) 解码真对白：ROM 0x08009F3D 那句必须是中文，不是 {字XXXX}');
{
  const font = new FontCodec(parsedData.font.code_to_char, parsedData.font.char_to_code);
  const audit = auditCodec(font);
  check('解出「“ 好 ～ ！ 出发啦」这些真实字符',
    audit.missing.length === 0,
    audit.missing.length ? `缺 ${audit.missing.join('、')}` : audit.text);
  check('不得出现 {字 字样', audit.noPlaceholder, audit.text);
  check('解出来的正是那一句',
    audit.text === '“好～～！！　　\n出发啦～～～～！！”　　　　',
    JSON.stringify(audit.text));
}

head('\n4) 编码往返：decode → encode 必须与 ROM 那段逐字节相同');
{
  const font = new FontCodec(parsedData.font.code_to_char, parsedData.font.char_to_code);
  const audit = auditCodec(font);
  check('decode → encode 与原 ROM 那段逐字节相同',
    audit.roundTrip, `${SENTENCE.length} 字节：${hexBytes(SENTENCE)}`);
  check('单字「好」编成 8D C0',
    audit.haoOk, audit.haoHex);
}

head('\n5) 导出路径：ContentPack.fromJSON(pack.toJSON()) 之后字库完全一致');
{
  const exported = ContentPack.fromJSON(packJson).toJSON();
  const audit = auditFontTables(exported);
  check('导出的 code_to_char 与 pack.json 逐格相同',
    audit.keysOk, `${audit.keys.length} 个键`);
  check('导出的 char_to_code 与 pack.json 逐格相同',
    audit.valsOk, `${audit.vals.length} 个值`);
  check('导出的键/值是十六进制字符串（不是十进制）',
    audit.hexOk, `示例 ${audit.keys.slice(0, 3).join(',')}`);
  // 再从导出的内容包重建一次字库：解码 / 编码都得对。
  const font = new FontCodec(exported.font.code_to_char, exported.font.char_to_code);
  const audit2 = auditCodec(font);
  check('导出的字库仍能解出真对白', audit2.noPlaceholder && audit2.missing.length === 0,
    audit2.text);
  check('导出的字库仍能把「好」编成 8D C0', audit2.haoOk, audit2.haoHex);
}

head('\n6) 编辑器层面：「剧情与对白」页不再有红字');
{
  const parsed = ContentPack.fromJSON(parsedData);
  const root = readU32(rom, 0x060c74 + 1 * 4) - ROM_BASE;
  const instruction = scanScript(rom, root).find((i) => i.offset === SENTENCE_INSTRUCTION);
  const segments = instruction ? textSegments(rom, parsed, instruction) : [];
  const seg = segments[0];
  check('找得到 0x08009F3D 那句对白', !!seg,
    instruction ? `指令 op=0x${instruction.op.toString(16)}` : '没找到指令');
  check('那段的「问题提示」是空的（红字消失）',
    !!(seg && !seg.problem), seg ? String(seg.problem) : '—');
  check('那段的正文是中文（没有 {字XXXX}）',
    !!(seg && !seg.text.includes('{字')), seg ? seg.text : '—');
  check('正文里能看到「出发啦」',
    !!(seg && seg.text.includes('出发啦')), seg ? seg.text : '—');

  // 全剧扫一遍：没有任何一段带「字库解不出来」的提示。
  let total = 0;
  let bad = 0;
  let firstBad = '';
  for (const script of parsed.scripts || []) {
    for (const instr of scanScript(rom, script.script_offset)) {
      for (const s of textSegments(rom, parsed, instr)) {
        total += 1;
        if (s.problem && s.problem.includes('字库解不出来')) {
          bad += 1;
          if (!firstBad) firstBad = `${script.id}@0x${s.offset.toString(16)}`;
        }
      }
    }
  }
  check('全部剧本的所有文本段都没有「字库解不出来」的提示',
    bad === 0,
    bad ? `${total} 段里 ${bad} 段有问题（第一条 ${firstBad}）` : `${total} 段全过`);
}

head('\n7) 无头渲染「剧情与对白」页：正文是中文，没有红色提示');
{
  const parsed = ContentPack.fromJSON(parsedData);
  const container = new StubNode('div');
  const ctx = {
    pack: parsed,
    rom,
    state: { view: { panel: { kind: 'script', id: 'script', params: { root: 'before', scene: 1 } } } },
    openPanel() {},
    onJump() {},
  };
  renderScriptView(container, ctx);
  const nodes = container.descendants();
  const bads = nodes.filter((n) => String(n.className || '').split(/\s+/).includes('bad'));
  const inputs = nodes.filter((n) => String(n.className || '').includes('script-text-input'));
  const inputValues = inputs.map((n) => String(n.attributes.value ?? ''));
  const allText = container.textContent;
  check('页面里没有 class="bad" 的红色提示',
    bads.length === 0, bads.length ? bads.map((n) => n.textContent).join(' | ') : `${nodes.length} 个节点，0 个 bad`);
  check('正文输入框里是中文（没有 {字XXXX}）',
    inputValues.length > 0 && inputValues.every((v) => !v.includes('{字')),
    inputValues.length ? `${inputValues.length} 个输入框，示例 ${inputValues[0]}` : '没有输入框');
  check('正文里能看到「出发啦」',
    inputValues.some((v) => v.includes('出发啦')), inputValues.join(' | ').slice(0, 120));
  check('页面正文里没有 {字 字样', !allText.includes('{字'), '');
  check('编辑器认为这段是「等长，失焦即保存」（可以改）',
    allText.includes('等长，失焦即保存'), '');
}

head('\n8) 端到端：解析 → 构建 → 再解析（一个字都不改）');
{
  const rebuilt = buildRom(ContentPack.fromJSON(parsedData), rom);
  check('构建无错误', rebuilt.report.errors.length === 0, rebuilt.report.errors.join('; '));
  check('重建出来的 ROM 与原版逐字节相同',
    bytesEqual(rebuilt.bytes, rom), `${rom.length} 字节`);
  const again = parsePackFromRom(ContentPack.fromJSON(packJson), rebuilt.bytes, { name: 'base.gba' });
  const audit = auditFontTables(again.pack);
  check('再解析回来的字库与 pack.json 逐格相同',
    audit.keysOk && audit.valsOk, `code_to_char ${audit.keys.length} / char_to_code ${audit.vals.length}`);
  check('再解析回来的 13 张文本表与第一次解析的逐表相同',
    sameTexts(parsedData.texts, again.pack.texts),
    `${again.pack.texts.length} 张表`);
}

head('\n9) 变异对照：把输出改回「数字键」⇒ 同样的断言必须变红（临时副本，仓库文件零改动）');
{
  mkdirSync(workDir, { recursive: true });

  // A. parsepack.js —— 解析路径
  const parsepackSrc = readFileSync(join(jsDir, 'parsepack.js'), 'utf8');
  const brokenParse = '({ code_to_char: Object.fromEntries(template.font.codeToChar),' +
    ' char_to_code: Object.fromEntries(template.font.charToCode) })';
  const mutatedParseSrc = parsepackSrc.replace('fontTablesToJson(template.font)', brokenParse);
  check('变异点命中：parsepack.js 里确实有那一行',
    mutatedParseSrc !== parsepackSrc, 'fontTablesToJson(template.font)');
  const mutantParse = await loadMutant(mutatedParseSrc, join(workDir, 'parsepack.mjs'));
  const { pack: mutantData } = mutantParse.parsePackFromRom(template, rom, { name: 'base.gba' });
  const mutantAudit = auditFontTables(mutantData);
  check('变异体：code_to_char 与 pack.json **不同**（第 2 节会红）',
    !mutantAudit.keysOk, `${mutantAudit.keys.length} 个键，示例 ${mutantAudit.keys.slice(0, 3).join(',')}`);
  check('变异体：char_to_code 与 pack.json **不同**（第 2 节会红）',
    !mutantAudit.valsOk, `${mutantAudit.vals.length} 个值，示例 ${mutantAudit.vals.slice(0, 3).join(',')}`);
  check('变异体：键不是十六进制字符串（是十进制）',
    !mutantAudit.hexOk, `示例 ${mutantAudit.keys.slice(0, 3).join(',')}`);
  const mutantFont = new FontCodec(mutantData.font.code_to_char, mutantData.font.char_to_code);
  const mutantCodec = auditCodec(mutantFont);
  check('变异体：解不出真对白（第 3 节会红）',
    !mutantCodec.noPlaceholder || mutantCodec.missing.length > 0,
    mutantCodec.text.slice(0, 40));
  check('变异体：decode → encode 不再逐字节相同（第 4 节会红）',
    !mutantCodec.roundTrip, `「好」编成 ${mutantCodec.haoHex}`);
  check('变异体：「好」编成乱码字节（数据损坏）',
    !mutantCodec.haoOk, mutantCodec.haoHex);

  // B. pack.js —— 导出路径
  const packSrc = readFileSync(join(jsDir, 'pack.js'), 'utf8');
  const brokenExport = 'font: { code_to_char: Object.fromEntries(this.font.codeToChar),' +
    ' char_to_code: Object.fromEntries(this.font.charToCode) },';
  const mutatedPackSrc = packSrc.replace('font: fontTablesToJson(this.font),', brokenExport);
  check('变异点命中：pack.js 的 toJSON 里确实有那一行',
    mutatedPackSrc !== packSrc, 'font: fontTablesToJson(this.font),');
  const mutantPack = await loadMutant(mutatedPackSrc, join(workDir, 'pack.mjs'));
  const mutantExport = mutantPack.ContentPack.fromJSON(packJson).toJSON();
  const mutantExportAudit = auditFontTables(mutantExport);
  check('变异体：导出的 code_to_char 与 pack.json **不同**（第 5 节会红）',
    !mutantExportAudit.keysOk,
    `${mutantExportAudit.keys.length} 个键，示例 ${mutantExportAudit.keys.slice(0, 3).join(',')}`);
  check('变异体：导出的键不是十六进制字符串（是十进制）',
    !mutantExportAudit.hexOk, `示例 ${mutantExportAudit.keys.slice(0, 3).join(',')}`);
}

const summary = failures === 0
  ? `全部通过（${lines.filter((l) => l.includes('[PASS]')).length} 条断言）`
  : `${failures} 项失败`;
lines.push('');
lines.push(summary);
writeFileSync(join(repoRoot, 'build', 'font-map-verify.txt'), lines.join('\n') + '\n', 'utf8');
console.log('');
console.log(summary);
process.exit(failures === 0 ? 0 : 1);
