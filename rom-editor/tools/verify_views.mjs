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
const { renderBattle, renderStage } = await import('../js/modules/battle.js');
const { renderRoute } = await import('../js/modules/route.js');
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

console.log('\n2) 战斗：第 40 关的视图');
{
  const host = new StubNode('div');
  let error = null;
  let text = '';
  try {
    renderStage(host, ctx, 40, 0);
    text = host.textContent;
  } catch (err) {
    error = err;
  }
  check('战斗视图渲染成功', !error && text.length > 200,
    error ? String(error.message) : `${text.length} 字符`);
  for (const needle of ['战场布置', '角色出生点', '战斗目标', '战场物件', '战场事件']) {
    check(`战斗视图含「${needle}」`, text.includes(needle));
  }

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
  check('说明文字标出字节用量与地址', /\d+ \/ \d+ 字节 · 0x[0-9A-F]+/.test(text),
    (text.match(/\d+ \/ \d+ 字节 · 0x[0-9A-F]+/) || ['没有'])[0]);

  // 类型 2 的语义必须与原生行为一致
  check('类型 2 标注为「回合用尽」', text.includes('回合用尽'),
    text.includes('回合用尽') ? '已标注' : '没有标注');
  check('不再声称类型 2 是「指定角色仍在场」', !text.includes('指定角色仍在场上'));

  // 参数含义要写出来
  check('参数含义被标注', text.includes('角色 id') || text.includes('道具序号'));
}

console.log(`\n${failures === 0 ? '全部通过' : failures + ' 项失败'}`);
process.exit(failures === 0 ? 0 : 1);
