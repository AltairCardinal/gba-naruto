// 战斗域的「剧情触发」模型：把「战场事件逻辑」+「战场事件表」这一对剧本
// 切成**触发块**与**剧情段**，配对，算人话摘要。
//
// **纯计算，不碰 DOM** —— 视图在 `js/modules/battle-sections.js`，
// 机器验收在 `rom-editor/tools/verify_battle_story_triggers.mjs`。
//
// 数据事实（notes/specs/battle-story-triggers-20261022.md §1 与
// notes/reviews/battle-story-triggers-review-20261022.md §2 复核过）：
//
//   * logic 剧本 = 一串「条件 → 0x33 压入事件 id」；
//   * events 剧本开头 = 一条连续的 0x32 事件链，每条指向一段对白；
//   * 事件 id 选中链上第 id 段（1 基）。**这是按 ROM 字节推定的**：
//     handler 里 `subs r0,#1`（0x08097D1A）把压入的值减 1 再与链游标比。
//     静态字节证据 + 39/46 关的值集合恰好是 {1..N}，
//     **没有做运行期确认** —— 界面上必须带这个限定词。
//
// 条件指令的跳转语义（审核 M1，**不要写反**）：
//   handler 的形状是「判定结果 == 1 → b 0x08097B20（跳到 u32 目标）；
//   落空 → 继续下一条指令」。
//   ⇒ **u32 目标是「条件命中时跳到哪」，不是「不满足时跳到哪」。**
//   ⇒ 0x34 / 0x36 / 0x38 / 0x39 是「成立才跳」；
//     **0x35 的极性相反**（a 恒为 0 ⇒ 它的「命中」= 复合条件**不成立**）。

import {
  ROM_BASE, BRANCH, COMPARATOR_NAMES, editableOperands, scanScript,
} from './storyvm.js';
import { hexToBytes } from './bytes.js';

/** 0x33：压入事件队列值（一个触发块的结尾）。 */
export const PUSH_OP = 51;
/** 0x32：事件链选择（events 剧本开头的一条链）。 */
export const CHAIN_OP = 50;
/** 0x37：置/清战斗标志（不跳转，是副作用）。 */
export const FLAG_OP = 55;
/** 条件类指令：0x34 / 0x35 / 0x36 / 0x38 / 0x39。 */
export const CONDITION_OPS = new Set([52, 53, 54, 56, 57]);
/** 文本指令：0x01 显示文本、0x20 带说话人的对话。 */
export const TEXT_OPS = new Set([1, 32]);

/** 两张根表的 id 与中文名。 */
export const TRIGGER_ROOTS = [
  { id: 'story_before_root', label: '战前剧情', root: 'before' },
  { id: 'story_after_root', label: '战后剧情', root: 'after' },
  { id: 'story_logic_root', label: '战场事件逻辑', root: 'logic' },
  { id: 'story_events_root', label: '战场事件表', root: 'events' },
];

/** 1 基映射的限定说法（界面各处都要用同一句，别各写各的）。 */
export const ONE_BASED_NOTE =
  '按 ROM 字节推定：压入的值 N 选中链上第 N 段（静态字节证据，未做运行期确认）。';

/** 读 ROM 里的 u32（绝对地址）。 */
function readU32(rom, at) {
  return (rom[at] | (rom[at + 1] << 8) | (rom[at + 2] << 16) | (rom[at + 3] << 24)) >>> 0;
}

/**
 * 把补丁叠上去之后的 ROM 视图。
 *
 * 剧情脚本的正文**不在任何结构表 / 文本表的写回范围内**，改动只以补丁存在
 * （与 `scripttext.js::currentBytes` 同一件事）。
 * 所以界面上看到的操作数值必须是「当前值」，不是原版值。
 */
export function patchedRom(pack, rom) {
  if (!rom) return null;
  const patches = (pack && pack.patches) || [];
  if (!patches.length) return rom;
  const out = new Uint8Array(rom);
  for (const patch of patches) {
    const after = hexToBytes(patch.after_hex || '');
    for (let i = 0; i < after.length; i++) {
      const at = patch.offset + i;
      if (at >= 0 && at < out.length) out[at] = after[i];
    }
  }
  return out;
}

/** 根表里第 `scene` 场的剧本首地址（0 表示没有）。 */
export function rootPointer(pack, structureId, scene) {
  const structure = pack && pack.structure ? pack.structure(structureId) : null;
  const record = structure && structure.records ? structure.records[scene] : null;
  const ptr = record && record.values ? record.values.ptr : 0;
  return ptr ? ptr >>> 0 : 0;
}

/**
 * 这一关的触发模型。
 *
 * @param {Uint8Array} rom
 * @param {object} pack      内容包（只为拿根指针）
 * @param {number} scene     关卡（场景）编号
 */
export function buildTriggerModel(rom, pack, scene) {
  const model = {
    scene,
    logicPtr: 0,
    eventsPtr: 0,
    logicInstructions: [],
    eventsInstructions: [],
    chain: [],
    segments: [],
    blocks: [],
    counts: {
      blocks: 0, linked: 0, unlinked: 0,
      chainLength: 0, unconditional: 0, conditions: 0,
    },
    /** logic 与 events 是不是同一段字节（场景 32..38 是）。 */
    overlapping: false,
    /** 没有 ROM / 没有剧本时给界面看的一句话。 */
    empty: null,
  };

  model.logicPtr = rootPointer(pack, 'story_logic_root', scene);
  model.eventsPtr = rootPointer(pack, 'story_events_root', scene);

  if (!rom) {
    model.empty = '未载入原版 ROM —— 反汇编剧情脚本需要 ROM 字节。';
    return model;
  }
  if (!model.logicPtr || !model.eventsPtr) {
    model.empty = '这一关没有战场事件剧本（根表里没有指针）。';
    return model;
  }

  // 界面要看的是**当前值**：脚本正文的改动只以补丁存在。
  const view = patchedRom(pack, rom);
  const logic = scanScript(view, model.logicPtr - ROM_BASE);
  const events = scanScript(view, model.eventsPtr - ROM_BASE);
  model.logicInstructions = logic;
  model.eventsInstructions = events;

  // --- 事件链（events 剧本开头的连续 0x32）------------------------------
  const chain = [];
  for (const instruction of events) {
    if (instruction.op !== CHAIN_OP) break;
    chain.push({
      index: chain.length + 1,
      offset: instruction.offset,
      // u32 载荷是「段首地址」
      target: readU32(view, instruction.offset + 1) - ROM_BASE,
    });
  }
  model.chain = chain;

  // --- 剧情段（链上每一条 = 一段对白，段尾是 0x00）----------------------
  const eventsEnd = events.reduce((max, i) => Math.max(max, i.offset + i.length), 0);
  const segments = chain.map((item, i) => {
    const start = item.target;
    const end = i + 1 < chain.length ? chain[i + 1].target : eventsEnd;
    const instructions = events.filter((ins) => ins.offset >= start && ins.offset < end);
    return {
      index: item.index,
      start,
      end,
      instructions,
      lines: instructions.filter((ins) => TEXT_OPS.has(ins.op)),
    };
  });
  model.segments = segments;

  // --- 触发块（logic 剧本里「到 0x33 为止的一段条件指令」）---------------
  const blocks = [];
  let pending = [];
  let pendingFlag = null;
  for (const instruction of logic) {
    if (instruction.op === PUSH_OP) {
      blocks.push({
        index: blocks.length,
        value: view[instruction.offset + 1],
        push: instruction,
        conditions: pending,
        flag: pendingFlag,
      });
      pending = [];
      pendingFlag = null;
    } else if (CONDITION_OPS.has(instruction.op)) {
      pending.push(instruction);
    } else if (instruction.op === FLAG_OP) {
      pendingFlag = instruction;
    }
  }
  model.blocks = blocks;

  // --- 跳转目标解析（三档 + 末尾 + 本组压栈）----------------------------
  const endOffset = logic.reduce(
    (found, i) => (i.op === 0 ? i.offset : found), null);
  model.endOffset = endOffset === null ? null : endOffset;

  for (const block of blocks) {
    block.first = block.conditions.length ? block.conditions[0].offset : block.push.offset;
  }
  for (const block of blocks) {
    block.conditions = block.conditions.map((instruction, i) =>
      conditionEntry(view, instruction, i, block, blocks, endOffset));
    block.pushOperands = editableOperands(view, block.push);
    if (block.flag) {
      const flagOperands = editableOperands(view, block.flag);
      const flagValues = {};
      for (const operand of flagOperands) flagValues[operand.name] = operand.value;
      block.flag = {
        op: block.flag.op,
        offset: block.flag.offset,
        operands: flagOperands,
        values: flagValues,
      };
    }
    // --- 配对：事件 id → 链上第 id 段（1 基）--------------------------
    const linked = block.value >= 1 && block.value <= chain.length;
    block.segment = linked ? segments[block.value - 1] : null;
    block.linked = linked;
    block.lineCount = block.segment ? block.segment.lines.length : 0;
    block.summary = blockSummary(block);
  }

  // --- 计数 -------------------------------------------------------------
  model.counts.blocks = blocks.length;
  model.counts.linked = blocks.filter((b) => b.linked).length;
  model.counts.unlinked = blocks.filter((b) => !b.linked).length;
  model.counts.chainLength = chain.length;
  model.counts.unconditional = blocks.filter((b) => !b.conditions.length).length;
  model.counts.conditions = blocks.reduce((n, b) => n + b.conditions.length, 0);

  // logic 与 events 是不是同一段字节（场景 32..38：events 根 = logic 根 + 8）
  model.overlapping = model.eventsPtr > model.logicPtr
    && model.eventsPtr - model.logicPtr < 64
    && events.length < logic.length;

  return model;
}

/** 一条条件指令的完整描述（操作数 + 极性 + 跳转目标）。 */
function conditionEntry(rom, instruction, index, block, blocks, endOffset) {
  const operands = editableOperands(rom, instruction);
  const delta = BRANCH[instruction.op];
  const address = readU32(rom, instruction.offset + delta);
  const fileOffset = address - ROM_BASE;
  const target = classifyTarget(fileOffset, block, blocks, endOffset);
  const byName = {};
  for (const operand of operands) byName[operand.name] = operand.value;
  return {
    op: instruction.op,
    offset: instruction.offset,
    length: instruction.length,
    index,
    operands,
    values: byName,
    target: { address, fileOffset, ...target },
    polarity: polarityOf(instruction.op),
    summary: conditionSummary(instruction.op, byName),
    detail: conditionDetail(instruction.op, byName),
  };
}

/**
 * 跳转目标落在哪儿 —— 六档。
 *
 * 实测 1013 条条件指令的落点分布（notes/reviews/…-review-20261022.md §3 P1-4）：
 * 868 跳下一组首条 / 118 跳脚本末尾 / 27 跳别处
 * （19 跳本组内部 —— 含 7 条跳本组里的 0x07 无条件跳转、
 *   3 跳本组自己的 0x33、5 跳后面某一组的 0x33）。
 */
function classifyTarget(fileOffset, block, blocks, endOffset) {
  if (endOffset !== null && fileOffset === endOffset) return { kind: 'end' };
  if (fileOffset === block.push.offset) return { kind: 'self-push' };
  if (fileOffset >= block.first && fileOffset < block.push.offset) {
    const inGroup = block.conditions.findIndex((c) => c.offset === fileOffset);
    return {
      kind: 'in-group',
      groupIndex: inGroup >= 0 ? inGroup : null,
    };
  }
  const next = blocks[block.index + 1];
  if (next && fileOffset >= next.first && fileOffset < next.push.offset) {
    const inNext = next.conditions.findIndex((c) => c.offset === fileOffset);
    return { kind: 'next-group', block: next, groupIndex: inNext >= 0 ? inNext : null };
  }
  const later = blocks.find((b) => b.index > block.index && b.push.offset === fileOffset);
  if (later) return { kind: 'later-push', block: later };
  return { kind: 'other' };
}

/** 条件指令的极性：0x35 与其它相反。 */
export function polarityOf(op) {
  if (op === 53) return '不成立才跳';
  if (op === FLAG_OP) return '不跳转';
  return '成立才跳';
}

/**
 * 条件指令的人话摘要（**短**，用在行头）。
 *
 * 只说这条条件在测什么，不替它下「所以什么时候触发」的结论 ——
 * 那个结论取决于跳转目标，放在「命中时跳到」那一列里说。
 */
export function conditionSummary(op, values) {
  switch (op) {
    case 52: {
      const cmp = COMPARATOR_NAMES[values.comparator] ?? `?${values.comparator}`;
      return `回合计数 ${cmp} ${values.round_count}`;
    }
    case 53:
      // 审核 P1-7：这一条与其它条件**极性相反**，摘要必须自己说清楚。
      return '复合条件不成立才跳走';
    case 54:
      return `角色 #${values.role_id} ${values.expect === 1 ? '在场' : '不在场'}`;
    case 55:
      return `置/清战斗标志 #${values.battle_flag}`;
    case 56:
      return `战斗标志 #${values.battle_flag} 已置`;
    case 57:
      return `子配置 = ${values.sub_config}`;
    default:
      return '';
  }
}

/**
 * 条件指令的详细说明（**长**，用在条件表里）。
 *
 * 没证明的语义照实写：0x35 的三个参数、0x36 的 b、
 * 0x34 的控制字节（0x0202680E）都没有业务名。
 */
export function conditionDetail(op, values) {
  switch (op) {
    case 52:
      return `回合计数 ${COMPARATOR_NAMES[values.comparator] ?? values.comparator} ` +
        `${values.round_count}、且那个未定名的字节 = ${values.phase_byte} 时成立 —— 成立就跳走。` +
        '回合计数是战斗控制块 0x0202680C 的首字节；另一个字节（0x0202680E）仓库还没给它起名字。';
    case 53:
      // 这一句是**两句**，措辞由审核 P1-7 定死。
      return '复合条件（三个参数未命名）成立时才继续；不成立就跳过本组。' +
        `本 ROM 里期望值恒为 ${values.expect}，三个参数分别是 ` +
        `${values.param_b} / ${values.param_c} / ${values.param_d}，仓库还没解它们是什么。`;
    case 54:
      return `检查指定角色 #${values.role_id} 是否在场，结果等于设定值 ${values.expect} 时成立 —— 成立就跳走。` +
        `参数 b = ${values.param_b} 的作用仓库还没解。`;
    case 55:
      return `把战斗标志 #${values.battle_flag} 置上或清掉（模式 = ${values.flag_mode}）。` +
        '模式的两个取值分别代表什么，仓库还没命名。';
    case 56:
      return `战斗标志 #${values.battle_flag} 的位域为 1 时成立 —— 成立就跳走（模式 = ${values.flag_mode}）。` +
        '模式的取值仓库还没命名。';
    case 57:
      return `子配置 id = ${values.sub_config} 时成立 —— 成立就跳走。`;
    default:
      return '';
  }
}

/** 跳转目标的人话说法。 */
export function targetText(target, block) {
  switch (target.kind) {
    case 'end':
      return '跳到脚本末尾';
    case 'self-push':
      return '跳到本组的压栈（这一组会触发）';
    case 'in-group':
      return target.groupIndex === null
        ? '跳到本组内的跳转（本组继续判）'
        : `跳到本组第 ${target.groupIndex + 1} 条（本组继续判）`;
    case 'next-group':
      return `跳到触发块 #${target.block.index + 1} 的第 ${(target.groupIndex ?? 0) + 1} 条（跳过本组）`;
    case 'later-push':
      return `跳到触发块 #${target.block.index + 1} 的压栈（跳过本组）`;
    default:
      return `跳到 0x${(target.address >>> 0).toString(16).toUpperCase()}（本组之外）`;
  }
}

/**
 * 一个触发块的行头摘要。
 *
 * 「守门条件」是刻意这么叫的：每条条件成立就跳走（多数是跳过本组），
 * **全部落空**才会压入事件 id、触发那一段对白。
 */
export function blockSummary(block) {
  if (!block.conditions.length) return '无条件（一直成立）';
  const parts = block.conditions.map((c) => c.summary).filter(Boolean);
  return `守门条件：${parts.join('、')}`;
}

/**
 * 这一关的 logic / events 剧本覆盖的字节区间（文件偏移）。
 *
 * 角标口径用：补丁偏移落在这两个区间里，才算「本关触发块里的改动」。
 */
export function sceneScriptRanges(rom, pack, scene) {
  const ranges = [];
  for (const id of ['story_logic_root', 'story_events_root']) {
    const ptr = rootPointer(pack, id, scene);
    if (!ptr) continue;
    const instructions = scanScript(rom, ptr - ROM_BASE);
    if (!instructions.length) continue;
    let start = Infinity;
    let end = 0;
    for (const instruction of instructions) {
      start = Math.min(start, instruction.offset);
      end = Math.max(end, instruction.offset + instruction.length);
    }
    ranges.push([start, end]);
  }
  return ranges;
}

/**
 * 本关的触发块里改了几处。
 *
 * **按当前状态重算**（不看累加值）—— 撤销之后要回落。
 * `pack.patches` 是全局的，所以要有「补丁偏移 → 本关触发块」的映射：
 * 落在本关 logic / events 剧本指令范围内的补丁才算。
 */
export function sceneTriggerChangeCount(pack, rom, scene) {
  if (!rom || !pack) return 0;
  const ranges = sceneScriptRanges(rom, pack, scene);
  if (!ranges.length) return 0;
  let n = 0;
  for (const patch of pack.patches || []) {
    if ((patch.after_hex || '') === (patch.before_hex || '')) continue;
    if (ranges.some(([start, end]) => patch.offset >= start && patch.offset < end)) n += 1;
  }
  return n;
}
