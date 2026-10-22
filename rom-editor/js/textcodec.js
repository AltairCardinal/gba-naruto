// The game's own double-byte font code codec.
//
// The ROM renders Chinese from a baked-in bitmap font; a text byte pair whose
// *lead* byte is 0x80..0x9F is a font code (code = lead*256 + trail), NOT
// Shift-JIS.  See notes/font-encoding.md and notes/evidence/font-reverse-mapping-20261020.md.
//
// The code->character table is carried in the content pack (it was derived from
// the ROM's own font segments plus the character-name table), so the editor can
// decode and re-encode without shipping the ROM around.
//
// Caveat that the pack records honestly: a handful of characters have TWO
// codes in the font.  The decoder is therefore lossless (code -> char) but the
// encoder is not: it always emits the canonical (first) code for a character.
// tools/text_codec.py::encode_tokens is the byte-exact counterpart.

export const CTRL_BYTES = new Set([0x01, 0x02]);

export class FontCodec {
  /**
   * @param {Object<string,string>} codeToChar  "8A8B" -> "的"
   * @param {Object<string,string>} [charToCode] canonical "的" -> "8A8B"
   *
   * `charToCode` is the encoder's table.  It is exported separately because
   * eight characters are spelled by two codes in the ROM's font, and only the
   * base-run spelling is canonical
   * (tools/text_codec.py::build_canonical_reverse_mapping).
   */
  constructor(codeToChar, charToCode) {
    this.codeToChar = new Map();
    this.charToCode = new Map();
    for (const [code, ch] of Object.entries(codeToChar || {})) {
      const value = parseInt(code, 16);
      this.codeToChar.set(value, ch);
    }
    if (charToCode) {
      for (const [ch, code] of Object.entries(charToCode)) {
        this.charToCode.set(ch, parseInt(code, 16));
      }
    } else {
      for (const [code, ch] of [...this.codeToChar.entries()].sort((a, b) => a[0] - b[0])) {
        if (!this.charToCode.has(ch)) this.charToCode.set(ch, code);
      }
    }
  }

  get size() {
    return this.codeToChar.size;
  }

  /** Characters that the font cannot draw (no code at all). */
  missingCharacters(text) {
    const missing = new Set();
    for (const ch of text) {
      if (ch === '\n') continue;
      if (!this.charToCode.has(ch)) missing.add(ch);
    }
    return [...missing];
  }

  /**
   * Decode a byte run into text.  Control bytes are surfaced as \u0001/\u0002
   * so round-tripping keeps them; unknown codes become {字XXXX}.
   */
  decode(bytes) {
    let out = '';
    let i = 0;
    while (i < bytes.length) {
      const b = bytes[i];
      if (CTRL_BYTES.has(b)) {
        out += String.fromCharCode(b);
        i += 1;
        continue;
      }
      if (b >= 0x80 && b <= 0x9f) {
        if (i + 1 >= bytes.length) {
          out += `{字${b.toString(16).toUpperCase().padStart(4, '0')}}`;
          i += 1;
          continue;
        }
        const code = (b << 8) | bytes[i + 1];
        const ch = this.codeToChar.get(code);
        out += ch === undefined
          ? `{字${code.toString(16).toUpperCase().padStart(4, '0')}}`
          : ch;
        i += 2;
        continue;
      }
      if (b === 0x0a) {
        out += '\n';
        i += 1;
        continue;
      }
      if (b === 0) break; // NUL terminator
      out += String.fromCharCode(b);
      i += 1;
    }
    return out;
  }

  /**
   * Encode text back into the game's font codes.
   * Unknown characters are skipped and reported through `onMissing`.
   */
  encode(text, onMissing) {
    const bytes = [];
    for (const ch of text) {
      if (ch === '\n') {
        bytes.push(0x0a);
        continue;
      }
      if (CTRL_BYTES.has(ch.charCodeAt(0))) {
        bytes.push(ch.charCodeAt(0));
        continue;
      }
      const code = this.charToCode.get(ch);
      if (code === undefined) {
        if (onMissing) onMissing(ch);
        continue;
      }
      bytes.push((code >> 8) & 0xff, code & 0xff);
    }
    return new Uint8Array(bytes);
  }

  /** The same text, as a token stream (so control codes can be carried). */
  encodeTokens(text, onMissing) {
    const tokens = [];
    for (const ch of text) {
      if (ch === '\n') {
        tokens.push({ k: 't', c: 10 });
        continue;
      }
      const code = this.charToCode.get(ch);
      if (code === undefined) {
        if (onMissing) onMissing(ch);
        continue;
      }
      tokens.push({ k: 't', c: code });
    }
    return tokens;
  }

  /** Byte length the encoded form of `text` will occupy. */
  encodedLength(text) {
    return this.encode(text).length;
  }
}

/**
 * Scan a byte run into a token stream that **preserves control codes**.
 *
 * Mirrors `tools/konoha_font.py::scan_tokens`:
 *   {k:'t', c}  a font code (2 bytes in the ROM) or an ASCII byte
 *   {k:'c', b}  a control code, exactly as it appears in the ROM
 *
 * Control bytes 0x01/0x02 carry layout meaning (line breaks, page breaks).
 * Anything that writes text back has to work on tokens, never on the decoded
 * string — see notes/font-encoding.md.
 */
export function scanTokens(bytes) {
  const tokens = [];
  let p = 0;
  while (p < bytes.length) {
    const a = bytes[p];
    if (a === 0) break;
    if (a === 1 || a === 2) {
      // A control code takes 2 or 3 bytes.  When the run ends right after the
      // control byte, the remaining payload byte is the string terminator and
      // belongs to the *next* record — so the control code is recorded with
      // only the bytes that are actually here, and the round trip stays
      // byte-exact.  (The repo's scanner runs on the whole ROM and swallows
      // the terminator, which merges two records.)
      const width = a === 1 ? 2 : 3;
      const b = [a];
      for (let i = 1; i < width && p + i < bytes.length; i++) b.push(bytes[p + i]);
      tokens.push({ k: 'c', b });
      p += b.length;
      continue;
    }
    if (a >= 0x80 && a <= 0x9f) {
      if (p + 1 >= bytes.length || bytes[p + 1] === 0) break;
      tokens.push({ k: 't', c: (a << 8) | bytes[p + 1] });
      p += 2;
      continue;
    }
    tokens.push({ k: 't', c: a });
    p += 1;
  }
  return tokens;
}

/**
 * Encode a token stream back into ROM bytes.
 * Mirrors `tools/konoha_font.py::encode_tokens`.
 */
export function encodeTokens(tokens) {
  const out = [];
  for (const token of tokens) {
    if (token.k === 'c') {
      for (const b of token.b) out.push(b & 0xff);
      continue;
    }
    const code = token.c;
    if (code === 10) out.push(0x0a);
    else if (code >= 32 && code < 127) out.push(code);
    else if (code === 0x8140) out.push(0x81, 0x40);
    else out.push((code >> 8) & 0xff, code & 0xff);
  }
  return new Uint8Array(out);
}

/** How many control codes a token stream carries. */
export function countControlCodes(tokens) {
  return tokens.reduce((n, t) => n + (t.k === 'c' ? 1 : 0), 0);
}

/**
 * Replace the text of an existing token stream while **keeping every control
 * code where it was**.
 *
 * The original stream is T0 C1 T1 C2 T2 … Cn-1 Cn Tn.  The new text is split
 * across the same n+1 runs (each run keeps its original length when it can,
 * the last run absorbs the difference), so the control codes stay exactly
 * where the author had them — line breaks and page breaks do not move.
 */
export function mergeTokens(originalTokens, newTextTokens) {
  const runs = [];
  const controls = [];
  let current = [];
  for (const token of originalTokens) {
    if (token.k === 'c') {
      controls.push(token);
      runs.push(current);
      current = [];
    } else {
      current.push(token);
    }
  }
  runs.push(current);

  const out = [];
  let index = 0;
  for (let i = 0; i < runs.length; i++) {
    const wanted = i < runs.length - 1
      ? runs[i].length
      : newTextTokens.length - index;
    for (let j = 0; j < wanted && index < newTextTokens.length; j++) {
      out.push(newTextTokens[index++]);
    }
    if (i < controls.length) out.push(controls[i]);
  }
  while (index < newTextTokens.length) out.push(newTextTokens[index++]);
  return out;
}
