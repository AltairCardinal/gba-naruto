// 剧情脚本里的对白：文本段的定位、编码、等长校验与提交。
//
// 剧情脚本的正文是**内联在字节流里**的（不是指针），而脚本里的分支目标是
// **绝对 ROM 地址**。所以改对白只有一条安全的路：**原地等长改写** ——
// 新文本编码后的字节数必须与原来**完全一样**；改长改短都会让后面的指令
// 移位，脚本里的分支全部失效。这不是权宜之计，是硬约束。
//
// 写回走**显式补丁**（与「原始字节」模块同一套）：构建时按「原字节必须
// 匹配」写回，撤销时把 after_hex 恢复回去。
//
// 控制码 0x01 / 0x02 带着换行 / 分页的排版含义，所以正文按 **token 流**
// 处理（`rom-editor/js/textcodec.js` 是 `tools/text_codec.py` 的 JS 版）：
// 写回时控制码按原位保留，位置数也要对得上。

import { bytesToHex, hexToBytes } from './bytes.js';
import { encodeTokens, mergeTokens } from './textcodec.js';
import { instructionTextRuns } from './storyvm.js';

/** 换行在输入框里的样子（ROM 里是 0x0A 码位）。 */
export const NEWLINE_MARK = '↵';

/** 控制码宽度：0x01 占 2 字节，0x02 占 3 字节。 */
const CONTROL_WIDTH = { 1: 2, 2: 3 };

/** 两段字节是否逐字节相同。 */
function sameBytes(a, b) {
  if (a.length !== b.length) return false;
  for (let i = 0; i < a.length; i++) if (a[i] !== b[i]) return false;
  return true;
}

/**
 * 逐字节扫描一段正文，产出 token 流。
 *
 * 分段规则与 `storyvm.js::textEnd` **完全一致**（0x00 结束、0x01 占 2 字节、
 * 0x02 占 3 字节、0x80..0x9F 是双字节字形码），所以扫出来的 token 数与
 * 指令长度永远对得上。
 *
 * @param {Uint8Array} bytes  正文（不含结尾的 NUL）
 * @returns {Array<{k:'t',c:number}|{k:'c',b:number[]}>}
 */
export function scanRun(bytes) {
  const tokens = [];
  let p = 0;
  while (p < bytes.length) {
    const b = bytes[p];
    if (b === 0) break;
    if (b === 1 || b === 2) {
      const width = CONTROL_WIDTH[b];
      const part = [];
      for (let i = 0; i < width && p + i < bytes.length; i++) part.push(bytes[p + i]);
      tokens.push({ k: 'c', b: part });
      p += part.length;
      continue;
    }
    if (b >= 0x80 && b <= 0x9f) {
      if (p + 1 >= bytes.length) {
        // 落单的高位字节：原样记成单字节码，别把它当字形码吃掉后半段。
        tokens.push({ k: 't', c: b });
        p += 1;
        continue;
      }
      tokens.push({ k: 't', c: (b << 8) | bytes[p + 1] });
      p += 2;
      continue;
    }
    tokens.push({ k: 't', c: b });
    p += 1;
  }
  return tokens;
}

/**
 * 某段字节的**当前**内容：把已经记下的补丁算进去。
 *
 * 脚本正文不在任何结构表 / 文本表的写回范围内，改动只以补丁的形式存在，
 * 所以界面必须自己把补丁叠上去看，否则改完再切回来就变回原文了。
 * 与 `js/modules/raw.js` 的 `currentBytes` 同一套做法。
 */
export function currentBytes(pack, rom, offset, length) {
  const out = new Uint8Array(length);
  out.set(rom.subarray(offset, offset + length));
  for (const patch of (pack && pack.patches) || []) {
    const after = hexToBytes(patch.after_hex || '');
    for (let i = 0; i < after.length; i++) {
      const at = patch.offset + i;
      if (at >= offset && at < offset + length) out[at - offset] = after[i];
    }
  }
  return out;
}

/**
 * 有一条补丁**盖住**这段字节、但又不正好等于这段字节吗？
 *
 * 有的话就别动它：写回会覆盖那条补丁的内容，两处改动会互相打架。
 * 正好等于这段字节的是「上一次改这段留下的补丁」，可以继续改。
 */
export function conflictingPatch(pack, offset, length) {
  for (const patch of (pack && pack.patches) || []) {
    const after = hexToBytes(patch.after_hex || '');
    if (!after.length) continue;
    const start = patch.offset;
    const end = patch.offset + after.length;
    if (start === offset && end === offset + length) continue;
    if (offset < end && start < offset + length) return patch;
  }
  return null;
}

/**
 * 文本段的显示文本：换行显示成 ↵，控制码不占正文位置。
 *
 * 控制码没有字形，所以它们不出现在输入框里（界面另有分段条标出位置），
 * 但写回时会按原位保留。
 */
export function displayText(tokens, font) {
  let out = '';
  for (const token of tokens) {
    if (token.k === 'c') continue;
    const c = token.c;
    if (c === 10) { out += NEWLINE_MARK; continue; }
    if (c === 0x8140) { out += '　'; continue; }
    if (c >= 32 && c < 127) { out += String.fromCharCode(c); continue; }
    const ch = font.codeToChar.get(c);
    out += ch === undefined ? `{字${c.toString(16).toUpperCase().padStart(4, '0')}}` : ch;
  }
  return out;
}

/** 这段正文里有多少个字形码是字库解不出来的。 */
function undecodedCount(tokens, font) {
  let n = 0;
  for (const token of tokens) {
    if (token.k === 'c') continue;
    const c = token.c;
    if (c === 10 || c === 0x8140) continue;
    if (c >= 32 && c < 127) continue;
    if (!font.codeToChar.has(c)) n += 1;
  }
  return n;
}

/**
 * 一条指令里的文本段。
 *
 * 每个段带：文件偏移、正文字节数（= 容量）、当前字节、token 流、显示文本、
 * 控制码列表，以及「为什么不能改」（有的话）。
 *
 * @param {Uint8Array} rom
 * @param {ContentPack} pack
 * @param {{offset:number, op:number}} instruction
 */
export function textSegments(rom, pack, instruction) {
  const runs = instructionTextRuns(rom, instruction);
  const font = pack.font;
  const out = [];
  for (let i = 0; i < runs.length; i++) {
    const run = runs[i];
    const bytes = currentBytes(pack, rom, run.offset, run.length);
    const tokens = scanRun(bytes);
    const controls = tokens.filter((token) => token.k === 'c');
    const undecoded = undecodedCount(tokens, font);
    const conflict = conflictingPatch(pack, run.offset, run.length);
    let problem = null;
    if (conflict) {
      problem = `这段字节已经被另一条补丁盖住（0x${conflict.offset.toString(16).toUpperCase()}），` +
        '先在「原始字节」里撤销它再改。';
    } else if (undecoded > 0) {
      problem = `这段正文里有 ${undecoded} 个字库解不出来的字形码，改写会丢掉它们。`;
    } else if (!sameBytes(encodeTokens(tokens), bytes)) {
      problem = '这段正文现在不是合法的文本段（可能已经被「原始字节」改过），不能改写。';
    }
    out.push({
      index: i,
      kind: run.kind,
      offset: run.offset,
      length: run.length,
      capacity: run.length,
      bytes,
      tokens,
      controls,
      text: displayText(tokens, font),
      speaker: run.speaker === undefined ? null : run.speaker,
      problem,
    });
  }
  return out;
}

/**
 * 把文本编码成 token 流。
 *
 * 规则与 `tools/text_codec.py::encode_tokens`（→ `tools/konoha_font.py::encode_tokens`）
 * **同一套**：码位 10 是换行、ASCII 32..126 是单字节、其余是双字节字形码。
 * 字库（`pack.font`）只负责「字 → 码位」；ASCII 不在字库里，但 ROM 的字体有，
 * 所以这里按码位直接写。
 *
 * 字库里没有、又不是 ASCII 的字会被**跳过并报出来**（绝不悄悄丢掉）。
 *
 * @param {string} text
 * @param {FontCodec} font
 * @returns {{tokens: Array, missing: string[]}}
 */
export function encodeText(text, font) {
  const tokens = [];
  const missing = [];
  for (const ch of String(text === null || text === undefined ? '' : text)) {
    if (ch === '\n') {
      tokens.push({ k: 't', c: 10 });
      continue;
    }
    const code = ch.charCodeAt(0);
    if (code >= 32 && code < 127) {
      tokens.push({ k: 't', c: code });
      continue;
    }
    const fontCode = font.charToCode.get(ch);
    if (fontCode === undefined) {
      missing.push(ch);
      continue;
    }
    tokens.push({ k: 't', c: fontCode });
  }
  return { tokens, missing };
}

/**
 * 算出「这段还能改几个字节」。
 *
 * 预算与**写回路径同源**：先把新文本编码成 token 流，再按原位保留控制码，
 * 最后算字节数。控制码的字节是原样搬过去的，所以 `used === capacity`
 * 等价于「新正文的字节数与原正文完全一样」。
 */
export function segmentBudget(segment, text, font) {
  const plain = String(text === null || text === undefined ? '' : text)
    .split(NEWLINE_MARK).join('\n');
  const encoded = encodeText(plain, font);
  const merged = mergeTokens(segment.tokens, encoded.tokens);
  const used = encodeTokens(merged).length;
  return {
    used,
    capacity: segment.capacity,
    over: used > segment.capacity,
    under: used < segment.capacity,
    missing: encoded.missing,
    ok: used === segment.capacity && !encoded.missing.length,
  };
}

/**
 * 把新文本写回这一段。
 *
 * 只有**等长**才写：长度对不上当场拒绝并回滚，绝不默默截断、也不静默不保存。
 * 写回走显式补丁（`pack.setBytesAt`），所以构建时按「原字节必须匹配」
 * 校验，撤销时也能把 after_hex 恢复回去。
 *
 * @param {ContentPack} pack
 * @param {object} segment   `textSegments` 给出的一段
 * @param {string} text      输入框里的新文本
 * @returns {{ok:boolean, message?:string, bytes?:number, capacity?:number, patch?:object, unchanged?:boolean}}
 */
export function commitSegment(pack, segment, text) {
  const font = pack.font;
  if (segment.problem) {
    return { ok: false, reason: 'problem', message: segment.problem };
  }
  const budget = segmentBudget(segment, text, font);
  if (budget.missing.length) {
    return {
      ok: false,
      reason: 'missing',
      message: `字库里没有这些字：${budget.missing.join(' ')}`,
    };
  }
  if (budget.used !== segment.capacity) {
    const diff = budget.used - segment.capacity;
    return {
      ok: false,
      reason: 'length',
      bytes: budget.used,
      capacity: segment.capacity,
      message: (diff > 0
        ? `等长才能改：现在要 ${budget.used} 字节，比原来的 ${segment.capacity} 字节多 ${diff} 个。`
        : `等长才能改：现在要 ${budget.used} 字节，比原来的 ${segment.capacity} 字节少 ${-diff} 个。`) +
        '后面的指令会移位，分支目标全部失效 —— 请改成同样长的文字。',
    };
  }
  const plain = String(text === null || text === undefined ? '' : text)
    .split(NEWLINE_MARK).join('\n');
  const merged = mergeTokens(segment.tokens, encodeText(plain, font).tokens);
  const bytes = encodeTokens(merged);
  if (sameBytes(bytes, segment.bytes)) {
    return { ok: true, unchanged: true };
  }
  const patch = pack.setBytesAt(
    segment.offset,
    bytesToHex(segment.bytes),
    bytesToHex(bytes),
    `剧情对白 0x${segment.offset.toString(16).toUpperCase()}`
  );
  // 让界面立刻反映新值（这一格不会整页重画）。
  segment.bytes = bytes;
  segment.tokens = merged;
  segment.controls = merged.filter((token) => token.k === 'c');
  segment.text = displayText(merged, font);
  return { ok: true, patch, bytes };
}
