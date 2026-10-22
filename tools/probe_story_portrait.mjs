// 探针：把头像（立绘）从 ROM 里渲成 PNG，好与真机画面逐像素比对。
//
// 用法：
//   node tools/probe_story_portrait.mjs 1 44            # 渲染 id 1 与 id 44
//   node tools/probe_story_portrait.mjs 1 --out build/x.png
//
// 事实依据：notes/evidence/portrait-writeback-20261021.md（表布局与格式）
// 与 notes/evidence/portrait-render-chain-20261022.md（渲染链）。
import { readFileSync, writeFileSync } from 'node:fs';
import { deflateSync } from 'node:zlib';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const repo = join(here, '..');

const { paintPortrait, portraitEntry, PORTRAIT_GFX_BYTES } =
  await import('../rom-editor/js/portraits.js');

const rom = new Uint8Array(readFileSync(join(repo, 'rom', 'base.gba')));

/** RGBA 缓冲 → PNG 字节。 */
function encodePng(width, height, pixels) {
  const raw = Buffer.alloc((width * 4 + 1) * height);
  for (let y = 0; y < height; y++) {
    raw[y * (width * 4 + 1)] = 0;                       // 过滤器：none
    Buffer.from(pixels.buffer, pixels.byteOffset + y * width * 4, width * 4)
      .copy(raw, y * (width * 4 + 1) + 1);
  }
  const chunk = (type, data) => {
    const out = Buffer.alloc(8 + data.length + 4);
    out.writeUInt32BE(data.length, 0);
    out.write(type, 4, 'ascii');
    data.copy(out, 8);
    out.writeUInt32BE(crc32(out.subarray(4, 8 + data.length)) >>> 0, 8 + data.length);
    return out;
  };
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(width, 0);
  ihdr.writeUInt32BE(height, 4);
  ihdr[8] = 8;      // bit depth
  ihdr[9] = 6;      // RGBA
  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    chunk('IHDR', ihdr),
    chunk('IDAT', deflateSync(raw, { level: 9 })),
    chunk('IEND', Buffer.alloc(0)),
  ]);
}

const CRC_TABLE = (() => {
  const table = new Int32Array(256);
  for (let n = 0; n < 256; n++) {
    let c = n;
    for (let k = 0; k < 8; k++) c = (c & 1) ? (0xedb88320 ^ (c >>> 1)) : (c >>> 1);
    table[n] = c;
  }
  return table;
})();
function crc32(buf) {
  let c = 0xffffffff;
  for (let i = 0; i < buf.length; i++) c = CRC_TABLE[(c ^ buf[i]) & 0xff] ^ (c >>> 8);
  return c ^ 0xffffffff;
}

const args = process.argv.slice(2);
const outIndex = args.indexOf('--out');
const outPath = outIndex >= 0 ? args[outIndex + 1] : null;
const ids = args
  .filter((a, i) => a !== '--out' && !(outIndex >= 0 && i === outIndex + 1))
  .map(Number).filter((n) => Number.isFinite(n) && n > 0);
if (!ids.length) ids.push(1, 44);

const images = [];
for (const id of ids) {
  const entry = portraitEntry(rom, id, 0);
  const image = paintPortrait(rom, id, 0);
  let line = `id ${id}: ` + (entry
    ? `gfx=0x${entry.gfxPtr.toString(16).toUpperCase()} pal=0x${entry.palettePtr.toString(16).toUpperCase()}`
    : '（表里没有可用数据）');
  let opaque = 0;
  if (image) {
    for (let i = 3; i < image.pixels.length; i += 4) if (image.pixels[i]) opaque += 1;
    line += `  渲染 ${image.width}×${image.height}，不透明像素 ${opaque} / ${image.width * image.height}`;
  }
  console.log(line);
  if (image) images.push({ id, image });
}

if (images.length) {
  const width = images[0].image.width * images.length;
  const height = images[0].image.height;
  const pixels = new Uint8ClampedArray(width * height * 4);
  images.forEach((item, i) => {
    const at = i * item.image.width * 4;
    pixels.set(item.image.pixels, at);
  });
  const target = outPath || join(repo, 'build', 'story-portrait-probe.png');
  writeFileSync(target, encodePng(width, height, pixels));
  console.log(`写出：${target}`);
}
