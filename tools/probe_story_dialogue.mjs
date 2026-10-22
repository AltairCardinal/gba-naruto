// 探针：把剧情脚本里的**整幅画面**（背景 + 立绘 + 对白框 + 正文）渲成 PNG，
// 并与 mGBA 真机画面逐像素比对。
//
// 用法：
//   node tools/probe_story_dialogue.mjs 54 5            # 第 54 场 第 5 句
//   node tools/probe_story_dialogue.mjs 54 5 --out build/x.png
//
// 依据：
//   * notes/evidence/story-background-chain-20261022.md（背景）
//   * notes/evidence/portrait-render-chain-20261022.md（立绘）
//   * notes/evidence/dialogue-font-render-20261022.md（正文与对白框配色）
import { readFileSync, writeFileSync } from 'node:fs';
import { gunzipSync, deflateSync } from 'node:zlib';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const repo = join(here, '..');

const { ContentPack } = await import('../rom-editor/js/pack.js');
const { buildDialogueModel } = await import('../rom-editor/js/dialogue.js');
const { renderSceneBackground } = await import('../rom-editor/js/maprender.js');
const { paintPortrait, portraitSlots } = await import('../rom-editor/js/portraits.js');
const { renderText, renderDialogueBox, NAME_COLORS, NAME_X0, NAME_Y0 } =
  await import('../rom-editor/js/dialoguefont.js');

const pack = ContentPack.fromJSON(JSON.parse(
  gunzipSync(readFileSync(join(repo, 'rom-editor', 'content', 'pack.min.json.gz'))).toString('utf8')));
const rom = new Uint8Array(readFileSync(join(repo, 'rom', 'base.gba')));

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
function encodePng(width, height, pixels) {
  const raw = Buffer.alloc((width * 4 + 1) * height);
  for (let y = 0; y < height; y++) {
    raw[y * (width * 4 + 1)] = 0;
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
  ihdr[8] = 8;
  ihdr[9] = 6;
  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    chunk('IHDR', ihdr),
    chunk('IDAT', deflateSync(raw, { level: 9 })),
    chunk('IEND', Buffer.alloc(0)),
  ]);
}

/** 把一张 RGBA 图贴到目标缓冲上（跳过透明像素）。 */
function blit(target, width, image, x0, y0) {
  for (let y = 0; y < image.height; y++) {
    for (let x = 0; x < image.width; x++) {
      const from = (y * image.width + x) * 4;
      if (!image.pixels[from + 3]) continue;
      const tx = x0 + x;
      const ty = y0 + y;
      if (tx < 0 || tx >= width || ty < 0 || ty >= 160) continue;
      const to = (ty * width + tx) * 4;
      target[to] = image.pixels[from];
      target[to + 1] = image.pixels[from + 1];
      target[to + 2] = image.pixels[from + 2];
      target[to + 3] = 255;
    }
  }
}

const args = process.argv.slice(2);
const outIndex = args.indexOf('--out');
const outPath = outIndex >= 0 ? args[outIndex + 1] : null;
const nums = args.filter((a, i) => a !== '--out' && !(outIndex >= 0 && i === outIndex + 1))
  .map(Number).filter((n) => Number.isFinite(n));
const scene = nums[0] || 54;
const lineNo = (nums[1] || 5) - 1;

const model = buildDialogueModel(rom, pack, 'before', scene);
const line = model.lines[lineNo];
if (!line) {
  console.error(`第 ${scene} 场没有第 ${lineNo + 1} 句`);
  process.exit(1);
}
console.log(`第 ${scene} 场 第 ${lineNo + 1} 句：${line.text.replace(/↵/g, '\\n')}`);
console.log(`  底图 ${line.backgroundId}　立绘 ${JSON.stringify(line.portraits)}　说话人 ${line.speakerName}`);

const W = 240;
const H = 160;
const pixels = new Uint8ClampedArray(W * H * 4);

// 1. 背景
if (line.backgroundId !== null && line.backgroundId !== undefined) {
  const background = renderSceneBackground(rom, line.backgroundId);
  if (background) blit(pixels, W, background, 0, 0);
}
// 2. 立绘
for (const slot of portraitSlots(line)) {
  const image = paintPortrait(rom, slot.id, slot.expr);
  if (image) blit(pixels, W, image, slot.x, slot.y);
}
// 3. 对白框
blit(pixels, W, renderDialogueBox(W, H), 0, 0);
// 4. 说话人名牌（同一套字形，换一组颜色）
if (line.speakerCodes && line.speakerCodes.length) {
  const nameTokens = line.speakerCodes.map((code) => ({ k: 't', c: code }));
  blit(pixels, W, renderText(rom, nameTokens, {
    width: W, height: H, x: NAME_X0, y: NAME_Y0, colors: NAME_COLORS, pitch: 8,
  }), 0, 0);
}
// 5. 正文（原字形）
const tokens = [];
for (const segment of line.segments) for (const token of segment.tokens) tokens.push(token);
blit(pixels, W, renderText(rom, tokens, { width: W, height: H }), 0, 0);

const target = outPath || join(repo, 'build', `story-stage-scene${scene}-line${lineNo + 1}.png`);
writeFileSync(target, encodePng(W, H, pixels));
console.log(`写出：${target}`);
