// 载入 ROM 门禁的契约自检（无头，不需要浏览器）。
//
// 门禁的判据写在 notes/specs/rom-gate-20261023.md §4：
//
//   G1  窗口里只有两个选择：载入内置 ROM / 上传本地 ROM
//   G2  没有关闭按钮（× / 取消 / 关闭）
//   G3  Esc 不关窗（必需模式）
//   G4  点遮罩不关窗（必需模式）
//   G5  下方应用外壳被置 inert
//   G6  焦点锁在窗口里（focusin 到窗外会被拉回）
//   G7  载入成功 ⇒ 关窗 + 把 ROM 交回调用方
//   G8  载入失败 ⇒ 不关窗 + 窗口内报错 + 按钮恢复可用
//   G9  ROM 已经载入了 ⇒ 这一次可以关（Esc）
//   G10 下面的内容收不到点击（点不到窗口后面的东西）
//   G11 文件输入框不在 inert 的外壳里（否则文件选择框点不开）
//   G12 「上传本地 ROM」这条路真的能走通
//
// Run:  node tools/verify_rom_gate.mjs
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));

// --- 一个够用的 DOM 桩（要有真的事件传播，门禁的拦截才测得到） ------------
class StubEvent {
  constructor(type, init = {}) {
    this.type = type;
    this.key = init.key || '';
    this.shiftKey = !!init.shiftKey;
    this.defaultPrevented = false;
    this.propagationStopped = false;
    this.target = null;
  }
  preventDefault() { this.defaultPrevented = true; }
  stopPropagation() { this.propagationStopped = true; }
}

class StubNode {
  constructor(tag) {
    this.tagName = String(tag || '').toUpperCase();
    this.nodeType = 1;
    this.children = [];
    this.parentNode = null;
    this.attributes = {};
    this.dataset = {};
    this.style = { setProperty() {}, getPropertyValue() { return ''; } };
    this.listeners = {};
    this._text = '';
    this._className = '';
    this.disabled = false;
    this.files = null;
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
    if (node) node.parentNode = null;
    return node;
  }
  remove() { if (this.parentNode) this.parentNode.removeChild(this); }
  addEventListener(name, fn, capture) {
    (this.listeners[name] ||= []).push({ fn, capture: !!capture });
  }
  removeEventListener(name, fn, capture) {
    const list = this.listeners[name] || [];
    const at = list.findIndex((l) => l.fn === fn && l.capture === !!capture);
    if (at >= 0) list.splice(at, 1);
  }
  setAttribute(name, value) { this.attributes[name] = String(value); }
  getAttribute(name) { return this.attributes[name] ?? null; }
  removeAttribute(name) { delete this.attributes[name]; }
  hasAttribute(name) { return name in this.attributes; }
  querySelector() { return null; }
  querySelectorAll() { return []; }
  focus() { documentStub.activeElement = this; }
  blur() { if (documentStub.activeElement === this) documentStub.activeElement = null; }
  click() { dispatchTo(this, new StubEvent('click')); }
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

/** 事件传播：捕获（window → 目标）→ 目标 → 冒泡（目标 → window）。 */
function fire(node, event, capturePhase) {
  const list = (node.listeners && node.listeners[event.type]) || [];
  for (const listener of [...list]) {
    if (capturePhase !== listener.capture) continue;
    listener.fn.call(node, event);
    if (event.propagationStopped) return;
  }
}

function dispatchTo(target, event) {
  event.target = target;
  const path = [];
  let node = target;
  while (node) { path.push(node); node = node.parentNode; }
  // 捕获阶段：window → body → … → 目标的父
  for (const n of [windowStub, ...path.slice().reverse()]) {
    if (n === target) break;
    fire(n, event, true);
    if (event.propagationStopped) return;
  }
  // 目标阶段
  for (const l of [...(target.listeners[event.type] || [])]) {
    l.fn.call(target, event);
    if (event.propagationStopped) return;
  }
  // 冒泡阶段
  for (const n of path.slice(1)) {
    fire(n, event, false);
    if (event.propagationStopped) return;
  }
  fire(windowStub, event, false);
}

const windowStub = {
  location: { hash: '' },
  listeners: {},
  addEventListener(name, fn, capture) {
    (this.listeners[name] ||= []).push({ fn, capture: !!capture });
  },
  removeEventListener(name, fn, capture) {
    const list = this.listeners[name] || [];
    const at = list.findIndex((l) => l.fn === fn && l.capture === !!capture);
    if (at >= 0) list.splice(at, 1);
  },
};

const body = new StubNode('body');
const shell = new StubNode('div');
shell.setAttribute('id', 'app-shell');
body.appendChild(shell);

const documentStub = {
  activeElement: null,
  body,
  listeners: {},
  createElement: (tag) => new StubNode(tag),
  createTextNode: (text) => ({ __text: String(text), textContent: String(text), nodeType: 3 }),
  getElementById: (id) => (id === 'app-shell' ? shell : null),
  querySelector: () => null,
  addEventListener(name, fn, capture) {
    (this.listeners[name] ||= []).push({ fn, capture: !!capture });
  },
  removeEventListener(name, fn, capture) {
    const list = this.listeners[name] || [];
    const at = list.findIndex((l) => l.fn === fn && l.capture === !!capture);
    if (at >= 0) list.splice(at, 1);
  },
};

globalThis.document = documentStub;
globalThis.window = windowStub;

const { openRomGate, isGateOpen } = await import('../js/romgate.js');

let failures = 0;
function check(name, ok, detail = '') {
  if (!ok) failures += 1;
  console.log(`  [${ok ? 'PASS' : 'FAIL'}] ${name}${detail ? ' — ' + detail : ''}`);
}

/** 门禁窗口（body 的最后一个子节点）。 */
function overlay() {
  return body.children[body.children.length - 1];
}
function buttons(root) {
  return root.descendants().filter((n) => n.tagName === 'BUTTON');
}
function byText(root, text) {
  return buttons(root).find((b) => String(b.textContent).trim() === text);
}
const tick = () => new Promise((resolve) => setTimeout(resolve, 5));

// ---------------------------------------------------------------------------
console.log('1) 必需模式：窗口里只有两个选择，且关不掉');
// ---------------------------------------------------------------------------
const romBytes = new Uint8Array([0x24, 0xff, 0xae, 0x51]);
let gatePromise = openRomGate({
  reason: '测试用理由',
  closable: false,
  loadBundled: () => Promise.resolve(romBytes),
  loadFile: () => Promise.resolve(romBytes),
});

check('门禁开着', isGateOpen());
const gate = overlay();
const gateButtons = buttons(gate);
check('窗口里正好两个按钮',
  gateButtons.length === 2, `实际 ${gateButtons.length} 个：${gateButtons.map((b) => b.textContent).join(' / ')}`);
check('有「载入内置 ROM」', !!byText(gate, '载入内置 ROM'));
check('有「上传本地 ROM」', !!byText(gate, '上传本地 ROM'));
check('没有关闭按钮',
  !gateButtons.some((b) => /关闭|取消|×|✕/.test(String(b.textContent))),
  gateButtons.map((b) => b.textContent).join(' / '));

// G3：Esc
const esc = new StubEvent('keydown', { key: 'Escape' });
dispatchTo(gate, esc);
check('Esc 不关窗', isGateOpen() && body.children.includes(gate));
check('Esc 被 preventDefault 吃掉', esc.defaultPrevented);
check('Esc 被 stopPropagation 吃掉（页面里别的 Esc 处理器不会跟着触发）', esc.propagationStopped);

// G4：点遮罩
dispatchTo(gate, new StubEvent('mousedown'));
check('点遮罩不关窗', isGateOpen() && body.children.includes(gate));

// G5：外壳 inert
check('应用外壳被置 inert', shell.hasAttribute('inert'));
check('应用外壳被 aria-hidden', shell.getAttribute('aria-hidden') === 'true');

// G6：焦点锁
const shellButton = new StubNode('button');
shell.appendChild(shellButton);
dispatchTo(shellButton, new StubEvent('focusin'));
const trapped = documentStub.activeElement;
check('焦点被拉回窗口里',
  !!trapped && buttons(gate).includes(trapped),
  trapped ? String(trapped.textContent) : '没有焦点');

// G10：下面的内容收不到点击
let shellClicked = 0;
shellButton.addEventListener('click', () => { shellClicked += 1; });
dispatchTo(gate, new StubEvent('click'));
check('点窗口不会把点击透给下面的内容', shellClicked === 0, `下面的内容收到 ${shellClicked} 次点击`);

// G11：文件输入框不在 inert 的外壳里
const fileInput = gate.descendants().find((n) => n.tagName === 'INPUT');
check('窗口里有一个文件输入框', !!fileInput);
check('文件输入框不在 inert 的外壳里',
  !!fileInput && !shell.descendants().includes(fileInput));

// G7：载入成功 ⇒ 关窗 + 交回 ROM
byText(gate, '载入内置 ROM').click();
const loaded = await gatePromise;
check('载入成功后拿到 ROM', loaded && loaded.length === romBytes.length);
check('载入成功后窗口关掉', !isGateOpen() && !body.children.includes(gate));
check('载入成功后外壳不再 inert', !shell.hasAttribute('inert'));

// ---------------------------------------------------------------------------
console.log('\n2) 载入失败：不关窗，窗口内报错，按钮恢复');
// ---------------------------------------------------------------------------
let gatePromise2 = openRomGate({
  reason: '测试用理由',
  closable: false,
  loadBundled: () => Promise.reject(new Error('内置 ROM 取不到')),
  loadFile: () => Promise.resolve(romBytes),
});
const gate2 = overlay();
byText(gate2, '载入内置 ROM').click();
await tick();
check('失败时窗口还开着', isGateOpen() && body.children.includes(gate2));
const errorBox = gate2.descendants().find((n) => n.className.includes('rom-gate-error'));
check('错误显示在窗口里', !!errorBox && !errorBox.classList.contains('hidden')
  && errorBox.textContent.includes('内置 ROM 取不到'),
  errorBox ? errorBox.textContent : '没有错误框');
check('按钮恢复可用',
  buttons(gate2).every((b) => !b.disabled));

// ---------------------------------------------------------------------------
console.log('\n3) 「上传本地 ROM」这条路');
// ---------------------------------------------------------------------------
const input2 = gate2.descendants().find((n) => n.tagName === 'INPUT');
input2.files = [{ name: 'base.gba' }];
dispatchTo(input2, new StubEvent('change'));
const loaded2 = await gatePromise2;
check('上传本地文件也能拿到 ROM', loaded2 && loaded2.length === romBytes.length);
check('上传成功后窗口关掉', !isGateOpen() && !body.children.includes(gate2));

// ---------------------------------------------------------------------------
console.log('\n4) ROM 已经载入了：这一次可以关');
// ---------------------------------------------------------------------------
const gate3Promise = openRomGate({
  reason: '换一份 ROM',
  closable: true,
  loadBundled: () => Promise.resolve(romBytes),
  loadFile: () => Promise.resolve(romBytes),
});
const gate3 = overlay();
check('可选模式有「取消」按钮', !!byText(gate3, '取消'));
dispatchTo(gate3, new StubEvent('keydown', { key: 'Escape' }));
check('可选模式 Esc 能关窗', !isGateOpen() && !body.children.includes(gate3));
const result3 = await gate3Promise;
check('被关掉时交回 null（调用方知道没载入）', result3 === null);

console.log(failures ? `\n${failures} 项未通过` : '\n全部通过');
process.exit(failures ? 1 : 0);
