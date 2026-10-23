#!/usr/bin/env node
/**
 * probe_speaker_code_patches.mjs
 * -------------------------------------------------------------------------
 * 校验「说话人名表」12 个原生读者改「4 字节步长指针表 + 解引用」的代码补丁。
 *
 * 它只读 ROM 与补丁清单，不写 ROM、不改任何既有文件。
 *
 * 检查项：
 *   1. before_hex 与 ROM 里的字节逐字节相符（不符 ⇒ 补丁会打歪）
 *   2. before_hex / after_hex 长度相同（⇒ 不挪动任何后续代码）
 *   3. 补丁区间不与「说话人全名表」保护区 0x085A5AB8 起重叠
 *   4. 用 capstone 反汇编补丁前后的指令：
 *      旧序列与清单 old_disasm **逐字**比对（old_disasm 就是 capstone 原样文本）；
 *      新序列与清单 new_disasm **按语义**比对（new_disasm 是语义等价的人工可读写法，
 *      解引用写作 `ldr rX, [rX, #0]`，而 capstone 5.0.7 原样打印 `ldr rX, [rX]`
 *      —— 同一编码、语义相同，立即数偏移 0）
 *   5. 独立解析 Thumb 位域：新序列的 ldr [pc,#imm] 必须仍然指向同一个字面量；
 *      lsls 的移位量必须是 2（步长 4）；解引用必须是**立即数偏移**形式
 *      `ldr rD,[rD,#0]`（0x68xx, imm5=0）；**寄存器偏移**形式（0x58xx ⇒ 2×rD）
 *      必须被判为错误；末尾不得是被禁用的填充指令、且必须是清单约定的那条安全填充指令
 *      （约定从清单 conventions.filler 推导，不写死）
 *   6. 把所有补丁打进 ROM 副本，确认 ROM 只在补丁区间内变化，
 *      且补丁后 16 字节与补丁前完全一致（代码没有移动）
 *   7. 独立扫描全 ROM 的 ldr-literal 引用，确认 12 个读者都被补丁覆盖，
 *      而 0x085A5AB8 全名表的 3 个读者没有被碰
 *   8. 确认新指针表区间 [0x085A57C4, 0x085A58C4) 与保护区不相交
 *
 * 用法： node tools/probe_speaker_code_patches.mjs
 *   环境变量（仅供变异测试用，仓库源文件零改动）：
 *     SPK_MANIFEST  换掉补丁清单（绝对路径）
 *     SPK_REPORT    换掉报告输出路径
 * 产物： build/speaker-name-patches.txt（人类可读报告）
 * 退出码： 0 = 全通过；1 = 有失败项
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.resolve(HERE, "..");
const ROM_PATH = path.join(REPO, "rom", "base.gba");
// 变异测试用：SPK_MANIFEST / SPK_REPORT 可把清单与报告指到临时副本（仓库源文件零改动）。
const MANIFEST_PATH = process.env.SPK_MANIFEST
  ? path.resolve(process.env.SPK_MANIFEST)
  : path.join(REPO, "tools", "data", "speaker_name_code_patches.json");
const REPORT_PATH = process.env.SPK_REPORT
  ? path.resolve(process.env.SPK_REPORT)
  : path.join(REPO, "build", "speaker-name-patches.txt");

const ROM_BASE = 0x08000000;
const TABLE_BASE = 0x085a57c4;

/* ------------------------------------------------------------------ utils */
const hex = (n, w = 8) => "0x" + n.toString(16).toUpperCase().padStart(w, "0");
const fileOff = (romAddr) => romAddr - ROM_BASE;

let failures = 0;
let checks = 0;
const report = [];
function say(line = "") {
  report.push(line);
}
function check(ok, label, detail = "") {
  checks += 1;
  if (!ok) failures += 1;
  say(`  [${ok ? "PASS" : "FAIL"}] ${label}${detail ? " :: " + detail : ""}`);
  return ok;
}
function section(title) {
  say();
  say("=".repeat(78));
  say(title);
  say("=".repeat(78));
}

/* -------------------------------------------------- tiny Thumb bit decoders */
const REG = ["r0", "r1", "r2", "r3", "r4", "r5", "r6", "r7"];

/** 归一化反汇编文本：去掉逗号后的空格（capstone 打印 "ldr r0, [r0, r0]"，
 *  清单里写成 "ldr r0, [r0,r0]"；两者语义相同）。 */
const normAsm = (s) => s.replace(/\s*,\s*/g, ",");

/* ---------------------------------------------------------------------------
 * 语义归一化：把一条反汇编文本归一化成「助记符 + 操作数语义」键。
 *
 * 用途：清单的 new_disasm 是**语义等价的人工可读写法**（解引用写成
 *   `ldr rX, [rX, #0]`，而本机 Capstone 5.0.7 原样打印成 `ldr rX, [rX]`），
 *   **不是** capstone 原样文本 ⇒ 只能按语义比对，不能逐字比对。
 *   （清单的 old_disasm 才是逐字等于 capstone 原样输出的那一份，仍走逐字比对。）
 *
 * 归一化规则：
 *   - 立即数：#0x7c → #124（进制统一）
 *   - 内存 [base, #imm]：imm=0 时省略 ⇒ [r0] 与 [r0, #0] **同义**（立即数偏移 0）
 *   - 内存 [base, reg]：保留为「寄存器偏移」形式 ⇒ [r0, r0] 与 [r0, #0] **不同义**
 * ------------------------------------------------------------------------- */

/** 顶层逗号切分（方括号内的逗号不切）。 */
function splitTopLevel(s) {
  const out = [];
  let depth = 0;
  let cur = "";
  for (const ch of s) {
    if (ch === "[") depth += 1;
    else if (ch === "]") depth -= 1;
    if (ch === "," && depth === 0) {
      out.push(cur.trim());
      cur = "";
    } else {
      cur += ch;
    }
  }
  if (cur.trim() !== "") out.push(cur.trim());
  return out;
}

/** "#0x7c" / "#124" → 124；不是立即数则返回 null。 */
function parseImm(text) {
  const t = text.trim();
  if (!t.startsWith("#")) return null;
  const body = t.slice(1);
  if (/^0x[0-9a-f]+$/i.test(body)) return parseInt(body.slice(2), 16);
  if (/^-?\d+$/.test(body)) return parseInt(body, 10);
  return null;
}

/** 归一化单个操作数。 */
function normOperand(op) {
  const t = op.trim().toLowerCase();
  const imm = parseImm(t);
  if (imm !== null) return `#${imm}`;
  const mem = t.match(/^\[(.*)\]$/);
  if (mem) {
    const out = [];
    for (const part of splitTopLevel(mem[1])) {
      const pimm = parseImm(part);
      if (pimm !== null) {
        if (pimm !== 0) out.push(`imm${pimm}`); // 立即数偏移 0 ≡ 无偏移
        continue;
      }
      // 寄存器偏移（[r0, r0]）/ 移位（[r0, r1, lsl #2]）：原样保留，
      // **不能**与立即数偏移混为一谈。
      out.push(part.replace(/\s+/g, ""));
    }
    return `[${out.join(",")}]`;
  }
  return t.replace(/\s+/g, "");
}

/** 一条反汇编文本 → 语义键。 */
function semNorm(asm) {
  const s = String(asm).trim().replace(/\s+/g, " ");
  const m = s.match(/^([a-zA-Z][a-zA-Z0-9_.]*)\s*(.*)$/);
  if (!m) return s.toLowerCase();
  const ops = splitTopLevel(m[2]).map(normOperand);
  return m[1].toLowerCase() + (ops.length ? " " + ops.join(" ") : "");
}

function decodeLslsImm(hw) {
  if ((hw & 0xf800) !== 0x0000) return null; // 00000 imm5 Rm Rd
  return { imm5: (hw >> 6) & 0x1f, rm: (hw >> 3) & 7, rd: hw & 7 };
}
function decodeLdrLiteral(hw) {
  if ((hw & 0xf800) !== 0x4800) return null; // 01001 Rt imm8
  return { rt: (hw >> 8) & 7, imm8: hw & 0xff };
}
/** Thumb-1 LDR (register) T1 —— 0101 1000 00 Rm Rn Rt（0x58xx）。
 *  Rm=Rn=Rd 时读的是 *(Rm+Rn) = 2×rD，**不是** *(rD)；
 *  这正是「第十八轮更正」修掉的那个坑，清单里一律用立即数偏移形式。 */
function decodeLdrReg(hw) {
  if ((hw & 0xfc00) !== 0x5800) return null;
  return { rm: (hw >> 6) & 7, rn: (hw >> 3) & 7, rt: hw & 7 };
}
/** Thumb-1 LDR (immediate) T1 —— 0101 1 imm5 Rn Rt（0x68xx）。
 *  imm5=0 ⇒ 读 *(Rn)，即解引用 `ldr rD,[rD,#0]`。 */
function decodeLdrImm(hw) {
  if ((hw & 0xf800) !== 0x6800) return null;
  return { imm5: (hw >> 6) & 0x1f, rn: (hw >> 3) & 7, rt: hw & 7 };
}

/* --------------------------------- 填充指令约定（从清单推导，不写死） */
/** 约定文本里所有 0xXXXX 形式的半字（按出现顺序）。 */
function hexWords(text) {
  return [...String(text).matchAll(/0x([0-9a-fA-F]{4})\b/g)].map((m) => parseInt(m[1], 16));
}
const FILLER_FORBIDDEN_RE = /禁用|禁止|不得|不能|严禁/;
/**
 * 从清单的 conventions.filler 推导两条约定：
 *   - safe     ：「固定是 0xXXXX」的那一条（ARMv4T 安全填充指令）
 *   - forbidden：「禁用 0xXXXX」的那一条（ARMv4T 未定义指令 ⇒ 真机异常死循环）
 * 推导不出来就返回 null —— 由调用方判红，绝不静默写死一个值。
 */
function deriveFillerConvention(text) {
  const s = String(text || "");
  const cut = s.search(FILLER_FORBIDDEN_RE);
  const head = cut >= 0 ? s.slice(0, cut) : s;
  const tail = cut >= 0 ? s.slice(cut) : "";
  return { text: s, safe: hexWords(head)[0] ?? null, forbidden: hexWords(tail)[0] ?? null };
}

/* ------------------------------------------------------------ capstone glue */
const PY_SCRIPT = `
import json, os, pathlib, sys
repo = pathlib.Path(os.environ["SPK_REPO"])
sys.path.insert(0, str(repo / "tools"))
import capstone_loader
capstone = capstone_loader.load_capstone()
from capstone import CS_ARCH_ARM, CS_MODE_THUMB, Cs
payload = json.loads(os.environ["SPK_PAYLOAD"])
md = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
out = []
for item in payload:
    blob = bytes.fromhex(item["hex"])
    insns = []
    for insn in md.disasm(blob, item["addr"]):
        insns.append([insn.address, bytes(insn.bytes).hex(),
                      (insn.mnemonic + " " + insn.op_str).strip()])
    out.append(insns)
sys.stdout.write(json.dumps(out))
`;

function capstoneDisasm(items) {
  const res = spawnSync("python", ["-"], {
    input: PY_SCRIPT,
    encoding: "utf8",
    env: { ...process.env, SPK_REPO: REPO, SPK_PAYLOAD: JSON.stringify(items) },
    maxBuffer: 64 * 1024 * 1024,
  });
  if (res.error) return { error: String(res.error) };
  if (res.status !== 0) {
    return { error: (res.stderr || "").trim() || `python exited ${res.status}` };
  }
  try {
    return { data: JSON.parse(res.stdout) };
  } catch (e) {
    return { error: "cannot parse capstone output: " + e.message + " :: " + res.stdout.slice(0, 400) };
  }
}

/* ------------------------------------------------------------------- main */
const rom = fs.readFileSync(ROM_PATH);
const manifest = JSON.parse(fs.readFileSync(MANIFEST_PATH, "utf8"));
const patches = manifest.patches;

/* 填充指令约定：唯一真相源是清单的 conventions.filler（不写死 0x46C0 / 0xBF00）。 */
const FILLER = deriveFillerConvention(manifest.conventions && manifest.conventions.filler);

say("说话人名表『12 字节内联名』→『4 字节指针表 + 解引用』代码补丁核验报告");
say("生成时间：2026-10-23   （本文件由 tools/probe_speaker_code_patches.mjs 生成）");
say("");
say(`ROM        : ${path.relative(REPO, ROM_PATH)}  (${rom.length} 字节)`);
say(`清单       : ${path.relative(REPO, MANIFEST_PATH)}  (${patches.length} 处补丁)`);
say(`ROM 基址   : ${hex(ROM_BASE)}   ROM 地址 = 文件偏移 + ${hex(ROM_BASE)}`);
say(`表基址     : ROM ${hex(TABLE_BASE)} / 文件 ${hex(fileOff(TABLE_BASE))}  (${manifest.table.old_stride_bytes} 字节/条 → ${manifest.table.new_stride_bytes} 字节/条)`);
say(`保护区     : ROM ${manifest.table.protected_region_rom_addr[0]} 起（说话人全名表，19 字节/条）`);
say(`新指针表   : ROM ${manifest.table.new_pointer_table_rom_addr[0]}..${manifest.table.new_pointer_table_rom_addr[1]}（${manifest.table.new_pointer_table_size} 字节）`);
say(`填充约定   : 安全 ${FILLER.safe === null ? "推导失败" : hex(FILLER.safe, 4)} / 禁用 ${FILLER.forbidden === null ? "推导失败" : hex(FILLER.forbidden, 4)}（从清单 conventions.filler 推导）`);

check(
  FILLER.safe !== null,
  "能从清单 conventions.filler 推导安全填充指令",
  FILLER.safe === null ? "清单里没有 conventions.filler 或读不出 0xXXXX" : hex(FILLER.safe, 4),
);
check(
  FILLER.forbidden !== null,
  "能从清单 conventions.filler 推导被禁用的填充指令",
  FILLER.forbidden === null ? "清单里没有 conventions.filler 或读不出 0xXXXX" : hex(FILLER.forbidden, 4),
);

const patched = Buffer.from(rom);
const touched = new Set();

/* ------------------------------------------------- 逐处补丁检查 */
const disasmItems = [];
const disasmIndex = new Map();

for (const p of patches) {
  const addr = parseInt(p.rom_addr, 16);
  const off = parseInt(p.rom_offset, 16);
  if (off !== fileOff(addr)) {
    check(false, `patch #${p.reader}/${p.site} 地址自洽`, `rom_offset ${p.rom_offset} != rom_addr - 0x08000000`);
  }
  const before = Buffer.from(p.before_hex, "hex");
  const after = Buffer.from(p.after_hex, "hex");
  if (before.length !== after.length) {
    check(false, `patch #${p.reader}/${p.site} 长度相同`, `${before.length} vs ${after.length}`);
  }
  if (before.length !== p.byte_length) {
    check(false, `patch #${p.site} byte_length 自洽`, `${before.length} vs ${p.byte_length}`);
  }
  const romSlice = rom.subarray(off, off + before.length);
  check(
    romSlice.equals(before),
    `patch #${p.reader}/${p.site} before_hex 与 ROM 逐字节相符`,
    `ROM ${romSlice.toString("hex")} / 清单 ${before.toString("hex")}`,
  );

  // 保护区 / 新指针表区间都不许被代码补丁覆盖
  const protLo = parseInt(manifest.table.protected_region_file_offset[0], 16);
  const protHi = parseInt(manifest.table.protected_region_file_offset[1], 16);
  const ptLo = parseInt(manifest.table.new_pointer_table_file_offset[0], 16);
  const ptHi = parseInt(manifest.table.new_pointer_table_file_offset[1], 16);
  check(
    off + before.length <= protLo || off >= protHi,
    `patch #${p.reader}/${p.site} 不碰全名表保护区`,
    `[${hex(off, 6)}, ${hex(off + before.length - 1, 6)}) vs 保护区 [${hex(protLo, 6)}, ${hex(protHi, 6)})`,
  );
  check(
    off + before.length <= ptLo || off >= ptHi,
    `patch #${p.reader}/${p.site} 不碰新指针表数据区`,
    `[${hex(off, 6)}, ${hex(off + before.length - 1, 6)}) vs [${hex(ptLo, 6)}, ${hex(ptHi, 6)})`,
  );

  // 写进 ROM 副本
  after.copy(patched, off);
  for (let i = 0; i < before.length; i += 1) touched.add(off + i);

  disasmItems.push({ addr, hex: p.before_hex, key: `${p.reader}/${p.site}/before` });
  disasmItems.push({ addr, hex: p.after_hex, key: `${p.reader}/${p.site}/after` });
  disasmIndex.set(`${p.reader}/${p.site}/before`, disasmItems.length - 2);
  disasmIndex.set(`${p.reader}/${p.site}/after`, disasmItems.length - 1);
}

/* ---------------------------------------------------------- capstone 反汇编 */
section("逐处补丁核验（含 capstone 反汇编）");
const cap = capstoneDisasm(disasmItems);
if (cap.error) {
  check(false, "capstone 反汇编可用", cap.error);
} else {
  check(true, "capstone 反汇编可用", `${disasmItems.length} 段`);

  for (const p of patches) {
    const addr = parseInt(p.rom_addr, 16);
    const before = Buffer.from(p.before_hex, "hex");
    const after = Buffer.from(p.after_hex, "hex");

    section(`读者 ${p.reader} / ${p.site}   (变体 ${p.variant})`);
    say(`  ROM 地址 ${hex(addr)}   文件偏移 ${hex(fileOff(addr), 6)}   长度 ${before.length} 字节`);
    say(`  id 来源 : ${p.id_source}`);
    say(`  字面量   : ROM ${p.literal_rom_addr} = ${p.literal_value}`);
    say(`  旧字节   : ${p.before_hex}`);
    say(`  新字节   : ${p.after_hex}`);

    const beforeText = cap.data[disasmIndex.get(`${p.reader}/${p.site}/before`)];
    const afterText = cap.data[disasmIndex.get(`${p.reader}/${p.site}/after`)];

    const beforeAsm = beforeText.map((x) => normAsm(x[2]));
    const manifestOld = p.old_disasm.map(normAsm);
    // old_disasm 是 capstone 原样文本 ⇒ 逐字比对；
    // new_disasm 是语义等价的人工可读写法 ⇒ 按语义比对（不能逐字）。
    const afterSem = afterText.map((x) => semNorm(x[2]));
    const manifestNewSem = p.new_disasm.map(semNorm);
    const afterAsm = afterText.map((x) => normAsm(x[2]));
    const manifestNewRaw = p.new_disasm.map(normAsm);

    say("  旧序列   :");
    beforeText.forEach((x) => say(`    ${hex(x[0])}: ${x[1]}    ${x[2]}`));
    say("  新序列   :");
    afterText.forEach((x) => say(`    ${hex(x[0])}: ${x[1]}    ${x[2]}`));

    check(
      JSON.stringify(beforeAsm) === JSON.stringify(manifestOld),
      "旧序列反汇编与清单一致",
      `capstone ${JSON.stringify(beforeAsm)} vs 清单 ${JSON.stringify(manifestOld)}`,
    );
    const semOk =
      JSON.stringify(afterSem) === JSON.stringify(manifestNewSem);
    check(
      semOk,
      "新序列反汇编与清单语义一致（new_disasm 是语义可读写法，不逐字比对）",
      `capstone ${JSON.stringify(afterSem)} vs 清单 ${JSON.stringify(manifestNewSem)}`,
    );
    if (semOk && JSON.stringify(afterAsm) !== JSON.stringify(manifestNewRaw)) {
      say("  注：清单 new_disasm 与 capstone 原样文本只在**写法**上不同（解引用写作 [rX, #0] = 立即数偏移 0），语义一致 ⇒ 按语义比对通过。");
    }
    check(
      before.length === after.length && beforeText.length === afterText.length,
      "长度不变（不挪动任何后续代码）",
      `${before.length} B / ${beforeText.length} 条 → ${after.length} B / ${afterText.length} 条`,
    );

    /* --- 位域语义检查（不依赖 capstone 文本） --- */
    const oldHw = [];
    const newHw = [];
    for (let i = 0; i + 1 < before.length; i += 2) oldHw.push(before.readUInt16LE(i));
    for (let i = 0; i + 1 < after.length; i += 2) newHw.push(after.readUInt16LE(i));

    const oldLsl = oldHw.map(decodeLslsImm).filter(Boolean);
    const newLsl = newHw.map(decodeLslsImm).filter(Boolean);
    check(
      newLsl.length >= 1 && newLsl[0].imm5 === 2,
      "新序列步长 = 4（lsls #2）",
      `imm5=${newLsl.length ? newLsl[0].imm5 : "n/a"}`,
    );
    check(
      oldLsl.length === 2 && oldLsl[0].imm5 === 1 && oldLsl[1].imm5 === 2,
      "旧序列步长 = 12（lsls #1 → adds → lsls #2）",
      JSON.stringify(oldLsl),
    );

    const oldLit = oldHw.map(decodeLdrLiteral).filter(Boolean);
    const newLit = newHw.map(decodeLdrLiteral).filter(Boolean);
    const oldLitIdx = oldHw.findIndex((hw) => decodeLdrLiteral(hw) !== null);
    const newLitIdx = newHw.findIndex((hw) => decodeLdrLiteral(hw) !== null);
    if (oldLit.length === 1) {
      const litAddr = p.literal_rom_addr;
      const oldTarget = ((addr + oldLitIdx * 2 + 4) & ~3) + oldLit[0].imm8 * 4;
      // 新 ldr 往前挪了 4 字节，按新地址重算目标
      const newTarget = ((addr + newLitIdx * 2 + 4) & ~3) + newLit[0].imm8 * 4;
      check(
        oldTarget === newTarget && newTarget === parseInt(litAddr, 16),
        "新 ldr 字面量仍指向同一个字面量地址",
        `旧 ${hex(oldTarget)} / 新 ${hex(newTarget)} / 清单 ${litAddr}`,
      );
      const litWord = rom.readUInt32LE(fileOff(newTarget));
      check(
        litWord === TABLE_BASE,
        "字面量字仍是 0x085A57C4（基址常量不变）",
        hex(litWord),
      );
      check(
        newLit[0].imm8 === oldLit[0].imm8 + 1,
        "ldr 的 imm8 加 1（偏移 +4 字节）",
        `${oldLit[0].imm8} → ${newLit[0].imm8}`,
      );
    } else {
      check(oldLit.length === 0 && newLit.length === 0, "本处不含 ldr 字面量（基址已在寄存器里）");
    }

    // 解引用必须是「立即数偏移 0」形式：ldr rD,[rD,#0]（0x68xx, imm5=0）⇒ 读 *(rD)
    const newLdrImm = newHw.map(decodeLdrImm).filter(Boolean);
    const derefImm = newLdrImm.filter((x) => x.imm5 === 0 && x.rt === x.rn);
    check(
      derefImm.length === 1,
      "新序列含且仅含一条解引用 ldr rD,[rD,#0]（立即数偏移 0）",
      JSON.stringify(newLdrImm.map((x) => ({ imm5: x.imm5, rn: REG[x.rn], rt: REG[x.rt] }))),
    );
    // 寄存器偏移形式（0x58xx；Rm=Rn=Rd ⇒ 读 *(Rm+Rn) = 2×rD）必须被明确判为错误：
    // 它长得像解引用，其实算的是 2×rD —— 正是「第十八轮更正」修掉的那个坑。
    const newLdrRegOff = newHw.map(decodeLdrReg).filter(Boolean);
    check(
      newLdrRegOff.length === 0,
      "新序列不含寄存器偏移 ldr rD,[rD,rD]（那是 2×rD，不是 *(rD)）",
      JSON.stringify(newLdrRegOff.map((x) => ({ rm: REG[x.rm], rn: REG[x.rn], rt: REG[x.rt] }))),
    );
    // 补丁末尾的填充指令：
    //   1) 不得是被禁用的那一条（ARMv4T 上是未定义指令 ⇒ 真机异常死循环 ⇒ 卡死）
    //   2) 必须是清单 conventions.filler 约定的那条安全填充指令
    const tailHw = newHw[newHw.length - 1];
    check(
      FILLER.forbidden === null ? false : tailHw !== FILLER.forbidden,
      "新序列末尾不是被禁用的填充指令（ARMv4T 未定义指令 ⇒ 真机异常死循环）",
      `末尾 ${hex(tailHw, 4)} / 禁用 ${FILLER.forbidden === null ? "n/a" : hex(FILLER.forbidden, 4)}`,
    );
    check(
      FILLER.safe !== null && tailHw === FILLER.safe,
      "新序列以清单约定的安全填充指令补齐",
      `末尾 ${hex(tailHw, 4)} / 约定 ${FILLER.safe === null ? "n/a" : hex(FILLER.safe, 4)}`,
    );

    // 旧序列的最后一条 adds（把基址加上）必须原样保留；
    // 中间那条「id*3」用的 adds 被有意删掉（所以 adds 数量恰好少 1）。
    const oldAdds = [];
    for (let i = 0; i + 1 < before.length; i += 2) {
      const hw = before.readUInt16LE(i);
      if ((hw & 0xfc00) === 0x1800) oldAdds.push(hw); // ADD (register) T2
    }
    const newAdds = [];
    for (let i = 0; i + 1 < after.length; i += 2) {
      const hw = after.readUInt16LE(i);
      if ((hw & 0xfc00) === 0x1800) newAdds.push(hw);
    }
    check(
      oldAdds.length === 2 &&
        newAdds.length === 1 &&
        newAdds[0] === oldAdds[1],
      "加基址那条 adds 字节原样保留（中间的 id*3 加法被删掉）",
      `${oldAdds.map((h) => hex(h, 4)).join(",")} → ${newAdds.map((h) => hex(h, 4)).join(",")}`,
    );
  }
}

/* ------------------------------------------------- 补丁后 16 字节是否移动 */
section("后续代码是否移动（补丁前后 16 字节对比）");
for (const p of patches) {
  const off = parseInt(p.rom_offset, 16);
  const len = p.byte_length;
  const tailBefore = rom.subarray(off + len, off + len + 16);
  const tailAfter = patched.subarray(off + len, off + len + 16);
  check(
    tailBefore.equals(tailAfter),
    `读者 ${p.reader}/${p.site} 补丁后 16 字节一致`,
    tailAfter.toString("hex"),
  );
  const headBefore = rom.subarray(off - 16, off);
  const headAfter = patched.subarray(off - 16, off);
  check(
    headBefore.equals(headAfter),
    `读者 ${p.reader}/${p.site} 补丁前 16 字节一致`,
    headAfter.toString("hex"),
  );
}

/* --------------------------------------------- ROM 副本只在补丁处变化 */
section("ROM 副本差异扫描");
{
  const diffs = [];
  for (let i = 0; i < rom.length; i += 1) {
    if (rom[i] !== patched[i]) diffs.push(i);
  }
  check(
    diffs.length > 0 && diffs.every((d) => touched.has(d)),
    "打补丁后的 ROM 与原 ROM 的差异完全落在补丁区间内",
    `差异 ${diffs.length} 字节 / 补丁区间覆盖 ${touched.size} 字节（其中 ${touched.size - diffs.length} 字节与原 ROM 相同，如原样保留的 adds）`,
  );
  const outside = diffs.filter((d) => !touched.has(d));
  check(outside.length === 0, "没有任何补丁区间之外的字节被改动", `越界 ${outside.length} 字节`);
  const protLo = parseInt(manifest.table.protected_region_file_offset[0], 16);
  const protHi = parseInt(manifest.table.protected_region_file_offset[1], 16);
  const protDiff = diffs.filter((d) => d >= protLo && d < protHi);
  check(protDiff.length === 0, "全名表保护区 0x085A5AB8 起一个字节都没动", `差异 ${protDiff.length} 字节`);
}

/* ---------------------------------- 独立扫描：12 个读者是否都被覆盖 */
section("全 ROM ldr-literal 引用扫描（覆盖度自检）");
{
  const found = [];
  for (let off = 0; off + 2 <= rom.length; off += 2) {
    const hw = rom.readUInt16LE(off);
    if ((hw & 0xf800) !== 0x4800) continue;
    const litAddr = ((ROM_BASE + off + 4) & ~3) + (hw & 0xff) * 4;
    const lo = fileOff(litAddr);
    if (lo < 0 || lo + 4 > rom.length) continue;
    const val = rom.readUInt32LE(lo);
    if (val === TABLE_BASE) found.push({ insn: ROM_BASE + off, lit: litAddr });
  }
  const patchedReaders = new Set();
  for (const p of patches) {
    const before = Buffer.from(p.before_hex, "hex");
    const addr = parseInt(p.rom_addr, 16);
    for (let i = 0; i + 1 < before.length; i += 2) {
      if (decodeLdrLiteral(before.readUInt16LE(i))) patchedReaders.add(addr + i);
    }
  }
  const foundSet = new Set(found.map((f) => f.insn));
  const missing = [...foundSet].filter((a) => !patchedReaders.has(a));
  const extra = [...patchedReaders].filter((a) => !foundSet.has(a));
  check(
    found.length === 12,
    "全 ROM 恰好 12 处引用 0x085A57C4",
    `实际 ${found.length} 处`,
  );
  check(
    missing.length === 0,
    "12 个读者全部被补丁覆盖",
    `漏掉 ${missing.map((a) => hex(a)).join(",") || "无"}`,
  );
  check(
    extra.length === 0,
    "清单里没有多余的 ldr-literal 补丁点",
    `多余 ${extra.map((a) => hex(a)).join(",") || "无"}`,
  );
  say("  读者（ldr 指令地址 → 字面量地址）：");
  for (const f of found.sort((a, b) => a.insn - b.insn)) {
    say(`    ${hex(f.insn)} → ${hex(f.lit)}`);
  }

  // 全名表的 3 个读者必须没被碰
  const prot = [];
  for (let off = 0; off + 2 <= rom.length; off += 2) {
    const hw = rom.readUInt16LE(off);
    if ((hw & 0xf800) !== 0x4800) continue;
    const litAddr = ((ROM_BASE + off + 4) & ~3) + (hw & 0xff) * 4;
    const lo = fileOff(litAddr);
    if (lo < 0 || lo + 4 > rom.length) continue;
    if (rom.readUInt32LE(lo) === 0x085a5ab8) prot.push({ insn: ROM_BASE + off, lit: litAddr });
  }
  check(
    prot.length === 3 && prot.every((p2) => !patchedReaders.has(p2.insn)),
    "全名表 0x085A5AB8 的 3 个读者未被触碰",
    prot.map((p2) => hex(p2.insn)).join(", "),
  );
}

/* ------------------------------------- 新指针表区间与新条目地址的静态核对 */
section("新指针表地址空间静态核对");
{
  const ptLo = parseInt(manifest.table.new_pointer_table_rom_addr[0], 16);
  const ptHi = parseInt(manifest.table.new_pointer_table_rom_addr[1], 16);
  const protLo = parseInt(manifest.table.protected_region_rom_addr[0], 16);
  check(ptHi <= protLo, "新指针表区间不与全名表保护区相交", `${hex(ptHi)} <= ${hex(protLo)}`);
  check(
    ptHi - ptLo === manifest.table.new_entry_count * manifest.table.new_stride_bytes,
    "新指针表长度 = 条数 × 步长",
    `${ptHi - ptLo} = ${manifest.table.new_entry_count} × ${manifest.table.new_stride_bytes}`,
  );
  const last = TABLE_BASE + (manifest.table.new_entry_count - 1) * manifest.table.new_stride_bytes;
  check(last + 4 <= ptHi, "最后一个表项也不越界", `${hex(last + 4)} <= ${hex(ptHi)}`);
  say("  id → 旧槽地址 / 新表项地址：");
  for (const id of [0, 1, 44, 62, 63]) {
    const oldSlot = TABLE_BASE + id * manifest.table.old_stride_bytes;
    const newSlot = TABLE_BASE + id * manifest.table.new_stride_bytes;
    say(`    id ${String(id).padStart(2)} : 旧 ${hex(oldSlot)} (文件 ${hex(fileOff(oldSlot), 6)})  →  新表项 ${hex(newSlot)} (文件 ${hex(fileOff(newSlot), 6)})`);
  }
  say("  注：id 63 的旧槽地址 0x085A5AB8 正是全名表第 0 条 —— 变长方案必须把 id 63 的名字搬进新串池，");
  say("      并且绝不能覆盖 0x085A5AB8 起的数据（新指针表区间到 0x085A58C3 为止，不相交）。");
}

/* ------------------------------------------------------------------ 结论 */
section("结论");
say(`  检查项 ${checks}，失败 ${failures}`);
say(failures === 0 ? "  全部通过：14 处补丁字节级可核验、长度不变、后续代码未移动。" : "  存在失败项，见上。");
say("");
say("  尚未由本探针覆盖的部分（属于数据侧 / 运行时侧，另行处理）：");
say("   1. 新指针表 64 项与变长串池的实际内容尚未生成（本清单只改代码）。");
say("   2. 读者 4/5（0x08066EFC 逐字节抄写）变长后『每字形一列』的列数组容量未实测。");
say("   3. 本探针只做**静态**核验；运行时（mGBA 真机：原版/转换版都能跑、名字逐像素核对）");
say("      由 tools/mgba_probe/speaker_acceptance.py 与 speaker_namebox_check.py 负责，");
say("      记录见 notes/evidence/speaker-name-fix-20261023.md §4 / §5(e)。");

fs.mkdirSync(path.dirname(REPORT_PATH), { recursive: true });
fs.writeFileSync(REPORT_PATH, report.join("\n") + "\n", "utf8");

process.stdout.write(report.join("\n") + "\n");
process.stdout.write(`\n报告已写入 ${path.relative(REPO, REPORT_PATH)}\n`);
process.exit(failures === 0 ? 0 : 1);
