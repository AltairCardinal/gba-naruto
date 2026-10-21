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

/** 渲染音频域的某个面板。 */
function renderPanel(panel) {
  const host = new StubNode('div');
  ctx.state.view = { panel };
  renderAudio(host, ctx);
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
  const block = byClass(detail, 'xref-block')[0];
  check('详情里有「被谁引用」块', !!block,
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
  const fresh = ContentPack.fromJSON(packData);
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

console.log(failures ? `\n${failures} 项未通过` : '\n全部通过');
process.exit(failures ? 1 : 0);
