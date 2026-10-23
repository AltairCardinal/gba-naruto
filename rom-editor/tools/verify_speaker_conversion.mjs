// 说话人名表**转换成指针表**的无头验收（第十八轮）。
//
// 用法：node rom-editor/tools/verify_speaker_conversion.mjs
//
// 这道门禁断的是「定长内联槽 → 指针表 + 变长串池」这条新路：
//   S1 **没改过的内容包重建出来仍与原版逐字节相同**（转换是可选的 ——
//      这条不变量不能被转换弄丢）；
//   S2 改了一个名字之后，构建**不报错**，而且：
//       a. ROM 里的 **12 个取名读者**真的被改了（逐字节比对补丁清单）；
//       b. **指针表**落在原表的位置上（`0x085A57C4`），64 个槽都是合法指针；
//       c. **64 条名字**搬到了空闲区（串池），内容逐字节等于新文本；
//       d. 保护区里的**两张表合起来**（说话人全名表 `0x085A5AB8..0x085A5F77`
//          + 地点名表 `0x085A5F65..0x085A6342`，两者在 `0x085A5F65` 处重叠 19 字节）
//          **一个字节都没动** —— 断言按**并集**算，并且断「清单里的保护区」
//          与这两张表的并集完全相等（范围写小一个字节就红）；
//   S3 转换后「指针表 + 串池」能被**解析回来**（`parsepack.js` 认得转换后的形态）；
//      S3a 已转换形态的槽元数据没被解析坏：`capacity` = 名字长度 + 1、`pointer` 有值。
//   S4 转换**前**的形态（定长内联槽，每条 12 字节）能被**解析回来** ——
//      `capacity` 全是 **12**（不是「名字长度 + 1」）、`raw` 是**整槽 12 字节**
//      （含 NUL 与填充）、`pointer` 为空，且与内容包里记的逐字段相同；
//   S5 往返不变量：原版 ROM 解析出来的包**重建**出来仍与原版逐字节相同
//      （6,291,456 字节全等）—— 证明「按 12 字节整槽读」没有把填充字节丢掉。
//   S6 **补丁末尾的填充指令**必须是 `0x46C0`（Thumb `mov r8, r8`）——
//      **不能是 `0xBF00`**：ARMv4T（GBA 的 ARM7TDMI）上 `0xBFxx` 本身就是
//      **未定义指令**（`NOP/YIELD/WFE/WFI/SEV` 这些 hint 指令是 ARMv5T 才有的；
//      mGBA 自己的反汇编器把它打成 `ill`）⇒ Undefined Instruction 异常
//      ⇒ BIOS 异常向量 ⇒ 异常返回按偶数地址回跳 ⇒ CPU 切进 ARM 状态
//      ⇒ 再执行 `0xBF000000` ⇒ **无限异常循环** ⇒ 画面永远不再推进。
//      依据：notes/evidence/speaker-name-freeze-trace-20261023.md §0 / §3.2 / §4.0。
//   S7 **清单与内容包里的 14 处补丁逐字节一致**（`tools/data/speaker_name_code_patches.json`
//      与 `rom-editor/content/pack.json`）—— 防「清单改了、内容包没改」的漂移。
//
// 依据：notes/evidence/speaker-name-table-20261023.md
// 　　　notes/evidence/speaker-name-code-patches-20261023.md
import { readFileSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const repoRoot = join(here, '..', '..');
const packPath = join(repoRoot, 'rom-editor', 'content', 'pack.json');
const romPath = join(repoRoot, 'rom', 'base.gba');
const patchPath = join(repoRoot, 'tools', 'data', 'speaker_name_code_patches.json');

const { ContentPack } = await import('../js/pack.js');
const { buildRom } = await import('../js/rom.js');
const { parsePackFromRom } = await import('../js/parsepack.js');
const { bytesToHex, hexToBytes, base64ToBytes } = await import('../js/bytes.js');
const { encodeTokens } = await import('../js/textcodec.js');

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

const packData = JSON.parse(readFileSync(packPath, 'utf8'));
const rom = new Uint8Array(readFileSync(romPath));
const patchData = JSON.parse(readFileSync(patchPath, 'utf8'));

function freshPack() {
  const pack = ContentPack.fromJSON(JSON.parse(readFileSync(packPath, 'utf8')));
  pack.patches = [];
  return pack;
}

/**
 * `buildRom` 在构建出错时会**抛异常**（`rom.js` 的 `BuildError`）。
 * 门禁要**干净地红**，不能崩在半路 —— 这里把异常变成一条普通的失败。
 */
function safeBuild(pack, rom) {
  try {
    const out = buildRom(pack, rom);
    return { ok: true, bytes: out.bytes, report: out.report };
  } catch (err) {
    return { ok: false, bytes: null, report: { errors: [String((err && err.message) || err)], conversions: [] } };
  }
}

const SPEAKER_BASE = 0x5a57c4;      // 文件偏移
const FULLNAME_BASE = 0x5a5ab8;     // 全名表第 0 条（保护区）
const ROM_BASE = 0x08000000;

head('\n1) 没改过的内容包：转换**不触发**，重建逐字节相同');
{
  const pack = freshPack();
  const out = buildRom(pack, rom);
  check('构建无错误', out.report.errors.length === 0, out.report.errors.join('; '));
  check('没有发生转换', (out.report.conversions || []).length === 0);
  let diff = -1;
  for (let i = 0; i < rom.length; i++) {
    if (out.bytes[i] !== rom[i]) { diff = i; break; }
  }
  check('逐字节与原版相同', diff === -1,
    diff === -1 ? `${rom.length} 字节全等` : `0x${diff.toString(16).toUpperCase()} 处不同`);
}

head('\n2) 改一个名字 ⇒ 转换发生');
let built = null;
{
  const pack = freshPack();
  const table = pack.textTable('speaker_names');
  check('说话人名表标着「可转换」', table.convert === 'speaker_names', String(table.convert));
  const record = table.records.find((r) => r.id === 1);   // id 1 = 「鸣人」
  const original = record.text;
  const longer = `${original}测试`;
  pack.setText(table, record, longer);
  const out = buildRom(pack, rom);
  built = out;
  check('构建无错误', out.report.errors.length === 0, out.report.errors.join('; '));
  check('报告里有转换记录', (out.report.conversions || []).length === 1,
    JSON.stringify(out.report.conversions || []));
  check('64 条名字都进了串池',
    out.report.movedTexts.filter((m) => m.table === 'speaker_names').length === 64,
    `${out.report.movedTexts.filter((m) => m.table === 'speaker_names').length} 条`);
}

head('\n3) ROM 里的 12 个取名读者真的被改了');
{
  const out = built;
  let allMatch = true;
  const bad = [];
  for (const patch of patchData.patches) {
    const offset = parseInt(String(patch.rom_offset), 0);
    const before = hexToBytes(patch.before_hex);
    const after = hexToBytes(patch.after_hex);
    const actual = out.bytes.subarray(offset, offset + before.length);
    if (bytesToHex(actual) !== bytesToHex(after)) {
      allMatch = false;
      if (bad.length < 4) {
        bad.push(`${patch.site || patch.reader} @0x${offset.toString(16).toUpperCase()}`);
      }
    }
  }
  check(`全部 ${patchData.patches.length} 处补丁逐字节落地`, allMatch, bad.join('、'));
  check('补丁长度都没变（不挪动后续代码）',
    patchData.patches.every((p) => p.before_hex.length === p.after_hex.length));
}

head('\n4) 指针表落在原表的位置上，64 个槽都是合法指针');
{
  const out = built;
  const pool = out.report.movedTexts.filter((m) => m.table === 'speaker_names');
  const pointers = [];
  for (let id = 0; id < 64; id++) {
    const at = SPEAKER_BASE + id * 4;
    const value = (out.bytes[at] | (out.bytes[at + 1] << 8)
      | (out.bytes[at + 2] << 16) | (out.bytes[at + 3] << 24)) >>> 0;
    pointers.push(value);
  }
  const allValid = pointers.every((p) => p >= ROM_BASE && p < ROM_BASE + rom.length);
  check('64 个指针都落在 ROM 内', allValid,
    pointers.slice(0, 3).map((p) => '0x' + p.toString(16).toUpperCase()).join(' '));
  const inPool = pointers.every((p) => p - ROM_BASE >= 0x5dfbec);
  check('64 个指针都指向空闲区里的串池', inPool);
  check('指针表没有超出原表的范围',
    SPEAKER_BASE + 64 * 4 <= FULLNAME_BASE,
    `0x${(SPEAKER_BASE + 64 * 4).toString(16).toUpperCase()} < 0x${FULLNAME_BASE.toString(16).toUpperCase()}`);
}

head('\n5) 保护区：**说话人全名表 + 地点名表**两张表合起来逐字节未动');
{
  const out = built;

  // 两张表的**声明范围**（文件偏移，[lo, hi) 口径）——
  //   说话人全名表 0x5A5AB8 起，19 字节/条 × 64 条（id 0..63）⇒ [0x5A5AB8, 0x5A5F78)
  //   地点名表     0x5A5F65 起，18 字节/条 × 55 条（id 0..54）⇒ [0x5A5F65, 0x5A6343)
  //
  // 两者在 0x5A5F65..0x5A5F77 这 19 字节上**重叠**（全名表 id 63 与地点名表 id 0
  // 是同一批「没有」字节），所以并集必须**按并集算**，不能相加、也不能漏。
  const FULLNAME_TABLE = { lo: 0x5a5ab8, hi: 0x5a5f78 };
  const LOCATION_TABLE = { lo: 0x5a5f65, hi: 0x5a6343 };
  const unionLo = Math.min(FULLNAME_TABLE.lo, LOCATION_TABLE.lo);
  const unionHi = Math.max(FULLNAME_TABLE.hi, LOCATION_TABLE.hi);

  // 清单（`tools/data/speaker_name_code_patches.json`）里的保护区是**唯一口径** ——
  // 门禁断它与上面两张表的并集**完全相等**（不多不少）。
  // ⚠️ 这条断言是护栏的**牙齿**：保护区范围写小一个字节（无论改清单还是改这里
  // 的表范围），它立刻变红。
  const manifestRegion = (patchData.table && patchData.table.protected_region_file_offset) || [];
  const mLo = parseInt(String(manifestRegion[0]), 0);
  const mHi = parseInt(String(manifestRegion[1]), 0);
  check(`清单里的保护区 = 两张表的并集（0x${unionLo.toString(16).toUpperCase()}..`
    + `0x${unionHi.toString(16).toUpperCase()}，${unionHi - unionLo} 字节）`,
    mLo === unionLo && mHi === unionHi,
    `清单 0x${mLo.toString(16).toUpperCase()}..0x${mHi.toString(16).toUpperCase()}`);

  // 两张表**合起来**（并集）逐字节未动。
  const before = rom.subarray(unionLo, unionHi);
  const after = out.bytes.subarray(unionLo, unionHi);
  check(`0x${unionLo.toString(16).toUpperCase()}..0x${(unionHi - 1).toString(16).toUpperCase()}`
    + `（${unionHi - unionLo} 字节）逐字节相同`,
    bytesToHex(before) === bytesToHex(after));

  // ⚠️ 上面那条「逐字节相同」**单靠自己没有牙齿**：转换根本不写保护区，
  // 所以哪怕保护区范围写错了它照样绿。⇒ **变异对照**：故意改掉保护区里的
  // 一个字节，比较必须能发现（首字节 = 全名表 id 0，末字节 = 地点名表 id 54）。
  const mutantHead = Uint8Array.from(out.bytes);
  mutantHead[unionLo] ^= 0xff;
  check('变异对照：保护区**首字节**被改 ⇒ 比较能发现（断言不是空转）',
    bytesToHex(rom.subarray(unionLo, unionHi))
      !== bytesToHex(mutantHead.subarray(unionLo, unionHi)));

  const mutantTail = Uint8Array.from(out.bytes);
  mutantTail[unionHi - 1] ^= 0xff;
  check('变异对照：保护区**末字节**被改 ⇒ 比较能发现（断言不是空转）',
    bytesToHex(rom.subarray(unionLo, unionHi))
      !== bytesToHex(mutantTail.subarray(unionLo, unionHi)));

  // 保护区**两端**必须正好是两张表的边界（不是随便一段）：
  // 首字节是「没有」（全名表 id 0 = 简称表 id 63），末字节是地点名表 id 54 的填充。
  const headBytes = rom.subarray(unionLo, unionLo + 5);
  check('保护区首字节 = 「没有」（92 59 9a 9a 00）—— 全名表 id 0 = 简称表 id 63',
    bytesToHex(headBytes) === '92599a9a00',
    bytesToHex(headBytes));
  const tailBytes = rom.subarray(unionHi - 1, unionHi);
  check('保护区末字节 = 地点名表 id 54 的填充 0x00',
    bytesToHex(tailBytes) === '00',
    bytesToHex(tailBytes));
}

head('\n6) 串池里的名字逐字节等于新文本');
{
  const out = built;
  const pack = freshPack();
  const table = pack.textTable('speaker_names');
  const record = table.records.find((r) => r.id === 1);
  // ⚠️ `setText` 会**就地改** `record.text` —— 先把原文存下来。
  const newText = `${record.text}测试`;
  pack.setText(table, record, newText);
  const expected = encodeTokens(pack.font.encodeTokens(newText));
  const moved = out.report.movedTexts.find((m) => m.table === 'speaker_names' && m.id === 1);
  check('找到了 id 1 的新位置', !!moved,
    moved ? `0x${moved.to.toString(16).toUpperCase()}` : '没找到');
  if (moved) {
    const written = out.bytes.subarray(moved.to, moved.to + expected.length);
    check('串池里的字节逐字节等于新文本', bytesToHex(written) === bytesToHex(expected),
      `${expected.length} 字节`);
    check('串池里紧跟一个 NUL', out.bytes[moved.to + expected.length] === 0);
  }
}

head('\n7) 转换后的 ROM 能被解析回来');
{
  const out = built;
  const template = ContentPack.fromJSON(JSON.parse(readFileSync(packPath, 'utf8')));
  const parsed = parsePackFromRom(template, out.bytes, { name: 'reloc.gba', sha256: '' });
  const table = parsed.pack.texts.find((t) => t.id === 'speaker_names');
  const record = table.records.find((r) => r.id === 1);
  check('解析出来的 id 1 是新文本',
    record.text === `${record.original_text}` && record.text.includes('测试'),
    JSON.stringify(record.text));
  const others = table.records.filter((r) => r.id !== 1);
  const allOk = others.every((r) => r.text === r.original_text && r.text.length > 0);
  check('其余 63 条名字也解析回来了', allOk,
    `${others.filter((r) => r.text && r.text.length > 0).length} / ${others.length}`);

  // S3a：**已转换形态的槽元数据**没被解析坏 ——
  // 指针表形态里 `raw` 是**名字内容**（不含 NUL），`capacity` = 内容长度 + 1，
  // `pointer` 指着串池里那串名字。（`parsepack.js` 认得两种形态，这条断的是
  // 「别把已转换的 ROM 当成定长内联槽读」。）
  const convMeta = table.records.filter((r) => {
    const raw = base64ToBytes(r.raw);
    return raw.length + 1 !== r.capacity
      || r.pointer === null || r.pointer === undefined;
  });
  check('转换后：capacity = 名字长度 + 1、pointer 有值（64 条）',
    table.records.length === 64 && convMeta.length === 0,
    convMeta.length ? convMeta.slice(0, 4).map((r) => `#${r.id}`).join('、')
      : `capacity 集合 ${JSON.stringify([...new Set(table.records.map((r) => r.capacity))])}`);
  const convBytes = table.records.filter((r) => {
    const at = r.pointer - ROM_BASE;
    const raw = base64ToBytes(r.raw);
    if (at < 0 || at + raw.length > out.bytes.length) return true;
    return bytesToHex(out.bytes.subarray(at, at + raw.length)) !== bytesToHex(raw);
  });
  check('转换后：raw 就是指针指的那串名字（逐字节）', convBytes.length === 0,
    convBytes.length ? convBytes.slice(0, 4).map((r) => `#${r.id}`).join('、') : '64 条全对');
}

head('\n8) 原版 ROM（**未转换**）：说话人名表是定长内联槽，每条 12 字节');
{
  const template = ContentPack.fromJSON(JSON.parse(readFileSync(packPath, 'utf8')));
  const parsed = parsePackFromRom(template, rom, { name: 'base.gba' });
  const table = parsed.pack.texts.find((t) => t.id === 'speaker_names');
  check('解析出 64 条名字', table.records.length === 64, `${table.records.length} 条`);

  // S4 的一条：**槽的容量是 12**（定长内联槽的大小），
  // 不是「名字长度 + 1」—— 后者是「把内联槽当 C 串读」的结果。
  const caps = [...new Set(table.records.map((r) => r.capacity))];
  check('64 条的 capacity 全是 12（槽的大小）',
    caps.length === 1 && caps[0] === 12, `capacity 取值集合：${JSON.stringify(caps)}`);

  // S4 的另一条：**raw 是整个槽**（内容 + NUL + 填充），12 字节。
  const rawLens = [...new Set(table.records.map((r) => base64ToBytes(r.raw).length))];
  check('64 条的 raw 全是 12 字节（整槽：内容 + NUL + 填充）',
    rawLens.length === 1 && rawLens[0] === 12, `raw 长度集合：${JSON.stringify(rawLens)}`);

  // 内联槽**没有指针**。
  const noPointer = table.records.every((r) => r.pointer === null || r.pointer === undefined);
  check('64 条的 pointer 都是空（内联槽没有指针）', noPointer);

  // raw 就是 ROM 里那 12 个字节 —— 填充字节没丢。
  const slotMismatch = table.records.filter((r) => {
    const raw = base64ToBytes(r.raw);
    const at = r.text_offset;
    if (raw.length !== 12 || at === null || at === undefined) return true;
    if (at + 12 > rom.length) return true;
    return bytesToHex(raw) !== bytesToHex(rom.subarray(at, at + 12));
  });
  check('每条 raw 就是 ROM 里那 12 个字节（含 NUL 与填充）',
    slotMismatch.length === 0,
    slotMismatch.length ? slotMismatch.slice(0, 4).map((r) => `#${r.id}`).join('、') : '64 条全对');

  // ⚠️ 上面那条有个盲区：**形态判错**（比如把原版 ROM 误判成「已转换」）时，
  // 解析器会**跳过**全部 64 条 ⇒ 包里留着**模板的旧值** —— 而模板值恰好就是
  // ROM 里那 12 个字节 ⇒ 上面的断言**照样全绿**。
  // 「实际读到了几条」才能分辨这两件事。
  check('说话人名表实际从 ROM 读到 64 条（不是静默留着模板的值）',
    parsed.report.textsRead.speaker_names === 64,
    `读了 ${parsed.report.textsRead.speaker_names} 条`);

  // 更硬的一条：**改 ROM 里的一个字节**，解析回来的 raw 必须跟着变 ——
  // 只有真的从 ROM 里读过才会这样；「留着模板的值」的话 raw 不会动。
  {
    const patched = new Uint8Array(rom);
    patched[SPEAKER_BASE] = patched[SPEAKER_BASE] ^ 0x01;
    const again = parsePackFromRom(template, patched, { name: 'patched.gba' });
    const table2 = again.pack.texts.find((t) => t.id === 'speaker_names');
    const record0 = table2.records.find((r) => r.id === 0);
    const raw0 = base64ToBytes(record0.raw);
    check('改 ROM 里的一个字节 ⇒ 解析回来的 raw 跟着变（证明是从 ROM 读的）',
      raw0.length === 12 && raw0[0] === patched[SPEAKER_BASE]
      && raw0[0] !== rom[SPEAKER_BASE],
      `raw[0]=0x${raw0[0].toString(16).toUpperCase()}` +
      `（ROM 里原来是 0x${rom[SPEAKER_BASE].toString(16).toUpperCase()}）`);
  }

  // 文本没坏。
  const textsOk = table.records.every((r) => r.text === r.original_text && r.text.length > 0);
  check('64 条名字的文本都读回来了', textsOk);

  // 最强的一条：解析原版 ROM 得到的说话人名表，必须与**内容包里记的**逐字段相同
  // —— 内容包记的就是「12 字节的定长内联槽」。形态判错（把内联槽当 C 串读）
  // ⇒ `raw` / `capacity` 与内容包对不上 ⇒ 这里红。
  const authored = template.texts.find((t) => t.id === 'speaker_names');
  const diffs = [];
  for (const a of authored.records) {
    const b = table.records.find((r) => r.id === a.id);
    if (!b) { diffs.push(`#${a.id}`); continue; }
    for (const key of new Set([...Object.keys(a), ...Object.keys(b)])) {
      if (JSON.stringify(a[key]) !== JSON.stringify(b[key])) diffs.push(`#${a.id}.${key}`);
    }
  }
  check('解析原版 ROM：说话人名表与内容包里记的逐字段相同',
    diffs.length === 0,
    diffs.length ? diffs.slice(0, 6).join('、') : '64 条 × 全部字段');
}

head('\n9) 往返不变量：原版 ROM 解析出来的包，重建后与原版逐字节相同');
{
  const template = ContentPack.fromJSON(JSON.parse(readFileSync(packPath, 'utf8')));
  const parsed = parsePackFromRom(template, rom, { name: 'base.gba' });
  const out = safeBuild(ContentPack.fromJSON(JSON.parse(JSON.stringify(parsed.pack))), rom);
  check('重建无错误', out.ok && out.report.errors.length === 0,
    out.report.errors.join('; '));
  let firstDiff = -1;
  if (out.bytes) {
    for (let i = 0; i < rom.length; i++) {
      if (out.bytes[i] !== rom[i]) { firstDiff = i; break; }
    }
  }
  check('重建出来的 ROM 与原版逐字节相同',
    out.ok && out.bytes && out.bytes.length === rom.length && firstDiff === -1,
    firstDiff === -1 ? `${rom.length} 字节全等` : `0x${firstDiff.toString(16).toUpperCase()} 处不同`);
  // 没改过的内容包**不该触发转换** —— 触发了就说明「按整槽读」把字节读坏了。
  check('重建没有触发转换（没改过就不转换）',
    (out.report.conversions || []).length === 0,
    JSON.stringify(out.report.conversions || []));
}

head('\n10) 补丁末尾的填充指令：必须是 0x46C0（**0xBF00 在 ARMv4T 上是未定义指令**）');
{
  // 根因（第十九轮修掉的那个）：`0xBF00` 是 Thumb `nop` 的编码，但**在 ARMv4T
  // （GBA 的 ARM7TDMI）上它本身就是未定义指令** —— hint 指令（NOP/YIELD/WFE/WFI/SEV）
  // 是 ARMv5T 才有的（mGBA 自己的反汇编器在那一格打出来的是 `BF00: ill`）。
  // 于是撞上它就抛 Undefined Instruction：
  //   ⇒ 进 BIOS 异常向量 0x00000008
  //   ⇒ 异常返回按 Thumb 地址的**偶数**回跳 ⇒ CPU **切进 ARM 状态**
  //   ⇒ 再执行 0xBF000000 ⇒ 又是未定义指令 ⇒ **无限异常循环** ⇒ 画面永远不再推进。
  // 依据：notes/evidence/speaker-name-freeze-trace-20261023.md §0 / §3.2 / §4.0（已实测确认）
  const SAFE_FILLER = 'c046';    // 0x46C0 = Thumb `mov r8, r8`：合法、不写标志位、不改寄存器、2 字节
  const BANNED_FILLER = '00bf';  // 0xBF00 = Thumb `nop` 的编码 —— **ARMv4T 上是未定义指令**
  const hex = (s) => String(s || '').toLowerCase();

  const banned = patchData.patches.filter((p) => hex(p.after_hex).endsWith(BANNED_FILLER));
  check(`14 处补丁末尾都没有 0xBF00（ARMv4T 未定义指令 ⇒ 异常死循环 ⇒ 卡死）`,
    banned.length === 0,
    banned.map((p) => `${p.site}=${hex(p.after_hex).slice(-4)}`).join('、'));

  const notSafe = patchData.patches.filter((p) => !hex(p.after_hex).endsWith(SAFE_FILLER));
  check('14 处补丁末尾的填充指令都是 0x46C0（mov r8, r8）',
    notSafe.length === 0,
    notSafe.map((p) => `${p.site}=${hex(p.after_hex).slice(-4)}`).join('、'));

  // 补丁长度不变 ⇒ 不挪动任何后续代码（这条是填充指令能「原地换掉」的前提）。
  check('填充指令换掉之后补丁长度仍然不变',
    patchData.patches.every((p) => p.before_hex.length === p.after_hex.length));

  // `new_disasm` 的最后一条就是那条填充指令 —— 不能再写 `nop`。
  const nopTail = patchData.patches.filter((p) => {
    const dis = p.new_disasm || [];
    return dis.length > 0 && /^nop\b/.test(String(dis[dis.length - 1]).trim());
  });
  check('new_disasm 的最后一条不再是 nop', nopTail.length === 0,
    nopTail.map((p) => p.site).join('、'));

  // 反汇编文本要和字节对得上：0x46C0 ⇔ `mov r8, r8`。
  const mismatched = patchData.patches.filter((p) => {
    const dis = p.new_disasm || [];
    const tail = dis.length ? String(dis[dis.length - 1]).trim() : '';
    return hex(p.after_hex).endsWith(SAFE_FILLER) ? tail !== 'mov r8, r8' : false;
  });
  check('new_disasm 末条与填充字节一致（c046 ⇔ `mov r8, r8`）',
    mismatched.length === 0,
    mismatched.map((p) => `${p.site}=${(p.new_disasm || []).slice(-1)[0]}`).join('、'));

  // 真正落到 ROM 里的字节也得是安全填充（清单对了、内容包错了也要红）。
  if (built) {
    const romBanned = patchData.patches.filter((p) => {
      const offset = parseInt(String(p.rom_offset), 0);
      const after = hexToBytes(p.after_hex);
      const tail = bytesToHex(built.bytes.subarray(offset + after.length - 2, offset + after.length));
      return tail === BANNED_FILLER;
    });
    check('转换后 ROM 里落地的填充字节没有 0xBF00', romBanned.length === 0,
      romBanned.map((p) => p.site).join('、'));
    const romSafe = patchData.patches.filter((p) => {
      const offset = parseInt(String(p.rom_offset), 0);
      const after = hexToBytes(p.after_hex);
      const tail = bytesToHex(built.bytes.subarray(offset + after.length - 2, offset + after.length));
      return tail !== SAFE_FILLER;
    });
    check('转换后 ROM 里落地的填充字节都是 0x46C0', romSafe.length === 0,
      romSafe.map((p) => p.site).join('、'));
  }
}

head('\n11) 清单与内容包里的 14 处补丁逐字节一致（防「清单改了、内容包没改」的漂移）');
{
  const packPatches = (packData.conversions
    && packData.conversions.speaker_names
    && packData.conversions.speaker_names.code_patches) || [];
  check('内容包里也有 14 处补丁',
    packPatches.length === patchData.patches.length,
    `清单 ${patchData.patches.length} 处 / 内容包 ${packPatches.length} 处`);

  const drift = [];
  for (const p of patchData.patches) {
    const offset = parseInt(String(p.rom_offset), 0);
    const twin = packPatches.find((q) => Number(q.offset) === offset);
    if (!twin) {
      drift.push(`${p.site}@0x${offset.toString(16).toUpperCase()}：内容包里没有`);
      continue;
    }
    if (String(twin.before_hex).toLowerCase() !== String(p.before_hex).toLowerCase()) {
      drift.push(`${p.site}@0x${offset.toString(16).toUpperCase()}：before_hex 不同`);
    }
    if (String(twin.after_hex).toLowerCase() !== String(p.after_hex).toLowerCase()) {
      drift.push(`${p.site}@0x${offset.toString(16).toUpperCase()}：after_hex 不同`
        + `（清单 ${String(p.after_hex).slice(-4)} / 内容包 ${String(twin.after_hex).slice(-4)}）`);
    }
  }
  check('清单与内容包的 14 处补丁逐字节一致（offset / before_hex / after_hex）',
    drift.length === 0, drift.slice(0, 6).join('、'));

  // 内容包里的那 14 条**自己**也不能带 0xBF00（漂移的另一面）。
  const packBanned = packPatches.filter((q) => String(q.after_hex || '').toLowerCase().endsWith('00bf'));
  check('内容包里的 14 处补丁末尾也没有 0xBF00', packBanned.length === 0,
    packBanned.length ? String(packBanned[0].after_hex).slice(-4) : '');
}

const summary = failures === 0
  ? `全部通过（${lines.filter((l) => l.includes('[PASS]')).length} 条断言）`
  : `${failures} 项失败`;
lines.push('');
lines.push(summary);
console.log('');
console.log(summary);
process.exit(failures === 0 ? 0 : 1);
