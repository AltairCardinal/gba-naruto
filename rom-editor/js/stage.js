// 剧情场景的**整幅画面**：240×160，背景 + 立绘 + 对白框 + 名牌 + 正文。
//
// **纯计算，不碰 DOM** —— 返回 RGBA 缓冲。
// 视图（`js/modules/dialogueview.js`）把它贴到画布上；
// 门禁（`rom-editor/tools/verify_dialogue_view.mjs`）拿它与
// **mGBA 真机截图** `notes/evidence/story-scene-l3.png` 逐像素比对。
//
// 每一层的数据来源与考证：
//   * 背景 —— `notes/evidence/story-background-chain-20261022.md`
//     （剧情底图，240×80 在上半屏；`BG0VOFS=-8` 的下移已经算进去了）
//   * 立绘 —— `notes/evidence/portrait-render-chain-20261022.md`
//     （消息框立绘，80×80，槽 0 在 x=16、槽 1 在 x=144）
//   * 对白框 —— 几何与配色从真机画面量出来（框的**边框花纹**是 BG3 的图块，
//     仓库还没定位到那组图块 ⇒ 这里只画等效的框，花纹对不上）
//   * 名牌与正文 —— `notes/evidence/dialogue-font-render-20261022.md`
//     （用 ROM 里的**原字形**：8 宽 × 16 高、每像素 2 bit）
//
// 已知与真机画面**对不上**的两处（不是 bug，是仓库还没查清的地方）：
//   1. 左边那个金发人物 —— 它**不是**消息框立绘（脚本在那一帧前已用 `0x11` 清了槽 0），
//      是过场人物精灵，**复用了同一份图块但有自己的调色板**，来源未闭合；
//   2. 对白框的边框花纹与左右装饰 —— BG3 的图块图形，仓库还没定位。

import { renderSceneBackground } from './maprender.js';
import { paintPortrait, portraitSlots } from './portraits.js';
import {
  renderText, renderDialogueBox, NAME_COLORS, NAME_X0, NAME_Y0,
} from './dialoguefont.js';

/** 屏幕尺寸。 */
export const STAGE_WIDTH = 240;
export const STAGE_HEIGHT = 160;

/** 把一张 RGBA 图贴到目标缓冲上（跳过透明像素）。 */
function blit(target, width, height, image, x0, y0) {
  if (!image) return;
  for (let y = 0; y < image.height; y++) {
    for (let x = 0; x < image.width; x++) {
      const from = (y * image.width + x) * 4;
      if (!image.pixels[from + 3]) continue;
      const tx = x0 + x;
      const ty = y0 + y;
      if (tx < 0 || tx >= width || ty < 0 || ty >= height) continue;
      const to = (ty * width + tx) * 4;
      target[to] = image.pixels[from];
      target[to + 1] = image.pixels[from + 1];
      target[to + 2] = image.pixels[from + 2];
      target[to + 3] = 255;
    }
  }
}

/**
 * 画出一句话对应的整幅画面。
 *
 * @param {Uint8Array} rom
 * @param {object} line  `buildDialogueModel` 给的那一句
 * @returns {{width:number, height:number, pixels:Uint8ClampedArray}}
 */
export function renderStage(rom, line) {
  const width = STAGE_WIDTH;
  const height = STAGE_HEIGHT;
  const pixels = new Uint8ClampedArray(width * height * 4);
  if (!rom || !line) return { width, height, pixels };

  // 1. 背景
  if (line.backgroundId !== null && line.backgroundId !== undefined) {
    blit(pixels, width, height, renderSceneBackground(rom, line.backgroundId), 0, 0);
  }
  // 2. 立绘
  for (const slot of portraitSlots(line)) {
    blit(pixels, width, height, paintPortrait(rom, slot.id, slot.expr), slot.x, slot.y);
  }
  // 3. 对白框
  blit(pixels, width, height, renderDialogueBox(width, height), 0, 0);
  // 4. 说话人名牌（同一套字形，换一组颜色）
  if (line.speakerCodes && line.speakerCodes.length) {
    const nameTokens = line.speakerCodes.map((code) => ({ k: 't', c: code }));
    blit(pixels, width, height, renderText(rom, nameTokens, {
      width, height, x: NAME_X0, y: NAME_Y0, colors: NAME_COLORS, pitch: 8,
    }), 0, 0);
  }
  // 5. 正文
  const tokens = [];
  for (const segment of line.segments || []) {
    for (const token of segment.tokens) tokens.push(token);
  }
  blit(pixels, width, height, renderText(rom, tokens, { width, height }), 0, 0);

  return { width, height, pixels };
}
