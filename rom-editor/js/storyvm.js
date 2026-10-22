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
 * 哪些操作码的哪个字节偏移上是**剧本内的绝对地址** —— 搬迁剧本时必须重基。
 *
 * 取自 `BRANCH`（u32 在指令内的偏移）、`SINGLE_TARGET`（u32 恒在 +1）
 * 与 `0x06` 的两个目标（+1 / +5）。共 13 个槽位。
 *
 * ⚠️ **不要**用「值落在 [A, A+L) 就 += Δ」这种看数值的判据 ——
 * 本 ROM 实测那种判据会误伤 30 处（指令内部）与 1,119 处（原生代码里
 * `12 xx xx xx` 这类操作数字节凑出来的 `0x08xxxxxx` 巧合值）。
 * 正确的主规则是**这张白名单**；区间判据只能降级为断言
 * （每个目标必须落在本剧本某条指令的起点上）。
 *
 * 依据：`notes/evidence/story-script-relocation-20261022.md`。
 */
export const ADDRESS_SLOTS = (() => {
  const out = {};
  for (const [op, delta] of Object.entries(BRANCH)) out[op] = [delta];
  for (const op of SINGLE_TARGET) out[op] = [1];
  out[6] = [1, 5];
  return out;
})();

/**
 * 一个剧本的**连续字节段**。
 *
 * 剧本在 ROM 里不一定是一段连续的字节：`before` 与 `after` 是**物理交错**的
 * （`before.1` 的两段中间夹着 `after.1`）。每一段都以 `0x00`（结束脚本）收尾，
 * 段与段之间靠**分支**相连 —— 所以搬迁时把各段搬到一起是安全的：
 * 终止符还在，分支目标重基过。
 *
 * @param {Uint8Array} rom
 * @param {number} root  剧本第一段的起点（**文件偏移**）
 * @returns {Array<{start:number,end:number,instructions:Array}>}
 */
export function scriptFragments(rom, root) {
  const instructions = scanScript(rom, root);
  const fragments = [];
  for (const instruction of instructions) {
    const last = fragments[fragments.length - 1];
    if (last && instruction.offset === last.end) {
      last.end = instruction.offset + instruction.length;
      last.instructions.push(instruction);
    } else {
      fragments.push({
        start: instruction.offset,
        end: instruction.offset + instruction.length,
        instructions: [instruction],
      });
    }
  }
  return fragments;
}

/**
 * 把若干组片段**合并**成一组互不重叠的区间。
 *
 * 为什么需要：有些剧本是**另一个剧本的后缀** —— `after.53` 就是 `before.53`
 * 去掉第一条指令（`0x47f40` 的「载入地图」）。它们的字节**重叠**。
 *
 * 搬迁时这一组必须**当作一个整体**搬：共享的字节只能搬一份 ——
 * 搬两份的话，两个剧本各留一份同一段对白，改了其中一个另一个不变。
 *
 * 指令按偏移去重（同一段字节在两个剧本里是**同一条**指令）。
 *
 * @param {Array<Array<{start:number,end:number,instructions:Array}>>} lists
 * @returns {Array<{start:number,end:number,instructions:Array}>}
 */
export function mergeFragments(lists) {
  const all = [];
  for (const list of lists) {
    for (const fragment of list) {
      all.push({
        start: fragment.start,
        end: fragment.end,
        instructions: fragment.instructions.slice(),
      });
    }
  }
  all.sort((a, b) => a.start - b.start);
  const out = [];
  for (const fragment of all) {
    const last = out[out.length - 1];
    if (last && fragment.start <= last.end) {
      // 重叠（或正好接上）→ 并进上一段。
      last.end = Math.max(last.end, fragment.end);
      const seen = new Set(last.instructions.map((i) => i.offset));
      for (const instruction of fragment.instructions) {
        if (seen.has(instruction.offset)) continue;
        seen.add(instruction.offset);
        last.instructions.push(instruction);
      }
      last.instructions.sort((a, b) => a.offset - b.offset);
    } else {
      out.push(fragment);
    }
  }
  return out;
}

/** 两组片段有没有交集。 */
function fragmentsOverlap(a, b) {
  for (const x of a) {
    for (const y of b) {
      if (x.start < y.end && y.start < x.end) return true;
    }
  }
  return false;
}

/**
 * 把互相**重叠**的剧本分组。
 *
 * 实测：11 对剧本共享字节（`before.4`/`after.4`、`before.20`/`after.20`、
 * `before.51`/`after.51`、`before.53`/`after.53`、
 * `logic.32`..`logic.38` / `events.32`..`events.38`）。
 * 每一对里，共享的那段里有**几百段对白**（`before.53`/`after.53` 共享 7,987 字节、
 * 282 段正文）—— 所以这一组必须一起搬、一起改指针。
 *
 * @param {Uint8Array} rom
 * @param {number[]} roots  剧本首地址（文件偏移）
 * @returns {Array<{roots:number[], fragments:Array}>}
 */
export function scriptComponents(rom, roots) {
  const unique = [...new Set(roots)];
  const fragmentsOf = unique.map((root) => scriptFragments(rom, root));

  // 并查集：片段有交集的两个剧本并成一组。
  const parent = unique.map((_, i) => i);
  const find = (i) => {
    while (parent[i] !== i) {
      parent[i] = parent[parent[i]];
      i = parent[i];
    }
    return i;
  };
  const union = (a, b) => {
    const ra = find(a);
    const rb = find(b);
    if (ra !== rb) parent[rb] = ra;
  };
  for (let i = 0; i < unique.length; i++) {
    for (let j = i + 1; j < unique.length; j++) {
      if (fragmentsOverlap(fragmentsOf[i], fragmentsOf[j])) union(i, j);
    }
  }

  const groups = new Map();
  for (let i = 0; i < unique.length; i++) {
    const key = find(i);
    if (!groups.has(key)) groups.set(key, { roots: [], fragments: [] });
    const group = groups.get(key);
    group.roots.push(unique[i]);
    group.fragments = mergeFragments([group.fragments, fragmentsOf[i]]);
  }
  return [...groups.values()];
}

/**
 * 规划一次**搬迁**：把剧本搬到新地址，并把它的内部绝对地址全部重基。
 *
 * **纯函数** —— 只算不写，所以可以对着**全部 202 个剧本**跑一遍当门禁。
 *
 * `roots` 可以是**一个**剧本，也可以是**一组互相重叠的剧本** ——
 * 后一种必须一起搬（共享的字节只能有一份）。
 *
 * @param {Uint8Array} rom
 * @param {number|number[]} roots  剧本首地址（**文件偏移**）
 * @param {number} newStart  搬到哪里去（**文件偏移**）
 * @param {Array<{offset:number,length:number,bytes:Uint8Array}>} edits
 *        正文替换（offset/length 是原文件的字节区间，bytes 是新字节）
 * @returns {{bytes:Uint8Array, fragments:Array, roots:Array, rebase:Array, errors:Array}|null}
 */
export function planRelocation(rom, root, newStart, edits = []) {
  const roots = Array.isArray(root) ? root : [root];
  const fragments = mergeFragments(roots.map((r) => scriptFragments(rom, r)));
  if (!fragments.length) return null;
  const errors = [];
  const sorted = [...edits].sort((a, b) => a.offset - b.offset);

  // --- 1. 每一段：把落在它里面的正文替换掉 --------------------------------
  const newFragments = [];
  let cursor = newStart;
  for (const fragment of fragments) {
    const inside = sorted.filter((e) => e.offset >= fragment.start && e.offset < fragment.end);
    const chunks = [];
    let at = fragment.start;
    for (const edit of inside) {
      if (edit.offset < at) {
        errors.push(`正文 ${edit.offset} 落在上一段里，跳过`);
        continue;
      }
      if (edit.offset + edit.length > fragment.end) {
        errors.push(
          `正文 ${edit.offset} 的替换范围跨出了这一段`
          + `（${edit.offset + edit.length} > ${fragment.end}），无法安全搬迁`
        );
        continue;
      }
      chunks.push(rom.subarray(at, edit.offset));
      chunks.push(edit.bytes);
      at = edit.offset + edit.length;
    }
    chunks.push(rom.subarray(at, fragment.end));
    let length = 0;
    for (const chunk of chunks) length += chunk.length;
    const bytes = new Uint8Array(length);
    let write = 0;
    for (const chunk of chunks) {
      bytes.set(chunk, write);
      write += chunk.length;
    }
    newFragments.push({
      oldStart: fragment.start,
      oldEnd: fragment.end,
      newStart: cursor,
      newEnd: cursor + bytes.length,
      bytes,
    });
    cursor += bytes.length;
  }

  // --- 2. 段内偏移映射 ----------------------------------------------------
  /** 旧文件偏移 → 新文件偏移（在本剧本内；不在则返回 null）。 */
  const mapOffset = (oldOffset) => {
    for (const fragment of newFragments) {
      if (oldOffset < fragment.oldStart || oldOffset >= fragment.oldEnd) continue;
      let delta = 0;
      for (const edit of sorted) {
        if (edit.offset < fragment.oldStart || edit.offset >= fragment.oldEnd) continue;
        if (edit.offset + edit.length <= oldOffset) {
          delta += edit.bytes.length - edit.length;
        }
      }
      return fragment.newStart + (oldOffset - fragment.oldStart) + delta;
    }
    return null;
  };

  // --- 3. 重基：把每个地址槽的 u32 改成新地址 ------------------------------
  const scriptBytes = new Uint8Array(cursor - newStart);
  let write = 0;
  for (const fragment of newFragments) {
    scriptBytes.set(fragment.bytes, write);
    write += fragment.bytes.length;
  }
  const rebase = [];
  for (const fragment of fragments) {
    for (const instruction of fragment.instructions) {
      const slots = ADDRESS_SLOTS[instruction.op];
      if (!slots) continue;
      for (const slot of slots) {
        const at = instruction.offset + slot;
        if (at + 4 > rom.length) continue;
        const oldTarget = (rom[at] | (rom[at + 1] << 8)
          | (rom[at + 2] << 16) | (rom[at + 3] << 24)) >>> 0;
        const oldFile = oldTarget - ROM_BASE;
        const newFile = mapOffset(oldFile);
        if (newFile === null) {
          errors.push(
            `0x${instruction.op.toString(16).toUpperCase()} @0x${instruction.offset.toString(16).toUpperCase()}`
            + ` 的目标 0x${oldTarget.toString(16).toUpperCase()} 不在本剧本内`
          );
          continue;
        }
        const newAt = mapOffset(at);
        if (newAt === null) continue;
        const value = (ROM_BASE + newFile) >>> 0;
        // 索引要相对 `scriptBytes` 的起点 —— `newAt` 是绝对文件偏移。
        const index = newAt - newStart;
        if (index < 0 || index + 4 > scriptBytes.length) continue;
        scriptBytes[index] = value & 0xff;
        scriptBytes[index + 1] = (value >>> 8) & 0xff;
        scriptBytes[index + 2] = (value >>> 16) & 0xff;
        scriptBytes[index + 3] = (value >>> 24) & 0xff;
        rebase.push({ oldOffset: at, newOffset: newAt, oldTarget, newTarget: value });
      }
    }
  }

  // --- 4. 每个入口的新地址 ------------------------------------------------
  const rootMoves = [];
  for (const oldRoot of roots) {
    const newRoot = mapOffset(oldRoot);
    if (newRoot === null) {
      errors.push(`入口 0x${oldRoot.toString(16).toUpperCase()} 不在搬走的字节里`);
      continue;
    }
    rootMoves.push({ old: oldRoot, new: newRoot });
  }

  return { bytes: scriptBytes, fragments: newFragments, roots: rootMoves, rebase, errors };
}

/**
 * Proved fixed-width operands that may be rewritten in place.
 * opcode → operand name → (offset inside the instruction, size in bytes).
 * Mirrors `tools/import_story_script.py::KNOWN_OPERANDS`; a rewrite here
 * cannot move anything, so branch targets stay valid.
 *
 * 0x32（事件链选择）**不在表里**：它的 u32 载荷是「段首地址」，
 * 改它等于改控制流，不是改参数（见 notes/specs/battle-story-triggers-20261022.md D5）。
 * 0x34..0x39（战场触发的条件指令）的定宽 u8 字段在这里补齐，
 * 语义边界见 notes/story-vm-opcodes-20261020.md §3。
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
  // 0x34 回合/相位条件：比较器 @+1、b @+2、c @+3（u32 目标 @+4 不给输入框）
  52: { comparator: [1, 1], round_count: [2, 1], phase_byte: [3, 1] },
  // 0x35 复合条件：a @+1、b @+2、c @+3、d @+4（三个参数的业务含义仓库还没解）
  53: { expect: [1, 1], param_b: [2, 1], param_c: [3, 1], param_d: [4, 1] },
  // 0x36 指定角色在场：a @+1、b @+2、c @+3
  54: { expect: [1, 1], param_b: [2, 1], role_id: [3, 1] },
  // 0x37 置/清战斗标志：模式 @+1、标志 @+2
  55: { flag_mode: [1, 1], battle_flag: [2, 1] },
  // 0x38 测试战斗标志：模式 @+1、标志 @+2
  56: { flag_mode: [1, 1], battle_flag: [2, 1] },
  // 0x39 子配置匹配：id @+1
  57: { sub_config: [1, 1] },
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
  comparator: '比较器',
  round_count: '回合计数',
  phase_byte: '未定名字节',
  expect: '期望值',
  param_b: '参数 b（未命名）',
  param_c: '参数 c（未命名）',
  param_d: '参数 d（未命名）',
  role_id: '角色 id',
  flag_mode: '标志模式',
  battle_flag: '战斗标志 id',
  sub_config: '子配置 id',
};

/**
 * 比较器（0x34 的 @+1）。
 *
 * `0x08097210` 分发到 `0x08097230` 的六项表：**无符号**，两个操作数都按 u8 取值。
 * 见 notes/story-vm-opcodes-20261020.md §3.1。
 */
export const COMPARATOR_NAMES = {
  0: '==',
  1: '!=',
  2: '>',
  3: '>=',
  4: '<',
  5: '<=',
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
 *
 * 每个操作数还带 `before_hex`（原版字节）—— 写回通路 `pack.setScriptOperand`
 * 拿它当补丁的「改前字节」：缺了它补丁就没有校验依据，构建时的
 * 「原字节必须匹配」过不了，补丁的 before/after 长度也不相等。
 * （`common.js::operandInput` 自己**不**补这个字段 ——
 *  它之所以能用，是因为内容包里的 `pack.scripts[].operands` 自带 before_hex；
 *  这里新算出来的操作数必须自带，才喂得进去。）
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
      before_hex: bytesOf(rom, at, size),
    });
  }
  return out;
}

/** 若干字节的十六进制（小端原样，补丁的「改前字节」用这个格式）。 */
function bytesOf(rom, at, size) {
  let out = '';
  for (let i = 0; i < size; i++) {
    out += (rom[at + i] & 0xff).toString(16).padStart(2, '0');
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
