// 剧情路线工作台的无头验收探针（notes/specs/route-workbench.md §6）。
//
// verify_views.mjs 覆盖的是「旧视图别坏掉」；这个文件覆盖的是**新设计**的
// 六条验收标准：路线边按关卡过滤、下一场景是下拉、任务文案就地可改、
// 奖励就地可改且与道具域同一份数据、跨关共用显式告知、键盘与撤销。
//
//   node rom-editor/tools/verify_route_workbench.mjs
//
// 它自带一个极小的 DOM 桩（与 verify_views.mjs 同款），所以不依赖浏览器。
import { readFileSync } from 'node:fs';
import { gunzipSync } from 'node:zlib';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

// --- a very small DOM ------------------------------------------------------
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
  removeEventListener(name, fn) {
    const list = this.listeners[name] || [];
    const at = list.indexOf(fn);
    if (at >= 0) list.splice(at, 1);
  }
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
globalThis.setTimeout = globalThis.setTimeout || (() => 0);
globalThis.window = {
  location: { hash: '' },
  addEventListener() {},
  removeEventListener() {},
};

const { ContentPack } = await import('../js/pack.js');
const routeModule = await import('../js/modules/route.js');
const renderRoute = routeModule.renderRoute;
const renderRouteStage = routeModule.renderStage;

const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, '..');

let failures = 0;
function check(name, ok, detail = '') {
  if (!ok) failures += 1;
  console.log(`  [${ok ? 'PASS' : 'FAIL'}] ${name}${detail ? ' — ' + detail : ''}`);
}

const packData = JSON.parse(readFileSync(join(root, 'content', 'pack.json'), 'utf8'));
const pack = ContentPack.fromJSON(packData);
try {
  const index = JSON.parse(gunzipSync(readFileSync(join(root, 'content', 'text-index.json.gz'))).toString('utf8'));
  pack.texts.push(index);
} catch (err) {
  console.log('  （未找到 text-index.json.gz）');
}

const base = new Uint8Array(0x600000);
base.fill(0xff, 0x5dfbec);
const calls = [];
const ctx = {
  pack,
  rom: base,
  baseRom: base,
  state: { module: 'route', view: { panel: null } },
  onChange() {},
  openPanel(kind, id, params) { calls.push({ kind, id, params }); },
  goModule(id) { calls.push({ module: id }); },
  render() {},
  setStatus() {},
};

function renderStage(stage) {
  const host = new StubNode('div');
  renderRouteStage(host, ctx, stage);
  return host;
}

function all(node, predicate) {
  return node.descendants().filter(predicate);
}

/**
 * 切到右侧面板的某个页签（内容按需渲染，要拿某一页得先切过去）。
 */
function switchTab(host, label) {
  const btn = all(host, (n) => String(n.className || '').split(/\s+/).includes('tab-btn'))
    .find((n) => String(n.textContent || '').includes(label));
  if (!btn) return false;
  const click = btn.listeners && btn.listeners.click && btn.listeners.click[0];
  if (!click) return false;
  click();
  return true;
}

// --- 1) 路线边按关卡过滤 ---------------------------------------------------
console.log('1) 路线边按关卡过滤');
{
  const host = renderStage(40);
  const rootNode = all(host, (n) => n.className === 'route-workbench')[0];
  check('工作台根元素存在且可聚焦', !!rootNode && rootNode.getAttribute('tabindex') === '-1',
    rootNode ? `tabindex=${rootNode.getAttribute('tabindex')}` : '没有');

  const tables = all(host, (n) => n.tagName === 'TABLE');
  const edgeRows = (table) => table.children[1] ? table.children[1].children : [];
  const outTable = tables[0];
  const inTable = tables[1];
  const outRows = edgeRows(outTable);
  const inRows = edgeRows(inTable);

  const expectedOut = (pack.scripts || []).filter((s) => s.scene === 40)
    .reduce((n, s) => n + (s.route || []).length, 0);
  const expectedIn = (pack.scripts || [])
    .flatMap((s) => s.route || []).filter((e) => e.scene === 40).length;
  check('本关出边表只列本关的边', outRows.length === expectedOut,
    `${outRows.length} 行（应 ${expectedOut}）`);
  check('入边表只列跳到本关的边', inRows.length === expectedIn,
    `${inRows.length} 行（应 ${expectedIn}）`);
  check('出边行的来源剧本是本关',
    outRows.every((tr) => tr.children[0].textContent.includes('第 40 关')),
    outRows.map((tr) => tr.children[0].textContent).join(' / '));
  check('入边行的目标就是本关',
    inRows.every((tr) => tr.children[3].textContent.includes('第 40 关')),
    inRows.map((tr) => tr.children[3].textContent).join(' / '));

  const clickable = [...outRows, ...inRows].every((tr) => {
    const cell = tr.children[3];
    return cell.children.some((c) => c.className === 'xref-link');
  });
  check('两表的「目标」列每一行都可点', clickable);

  const details = all(host, (n) => n.tagName === 'DETAILS')[0];
  const summary = details ? details.children[0].textContent : '';
  check('全部 63 条路线边收在默认折叠的 details 里',
    !!details && /全部 63 条路线边/.test(summary) && details.getAttribute('open') === null,
    summary);
  const edgeCount = (pack.scripts || []).reduce((n, s) => n + (s.route || []).length, 0);
  check('内容包里的路线边确实是 63 条', edgeCount === 63, `${edgeCount} 条`);
}

// --- 2) 「下一场景」是下拉而不是裸数字 --------------------------------------
console.log('\n2) 「下一场景 id」是下拉');
{
  const host = renderStage(40);
  const rows = all(host, (n) => n.className === 'route-operand-row');
  check('本关有「下一场景」控件行', rows.length > 0, `${rows.length} 行`);
  const selects = rows.flatMap((r) => r.children.filter((c) => c.tagName === 'SELECT'));
  const inputs = rows.flatMap((r) => r.children.filter((c) => c.tagName === 'INPUT'));
  check('下一场景是 <select>，不是数字输入框', selects.length > 0 && inputs.length === 0,
    `${selects.length} 个下拉 / ${inputs.length} 个输入框`);
  const options = selects.flatMap((s) => s.children.map((o) => o.textContent));
  check('选项文案同时含场景号与关卡名',
    options.some((t) => /^\d+ · 第 \d+ 关 · after 剧本$/.test(t)),
    options.find((t) => t.includes('after 剧本')) || '没有');
  check('有「0 · 场景 0」这一项', options.includes('0 · 场景 0'));
  const operand = (pack.scripts || []).filter((s) => s.scene === 40)
    .flatMap((s) => s.operands || []).find((o) => o.label === '下一场景 id');
  check('下拉覆盖了操作数的当前值',
    selects.some((s) => s.children.some((o) => o.getAttribute('value') === String(operand.value))),
    `当前值 ${operand.value}`);
}

// --- 3) 任务文案就地可改且只改本槽 ----------------------------------------
console.log('\n3) 任务文案就地可改');
{
  const host = renderStage(40);
  const titles = pack.textTable('mission_titles');
  const descs = pack.textTable('mission_descriptions');
  const base40 = pack.structure('mission_index').records[40].values.value;
  const before = pack.changedCount();
  const input = all(host, (n) => n.tagName === 'INPUT')
    .find((n) => n.value === titles.records[base40].text);
  check('找到标题输入框', !!input, input ? `值「${input.value}」` : '没有');
  if (input) {
    const next = '宝箱得到！';
    input.listeners.change[0]({ target: { value: next } });
    check('标题改完写回本槽', titles.records[base40].text === next,
      `「${titles.records[base40].text}」`);
    check('隔壁槽位没被动', descs.records[base40 + 1].text === '攻击练习。\n用「忍者组合拳」来打木叶丸',
      `「${String(descs.records[base40 + 1].text).slice(0, 8)}…」`);
    check('改动计数 +1', pack.changedCount() === before + 1,
      `${before} → ${pack.changedCount()}`);
    // 复原
    titles.records[base40].text = '得到宝箱！';
    titles.records[base40].original_text = '得到宝箱！';
    delete titles.records[base40].text_changed;
    titles.records[base40].tokens = null;
  }
}

// --- 4) 奖励可就地改、且与道具域是同一份数据 -------------------------------
console.log('\n4) 奖励可就地改');
{
  const host = renderStage(40);
  const rewards = pack.structure('reward_table');
  const base40 = pack.structure('mission_index').records[40].values.value;
  const record = rewards.records[base40];
  // 奖励在右侧「本关奖励」页签里 —— 先切过去。
  switchTab(host, '本关奖励');
  const blocks = all(host, (n) => n.className === 'route-reward');
  const block = blocks[0];
  const goldInput = all(block, (n) => n.tagName === 'INPUT')
    .find((n) => n.value === String(record.values.gold));
  check('找到金币输入框', !!goldInput, goldInput ? `值 ${goldInput.value}` : '没有');
  if (goldInput) {
    goldInput.listeners.change[0]({ target: { value: '250' } });
    check('金币改完写回奖励表同一条记录',
      rewards.records[base40].values.gold === 250 && record.values.gold === 250,
      `gold = ${rewards.records[base40].values.gold}`);
    check('改的就是道具域打开的那一条（同一个对象）',
      rewards.records[base40] === rewards.records.find((r) => r.id === base40));
    pack.setValue(rewards, record, 'gold', 100);
  }
  const jump = all(block, (n) => n.tagName === 'BUTTON')
    .find((b) => b.textContent === '在道具域打开这一条');
  check('行尾有「在道具域打开这一条」', !!jump);
  if (jump) {
    calls.length = 0;
    jump.listeners.click[0]({ target: {} });
    const moduleCall = calls.find((c) => c.module);
    const panelCall = calls.find((c) => c.kind);
    check('跳到道具域的同一条记录',
      moduleCall && moduleCall.module === 'items' &&
      panelCall && panelCall.kind === 'structure' &&
      panelCall.id === 'reward_table' &&
      panelCall.params.recordId === base40,
      `${moduleCall ? moduleCall.module : '?'} / ${panelCall ? `${panelCall.kind}/${panelCall.id}#${panelCall.params.recordId}` : '?'}`);
  }
}

// --- 5) 跨关共用必须显式告知 ----------------------------------------------
console.log('\n5) 跨关共用显式告知');
{
  const host = renderStage(40);
  const text = host.textContent;
  check('任务文案行写出「同时是第 41 关子 1」', text.includes('同时是第 41 关子 1'));
  check('任务文案行写出文本表下标', /文本表下标 #\d+/.test(text),
    (text.match(/文本表下标 #\d+/) || ['没有'])[0]);
  // 奖励在另一个页签里 —— 切过去再看。
  switchTab(host, '本关奖励');
  const rewardText = host.textContent;
  check('奖励行写出「奖励表 #」与归属', /奖励表 #\d+/.test(rewardText) && rewardText.includes('同时是第 41 关子 1'),
    (rewardText.match(/奖励表 #\d+/) || ['没有'])[0]);
  check('共用的一格写出「被 N 处共用」', /被 \d+ 处共用/.test(text),
    (text.match(/被 \d+ 处共用[^，]*/) || ['没有'])[0]);
  // 真正共用同一段字节的槽位（第 1 关的第 2 个子任务落在共用组里）
  const host1 = renderStage(1);
  const text1 = host1.textContent;
  check('共用同一段字节的槽位给出共用提示', /这段字被 \d+ 处共用，改一处会一起变/.test(text1),
    (text1.match(/这段字被 \d+ 处共用[^，]*/) || ['没有'])[0]);
}

// --- 6) 键盘与撤销 --------------------------------------------------------
console.log('\n6) 键盘与撤销');
{
  const host = renderStage(40);
  const rootNode = all(host, (n) => n.className === 'route-workbench')[0];
  calls.length = 0;
  rootNode.listeners.keydown[0]({ key: ']', target: rootNode });
  const next = calls.find((c) => c.kind === 'stage');
  check('按 ] 跳到第 41 关', !!next && next.params.stage === 41,
    next ? `stage ${next.params.stage}` : '没有');
  calls.length = 0;
  rootNode.listeners.keydown[0]({ key: 'g', target: rootNode });
  const graph = calls.find((c) => c.kind === 'graph');
  check('按 g 打开整条路线总览', !!graph, graph ? `#route/graph` : '没有');
  calls.length = 0;
  rootNode.listeners.keydown[0]({ key: '[', target: rootNode });
  const prev = calls.find((c) => c.kind === 'stage');
  check('按 [ 回到第 39 关', !!prev && prev.params.stage === 39,
    prev ? `stage ${prev.params.stage}` : '没有');

  // 改一次「下一场景」，再撤销
  const operand = (pack.scripts || []).filter((s) => s.scene === 40)
    .flatMap((s) => s.operands || []).find((o) => o.label === '下一场景 id');
  const before = operand.value;
  const patchBefore = pack.changedPatchCount();
  const select = all(host, (n) => n.className === 'route-operand-row')
    .flatMap((r) => r.children.filter((c) => c.tagName === 'SELECT'))
    .find((s) => s.children.some((o) => o.getAttribute('value') === '2'));
  check('找到「下一场景」下拉', !!select);
  if (select) {
    select.listeners.change[0]({ target: { value: '2' } });
    check('操作数改掉了', operand.value === 2, `value = ${operand.value}`);
    check('改动进了补丁表', pack.changedPatchCount() === patchBefore + 1,
      `${patchBefore} → ${pack.changedPatchCount()}`);
    pack.undo();
    check('撤销把操作数恢复成原值', operand.value === before,
      `value = ${operand.value}（原值 ${before}）`);
    check('撤销后改动计数回落', pack.changedPatchCount() === patchBefore,
      `${pack.changedPatchCount()}（原 ${patchBefore}）`);
  }
}

// --- 7) 整条路线总览、域首页与其余按键 ------------------------------------
console.log('\n7) 整条路线总览、域首页与其余按键');
{
  // 域首页
  ctx.state.view = { module: 'route', panel: null };
  const host = new StubNode('div');
  renderRoute(host, ctx);
  const text = host.textContent;
  check('域首页有「按关卡改」与「46 关的完整一环」',
    text.includes('按关卡改') && text.includes('46 关的完整一环'));
  check('域首页有「打开第 1 关」与「看整条路线」',
    text.includes('打开第 1 关') && text.includes('看整条路线'));
  check('域首页不再有自夸式说明句', !text.includes('路线不在任何表里'));

  // 整条路线总览（#route/graph）
  ctx.state.view = { module: 'route', panel: { kind: 'graph', id: 'graph', params: {} } };
  const graphHost = new StubNode('div');
  let error = null;
  try {
    renderRoute(graphHost, ctx);
  } catch (err) {
    error = err;
  }
  const graphText = graphHost.textContent;
  check('整条路线总览渲染成功', !error && graphText.length > 200,
    error ? String(error.message) : `${graphText.length} 字符`);
  check('总览列出全部 63 条路线边', graphText.includes('全部路线边（63 条）'));
  check('总览里有每一关的出边与入边', graphText.includes('每一关的出边与入边'));

  // 1 / 2 / 3 聚焦标题框，Esc 回域首页
  ctx.state.view = { module: 'route', panel: { kind: 'stage', id: 'stage', params: { stage: 40 } } };
  const stageHost = renderStage(40);
  const rootNode = all(stageHost, (n) => n.className === 'route-workbench')[0];
  const titles = pack.textTable('mission_titles');
  const base40 = pack.structure('mission_index').records[40].values.value;
  let focused = null;
  for (const input of all(stageHost, (n) => n.tagName === 'INPUT')) {
    input.focus = () => { focused = input; };
  }
  rootNode.listeners.keydown[0]({ key: '2', target: rootNode });
  check('按 2 聚焦第 2 个子任务的标题框',
    !!focused && focused.value === titles.records[base40 + 1].text,
    focused ? `「${focused.value}」` : '没有聚焦');
  calls.length = 0;
  rootNode.listeners.keydown[0]({ key: 'Escape', target: rootNode });
  check('按 Esc 回剧情路线域首页', calls.some((c) => c.module === 'route'),
    JSON.stringify(calls));
}

// --- 8) 右侧页签 ------------------------------------------------------------
console.log('\n8) 右侧页签：主界面是路线走向，其它配置按类分页');
{
  const host = renderStage(40);
  const tabLabels = all(host, (n) => String(n.className || '').split(/\s+/).includes('tab-btn'))
    .map((n) => n.textContent);
  check('工作台右侧有页签条', tabLabels.length >= 2, tabLabels.join(' / '));
  check('页签里有「任务文案」', tabLabels.some((t) => t.includes('任务文案')));
  check('页签里有「本关奖励」', tabLabels.some((t) => t.includes('本关奖励')));

  // 路线走向是**主界面**：它在左边常驻，不在页签里。
  const main = all(host, (n) => n.className === 'route-main')[0];
  check('左边是路线走向（主界面）', !!main && main.textContent.includes('路线走向'),
    main ? '有' : '没有');
  check('路线走向不在页签里', !tabLabels.some((t) => t.includes('路线走向')));

  // 任务文案那一页在，奖励那一页不在。
  const rewardBlocks = () => all(host, (n) => n.className === 'route-reward').length;
  check('默认页签是任务文案（奖励不在 DOM 里）', rewardBlocks() === 0,
    `${rewardBlocks()} 个奖励块`);
  check('切到「本关奖励」后奖励出现了', switchTab(host, '本关奖励') && rewardBlocks() === 3,
    `${rewardBlocks()} 个奖励块`);
  check('切走后任务文案也不在了', switchTab(host, '任务文案') && rewardBlocks() === 0,
    `${rewardBlocks()} 个奖励块`);

  // 角标：改一处任务文案，「任务文案」那一页要有角标。
  const titles = pack.textTable('mission_titles');
  const base40 = pack.structure('mission_index').records[40].values.value;
  const before = titles.records[base40].text;
  pack.setText(titles, titles.records[base40], '改一下');
  switchTab(host, '任务文案');
  const badge = all(host, (n) => String(n.className || '').split(/\s+/).includes('tab-badge'))
    .map((n) => n.textContent);
  check('改过的任务文案在页签上有角标', badge.includes('1'), badge.join(' / ') || '没有角标');
  pack.setText(titles, titles.records[base40], before);
  switchTab(host, '任务文案');
  const badge2 = all(host, (n) => String(n.className || '').split(/\s+/).includes('tab-badge'))
    .map((n) => n.textContent);
  check('改回原值后角标消失', !badge2.includes('1'), badge2.join(' / ') || '没有角标');
}

console.log(failures === 0 ? '\n全部通过' : `\n${failures} 项失败`);
process.exit(failures === 0 ? 0 : 1);
