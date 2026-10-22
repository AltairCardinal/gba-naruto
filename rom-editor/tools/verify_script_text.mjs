// 剧情脚本「对白可改」的无头验收脚本。
//
// 对应需求：剧情脚本里带文本的指令（op 0x01 文本、0x05 菜单文字、
// 0x20 带说话人的对白、0x13 取文本+下一段）的正文可以就地改写。
//
// 核心约束（第十七轮起变了）：**长度不限**。
// 文本是内联在脚本字节流里的，而脚本里的分支目标是绝对 ROM 地址 ——
// 等长改写直接原地落地；变长 / 变短则由「构建时把整个剧本搬到空闲区、
// 重基它内部的绝对地址、改根表指针」兜住（`js/rom.js::applyScriptRelocations`，
// 端到端的验收在 `rom-editor/tools/verify_variable_text.mjs`）。
//
// 用法：node rom-editor/tools/verify_script_text.mjs
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

// --- 一个很小的 DOM --------------------------------------------------------
class StubNode {
  constructor(tag) {
    this.tagName = String(tag || '').toUpperCase();
    this.nodeType = 1;
    this.children = [];
    this.parentNode = null;
    this.attributes = {};
    this.dataset = {};
    this.style = {};
    this.listeners = {};
    this._text = '';
    this._className = '';
    const self = this;
    this.classList = {
      add: (...names) => {
        const set = new Set(self._className.split(/\s+/).filter(Boolean));
        names.forEach((n) => set.add(n));
        self._className = [...set].join(' ');
      },
      remove: (...names) => {
        const set = new Set(self._className.split(/\s+/).filter(Boolean));
        names.forEach((n) => set.delete(n));
        self._className = [...set].join(' ');
      },
      toggle: (name, force) => {
        const has = self.classList.contains(name);
        const want = force === undefined ? !has : !!force;
        if (want) self.classList.add(name); else self.classList.remove(name);
        return want;
      },
      contains: (name) => self._className.split(/\s+/).includes(name),
    };
  }
  get className() { return this._className; }
  set className(v) { this._className = String(v || ''); }
  get value() { return this.attributes.value ?? ''; }
  set value(v) { this.attributes.value = String(v); }
  get firstChild() { return this.children[0] || null; }
  get textContent() {
    if (this.children.length) return this.children.map((c) => c.textContent).join('');
    return this._text;
  }
  set textContent(v) { this.children = []; this._text = String(v === null || v === undefined ? '' : v); }
  set innerHTML(v) { this.children = []; this._text = String(v || ''); }
  get innerHTML() { return this.textContent; }
  appendChild(node) {
    if (node && node.__text) {
      this.children.push({ textContent: node.__text, nodeType: 3, children: [] });
    } else {
      this.children.push(node);
      if (node) node.parentNode = this;
    }
    return node;
  }
  get parentElement() { return this.parentNode || null; }
  removeChild(node) {
    const at = this.children.indexOf(node);
    if (at >= 0) this.children.splice(at, 1);
    return node;
  }
  remove() { if (this.parentNode) this.parentNode.removeChild(this); }
  addEventListener(name, fn) { (this.listeners[name] ||= []).push(fn); }
  setAttribute(name, value) { this.attributes[name] = String(value); }
  getAttribute(name) { return this.attributes[name] ?? null; }
  querySelector() { return null; }
  querySelectorAll() { return []; }
  descendants() {
    const out = [];
    const walk = (node) => {
      for (const child of node.children) {
        if (!child || !child.children) continue;
        out.push(child);
        walk(child);
      }
    };
    walk(this);
    return out;
  }
}

globalThis.document = {
  createElement: (tag) => new StubNode(tag),
  createTextNode: (text) => ({ __text: String(text), textContent: String(text), nodeType: 3 }),
  body: new StubNode('body'),
  getElementById: () => null,
  querySelector: () => null,
};
globalThis.window = {
  location: { hash: '' },
  addEventListener() {},
  removeEventListener() {},
};

const here = dirname(fileURLToPath(import.meta.url));
// 这个脚本住在 rom-editor/tools/，所以仓库根在两级之上。
const repoRoot = join(here, '..', '..');
const packPath = join(repoRoot, 'rom-editor', 'content', 'pack.json');
const romPath = join(repoRoot, 'rom', 'base.gba');

const { ContentPack } = await import('../js/pack.js');
const { buildRom } = await import('../js/rom.js');
const { scanScript, ROM_BASE } = await import('../js/storyvm.js');
const {
  textSegments, segmentBudget, commitSegment, displayText, encodeText, NEWLINE_MARK,
} = await import('../js/scripttext.js');
const { encodeTokens, mergeTokens } = await import('../js/textcodec.js');
const { hexToBytes, bytesToHex } = await import('../js/bytes.js');
const { renderScriptView } = await import('../js/modules/scriptview.js');

let failures = 0;
function check(name, ok, detail = '') {
  if (!ok) failures += 1;
  console.log(`  [${ok ? 'PASS' : 'FAIL'}] ${name}${detail ? ' — ' + detail : ''}`);
}

const packData = JSON.parse(readFileSync(packPath, 'utf8'));
const rom = new Uint8Array(readFileSync(romPath));

/**
 * 一个干净的内容包。
 *
 * `pack.json` 里的 `patches` 是一个**共享数组**，直接 `fromJSON` 会让几段测试
 * 共用同一批补丁 —— 这里每次都给一份新的。
 */
function freshPack() {
  const pack = ContentPack.fromJSON(packData);
  pack.patches = [];
  return pack;
}

/** 一个带文本的指令（取第一场剧本里第一条 op 0x01）。 */
function firstTextInstruction() {
  const structure = packData.structures.find((s) => s.id === 'story_before_root');
  for (const record of structure.records) {
    const ptr = record.values.ptr;
    if (!ptr) continue;
    const instructions = scanScript(rom, ptr - ROM_BASE);
    const hit = instructions.find((ins) => ins.op === 0x01);
    if (hit) return { record, instruction: hit };
  }
  return null;
}

/** 找一个与 `ch` 编码宽度相同的字（用来造等长的新文本）。 */
function sameWidthChar(font, ch) {
  const width = font.encode(ch).length;
  for (const candidate of font.charToCode.keys()) {
    if (candidate === ch) continue;
    if (candidate === '\n' || candidate === NEWLINE_MARK) continue;
    if (font.encode(candidate).length !== width) continue;
    return candidate;
  }
  return null;
}

/** 新文本编码后应当得到的字节（与写回路径同源）。 */
function expectedBytes(segment, text, font) {
  const plain = text.split(NEWLINE_MARK).join('\n');
  return encodeTokens(mergeTokens(segment.tokens, encodeText(plain, font).tokens));
}

console.log('1) 文本段能被定位（文件偏移 + 字节长度 + 解码后的文本）');
{
  const pack = freshPack();
  const hit = firstTextInstruction();
  check('剧本里有带文本的指令', !!hit,
    hit ? `0x${hit.instruction.offset.toString(16).toUpperCase()}` : '没有');
  const segments = textSegments(rom, pack, hit.instruction);
  check('这条指令的文本段被定位出来', segments.length === 1,
    `${segments.length} 段`);
  const segment = segments[0];
  check('文本段带文件偏移与字节长度',
    segment.offset > 0 && segment.length > 0,
    `offset 0x${segment.offset.toString(16).toUpperCase()} / ${segment.length} 字节`);
  // 偏移与长度必须与 ROM 里的实际字节对上：正文后面紧跟 NUL。
  const body = rom.subarray(segment.offset, segment.offset + segment.length);
  check('正文后面紧跟 NUL 结束符', rom[segment.offset + segment.length] === 0,
    `0x${rom[segment.offset + segment.length].toString(16)}`);
  check('解码出的文本非空', segment.text.length > 0,
    JSON.stringify(segment.text.slice(0, 24)));
  check('解码出的文本与正文逐字节自洽',
    displayText(segment.tokens, pack.font) === segment.text,
    `${segment.tokens.length} 个 token`);
  check('换行显示成 ↵', segment.text.includes(NEWLINE_MARK),
    JSON.stringify(segment.text.slice(0, 24)));
}

console.log('\n2) 等长改写：补丁计数 +1、after_hex 是新字节、撤销后回落');
{
  const pack = freshPack();
  const hit = firstTextInstruction();
  const segment = textSegments(rom, pack, hit.instruction)[0];
  const font = pack.font;
  const original = rom.subarray(segment.offset, segment.offset + segment.length);

  // 造一个**等长**的新文本：把第一个字换成同样宽度的另一个字。
  const swapAt = [...segment.text].findIndex((ch) => font.encode(ch).length === 2);
  check('原文本里有可替换的双字节字', swapAt >= 0, `位置 ${swapAt}`);
  const chars = [...segment.text];
  chars[swapAt] = sameWidthChar(font, chars[swapAt]);
  const newText = chars.join('');

  const expected = expectedBytes(segment, newText, font);
  check('新文本编码后与原正文一样长', expected.length === segment.length,
    `${expected.length} / ${segment.length} 字节`);

  const before = pack.changedPatchCount();
  const result = commitSegment(pack, segment, newText);
  check('等长改写被接受', result.ok === true,
    result.ok ? '' : result.message);
  check('改动计数 +1', pack.changedPatchCount() === before + 1,
    `${before} → ${pack.changedPatchCount()}`);

  const patch = (pack.patches || []).find((p) => p.offset === segment.offset);
  check('补丁落在文本段上', !!patch,
    patch ? `0x${patch.offset.toString(16).toUpperCase()}` : '没有补丁');
  check('after_hex 等于新字节', patch.after_hex === bytesToHex(expected),
    `${patch.after_hex.slice(0, 24)}… vs ${bytesToHex(expected).slice(0, 24)}…`);
  check('after_hex 逐字节等于字库编码出来的新文本',
    bytesToHex(hexToBytes(patch.after_hex)) === bytesToHex(expected),
    `${expected.length} 字节`);
  check('before_hex 是原正文', patch.before_hex === bytesToHex(original),
    patch.before_hex.slice(0, 24));

  // 撤销：after_hex 恢复，改动计数回落。
  pack.undo();
  const after = pack.changedPatchCount();
  check('撤销后 after_hex 恢复原值',
    patch.after_hex === patch.before_hex,
    `${patch.after_hex.slice(0, 24)}…`);
  check('撤销后改动计数回落', after === before,
    `${pack.changedPatchCount()} → ${after}`);
}

console.log('\n3) 不等长改写：被接受（会搬动剧本）、字库缺字仍拦下');
{
  const pack = freshPack();
  const hit = firstTextInstruction();
  const segment = textSegments(rom, pack, hit.instruction)[0];
  const before = pack.changedPatchCount();
  const patchesBefore = (pack.patches || []).length;

  // 改长：用一个字库里有的字（否则先被「缺字」拦下，测不到长度规则）。
  const tooLong = segment.text + '　';
  const result = commitSegment(pack, segment, tooLong);
  check('变长改写被接受', result.ok === true, result.ok ? '' : result.message);
  check('结果里标明「会搬动剧本」', result.relocated === true, String(result.relocated));
  check('产生了一条补丁', (pack.patches || []).length === patchesBefore + 1,
    `${patchesBefore} → ${(pack.patches || []).length}`);
  check('改动计数 +1', pack.changedPatchCount() === before + 1,
    `${before} → ${pack.changedPatchCount()}`);
  const patch = (pack.patches || []).find((p) => p.offset === segment.offset);
  check('补丁变长了', hexToBytes(patch.after_hex).length > segment.originalLength,
    `${segment.originalLength} → ${hexToBytes(patch.after_hex).length} 字节`);
  check('补丁的 before_hex 是**原版**正文（搬迁按原版布局算偏移）',
    patch.before_hex === bytesToHex(segment.originalBytes),
    `${patch.before_hex.length / 2} 字节`);

  // 改短也一样能写（靠搬迁腾地方）。
  const pack2 = freshPack();
  const segment2 = textSegments(rom, pack2, hit.instruction)[0];
  const tooShort = segment2.text.slice(0, Math.max(0, segment2.text.length - 1));
  const short = commitSegment(pack2, segment2, tooShort);
  check('变短同样被接受', short.ok === true && short.relocated === true,
    short.ok ? '' : short.message);

  // 字库缺字也要拦下（不能默默丢掉那个字）。
  // 找一个字库里真的没有的字（ASCII 不算 —— ROM 的字体有 ASCII）。
  const missingChar = ['Ж', 'ѐ', 'Ω', '€', '←', '😀']
    .find((ch) => pack.font.encode(ch).length === 0);
  check('找得到一个字库里没有的字', !!missingChar,
    missingChar ? `U+${missingChar.charCodeAt(0).toString(16).toUpperCase()}` : '没有');
  const missing = commitSegment(pack, segment, segment.text + (missingChar || 'Ж'));
  check('字库缺字被拦下', missing.ok === false && /字库/.test(missing.message || ''),
    (missing.message || '').slice(0, 30));
}

console.log('\n4) 写回真的进了 ROM（构建后逐字节相等）');
{
  const pack = freshPack();
  const hit = firstTextInstruction();
  const segment = textSegments(rom, pack, hit.instruction)[0];
  const font = pack.font;
  const chars = [...segment.text];
  const swapAt = [...segment.text].findIndex((ch) => font.encode(ch).length === 2);
  chars[swapAt] = sameWidthChar(font, chars[swapAt]);
  const newText = chars.join('');
  const expected = expectedBytes(segment, newText, font);
  commitSegment(pack, segment, newText);

  const out = buildRom(pack, rom);
  check('构建无错误', out.report.errors.length === 0, out.report.errors.join('; '));
  const written = out.bytes.subarray(segment.offset, segment.offset + expected.length);
  check('构建后的字节逐字节等于字库编码出来的新文本',
    bytesToHex(written) === bytesToHex(expected),
    bytesToHex(written).slice(0, 40));
  check('结束符还在原位', out.bytes[segment.offset + expected.length] === 0,
    `0x${out.bytes[segment.offset + expected.length].toString(16)}`);
  check('后面那条指令没有被移动',
    out.bytes[segment.offset + expected.length + 1] ===
      rom[segment.offset + segment.length + 1],
    '下一个字节没变');
}

console.log('\n5) 界面：输入框、失焦即保存、变长提示、跳到原始字节');
{
  const pack = freshPack();
  const hit = firstTextInstruction();
  const structure = packData.structures.find((s) => s.id === 'story_before_root');
  const scene = structure.records.indexOf(hit.record);
  const jumps = [];
  let changes = 0;
  const ctx = {
    pack,
    rom,
    baseRom: rom,
    state: { view: { panel: { kind: 'script', id: 'script', params: { root: 'before', scene } } } },
    onChange() { changes += 1; },
    openPanel() {},
    goModule() {},
    render() {},
    setStatus() {},
    onJump(target) { jumps.push(target); },
  };
  const host = new StubNode('div');
  renderScriptView(host, ctx);
  const inputs = host.descendants()
    .filter((n) => n.tagName === 'INPUT')
    .filter((n) => String(n.className || '').includes('script-text-input'));
  check('对白那一列给的是输入框', inputs.length > 0, `${inputs.length} 个对白输入框`);

  const text = host.textContent || '';
  check('说明里写明「长度不限」', text.includes('长度不限'), '');
  check('说明里写明会「搬到空闲区」', text.includes('搬到'), '');
  check('说明里不再说「必须等长」', !text.includes('必须等长'));
  check('有字节预算', /\d+ \/ \d+ 字节/.test(text),
    (text.match(/\d+ \/ \d+ 字节/) || [''])[0]);

  // 找一条对白输入框，改长 → 预算变黄并写明「会搬到空闲区」，失焦即保存。
  const target = inputs.find((input) => input.value.length > 3);
  check('找到可编辑的对白', !!target, target ? target.value.slice(0, 20) : '');
  const original = target.value;
  const patchesBefore = (pack.patches || []).length;
  target.value = original + '　';
  target.listeners.input[0]();               // 预算立刻重算
  const warnText = host.textContent || '';
  check('改长后预算写明「变长」', warnText.includes('变长'),
    (warnText.match(/变长[^，。]{0,30}/) || [''])[0]);
  check('改长后写明「整个剧本会搬到空闲区」', warnText.includes('搬到空闲区'),
    (warnText.match(/[^，。]{0,24}搬到空闲区/) || [''])[0]);
  check('改长后不再说「等长才能改」', !warnText.includes('等长才能改'));
  target.listeners.change[0]();              // 失焦即保存
  check('改长后被接受（输入框保留新文本）', target.value === original + '　',
    `${target.value.slice(0, 12)}…`);
  check('改长后产生了一条补丁', (pack.patches || []).length === patchesBefore + 1,
    `${patchesBefore} → ${(pack.patches || []).length}`);
  check('改长触发改动计数', changes === 1, `${changes} 次 onChange`);

  // 等长改写 → 也走 onChange（顶部「已改动 N」+1）。
  const font = pack.font;
  const chars = [...original];
  const swapAt = [...original].findIndex((ch) => font.encode(ch).length === 2);
  if (swapAt >= 0) {
    chars[swapAt] = sameWidthChar(font, chars[swapAt]);
    target.value = chars.join('');
    target.listeners.change[0]();
    check('等长改写被接受', (pack.patches || []).length === patchesBefore + 1,
      `${(pack.patches || []).length} 条补丁（原来 ${patchesBefore}）`);
    check('等长改写触发 onChange（顶部计数 +1）', changes === 2, `${changes} 次`);
    check('顶部计数真的 +1', pack.changedCount() >= 1, `changedCount=${pack.changedCount()}`);
    check('等长改写后输入框保留新文本', target.value === chars.join(''),
      target.value.slice(0, 12));
  }

  // 跳到原始字节。
  const links = host.descendants()
    .filter((n) => n.tagName === 'BUTTON')
    .filter((n) => String(n.className || '').includes('script-text-link'));
  check('文本段旁边有「跳到原始字节」', links.length > 0, `${links.length} 个链接`);
  if (links.length) {
    links[0].listeners.click[0]();
    const jump = jumps[jumps.length - 1];
    check('跳转目标是原始字节的地址',
      jump && jump.module === 'raw' && jump.kind === 'raw-offset' && jump.id === 'raw' &&
        Number.isFinite(jump.params.offset),
      jump ? `#raw/offset/0x${jump.params.offset.toString(16).toUpperCase()}` : '没有跳转');
  }
}

console.log('\n6) 控制码原位保留、0x13 的第二段、说话人');
{
  const pack = freshPack();
  const structure = packData.structures.find((s) => s.id === 'story_before_root');
  // 找一条带控制码的正文（0x05 菜单文字里就有）。
  let found = null;
  for (const record of structure.records) {
    const ptr = record.values.ptr;
    if (!ptr) continue;
    for (const ins of scanScript(rom, ptr - ROM_BASE)) {
      if (ins.op !== 0x05) continue;
      const segments = textSegments(rom, pack, ins);
      if (segments.length && segments[0].controls.length) { found = { ins, segment: segments[0] }; break; }
    }
    if (found) break;
  }
  check('找得到带控制码的正文', !!found,
    found ? `${found.segment.controls.length} 个控制码` : '没有');
  if (found) {
    const segment = found.segment;
    const controlsBefore = segment.controls
      .map((c) => c.b.map((b) => b.toString(16).padStart(2, '0')).join(' ')).join('|');
    const font = pack.font;
    const chars = [...segment.text];
    const swapAt = [...segment.text].findIndex((ch) => font.encode(ch).length === 2);
    if (swapAt >= 0) {
      chars[swapAt] = sameWidthChar(font, chars[swapAt]);
      const result = commitSegment(pack, segment, chars.join(''));
      check('带控制码的正文也能等长改写', result.ok === true, result.ok ? '' : result.message);
      const controlsAfter = segment.controls
        .map((c) => c.b.map((b) => b.toString(16).padStart(2, '0')).join(' ')).join('|');
      check('控制码的位置与内容原位保留', controlsAfter === controlsBefore,
        `${controlsBefore} → ${controlsAfter}`);
    }
  }

  // 0x13：第一段与第二段都要能被定位。
  const pack2 = freshPack();
  let two = null;
  for (const record of structure.records) {
    const ptr = record.values.ptr;
    if (!ptr) continue;
    for (const ins of scanScript(rom, ptr - ROM_BASE)) {
      if (ins.op !== 0x13) continue;
      const segments = textSegments(rom, pack2, ins);
      if (segments.length === 2) { two = { ins, segments }; break; }
    }
    if (two) break;
  }
  check('0x13 的两段正文都被定位出来', !!two,
    two ? two.segments.map((s) => s.offset).join(' / ') : '没找到两段的 0x13');
  if (two) {
    check('第二段在第一段之后（中间隔着 1 个字节）',
      two.segments[1].offset > two.segments[0].offset,
      `${two.segments[0].offset} → ${two.segments[1].offset}`);
    check('两段的正文都解出了文字',
      two.segments.every((s) => s.text.length > 0),
      two.segments.map((s) => s.text.slice(0, 10)).join(' | '));
  }

  // 0x20：说话人字段（指令的第 2 字节）被读出来。
  const pack3 = freshPack();
  let dialogue = null;
  for (const record of structure.records) {
    const ptr = record.values.ptr;
    if (!ptr) continue;
    for (const ins of scanScript(rom, ptr - ROM_BASE)) {
      if (ins.op !== 0x20) continue;
      dialogue = textSegments(rom, pack3, ins)[0];
      break;
    }
    if (dialogue) break;
  }
  check('0x20 的说话人字段被读出来', dialogue && dialogue.speaker !== null,
    dialogue ? `说话人 #${dialogue.speaker}` : '没找到 0x20');
}

console.log(failures ? `\n${failures} 项未通过` : '\n全部通过');
process.exit(failures ? 1 : 0);
