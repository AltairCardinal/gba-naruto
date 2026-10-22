// 可视化对白编辑器：这一场戏的**纯模型**。
//
// **这个文件不碰 DOM。** 视图在 `js/modules/dialogue.js`，
// 机器验收在 `rom-editor/tools/verify_dialogue_view.mjs`。
//
// 模型要回答三个问题：
//
//  1. 这一场有**哪几句对白**、每句在脚本的哪个位置；
//  2. 每句说出口的时候，**画面上该是什么样**（背景是哪张、谁在说、有没有立绘）；
//  3. 怎么从任意一句**跳到**别的句子、怎么**按顺序播放**。
//
// 事实依据：
//   * `notes/story-vm-opcodes-20261020.md` §3（44 条操作码的语义，**权威**）
//   * `notes/evidence/story-scene-l3-20261020.md`（mGBA 真机画面）
//   * `notes/evidence/story-message-box-20261022.md`（消息框与台词表）
//   * `notes/evidence/portrait-render-chain-20261022.md`（立绘渲染链）
//   * `notes/evidence/story-background-chain-20261022.md`（背景渲染链）
//
// **一条对白 = 一条带文字的指令**（0x01 / 0x05 / 0x20 / 0x13）。
// 列表按**脚本里的字节顺序**排 —— 那是作者读脚本时的自然顺序，
// 也是「快速跳转」要的那个顺序。播放则按同一条顺序推进。

import { ROM_BASE, scanScript } from './storyvm.js';
import { textSegments } from './scripttext.js';

/** GBA 屏幕：240×160。 */
export const STAGE_W = 240;
export const STAGE_H = 160;

/**
 * 剧情底图只占**上半屏**（240×80）——
 * 下半屏是对白框（见 `notes/specs/battle-map-editor.md` 与真机截图）。
 * 所以舞台是 240×160，底图只画上面 80 行。
 */
export const BG_H = 80;

/** 根表 id → 内容包里的根表结构 id。 */
export const ROOT_STRUCTURES = {
  before: 'story_before_root',
  after: 'story_after_root',
  logic: 'story_logic_root',
  events: 'story_events_root',
};

/** 根表的中文名。 */
export const ROOT_LABELS = {
  before: '战前剧情',
  after: '战后剧情',
  logic: '战场事件逻辑',
  events: '战场事件表',
};

/** 带文字的指令。 */
export const TEXT_OPS = new Set([0x01, 0x05, 0x20, 0x13]);

/** 这一场戏的剧本首地址（0 表示没有剧本）。 */
export function scriptPointer(pack, root, scene) {
  const structureId = ROOT_STRUCTURES[root];
  const structure = pack && pack.structure ? pack.structure(structureId) : null;
  const record = structure && structure.records ? structure.records[scene] : null;
  const ptr = record && record.values ? record.values.ptr : 0;
  return ptr ? ptr >>> 0 : 0;
}

/**
 * 这一场用到的底图 id。
 *
 * 链路：`0x1E`（载入地图，地图 id @+1）→ 地图表 `map_table` 的
 * `background_id`（剧情底图 ID）→ 剧情底图表 `background_table`。
 * 地图表在内容包里就是 `map_table`（47 条），字段 `background_id`。
 */
export function backgroundForId(pack, mapId) {
  // id ≥ 50 时不查地图表，直接用 id - 41（见 notes/evidence/story-background-chain-20261022.md §2.3）
  if (mapId === null || mapId === undefined) return null;
  if (mapId >= 50) return mapId - 41;
  if (!pack) return null;
  const map = pack.structure ? pack.structure('map_table') : null;
  const record = map && map.records ? map.records[mapId] : null;
  const id = record && record.values ? record.values.background_id : null;
  return id === null || id === undefined ? null : id;
}

/**
 * 这一场用到的底图 id。
 *
 * 剧情场景的底图**由场景号决定**（调度器 `0x0808F544` 直接调 `0x0808F4D4`），
 * 不是脚本里的 `0x1E` —— 55 个 before 剧本里 `0x1E` 一共只出现 6 次。
 * 脚本里的 `0x1E` 是**中途换底图**，用的是同一个函数。
 *
 * 链路（`0x0808F4D4`）：
 *   id ≤ 49 → 地图表 `map_table` 的 `background_id` 字段（+0x1C）
 *   id ≥ 50 → id − 41
 */
export function backgroundIdFor(pack, id) {
  return backgroundForId(pack, id);
}

/** 说话人名字（说话人名表 `speaker_names`，12 字节一条，内联 2 字节字形码）。 */
export function speakerName(pack, id) {
  if (id === null || id === undefined) return null;
  const table = pack && pack.textTable ? pack.textTable('speaker_names') : null;
  if (!table) return null;
  const record = (table.records || []).find((r) => r.id === id);
  const name = record ? record.text : null;
  return name ? name : null;
}

/** 说话人名表在 ROM 里的位置（文件偏移）：`0x085A57C4`，每条 12 字节。 */
export const SPEAKER_NAME_BASE = 0x5a57c4;
export const SPEAKER_NAME_STRIDE = 12;

/**
 * 说话人名字的**字形码**（名牌要用同一套字形画出来）。
 *
 * 每条 12 字节：前 6 字节是最多 3 个双字节字形码，后面是填充。
 * 依据：`notes/evidence/portrait-render-chain-20261022.md` §1.1 与
 * `notes/evidence/dialogue-font-render-20261022.md`。
 */
export function speakerNameCodes(rom, id) {
  if (!rom || id === null || id === undefined) return null;
  const at = SPEAKER_NAME_BASE + id * SPEAKER_NAME_STRIDE;
  if (at + 6 > rom.length) return null;
  const codes = [];
  for (let i = 0; i < 6; i += 2) {
    const code = (rom[at + i] << 8) | rom[at + i + 1];
    if (!code) break;
    codes.push(code);
  }
  return codes.length ? codes : null;
}

/**
 * 这一场戏的模型。
 *
 * @param {Uint8Array} rom
 * @param {object} pack
 * @param {string} root   before / after / logic / events
 * @param {number} scene  场景号
 */
export function buildDialogueModel(rom, pack, root, scene) {
  const model = {
    scene,
    root,
    rootLabel: ROOT_LABELS[root] || root,
    hasRom: !!rom,
    hasScript: false,
    instructions: [],
    lines: [],
    branches: [],
    counts: { lines: 0, characters: 0, menus: 0, dual: 0, instructions: 0 },
    /** 没有 ROM / 没有剧本时给界面看的一句话。 */
    empty: null,
  };

  const pointer = scriptPointer(pack, root, scene);
  model.pointer = pointer;
  if (!pointer) {
    model.empty = `这一场没有${model.rootLabel}剧本（根表里没有指针）。`;
    return model;
  }
  if (!rom) {
    model.empty = '未载入原版 ROM —— 剧情脚本要反汇编 ROM 字节才画得出来。';
    return model;
  }

  const instructions = scanScript(rom, pointer - ROM_BASE);
  model.instructions = instructions;
  model.hasScript = instructions.length > 0;
  if (!model.hasScript) {
    model.empty = '这一场的剧本扫不出指令。';
    return model;
  }

  // --- 走一遍脚本，维护「画面状态」，每遇到一条带文字的指令就记一句 ---------
  const state = {
    mapId: null,
    // 底图**由场景号决定**（调度器在进 VM 之前就把这一场的底图载好了）
    backgroundId: backgroundForId(pack, scene),
    // 立绘按**槽**存（VM 只有槽 0 / 槽 1 ⇒ 画面上最多两个立绘）
    portraits: [null, null],
    speaker: null,
    speaker2: null,
    waitFrames: null,
  };
  const lines = [];
  const branches = [];

  for (const instruction of instructions) {
    const op = instruction.op;
    const b1 = rom[instruction.offset + 1];
    const b2 = rom[instruction.offset + 2];
    const b3 = rom[instruction.offset + 3];

    if (op === 0x1e) {                     // 载入地图 / 背景
      state.mapId = b1;
      state.backgroundId = backgroundIdFor(pack, b1);
      continue;
    }
    if (op === 0x02 || op === 0x04) {         // 设立绘：<槽> <头像ID> <表情>
      const slot = b1;
      if (slot >= 0 && slot < 2) {
        state.portraits[slot] = { id: b2, expr: b3, slot };
      }
      continue;
    }
    if (op === 0x08) {                     // 只设说话人名字（头像 id）
      state.speaker = b1;
      continue;
    }
    if (op === 0x0e) {                     // 设两个名字（第二个写进 obj+0x0C）
      state.speaker = b1;
      state.speaker2 = b2;
      continue;
    }
    if (op === 0x11) {                     // 清立绘：操作数 = 槽号，0xFF = 两个都清
      if (b1 === 0xff) { state.portraits[0] = null; state.portraits[1] = null; }
      else if (b1 >= 0 && b1 < 2) { state.portraits[b1] = null; }
      continue;
    }
    if (op === 0x0f) {                     // 等待 N 帧
      state.waitFrames = b1;
      continue;
    }
    if (op === 0x07 || op === 0x0b || op === 0x0c || op === 0x15) {
      branches.push({
        op,
        offset: instruction.offset,
        kind: op === 0x07 ? 'unconditional' : 'conditional',
      });
      continue;
    }
    if (!TEXT_OPS.has(op)) continue;

    // --- 一句对白 ---------------------------------------------------------
    const segments = textSegments(rom, pack, instruction);
    const text = segments.map((s) => s.text).join('');
    lines.push({
      index: lines.length,
      op,
      offset: instruction.offset,
      kind: op === 0x05 ? 'menu' : op === 0x13 ? 'dual' : op === 0x20 ? 'dialogue' : 'text',
      speaker: state.speaker,
      speakerName: speakerName(pack, state.speaker),
      speakerCodes: speakerNameCodes(rom, state.speaker),
      portraits: state.portraits.map((p) => (p ? { ...p } : null)),
      mapId: state.mapId,
      backgroundId: state.backgroundId,
      waitFrames: state.waitFrames,
      segments,
      text,
      characters: text.length,
    });
    state.waitFrames = null;
  }

  model.lines = lines;
  model.branches = branches;
  model.counts.lines = lines.length;
  model.counts.menus = lines.filter((l) => l.kind === 'menu').length;
  model.counts.dual = lines.filter((l) => l.kind === 'dual').length;
  model.counts.characters = lines.reduce((n, l) => n + l.characters, 0);
  model.counts.instructions = instructions.length;
  return model;
}

/**
 * 播放的**时间轴**：每一句之间隔多少毫秒。
 *
 * 脚本里的 `0x0F`（等待 N 帧）是**游戏**的等待，不是「这一句显示多久」。
 * 对白框里的字要等玩家按键才翻页，所以这一句的停留时间由**作者**决定，
 * 不是 ROM 定的 —— 界面上给一个可调的间隔，并说明这一点。
 *
 * GBA 一帧 = 1/60 秒。
 */
export const FRAME_MS = 1000 / 60;

/** 播放的默认间隔（毫秒）。 */
export const DEFAULT_STEP_MS = 2200;

/**
 * 播放时的间隔：优先用这一句前面的 `0x0F` 等待帧数（那是作者写在脚本里的
 * 「等这么久」），没有就用默认值。
 *
 * 注意：`0x0F` 等的是**游戏帧**，而这里播放的是「一句话停在屏幕上多久」，
 * 两者语义不同（见上面的说明）。所以默认用可调间隔，
 * 只有在作者显式写了等待时才用它当参考。
 */
export function stepDelayMs(line, defaultMs = DEFAULT_STEP_MS) {
  if (line && line.waitFrames !== null && line.waitFrames !== undefined) {
    return Math.max(300, Math.round(line.waitFrames * FRAME_MS));
  }
  return defaultMs;
}

/**
 * 从任意一句跳到别的句子。
 *
 * 返回目标句的下标；越界就夹到边界。
 * 「快速跳转」用得上：点列表里第 N 句 → 舞台跳到第 N 句。
 */
export function jumpTo(lines, index) {
  if (!lines.length) return -1;
  const n = Number(index);
  if (!Number.isFinite(n)) return 0;
  return Math.max(0, Math.min(lines.length - 1, Math.trunc(n)));
}
