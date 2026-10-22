// 对白正文用**游戏原字形**渲染。
//
// 这不是「用系统字体显示解码后的文字」——那只能验证内容对不对，显示不出游戏的样子。
// 这里直接读 ROM 里的字形位图，按游戏的方式画成像素：
//
//   * 汉字字形在 `0x0853D644`（内容包里的 `font_segments`）：
//     **8 宽 × 16 高、每像素 2 bit、每字形 32 字节**（每字节 4 像素、每行 2 字节）。
//     旧笔记记成「8×8 4bpp」是**错的** —— 字节数对，格式不对。
//   * ASCII 字形在 `0x0853D73C` 的段表 → `0x0809CD54` / `0x0809D354`：
//     8×8 2bpp、每字形 16 字节。
//   * 对白调色板在 ROM `0x0809C87E`（16 × u16 LE BGR555），
//     对白用的是颜色 8–11：`0x6BDC`（框底）/ `0x4ED5`（高光）/ `0x35EE` / `0x1D07`（笔画）。
//   * 屏幕上一个汉字占 **8 px 宽 × 16 px 高**，字距 8 px，**1:1 不缩放**。
//
// 依据：`notes/evidence/dialogue-font-render-20261022.md`（含地址证据链与可证伪检验）。
// 那个笔记用本 ROM 的字形渲染场景 54 的第 5 句，与 mGBA 真机画面
// **逐像素相同（2304/2304）**。
//
// **纯计算，不碰 DOM**：返回 RGBA 缓冲，视图自己贴到画布上。

/** 汉字字形段表（文件偏移）。 */
export const FONT_SEGMENTS_OFFSET = 0x53d644;
/** 字形段数（31 段 × 8 字节）。 */
export const FONT_SEGMENT_COUNT = 31;
/** ASCII 字形段表（文件偏移，2 段 × 8 字节）。 */
export const ASCII_SEGMENTS_OFFSET = 0x53d73c;
/**
 * 对白调色板（文件偏移，16 × u16 LE BGR555）。
 *
 * ⚠️ 笔记 `dialogue-font-render-20261022.md` 里写的是 `0x9C87E`，
 * **那是错的**（偏了 7 字节）—— 实测「颜色 8–11」那一段
 * （`0x6BDC / 0x4ED5 / 0x35EE / 0x1D07`）在文件偏移 `0x9C887`，
 * 反推基址 = `0x9C887 − 8×2 = 0x9C877`。这里用实测值。
 */
export const DIALOGUE_PALETTE_OFFSET = 0x9c877;

/** 汉字字格：8 宽 × 16 高。 */
export const CJK_W = 8;
export const CJK_H = 16;
/** 汉字字形字节数（2bpp，16 行 × 2 字节）。 */
export const CJK_BYTES = 32;
/** ASCII 字格：8 宽 × 8 高（画在格子的上半）。 */
export const ASCII_W = 8;
export const ASCII_H = 8;
/** ASCII 字形字节数。 */
export const ASCII_BYTES = 16;

/** 全角空格码：画成空白但照样前进 8 px。 */
export const FULL_WIDTH_SPACE = 0x8140;

/**
 * 正文起点的**屏幕坐标**（像素）。
 *
 * 公式是 `x = ((L + (L & 0x1F)) >> 1) - 1`（格）、`y = [state+0x0a] - 6`，
 * 但 `pitch` 与 `state[0x0a]` 的确切值仓库还没闭合（见那份笔记 §9.2），
 * 所以这里用**真机实测值**：场景 54 的首格在 x=24 px、首行基线 y=120 px。
 * **推定**（只在一场戏上量过），别的场景可能差几像素。
 */
export const TEXT_X0 = 24;
export const TEXT_Y0 = 120;

/** 每行能放几个汉字（自动换行的列数）。 */
export const TEXT_PITCH = 26;

/**
 * 对白框的几何与配色（**从真机画面逐行扫描量出来的**）。
 *
 * 依据 `notes/evidence/story-scene-l3.png`（mGBA 真机，240×160）：
 *
 * | 位置 | 颜色 | 说明 |
 * |---|---|---|
 * | y=97..158 | `#63BD73` / `#6B9C5A` | 框的边框（是 BG3 的一组**图块**，不是纯色矩形） |
 * | y=102 / y=153 | `#E7D663` | 框里的两条黄线 |
 * | y=103..152 | `#E7F7D6` | 框内底色（正文就画在这上面） |
 *
 * ⚠️ 框的边框**是 BG3 的图块图形**（仓库还没定位到那组图块），
 * 所以这里是用**同色系**画出来的等效框：位置与配色对，**花纹不对**。
 * 框内底色 `#E7F7D6` 与正文用的调色板颜色 8（`0x6BDC`）是同一个值。
 */
export const BOX = {
  x0: 4, x1: 239, y0: 97, y1: 158,
  interiorX0: 5, interiorX1: 238,
  interiorY0: 103, interiorY1: 152,
  accentY0: 102, accentY1: 153,
  border: [0x63, 0xbd, 0x73],
  borderAlt: [0x6b, 0x9c, 0x5a],
  accent: [0xe7, 0xd6, 0x63],
  fill: [0xe7, 0xf7, 0xd6],
};

/**
 * 一组字形值 → 颜色的对照表。
 *
 * 正文用游戏对白调色板（颜色 8–11）：
 *   v=1 → `0x4ED5`（浅色高光）、v=2 → `0x35EE`、v=3 → `0x1D07`（深色笔画）。
 * **说话人名牌**是同一套字形，但换了一组颜色（**从真机画面逐像素反推**）：
 *   v=1 → `#BDADDE`、v=3 → `#7321FF`。
 */
export function dialogueColors(rom) {
  const palette = dialoguePalette(rom);
  return { 1: palette[9], 2: palette[10], 3: palette[11] };
}

/** 说话人名牌的配色。 */
export const NAME_COLORS = {
  1: [0xbd, 0xad, 0xde],
  2: [0x9a, 0x67, 0xe2],
  3: [0x73, 0x21, 0xff],
};

/** 名牌文字的起点（真机实测：x=24、y=104，字格 8×16）。 */
export const NAME_X0 = 24;
export const NAME_Y0 = 104;

/**
 * 画一个对白框（不含文字）。
 *
 * @returns {{width:number, height:number, pixels:Uint8ClampedArray}}
 */
export function renderDialogueBox(width = 240, height = 160) {
  const pixels = new Uint8ClampedArray(width * height * 4);
  const put = (x, y, rgb) => {
    if (x < 0 || x >= width || y < 0 || y >= height) return;
    const at = (y * width + x) * 4;
    pixels[at] = rgb[0];
    pixels[at + 1] = rgb[1];
    pixels[at + 2] = rgb[2];
    pixels[at + 3] = 255;
  };
  // 边框（上下各一条）
  for (let x = BOX.x0; x <= BOX.x1; x++) {
    for (let y = BOX.y0; y <= BOX.y1; y++) {
      const inTop = y <= BOX.y0 + 4;
      const inBottom = y >= BOX.y1 - 4;
      if (!inTop && !inBottom) continue;
      put(x, y, ((x + y) & 1) ? BOX.border : BOX.borderAlt);
    }
  }
  // 两条黄线
  for (let x = BOX.interiorX0; x <= BOX.interiorX1; x++) {
    put(x, BOX.accentY0, BOX.accent);
    put(x, BOX.accentY1, BOX.accent);
  }
  // 框内底色
  for (let y = BOX.interiorY0; y <= BOX.interiorY1; y++) {
    for (let x = BOX.interiorX0; x <= BOX.interiorX1; x++) put(x, y, BOX.fill);
  }
  return { width, height, pixels };
}

function readU16(rom, at) {
  return rom[at] | (rom[at + 1] << 8);
}
function readU32(rom, at) {
  return (rom[at] | (rom[at + 1] << 8) | (rom[at + 2] << 16) | (rom[at + 3] << 24)) >>> 0;
}

/** BGR555 → RGB888（5 位 → 8 位按 `(v<<3)|(v>>2)` 展开）。 */
export function bgr555ToRgb(value) {
  const r = value & 0x1f;
  const g = (value >> 5) & 0x1f;
  const b = (value >> 10) & 0x1f;
  return [
    (r << 3) | (r >> 2),
    (g << 3) | (g >> 2),
    (b << 3) | (b >> 2),
  ];
}

/** 对白用的 16 色调色板。 */
export function dialoguePalette(rom) {
  const colors = [];
  for (let i = 0; i < 16; i++) {
    colors.push(bgr555ToRgb(readU16(rom, DIALOGUE_PALETTE_OFFSET + i * 2)));
  }
  return colors;
}

/**
 * 找一个字形码的字形数据。
 *
 * @returns {{offset:number, width:number, height:number, bytes:number}|null}
 */
export function glyphFor(rom, code) {
  if (!rom) return null;
  if (code >= 0x20 && code <= 0x7f) {
    // ASCII：段表第 0 段（0x20 起）。
    return asciiGlyph(rom, code, 0);
  }
  if (code >= 0xa0 && code <= 0xff) {
    return asciiGlyph(rom, code, 1);
  }
  if (code < 0x80) return null;
  // 汉字：在 31 段里找包含这个码的那一段。
  for (let i = 0; i < FONT_SEGMENT_COUNT; i++) {
    const at = FONT_SEGMENTS_OFFSET + i * 8;
    const start = readU16(rom, at);
    const count = rom[at + 2];
    if (!count) continue;
    if (code < start || code >= start + count) continue;
    const glyphBase = readU32(rom, at + 4) - 0x08000000;
    const offset = glyphBase + (code - start) * CJK_BYTES;
    if (offset < 0 || offset + CJK_BYTES > rom.length) return null;
    return { offset, width: CJK_W, height: CJK_H, bytes: CJK_BYTES };
  }
  return null;
}

/** ASCII 段表里的一段。 */
function asciiGlyph(rom, code, segment) {
  const at = ASCII_SEGMENTS_OFFSET + segment * 8;
  const start = rom[at];
  const count = rom[at + 1];
  if (!count || code < start || code >= start + count) return null;
  const base = readU32(rom, at + 4) - 0x08000000;
  const offset = base + (code - start) * ASCII_BYTES;
  if (offset < 0 || offset + ASCII_BYTES > rom.length) return null;
  return { offset, width: ASCII_W, height: ASCII_H, bytes: ASCII_BYTES };
}

/**
 * 把一个字形画到 RGBA 缓冲上。
 *
 * 2bpp：每个字节 4 个像素，**高 2 位在前**（`(byte >> ((col%4)*2)) & 3`）。
 * 像素值 v = 0 是透明；v = 1..3 按 `colors` 查颜色。
 */
function drawGlyph(rom, pixels, width, height, code, x, y, colors) {
  if (code === FULL_WIDTH_SPACE) return CJK_W;      // 全角空格：留白，前进一格
  const glyph = glyphFor(rom, code);
  if (!glyph) return CJK_W;
  for (let row = 0; row < glyph.height; row++) {
    for (let col = 0; col < glyph.width; col++) {
      const byte = rom[glyph.offset + row * 2 + (col >> 2)];
      const v = (byte >> ((col & 3) * 2)) & 3;
      if (!v) continue;
      const rgb = colors[v] || [0, 0, 0];
      const px = x + col;
      const py = y + row;
      if (px < 0 || px >= width || py < 0 || py >= height) continue;
      const at = (py * width + px) * 4;
      pixels[at] = rgb[0];
      pixels[at + 1] = rgb[1];
      pixels[at + 2] = rgb[2];
      pixels[at + 3] = 255;
    }
  }
  return CJK_W;
}

/**
 * 把一段正文渲染成像素。
 *
 * @param {Uint8Array} rom
 * @param {Array<{k:string,c:number}>} tokens  `scripttext.js::scanRun` 的 token 流
 * @param {object} opts { width, height, x, y, pitch, colors }
 * @returns {{width:number, height:number, pixels:Uint8ClampedArray}}
 */
export function renderText(rom, tokens, opts = {}) {
  const width = opts.width || 240;
  const height = opts.height || 160;
  const pixels = new Uint8ClampedArray(width * height * 4);
  const colors = opts.colors || (rom ? dialogueColors(rom) : {});
  if (!rom || !tokens || !tokens.length) {
    return { width, height, pixels };
  }
  const x0 = opts.x === undefined ? TEXT_X0 : opts.x;
  const y0 = opts.y === undefined ? TEXT_Y0 : opts.y;
  const pitch = opts.pitch || TEXT_PITCH;

  let x = x0;
  let y = y0;
  for (const token of tokens) {
    if (token.k !== 't') continue;          // 控制码不进画面
    const code = token.c;
    if (code === 0x0a) {                    // 换行
      x = x0;
      y += CJK_H;
      continue;
    }
    if (code === 0x00) break;
    // 自动换行：到达一行的末格就换到下一行。
    if (x >= x0 + pitch * CJK_W) {
      x = x0;
      y += CJK_H;
    }
    x += drawGlyph(rom, pixels, width, height, code, x, y, colors);
  }
  return { width, height, pixels };
}

/**
 * 把一段正文渲染到**已有的**画布上（叠在背景与立绘之上）。
 *
 * @param {Uint8ClampedArray} target 目标 RGBA 缓冲（就地改）
 * @param {number} width 目标宽
 */
export function drawTextInto(rom, tokens, target, width, opts = {}) {
  const colors = opts.colors || (rom ? dialogueColors(rom) : {});
  if (!rom || !tokens || !tokens.length) return;
  const x0 = opts.x === undefined ? TEXT_X0 : opts.x;
  const y0 = opts.y === undefined ? TEXT_Y0 : opts.y;
  const pitch = opts.pitch || TEXT_PITCH;

  let x = x0;
  let y = y0;
  for (const token of tokens) {
    if (token.k !== 't') continue;
    const code = token.c;
    if (code === 0x0a) { x = x0; y += CJK_H; continue; }
    if (code === 0x00) break;
    if (x >= x0 + pitch * CJK_W) { x = x0; y += CJK_H; }
    x += drawGlyph(rom, target, width, 0x10000, code, x, y, colors);
  }
}
