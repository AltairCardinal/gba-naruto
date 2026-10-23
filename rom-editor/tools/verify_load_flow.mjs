// 载入状态条 与「从 ROM 解析内容包」的无头验收（第十五轮）。
//
// 用法：node rom-editor/tools/verify_load_flow.mjs
//
// stdout 在 PowerShell 下会被 GBK 弄乱，所以正文写到
// build/load-flow-verify.txt。
import { readFileSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

import { installDom, StubNode } from './domstub.mjs';

installDom();

const here = dirname(fileURLToPath(import.meta.url));
const repoRoot = join(here, '..', '..');
const packPath = join(repoRoot, 'rom-editor', 'content', 'pack.json');
const romPath = join(repoRoot, 'rom', 'base.gba');

const { ContentPack } = await import('../js/pack.js');
const { renderLoadBar, confirmOverwrite } = await import('../js/loadbar.js');
const { parsePackFromRom } = await import('../js/parsepack.js');
const { buildRom } = await import('../js/rom.js');
const { base64ToBytes } = await import('../js/bytes.js');

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

/** 画一次载入状态条，返回两个槽的文本。 */
function draw(view) {
  const romSlot = new StubNode('div');
  const packSlot = new StubNode('div');
  renderLoadBar(romSlot, packSlot, view, {});
  return { rom: romSlot, pack: packSlot, romText: romSlot.textContent, packText: packSlot.textContent };
}

/**
 * `buildRom` 在构建有 error 时会**抛异常**（`rom.js` 的 `BuildError`）。
 * 门禁要**干净地红**，不能崩在半路 —— 这里把异常变成一条普通的失败。
 */
function safeBuild(pack, rom) {
  try {
    const out = buildRom(pack, rom);
    return { ok: true, bytes: out.bytes, report: out.report };
  } catch (err) {
    return { ok: false, bytes: null, report: { errors: [String((err && err.message) || err)] } };
  }
}

const baseView = {
  rom: { loaded: false, name: null, size: 0, sha: null },
  pack: { loaded: false, source: null, structures: 0, texts: 0, changed: false },
};

head('\n1) 载入状态条：ROM 槽');
{
  const none = draw(baseView);
  check('未载入时给「二选一」：内置原版 + 在本地浏览上传',
    none.romText.includes('木叶战记熊组汉化版原版') && none.romText.includes('在本地浏览上传'),
    none.romText);
  check('未载入时没有 √', !none.romText.includes('√'), none.romText);
  check('未载入时没有「卸载」', !none.romText.includes('卸载'), none.romText);

  const loaded = draw({
    ...baseView,
    rom: { loaded: true, name: 'base.gba', size: 6291456, sha: '1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b' },
  });
  check('已载入时有绿底白 √', loaded.romText.includes('√'), loaded.romText);
  check('已载入时写着文件名 / 字节数 / sha256',
    loaded.romText.includes('base.gba') && loaded.romText.includes('6,291,456')
    && loaded.romText.includes('1198ece781a'), loaded.romText);
  check('已载入时给「导出修改后卸载 ROM」',
    loaded.romText.includes('导出修改后卸载 ROM'), loaded.romText);
  check('已载入时**不再**提供载入别的 ROM 的入口',
    !loaded.romText.includes('木叶战记熊组汉化版原版') && !loaded.romText.includes('在本地浏览上传'),
    loaded.romText);
}

head('\n2) 载入状态条：内容包槽');
{
  const none = draw(baseView);
  check('未载入时给「二选一」：从 ROM 中解析 + 在本地浏览上传',
    none.packText.includes('从 ROM 中解析') && none.packText.includes('在本地浏览上传'),
    none.packText);
  check('未载入时没有 √', !none.packText.includes('√'), none.packText);

  const loaded = draw({
    ...baseView,
    rom: { loaded: true, name: 'base.gba', size: 6291456, sha: null },
    pack: { loaded: true, source: 'rom', structures: 116, texts: 11, changed: false },
  });
  check('已载入时有 √', loaded.packText.includes('√'), loaded.packText);
  check('已载入时注明「从 ROM 中解析」', loaded.packText.includes('从 ROM 中解析'), loaded.packText);
  check('已载入时有【载入】', loaded.packText.includes('载入'), loaded.packText);
  check('没有修改时**没有**【导出】',
    !loaded.packText.split('从 ROM 中解析')[1].includes('导出'), loaded.packText);

  const changed = draw({
    ...baseView,
    rom: { loaded: true, name: 'base.gba', size: 6291456, sha: null },
    pack: { loaded: true, source: 'rom', structures: 116, texts: 11, changed: true },
  });
  check('有修改时【导出】出现在【载入】后面',
    changed.packText.indexOf('导出') > changed.packText.indexOf('载入')
    && changed.packText.includes('导出'), changed.packText);
}

head('\n3) 覆盖前的确认框');
{
  const before = globalThis.document.body.children.length;
  confirmOverwrite(() => {});
  const after = globalThis.document.body.children.length;
  check('确认框被挂出来了', after === before + 1, `${before} → ${after}`);
  const overlay = globalThis.document.body.children[after - 1];
  const text = overlay.textContent;
  check('文案一字不差',
    text.includes('当前有未导出过的修改，载入新内容包会导致当前变动被覆盖，是否确认？'), text);
  const buttons = overlay.descendants().filter((n) => n.tagName === 'BUTTON');
  const no = buttons.find((b) => b.textContent === '否');
  const yes = buttons.find((b) => b.textContent === '是');
  check('有「否」和「是」两个按钮', !!no && !!yes,
    buttons.map((b) => b.textContent).join('/'));
  check('**「否」是高亮按钮**',
    !!no && String(no.className).includes('btn-primary')
    && (!yes || !String(yes.className).includes('btn-primary')),
    `否=${no ? no.className : '—'}　是=${yes ? yes.className : '—'}`);
  overlay.remove();
}

head('\n4) 从 ROM 解析出的内容包：原版 ROM（说话人名表**未转换**）');
{
  const template = ContentPack.fromJSON(JSON.parse(readFileSync(packPath, 'utf8')));
  const rom = new Uint8Array(readFileSync(romPath));
  const { pack, report } = parsePackFromRom(template, rom, { name: 'base.gba' });
  check('结构表逐表相等',
    JSON.stringify(template.structures) === JSON.stringify(pack.structures),
    `${report.structures} 张`);
  check('剧本元信息逐条相等',
    JSON.stringify(template.scripts) === JSON.stringify(pack.scripts),
    `${report.scripts} 条`);

  // 文本表：**11 张整表**必须一模一样 ——
  //
  // （曾经误解过：「`speaker_names` 现在是『可转换』的表 ⇒ 解析回来时
  //  `raw`/`capacity` 会按『槽里 NUL 之前的内容』重算 ⇒ 整表 JSON 不可能再相同」。
  //  那描述的是**形态判错**（把内联槽当成 C 串读）的行为，**不是现在的行为**：
  //  原版 ROM 里 `speaker_names` 还是**定长内联槽**（每条 12 字节），解析器按
  //  整槽读回来 ⇒ `raw`（内容 + NUL + 填充）与 `capacity`（12）都与内容包里
  //  记的逐字段相同。形态一旦判错，`capacity` 会变成「名字长度 + 1」、
  //  `raw` 会少掉 NUL 与填充 ⇒ 下面这条断言立刻红。）
  check('11 张文本表整表 JSON 相同（解析没有改动任何一格）',
    JSON.stringify(template.texts) === JSON.stringify(pack.texts),
    `${report.texts} 张表`);

  // 逐条文本相等（整表相等的**诊断版**：第一条不同的记录是谁）。
  let textDiff = 0;
  let firstTextDiff = '';
  for (const tt of template.texts) {
    const pt = pack.texts.find((x) => x.id === tt.id);
    const records = tt.records || [];
    for (let i = 0; i < records.length; i++) {
      const a = records[i];
      const b = ((pt && pt.records) || [])[i];
      if (!b || a.text !== b.text || a.original_text !== b.original_text) {
        textDiff += 1;
        if (!firstTextDiff) firstTextDiff = `${tt.id}#${a.id}`;
      }
    }
  }
  check('文本表的文本内容逐条相等', textDiff === 0,
    textDiff ? `${textDiff} 条不同，第一条 ${firstTextDiff}` : `${report.texts} 张表`);

  // 每张表**实际从 ROM 读到了几条记录** ——
  // 「整表 JSON 相同」有个盲区：形态判错（比如把原版 ROM 误判成「已转换」）
  // 时，解析器会**跳过**全部记录 ⇒ 包里留着**模板的旧值** ⇒ 整表 JSON 照样
  // 「相同」。所以要单独断「真的读了那么多条」。
  //
  // 读到的条数 = 该表**有内容的**槽数（空槽没有字节可读，本来就该跳过：
  // `dialogue_slots` 1524 条里有 304 个空槽）。
  const slotsWithText = (tt) => (tt.records || [])
    .filter((r) => r.raw && base64ToBytes(r.raw).length > 0).length;
  const readCounts = template.texts
    .map((tt) => `${tt.id}:${(report.textsRead || {})[tt.id]}/${slotsWithText(tt)}`)
    .join(' ');
  check('11 张文本表都把有内容的槽读了一遍',
    template.texts.every((tt) =>
      (report.textsRead || {})[tt.id] === slotsWithText(tt)),
    readCounts);
  check('说话人名表实际读到 64 条（形态没判错）',
    (report.textsRead || {}).speaker_names === 64,
    `读了 ${(report.textsRead || {}).speaker_names} 条`);

  // 载入流程读出来的**字节**必须就是 ROM 里的那些字节 ——
  // （比「与模板相同」更强：模板自己错了也能抓出来）
  // `text_offset` 为空的槽是**没被读到**的槽（指针为空的空槽），
  // 它们本来就没什么字节可对 —— 跳过，但记在明细里。
  let rawDiff = 0;
  let rawSkipped = 0;
  let firstRawDiff = '';
  for (const pt of pack.texts) {
    for (const r of pt.records || []) {
      const raw = r.raw ? base64ToBytes(r.raw) : new Uint8Array(0);
      const at = r.text_offset;
      if (at === null || at === undefined) { rawSkipped += 1; continue; }
      if (at < 0 || at + raw.length > rom.length) {
        rawDiff += 1;
        if (!firstRawDiff) firstRawDiff = `${pt.id}#${r.id}（地址 ${at}）`;
        continue;
      }
      for (let i = 0; i < raw.length; i++) {
        if (rom[at + i] !== raw[i]) {
          rawDiff += 1;
          if (!firstRawDiff) firstRawDiff = `${pt.id}#${r.id}@0x${at.toString(16)}`;
          break;
        }
      }
    }
  }
  check('解析回来的字节就是 ROM 里的那些字节', rawDiff === 0,
    rawDiff ? `${rawDiff} 条对不上，第一条 ${firstRawDiff}` :
      `逐字节一致（${rawSkipped} 个空槽没读）`);

  // 解析**没有改动任何一条记录** —— 结构记录与文本记录都要 0。
  // （`textsChanged` 这一半是关键：形态判错时 64 条名字的 `raw` 全变了。）
  check('解析没有改动任何一条记录（结构 + 文本）',
    report.recordsChanged === 0 && report.textsChanged === 0,
    `结构 ${report.recordsChanged} / 文本 ${report.textsChanged}`);

  // 最强的一条：载入流程不破坏内容包 ——
  // 解析回来的包**重建**出来的 ROM 必须与原版逐字节相同。
  const rebuilt = safeBuild(ContentPack.fromJSON(pack), rom);
  let firstDiff = -1;
  if (rebuilt.bytes) {
    for (let i = 0; i < rom.length; i++) {
      if (rebuilt.bytes[i] !== rom[i]) { firstDiff = i; break; }
    }
  }
  check('解析回来的内容包重建出来的 ROM 与原版逐字节相同',
    rebuilt.ok && rebuilt.report.errors.length === 0 && firstDiff === -1,
    rebuilt.report.errors.join('; ') ||
    (firstDiff === -1 ? `${rom.length} 字节全等` : `首个差异 @0x${firstDiff.toString(16)}`));
}

head('\n5) 说话人名表转换后的 ROM：也能解析回来（变的正好是那 64 条名字）');
{
  const template = ContentPack.fromJSON(JSON.parse(readFileSync(packPath, 'utf8')));
  const rom = new Uint8Array(readFileSync(romPath));

  // 造一个「已转换」的 ROM：改一个名字 ⇒ 整张表转成「指针表 + 变长串池」
  const editor = ContentPack.fromJSON(JSON.parse(readFileSync(packPath, 'utf8')));
  const table = editor.textTable('speaker_names');
  const record = table.records.find((r) => r.id === 1);
  const newText = `${record.text}测试`;
  editor.setText(table, record, newText);
  const built = safeBuild(editor, rom);
  const buildOk = built.ok && built.report.errors.length === 0;
  check('转换后的 ROM 构建无错误', buildOk, built.report.errors.join('; '));

  // 构建炸了 ⇒ 没有 ROM 可解析 —— 后面的断言统一判失败（**干净地红**，不崩）
  const parsed = buildOk
    ? parsePackFromRom(template, built.bytes, { name: 'converted.gba' })
    : { pack: { texts: [], structures: [] }, report: { errors: ['构建失败，没有 ROM 可解析'] } };
  const pack = parsed.pack;
  const report = parsed.report;
  check('转换后的 ROM 解析无错误', report.errors.length === 0, report.errors.join('; '));

  const base = (template.conversions.speaker_names || {}).base;   // 0x5A57C4
  const pointerEnd = base + 64 * 4;

  // a. 别的 10 张文本表逐表相等（转换只该动说话人名表）
  const others = template.texts.filter((t) => !t.convert);
  const othersSame = buildOk && others.every((tt) => {
    const pt = pack.texts.find((x) => x.id === tt.id);
    return JSON.stringify(tt) === JSON.stringify(pt);
  });
  check(`转换只动说话人名表：别的 ${others.length} 张文本表逐表相等`, othersSame,
    `可转换表：${template.texts.filter((t) => t.convert).map((t) => t.id).join('、')}`);

  // b. 变化的文本记录**正好是**那 64 条说话人名
  let changedText = 0;
  const changedTables = new Set();
  for (const tt of template.texts) {
    const pt = pack.texts.find((x) => x.id === tt.id);
    for (let i = 0; i < (tt.records || []).length; i++) {
      const other = ((pt && pt.records) || [])[i];
      if (JSON.stringify(tt.records[i].raw) !== JSON.stringify(other && other.raw)) {
        changedText += 1;
        changedTables.add(tt.id);
      }
    }
  }
  check('变化的文本记录正好是那 64 条说话人名',
    buildOk && changedText === 64 && changedTables.size === 1 && changedTables.has('speaker_names'),
    `变了 ${changedText} 条，涉及 ${[...changedTables].join('、') || '无'}`);

  // c. 结构表：只有**被指针表盖到**的那条记录变了（其余结构表一个字节都没动）
  const changedStruct = [];
  for (const ts of template.structures) {
    const ps = pack.structures.find((x) => x.id === ts.id);
    for (let i = 0; i < (ts.records || []).length; i++) {
      const a = ts.records[i];
      const b = ((ps && ps.records) || [])[i];
      if (!b || JSON.stringify(a.raw) !== JSON.stringify(b.raw)) {
        const size = ts.entry_size || a.raw_bytes || 0;
        changedStruct.push({
          label: `${ts.id}#${a.id}`,
          covered: a.rom_offset < pointerEnd && (a.rom_offset + size) > base,
        });
      }
    }
  }
  check('结构表：只有被指针表盖到的那条记录变了',
    buildOk && changedStruct.every((c) => c.covered),
    changedStruct.length
      ? changedStruct.slice(0, 8).map((c) => c.label).join('、')
      : '没有结构记录变');

  // d. 64 条名字的**地址**都搬到了串池（text_offset / pointer 指向池里的新地址），
  //    **文本**只变了改过的那一条 —— 其余 63 条一个字都不能动。
  const before = template.texts.find((t) => t.id === 'speaker_names');
  const after = pack.texts.find((t) => t.id === 'speaker_names');
  const afterRecords = (after && after.records) || [];
  let addrMoved = 0;
  const textChanged = [];
  for (let i = 0; i < afterRecords.length; i++) {
    const b = before.records[i];
    const a = afterRecords[i];
    if (a.pointer >= 0x08000000 && a.text_offset !== b.text_offset) addrMoved += 1;
    if (a.text !== b.text) textChanged.push(a.id);
  }
  check('64 条名字的地址都搬到了串池', buildOk && addrMoved === 64,
    `${addrMoved}/64 条的 text_offset / pointer 换了新地址`);
  check('文本只变了改过的那一条（其余 63 条原文）',
    buildOk &&
    textChanged.length === 1 && textChanged[0] === 1 &&
    afterRecords[1] && afterRecords[1].text === newText &&
    afterRecords.slice(2).every((r, i) => r.text === before.records[i + 2].text),
    `变了 ${textChanged.length} 条：${textChanged.join('、') || '无'}`);
}

head('\n6) ROM 改了，解析出来的内容包要跟着改');
{
  const template = ContentPack.fromJSON(JSON.parse(readFileSync(packPath, 'utf8')));
  const rom = new Uint8Array(readFileSync(romPath));
  // 改角色 #3 的 hp_base：内容包里它在记录内的 +0xA。
  const structure = template.structure('character_template');
  const record = structure.records.find((r) => r.id === 3);
  const field = structure.fields.find((f) => f.key === 'hp_base');
  const at = record.rom_offset + field.offset;
  const patched = new Uint8Array(rom);
  patched[at] = 99;
  const { pack } = parsePackFromRom(template, patched, { name: 'patched.gba' });
  const parsed = pack.structures.find((s) => s.id === 'character_template')
    .records.find((r) => r.id === 3);
  check('改过的那个字节被读回来了', parsed.values.hp_base === 99,
    `hp_base = ${parsed.values.hp_base}`);
  check('没改的那些字段原样',
    parsed.values.stat_a === record.values.stat_a
    && parsed.values.jutsu_0_id === record.values.jutsu_0_id,
    `stat_a=${parsed.values.stat_a} jutsu_0_id=${parsed.values.jutsu_0_id}`);
  // 别处的剧本不该跟着变
  const other = pack.scripts.find((s) => s.id === 'before.7');
  const templateOther = template.scripts.find((s) => s.id === 'before.7');
  check('别的剧本的元信息不变',
    JSON.stringify(other) === JSON.stringify(templateOther), '');
}

const summary = failures === 0
  ? `全部通过（${lines.filter((l) => l.includes('[PASS]')).length} 条断言）`
  : `${failures} 项失败`;
lines.push('');
lines.push(summary);
writeFileSync(join(repoRoot, 'build', 'load-flow-verify.txt'), lines.join('\n') + '\n', 'utf8');
console.log('');
console.log(summary);
process.exit(failures === 0 ? 0 : 1);
