// 角色域「统一角色视图」的无头验收脚本。
//
// 对应用户反馈：「光一个任务表就分了索引、标题、说明、提示表来呈现，过于细碎繁琐，
// 应当按统一的任务编辑来呈现，然后按索引表列出，将其他表的内容都作为字段呈现。」
// 角色域照同样的思路做：左边按角色列出，右边是这个角色的各个侧面。
//
// 四条断言：
//   1. 角色视图能渲染，左边列表的行数 = 角色定义表的条数；
//   2. 详情里能看到属性 / 成长 / 特性 / 忍术槽 / 技能槽 / 道具槽 / 头像这几段；
//   3. 改一个字段后 pack.changedCount() +1，改回原值后回落；
//   4. 域首页的「本域可编辑内容」里，角色那几张表合成了一行。
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
globalThis.window = {
  location: { hash: '' },
  addEventListener() {},
  removeEventListener() {},
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
  const host = new StubNode('div');
  ctx.state.view = { panel };
  renderCharacters(host, ctx);
  return host;
}

/** 带 class 的节点。 */
function byClass(host, name) {
  return host.descendants().filter((n) => String(n.className || '').split(/\s+/).includes(name));
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

console.log('2) 详情里能看到角色的各个侧面');
{
  const host = renderPanel({ kind: 'character', id: '角色', params: {} });
  const detail = byClass(host, 'detail-panel')[0];
  const text = detail ? detail.textContent : '';
  if (process.env.CHAR_DEBUG) console.log(text.slice(0, 1200));
  check('有详情面板', !!detail, detail ? '' : '没有');
  for (const needle of ['属性', '成长', '特性（技能）', '忍术列表', '技能列表', '道具槽', '头像']) {
    check(`详情含「${needle}」`, text.includes(needle));
  }
  for (const needle of ['攻击力', '防御力', '敏捷度', '移动力', '忍具数', '查克拉', '副属性', '体力']) {
    check(`属性段含「${needle}」`, text.includes(needle));
  }
  check('成长段写的是每级成长', text.includes('每级成长'),
    (text.match(/每级成长/) || ['没有'])[0]);
  check('特性段写的是效果类型 / 基础值 / 次要值 / 附加属性',
    text.includes('效果类型') && text.includes('基础值') &&
    text.includes('次要值') && text.includes('附加属性'));
  const slotTables = byClass(detail, 'grid-slots');
  check('重复槽位渲染成表（忍术 / 技能 / 道具 / 表情 / 特性）', slotTables.length >= 5,
    `${slotTables.length} 张`);
  const controls = detail.descendants().filter(
    (n) => ['INPUT', 'SELECT', 'TEXTAREA'].includes(n.tagName));
  check('每一项都能直接改（控件数 > 50）', controls.length > 50, `${controls.length} 个控件`);
  check('详情里没有 undefined / NaN', !/undefined|NaN/.test(text),
    (text.match(/.{0,20}(undefined|NaN).{0,20}/) || [''])[0]);
  const jumpTexts = byClass(detail, 'xref-link').map((n) => n.textContent);
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

console.log(failures ? `\n${failures} 项未通过` : '\n全部通过');
process.exit(failures ? 1 : 0);
