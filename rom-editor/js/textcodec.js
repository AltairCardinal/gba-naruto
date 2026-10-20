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

  /** Byte length the encoded form of `text` will occupy. */
  encodedLength(text) {
    return this.encode(text).length;
  }
}
