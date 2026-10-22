// 战斗地图的纯函数模块：解码素材、合成像素、坐标换算。
//
// **这个文件不碰 DOM。** 无头验收脚本（rom-editor/tools/verify_battle_map.mjs）
// 直接 import 它做断言 —— 画布在无头环境里没有 2D 上下文，所以像素合成必须是
// 纯函数（返回 RGBA 缓冲），只有最后一步才 putImageData。
//
// 依据：
//   * notes/specs/battle-map-editor.md §2（事实核对）/ §5（纯函数契约）
//   * notes/evidence/battle-map-render-facts-20261022.md（实测）

/**
 * 1 格 = 32 × 16 像素。
 *
 * 三条互相独立的证据（规格 §2.3）：通行值块长度 == 格数 × 2、图层块长度 ==
 * 格数 × 4、原生代码 0x08068FB4 写 `raw宽 >> 2` / `raw高 >> 1`；
 * 加上「每张图按 32×16 换算都 ≥ GBA 屏幕 240×160」这条最硬的旁证。
 */
export const CELL_PX_W = 32;
export const CELL_PX_H = 16;

/** 地图表：47 条 × 32 字节（文件偏移）。 */
export const MAP_TABLE_OFFSET = 0x53d910;

/** 剧情底图表：36 条 × 16 字节（文件偏移）。 */
export const BACKGROUND_TABLE_OFFSET = 0x59903c;

/** ROM 里的指针是 0x08xxxxxx，文件偏移 = 指针 − 这个基址。 */
export const ROM_BASE = 0x08000000;

// ---------------------------------------------------------------------------
// 坐标换算（规格 §5）
// ---------------------------------------------------------------------------

/**
 * 像素 → 格。
 *
 * @param {number} px    地图像素 X
 * @param {number} py    地图像素 Y
 * @param {number} cellW 格宽（越界判定用）
 * @param {number} cellH 格高（越界判定用）
 * @returns {?{x: number, y: number}} 越界返回 null
 */
export function cellFromPixel(px, py, cellW, cellH) {
  const x = Math.floor(px / CELL_PX_W);
  const y = Math.floor(py / CELL_PX_H);
  if (x < 0 || y < 0 || x >= cellW || y >= cellH) return null;
  return { x, y };
}

/**
 * 格 → 像素（格的左上角）。
 */
export function pixelFromCell(x, y) {
  return { px: x * CELL_PX_W, py: y * CELL_PX_H };
}

/**
 * 一格在像素平面上的矩形。
 */
export function cellRect(x, y) {
  return { x: x * CELL_PX_W, y: y * CELL_PX_H, w: CELL_PX_W, h: CELL_PX_H };
}

/**
 * 屏幕坐标 → 格（**带显示缩放**）。
 *
 * `rect` 是画布元素的 getBoundingClientRect()；显示缩放 = rect.width ÷ 图宽。
 * 不能假设 1:1 —— 画布可能被缩放档放大过。
 *
 * @returns {?{x: number, y: number}} 越界返回 null
 */
export function cellFromClientPoint(clientX, clientY, rect, cellW, cellH) {
  if (!rect) return null;
  const mapWidth = cellW * CELL_PX_W;
  const scale = mapWidth ? rect.width / mapWidth : 1;
  if (!scale || !Number.isFinite(scale)) return null;
  const px = (clientX - rect.left) / scale;
  const py = (clientY - rect.top) / scale;
  return cellFromPixel(px, py, cellW, cellH);
}

// ---------------------------------------------------------------------------
// 素材解码
// ---------------------------------------------------------------------------

/**
 * 内容包里的 `map_assets` 段（由主代理在 pack.js 里挂上，或本模块自己拉一次）。
 *
 * 结构见规格 §6.3：
 *   { format, file, sha256, raw_size, packed_size, maps: { "<关卡>": {...} } }
 */
let assetIndex = null;

/** 登记内容包里的 map_assets 段（`maps` 的键是关卡 id 的字符串）。 */
export function setMapAssetIndex(meta) {
  assetIndex = meta && meta.maps ? meta : null;
  return assetIndex;
}

/** 当前登记的 map_assets 段（没有登记就是 null）。 */
export function mapAssetIndex() {
  return assetIndex;
}

function mapMeta(index) {
  if (index && typeof index === 'object') return index;
  if (!assetIndex || !assetIndex.maps) return null;
  return assetIndex.maps[String(index)] || null;
}

/**
 * 把素材二进制解成一张地图的素材。
 *
 * @param {Uint8Array|ArrayBuffer} bytes 素材文件（一张图 = 六个块紧挨着）
 * @param {number|object} index 关卡 id；也可以直接给 map_assets.maps 里的那条元数据
 * @returns {?object} { cellW, cellH, pxW, pxH, gfx, palette, layer0, layer1, metatiles, terrain }
 */
export function decodeMapAsset(bytes, index) {
  const meta = mapMeta(index);
  if (!meta || !bytes) return null;
  const view = toBytes(bytes);
  if (!view) return null;
  const block = (name) => {
    const info = (meta.blocks || {})[name];
    if (!info || !info.length) return new Uint8Array(0);
    const start = info.offset;
    if (start < 0 || start + info.length > view.length) return new Uint8Array(0);
    return view.subarray(start, start + info.length);
  };
  const cellW = meta.cell_w;
  const cellH = meta.cell_h;
  return {
    cellW,
    cellH,
    pxW: meta.px_w !== undefined ? meta.px_w : cellW * CELL_PX_W,
    pxH: meta.px_h !== undefined ? meta.px_h : cellH * CELL_PX_H,
    gfx: block('gfx'),
    palette: block('palette'),
    layer0: block('layer0'),
    layer1: block('layer1'),
    metatiles: block('metatiles'),
    terrain: block('terrain'),
  };
}

/**
 * 从 ROM 现解一张地图的素材（规格 §6.4 留的同构入口）。
 *
 * 素材包里已经有解压好的素材，所以这一条是 P2 路径（素材文件拿不到时的兜底）；
 * 但它必须存在 —— 以后要改成「运行时从 ROM 解」时就不用重写解码器了。
 *
 * @param {Uint8Array} rom  整份 ROM
 * @param {number} stage     关卡 id（= 地图表下标）
 */
export function decodeMapAssetFromRom(rom, stage) {
  if (!rom) return null;
  const base = MAP_TABLE_OFFSET + stage * 32;
  if (base + 32 > rom.length) return null;
  const cellW = readU16(rom, base) >> 2;
  const cellH = readU16(rom, base + 2) >> 1;
  const load = (delta) => {
    const ptr = readU32(rom, base + delta);
    if (!ptr) return new Uint8Array(0);
    if (ptr < ROM_BASE || ptr - ROM_BASE >= rom.length) return new Uint8Array(0);
    return lz77Decompress(rom, ptr - ROM_BASE) || new Uint8Array(0);
  };
  return {
    cellW,
    cellH,
    pxW: cellW * CELL_PX_W,
    pxH: cellH * CELL_PX_H,
    gfx: load(4),
    palette: load(8),
    layer0: load(12),
    layer1: load(16),
    metatiles: load(20),
    terrain: load(24),
  };
}

/**
 * GBA 的 LZ77（type 0x10）解压。
 *
 * 格式（规格 §2.6）：
 *   +0x00 u8 = 0x10
 *   +0x01 u24 解压后长度（小端）
 *   +0x04 数据：每 1 个标志字节管 8 个单元，从高位到低位
 *              标志位 0 = 1 个字面量（1 字节）
 *              标志位 1 = 回溯：2 字节 b0,b1 → 长度 = (b0>>4)+3，
 *                        距离 = ((b0&0xF)<<8)|b1，回溯起点 = 当前位置 − 距离 − 1
 */
export function lz77Decompress(bytes, offset = 0) {
  if (!bytes || offset < 0 || offset + 4 > bytes.length) return null;
  if (bytes[offset] !== 0x10) return null;
  const size = bytes[offset + 1] | (bytes[offset + 2] << 8) | (bytes[offset + 3] << 16);
  const out = new Uint8Array(size);
  let src = offset + 4;
  let dst = 0;
  while (dst < size) {
    if (src >= bytes.length) return null;
    const flags = bytes[src++];
    for (let bit = 7; bit >= 0 && dst < size; bit--) {
      if (flags & (1 << bit)) {
        if (src + 1 >= bytes.length) return null;
        const b0 = bytes[src++];
        const b1 = bytes[src++];
        const length = (b0 >> 4) + 3;
        const distance = (((b0 & 0x0f) << 8) | b1) + 1;
        if (distance > dst) return null;
        let from = dst - distance;
        for (let i = 0; i < length && dst < size; i++) out[dst++] = out[from++];
      } else {
        if (src >= bytes.length) return null;
        out[dst++] = bytes[src++];
      }
    }
  }
  return out;
}

// ---------------------------------------------------------------------------
// 像素合成（规格 §5）
// ---------------------------------------------------------------------------

/**
 * 合成一张地图的整幅像素。
 *
 * @param {object} asset decodeMapAsset / decodeMapAssetFromRom 的结果
 * @param {object} opts  { layer1: false } = 只画图层 0
 * @returns {{width: number, height: number, pixels: Uint8ClampedArray}} RGBA
 */
export function renderMapImage(asset, opts = {}) {
  const cellW = asset.cellW;
  const cellH = asset.cellH;
  const width = cellW * CELL_PX_W;
  const height = cellH * CELL_PX_H;
  const pixels = new Uint8ClampedArray(width * height * 4);
  const layer1 = opts.layer1 === false ? null : asset.layer1;
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      const index = composedIndex(asset, x, y, layer1);
      const at = (y * width + x) * 4;
      if (!index) continue;                 // 像素值 0 = 透明（alpha 0）
      const rgb = paletteColor(asset.palette, index);
      pixels[at] = rgb[0];
      pixels[at + 1] = rgb[1];
      pixels[at + 2] = rgb[2];
      pixels[at + 3] = 255;
    }
  }
  return { width, height, pixels };
}

/**
 * 某个地图像素的颜色（测试用）。
 *
 * @returns {number[]} [r, g, b, a]
 */
export function assetPixelColor(asset, px, py) {
  const layer1 = asset.layer1;
  const index = composedIndex(asset, px, py, layer1);
  if (!index) return [0, 0, 0, 0];
  const rgb = paletteColor(asset.palette, index);
  return [rgb[0], rgb[1], rgb[2], 255];
}

/**
 * 某一格的地形（通行值）。
 *
 * 通行值块每格 1 个 u16，原生只读低字节（第三方编辑器取 `terrain[i*2] & 15`）。
 * 战斗加载器 0x08068FF0 根本不读这一块，所以它**只读不写**（规格 §2.7）。
 */
export function terrainAt(asset, x, y) {
  if (!asset || !asset.terrain || !asset.terrain.length) return 0;
  const at = (y * asset.cellW + x) * 2;
  if (at + 1 >= asset.terrain.length) return 0;
  return asset.terrain[at] & 15;
}

/**
 * 图层 1 覆盖图层 0 之后的调色板下标（0 = 透明）。
 */
function composedIndex(asset, px, py, layer1) {
  const top = layer1 && layer1.length ? sampleLayer(asset, layer1, px, py) : 0;
  if (top) return top;
  return sampleLayer(asset, asset.layer0, px, py);
}

/**
 * 取一个图层的某个像素的调色板下标（0 = 透明）。
 *
 * 图层是一张 u16 的**组合图块索引**矩阵，形状是 格行数 × (格列数 × 2)：
 *   metatile 索引 = u16[ 图层[ (y * 格宽 * 2 + x * 2 + h) * 2 ] ]，h = 左半 / 右半
 * 组合图块 = 2×2 个 8×8 图块（8 字节 = 4 个 u16），所以 1 格 = 32×16 像素。
 */
function sampleLayer(asset, layer, px, py) {
  if (!layer || !layer.length) return 0;
  const cellW = asset.cellW;
  // 这一格里的第几个组合图块（横向 2 个）：格宽 32 像素 = 2 个组合图块
  const cellRow = py >> 4;          // 格高 16 像素 = 1 行组合图块
  const half = (px >> 4) & 1;
  const layerOffset = (cellRow * cellW * 2 + (px >> 5) * 2 + half) * 2;
  const meta = readU16(layer, layerOffset);
  // 组合图块内的 2×2 个 8×8 图块
  const tileRow = (py >> 3) & 1;
  const tileCol = (px >> 3) & 1;
  const entry = readU16(asset.metatiles, meta * 8 + (tileRow * 2 + tileCol) * 2);
  // 图块内的像素坐标（4bpp，低半字节是左像素）
  let col = px & 7;
  let row = py & 7;
  if (entry & 0x400) col = 7 - col;     // bit10 = 水平翻转
  if (entry & 0x800) row = 7 - row;     // bit11 = 垂直翻转
  const tile = entry & 0x3ff;
  const gfx = asset.gfx;
  const at = tile * 32 + row * 4 + (col >> 1);
  if (at < 0 || at >= gfx.length) return 0;
  const byte = gfx[at];
  const value = (col & 1) ? (byte >> 4) : (byte & 0x0f);
  if (!value) return 0;                 // 像素值 0 = 透明
  const bank = entry >>> 12;            // bits 15-12 = 色卡号
  return value + bank * 16;
}

/**
 * 调色板的一个 BGR555 → 8 位 RGB。
 */
function paletteColor(palette, index) {
  const v = readU16(palette, index * 2);
  const r5 = v & 31;
  const g5 = (v >> 5) & 31;
  const b5 = (v >> 10) & 31;
  return [(r5 << 3) | (r5 >> 2), (g5 << 3) | (g5 >> 2), (b5 << 3) | (b5 >> 2)];
}

// ---------------------------------------------------------------------------
// 剧情底图（规格 §2.8 / §4.6）
// ---------------------------------------------------------------------------

/**
 * 底图表里**符合背景记录格式**的 id。
 *
 * 36 条里只有 1..7 / 9..13 符合：它们的第 4 个 u32 是色深标志（0 或 1）；
 * 14..35 那一批的同一个位置是指针（很大的数），是另一种 32 字节调色板形态。
 * 判据取自内容包，不写死编号。
 */
export function backgroundIds(pack) {
  const table = pack && pack.structure ? pack.structure('background_table') : null;
  if (!table) return [];
  const out = [];
  for (const record of table.records || []) {
    const v = record.values || {};
    if (v.bpp_flag !== 0 && v.bpp_flag !== 1) continue;
    if (!v.gfx_ptr || !v.palette_ptr || !v.tilemap_ptr) continue;
    out.push(record.id);
  }
  return out;
}

/**
 * 渲染一张剧情底图（240 × 80）。
 *
 * 底图是**剧情画面上半屏**的那张贴图（240×80 正好是 GBA 屏幕的上半屏），
 * 不是战场贴图 —— 所以它单列一块小面板，绝不叠在战场地图上。
 *
 * 只有 4bpp 的底图能预览：8bpp 的那几张（调色板只有 192 色）预览会失真，
 * 返回 null，由界面显示占位。
 *
 * @returns {?{width: number, height: number, pixels: Uint8ClampedArray}}
 */
export function renderBackgroundImage(rom, id) {
  if (!rom) return null;
  const base = BACKGROUND_TABLE_OFFSET + id * 16;
  if (base + 16 > rom.length) return null;
  const bpp = readU32(rom, base + 12);
  if (bpp !== 0) return null;
  const load = (delta) => {
    const ptr = readU32(rom, base + delta);
    if (!ptr || ptr < ROM_BASE || ptr - ROM_BASE >= rom.length) return null;
    return lz77Decompress(rom, ptr - ROM_BASE);
  };
  const gfx = load(0);
  const palette = load(4);
  const tilemap = load(8);
  if (!gfx || !palette || !tilemap) return null;

  const width = 240;
  const height = 80;
  const pixels = new Uint8ClampedArray(width * height * 4);
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      const entry = readU16(tilemap, ((y >> 3) * 32 + (x >> 3)) * 2);
      let col = x & 7;
      let row = y & 7;
      if (entry & 0x400) col = 7 - col;
      if (entry & 0x800) row = 7 - row;
      const tile = entry & 0x3ff;
      const at = tile * 32 + row * 4 + (col >> 1);
      if (at < 0 || at >= gfx.length) continue;
      const byte = gfx[at];
      const value = (col & 1) ? (byte >> 4) : (byte & 0x0f);
      if (!value) continue;
      const index = value + (entry >>> 12) * 16;
      const rgb = paletteColor(palette, index);
      const at2 = (y * width + x) * 4;
      pixels[at2] = rgb[0];
      pixels[at2 + 1] = rgb[1];
      pixels[at2 + 2] = rgb[2];
      pixels[at2 + 3] = 255;
    }
  }
  return { width, height, pixels };
}

// ---------------------------------------------------------------------------
// 小工具
// ---------------------------------------------------------------------------

function toBytes(bytes) {
  if (!bytes) return null;
  if (bytes instanceof Uint8Array) return bytes;
  if (bytes instanceof ArrayBuffer) return new Uint8Array(bytes);
  if (ArrayBuffer.isView(bytes)) return new Uint8Array(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  return null;
}

function readU16(bytes, offset) {
  if (!bytes || offset < 0 || offset + 2 > bytes.length) return 0;
  return bytes[offset] | (bytes[offset + 1] << 8);
}

function readU32(bytes, offset) {
  if (!bytes || offset < 0 || offset + 4 > bytes.length) return 0;
  return (bytes[offset] | (bytes[offset + 1] << 8) | (bytes[offset + 2] << 16) |
    (bytes[offset + 3] << 24)) >>> 0;
}
