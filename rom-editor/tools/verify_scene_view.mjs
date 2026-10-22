// 「场景」与「字库」两个统一编辑视图的无头验收探针。
//
// 对应 notes/story-scene-font-view-20261022.md 的验收标准：
//   1. 场景视图能渲染，左边列表的行数 = 场景数（按根表槽数算）；
//   2. 详情里有四个剧本指针的字段（现在分在四个页签里，一页一路）；
//   3. 字库视图能渲染，字宽表在「字宽」页里（256 行）；
//   4. 改一个字段后 pack.changedCount() +1，改回原值后回落；
//   5. 域首页的「本域可编辑内容」里，四张根表合成了一行、字形段表与字宽表合成了一行。
//
// 第 8 组是页签化的验收：右侧面板有页签条、页签标签是预期的那些、
// 切到某一页后那一页的内容在 DOM 里、切走后不在，角标只出现在改过的那一页上。
//
// 用法：node rom-editor/tools/verify_scene_view.mjs
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
    this.style = {
      setProperty(name, value) { this[name] = value; },
      getPropertyValue(name) { return this[name] ?? ''; },
      removeProperty(name) { delete this[name]; },
    };
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
const repoRoot = join(here, '..', '..');
const packPath = join(repoRoot, 'rom-editor', 'content', 'pack.json');

const { ContentPack } = await import('../js/pack.js');
const { renderScene, renderFont } = await import('../js/modules/scene.js');
const { renderStory } = await import('../js/modules/story.js');

let failures = 0;
function check(name, ok, detail = '') {
  if (!ok) failures += 1;
  console.log(`  [${ok ? 'PASS' : 'FAIL'}] ${name}${detail ? ' — ' + detail : ''}`);
}

const packData = JSON.parse(readFileSync(packPath, 'utf8'));
const pack = ContentPack.fromJSON(packData);
const base = new Uint8Array(0x600000);
const jumps = [];
const opened = [];
const ctx = {
  pack,
  rom: base,
  baseRom: base,
  state: { view: { panel: null } },
  onChange() {},
  openPanel(kind, id, params) { opened.push({ kind, id, params }); },
  goModule() {},
  render() {},
  setStatus() {},
  onJump(target) { jumps.push(target); },
};

/** 渲染一个视图。 */
function render(renderer, panel) {
  const host = new StubNode('div');
  ctx.state.view = { panel: panel || null };
  renderer(host, ctx);
  return host;
}

/** 表格的正文行（跳过表头行）。 */
function bodyRows(table) {
  if (!table) return [];
  const tbodies = table.children.filter((n) => n.tagName === 'TBODY');
  return tbodies.length ? tbodies[0].children.filter((n) => n.tagName === 'TR') : [];
}

/** 带某个 class 的后代节点。 */
function byClass(host, name) {
  return host.descendants().filter((n) => String(n.className || '').split(/\s+/).includes(name));
}

/** 第一张带某个 class 的表。 */
function tableByClass(host, name) {
  return byClass(host, name).find((n) => n.tagName === 'TABLE') || null;
}

/**
 * 切到右侧面板的某个页签（内容按需渲染，要拿某一页得先切过去）。
 */
function switchTab(host, label) {
  const btn = host.descendants()
    .filter((n) => String(n.className || '').split(/\s+/).includes('tab-btn'))
    .find((n) => String(n.textContent || '').includes(label));
  if (!btn) return false;
  const click = btn.listeners && btn.listeners.click && btn.listeners.click[0];
  if (!click) return false;
  click();
  return true;
}

/** 页签条上的标签（按顺序）。 */
function tabLabels(host) {
  const bar = byClass(host, 'tab-bar')[0];
  if (!bar) return [];
  return bar.children.map((btn) => {
    const label = btn.descendants()
      .find((n) => String(n.className || '').split(/\s+/).includes('tab-btn-label'));
    return label ? label.textContent : btn.textContent;
  });
}

/** 页签角标：标签 → 角标文字（没有角标就是空串）。 */
function tabBadges(host) {
  const out = {};
  const bar = byClass(host, 'tab-bar')[0];
  if (!bar) return out;
  for (const btn of bar.children) {
    const label = btn.descendants()
      .find((n) => String(n.className || '').split(/\s+/).includes('tab-btn-label'));
    const badge = btn.descendants()
      .find((n) => String(n.className || '').split(/\s+/).includes('tab-badge'));
    if (label) out[label.textContent] = badge ? badge.textContent : '';
  }
  return out;
}

/** 剧本指针块上的根表名（field-label 的第一格）。 */
function ptrLabel(node) {
  const label = node ? byClass(node, 'field-label')[0] : null;
  if (!label) return '';
  const span = label.children.find((n) => n.tagName === 'SPAN');
  return span ? span.textContent : label.textContent;
}

// ---------------------------------------------------------------------------
// 期望值：全部从内容包算，不写死数字。
// ---------------------------------------------------------------------------
const ROOTS = ['story_before_root', 'story_after_root', 'story_logic_root', 'story_events_root'];
const rootTables = ROOTS.map((id) => pack.structure(id));
const sceneCount = Math.max(...rootTables.map((t) => t.entry_count)) - 1;
const segmentCount = pack.structure('font_segments').entry_count;
const widthCount = pack.structure('font_width_table').entry_count;

console.log(`内容包：四张根表最多 ${sceneCount + 1} 槽 → ${sceneCount} 个场景；` +
  `${segmentCount} 段字形；${widthCount} 个字符码`);

console.log('\n1) 场景视图：左边列表的行数 = 场景数');
{
  const host = render(renderScene);
  const list = byClass(host, 'scene-list')[0];
  const rows = bodyRows(list && list.children.find((n) => n.tagName === 'TABLE'));
  check('场景视图渲染出来了', host.textContent.length > 100, `${host.textContent.length} 字符`);
  check(`左边列表 ${sceneCount} 行`, rows.length === sceneCount, `${rows.length} 行`);
  check('第一行是「场景 1」', rows.length > 0 && rows[0].children[1].textContent === '场景 1',
    rows.length ? rows[0].children[1].textContent : '没有行');
  check('页面文本里没有字面星号', !host.textContent.includes('**'));
}

console.log('\n2) 场景视图：四个剧本入口各占一页签，每页一个指针字段');
{
  const host = render(renderScene);
  const detail = byClass(host, 'scene-detail')[0];
  const labels = tabLabels(detail);
  check('场景视图右侧有页签条', byClass(detail, 'tab-bar').length === 1);
  check('页签是 战前 / 战后 / 逻辑 / 事件',
    labels.join(',') === '战前,战后,逻辑,事件', labels.join('、'));

  const ptrs = [];
  for (const label of labels) {
    switchTab(host, label);
    const one = byClass(detail, 'scene-ptr');
    check(`「${label}」页里有一个剧本指针`, one.length === 1, `${one.length} 个`);
    if (one.length === 1) ptrs.push(one[0]);
  }
  check('四个剧本指针字段（四页合起来）', ptrs.length === 4, `${ptrs.length} 个`);
  const inputs = ptrs.flatMap((p) => p.descendants().filter((n) => n.tagName === 'INPUT'));
  check('四个指针都是可编辑的十六进制框', inputs.length === 4 && inputs.every((n) => n.value.startsWith('0x')),
    inputs.map((n) => n.value).join('、'));

  // 每一页都有「看这个场景的剧本」的链接，而且分别跳到四张根表。
  const roots = [];
  for (const label of labels) {
    switchTab(host, label);
    const page = byClass(detail, 'scene-ptr')[0];
    const link = page && page.descendants()
      .find((n) => n.textContent.includes('的剧本 →') && n.listeners.click && n.listeners.click.length);
    check(`「${label}」页有「看这个场景的剧本」的链接`, !!link);
    if (!link) continue;
    link.listeners.click[0]({ target: {} });
    const jump = jumps[jumps.length - 1];
    check(`「${label}」的链接跳到剧本查看器（#story/script/<root>/<scene>）`,
      !!jump && jump.module === 'story' && jump.kind === 'script' &&
      ['before', 'after', 'logic', 'events'].includes(jump.params.root) &&
      typeof jump.params.scene === 'number',
      jump ? `${jump.params.root}/${jump.params.scene}` : '没有跳转');
    if (jump) roots.push(jump.params.root);
  }
  check('四页分别跳到四张根表', new Set(roots).size === 4, roots.join('、'));
}

console.log('\n3) 字库视图：字宽表在「字宽」页里（256 行）');
{
  const host = render(renderFont);
  const list = byClass(host, 'font-list')[0];
  const listRows = bodyRows(list && list.children.find((n) => n.tagName === 'TABLE'));
  check('字库视图渲染出来了', host.textContent.length > 100, `${host.textContent.length} 字符`);
  check(`左边列表 ${segmentCount} 行（字形段表）`, listRows.length === segmentCount, `${listRows.length} 行`);
  switchTab(host, '字宽');
  const widthTable = tableByClass(host, 'font-width-table');
  const widthRows = bodyRows(widthTable);
  check(`字宽表 ${widthCount} 行`, widthRows.length === widthCount, `${widthRows.length} 行`);
  check('每行都有可改的字宽输入框',
    widthRows.every((tr) => tr.descendants().some((n) => n.tagName === 'INPUT')),
    `${widthRows.filter((tr) => tr.descendants().some((n) => n.tagName === 'INPUT')).length} 行有输入框`);
  check('页面文本里没有字面星号', !host.textContent.includes('**'));
}

console.log('\n4) 改一个字段：写回 +1，改回原值后回落');
{
  const widths = pack.structure('font_width_table');
  const record = widths.records[0];
  const field = widths.fields.find((f) => f.type !== 'hex');
  const before = record.values[field.key];
  const base = pack.changedCount();

  const host = render(renderFont);
  switchTab(host, '字宽');
  const widthTable = tableByClass(host, 'font-width-table');
  const firstRow = bodyRows(widthTable)[0];
  const input = firstRow.descendants().find((n) => n.tagName === 'INPUT');
  const next = (Number(before) + 1) % 256;
  input.listeners.change[0]({ target: { value: String(next) } });
  check('改完立刻写回内容包', record.values[field.key] === next,
    `字符码 0 的字宽：${before} → ${record.values[field.key]}`);
  check('pack.changedCount() +1', pack.changedCount() === base + 1,
    `${base} → ${pack.changedCount()}`);

  input.listeners.change[0]({ target: { value: String(before) } });
  check('改回原值后回落', pack.changedCount() === base,
    `${pack.changedCount()}（基线 ${base}）`);
  check('值也回到了原样', record.values[field.key] === before,
    `字符码 0 的字宽：${record.values[field.key]}`);
}

console.log('\n5) 域首页：四张根表合成一行、字形段表与字宽表合成一行');
{
  const host = render(renderStory);
  const tables = byClass(host, 'domain-tables');
  const grid = tables.find((n) => n.tagName === 'TABLE');
  const rows = bodyRows(grid);
  // 组行的第一格里有两段：标题 + 「由 … 合成」的脚注；独立行只有一段。
  const cellLabel = (tr) => {
    const td = tr.children[0];
    const div = (td.children || []).find((c) => c.tagName === 'DIV');
    return div ? div.textContent : td.textContent;
  };
  const firstCells = rows.map(cellLabel);
  const groups = ['场景（四张剧情脚本根表）', '字库（字形段表 + 字宽表）'];
  for (const label of groups) {
    check(`有一行「${label}」`, firstCells.filter((t) => t === label).length === 1,
      `${firstCells.filter((t) => t === label).length} 行`);
  }
  const singles = [
    '剧情脚本根表（before）', '剧情脚本根表（after）',
    '战场事件逻辑根表', '战场事件根表',
    '字形段表', '字宽表',
  ];
  const leaked = singles.filter((label) => firstCells.includes(label));
  check('六张表不再单独占一行', leaked.length === 0,
    leaked.length ? `仍然单独出现：${leaked.join('、')}` : '都合成组行了');
  check('对白槽位表 / 说话人名表 / 剧情底图表仍是独立行',
    firstCells.some((t) => t.includes('对白槽位表')) &&
    firstCells.some((t) => t.includes('说话人名表')) &&
    firstCells.some((t) => t.includes('剧情底图表')),
    firstCells.join(' | '));
  check('页面文本里没有字面星号', !host.textContent.includes('**'));
}

console.log('\n6) 域首页的入口按钮跳到新视图');
{
  const host = render(renderStory);
  const buttons = host.descendants().filter((n) => n.tagName === 'BUTTON');
  const sceneBtn = buttons.find((b) => b.textContent === '打开场景');
  const fontBtn = buttons.find((b) => b.textContent === '打开字库');
  check('有「打开场景」按钮', !!sceneBtn);
  check('有「打开字库」按钮', !!fontBtn);
  if (sceneBtn) {
    sceneBtn.listeners.click[0]({ target: {} });
    const last = opened[opened.length - 1];
    check('「打开场景」进的是 scene 视图', last && last.kind === 'scene' && last.id === '场景',
      last ? `${last.kind}/${last.id}` : '没有打开');
  }
  if (fontBtn) {
    fontBtn.listeners.click[0]({ target: {} });
    const last = opened[opened.length - 1];
    check('「打开字库」进的是 font 视图', last && last.kind === 'font' && last.id === '字库',
      last ? `${last.kind}/${last.id}` : '没有打开');
  }
}

console.log('\n7) 交互：点场景行换详情 / 点字形段换段 / 按字符码查字宽');
{
  // 7a. 场景列表点第 3 行 → 详情变成「场景 3」
  const host = render(renderScene);
  const list = byClass(host, 'scene-list')[0];
  const rows = bodyRows(list.children.find((n) => n.tagName === 'TABLE'));
  rows[2].listeners.click[0]({ target: {} });
  const detail = byClass(host, 'scene-detail')[0];
  check('点第 3 行后详情是「场景 3」', detail.textContent.includes('场景 3'),
    (detail.textContent.match(/场景 \d+/) || [''])[0]);
  const labels = tabLabels(detail);
  check('换场景后页签还在', labels.join(',') === '战前,战后,逻辑,事件', labels.join('、'));
  let ptrCount = 0;
  for (const label of labels) {
    switchTab(host, label);
    ptrCount += byClass(detail, 'scene-ptr').length;
  }
  check('详情里仍然是四个剧本指针',
    ptrCount === 4,
    `${ptrCount} 个`);

  // 7b. 字库：点第 2 段 → 详情换成那一段的字段
  const fontHost = render(renderFont);
  const fontList = byClass(fontHost, 'font-list')[0];
  const segRows = bodyRows(fontList.children.find((n) => n.tagName === 'TABLE'));
  segRows[1].listeners.click[0]({ target: {} });
  const fontDetail = byClass(fontHost, 'font-detail')[0];
  check('点第 2 段后详情是「第 1 段」', fontDetail.textContent.includes('第 1 段'),
    (fontDetail.textContent.match(/第 \d+ 段/) || [''])[0]);
  const segFields = byClass(fontDetail, 'font-seg-field');
  check('这一段的字段都是可改的控件', segFields.length >= 3 &&
    segFields.every((f) => f.descendants().some((n) => n.tagName === 'INPUT')),
    `${segFields.length} 个字段`);
  switchTab(fontHost, '字宽');
  check('字宽表仍然在详情里', !!tableByClass(fontHost, 'font-width-table'));

  // 7c. 「按字符码查字宽」：填一个码位 → 详情里出现那一码的字宽
  const lookup = byClass(fontHost, 'font-lookup')[0];
  check('「字宽」页里有「按字符码查字宽」的入口', !!lookup);
  const lookupInput = lookup && lookup.descendants().find((n) => n.tagName === 'INPUT');
  const lookupBtn = lookup && lookup.descendants().find((n) => n.tagName === 'BUTTON');
  check('有「按字符码查字宽」的入口', !!lookupInput && !!lookupBtn);
  if (lookupInput && lookupBtn) {
    lookupInput.value = '64';
    lookupBtn.listeners.click[0]({ target: { value: '64' } });
    const after = byClass(fontHost, 'font-detail')[0];
    check('查得到那一码并给出它的字宽',
      after.textContent.includes('字符码 64 的字宽'),
      (after.textContent.match(/字符码 \d+ 的字宽/) || ['没有'])[0]);
    const hit = bodyRows(tableByClass(fontHost, 'font-width-table'))
      .filter((tr) => (tr.className || '').includes('lookup-hit'));
    check('字宽表里那一行被标出来', hit.length === 1, `${hit.length} 行`);
  }
}

console.log('\n8) 页签化：右侧有页签条 / 标签对 / 内容进页签 / 切走后不在 / 角标只挂在改过的那一页');
{
  // 8a. 场景视图
  const host = render(renderScene);
  const detail = byClass(host, 'scene-detail')[0];
  check('场景视图右侧有页签条', byClass(detail, 'tab-bar').length === 1);
  const labels = tabLabels(detail);
  check('场景视图的页签是 战前 / 战后 / 逻辑 / 事件',
    labels.join(',') === '战前,战后,逻辑,事件', labels.join('、'));
  check('默认页（战前）里只有那一个剧本指针',
    byClass(detail, 'scene-ptr').length === 1 &&
    ptrLabel(byClass(detail, 'scene-ptr')[0]) === '战前剧情',
    ptrLabel(byClass(detail, 'scene-ptr')[0]));
  switchTab(host, '战后');
  const after = byClass(detail, 'scene-ptr');
  check('切到「战后」后那一页的内容在 DOM 里',
    after.length === 1 && ptrLabel(after[0]) === '战后剧情',
    after.length ? ptrLabel(after[0]) : '没有');
  switchTab(host, '战前');
  const back = byClass(detail, 'scene-ptr');
  check('切走后那一页的内容不在 DOM 里',
    back.length === 1 && ptrLabel(back[0]) === '战前剧情',
    back.length ? ptrLabel(back[0]) : '没有');

  // 8b. 场景视图的角标：改了哪一路，哪一页签上出现角标
  const base = pack.changedCount();
  const ptrInput = byClass(detail, 'scene-ptr')[0].descendants().find((n) => n.tagName === 'INPUT');
  const original = ptrInput.value;
  ptrInput.listeners.change[0]({ target: { value: '0x08001234' } });
  const badges = tabBadges(detail);
  check('改过的那一路页签上有角标', badges['战前'] === '1', JSON.stringify(badges));
  check('没改过的页签没有角标', !badges['战后'], JSON.stringify(badges));
  check('写回后改动数 +1', pack.changedCount() === base + 1,
    `${base} → ${pack.changedCount()}`);
  ptrInput.listeners.change[0]({ target: { value: original } });
  check('改回原值后角标消失', !tabBadges(detail)['战前'], JSON.stringify(tabBadges(detail)));
  check('改回原值后改动数回到基线', pack.changedCount() === base,
    `${pack.changedCount()}（基线 ${base}）`);

  // 8c. 字库视图
  const fontHost = render(renderFont);
  const fontDetail = byClass(fontHost, 'font-detail')[0];
  check('字库视图右侧有页签条', byClass(fontDetail, 'tab-bar').length === 1);
  const fontLabels = tabLabels(fontDetail);
  check('字库视图的页签是 字形段 / 字宽',
    fontLabels.join(',') === '字形段,字宽', fontLabels.join('、'));
  check('默认页（字形段）里有这一段的字段',
    byClass(fontDetail, 'font-seg-field').length >= 3,
    `${byClass(fontDetail, 'font-seg-field').length} 个字段`);
  check('默认页里没有字宽表', !tableByClass(fontDetail, 'font-width-table'));
  switchTab(fontHost, '字宽');
  check('切到「字宽」后字宽表在 DOM 里', !!tableByClass(fontDetail, 'font-width-table'));
  check('切到「字宽」后字形段的字段不在 DOM 里',
    byClass(fontDetail, 'font-seg-field').length === 0,
    `${byClass(fontDetail, 'font-seg-field').length} 个字段`);
  switchTab(fontHost, '字形段');
  check('切走后字宽表不在 DOM 里', !tableByClass(fontDetail, 'font-width-table'));
  check('切回来后字形段的字段又在了',
    byClass(fontDetail, 'font-seg-field').length >= 3,
    `${byClass(fontDetail, 'font-seg-field').length} 个字段`);

  // 8d. 字库视图的角标：改了字宽，字宽页签上有角标
  const fontBase = pack.changedCount();
  switchTab(fontHost, '字宽');
  const widthInput = bodyRows(tableByClass(fontHost, 'font-width-table'))[0]
    .descendants().find((n) => n.tagName === 'INPUT');
  const widthValue = Number(widthInput.value);
  widthInput.listeners.change[0]({ target: { value: String((widthValue + 1) % 256) } });
  const fontBadges = tabBadges(fontDetail);
  check('改过字宽后「字宽」页签上有角标', fontBadges['字宽'] === '1', JSON.stringify(fontBadges));
  check('没改过的「字形段」页签没有角标', !fontBadges['字形段'], JSON.stringify(fontBadges));
  widthInput.listeners.change[0]({ target: { value: String(widthValue) } });
  check('改回原值后角标消失', !tabBadges(fontDetail)['字宽'], JSON.stringify(tabBadges(fontDetail)));
  check('改回原值后改动数回到基线', pack.changedCount() === fontBase,
    `${pack.changedCount()}（基线 ${fontBase}）`);
}

console.log(`\n${failures ? `${failures} 项未通过` : '全部通过'}`);
process.exit(failures ? 1 : 0);
