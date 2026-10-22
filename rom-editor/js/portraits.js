// 立绘（头像）的读取与渲染。
//
// **纯计算，不碰 DOM**：返回 RGBA 缓冲，视图（`js/modules/dialogueview.js`）自己
// 往画布上贴。
//
// 事实依据：`notes/evidence/portrait-render-chain-20261022.md`
// （本仓库自己的考证，逐像素验证过）。
//
// ## 链路
//
// 剧情脚本 `0x02 / 0x04 <槽> <头像ID> <表情>` 选出一个立绘：
//
//   1. 表 `0x085A4DEC`（文件偏移 `0x5A4DEC`）的 8 字节项
//      `id*40 + expr*8`：**+0 = LZ77(0x10) 压缩的 8bpp 图形**、**+4 = 64 色 BGR555 调色板**（128 字节）。
//      图形解压后**恰好 6400 字节 = 100 张 8×8 图块**。
//   2. 装配：按**拼块表 `0x084643C0`**（6 条 × 20 字节）把 100 张图块
//      **按拼块表的顺序连续消费**，拼成 **80×80**。
//      ⚠️ 拼块项里的 `start_tile` **不是**缓冲里的图块号（那是另一片 136 槽的图块池）——
//      按 `start_tile` 取图块会得到完全错乱的画面。
//   3. 上色：像素值直接查那张 64 色调色板（`param<<4` 的平移在配色上是恒等变换），
//      **索引 0 = 透明**。
//   4. 位置：80×80 贴在 `(obj+0x30, 8)` —— 槽 0 → **x=16**、槽 1 → **x=144**，y 恒为 8。
//
// 依据「id=44（伊鲁卡）、expr=0」渲染出来的 80×80，与 mGBA 真机画面
// `notes/evidence/story-scene-l3.png` 的 (144, 8) 区域
// **4543/4543 不透明像素逐字节全等**。

import { lz77Decompress } from './maprender.js';

/** 头像表：ROM 0x085A4DEC ⇒ 文件偏移 0x5A4DEC。 */
export const PORTRAIT_TABLE_OFFSET = 0x5a4dec;
/** 行步长（字节）：id × 40。 */
export const PORTRAIT_ROW_STRIDE = 40;
/** 行内步长（字节）：expr × 8。 */
export const PORTRAIT_ENTRY_STRIDE = 8;
/** 拼块表：ROM 0x084643C0 ⇒ 文件偏移 0x4643C0，6 条 × 20 字节。 */
export const PORTRAIT_PIECES_OFFSET = 0x4643c0;
export const PORTRAIT_PIECE_COUNT = 6;
export const PORTRAIT_PIECE_STRIDE = 20;
/** 解压后的图像字节数（100 张 8bpp 图块 = 80×80）。 */
export const PORTRAIT_GFX_BYTES = 6400;
/** 调色板字节数（64 条 BGR555）。 */
export const PORTRAIT_PALETTE_BYTES = 128;
/** 图像宽高（像素）。 */
export const PORTRAIT_W = 80;
export const PORTRAIT_H = 80;
/** 有效头像 id 的上限（行 63 的指针是垃圾）。 */
export const PORTRAIT_MAX_ID = 62;
/** 画面上最多同时显示两个立绘（VM 只有槽 0 / 槽 1）。 */
export const PORTRAIT_SLOT_COUNT = 2;

/**
 * 立绘在画面上的位置。
 *
 * 槽 0 → x=16、槽 1 → x=144，y 恒为 8（**实测**：真机画面里两块 80×80 盒不重叠）。
 * 这个 x 是消息框对象的 `obj+0x30` 位置码（0x10 / 0x90）决定的。
 */
export const PORTRAIT_SLOTS = [
  { x: 16, y: 8 },
  { x: 144, y: 8 },
];

function readU16(rom, at) {
  return rom[at] | (rom[at + 1] << 8);
}
function readU32(rom, at) {
  return (rom[at] | (rom[at + 1] << 8) | (rom[at + 2] << 16) | (rom[at + 3] << 24)) >>> 0;
}

/** BGR555 → RGB888（5 位 → 8 位按 `(v<<3)|(v>>2)` 展开，与 mGBA 一致）。 */
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

/**
 * 表里第 (id, expr) 格的指针。
 *
 * @returns {{gfxPtr:number, palettePtr:number}|null}
 */
export function portraitEntry(rom, id, expr = 0) {
  if (!rom) return null;
  if (id === null || id === undefined) return null;
  if (id < 1 || id > PORTRAIT_MAX_ID) return null;      // 行 0 空槽、行 63 垃圾
  const at = PORTRAIT_TABLE_OFFSET + id * PORTRAIT_ROW_STRIDE
    + expr * PORTRAIT_ENTRY_STRIDE;
  if (at + 8 > rom.length) return null;
  const gfxPtr = readU32(rom, at);
  const palettePtr = readU32(rom, at + 4);
  if (!gfxPtr || !palettePtr) return null;
  if (gfxPtr - 0x08000000 >= rom.length) return null;
  if (palettePtr - 0x08000000 >= rom.length) return null;
  return { gfxPtr, palettePtr };
}

/** 拼块表的一条：x / y / 宽 / 高（像素）。 */
function portraitPiece(rom, index) {
  const at = PORTRAIT_PIECES_OFFSET + index * PORTRAIT_PIECE_STRIDE;
  return {
    x: readU16(rom, at + 4),
    y: readU16(rom, at + 6),
    w: readU16(rom, at + 8),
    h: readU16(rom, at + 10),
  };
}

/**
 * 把一个立绘渲染成 RGBA 缓冲（80×80）。
 *
 * @param {Uint8Array} rom
 * @param {number} id      头像 id（1..62）
 * @param {number} expr    表情（行内格号，0..4）
 * @returns {{width:number, height:number, pixels:Uint8ClampedArray}|null}
 */
export function paintPortrait(rom, id, expr = 0) {
  if (!rom) return null;
  const entry = portraitEntry(rom, id, expr);
  if (!entry) return null;

  const buffer = lz77Decompress(rom, entry.gfxPtr - 0x08000000);
  if (!buffer || buffer.length < PORTRAIT_GFX_BYTES) return null;

  const paletteAt = entry.palettePtr - 0x08000000;
  if (paletteAt < 0 || paletteAt + PORTRAIT_PALETTE_BYTES > rom.length) return null;
  const colors = [];
  for (let i = 0; i < 64; i++) {
    colors.push(bgr555ToRgb(readU16(rom, paletteAt + i * 2)));
  }

  // --- 按拼块表把 100 张图块装配成 80×80 ---------------------------------
  const index = new Uint8Array(PORTRAIT_W * PORTRAIT_H);   // 0 = 透明
  let tile = 0;                                              // 缓冲图块游标
  for (let j = 0; j < PORTRAIT_PIECE_COUNT; j++) {
    const piece = portraitPiece(rom, j);
    const tw = piece.w >> 3;
    const th = piece.h >> 3;
    for (let ty = 0; ty < th; ty++) {
      for (let tx = 0; tx < tw; tx++) {
        const source = (tile + ty * tw + tx) * 64;             // 8bpp 图块起点
        const dx = (piece.x >> 3) + tx;
        const dy = (piece.y >> 3) + ty;
        for (let yy = 0; yy < 8; yy++) {
          for (let xx = 0; xx < 8; xx++) {
            const px = dx * 8 + xx;
            const py = dy * 8 + yy;
            if (px >= PORTRAIT_W || py >= PORTRAIT_H) continue;
            index[py * PORTRAIT_W + px] = buffer[source + yy * 8 + xx];
          }
        }
      }
    }
    tile += tw * th;                                          // 连续消费
  }

  // --- 上色 ---------------------------------------------------------------
  const pixels = new Uint8ClampedArray(PORTRAIT_W * PORTRAIT_H * 4);
  for (let i = 0; i < PORTRAIT_W * PORTRAIT_H; i++) {
    const value = index[i];
    if (!value) continue;                                     // 索引 0 = 透明
    const rgb = colors[value & 0x3f] || [0, 0, 0];
    const at = i * 4;
    pixels[at] = rgb[0];
    pixels[at + 1] = rgb[1];
    pixels[at + 2] = rgb[2];
    pixels[at + 3] = 255;
  }
  return { width: PORTRAIT_W, height: PORTRAIT_H, pixels };
}

/**
 * 这一句该画哪几个立绘、画在哪。
 *
 * `line.portraits` = [{slot, id, expr}]（模型按 `0x02 / 0x04 / 0x11` 维护）。
 */
export function portraitSlots(line) {
  const slots = [];
  if (!line || !line.portraits) return slots;
  for (const portrait of line.portraits) {
    if (!portrait || portrait.id === null || portrait.id === undefined) continue;
    if (!portrait.id) continue;                               // 0 = 没有立绘
    const place = PORTRAIT_SLOTS[portrait.slot] || PORTRAIT_SLOTS[0];
    slots.push({
      id: portrait.id,
      expr: portrait.expr || 0,
      x: place.x,
      y: place.y,
    });
  }
  return slots;
}
