// 从 ROM 解析出内容包。
//
// 内容包里存着**ROM 的结构知识**：每张表在哪、每条记录多少字节、每个字段在记录里的
// 偏移与类型、每张文本表的指针在哪、每条剧本的根表槽位在哪。
// 而**值**是从 ROM 的字节里读出来的。
//
// 所以「从 ROM 解析出内容包」= **用内容包当模板**，把每一个值从 ROM 里重读一遍。
// 这跟 Python 那边的 `tools/export_content_pack.py` 是同一件事，
// 区别是这里在浏览器里做 —— 所以它只能覆盖「模板里已经描述过」的那些表；
// 模板之外的东西（`derived` / `map_assets` / 字库）沿用原值，因为它们不是 ROM 的值。
//
// 与导出器一致的地方：结构记录的字段布局、文本表的指针表 / 内联槽两种形态、
// 剧本的「可改操作数 / 路线边 / 头像引用」三样元信息。

import { bytesToBase64, bytesToHex, base64ToBytes } from './bytes.js';
import { readField, textSlotKind } from './pack.js';
import { scanTokens } from './textcodec.js';
import { scanScript, ROM_BASE } from './storyvm.js';

/** 四张剧情根表（ROM 地址）：槽号 = 场景号。 */
export const STORY_ROOTS = {
  before: { base: 0x060c74, scenes: 55 },
  after: { base: 0x060d54, scenes: 55 },
  logic: { base: 0x060e34, scenes: 46 },
  events: { base: 0x060ef0, scenes: 46 },
};

/** 剧本里**可改**的定宽操作数（导出器 `wanted` 表的镜像）。 */
const WANTED = {
  0x16: { scene: [1, 1] },
  0x1a: { scene: [1, 1], flag: [2, 1] },
  0x1b: { music: [1, 1] },
  0x1e: { map: [1, 1] },
  0x1f: { config: [1, 1] },
  0x23: { member_a: [1, 1], member_b: [2, 1] },
};

/** 操作数的显示名（与导出器 `labels` 表一致）。 */
const OPERAND_LABELS = {
  scene: '下一场景 id',
  flag: '相位标志',
  music: '音乐曲目 id',
  map: '地图 id',
  config: '子配置 id',
  member_a: '队员 A',
  member_b: '队员 B',
};

function readU16(bytes, at) {
  return bytes[at] | (bytes[at + 1] << 8);
}
function readU32(bytes, at) {
  return (bytes[at] | (bytes[at + 1] << 8) | (bytes[at + 2] << 16)
    | (bytes[at + 3] << 24)) >>> 0;
}

/** 从 `at` 起读到 NUL（含 NUL）—— 文本表里的正文都是 NUL 结尾的。 */
function readCString(bytes, at, limit = 0x10000) {
  const out = [];
  for (let i = at; i < bytes.length && i < at + limit; i++) {
    out.push(bytes[i]);
    if (bytes[i] === 0) break;
  }
  return new Uint8Array(out);
}

/**
 * 用 ROM 的字节重读一个结构表。
 *
 * 每条记录的字节从 `rom_offset` 处读；字段按模板里的 `offset`/`type` 解码。
 * **没人解出来的字节（`hex` 填充）原样带过来** —— 这是「复制原生条目 +
 * 只改已知字段」那条写回模型的前提。
 */
function parseStructure(structure, rom) {
  let records = 0;
  let changed = 0;
  for (const record of structure.records || []) {
    const size = structure.entry_size || record.raw_bytes || 0;
    if (record.rom_offset < 0 || record.rom_offset + size > rom.length) continue;
    const bytes = rom.subarray(record.rom_offset, record.rom_offset + size);
    const values = {};
    for (const field of structure.fields || []) {
      if (!(field.key in (record.values || {}))) continue;
      values[field.key] = readField(bytes, field);
    }
    const before = record.raw;
    record.values = values;
    record.raw = bytesToBase64(bytes);
    records += 1;
    if (before !== record.raw) changed += 1;
  }
  return { records, changed };
}

/**
 * 把 token 流解成**正文**（控制码跳过）。
 *
 * 与导出器一致：`tools/text_codec.py::decode` 走 `scan_codes` ——
 * **控制码 0x01 / 0x02 连同它们的载荷整个跳过**，不显示、也不占位置。
 * （`FontCodec.decode` 是给「要原样往返」用的，它把控制码显示成 ，
 *  文本表里不适用 —— 导出器那边也是跳过的。）
 */
function decodeTextTokens(tokens, font) {
  let out = '';
  for (const token of tokens) {
    if (token.k !== 't') continue;
    const code = token.c;
    if (code === 0x0a) { out += '\n'; continue; }
    if (code >= 32 && code < 127) { out += String.fromCharCode(code); continue; }
    const ch = font.codeToChar.get(code);
    out += ch === undefined
      ? `{字${code.toString(16).toUpperCase().padStart(4, '0')}}`
      : ch;
  }
  return out;
}

/**
 * 用 ROM 的字节重读一张文本表。
 *
 * 三种形态（与导出器 `build_text_table` / `build_inline_text_table` /
 * `build_battle_objectives` 一一对应）：
 *
 *   * **指针表驱动** —— 指针在 `pointer_offset`，正文在它指向的地方。
 *     必须**跟指针走**（不能跟模板里记的 `text_offset` 走）：
 *     构建时正文可能被搬到空闲区，指针会变。
 *   * **绝对地址引用**（战斗目标说明文字）—— 正文在 `text_offset`，NUL 结尾。
 *   * **定长内联槽**（说话人名表）—— 正文写在 12 字节的固定槽里，
 *     槽尾有填充；`raw` 记的是**整个槽**。
 *
 * 前两种的 `raw` 记的是**内容**（不含结尾 NUL），`capacity` 含 NUL；
 * 第三种的 `raw` 是整个槽、`capacity` 就是槽大小 ——
 * 判据是模板里 `raw` 的长度与 `capacity` 是否相等。
 */
function parseTextTable(table, rom, font) {
  let records = 0;
  let changed = 0;
  for (const record of table.records || []) {
    // 形态判定与导出器同源（`pack.js::textSlotKind`）：
    // 指针表驱动 / 定长内联槽 / 绝对地址引用。
    const kind = textSlotKind(table, record);
    const fixedSlot = kind === 'fixed';
    let bytes = null;

    if (record.pointer_offset !== null && record.pointer_offset !== undefined) {
      // 指针表：跟指针走。
      const pointer = readU32(rom, record.pointer_offset);
      const at = pointer - ROM_BASE;
      if (at < 0 || at >= rom.length) continue;
      const withNul = readCString(rom, at);
      bytes = withNul.subarray(0, withNul.length - 1);
      record.pointer = pointer;
      record.text_offset = at;
      record.capacity = bytes.length + 1;
    } else if (fixedSlot) {
      // 定长内联槽：整个槽原样（内容 + NUL + 填充）。
      const size = record.capacity || 0;
      if (record.text_offset + size > rom.length) continue;
      bytes = rom.slice(record.text_offset, record.text_offset + size);
    } else {
      // 绝对地址引用：NUL 结尾的内容。
      const at = record.text_offset;
      if (at === null || at === undefined || at < 0 || at >= rom.length) continue;
      const withNul = readCString(rom, at);
      bytes = withNul.subarray(0, withNul.length - 1);
      record.capacity = bytes.length + 1;
    }
    if (!bytes) continue;

    const before = record.raw;
    record.raw = bytesToBase64(bytes);
    // **不存 tokens** —— 内容包里没有这个键（它是运行时按 `raw` 现算的缓存）。
    record.text = decodeTextTokens(scanTokens(bytes), font);
    record.original_text = record.text;
    delete record.text_changed;
    records += 1;
    if (before !== record.raw) changed += 1;
  }
  return { records, changed };
}

/**
 * 重推四张根表下的剧本元信息。
 *
 * 三样：**可改操作数**（定宽，改它不会移位）、**路线边**（0x16 / 0x1A）、
 * **头像引用**（0x08 设置头像 + 说话人名字）。
 */
function parseScripts(rom) {
  const out = [];
  for (const [root, info] of Object.entries(STORY_ROOTS)) {
    for (let scene = 1; scene <= info.scenes; scene++) {
      const slot = info.base + scene * 4;
      if (slot + 4 > rom.length) continue;
      const pointer = readU32(rom, slot);
      if (!pointer) continue;
      const offset = pointer - ROM_BASE;
      if (offset < 0 || offset >= rom.length) continue;
      const instructions = scanScript(rom, offset);
      if (!instructions.length) continue;

      const route = [];
      const operands = [];
      const portraits = [];
      for (const instruction of instructions) {
        const op = instruction.op;
        if (op === 0x08) {
          portraits.push({
            rom_offset: instruction.offset,
            portrait_id: rom[instruction.offset + 1],
          });
        }
        const wanted = WANTED[op];
        if (wanted) {
          for (const [name, [delta, size]] of Object.entries(wanted)) {
            const at = instruction.offset + delta;
            operands.push({
              name,
              label: OPERAND_LABELS[name] || name,
              rom_offset: at,
              size,
              value: size === 1 ? rom[at] : readU16(rom, at),
              before_hex: bytesToHex(rom.slice(at, at + size)),
              opcode: op,
            });
          }
          if (op === 0x16 || op === 0x1a) {
            route.push({
              op,
              rom_offset: instruction.offset,
              scene_rom_offset: instruction.offset + 1,
              scene: rom[instruction.offset + 1],
              flag: op === 0x1a ? rom[instruction.offset + 2] : null,
              kind: op === 0x1a ? 'cursor' : 'after',
            });
          }
        } else if (op === 0x22) {
          // 把角色加入战斗配置：三个字节的含义没钉死，按原始字节呈现
          // （value 与导出器一致，是**十六进制字符串**，不是数字）。
          const at = instruction.offset + 1;
          const hex = bytesToHex(rom.slice(at, at + 3));
          operands.push({
            name: 'raw',
            label: '把角色加入战斗配置（3 字节，字段含义未钉死）',
            rom_offset: at,
            size: 3,
            value: hex,
            before_hex: hex,
            opcode: op,
          });
        }
      }
      out.push({
        id: `${root}.${scene}`,
        root,
        scene,
        script_offset: offset,
        pointer_slot: slot,
        instruction_count: instructions.length,
        route,
        operands,
        portraits,
      });
    }
  }
  return out;
}

/**
 * 从 ROM 解析出一份内容包。
 *
 * @param {ContentPack} template  当模板用的内容包（提供字段布局与记录偏移）
 * @param {Uint8Array} rom
 * @param {object} options { name, sha256 }
 * @returns {{pack: object, report: object}} 新内容包的**数据**（还没进 ContentPack）
 */
export function parsePackFromRom(template, rom, options = {}) {
  const report = {
    structures: 0, records: 0, recordsChanged: 0,
    texts: 0, textsChanged: 0, scripts: 0,
    errors: [],
  };

  const structures = (template.structures || []).map((structure) => {
    const clone = {
      ...structure,
      records: (structure.records || []).map((record) => ({ ...record })),
    };
    const result = parseStructure(clone, rom);
    report.structures += 1;
    report.records += result.records;
    report.recordsChanged += result.changed;
    return clone;
  });

  const font = template.font;
  const texts = (template.texts || []).map((table) => {
    const clone = {
      ...table,
      records: (table.records || []).map((record) => ({ ...record })),
    };
    const result = parseTextTable(clone, rom, font);
    report.texts += 1;
    report.textsChanged += result.changed;
    return clone;
  });

  const scripts = parseScripts(rom);
  report.scripts = scripts.length;

  const data = {
    format: template.format,
    version: template.version,
    generated: null,
    rom: {
      name: options.name || 'base.gba',
      size: rom.length,
      sha256: options.sha256 || '',
    },
    font: {
      code_to_char: Object.fromEntries(template.font.codeToChar),
      char_to_code: Object.fromEntries(template.font.charToCode),
      coverage: template.font.coverage,
      segments_total: template.font.segmentsTotal,
      duplicate_characters: template.font.duplicateCharacters,
    },
    structures,
    texts,
    scripts,
    // **补丁不跟着 ROM 走** —— 补丁是「作者的改动」，不是 ROM 的内容。
    patches: [],
    notes: template.notes,
    derived: template.derived,
    map_assets: template.map_assets,
  };
  return { pack: data, report };
}
