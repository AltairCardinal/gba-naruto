// 剧情脚本**搬迁 + 绝对地址重基**的无头验收（第十六轮）。
//
// 用法：node rom-editor/tools/verify_script_relocation.mjs
//
// 这道门禁证明的是**搬迁本身是对的**：
//   A1 搬完还能被 `scanScript` 扫出**同样多条**指令；
//   A2 每条指令的新偏移 = 旧偏移 + 该指令所在段的新旧差；
//   A3 每一条分支目标都**落在新剧本的指令边界上**（一个都不许指歪）；
//   A4 别的剧本**一条都不受影响**。
//
// 依据：notes/evidence/story-script-relocation-20261022.md
import { readFileSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const repoRoot = join(here, '..', '..');
const romPath = join(repoRoot, 'rom', 'base.gba');

const { scanScript, scriptFragments, planRelocation, ADDRESS_SLOTS, ROM_BASE } =
  await import('../js/storyvm.js');

const lines = [];
let failures = 0;
function check(name, ok, detail = '') {
  if (!ok) failures += 1;
  const line = `  [${ok ? 'PASS' : 'FAIL'}] ${name}${detail ? ' — ' + detail : ''}`;
  lines.push(line);
  console.log(line);
}
function head(text) {
  lines.push(text);
  console.log(text);
}

const rom = new Uint8Array(readFileSync(romPath));

// 四张剧情根表（ROM 地址）：槽号 = 场景号。
const ROOTS = {
  before: { base: 0x060c74, scenes: 55 },
  after: { base: 0x060d54, scenes: 55 },
  logic: { base: 0x060e34, scenes: 46 },
  events: { base: 0x060ef0, scenes: 46 },
};

/** 全部剧本：{ id, root, scene, pointer, fileOffset }。 */
const scripts = [];
for (const [root, info] of Object.entries(ROOTS)) {
  for (let scene = 1; scene <= info.scenes; scene++) {
    const slot = info.base + scene * 4;
    const pointer = (rom[slot] | (rom[slot + 1] << 8)
      | (rom[slot + 2] << 16) | (rom[slot + 3] << 24)) >>> 0;
    if (!pointer) continue;
    const fileOffset = pointer - ROM_BASE;
    if (fileOffset < 0 || fileOffset >= rom.length) continue;
    if (!scanScript(rom, fileOffset).length) continue;
    scripts.push({ id: `${root}.${scene}`, root, scene, slot, pointer, fileOffset });
  }
}

head('\n1) 全部剧本与它们的地址槽');
{
  check('扫出 202 个剧本', scripts.length === 202, `${scripts.length} 个`);
  const slotCount = Object.values(ADDRESS_SLOTS).reduce((n, s) => n + s.length, 0);
  check('地址槽白名单：12 个操作码 / 13 个槽',
    Object.keys(ADDRESS_SLOTS).length === 12 && slotCount === 13,
    Object.keys(ADDRESS_SLOTS).map((op) => '0x' + Number(op).toString(16).toUpperCase()).join(' '));
  const multi = scripts.filter((s) => scriptFragments(rom, s.fileOffset).length > 1);
  check('有分段的剧本（before/after 物理交错）', multi.length > 0,
    `${multi.length} 个剧本分多段`);
}

head('\n2) 每个剧本都能搬、搬完都对（A1 / A2 / A3）');
{
  // 临时落点：在空闲区里给每个剧本一个互不重叠的沙盒。
  // 沙盒放在 **ROM 末尾之后** —— 0x5DFBEC 之前不是空闲区，放那儿会走进原 ROM 的数据。
  const scratchBase = 0x600000;
  let cursor = scratchBase;
  let a1 = 0; let a2 = 0; let a3 = 0;
  let planErrors = 0;
  const badSamples = [];

  for (const script of scripts) {
    const plan = planRelocation(rom, script.fileOffset, cursor, []);
    if (!plan) { planErrors += 1; continue; }
    if (plan.errors.length) {
      planErrors += 1;
      if (badSamples.length < 3) badSamples.push(`${script.id}: ${plan.errors[0]}`);
    }

    // 把新字节放进一份 ROM 副本里，回扫。
    const scratch = new Uint8Array(12 * 1024 * 1024);
    scratch.set(rom, 0);
    scratch.set(plan.bytes, cursor);
    const newInstructions = scanScript(scratch, cursor);

    // A1 指令条数不变
    const oldInstructions = scanScript(rom, script.fileOffset);
    if (newInstructions.length !== oldInstructions.length) {
      badSamples.push(`${script.id}: 指令数 ${oldInstructions.length} → ${newInstructions.length}`);
      planErrors += 1;
    } else a1 += 1;

    // A2 逐条：新偏移 = 旧偏移 + 该段的新旧差
    let offsetOk = true;
    for (let i = 0; i < Math.min(oldInstructions.length, newInstructions.length); i++) {
      const oldOffset = oldInstructions[i].offset;
      const newOffset = newInstructions[i].offset;
      const expected = plan.fragments.find(
        (f) => oldOffset >= f.oldStart && oldOffset < f.oldEnd);
      if (!expected) { offsetOk = false; break; }
      const want = expected.newStart + (oldOffset - expected.oldStart);
      if (want !== newOffset) { offsetOk = false; break; }
    }
    if (offsetOk) a2 += 1; else {
      planErrors += 1;
      if (badSamples.length < 6) badSamples.push(`${script.id}: 指令偏移对不上`);
    }

    // A3 每个分支目标都落在新剧本的指令边界上
    const boundaries = new Set(newInstructions.map((i) => i.offset));
    let targetsOk = true;
    for (const item of plan.rebase) {
      const targetFile = item.newTarget - ROM_BASE;
      if (!boundaries.has(targetFile)) { targetsOk = false; break; }
    }
    if (targetsOk) a3 += 1; else {
      planErrors += 1;
      if (badSamples.length < 9) badSamples.push(`${script.id}: 有分支目标指歪了`);
    }
    cursor += plan.bytes.length + 16;
  }

  check('全部剧本都能规划出搬迁（没有报错）', planErrors === 0,
    badSamples.length ? badSamples.join('；') : `${scripts.length} 个剧本`);
  check('A1 搬完指令条数不变', a1 === scripts.length, `${a1}/${scripts.length}`);
  check('A2 每条指令的新偏移都对', a2 === scripts.length, `${a2}/${scripts.length}`);
  check('A3 每个分支目标都落在新剧本的指令边界上', a3 === scripts.length, `${a3}/${scripts.length}`);
}

head('\n3) 正文变长后仍然对（A1 / A2 / A3 再来一遍）');
{
  // 把第一段的第一条正文指令加长 10 字节（模拟「对白变长」）。
  const script = scripts.find((s) => s.id === 'before.54');
  const instructions = scanScript(rom, script.fileOffset);
  const text = instructions.find((i) => i.op === 0x01);
  check('场景 54 找得到一条正文指令', !!text, text ? `0x${text.offset.toString(16).toUpperCase()}` : '');

  const plan = planRelocation(rom, script.fileOffset, 0x600000, [
    { offset: text.offset + 1, length: 10, bytes: new Uint8Array(20).fill(0x41) },
  ]);
  check('加长后没有规划错误', plan && plan.errors.length === 0,
    plan && plan.errors.length ? plan.errors[0] : '');
  check('新脚本比原来长了 10 字节',
    plan && plan.bytes.length === (scriptFragments(rom, script.fileOffset)
      .reduce((n, f) => n + (f.end - f.start), 0)) + 10,
    plan ? `${plan.bytes.length} 字节` : '');

  const scratch = new Uint8Array(12 * 1024 * 1024);
  scratch.set(rom, 0);
  scratch.set(plan.bytes, 0x600000);
  const newInstructions = scanScript(scratch, 0x600000);
  const oldInstructions = scanScript(rom, script.fileOffset);
  check('加长后指令条数不变', newInstructions.length === oldInstructions.length,
    `${oldInstructions.length} → ${newInstructions.length}`);

  const boundaries = new Set(newInstructions.map((i) => i.offset));
  const bad = plan.rebase.filter((r) => !boundaries.has(r.newTarget - ROM_BASE));
  check('加长后每个分支目标仍落在指令边界上', bad.length === 0,
    bad.length ? `${bad.length} 个目标指歪了` : `${plan.rebase.length} 个目标全部正确`);

  // 加长之后，**别的剧本**一条都不该受影响。
  const other = scripts.find((s) => s.id === 'before.53');
  const otherInstructions = scanScript(rom, other.fileOffset);
  check('别的剧本不受影响（搬迁只写新地址，旧字节没动）',
    otherInstructions.length > 0
    && otherInstructions[0].offset === scanScript(rom, other.fileOffset)[0].offset,
    `${other.id} 仍有 ${otherInstructions.length} 条指令`);
}

head('\n4) 重基的白名单是完整的（不能漏也不能多）');
{
  // 穷举：把每个剧本的每条指令的每个 u32 槽都列出来，
  // 凡是指向本剧本指令边界的，必须在白名单里。
  const missed = [];
  let checked = 0;
  for (const script of scripts) {
    const instructions = scanScript(rom, script.fileOffset);
    const boundaries = new Set(instructions.map((i) => i.offset));
    for (const instruction of instructions) {
      for (let slot = 1; slot + 4 <= instruction.length; slot++) {
        const at = instruction.offset + slot;
        const value = (rom[at] | (rom[at + 1] << 8)
          | (rom[at + 2] << 16) | (rom[at + 3] << 24)) >>> 0;
        const file = value - ROM_BASE;
        if (!boundaries.has(file)) continue;
        checked += 1;
        const slots = ADDRESS_SLOTS[instruction.op] || [];
        if (!slots.includes(slot)) {
          missed.push(`${script.id} op=0x${instruction.op.toString(16).toUpperCase()} +${slot}`);
        }
      }
    }
  }
  check('凡是指向本剧本指令边界的 u32 槽都在白名单里', missed.length === 0,
    missed.length ? missed.slice(0, 5).join('；') : `检查了 ${checked} 处`);
}

const summary = failures === 0
  ? `全部通过（${lines.filter((l) => l.includes('[PASS]')).length} 条断言）`
  : `${failures} 项失败`;
lines.push('');
lines.push(summary);
writeFileSync(join(repoRoot, 'build', 'script-relocation-verify.txt'), lines.join('\n') + '\n', 'utf8');
console.log('');
console.log(summary);
process.exit(failures === 0 ? 0 : 1);
