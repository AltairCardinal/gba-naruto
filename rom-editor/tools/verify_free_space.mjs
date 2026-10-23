// 空闲区**两个分配器不打架**的无头验收（第十八轮）。
//
// 用法：node rom-editor/tools/verify_free_space.mjs
//
// 背景：编辑器（`rom-editor/js/rom.js::allocate`）与 Python 老链路
// （`tools/import_dialogue_var.py`）都往 ROM 末尾那段空闲区里写东西，
// 而两个分配器**互不知情** —— 顺序写的那一个会直接踩到另一个写进去的内容。
//
// 这一轮把两边都改成**只写 0xFF 区**（编辑器本来就是这样；Python 那边改成
// `find_ff_run` 扫 0xFF 段）。于是冲突在结构上消失：谁先写谁把那段变成
// 非 0xFF，另一个自动避开。
//
// 这道门禁断的就是这件事：
//   F1 编辑器**避开**别人（Python 链路）写进空闲区的东西；
//   F2 Python 链路**避开**编辑器写进空闲区的东西（真的 spawn 起来跑）；
//   F3 两次分配**互不重叠**；
//   F4 分配到的区间在**当前 ROM 里确实全是 0xFF**（不会被写到活数据上）。
//
// 依据：notes/free-space.md「与编辑器的关系」一节
import { readFileSync, writeFileSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const repoRoot = join(here, '..', '..');
const romPath = join(repoRoot, 'rom', 'base.gba');

const { RomBuilder, FREE_SPACE_END } = await import('../js/rom.js');
const { ContentPack } = await import('../js/pack.js');

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

/** 空的内容包（只需要 `allocate`，不涉及写回）。 */
function emptyPack() {
  const pack = ContentPack.fromJSON({
    format: 'naruto-konoha-content-pack', version: 1,
    structures: [], texts: [], scripts: [], patches: [],
    font: { code_to_char: {}, char_to_code: {} },
  });
  return pack;
}

/** 在空闲区里摆一段「别人写的」内容（非 0xFF）。 */
function withForeignWrite(at, length) {
  const copy = new Uint8Array(rom);
  for (let i = 0; i < length; i++) copy[at + i] = 0x41;
  return copy;
}

/** 调用 Python 那边的 `find_ff_run`（真的 spawn 起来跑）。 */
function pythonFindFfRun(bytes, size, start) {
  // 6 MiB 的 ROM 塞不进命令行参数 —— 走临时文件。
  const tmp = join(repoRoot, 'build', 'free-space-probe.bin');
  writeFileSync(tmp, Buffer.from(bytes));
  const script = `
import sys, pathlib
sys.path.insert(0, ${JSON.stringify(repoRoot)})
from tools.import_dialogue_var import find_ff_run
data = pathlib.Path(sys.argv[1]).read_bytes()
try:
    print(find_ff_run(data, int(sys.argv[2]), int(sys.argv[3]), ${FREE_SPACE_END} + 1))
except ValueError as err:
    print("ERR " + str(err))
`;
  const out = execFileSync('python', ['-c', script, tmp, String(size), String(start)],
    { cwd: repoRoot, encoding: 'utf8' });
  return out.trim();
}

head('\n1) 空闲区在哪、有多大');
{
  const runs = [];
  let i = 0;
  while (i < rom.length) {
    if (rom[i] === 0xff) {
      let j = i;
      while (j < rom.length && rom[j] === 0xff) j++;
      if (j - i >= 0x1000) runs.push({ start: i, end: j });
      i = j;
    } else {
      i += 1;
    }
  }
  check('全 ROM 只有一段 ≥4KB 的 0xFF', runs.length === 1,
    `${runs.length} 段`);
  check('那一段从 0x5DFBEC 开始', runs[0] && runs[0].start === 0x5dfbec,
    runs[0] ? `0x${runs[0].start.toString(16).toUpperCase()}` : '没有');
  check('编辑器按 0x5FFFFF 收口（与 Python 链路同一处边界）',
    FREE_SPACE_END === 0x5fffff, `0x${FREE_SPACE_END.toString(16).toUpperCase()}`);
}

head('\n2) 编辑器避开「别人」写进空闲区的东西（F1 / F4）');
{
  const foreign = withForeignWrite(0x5dfbec, 100);
  const builder = new RomBuilder(foreign, emptyPack());
  const offset = builder.allocate(64);
  check('分配到的不是别人写的那段', offset !== 0x5dfbec && offset !== null,
    offset === null ? '没找到空闲区' : `0x${offset.toString(16).toUpperCase()}`);
  check('分配到的区间在当前 ROM 里全是 0xFF',
    offset !== null && foreign.subarray(offset, offset + 64).every((b) => b === 0xff),
    offset === null ? '' : `0x${offset.toString(16).toUpperCase()}..`);
  check('分配到的区间落在空闲区里', offset !== null && offset >= 0x5dfbec);
  check('没有越过收口的上界', offset === null || offset + 64 <= FREE_SPACE_END);
}

head('\n3) Python 链路避开编辑器写进空闲区的东西（F2）');
{
  // 编辑器先写：把一段搬过去的剧本放进空闲区（非 0xFF）。
  const editorWrote = withForeignWrite(0x5dfbec, 4096);
  const picked = pythonFindFfRun(editorWrote, 64, 0x5dfbec);
  check('Python 链路返回了一个偏移', picked.startsWith('0x') === false && picked !== 'ERR',
    picked.slice(0, 60));
  const offset = Number(picked);
  check('Python 链路避开了编辑器写的那段',
    offset !== 0x5dfbec && !(offset >= 0x5dfbec && offset < 0x5dfbec + 4096),
    `0x${offset.toString(16).toUpperCase()}`);
  check('Python 链路落点也在空闲区里', offset >= 0x5dfbec);
}

head('\n4) 两次分配互不重叠（F3 / F4）');
{
  const builder = new RomBuilder(rom, emptyPack());
  const first = builder.allocate(1000);
  const second = builder.allocate(1000);
  check('两次都分配到了', first !== null && second !== null,
    `${first} / ${second}`);
  check('两次不重叠', first === null || second === null
    || first + 1000 <= second || second + 1000 <= first,
    `0x${(first ?? 0).toString(16)} / 0x${(second ?? 0).toString(16)}`);
  check('落点全是 0xFF（当前 ROM 里没人写过）',
    first !== null && second !== null
    && rom.subarray(first, first + 1000).every((b) => b === 0xff)
    && rom.subarray(second, second + 1000).every((b) => b === 0xff));
}

head('\n5) Python 链路自己连续分配也不重叠');
{
  const tmp = join(repoRoot, 'build', 'free-space-probe.bin');
  writeFileSync(tmp, Buffer.from(rom));
  const script = `
import sys, pathlib
sys.path.insert(0, ${JSON.stringify(repoRoot)})
from tools.import_dialogue_var import find_ff_run
data = pathlib.Path(sys.argv[1]).read_bytes()
picked = []
cursor = 0x5DFBEC
for _ in range(3):
    at = find_ff_run(data, 200, cursor, ${FREE_SPACE_END} + 1)
    picked.append(at)
    data = data[:at] + b"\\x41" * 200 + data[at + 200:]
    cursor = at + 200
print(" ".join(str(x) for x in picked))
`;
  const out = execFileSync('python', ['-c', script, tmp],
    { cwd: repoRoot, encoding: 'utf8' }).trim();
  const picks = out.split(/\s+/).map(Number);
  check('分配了三次', picks.length === 3, out.slice(0, 60));
  let overlap = false;
  for (let i = 0; i < picks.length; i++) {
    for (let j = i + 1; j < picks.length; j++) {
      if (picks[i] < picks[j] + 200 && picks[j] < picks[i] + 200) overlap = true;
    }
  }
  check('三次互不重叠', !overlap, picks.map((p) => '0x' + p.toString(16)).join(' '));
  check('都在空闲区里', picks.every((p) => p >= 0x5dfbec));
}

const summary = failures === 0
  ? `全部通过（${lines.filter((l) => l.includes('[PASS]')).length} 条断言）`
  : `${failures} 项失败`;
lines.push('');
lines.push(summary);
console.log('');
console.log(summary);
process.exit(failures === 0 ? 0 : 1);
