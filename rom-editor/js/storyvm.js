// Story VM (剧情脚本) decoder.
//
// Port of the repo's proven disassembler: `tools/import_story_script.py`
// (instruction_length / scan_script / _branch_targets / _text_end) and
// `tools/decode_story_script.py` (LENGTHS / BRANCH / SINGLE_TARGET / TEXT_OPS).
// The tables below are copied verbatim from those two modules so the editor
// and the repo's own write-back path agree on the bytecode layout.
//
// The opcode numbers are decimal in the repo's tables; here they are kept as
// decimal too, with the hex form used in the comments and in the UI.
//
// Meaning of the opcodes (from notes/story-script-vm.md and
// notes/evidence/story-vm-opcodes-20261020.md):
//   0x16 (22) next scene — sets the route cursor
//   0x1A (26) next scene + phase flag — sets the route cursor
//   0x1E (30) load map / background
//   0x1F (31) set sub-config id
//   0x22 (34) add a character to the battle configuration
//   0x23 (35) set party members
//   0x01/0x05/0x13/0x20 carry text runs (variable length)

export const ROM_BASE = 0x08000000;

/** Fixed instruction lengths, in bytes (decimal opcode → length). */
export const LENGTHS = {
  0: 1, 2: 4, 3: 2, 4: 4, 7: 5, 8: 2, 9: 2, 10: 2, 11: 6, 12: 6, 13: 5,
  14: 3, 15: 2, 16: 1, 17: 2, 18: 5, 20: 3, 21: 8, 22: 2, 23: 4, 24: 4,
  25: 4, 26: 3, 27: 3, 28: 3, 29: 3, 30: 2, 31: 2, 33: 5, 34: 4, 35: 3,
  50: 5, 51: 2, 52: 8, 53: 9, 54: 8, 55: 3, 56: 7, 57: 6,
};

/** Opcodes whose text run starts at this offset inside the instruction. */
export const TEXT_OPS = { 1: 1, 5: 2, 32: 2 };

/** Opcodes that carry text runs (variable length). */
export const TEXT_OPCODES = new Set([32, 1, 19, 5]);

/** Opcodes with a u32 branch target at this offset inside the instruction. */
export const BRANCH = { 11: 2, 12: 2, 21: 4, 52: 4, 53: 5, 54: 4, 56: 3, 57: 2 };

/** Opcodes with a single u32 target at +1. */
export const SINGLE_TARGET = [7, 13, 50];

/**
 * Proved fixed-width operands that may be rewritten in place.
 * opcode → operand name → (offset inside the instruction, size in bytes).
 * Mirrors `tools/import_story_script.py::KNOWN_OPERANDS`; a rewrite here
 * cannot move anything, so branch targets stay valid.
 */
export const KNOWN_OPERANDS = {
  8: { portrait: [1, 1] },
  9: { flag: [1, 1] },
  10: { flag: [1, 1] },
  11: {},
  12: {},
  14: { portrait_a: [1, 1], portrait_b: [2, 1] },
  15: { frames: [1, 1] },
  17: { portrait: [1, 1] },
  20: { progress: [1, 2] },
  22: { scene: [1, 1] },
  26: { scene: [1, 1], flag: [2, 1] },
  27: { track: [1, 1], mode: [2, 1] },
  29: { track: [1, 1], mode: [2, 1] },
  30: { map: [1, 1] },
  31: { config: [1, 1] },
  35: { member_a: [1, 1], member_b: [2, 1] },
  51: { value: [1, 1] },
};

export const OPERAND_LABELS = {
  portrait: '头像 id',
  flag: '剧情标记 id',
  portrait_a: '头像 id A',
  portrait_b: '头像 id B',
  frames: '等待帧数',
  progress: '剧情进度',
  scene: '下一场景 id',
  track: '音轨',
  mode: '模式',
  map: '地图 id',
  config: '子配置 id',
  member_a: '队员 A',
  member_b: '队员 B',
  value: '事件队列值',
};

export const OPCODE_NAMES = {
  0: '结束脚本', 1: '显示文本', 2: '选择对话框', 3: '关闭对话框', 4: '切换对话框',
  5: '菜单选项', 6: '二选一分支', 7: '无条件跳转', 8: '设置头像与说话人',
  9: '置剧情标记', 10: '清剧情标记', 11: '标记为真则跳转', 12: '标记为假则跳转',
  13: '调用子脚本', 14: '设置两个头像', 15: '等待 N 帧', 16: '清对话状态',
  17: '清除头像', 18: '设置对话框尺寸', 19: '双段文本', 20: '剧情进度',
  21: '比较跳转', 22: '下一场景', 23: '场景物件参数', 24: '消息区尺寸',
  25: '批量置标记', 26: '下一场景（带相位）', 27: '播放音乐', 28: '画面切换',
  29: '停止音乐', 30: '载入地图/底图', 31: '设置子配置', 32: '带说话人的对话',
  33: '放置对话框', 34: '把角色加入战斗配置', 35: '设置队员',
  50: '事件链选择', 51: '压入事件队列值', 52: '回合条件', 53: '复合条件',
  54: '指定角色在场', 55: '置/清战斗标记', 56: '测试战斗标记', 57: '子配置匹配',
};

/** Offset just after the NUL-terminated text run starting at `pos`. */
export function textEnd(rom, pos) {
  let p = pos;
  const limit = Math.min(rom.length, pos + 8192);
  while (p < limit) {
    const a = rom[p];
    if (a === 0) return p + 1;
    if (a === 1) { p += 2; continue; }
    if (a === 2) { p += 3; continue; }
    if (a >= 0x80 && a <= 0x9f) { p += 2; continue; }
    p += 1;
  }
  return p;
}

/** Length of the instruction at `offset`. */
export function instructionLength(rom, offset) {
  const op = rom[offset];
  if (TEXT_OPCODES.has(op)) {
    if (op === 0x01) return 1 + (textEnd(rom, offset + 1) - (offset + 1));
    if (op === 0x05 || op === 0x20) return 2 + (textEnd(rom, offset + 2) - (offset + 2));
    // 0x13: the first text sits at +4; a second follows when +2 is non-zero
    let end = textEnd(rom, offset + 4);
    if (rom[offset + 2]) end = textEnd(rom, end + 1);
    return end - offset;
  }
  if (op === 0x06) return 9;
  const length = LENGTHS[op];
  if (length === undefined) return 0; // unknown / void opcode
  return length;
}

/** Branch targets (file offsets) of the instruction at `offset`. */
export function branchTargets(rom, offset, length) {
  const op = rom[offset];
  const targets = [];
  const read32 = (at) => rom[at] | (rom[at + 1] << 8) | (rom[at + 2] << 16) | (rom[at + 3] << 24);
  if (op === 0x06) {
    targets.push(read32(offset + 1) - ROM_BASE, read32(offset + 5) - ROM_BASE);
  } else if (SINGLE_TARGET.includes(op)) {
    targets.push(read32(offset + 1) - ROM_BASE);
  } else if (BRANCH[op] !== undefined) {
    targets.push(read32(offset + BRANCH[op]) - ROM_BASE);
  }
  return targets.filter((t) => t >= 0 && t < rom.length);
}

/**
 * Every reachable instruction of the script at `root` (a file offset).
 * Returns a list ordered by file offset.
 */
export function scanScript(rom, root) {
  if (root < 0 || root >= rom.length) return [];
  const seen = new Map();
  const stack = [root];
  while (stack.length) {
    const p = stack.pop();
    if (seen.has(p) || p < 0 || p >= rom.length) continue;
    const length = instructionLength(rom, p);
    if (!length) continue;
    seen.set(p, { offset: p, op: rom[p], length });
    for (const target of branchTargets(rom, p, length)) stack.push(target);
    const op = rom[p];
    if (op !== 0x00 && op !== 0x06 && op !== 0x07) stack.push(p + length);
  }
  return [...seen.values()].sort((a, b) => a.offset - b.offset);
}

/**
 * The editable (proved fixed-width) operands of one instruction.
 * Each entry carries the absolute ROM offset, so the editor can write it back
 * without moving a single byte.
 */
export function editableOperands(rom, instruction) {
  const spec = KNOWN_OPERANDS[instruction.op];
  if (!spec) return [];
  const out = [];
  for (const [name, [delta, size]] of Object.entries(spec)) {
    const at = instruction.offset + delta;
    let value;
    if (size === 1) value = rom[at];
    else value = rom[at] | (rom[at + 1] << 8);
    out.push({
      name,
      label: OPERAND_LABELS[name] || name,
      rom_offset: at,
      size,
      value,
    });
  }
  return out;
}

/**
 * The text runs of one instruction.
 *
 * A text-carrying instruction may hold more than one run: 0x13 ("双段文本")
 * holds two of them, and the second one starts one byte **after** the first
 * run's NUL — that gap byte belongs to neither run (see
 * notes/story-vm-opcodes-20261020.md §1.6; `instructionLength` above walks
 * the same way, so the two never disagree).
 *
 * Each run carries the file offset of its body and the body's length.  The
 * NUL terminator is **not** part of it, so rewriting the body cannot move
 * the terminator — and with it the following instruction.
 *
 * @param {Uint8Array} rom
 * @param {{offset:number, op:number}} instruction
 * @returns {Array<{offset:number, length:number, kind:string, speaker:?number}>}
 */
export function instructionTextRuns(rom, instruction) {
  const op = instruction.op;
  const runs = [];
  if (op === 0x01) {
    runs.push({ offset: instruction.offset + 1, kind: 'text' });
  } else if (op === 0x05) {
    runs.push({ offset: instruction.offset + 2, kind: 'menu' });
  } else if (op === 0x20) {
    // 0x20 的第 2 字节是这条指令自带的字段。**handler（0x08097A66）并不读它**：
    // 游戏显示的名牌取自对话框状态（由 0x08 写入），本 ROM 里该字节恒为 1。
    runs.push({
      offset: instruction.offset + 2,
      kind: 'dialogue',
      speaker: rom[instruction.offset + 1],
    });
  } else if (op === 0x13) {
    const first = instruction.offset + 4;
    runs.push({ offset: first, kind: 'text' });
    if (rom[instruction.offset + 2]) {
      runs.push({ offset: textEnd(rom, first) + 1, kind: 'text' });
    }
  } else {
    return [];
  }
  for (const run of runs) {
    const end = textEnd(rom, run.offset);
    run.length = Math.max(0, end - 1 - run.offset);
    run.end = end;
  }
  return runs;
}

/**
 * The route edges of one script: the "next scene" instructions.
 * 0x16 (22) jumps to the after-script of a scene and remembers the next
 * scene id; 0x1A (26) sets the route cursor itself.
 */
export function routeEdges(rom, instructions) {
  const edges = [];
  for (const instruction of instructions) {
    if (instruction.op === 0x16) {
      edges.push({
        op: 0x16,
        rom_offset: instruction.offset,
        scene_rom_offset: instruction.offset + 1,
        scene: rom[instruction.offset + 1],
        flag: null,
        kind: 'after',
      });
    } else if (instruction.op === 0x1A) {
      edges.push({
        op: 0x1a,
        rom_offset: instruction.offset,
        scene_rom_offset: instruction.offset + 1,
        scene: rom[instruction.offset + 1],
        flag: rom[instruction.offset + 2],
        kind: 'cursor',
      });
    }
  }
  return edges;
}
