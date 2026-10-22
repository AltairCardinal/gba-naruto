// 音频域工作台的无头验收脚本。
//
// 对应 notes/audio-ux-redesign-20261021.md §7 的七条验收标准。
//
// 用法：node rom-editor/tools/verify_audio_workbench.mjs
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

// --- 一个很小的 DOM --------------------------------------------------------
class StubNode {
  constructor(tag) {
    this.tagName = String(tag || '').toUpperCase();
    this.nodeType = 1;
    this.children = [];
    this.parentNode = null;
    this.attributes = {};
    this.dataset = {};
    this.style = {};
    this.listeners = {};
    this._text = '';
    this._className = '';
    const self = this;
    this.classList = {
      add: (...names) => {
        const set = new Set(self._className.split(/\s+/).filter(Boolean));
        names.forEach((n) => set.add(n));
        self._className = [...set].join(' ');
      },
      remove: (...names) => {
        const set = new Set(self._className.split(/\s+/).filter(Boolean));
        names.forEach((n) => set.delete(n));
        self._className = [...set].join(' ');
      },
      toggle: (name, force) => {
        const has = self.classList.contains(name);
        const want = force === undefined ? !has : !!force;
        if (want) self.classList.add(name); else self.classList.remove(name);
        return want;
      },
      contains: (name) => self._className.split(/\s+/).includes(name),
    };
  }
  get className() { return this._className; }
  set className(v) { this._className = String(v || ''); }
  get value() { return this.attributes.value ?? ''; }
  set value(v) { this.attributes.value = String(v); }
  get firstChild() { return this.children[0] || null; }
  get textContent() {
    if (this.children.length) return this.children.map((c) => c.textContent).join('');
    return this._text;
  }
  set textContent(v) { this.children = []; this._text = String(v === null || v === undefined ? '' : v); }
  set innerHTML(v) { this.children = []; this._text = String(v || ''); }
  get innerHTML() { return this.textContent; }
  appendChild(node) {
    if (node && node.__text) {
      this.children.push({ textContent: node.__text, nodeType: 3, children: [] });
    } else {
      this.children.push(node);
      if (node) node.parentNode = this;
    }
    return node;
  }
  get parentElement() { return this.parentNode || null; }
  removeChild(node) {
    const at = this.children.indexOf(node);
    if (at >= 0) this.children.splice(at, 1);
    return node;
  }
  remove() { if (this.parentNode) this.parentNode.removeChild(this); }
  addEventListener(name, fn) { (this.listeners[name] ||= []).push(fn); }
  setAttribute(name, value) { this.attributes[name] = String(value); }
  getAttribute(name) { return this.attributes[name] ?? null; }
  querySelector() { return null; }
  querySelectorAll() { return []; }
  descendants() {
    const out = [];
    const walk = (node) => {
      for (const child of node.children) {
        if (!child || !child.children) continue;
        out.push(child);
        walk(child);
      }
    };
    walk(this);
    return out;
  }
}

globalThis.document = {
  createElement: (tag) => new StubNode(tag),
  createTextNode: (text) => ({ __text: String(text), textContent: String(text), nodeType: 3 }),
  body: new StubNode('body'),
  getElementById: () => null,
  querySelector: () => null,
};
globalThis.window = {
  location: { hash: '' },
  addEventListener() {},
  removeEventListener() {},
};

const here = dirname(fileURLToPath(import.meta.url));
// 这个脚本住在 rom-editor/tools/，所以仓库根在两级之上。
const repoRoot = join(here, '..', '..');
const packPath = join(repoRoot, 'rom-editor', 'content', 'pack.json');
const romPath = join(repoRoot, 'rom', 'base.gba');

const { ContentPack } = await import('../js/pack.js');
const { buildRom } = await import('../js/rom.js');
const { renderAudio } = await import('../js/modules/audio.js');
const { backReferencesByPointer } = await import('../js/xref.js');

let failures = 0;
function check(name, ok, detail = '') {
  if (!ok) failures += 1;
  console.log(`  [${ok ? 'PASS' : 'FAIL'}] ${name}${detail ? ' — ' + detail : ''}`);
}

const packData = JSON.parse(readFileSync(packPath, 'utf8'));
// ContentPack.fromJSON() **不复制**数据 —— 记录对象是共享的，
// 写回会就地改 packData。所以「干净的内容包」得自己深拷贝一份。
const cleanPackData = JSON.parse(JSON.stringify(packData));
const pack = ContentPack.fromJSON(packData);
const rom = new Uint8Array(readFileSync(romPath));
const base = new Uint8Array(0x600000);
const jumps = [];
const ctx = {
  pack,
  rom: base,
  baseRom: base,
  state: { view: { panel: null } },
  onChange() {},
  openPanel() {},
  goModule() {},
  render() {},
  setStatus() {},
  onJump(target) { jumps.push(target); },
};

/** 一个干净的内容包（不带着别的组留下的改动）。 */
function freshPack() {
  return ContentPack.fromJSON(JSON.parse(JSON.stringify(cleanPackData)));
}

/** 渲染音频域的某个面板（可以换内容包）。 */
function renderPanel(panel, packOverride) {
  const host = new StubNode('div');
  const useCtx = packOverride ? { ...ctx, pack: packOverride } : ctx;
  ctx.state.view = { panel };
  renderAudio(host, useCtx);
  return host;
}

/** 表格里的正文行（跳过表头行）。 */
function bodyRows(host) {
  const tables = host.descendants().filter((n) => n.tagName === 'TABLE');
  if (!tables.length) return [];
  const tbodies = tables[0].children.filter((n) => n.tagName === 'TBODY');
  return tbodies.length ? tbodies[0].children.filter((n) => n.tagName === 'TR') : [];
}

/** 带 class 的节点。 */
function byClass(host, name) {
  return host.descendants().filter((n) => String(n.className || '').split(/\s+/).includes(name));
}

/** 页签按钮（按顺序）。 */
function tabButtons(host) {
  return byClass(host, 'tab-btn');
}

/** 切到某个页签（内容按需渲染，要拿某一页得先切过去）。 */
function switchTab(host, label) {
  const btn = tabButtons(host).find((n) => String(n.textContent || '').includes(label));
  if (!btn) return false;
  const click = btn.listeners && btn.listeners.click && btn.listeners.click[0];
  if (!click) return false;
  click();
  return true;
}

console.log('1) 音效分派表：第一列是 0 基的音效 id');
{
  const host = renderPanel({ kind: 'structure', id: 'sound_id_table' });
  const rows = bodyRows(host);
  const ids = rows.map((tr) => tr.children[0].textContent);
  check('159 行都在', rows.length === 159, `${rows.length} 行`);
  check('第一列是 #0 … #158（0 基）',
    ids.length === 159 && ids.every((text, i) => text === '#' + i),
    ids.slice(0, 3).join('、') + ' … ' + ids.slice(-2).join('、'));

  rows[1].listeners.click[0]({ target: {} });
  const detail = byClass(host, 'detail-panel')[0];
  const text = detail ? detail.textContent : '';
  check('详情里不出现「第 N / 159 条」这种 1 基计数',
    !text.includes('第 ') && !text.includes('/ 159 条'),
    text.includes('音效 id 1') ? '详情写的是「音效 id 1」' : text.slice(0, 60));
}

console.log('\n2) 描述符是指向下拉，选项带名字');
{
  const host = renderPanel({ kind: 'structure', id: 'sound_id_table' });
  bodyRows(host)[1].listeners.click[0]({ target: {} });
  const detail = byClass(host, 'detail-panel')[0];
  const selects = detail.descendants().filter((n) => n.tagName === 'SELECT');
  check('描述符控件是 <select> 而不是输入框',
    selects.length >= 1 && selects[0].tagName === 'SELECT',
    `${selects.length} 个下拉`);
  const options = selects[0].children.filter((o) => o.tagName === 'OPTION');
  check('选项数 = 81（81 个已导出描述符）', options.length === 81, `${options.length} 个选项`);
  const texts = options.map((o) => o.textContent);
  check('有带名字的选项（音频曲 1 · 0x536368）',
    texts.some((t) => t.includes('音频曲 1（m4a SongHeader）') && t.includes('0x536368')),
    (texts.find((t) => t.includes('音频曲 1')) || '没有').slice(0, 50));
  check('空哨兵在选项里，并写明被几个音效共用',
    texts.some((t) => t.includes('空哨兵') && t.includes('79 个音效共用')),
    (texts.find((t) => t.includes('空哨兵')) || '没有').slice(0, 60));
}

console.log('\n3) 指针反查：谁指向这个描述符');
{
  const one = backReferencesByPointer(pack, 0x08536368);
  const hit = one.find((r) => r.structure.id === 'sound_id_table' && r.record.id === 1);
  check('音效 #1 的描述符被 sound_id_table 记录 1 指着', !!hit,
    `${one.length} 处引用`);
  const empty = backReferencesByPointer(pack, 0x08466068);
  check('空哨兵被 79 条音效共用', empty.length === 79, `${empty.length} 处引用`);

  const host = renderPanel({ kind: 'structure', id: 'sound_id_table' });
  bodyRows(host)[19].listeners.click[0]({ target: {} });
  const detail = byClass(host, 'detail-panel')[0];
  // 反查块在「谁指向它」这一页 —— 先切过去再看。
  switchTab(detail, '谁指向它');
  const block = byClass(detail, 'xref-block')[0];
  check('详情里有「被谁引用」块（在「谁指向它」这一页）', !!block,
    block ? (block.children[0] ? block.children[0].textContent : '') : '没有');
}

console.log('\n4) 乐曲描述符的轨道指针是一张表');
{
  const host = renderPanel({ kind: 'structure', id: 'audio_song_2' });
  const slotTables = byClass(host, 'slot-table');
  check('有 .slot-table', slotTables.length === 1, `${slotTables.length} 张`);
  const rows = slotTables[0]
    ? slotTables[0].descendants().filter((n) => n.tagName === 'TR').length - 1
    : 0;
  check('轨道表是 10 行', rows === 10, `${rows} 行`);
  const inTable = new Set(slotTables[0] ? slotTables[0].descendants() : []);
  const outside = host.descendants()
    .filter((n) => ['INPUT', 'SELECT', 'TEXTAREA'].includes(n.tagName))
    .filter((n) => !inTable.has(n));
  check('轨道不是散装输入框（表外可编辑控件 < 10）', outside.length < 10,
    `表外 ${outside.length} 个控件`);
}

console.log('\n5) 空哨兵与未解码描述符被如实标注');
{
  const host = renderPanel({ kind: 'structure', id: 'sound_id_table' });
  bodyRows(host)[19].listeners.click[0]({ target: {} });
  const detail = byClass(host, 'detail-panel')[0];
  const text = detail.textContent;
  check('音效 #19 标成空哨兵并给出地址',
    text.includes('空哨兵') && text.includes('0x466068'),
    (text.match(/空哨兵[^·]{0,30}/) || [''])[0]);

  // 音效 #3 的描述符现在**已经解码**（audio_song_3，10 轨）；
  // 「未解码」这条路径留给不在导出表里的地址。
  bodyRows(host)[3].listeners.click[0]({ target: {} });
  const text3 = byClass(host, 'detail-panel')[0].textContent;
  check('音效 #3 的描述符已解码（不再是未解码）',
    text3.includes('音频曲 3（m4a SongHeader）') && text3.includes('轨道 10'),
    (text3.match(/音频曲 3[^·]{0,20}/) || [''])[0]);

  const table = pack.structure('sound_id_table');
  const record3 = table.records.find((r) => r.id === 3);
  pack.setValue(table, record3, 'descriptor_ptr', 0x08537400);
  const host2 = renderPanel({ kind: 'structure', id: 'sound_id_table' });
  bodyRows(host2)[3].listeners.click[0]({ target: {} });
  const text4 = byClass(host2, 'detail-panel')[0].textContent;
  check('不在导出表里的地址标成「未解码描述符」',
    text4.includes('未解码描述符') && text4.includes('0x537400'),
    (text4.match(/未解码描述符[^·]{0,20}/) || [''])[0]);
  pack.setValue(table, record3, 'descriptor_ptr', 0x085374B4);
}

console.log('\n6) 域首页：一览是统计，不是 159 行表');
{
  const host = renderPanel(null);
  const text = host.textContent;
  check('域首页没有字面星号', !text.includes('**'),
    text.includes('**') ? '还有星号' : '没有');
  const details = host.descendants().find((n) => n.tagName === 'DETAILS');
  const rows = details
    ? details.descendants().filter((n) => n.tagName === 'TR').length
    : 0;
  check('一览的行数 < 10', rows > 0 && rows < 10, `${rows} 行`);
  check('一览写明 79 个空哨兵', text.includes('79') && text.includes('空哨兵'),
    (text.match(/79[^，。]{0,20}/) || [''])[0]);
  const audioTables = pack.structures.filter((s) => s.module === 'audio').length;
  const listed = host.descendants().filter((n) => n.tagName === 'TR').length;
  check('本域全部表都列在首页', listed >= audioTables,
    `${listed} 行（应 ≥ ${audioTables}）`);
}

console.log('\n7) 写回只动该动的字节（回归）');
{
  const fresh = freshPack();
  const table = fresh.structure('sound_id_table');
  const record = table.records.find((r) => r.id === 3);
  const before = { ...record.values };
  fresh.setValue(table, record, 'descriptor_ptr', 0x08536368);
  const out = buildRom(fresh, rom);
  check('构建无错误', out.report.errors.length === 0, out.report.errors.join('; '));
  const base3 = 0x465B70 + 3 * 8;
  check('描述符指针写对了',
    out.bytes[base3] === 0x68 && out.bytes[base3 + 1] === 0x63,
    `0x${out.bytes[base3].toString(16)}${out.bytes[base3 + 1].toString(16)}`);
  check('播放通道没被动',
    out.bytes[base3 + 4] === (before.player_index & 0xff) &&
    out.bytes[base3 + 5] === ((before.player_index >> 8) & 0xff),
    `${before.player_index}`);
  check('播放配置没被动',
    out.bytes[base3 + 6] === (before.player_config & 0xff) &&
    out.bytes[base3 + 7] === ((before.player_config >> 8) & 0xff),
    `${before.player_config}`);
}

console.log('\n8) 函数指针表：1..11 槽标成播放入口（推定）');
{
  const host = renderPanel({ kind: 'structure', id: 'function_pointer_table' });
  const text = host.textContent;
  check('槽 1 标成「播放入口 · 音效 #1（推定）」',
    text.includes('播放入口 · 音效 #1（推定）'),
    (text.match(/播放入口[^）]{0,12}/) || [''])[0]);
  check('槽 0 / 12 标成哨兵',
    (text.match(/哨兵（FFFFFFFF）/g) || []).length >= 2,
    `${(text.match(/哨兵（FFFFFFFF）/g) || []).length} 处`);
  check('写明这是静态推定', text.includes('静态推定'));
}

console.log('\n9) 详情面板页签化：描述符 / 谁指向它 / 播放入口');
{
  const host = renderPanel({ kind: 'structure', id: 'sound_id_table' });
  bodyRows(host)[1].listeners.click[0]({ target: {} });
  const detail = byClass(host, 'detail-panel')[0];
  const tabs = byClass(detail, 'tab-panel')[0];
  check('右侧面板有页签条', !!tabs && byClass(tabs, 'tab-bar').length === 1,
    tabs ? `${tabButtons(tabs).length} 个页签` : '没有页签面板');
  const labels = byClass(tabs, 'tab-btn-label').map((n) => n.textContent);
  check('页签标签是预期的三个',
    JSON.stringify(labels) === JSON.stringify(['描述符', '谁指向它', '播放入口']),
    labels.join(' / '));
  check('页签内容区只有一个（懒渲染）', byClass(tabs, 'tab-body').length === 1,
    `${byClass(tabs, 'tab-body').length} 个内容区`);

  const body = () => byClass(tabs, 'tab-body')[0];
  const first = body();
  const firstSelects = first.descendants().filter((n) => n.tagName === 'SELECT');
  check('默认停在「描述符」：描述符下拉与自定义地址都在',
    firstSelects.length === 1 && first.textContent.includes('自定义地址'),
    `${firstSelects.length} 个下拉`);
  check('没切过去时，「谁指向它」的内容不在 DOM 里',
    byClass(first, 'xref-block').length === 0);

  check('能切到「谁指向它」', switchTab(tabs, '谁指向它'));
  const second = body();
  const refBlocks = byClass(second, 'xref-block')
    .filter((n) => !String(n.className || '').includes('audio-play-entry'));
  check('切过去后反查块在 DOM 里', refBlocks.length === 1,
    `${refBlocks.length} 个反查块`);
  check('切走后「描述符」页的内容不在 DOM 里',
    second.descendants().filter((n) => n.tagName === 'SELECT').length === 0
    && !second.textContent.includes('自定义地址'));

  check('能切到「播放入口」', switchTab(tabs, '播放入口'));
  const third = body();
  check('播放入口页有播放通道与推定的入口',
    third.textContent.includes('播放通道') && third.textContent.includes('静态推定'),
    (third.textContent.match(/槽 \d+ · 音效 #\d+/) || [''])[0]);
  check('切走后「谁指向它」的内容不在 DOM 里',
    byClass(third, 'xref-block')
      .filter((n) => !String(n.className || '').includes('audio-play-entry')).length === 0);
}

console.log('\n10) 角标：这一类改了几处（按字节判定，写回后自动跟上）');
{
  // 换一个**干净**的内容包（fromJSON 不复制数据，前面几组的写回会留在 packData 里）。
  const fresh = freshPack();
  const host = renderPanel({ kind: 'structure', id: 'sound_id_table' }, fresh);
  bodyRows(host)[1].listeners.click[0]({ target: {} });
  const detail = byClass(host, 'detail-panel')[0];
  const tabs = byClass(detail, 'tab-panel')[0];
  check('没改过就没有角标', byClass(tabs, 'tab-badge').length === 0,
    `${byClass(tabs, 'tab-badge').length} 个角标`);

  const table = fresh.structure('sound_id_table');
  const record = table.records.find((r) => r.id === 1);
  fresh.setValue(table, record, 'descriptor_ptr', 0x08466068);
  const badges = byClass(tabs, 'tab-badge');
  check('写回之后「描述符」页签自动亮出角标 1',
    badges.length === 1 && badges[0].textContent === '1',
    badges.map((b) => b.textContent).join('、'));

  // 改了又改回去 = 不算改（按字节判定）。
  fresh.setValue(table, record, 'descriptor_ptr', 0x08536368);
  const after = byClass(tabs, 'tab-badge');
  check('改回去之后角标消失', after.length === 0, `${after.length} 个角标`);
}

console.log('\n11) 乐曲描述符也页签化（跨域门禁 verify_tabs 看的就是它）');
{
  const host = renderPanel({ kind: 'structure', id: 'audio_song_1' });
  const tabs = byClass(host, 'tab-panel')[0];
  const labels = byClass(tabs, 'tab-btn-label').map((n) => n.textContent);
  check('乐曲描述符有页签条，标签也是三个',
    JSON.stringify(labels) === JSON.stringify(['描述符', '谁指向它', '播放入口']),
    labels.join(' / '));
  check('默认页是「描述符」：歌曲头与轨道表都在',
    byClass(host, 'slot-table').length === 1
    && host.textContent.includes('歌曲头'),
    `${byClass(host, 'slot-table').length} 张轨道表`);
  check('能切到「谁指向它」', switchTab(tabs, '谁指向它'));
  check('切过去后有反查块', byClass(host, 'xref-block').length >= 1);
  check('能切到「播放入口」', switchTab(tabs, '播放入口'));
  check('播放入口页标明了「推定」', host.textContent.includes('静态推定'));
}

console.log(failures ? `\n${failures} 项未通过` : '\n全部通过');
process.exit(failures ? 1 : 0);
