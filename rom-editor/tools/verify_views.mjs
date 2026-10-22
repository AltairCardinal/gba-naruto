// Headless view test: render the editor's views without a browser.
//
// The in-browser self-test (tools/selftest.html) covers the same ground, but
// this environment's embedded browser keeps reloading the tab, so the page
// never finishes a run.  This file renders the same views against a minimal
// DOM stub, which makes the view assertions reproducible in CI.
//
// Run:  node tools/verify_views.mjs
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
    // style 得有 setProperty / getPropertyValue —— splitPane() 会写
    // --split-right 这个 CSS 变量（列表 / 详情两栏的宽度）。
    this.style = {
      setProperty() {},
      getPropertyValue() { return ''; },
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
  /** Every descendant element (the stub has no CSS engine). */
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

const documentStub = {
  createElement: (tag) => new StubNode(tag),
  createTextNode: (text) => ({ __text: String(text), textContent: String(text), nodeType: 3 }),
  body: new StubNode('body'),
  getElementById: () => null,
  querySelector: () => null,
};
globalThis.document = documentStub;
globalThis.setTimeout = globalThis.setTimeout || (() => 0);
globalThis.window = {
  location: { hash: '' },
  addEventListener() {},
  removeEventListener() {},
};

const { ContentPack } = await import('../js/pack.js');
const { renderStory } = await import('../js/modules/story.js');
const { renderItems } = await import('../js/modules/items.js');
const { renderCharacters } = await import('../js/modules/characters.js');
const { renderNinjutsu } = await import('../js/modules/ninjutsu.js');
const { renderBattle } = await import('../js/modules/battle.js');
const routeModule = await import('../js/modules/route.js');
const renderRoute = routeModule.renderRoute;
const renderRouteStage = routeModule.renderStage;
const { renderAudio } = await import('../js/modules/audio.js');
const { renderAssets } = await import('../js/modules/assets.js');
const { renderRaw } = await import('../js/modules/raw.js');

const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, '..');

let failures = 0;
function check(name, ok, detail = '') {
  if (!ok) failures += 1;
  console.log(`  [${ok ? 'PASS' : 'FAIL'}] ${name}${detail ? ' — ' + detail : ''}`);
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

const packData = JSON.parse(readFileSync(join(root, 'content', 'pack.json'), 'utf8'));
const pack = ContentPack.fromJSON(packData);
try {
  const index = JSON.parse(gunzipSync(readFileSync(join(root, 'content', 'text-index.json.gz'))).toString('utf8'));
  pack.texts.push(index);
} catch (err) {
  console.log('  （未找到 text-index.json.gz）');
}

const statuses = [];
// A synthetic canvas that mirrors the real ROM's shape: zeroed, with the
// 0xFF free region at 0x5DFBEC that the text rewriter allocates from.
const base = new Uint8Array(0x600000);
base.fill(0xff, 0x5dfbec);
const ctx = {
  pack,
  rom: base,
  baseRom: base,
  state: { view: { panel: null } },
  onChange() {},
  openPanel() {},
  render() {},
  setStatus(message) { statuses.push(message); },
};

console.log('1) 每个模块的首页都能渲染');
const MODULES = [
  ['剧情与对白', renderStory],
  ['道具', renderItems],
  ['角色属性与技能', renderCharacters],
  ['忍术', renderNinjutsu],
  ['战斗', renderBattle],
  ['剧情路线', renderRoute],
  ['音频', renderAudio],
  ['素材与资源', renderAssets],
  ['原始字节', renderRaw],
];
for (const [label, render] of MODULES) {
  const host = new StubNode('div');
  ctx.state.view = { panel: null };
  let error = null;
  try {
    render(host, ctx);
  } catch (err) {
    error = err;
  }
  const text = host.textContent;
  check(`${label}：首页渲染`, !error && text.length > 80,
    error ? String(error.message) : `${text.length} 字符`);
}

console.log('\n2) 战斗：第 40 关的战场地图（主界面）与右侧页签');
{
  const host = new StubNode('div');
  let error = null;
  let text = '';
  try {
    ctx.state.view = { panel: { kind: 'map', id: 'map', params: { stage: 40, variant: 0 } } };
    renderBattle(host, ctx);
    text = host.textContent;
  } catch (err) {
    error = err;
  }
  check('战斗视图渲染成功', !error && text.length > 200,
    error ? String(error.message) : `${text.length} 字符`);

  // 右侧面板是分页签的：五类配置各占一页。
  const tabLabels = host.descendants()
    .filter((n) => String(n.className || '').split(/\s+/).includes('tab-btn'))
    .map((n) => n.textContent);
  check('战斗视图有页签条', tabLabels.length >= 5, tabLabels.join(' / '));
  for (const needle of ['战场布置', '战场物件', '角色出生点', '胜负条件', '剧情触发']) {
    check(`战斗视图的页签里有「${needle}」`, tabLabels.some((t) => t.includes(needle)));
  }
  // 地图是主界面：画布在
  check('战斗视图画出了地图', host.descendants().some((n) => n.className === 'map-canvas'));

  // 切到「胜负条件」那一页
  switchTab(host, '胜负条件');
  const rulesText = host.descendants()
    .filter((n) => String(n.className || '').split(/\s+/).includes('tab-body'))
    .map((n) => n.textContent).join('');
  check('胜负条件那一页里有胜利与失败', rulesText.includes('胜利') && rulesText.includes('失败'));
  check('胜负条件那一页里有回合上限', rulesText.includes('回合上限'));

  // 说明文字必须显示成原文，而不是只有指针
  const rules = pack.structure('battle_rules');
  const rule = rules.records.find((r) => r.rom_offset === 0x594758 + 40 * 0xcc);
  const objectives = pack.textTable('battle_objectives');
  const byPointer = new Map();
  for (const r of objectives.records) byPointer.set(r.pointer, r);
  let sample = '';
  for (let g = 0; g < 2 && !sample; g++) {
    for (let k = 0; k < 4 && !sample; k++) {
      const ptr = rule.values[`g${g}_${k}_text_ptr`];
      if (!ptr) continue;
      const rec = byPointer.get(ptr);
      if (rec && rec.text) sample = rec.text;
    }
  }
  // 说明文字放在输入框里，所以要读输入框的 value（不是 textContent）
  const inputs = host.descendants().filter((n) => n.tagName === 'INPUT');
  const values = inputs.map((n) => n.value);
  check('说明文字是可编辑的输入框', !!sample && values.includes(sample),
    `输入框 ${inputs.length} 个，样例「${sample}」${values.includes(sample) ? '在其中' : '不在其中'}`);
  // 输入框下面还要标出字节用量与地址
  check('说明文字标出字节用量与地址', /\d+ \/ \d+ 字节 · 0x[0-9A-F]+/.test(rulesText),
    (rulesText.match(/\d+ \/ \d+ 字节 · 0x[0-9A-F]+/) || ['没有'])[0]);

  // 类型 2 的语义必须与原生行为一致
  check('类型 2 标注为「回合用尽」', rulesText.includes('回合用尽'),
    rulesText.includes('回合用尽') ? '已标注' : '没有标注');
  check('不再声称类型 2 是「指定角色仍在场」', !rulesText.includes('指定角色仍在场上'));

  // 参数含义要写出来
  check('参数含义被标注', rulesText.includes('角色 id') || rulesText.includes('道具序号'));

  // 战斗目标的条件类型应当是**下拉**（语义取自内容包的 enum，只有这一处真相）
  const battleSelects = host.descendants().filter((n) => n.tagName === 'SELECT');
  const battleOptions = battleSelects.flatMap((s) => s.children.map((o) => o.textContent));
  check('条件类型是下拉且带原生语义',
    battleOptions.some((t) => t.includes('回合用尽')),
    (battleOptions.find((t) => t.includes('回合用尽')) || '没有下拉').slice(0, 40));

  // 「本关剧情脚本里可改的操作数」以前永远是空的（筛选排除了有操作数的剧本）
  const hasOperands = (pack.scripts || []).some(
    (s) => s.scene === 40 && (s.operands || []).length);
  switchTab(host, '剧情触发');
  const scriptText = host.descendants()
    .filter((n) => String(n.className || '').split(/\s+/).includes('tab-body'))
    .map((n) => n.textContent).join('');
  check('本关剧本的操作数小节不再是空的',
    !hasOperands || scriptText.includes('本关剧情脚本里可改的操作数'),
    hasOperands ? '有操作数，必须显示出来' : '本关确实没有操作数');
  check('剧情触发那一页列出四个剧本入口',
    ['战前剧情', '战后剧情', '战场事件逻辑', '战场事件表']
      .every((name) => scriptText.includes(name)));

  // 每一行都能跳到通用表格的同一条记录
  switchTab(host, '战场物件');
  const jumpLinks = host.descendants().filter((n) => n.textContent === '↗');
  check('战场物件能跳到通用表格的同一条记录', jumpLinks.length > 0,
    `${jumpLinks.length} 个跳转`);

  // 本关改动数
  check('显示本关已改几处',
    text.includes('本关已改') || text.includes('本关还没有改动'),
    (text.match(/本关[^，。]{0,8}/) || [''])[0]);

  // --- 就地编辑：改一个出生点的 X，落点必须正确 -------------------------
  switchTab(host, '角色出生点');
  const actors = pack.structure('battle_actors');
  const slot0 = actors.records.find(
    (r) => r.rom_offset === 0x5461c4 + 40 * 0x1aac + 4);
  // 出生点表：槽 / 角色 / 阵营 / X / Y / 朝向 / 等级 / ↗
  //   —— X 是第 4 列（从 0 数）。
  const actorTable = host.descendants().find((n) => n.tagName === 'TABLE');
  const actorRow = actorTable
    ? (actorTable.children.find((n) => n.tagName === 'TBODY') || { children: [] }).children
      .find((n) => n.tagName === 'TR')
    : null;
  const xInput = actorRow
    ? actorRow.children.filter((n) => n.tagName === 'TD')[3]
      .descendants().find((n) => n.tagName === 'INPUT')
    : null;
  check('出生点表格里 X 是可编辑输入框', !!xInput && xInput.value === String(slot0.values.x),
    `X=${xInput ? xInput.value : '没有输入框'}（原生 ${slot0.values.x}）`);
  if (xInput) {
    // 地图视图的坐标框有**越界拦截**（第 40 关的地图只有 9 列），
    // 所以这里用一个合法值 —— 越界的那条由 verify_battle_map 单独验。
    const originalX = slot0.values.x;
    xInput.listeners.change[0]({ target: { value: '5' } });
    const changed = slot0.values.x === 5;
    check('改出生点的 X 立刻写回内容包', changed,
      `x = ${slot0.values.x}`);
    // 构建后必须只动那一个字节
    const { buildRom } = await import('../js/rom.js');
    const rom = new Uint8Array(0x600000);
    rom.fill(0xff, 0x5dfbec);
    const out = buildRom(pack, rom);
    const offset = slot0.rom_offset + 0x02;   // x 在记录里的偏移
    check('改出生点的 X 只动那一个字节',
      out.report.errors.length === 0 && out.bytes[offset] === 5,
      out.report.errors.join('; ') ||
      `@0x${offset.toString(16)} = ${out.bytes[offset]}`);
    // 复原，避免影响后面的断言
    slot0.values.x = originalX;
  }
}

console.log('\n2b) 忍术域：记录表与名表合成一个忍术来改');
{
  const { renderJutsu } = await import('../js/modules/jutsu.js');
  const host = new StubNode('div');
  let error = null;
  try {
    renderJutsu(host, ctx, {});
  } catch (err) {
    error = err;
  }
  const text = host.textContent || '';
  check('忍术视图渲染成功', !error && text.length > 200,
    error ? String(error.message) : `${text.length} 字符`);
  check('忍术视图是「一个忍具一个对象」的说法',
    text.includes('忍术记录表') && text.includes('忍术名表'));
  // 左边列出 87 个忍术
  const rows = host.descendants().filter((n) => n.tagName === 'TR').length;
  check('左边按忍术 id 列出', rows >= 87, `${rows} 行`);

  // 名字页签能改名字（名字表由指针表驱动，可变长）
  const tabBtn = host.descendants()
    .find((n) => String(n.className || '').split(/\s+/).includes('tab-btn')
      && n.textContent.includes('名字'));
  check('有「名字」页签', !!tabBtn);
  if (tabBtn) {
    tabBtn.listeners.click[0]();
    const input = host.descendants().find((n) => n.tagName === 'INPUT');
    check('名字那一页有输入框', !!input, input ? `值「${input.value}」` : '没有');
  }
}

console.log('\n3) 剧情路线：第 40 关的视图');
{
  const host = new StubNode('div');
  let error = null;
  let text = '';
  try {
    renderRouteStage(host, ctx, 40);
    text = host.textContent;
  } catch (err) {
    error = err;
  }
  check('剧情路线视图渲染成功', !error && text.length > 200,
    error ? String(error.message) : `${text.length} 字符`);
  for (const needle of ['剧情脚本', '剧情路线', '任务文本', '奖励']) {
    check(`剧情路线视图含「${needle}」`, text.includes(needle));
  }
  // 路线边必须真的列出来（脚本里的「下一场景」）
  const edges = (pack.scripts || []).reduce((n, s) => n + ((s.route || []).length), 0);
  check('剧情路线列出脚本里的路线边', edges > 0 && text.includes('0x16') || text.includes('0x1A'),
    `内容包里有 ${edges} 条边`);
  // 本关的任务文本必须显示出来（标题/说明/提示）
  const titles = pack.textTable('mission_titles');
  const descs = pack.textTable('mission_descriptions');
  const hints = pack.textTable('mission_hints');
  const index = pack.structure('mission_index');
  const base = index.records[40] ? index.records[40].values.value : null;
  const slot = base === null ? null : base;
  const titleText = slot !== null && titles.records[slot] ? titles.records[slot].text : '';
  const descText = slot !== null && descs.records[slot] ? descs.records[slot].text : '';
  const hintText = slot !== null && hints.records[slot] ? hints.records[slot].text : '';
  check('本关任务标题/说明/提示都显示出来',
    !!titleText && !!descText && !!hintText &&
    text.includes(titleText) && text.includes(descText) && text.includes(hintText),
    `标题「${titleText}」说明「${(descText || '').slice(0, 12)}…」提示「${(hintText || '').slice(0, 12)}…」`);
}

console.log('\n4) 字段元数据：枚举 / 跨表引用 / 分组 / 原始字节表');
{
  const fields = await import('../js/fields.js');
  const rules = pack.structure('battle_rules');
  const rule = rules.records.find((r) => r.rom_offset === 0x594758 + 40 * 0xcc);

  // 4a. 枚举 → 下拉（标签是人话，不是裸数字）
  const typeField = rules.fields.find((f) => f.key === 'g0_0_type');
  const control = fields.fieldControl(ctx, rules, rule, typeField);
  const options = control.node.children ? control.node.children.map((o) => o.textContent) : [];
  check('枚举字段渲染成下拉并带中文标签',
    control.node.tagName === 'SELECT' && options.some((t) => t.includes('回合用尽')),
    `选项：${options.slice(0, 3).join(' / ')}`);

  // 4b. 跨表引用 → 显示出名字
  const actors = pack.structure('battle_actors');
  const slot = actors.records.find((r) => r.rom_offset === 0x5461c4 + 40 * 0x1aac + 4);
  const actorHint = fields.fieldControl(
    ctx, actors, slot, actors.fields.find((f) => f.key === 'character_id')).hint.join(' | ');
  check('角色 id 显示成角色名', actorHint.includes('漩涡鸣人'), actorHint);

  // 4c. 奖励的物品 id 依赖同槽的类别
  const rewards = pack.structure('reward_table');
  const reward = rewards.records.find((r) => {
    const v = r.values;
    return v.slot0_category && v.slot0_item;
  });
  const itemHint = rewards
    ? fields.fieldControl(ctx, rewards, reward,
        rewards.fields.find((f) => f.key === 'slot0_item')).hint.join(' | ')
    : '';
  check('奖励物品 id 按类别显示对应名字', /物品名：/.test(itemHint), itemHint || '没有带掉落的记录');

  // 4d. 分组信息没丢
  const groups = fields.groupFields(rules.fields);
  check('字段分组被保留',
    groups.length >= 3 && groups.some((g) => g.name === '胜利条件'),
    groups.map((g) => `${g.name}×${g.fields.length}`).join('、'));

  // 4e. 整张表都是未解码字节 → 认出来
  check('整表未解码的结构被标记为 raw_only',
    fields.isRawOnly(pack.structure('item_record')),
    '道具/忍具记录表 94 条全是原始字节');
}

console.log('\n5) 结构编辑器：分组折叠 + 重复槽位成表 + 记录导航');
{
  const { StructureEditor } = await import('../js/editors.js');
  const host = new StubNode('div');
  const template = pack.structure('character_template');
  const editor = new StructureEditor(pack, template, { onChange: ctx.onChange });
  editor.render(host);
  const text = host.textContent;

  // 5a. 分组：角色定义表的 5 个分组都在，标题可读
  const groups = template.fields.reduce((set, f) => {
    if (f.group) set.add(f.group);
    return set;
  }, new Set());
  check('字段分组被渲染成可折叠分区', groups.size >= 5,
    [...groups].join('、'));

  // 5b. 默认只展开「有主列的分组」，其余折叠（标题里带规模）
  const record = template.records.find((r) => r.id === 1);
  editor.openDetail(record);
  const defaultInputs = host.descendants().filter(
    (n) => n.tagName === 'INPUT' || n.tagName === 'TEXTAREA' || n.tagName === 'SELECT');
  check('默认只展开少量分组', defaultInputs.length < 30,
    `默认 ${defaultInputs.length} 个控件（字段共 ${template.fields.length} 个）`);

  // 5c. 展开全部分组后，重复槽位渲染成表格
  editor.collapsed.clear();
  editor.openDetail(record);
  const all = host.descendants();
  const slotTables = all.filter((n) => n.className === 'grid grid-slots');
  const inTable = new Set();
  for (const table of slotTables) {
    for (const row of table.descendants()) inTable.add(row);
  }
  const loose = all.filter(
    (n) => ['INPUT', 'TEXTAREA', 'SELECT'].includes(n.tagName) && !inTable.has(n));
  check('重复槽位渲染成表格', slotTables.length >= 2,
    `${slotTables.length} 张槽位表`);
  check('槽位之外的控件很少', loose.length < 40,
    `表内 ${all.filter((n) => ['INPUT', 'TEXTAREA', 'SELECT'].includes(n.tagName)).length - loose.length} 个 + 表外 ${loose.length} 个`);

  // 5c. 槽位表里的行数 = 槽位数
  const jutsuTable = slotTables[0];
  const rows = jutsuTable ? jutsuTable.children[1].children : [];
  check('忍术槽是 15 行的表', rows.length === 15, `${rows.length} 行`);

  // 5d. 枚举 → 下拉；引用 → 名字
  const selects = all.filter((n) => n.tagName === 'SELECT');
  const optionTexts = selects.flatMap((s) => s.children.map((o) => o.textContent));
  check('档位用下拉并带中文标签',
    optionTexts.some((t) => t.includes('未习得')),
    optionTexts.slice(0, 4).join(' / '));
  check('忍术 id 显示成忍术名',
    (host.textContent || '').includes('分身术') ||
    (host.textContent || '').includes('变身术'),
    ((host.textContent || '').match(/分身术|变身术|螺旋丸/) || ['没有'])[0]);

  // 5e. 记录导航：下一条 / 上一条
  const navTexts = all.filter((n) => n.tagName === 'BUTTON').map((b) => b.textContent);
  check('详情面板有上一条/下一条', navTexts.includes('← 上一条') && navTexts.includes('下一条 →'),
    navTexts.filter((t) => t.includes('条')).join(' / '));

  // 5f. 改动标记
  const hpField = template.fields.find((f) => f.key === 'hp_base');
  const hpOriginal = record.values.hp_base;
  pack.setValue(template, record, 'hp_base', 123);
  editor.renderTable();
  const rowsAfter = host.descendants().filter((n) => n.tagName === 'TR');
  const changedRow = rowsAfter.find((tr) => (tr.className || '').includes('changed'));
  check('改过的记录在表格里被标出来', !!changedRow,
    changedRow ? '有 changed 标记' : '没有标记');
  pack.setValue(template, record, 'hp_base', hpOriginal);
}

console.log('\n6) 写回安全性：越界拒绝 / 有符号原值 / 指针解析 / 改后即刷新');
{
  const { StructureEditor } = await import('../js/editors.js');
  const fields = await import('../js/fields.js');

  // 6a. 越界必须被拒绝，不能落到写回时的掩码里（999 → 231 那种静默截断）
  const template = pack.structure('character_template');
  const templateRecord = template.records.find((r) => r.id === 1);
  const statA = template.fields.find((f) => f.key === 'stat_a');
  const statABefore = templateRecord.values.stat_a;
  const control = fields.fieldControl(ctx, template, templateRecord, statA);
  control.node.listeners.change[0]({ target: { value: '999' } });
  check('越界的数值被拒绝写回',
    templateRecord.values.stat_a === statABefore,
    `u8 字段输入 999，原值 ${statABefore}，现在 ${templateRecord.values.stat_a}`);

  // 6b. s16 必须按有符号读：原值 -4，不是 65532
  const delta = pack.structure('unit_delta_table');
  const deltaRecord = delta.records[0];
  const deltaField = delta.fields.find((f) => f.key === 'delta');
  const original = fields.originalValue(delta, deltaRecord, deltaField);
  check('有符号字段按有符号读', original === -4, `原值 ${original}`);

  // 6c. 指针型 relation 要按地址查表（说明文字指针 → 那句话）
  const rules = pack.structure('battle_rules');
  const rule = rules.records.find((r) => r.rom_offset === 0x594758 + 40 * 0xcc);
  const ptrField = rules.fields.find((f) => f.key === 'g0_0_text_ptr');
  const ptrValue = rule.values[ptrField.key];
  const hit = fields.resolveRelation(pack, ptrField.relation, ptrValue);
  check('说明文字指针解析出那句话',
    !!hit && hit.name === '得到宝箱了',
    `0x${(ptrValue >>> 0).toString(16).toUpperCase()} → ${hit ? hit.name : '没解析出来'}`);

  // 6d. 改完必须立刻刷新：表格有 changed 标记、字段带「已改」
  const host = new StubNode('div');
  const editor = new StructureEditor(pack, template, { onChange: ctx.onChange });
  editor.render(host);
  const record = template.records.find((r) => r.id === 1);
  const hpBefore = record.values.hp_base;
  editor.openDetail(record);
  const hpField = template.fields.find((f) => f.key === 'hp_base');
  const hpInput = editor.detail.descendants().find(
    (n) => n.tagName === 'INPUT' && n.value === String(hpBefore));
  check('找到 HP 基础输入框', !!hpInput, hpInput ? `值 ${hpInput.value}` : '没有');
  if (hpInput) {
    hpInput.listeners.change[0]({ target: { value: '123' } });
    const changedRows = host.descendants().filter(
      (n) => n.tagName === 'TR' && (n.className || '').includes('changed'));
    const changedFields = editor.detail.descendants().filter(
      (n) => (n.className || '').includes('field-changed'));
    check('改完立刻刷新：行有 changed 标记',
      changedRows.length > 0,
      `${changedRows.length} 行被标记`);
    check('改完立刻刷新：字段带「已改」',
      changedFields.length > 0,
      `${changedFields.length} 个字段被标记`);
    // 复原
    pack.setValue(template, record, 'hp_base', hpBefore);
  }
}

console.log('\n7) 文本表编辑器：写回规则 / 控制码分段 / 标记 / 行数上限 / 无位置槽');
{
  const { TextTableEditor } = await import('../js/editors.js');
  const host = new StubNode('div');

  // 7a. 写回规则要说清楚：可重定位 vs 等长
  const names = pack.textTable('character_names');
  const reloc = new TextTableEditor(pack, names, { onChange: ctx.onChange });
  reloc.render(host);
  check('可重定位表说明写回规则',
    (host.textContent || '').includes('长度可变'),
    (host.textContent || '').slice(0, 40));
  const objectives = pack.textTable('battle_objectives');
  const fixed = new TextTableEditor(pack, objectives, { onChange: ctx.onChange });
  const host2 = new StubNode('div');
  fixed.render(host2);
  check('等长表说明写回规则',
    (host2.textContent || '').includes('长度不能变'),
    (host2.textContent || '').includes('长度不能变') ? '已说明' : '没有说明');

  // 7b. 控制码分段条
  const desc = pack.textTable('mission_descriptions');
  const withCtrl = desc.records.find((r) => r.text && r.raw && r.raw.includes('AQ'));
  if (!withCtrl) {
    check('控制码分段条', false, '没有找到带控制码的记录');
  } else {
    const host3 = new StubNode('div');
    const editor = new TextTableEditor(pack, desc, { onChange: ctx.onChange });
    editor.render(host3);
    editor.openDetail(withCtrl);
    const segs = host3.descendants().filter((n) => (n.className || '').includes('seg-ctrl'));
    check('控制码分段条把控制码画出来', segs.length > 0,
      `${segs.length} 个控制码段`);
  }

  // 7c. 共享 / 归属标记
  const titles = pack.textTable('mission_titles');
  const shared = titles.records.find((r) => (r.shared_with || []).length > 0);
  const host4 = new StubNode('div');
  const editor4 = new TextTableEditor(pack, titles, { onChange: ctx.onChange });
  editor4.render(host4);
  const chips = host4.descendants().filter((n) => (n.className || '').includes('mark-shared'));
  check('共用同一段字节的条目被标出来', chips.length > 0,
    shared ? `${shared.shared_with.length + 1} 处共用` : '没有共用条目');

  // 7d. 大表默认只渲染前 200 行
  const index = pack.textTable('rom_text_index');
  if (!index) {
    check('大表默认只渲染前 200 行', false, '文本索引未载入');
  } else {
    const host5 = new StubNode('div');
    const editor5 = new TextTableEditor(pack, index, { onChange: ctx.onChange });
    editor5.render(host5);
    const rows = host5.descendants().filter((n) => n.tagName === 'TR').length;
    check('大表默认只渲染前 200 行', rows <= 201, `渲染了 ${rows} 行（含表头）`);
    check('被具名表拥有的条目默认不显示',
      (host5.textContent || '').includes('显示已被其它表拥有的条目'),
      '有开关');
  }

  // 7e. 没有 ROM 位置的槽位不可编辑
  const slots = pack.textTable('dialogue_slots');
  const nullSlot = slots.records.find((r) => r.text_offset === null);
  if (!nullSlot) {
    check('无位置的槽位不可编辑', false, '没有找到空指针槽');
  } else {
    const host6 = new StubNode('div');
    const editor6 = new TextTableEditor(pack, slots, { onChange: ctx.onChange });
    editor6.render(host6);
    editor6.openDetail(nullSlot);
    const areas = editor6.detail.descendants().filter((n) => n.tagName === 'TEXTAREA');
    check('无位置的槽位不可编辑', areas.length > 0 && areas[0].attributes.disabled === '',
      areas.length ? '文本框已禁用' : '没有文本框');
  }
}

console.log('\n8) 域首页：每张表都够得着 + 带可编辑性信息');
{
  const DOMAINS = [
    ['剧情与对白', renderStory, 'story'],
    ['道具', renderItems, 'items'],
    ['角色属性与技能', renderCharacters, 'characters'],
    ['忍术', renderNinjutsu, 'ninjutsu'],
    ['战斗', renderBattle, 'battle'],
    ['剧情路线', renderRoute, 'route'],
    ['音频', renderAudio, 'audio'],
    ['素材与资源', renderAssets, 'assets'],
  ];
  for (const [label, render, module] of DOMAINS) {
    const host = new StubNode('div');
    ctx.state.view = { panel: null };
    let error = null;
    try {
      render(host, ctx);
    } catch (err) {
      error = err;
    }
    const text = host.textContent || '';
    const tables = host.descendants().filter((n) => n.tagName === 'TR');
    const cards = host.descendants().filter((n) => (n.className || '') === 'stat');
    const expected = pack.structures.filter((s) => s.module === module).length +
      pack.texts.filter((t) => t.module === module).length;
    // 几张表合成一行时，行数会少于表数 —— 按「覆盖了几张表」判可达性
    // （common.js 把这个数写在 table 的 data-covered 上；自己画表的域
    //  没有这个属性，那就退回按行数判）。
    const domainTables = host.descendants().filter((n) => n.className === 'grid domain-tables');
    const covered = domainTables.reduce((n, t) => {
      const value = Number((t.dataset || {}).covered || 0);
      return value > n ? value : n;
    }, 0);
    const reached = covered > 0 ? covered >= expected : tables.length >= expected;
    check(`${label}：域首页渲染且列出本域全部表`,
      !error && reached &&
      (host.textContent || '').includes('本域可编辑内容'),
      error ? String(error.message)
        : `覆盖 ${covered || tables.length} 张表（应 ≥ ${expected}）· ${tables.length} 行`);
    check(`${label}：不再是纯卡片墙`, cards.length <= 5,
      `${cards.length} 张卡片`);
  }

  // 战斗域的 7 张表以前在首页根本够不着
  const battleHost = new StubNode('div');
  ctx.state.view = { panel: null };
  renderBattle(battleHost, ctx);
  const battleText = battleHost.textContent || '';
  const hidden = ['单位槽位重映射表', '八方向位移表', '战场事件逻辑根表', '战场事件根表',
    '战斗/地图事件处理程序分派表', '精灵帧描述符表', '原生拾取分派表'];
  const stillHidden = hidden.filter((name) => !battleText.includes(name));
  check('战斗域 7 张原先够不着的表现在都在首页',
    stillHidden.length === 0,
    stillHidden.length ? `还缺：${stillHidden.join('、')}` : '全部可达');

  // 剧情与对白域的字宽表以前任何域都够不着
  const storyHost = new StubNode('div');
  ctx.state.view = { panel: null };
  renderStory(storyHost, ctx);
  check('字宽表现在在剧情与对白域首页',
    (storyHost.textContent || '').includes('字宽表'),
    '可达');
}

console.log('\n9) 导航：URL 可寻址 + 跨域引用可点');
{
  const routing = await import('../js/routing.js');
  const cases = [
    ['#overview', 'overview', null],
    ['#battle', 'battle', null],
    // 战斗域的关卡视图已经并进战场地图：老地址仍然能开，开的是地图。
    ['#battle/stage/40/0', 'battle', 'map'],
    ['#battle/map/40/0', 'battle', 'map'],
    ['#characters/structure/character_template/1', 'characters', 'structure'],
    ['#characters/text/dialogue_slots/12', 'characters', 'text'],
  ];
  for (const [hash, module, kind] of cases) {
    const parsed = routing.parseHash(hash);
    check(`URL 可寻址 ${hash}`,
      parsed.module === module && (kind === null || (parsed.panel && parsed.panel.kind === kind)),
      `${parsed.module}/${parsed.panel ? parsed.panel.kind : '无面板'}`);
  }
  check('hash 能写回去',
    routing.hashFor({ module: 'characters', panel: { kind: 'structure', id: 'character_template', params: { recordId: 1 } } })
      === '#characters/structure/character_template/1',
    '往返一致');

  // 跨域跳转：忍术 id 字段旁边应当有可点的链接
  const { StructureEditor } = await import('../js/editors.js');
  const template = pack.structure('character_template');
  const jumps = [];
  const host = new StubNode('div');
  const editor = new StructureEditor(pack, template, {
    onChange: ctx.onChange,
    onJump: (target) => jumps.push(target),
  });
  editor.render(host);
  const record = template.records.find((r) => r.id === 1);
  editor.collapsed.clear();     // 忍术槽在折叠的分组里，展开才看得见链接
  editor.openDetail(record);
  const links = editor.detail.descendants().filter((n) => (n.className || '') === 'xref-link');
  check('跨表引用是可点的链接', links.length > 0, `${links.length} 个链接`);
  if (links.length) {
    links[0].listeners.click[0]({ target: {} });
    const target = jumps[0];
    check('点击链接跳到目标表与记录',
      !!target && target.module === 'ninjutsu' && target.kind === 'text' &&
      target.id === 'jutsu_names' && target.recordId !== null,
      target ? `${target.module}/${target.kind}/${target.id}#${target.recordId}` : '没有跳转');
  }
}

console.log('\n10) 撤销：字段级恢复 + 全局撤销栈');
{
  const { StructureEditor } = await import('../js/editors.js');
  const template = pack.structure('character_template');
  const record = template.records.find((r) => r.id === 1);
  const hpField = template.fields.find((f) => f.key === 'hp_base');
  const before = record.values.hp_base;

  // 字段级 ↺：把这个字段恢复成原值
  const host = new StubNode('div');
  const editor = new StructureEditor(pack, template, { onChange: ctx.onChange });
  editor.render(host);
  editor.openDetail(record);
  const hpInput = editor.detail.descendants().find(
    (n) => n.tagName === 'INPUT' && n.value === String(before));
  if (!hpInput) {
    check('找到 HP 基础输入框', false, '没有');
  } else {
    hpInput.listeners.change[0]({ target: { value: '123' } });
    check('改值后记录被标记为已改', record.values.hp_base === 123,
      `hp_base = ${record.values.hp_base}`);
    // 找 ↺ 按钮并点它（要的是 hp_base 那个字段里的那一个）
    const field = hpInput.parentElement;
    const undoButton = field
      ? field.descendants().find((n) => n.tagName === 'BUTTON' && n.textContent === '↺')
      : null;
    check('改过的字段旁边有 ↺ 恢复按钮', !!undoButton, undoButton ? '有' : '没有');
    if (undoButton) {
      undoButton.listeners.click[0]({ target: {} });
      check('↺ 把字段恢复成原值', record.values.hp_base === before,
        `hp_base = ${record.values.hp_base}（原值 ${before}）`);
    }
  }

  // 全局撤销栈
  const depthBefore = pack.undoDepth;
  pack.setValue(template, record, 'stat_a', (record.values.stat_a + 1) % 200);
  const changed = record.values.stat_a;
  check('改动进了撤销栈', pack.undoDepth === depthBefore + 1,
    `栈深 ${depthBefore} → ${pack.undoDepth}`);
  pack.undo();
  check('撤销把值恢复回去', record.values.stat_a !== changed,
    `stat_a = ${record.values.stat_a}`);
  pack.setValue(template, record, 'stat_a', changed);
  pack.undo();
}

console.log('\n11) 通用能力：记录名 / 按名字搜 / 反查引用');
{
  const { StructureEditor } = await import('../js/editors.js');
  const { idRelationName } = await import('../js/fields.js');
  const { backReferences, missionIndexOwners } = await import('../js/xref.js');

  // 11a. 有 id_relation 的表，记录有名字
  const jutsu = pack.structure('jutsu_record');
  const named = jutsu.records.find((r) => idRelationName(pack, jutsu, r));
  check('记录名能从 id_relation 解析出来', !!named,
    named ? `id ${named.id} = ${idRelationName(pack, jutsu, named)}` : '没有');

  // 11b. 按名字能搜到（以前搜「分身术」永远 0 命中）
  const host = new StubNode('div');
  const editor = new StructureEditor(pack, jutsu, { onChange: ctx.onChange });
  editor.render(host);
  const name = named ? idRelationName(pack, jutsu, named) : '';
  editor.query = name;
  check('按名字能搜到记录', editor.records.length > 0,
    `搜「${name}」命中 ${editor.records.length} 条`);

  // 11c. 列表里多出名字一列
  editor.query = '';
  editor.renderTable();
  const nameCells = host.descendants().filter((n) => (n.className || '') === 'name-cell');
  check('记录列表显示名字', nameCells.length > 0,
    `${nameCells.length} 行有名字`);

  // 11d. 反查：谁引用了这条忍术（挑一条真的被引用的，跳过 id 0 的「没有」占位）
  const allRefs = jutsu.records
    .filter((r) => r.id > 0)
    .map((r) => ({
      record: r,
      refs: backReferences(pack, {
        kind: 'structure', id: 'jutsu_record', recordId: r.id,
      }),
    }))
    .sort((a, b) => b.refs.length - a.refs.length);
  const most = allRefs[0];
  check('能反查「谁引用了这条记录」', most && most.refs.length > 0,
    most
      ? `id ${most.record.id}（${idRelationName(pack, jutsu, most.record)}）被 ${most.refs.length} 处引用`
      : '没有引用');

  // 11e. 奖励表的下标归属（不是 3×(关卡−1)）
  const owners = missionIndexOwners(pack);
  const shared = [...owners.entries()].filter(([, list]) => list.length > 1);
  check('奖励表下标能反查到关卡', owners.size > 0,
    `${owners.size} 个下标，${shared.length} 个被多关共用`);
}

console.log('\n12) 表说明可见 / 超长当场拦 / 搜索不被过滤与行数上限挡住');
{
  const { TextTableEditor, StructureEditor, plainText } = await import('../js/editors.js');

  // 12a. 内容包里的表说明以前界面上一个字都看不到
  const names = pack.textTable('character_names');
  const host = new StubNode('div');
  const editor = new TextTableEditor(pack, names, { onChange: ctx.onChange });
  editor.render(host);
  const text = host.textContent || '';
  check('文本表的说明显示在面板上', text.includes('指针表驱动') || text.includes('槽位'),
    (text.match(/这张表.{0,40}/) || [''])[0].replace(/\n/g, ' '));
  check('说明里的 markdown 星号不露出来', !text.includes('**'),
    text.includes('**') ? '还有 ** 没去掉' : '已去掉');

  const structure = pack.structure('battle_actors');
  const host2 = new StubNode('div');
  new StructureEditor(pack, structure, { onChange: ctx.onChange }).render(host2);
  check('结构表的说明显示在面板上',
    (host2.textContent || '').includes('47 关'),
    (host2.textContent || '').includes('47 关') ? '已显示' : '没有');

  // 12b. 等长表超长**当场拦**（以前只在构建时才炸）
  const speakers = pack.textTable('speaker_names');
  const host3 = new StubNode('div');
  const editor3 = new TextTableEditor(pack, speakers, { onChange: ctx.onChange });
  editor3.render(host3);
  const record = speakers.records.find((r) => r.text);
  editor3.openDetail(record);
  const area = editor3.detail.descendants().find((n) => n.tagName === 'TEXTAREA');
  const before = record.text;
  check('找到说话人名的文本框', !!area, area ? '有' : '没有');
  if (area) {
    const counter = editor3.detail.descendants().find((n) => (n.className || '') === 'text-counter');
    const toastTexts = () => globalThis.document.body.descendants()
      .map((n) => n.textContent || '').join('\n');
    const beforeToast = toastTexts();
    area.listeners.change[0]({
      target: { value: '一二三四五六' },   // 6 个字 = 12 字节 > 11 字节可用
    });
    check('等长表超长被当场拒绝（记录没变）',
      record.text === before,
      `原值「${before}」，现在「${record.text}」`);
    check('超长时给出「放不下」的明确提示',
      toastTexts() !== beforeToast && /放不下|定长槽/.test(toastTexts()),
      (toastTexts().match(/[^。]{0,60}放不下[^。]{0,40}/) || ['没有提示'])[0]);
  }

  // 12c. 搜索不被「已归属」过滤与 200 行上限挡住
  const index = pack.textTable('rom_text_index');
  if (!index) {
    check('全 ROM 文本索引可用', false, '未载入');
  } else {
    const host4 = new StubNode('div');
    const editor4 = new TextTableEditor(pack, index, { onChange: ctx.onChange });
    editor4.render(host4);
    editor4.query = '漩涡鸣人';
    const hits = editor4.records.length;
    const owned = index.records.filter((r) => r.owned_by && (r.text || '').includes('漩涡鸣人')).length;
    check('搜索能命中「已被其它表拥有」的条目', owned > 0 ? hits > 0 : true,
      `搜「漩涡鸣人」命中 ${hits} 条（其中 ${owned} 条属其它表）`);
  }
}

console.log('\n13) 对白按组呈现：305 组「一道题 + 三个选项」');
{
  const { TextTableEditor } = await import('../js/editors.js');
  const slots = pack.textTable('dialogue_slots');
  const host = new StubNode('div');
  const editor = new TextTableEditor(pack, slots, { onChange: ctx.onChange });
  editor.render(host);
  check('对白表被切成组', editor.hasGroups,
    `${editor.groups.length} 组（槽 ${slots.count} 条）`);
  const rows = host.descendants().filter((n) => n.tagName === 'TR');
  check('列表按组显示而不是按槽平铺', rows.length <= editor.groups.length + 1,
    `${rows.length} 行（含表头），组数 ${editor.groups.length}`);
  const text = host.textContent || '';
  check('列表里没有「无位置」的空指针槽', !text.includes('⊘ 无位置'),
    text.includes('⊘ 无位置') ? '还有空指针槽' : '空指针分隔槽不出现');
  // 打开一组：题干 + 选项
  editor.openGroup(editor.groups[0], 0);
  const detail = editor.detail.textContent || '';
  check('组详情给出题干与选项', detail.includes('题干') && detail.includes('选项 1'),
    detail.includes('题干') ? '有题干/选项' : '没有');
}

console.log('\n14) 剧情脚本查看器：反汇编 + 可改操作数');
{
  const { renderScriptView } = await import('../js/modules/scriptview.js');
  const { readFileSync } = await import('node:fs');
  const { join } = await import('node:path');
  const { fileURLToPath } = await import('node:url');
  const { dirname } = await import('node:path');
  const here = dirname(fileURLToPath(import.meta.url));
  const rom = new Uint8Array(readFileSync(join(here, '..', '..', 'rom', 'base.gba')));

  const host = new StubNode('div');
  const saved = ctx.rom;
  ctx.rom = rom;
  ctx.state.view = { panel: { kind: 'script', id: 'script', params: { root: 'before', scene: 3 } } };
  let error = null;
  try {
    renderScriptView(host, ctx);
  } catch (err) {
    error = err;
  }
  const text = host.textContent || '';
  check('剧本查看器渲染成功', !error && text.includes('指令表'),
    error ? String(error.message) : `${text.length} 字符`);
  check('剧本查看器列出中文指令名',
    /0x[0-9A-F]{2} \S/.test(text) && (text.includes('下一场景') || text.includes('显示文本') || text.includes('设置头像')),
    (text.match(/0x[0-9A-F]{2} [^ ]+/) || [''])[0]);
  const inputs = host.descendants().filter((n) => n.tagName === 'INPUT');
  check('可改的定宽操作数给成输入框', inputs.length > 0,
    `${inputs.length} 个可改操作数`);
  ctx.rom = saved;
  ctx.state.view = { panel: null };
}

console.log('\n15) 复合键 / 大表行数上限 / 空记录隐藏 / 原生不读字节');
{
  const { StructureEditor } = await import('../js/editors.js');
  const { indexKey, isEmptyRecord } = await import('../js/indexkey.js');

  // 15a. 复合键分解：第 447 条 = 关卡 12 / 变体 1 / 槽 3
  const actors = pack.structure('battle_actors');
  const key = indexKey(actors, actors.records[447]);
  check('复合下标能分解成可读的键',
    !!key && key.text.includes('第 12 关') && key.text.includes('变体 1') && key.text.includes('槽 3'),
    key ? key.text : '没有分解');
  check('复合键的 ROM 地址与内容包一致',
    actors.records[447].rom_offset === 0x5461c4 + 12 * 0x1aac + 1 * 0x8e4 + 4 + 3 * 0xb8,
    `0x${actors.records[447].rom_offset.toString(16).toUpperCase()}`);

  // 15b. 大表：只渲染前 200 行，且空记录被藏起来
  const host = new StubNode('div');
  const editor = new StructureEditor(pack, actors, { onChange: ctx.onChange });
  editor.render(host);
  const rows = host.descendants().filter((n) => n.tagName === 'TR');
  check('大表默认只渲染前 200 行', rows.length <= 201,
    `${rows.length} 行（含表头），共 ${actors.entry_count} 条`);
  const foot = (host.descendants().find((n) => (n.className || '') === 'table-foot') || {}).textContent || '';
  check('页脚写明显示了多少条', /显示 \d+ \/ \d+ 条/.test(foot), foot.slice(0, 60));
  const emptyCount = actors.records.filter((r) => isEmptyRecord(actors, r)).length;
  check('空记录被识别出来', emptyCount > 0,
    `${emptyCount} 条全零记录（默认隐藏）`);

  // 15c. 原生不读的字节降级为只读
  const sideField = actors.fields.find((f) => f.key === 'side');
  check('原生不读的字节被标出来', sideField && sideField.not_read === true,
    sideField ? sideField.label : '没有这个字段');
  const record = actors.records.find((r) => r.rom_offset === 0x5461c4 + 4);
  const { fieldControl } = await import('../js/fields.js');
  const control = fieldControl(ctx, actors, record, sideField);
  check('原生不读的字段给的是只读控件',
    control.node.tagName === 'INPUT' && control.node.attributes.disabled === '',
    control.node.attributes.disabled === '' ? '已禁用' : '可以改（不对）');
  check('提示里说明「原生不读」',
    control.hint.some((h) => h.includes('不读')),
    (control.hint.find((h) => h.includes('不读')) || '没有')['slice'](0, 40));

  // 15d. 战场物件表的基址更正
  const objects = pack.structure('battle_map_objects');
  check('战场物件表的基址指向它的第一条记录',
    objects.rom_offset === objects.records[0].rom_offset,
    `结构基址 0x${objects.rom_offset.toString(16).toUpperCase()}，` +
    `第一条记录 0x${objects.records[0].rom_offset.toString(16).toUpperCase()}`);

  // 16. 指针：十六进制控件 / 载荷判定 / 反查 / 搜索吃十六进制
  const pointerTable = pack.structure('data_pointer_table_a');
  check('素材域的指针表在包里', !!pointerTable, pointerTable ? pointerTable.label : '没有这张表');
  if (pointerTable) {
    const ptrRecord = pointerTable.records[0];
    const ptrField = pointerTable.fields.find((f) => f.key === 'ptr');
    const ptrControl = fieldControl(ctx, pointerTable, ptrRecord, ptrField);
    const shown = ptrControl.node.value || '';
    check('指针字段给的是十六进制输入框',
      ptrControl.node.tagName === 'INPUT' && /^0x[0-9A-F]{8}$/.test(String(shown)),
      String(shown));
    check('指针的十进制原值不再直接暴露给作者',
      String(ptrRecord.values.ptr) !== String(shown),
      `记录里是十进制 ${ptrRecord.values.ptr}，框里是 ${shown}`);

    const target = pack.pointerTarget(ptrRecord.values.ptr);
    check('指针指向什么被判定出来并进了内容包', !!target,
      target ? target.label : '没有判定结果');

    // 反查：这个地址被哪些记录指着
    const { backReferencesByPointer } = await import('../js/xref.js');
    const refs = backReferencesByPointer(pack, ptrRecord.values.ptr);
    check('指针反查能找出指向它的记录', refs.length > 0, `${refs.length} 处`);

    // 搜索吃十六进制写法
    const { StructureEditor, valueMatches } = await import('../js/editors.js');
    const hexText = '0x' + (ptrRecord.values.ptr >>> 0).toString(16).toUpperCase();
    check('搜索同时吃十六进制与十进制',
      valueMatches(ptrRecord.values.ptr, hexText.slice(2).toLowerCase()) &&
      valueMatches(ptrRecord.values.ptr, String(ptrRecord.values.ptr)),
      hexText);
  }

  // 16b. 说明里的 markdown 星号当子节点传时也不露出来
  const proseHost = new StubNode('div');
  const { el } = await import('../js/ui.js');
  proseHost.appendChild(el('p', { class: 'section-note' }, [
    '这句说明里有', el('b', { text: '**加粗**' }), '这种写法。',
  ]));
  check('说明里的 markdown 星号不露出来',
    !(proseHost.textContent || '').includes('**'),
    (proseHost.textContent || '').slice(0, 40));

  // 16c. 路由：整条路线总览与第 0 关
  const routing = await import('../js/routing.js');
  check('第 0 关不会被解析成第 1 关',
    routing.parseHash('#route/stage/0').panel.params.stage === 0,
    String(routing.parseHash('#route/stage/0').panel.params.stage));
  check('整条路线总览有可寻址的 URL',
    routing.hashFor({ module: 'route', panel: { kind: 'graph', id: 'graph', params: {} } }) === '#route/graph',
    routing.hashFor({ module: 'route', panel: { kind: 'graph', id: 'graph', params: {} } }));
  check('原始字节按地址深链可寻址',
    routing.hashFor({ module: 'raw', panel: { kind: 'raw-offset', id: 'raw', params: { offset: 0x5a15c0 } } })
      === '#raw/offset/0x5A15C0',
    routing.hashFor({ module: 'raw', panel: { kind: 'raw-offset', id: 'raw', params: { offset: 0x5a15c0 } } }));

  // 17. id 空间的另一张表也要能跳过去
  //   （用户的原话：「技能表不支持配置么」—— 技能表其实能配，
  //    但从角色的技能槽跳过去只能到技能名表，技能自己的参数那张表没有入口。）
  const template2 = pack.structure('character_template');
  const tmplRecord = template2.records.find((r) => r.id === 5) || template2.records[0];
  const trainId = template2.fields.find((f) => f.key === 'train_0_id');
  const jumps = [];
  const linkCtx = {
    pack,
    onChange() {},
    onJump(target) { jumps.push(target); },
  };
  const { fieldControl: fieldControl2 } = await import('../js/fields.js');
  const trainLinks = fieldControl2(linkCtx, template2, tmplRecord, trainId).links || [];
  check('技能槽给的链接不止技能名表一条', trainLinks.length >= 2,
    `${trainLinks.length} 条：${trainLinks.map((l) => l.textContent).join(' / ')}`);
  check('技能槽能跳到「角色特性表（技能）」—— 技能自己的参数在那儿',
    trainLinks.some((l) => String(l.textContent || '').includes('角色特性表')),
    trainLinks.map((l) => l.textContent).join(' / '));
  const perkLink = trainLinks.find((l) => String(l.textContent || '').includes('角色特性表'));
  if (perkLink) {
    perkLink.listeners.click[0]({ target: perkLink });
    const landed = jumps[jumps.length - 1];
    check('点它就落到角色特性表的那条记录上',
      landed && landed.id === 'character_perks' && landed.kind === 'structure',
      landed ? `${landed.module}/${landed.id} #${landed.recordId}` : '没跳');
  }

  // 忍术槽同理：忍术名表 ↔ 忍术记录表
  const jutsuId = template2.fields.find((f) => f.key === 'jutsu_0_id');
  const jutsuLinks = fieldControl2(linkCtx, template2, tmplRecord, jutsuId).links || [];
  check('忍术槽能跳到「忍术记录表」',
    jutsuLinks.some((l) => String(l.textContent || '').includes('忍术记录表')),
    jutsuLinks.map((l) => l.textContent).join(' / '));
}

console.log('\n17) 剧情路线 · 任务视图：右侧面板分页签');
{
  const { renderMission } = await import('../js/modules/mission.js');
  const host = new StubNode('div');
  let error = null;
  try {
    renderMission(host, ctx, { stage: 40 });
  } catch (err) {
    error = err;
  }
  check('任务视图渲染成功', !error, error ? String(error.message) : '');

  // --- 页签条：五个页签各管一类 -------------------------------------------
  const tabButtons = host.descendants()
    .filter((n) => String(n.className || '').split(/\s+/).includes('tab-btn'));
  check('任务视图右侧面板有页签条', tabButtons.length === 5,
    `${tabButtons.length} 个页签`);
  const tabLabels = tabButtons.map((n) => String(n.textContent || ''));
  for (const needle of ['基址', '标题', '说明', '提示', '奖励']) {
    check(`任务视图的页签里有「${needle}」`,
      tabLabels.some((t) => t.includes(needle)), tabLabels.join(' / '));
  }

  // --- 头部留在页签外面 ---------------------------------------------------
  const head = host.descendants().find((n) => n.className === 'detail-head');
  const sub = host.descendants().find((n) => n.className === 'detail-sub');
  check('头部留在页签外面（第几关）',
    !!head && String(head.textContent || '').includes('第 40 关'),
    head ? String(head.textContent || '') : '没有头部');
  check('头部标出索引表第几条与基址',
    !!sub && String(sub.textContent || '').includes('索引表第 40 条')
      && String(sub.textContent || '').includes('基址 #'),
    sub ? String(sub.textContent || '') : '没有副标题');

  // --- 切页签：这一页在 DOM 里，切走之后不在 ------------------------------
  const tabBodies = () => host.descendants()
    .filter((n) => String(n.className || '').split(/\s+/).includes('tab-body'));
  const bodyInputs = () => tabBodies().flatMap((n) => n.descendants())
    .filter((n) => n.tagName === 'INPUT');

  const index = pack.structure('mission_index');
  const base = index.records[40].values.value;
  const titles = pack.textTable('mission_titles');
  const descs = pack.textTable('mission_descriptions');
  const hints = pack.textTable('mission_hints');
  const titleText = titles.records[base].text;
  const descText = descs.records[base].text;
  const hintText = hints.records[base].text;

  check('默认停在「基址」页：标题页的内容还不在 DOM 里',
    !bodyInputs().some((n) => n.value === titleText),
    `槽 ${base}`);
  switchTab(host, '标题');
  check('切到「标题」后这一页的内容在 DOM 里',
    bodyInputs().some((n) => n.value === titleText),
    `${bodyInputs().length} 个输入框`);
  check('「标题」页里不混着「说明」页的文案',
    !bodyInputs().some((n) => n.value === descText),
    descText === titleText ? '两页文案本来就一样' : '');
  switchTab(host, '说明');
  check('切走之后「标题」页的内容不在 DOM 里',
    !bodyInputs().some((n) => n.value === titleText));
  check('切到「说明」后这一页的内容在 DOM 里',
    bodyInputs().some((n) => n.value === descText));
  check('「说明」页里不混着「提示」页的文案',
    !bodyInputs().some((n) => n.value === hintText));

  // --- 每一页装的是不是它该装的东西 --------------------------------------
  switchTab(host, '基址');
  const baseText = tabBodies().map((n) => String(n.textContent || '')).join('');
  check('「基址」页里是索引表那一格',
    baseText.includes('本关的基址（索引表）'), baseText.slice(0, 40));
  switchTab(host, '奖励');
  const rewardText = tabBodies().map((n) => String(n.textContent || '')).join('');
  check('「奖励」页里是本关的三份奖励',
    rewardText.includes('金币') && rewardText.includes('强化点')
      && rewardText.includes('等级门槛') && rewardText.includes('掉落位'),
    rewardText.slice(0, 40));

  // --- 角标：这一类改了几处 ----------------------------------------------
  switchTab(host, '标题');
  const titleInput = bodyInputs().find((n) => n.value === titleText);
  const changedBefore = pack.changedCount();
  if (!titleInput) {
    check('找到标题输入框', false, '没有');
  } else {
    titleInput.listeners.change[0]({ target: { value: '宝箱得到！' } });
    check('改过的标题写回内容包', titles.records[base].text === '宝箱得到！',
      `「${titles.records[base].text}」`);
    check('改动计数 +1', pack.changedCount() === changedBefore + 1,
      `${changedBefore} → ${pack.changedCount()}`);
    const badges = host.descendants()
      .filter((n) => String(n.className || '').split(/\s+/).includes('tab-badge'))
      .map((n) => String(n.textContent || '').trim());
    check('改过之后「标题」页签上有角标', badges.includes('1'),
      badges.length ? badges.join(' / ') : '没有角标');
    // 复原
    titles.records[base].text = titleText;
    titles.records[base].original_text = titleText;
    delete titles.records[base].text_changed;
    titles.records[base].tokens = null;
  }

  // --- 换关卡：头部跟着换，页签面板不被重建 ------------------------------
  switchTab(host, '提示');
  const rows = host.descendants()
    .filter((n) => n.tagName === 'TR' && n.listeners && n.listeners.click);
  const otherRow = rows.find((n) => !String(n.textContent || '').includes('第 40 关'));
  if (!otherRow) {
    check('左边列表能点别的关卡', false, '没有可点的行');
  } else {
    otherRow.listeners.click[0]();
    const head2 = host.descendants().find((n) => n.className === 'detail-head');
    check('换关卡后头部跟着换',
      !!head2 && !String(head2.textContent || '').includes('第 40 关'),
      head2 ? String(head2.textContent || '') : '没有头部');
    const active = host.descendants()
      .filter((n) => String(n.className || '').split(/\s+/).includes('tab-btn'))
      .filter((n) => String(n.className || '').split(/\s+/).includes('active'));
    check('换关卡后还停在原来那一页（页签面板没被重建）',
      active.length === 1 && String(active[0].textContent || '').includes('提示'),
      active.map((n) => String(n.textContent || '')).join(' / '));
  }
}

console.log('\n18) 素材与资源：接线表与 EWRAM 内存图的右侧面板分页签');
{
  /** 某个宿主里当前页签页签体的文字。 */
  const tabBodyText = (host) => host.descendants()
    .filter((n) => String(n.className || '').split(/\s+/).includes('tab-body'))
    .map((n) => String(n.textContent || '')).join('');
  /** 某个宿主里当前页签页签体里的控件。 */
  const tabBodyControls = (host) => host.descendants()
    .filter((n) => String(n.className || '').split(/\s+/).includes('tab-body'))
    .flatMap((n) => n.descendants())
    .filter((n) => ['INPUT', 'SELECT', 'TEXTAREA'].includes(n.tagName));
  const tabButtons = (host) => host.descendants()
    .filter((n) => String(n.className || '').split(/\s+/).includes('tab-btn'));

  // --- 接线表（#assets/wiring） --------------------------------------------
  // 同一文件里的兄弟视图（#assets/records）本轮没改，但别被改坏。
  const recordsHost = new StubNode('div');
  let recordsError = null;
  try {
    ctx.state.view = { panel: { kind: 'records', id: '资源记录表', params: {} } };
    renderAssets(recordsHost, ctx);
  } catch (err) {
    recordsError = err;
  }
  check('资源记录表视图仍能渲染（同一文件的兄弟视图）', !recordsError,
    recordsError ? String(recordsError.message) : `${recordsHost.textContent.length} 字符`);

  const wiringHost = new StubNode('div');
  let wiringError = null;
  try {
    ctx.state.view = { panel: { kind: 'wiring', id: '接线表', params: {} } };
    renderAssets(wiringHost, ctx);
  } catch (err) {
    wiringError = err;
  }
  check('接线表视图渲染成功', !wiringError,
    wiringError ? String(wiringError.message) : '');

  const wiringBars = wiringHost.descendants()
    .filter((n) => String(n.className || '').split(/\s+/).includes('tab-bar'));
  check('接线表右侧面板有页签条', wiringBars.length === 1, `${wiringBars.length} 条`);

  const wiringLabels = tabButtons(wiringHost).map((n) => String(n.textContent || ''));
  check('接线表有三个页签', wiringLabels.length === 3, wiringLabels.join(' / '));
  for (const needle of ['指向哪', '换成哪一份', '改动后果']) {
    check(`接线表的页签里有「${needle}」`,
      wiringLabels.some((t) => t.includes(needle)), wiringLabels.join(' / '));
  }

  // 头部留在页签外面
  const wiringHead = wiringHost.descendants().find((n) => n.className === 'detail-head');
  const insideBody = wiringHost.descendants()
    .filter((n) => String(n.className || '').split(/\s+/).includes('tab-body'))
    .some((n) => n.descendants().includes(wiringHead));
  check('接线表的头部留在页签外面',
    !!wiringHead && !insideBody,
    wiringHead ? String(wiringHead.textContent || '') : '没有头部');

  // 默认停在「指向哪」：指针框在，别的两页不在
  check('接线表默认停在「指向哪」：指针输入框在 DOM 里',
    tabBodyControls(wiringHost).some((n) => n.tagName === 'INPUT'),
    `${tabBodyControls(wiringHost).length} 个控件`);
  check('接线表默认那一页里没有「从本表其它项复制…」',
    !tabBodyText(wiringHost).includes('从本表其它项复制'));
  switchTab(wiringHost, '换成哪一份');
  check('切到「换成哪一份」后这一页的内容在 DOM 里',
    tabBodyText(wiringHost).includes('从本表其它项复制')
      && tabBodyText(wiringHost).includes('从另一张指针表复制'),
    tabBodyText(wiringHost).slice(0, 40));
  check('「换成哪一份」那一页里没有指针输入框',
    !tabBodyControls(wiringHost).some((n) => n.tagName === 'INPUT'),
    `${tabBodyControls(wiringHost).length} 个控件`);
  switchTab(wiringHost, '改动后果');
  check('切到「改动后果」后这一页的内容在 DOM 里',
    tabBodyText(wiringHost).includes('这一项改动的后果'),
    tabBodyText(wiringHost).slice(0, 40));
  check('切走之后「换成哪一份」的内容不在 DOM 里',
    !tabBodyText(wiringHost).includes('从本表其它项复制'));
  switchTab(wiringHost, '指向哪');
  check('切回「指向哪」后指针输入框又回来了',
    tabBodyControls(wiringHost).some((n) => n.tagName === 'INPUT'));

  // 角标：改了这一格之后页签上有角标（按字节判定，自动跟上）
  const ptrTable = pack.structure('data_pointer_table_a');
  const ptrRecord = ptrTable.records[0];
  const ptrBefore = ptrRecord.values.ptr;
  pack.setValue(ptrTable, ptrRecord, 'ptr', (ptrBefore ^ 0xff) >>> 0);
  const wiringBadges = wiringHost.descendants()
    .filter((n) => String(n.className || '').split(/\s+/).includes('tab-badge'))
    .map((n) => String(n.textContent || '').trim());
  check('改过之后「指向哪」页签上有角标', wiringBadges.includes('1'),
    wiringBadges.length ? wiringBadges.join(' / ') : '没有角标');
  pack.setValue(ptrTable, ptrRecord, 'ptr', ptrBefore);

  // --- EWRAM 内存图（#assets/memory） ---------------------------------------
  const memoryHost = new StubNode('div');
  let memoryError = null;
  try {
    ctx.state.view = { panel: { kind: 'memory', id: 'EWRAM 内存图', params: {} } };
    renderAssets(memoryHost, ctx);
  } catch (err) {
    memoryError = err;
  }
  check('EWRAM 内存图视图渲染成功', !memoryError,
    memoryError ? String(memoryError.message) : '');

  const memoryBars = memoryHost.descendants()
    .filter((n) => String(n.className || '').split(/\s+/).includes('tab-bar'));
  check('EWRAM 内存图右侧面板有页签条', memoryBars.length === 1, `${memoryBars.length} 条`);

  const memoryLabels = tabButtons(memoryHost).map((n) => String(n.textContent || ''));
  check('EWRAM 内存图有两个页签', memoryLabels.length === 2, memoryLabels.join(' / '));
  for (const needle of ['内存分配', '邻接关系']) {
    check(`EWRAM 内存图的页签里有「${needle}」`,
      memoryLabels.some((t) => t.includes(needle)), memoryLabels.join(' / '));
  }

  const memoryHead = memoryHost.descendants().find((n) => n.className === 'detail-head');
  const memoryHeadInside = memoryHost.descendants()
    .filter((n) => String(n.className || '').split(/\s+/).includes('tab-body'))
    .some((n) => n.descendants().includes(memoryHead));
  check('EWRAM 内存图的头部留在页签外面',
    !!memoryHead && !memoryHeadInside,
    memoryHead ? String(memoryHead.textContent || '') : '没有头部');

  // 默认停在「内存分配」：地址与大小两个输入框在
  check('EWRAM 内存图默认停在「内存分配」：地址与大小输入框在 DOM 里',
    tabBodyControls(memoryHost).filter((n) => n.tagName === 'INPUT').length === 2,
    `${tabBodyControls(memoryHost).length} 个控件`);
  check('EWRAM 内存图默认那一页里没有邻接告警',
    !tabBodyText(memoryHost).includes('下一段：'));
  switchTab(memoryHost, '邻接关系');
  check('切到「邻接关系」后这一页的内容在 DOM 里',
    tabBodyText(memoryHost).includes('下一段：')
      || tabBodyText(memoryHost).includes('这是最后一段：'),
    tabBodyText(memoryHost).slice(0, 40));
  check('切走之后「内存分配」那一页的输入框不在 DOM 里',
    !tabBodyControls(memoryHost).some((n) => n.tagName === 'INPUT'));
  switchTab(memoryHost, '内存分配');
  check('切回「内存分配」后地址与大小输入框又回来了',
    tabBodyControls(memoryHost).filter((n) => n.tagName === 'INPUT').length === 2);

  // 角标：改了这一行之后页签上有角标
  const wram = pack.structure('wram_allocation');
  const wramRecord = wram.records[0];
  const sizeBefore = wramRecord.values.alloc_size;
  const sizeInput = tabBodyControls(memoryHost)
    .find((n) => n.tagName === 'INPUT' && n.className === 'num-input wram-size');
  if (!sizeInput) {
    check('找到大小输入框', false, '没有');
  } else {
    sizeInput.listeners.change[0]({ target: { value: String(sizeBefore - 16) } });
    const memoryBadges = memoryHost.descendants()
      .filter((n) => String(n.className || '').split(/\s+/).includes('tab-badge'))
      .map((n) => String(n.textContent || '').trim());
    check('改过之后「内存分配」页签上有角标', memoryBadges.includes('1'),
      memoryBadges.length ? memoryBadges.join(' / ') : '没有角标');
    check('改过之后大小写回了内容包',
      wramRecord.values.alloc_size === sizeBefore - 16,
      `${sizeBefore} → ${wramRecord.values.alloc_size}`);
    pack.setValue(wram, wramRecord, 'alloc_size', sizeBefore);
  }
}

console.log(`\n${failures === 0 ? '全部通过' : failures + ' 项失败'}`);
process.exit(failures === 0 ? 0 : 1);
