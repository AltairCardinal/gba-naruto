// 角色域「统一角色视图」的无头验收脚本。
//
// 对应用户反馈：「光一个任务表就分了索引、标题、说明、提示表来呈现，过于细碎繁琐，
// 应当按统一的任务编辑来呈现，然后按索引表列出，将其他表的内容都作为字段呈现。」
// 角色域照同样的思路做：左边按角色列出，右边是这个角色的各个侧面。
//
// 右边是**卡片**（见 notes/specs/human-readable-cards-20261022.md）：头部留在卡片外面，
// 内容按类分成卡片竖着排 —— 属性 / 成长 / 特性 / 忍术槽 / 技能槽 / 道具槽 / 头像。
// 卡片**不互斥**：所有卡片的内容同时在 DOM 里（这是与页签最大的不同）。
//
// 六条断言：
//   1. 角色视图能渲染，左边列表的行数 = 角色定义表的条数；
//   2. 详情里能看到属性 / 成长 / 特性 / 忍术槽 / 技能槽 / 道具槽 / 头像这几张卡片
//      （卡片不懒渲染：每一张的内容都在 DOM 里）；
//   3. 改一个字段后 pack.changedCount() +1，改回原值后回落；
//   4. 域首页的「本域可编辑内容」里，角色那几张表合成了一行；
//   5. 路由：#characters/character 能寻址；
//   6. 右侧面板确实是卡片：卡片堆、卡片头标题（七张，依次是预期的那几个）、
//      所有卡片的内容同时在 DOM 里；角标只在真正改了的那一张上亮。
//
// 用法：node rom-editor/tools/verify_character_view.mjs
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
      setProperty: (name, value) => { this.style[name] = value; },
      getPropertyValue: (name) => this.style[name] || '',
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
// 页签要记住上次停在哪一页 —— 给它一个 localStorage 桩。
const storage = new Map();
const localStorageStub = {
  getItem: (key) => (storage.has(key) ? storage.get(key) : null),
  setItem: (key, value) => { storage.set(key, String(value)); },
  removeItem: (key) => { storage.delete(key); },
  clear: () => storage.clear(),
};
globalThis.localStorage = localStorageStub;
globalThis.window = {
  location: { hash: '' },
  addEventListener() {},
  removeEventListener() {},
  localStorage: localStorageStub,
};

const here = dirname(fileURLToPath(import.meta.url));
const repoRoot = join(here, '..', '..');
const packPath = join(repoRoot, 'rom-editor', 'content', 'pack.json');

const { ContentPack } = await import('../js/pack.js');
const { renderCharacters } = await import('../js/modules/characters.js');
const { parseHash, hashFor } = await import('../js/routing.js');

let failures = 0;
function check(name, ok, detail = '') {
  if (!ok) failures += 1;
  console.log(`  [${ok ? 'PASS' : 'FAIL'}] ${name}${detail ? ' — ' + detail : ''}`);
}

const packData = JSON.parse(readFileSync(packPath, 'utf8'));
const pack = ContentPack.fromJSON(packData);
const jumps = [];
const ctx = {
  pack,
  rom: new Uint8Array(0),
  baseRom: new Uint8Array(0),
  state: { view: { panel: null } },
  onChange() {},
  openPanel(kind, id, params) { ctx.state.view = { panel: { kind, id, params: params || {} } }; },
  goModule() {},
  render() {},
  setStatus() {},
  onJump(target) { jumps.push(target); },
};

/** 渲染角色域的某个面板。 */
function renderPanel(panel) {
  // 卡片没有「当前页」，也就没什么要清的残留状态。
  const host = new StubNode('div');
  ctx.state.view = { panel };
  renderCharacters(host, ctx);
  return host;
}

/** 带 class 的节点。 */
function byClass(host, name) {
  return host.descendants().filter((n) => String(n.className || '').split(/\s+/).includes(name));
}

/** 卡片堆（.card-stack）—— 右侧面板装卡片的那一摞。 */
function cardStacks(host) {
  return byClass(host, 'card-stack');
}

/** 卡片（.editor-card）—— 每一类配置一张。 */
function cardsOf(host) {
  return byClass(host, 'editor-card');
}

/** 卡片头的标题。 */
function cardTitle(card) {
  const node = byClass(card, 'editor-card-title')[0];
  return node ? String(node.textContent || '').trim() : '';
}

/** 卡片体（装内容的那一格）。 */
function cardBody(card) {
  return byClass(card, 'editor-card-body')[0] || null;
}

/** 按标题找一张卡片。 */
function cardByTitle(host, title) {
  return cardsOf(host).find((c) => cardTitle(c) === title) || null;
}

/** 某张卡片上的角标文字（没有角标就是空串）。 */
function cardBadge(host, title) {
  const card = cardByTitle(host, title);
  if (!card) return '';
  const badge = byClass(card, 'card-badge')[0];
  return badge ? String(badge.textContent || '') : '';
}

/** 某张卡片里的文字。 */
function cardText(host, title) {
  const card = cardByTitle(host, title);
  return card ? String(card.textContent || '') : '';
}

/** 表格里的正文行（跳过表头行）。 */
function bodyRows(table) {
  const tbodies = (table.children || []).filter((n) => n.tagName === 'TBODY');
  return tbodies.length ? tbodies[0].children.filter((n) => n.tagName === 'TR') : [];
}

const template = pack.structure('character_template');
const characterCount = (template.records || []).length;

console.log('1) 角色视图能渲染，左边列表的行数 = 角色定义表的条数');
{
  const host = renderPanel({ kind: 'character', id: '角色', params: {} });
  const text = host.textContent;
  check('渲染没有报错且有内容', text.length > 200, `${text.length} 字符`);
  const lists = byClass(host, 'char-list');
  check('左边有一张角色一览表', lists.length === 1, `${lists.length} 张`);
  const rows = lists.length ? bodyRows(lists[0]) : [];
  check(`左边列表 ${characterCount} 行`, rows.length === characterCount,
    `${rows.length} 行（角色定义表 ${characterCount} 条）`);
  check('列表里能看到角色名', text.includes('漩涡鸣人'),
    (text.match(/漩涡[^·]{0,4}/) || ['没有'])[0]);
}

console.log('2) 详情里能看到角色的各个侧面（右侧是卡片，每一张都在 DOM 里）');
{
  const host = renderPanel({ kind: 'character', id: '角色', params: {} });
  const detail = byClass(host, 'detail-panel')[0];
  check('有详情面板', !!detail, detail ? '' : '没有');
  // 卡片不互斥：每一类都在自己那张卡片里，不用切。
  const pages = [
    { label: '属性', needles: ['属性', '攻击力', '防御力', '敏捷度', '移动力', '忍具数', '查克拉', '副属性', '体力'] },
    { label: '成长', needles: ['成长', '每级成长'] },
    { label: '特性', needles: ['特性（技能）', '效果类型', '基础值', '次要值', '附加属性'] },
    { label: '忍术槽', needles: ['忍术列表', '忍术'] },
    { label: '技能槽', needles: ['技能列表', '技能'] },
    { label: '道具槽', needles: ['道具槽', '忍具槽'] },
    { label: '头像', needles: ['头像', '表情'] },
  ];
  let allText = '';
  for (const page of pages) {
    const card = cardByTitle(host, page.label);
    check(`有「${page.label}」这张卡片`, !!card);
    const body = card ? cardBody(card) : null;
    const text = body ? body.textContent : '';
    if (process.env.CHAR_DEBUG) console.log(`--- ${page.label} ---\n${text.slice(0, 400)}`);
    allText += text;
    for (const needle of page.needles) {
      check(`「${page.label}」那张卡片含「${needle}」`, text.includes(needle));
    }
  }
  // 全部卡片的控件与表一次数（卡片都在 DOM 里，不用一页一页数）
  const slotTables = byClass(detail, 'grid-slots').length;
  const controls = detail.descendants().filter(
    (n) => ['INPUT', 'SELECT', 'TEXTAREA'].includes(n.tagName)).length;
  const jumpTexts = byClass(detail, 'xref-link').map((n) => n.textContent);
  check('重复槽位渲染成表（忍术 / 技能 / 道具 / 表情 / 特性）', slotTables >= 5,
    `${slotTables} 张`);
  check('每一项都能直接改（控件数 > 50）', controls > 50, `${controls} 个控件`);
  check('详情里没有 undefined / NaN', !/undefined|NaN/.test(allText),
    (allText.match(/.{0,20}(undefined|NaN).{0,20}/) || [''])[0]);
  check('技能槽能跳到角色特性表（技能）—— 同一个 id 的另一张表',
    jumpTexts.some((t) => t.includes('跳到角色特性表（技能）')),
    jumpTexts.find((t) => t.includes('跳到角色特性表')) || '没有这条链接');
}

console.log('\n3) 改一个字段后已改计数 +1，改回原值后回落');
{
  const host = renderPanel({ kind: 'character', id: '角色', params: {} });
  const detail = byClass(host, 'detail-panel')[0];
  const attack = byClass(detail, 'field').find((f) => f.textContent.includes('攻击力'));
  const input = attack ? attack.descendants().find((n) => n.tagName === 'INPUT') : null;
  check('属性段里「攻击力」有一个输入框', !!input,
    input ? `当前值 ${input.value}` : '没有输入框');
  if (input) {
    const original = Number(input.value);
    const before = pack.changedCount();
    input.listeners.change[0]({ target: { value: String(original + 1) } });
    const after = pack.changedCount();
    check('改一个字段后已改计数 +1', after === before + 1, `${before} → ${after}`);
    input.listeners.change[0]({ target: { value: String(original) } });
    const back = pack.changedCount();
    check('改回原值后已改计数回落', back === before, `${after} → ${back}`);
  }
}

console.log('\n4) 域首页：角色那几张表合成了一行');
{
  const host = renderPanel(null);
  const table = byClass(host, 'domain-tables')[0];
  const rows = table ? bodyRows(table) : [];
  check('「本域可编辑内容」是一张表', !!table, `${rows.length} 行`);
  const group = rows.filter((r) => r.textContent.includes('角色（定义表'));
  check('角色合成了一行', group.length === 1, `${group.length} 行`);
  if (group.length === 1) {
    const text = group[0].textContent;
    for (const needle of ['角色定义表', '逐角色成长表', '角色特性表', '头像指针表', '头像拼块表']) {
      check(`这一行里包含「${needle}」`, text.includes(needle));
    }
    check('这一行写明了改法', text.includes('按角色改'), text.includes('按角色改') ? '' : '没有');
  }
  check('角色定义表没有单独占一行',
    rows.filter((r) => r.textContent.includes('角色定义表')).length === 1);
  check('逐角色成长表没有单独占一行',
    rows.filter((r) => r.textContent.includes('逐角色成长表')).length === 1);
  check('头像拼块表没有单独占一行',
    rows.filter((r) => r.textContent.includes('头像拼块表')).length === 1);
  check('人物名表仍然是独立的一行',
    rows.filter((r) => r.textContent.includes('人物名表')).length === 1);
  check('技能名表仍然是独立的一行',
    rows.filter((r) => r.textContent.includes('技能名表')).length === 1);
  check('首页没有字面星号', !host.textContent.includes('**'));
}

console.log('\n5) 路由：角色视图可以被地址寻址');
{
  const parsed = parseHash('#characters/character');
  check('parseHash 认得 #characters/character',
    parsed.module === 'characters' && parsed.panel && parsed.panel.kind === 'character',
    JSON.stringify(parsed.panel));
  check('hashFor 能写回去',
    hashFor({ module: 'characters', panel: { kind: 'character', id: '角色' } }) ===
    '#characters/character',
    hashFor({ module: 'characters', panel: { kind: 'character', id: '角色' } }));
}

console.log('\n6) 右侧面板是卡片：卡片堆、卡片头、内容同时在 DOM 里、角标');
{
  const host = renderPanel({ kind: 'character', id: '角色', params: {} });
  const detail = byClass(host, 'detail-panel')[0];

  // 6a. 卡片堆在，里头是预期的那七张卡片
  check('详情面板里有卡片堆', cardStacks(host).length === 1,
    `${cardStacks(host).length} 个`);
  const expected = ['属性', '成长', '特性', '忍术槽', '技能槽', '道具槽', '头像'];
  const cards = cardsOf(host);
  check('卡片头标题就是预期的那七个（依次）',
    JSON.stringify(cards.map(cardTitle)) === JSON.stringify(expected),
    cards.map(cardTitle).join(' / '));

  // 6b. 头部留在卡片外面
  const allCardText = cards.map((c) => String(c.textContent || '')).join('');
  check('头部留在卡片外面',
    detail.textContent.includes('角色定义表 #1') && !allCardText.includes('角色定义表 #1'));
  check('跳转条留在卡片外面',
    detail.textContent.includes('人物名表（改名字）') &&
    !allCardText.includes('人物名表（改名字）'));

  // 6c. 所有卡片的内容**同时**在 DOM 里（卡片不互斥 —— 与页签最大的不同）
  check('「属性」那张卡片的内容在 DOM 里', cardText(host, '属性').includes('副属性'));
  check('「成长」那张卡片的内容同时在 DOM 里', cardText(host, '成长').includes('体力每级成长'));
  check('「特性」那张卡片的内容同时在 DOM 里', cardText(host, '特性').includes('特性（技能）'));
  check('「忍术槽」那张卡片的内容同时在 DOM 里', cardText(host, '忍术槽').includes('忍术列表'));
  check('「技能槽」那张卡片的内容同时在 DOM 里', cardText(host, '技能槽').includes('技能列表'));
  check('「道具槽」那张卡片的内容同时在 DOM 里', cardText(host, '道具槽').includes('道具槽'));
  check('「头像」那张卡片的内容同时在 DOM 里', cardText(host, '头像').includes('表情'));
  check('属性与成长两张卡片的内容**都在**（不再互斥）',
    cardText(host, '属性').includes('副属性') && cardText(host, '成长').includes('体力每级成长'));

  // 6d. 角标：改了哪一类，哪张卡片才亮
  const attack = byClass(detail, 'field').find((f) => f.textContent.includes('攻击力'));
  const input = attack ? attack.descendants().find((n) => n.tagName === 'INPUT') : null;
  check('「属性」那张卡片里「攻击力」有输入框', !!input,
    input ? `当前值 ${input.value}` : '没有输入框');
  if (input) {
    const original = Number(input.value);
    input.listeners.change[0]({ target: { value: String(original + 1) } });
    check('改了属性，「属性」那张卡片亮角标', cardBadge(host, '属性') === '1',
      `角标「${cardBadge(host, '属性')}」`);
    for (const other of ['成长', '特性', '忍术槽', '技能槽', '道具槽', '头像']) {
      check(`改属性不会让「${other}」那张卡片亮角标`, cardBadge(host, other) === '',
        `角标「${cardBadge(host, other)}」`);
    }
    // 头部（「已改 N 处」）也要跟上
    check('头部的「已改 N 处」跟上了', detail.textContent.includes('已改 1 处'),
      (detail.textContent.match(/已改\s*\d+\s*处/) || ['没有'])[0]);
    // 改完一格：这一格的新值还在，别的卡片的内容也不能丢
    const after = byClass(detail, 'field')
      .find((f) => f.textContent.includes('攻击力'))
      .descendants().find((n) => n.tagName === 'INPUT');
    check('改完一格，「攻击力」的新值还在卡片里',
      !!after && Number(after.value) === original + 1,
      after ? `当前值 ${after.value}` : '输入框没了');
    check('改完一格，别的卡片内容没丢', cardText(host, '成长').includes('体力每级成长'));
    // 改回去：角标也要跟着灭（按字节判定 —— 改了又改回去不算改）
    input.listeners.change[0]({ target: { value: String(original) } });
    check('改回原值后角标灭掉', cardBadge(host, '属性') === '',
      `角标「${cardBadge(host, '属性')}」`);
    check('改回原值后头部也回到「已改 0 处」', detail.textContent.includes('已改 0 处'),
      (detail.textContent.match(/已改\s*\d+\s*处/) || ['没有'])[0]);
  }
}

console.log(failures ? `\n${failures} 项未通过` : '\n全部通过');
process.exit(failures ? 1 : 0);
