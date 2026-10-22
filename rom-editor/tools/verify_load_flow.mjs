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

head('\n4) 从 ROM 解析出的内容包，与仓库里那份完全一致');
{
  const template = ContentPack.fromJSON(JSON.parse(readFileSync(packPath, 'utf8')));
  const rom = new Uint8Array(readFileSync(romPath));
  const { pack, report } = parsePackFromRom(template, rom, { name: 'base.gba' });
  check('结构表逐表相等',
    JSON.stringify(template.structures) === JSON.stringify(pack.structures),
    `${report.structures} 张`);
  check('文本表逐表相等',
    JSON.stringify(template.texts) === JSON.stringify(pack.texts),
    `${report.texts} 张`);
  check('剧本元信息逐条相等',
    JSON.stringify(template.scripts) === JSON.stringify(pack.scripts),
    `${report.scripts} 条`);
  check('解析没有改动任何一条记录',
    report.recordsChanged === 0 && report.textsChanged === 0,
    `记录 ${report.recordsChanged} / 文本 ${report.textsChanged}`);
}

head('\n5) ROM 改了，解析出来的内容包要跟着改');
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
