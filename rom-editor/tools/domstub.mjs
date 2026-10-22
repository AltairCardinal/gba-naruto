// 无头验收用的**极小 DOM 桩**。
//
// 编辑器要跑在浏览器里，但门禁要能在 Node 里跑 —— 于是有了这个桩：
// 它只实现 `rom-editor/js/ui.js` 与各视图真正用到的那几个接口
// （createElement / createTextNode / classList / dataset / style /
//   addEventListener / appendChild / textContent / descendants）。
//
// **它不是浏览器**：没有布局、没有 getBoundingClientRect、没有 canvas 2D 上下文
// （视图里凡是依赖这些的地方都做了降级）。所以门禁能断**结构与文本**，
// 断不了像素 —— 像素级的复核要看 `rom-editor/tools/qa-trigger-view.html`
// 那类真浏览器页面。

/** 一个元素节点。 */
export class StubNode {
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
  /** 这个节点下面的所有后代（不含自己）。 */
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

/**
 * 把桩装到全局上。
 *
 * 必须在**任何 `el()` 调用之前**装好（`ui.js` 在调用时才碰 `document`，
 * 所以 import 顺序不影响，只要第一次渲染前装好就行）。
 *
 * @param {object} extra 额外的 document 接口（`querySelector` 等）
 * @returns {object} document 桩
 */
export function installDom(extra = {}) {
  const documentStub = {
    createElement: (tag) => new StubNode(tag),
    createTextNode: (text) => ({ __text: String(text), textContent: String(text), nodeType: 3 }),
    body: new StubNode('body'),
    getElementById: () => null,
    querySelector: () => null,
    querySelectorAll: () => [],
    ...extra,
  };
  globalThis.document = documentStub;
  globalThis.window = {
    location: { hash: '' },
    addEventListener() {},
    removeEventListener() {},
  };
  return documentStub;
}
