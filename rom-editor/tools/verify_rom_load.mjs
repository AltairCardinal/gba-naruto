// 载入 ROM 的回归验收（无头）。
//
// 覆盖的是**两个用户报出来的 bug**（2026-10-24）：
//
//   BUG-1  打开编辑器 → 弹出的门禁里选「载入内置 ROM」⇒ 弹窗关了，
//          但编辑器里**没有 ROM**（载入状态条仍然是「木叶战记熊组汉化版原版」）。
//          根因：门禁的两条回调不对称 —— 本地文件那条写了状态，
//          内置那条只取字节、忘了写。
//
//   BUG-2  再点载入状态条上的【木叶战记熊组汉化版原版】⇒ ROM 这次真的载入了，
//          但**顶栏还在一直转「加载中」的滚动条**。
//          根因：顶栏进度条「显示」与「撤掉」分写在两处，撤掉的那处漏了。
//
// 分三段：
//   1) 流程模块 `js/romload.js`：两条来源都写状态；带进度条的那条路结束一定撤条。
//   2) 端到端：门禁里点「载入内置 ROM」⇒ `state.rom` 真的有 ROM（BUG-1）。
//   3) 端到端：载入状态条那条路 ⇒ 载入完成后顶栏进度条是收起来的（BUG-2）。
//
// 端到端两段**真的 import `js/app.js`**（带桩 DOM / 桩 fetch）——
// 光测流程模块测不到「app.js 是不是把两条路都接对了」，
// 而 BUG-1 恰恰就出在那儿。
//
// 用法：node rom-editor/tools/verify_rom_load.mjs
// stdout 在 PowerShell 下会被 GBK 弄乱，所以正文写到 build/rom-load-verify.txt。
import { readFileSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const repoRoot = join(here, '..', '..');
const packPath = join(repoRoot, 'rom-editor', 'content', 'pack.json');
const romPath = join(repoRoot, 'rom', 'base.gba');

const lines = [];
let failures = 0;
function check(name, ok, detail = '') {
  if (!ok) failures += 1;
  const line = `  [${ok ? 'PASS' : 'FAIL'}] ${name}${detail ? ' — ' + detail : ''}`;
  lines.push(line);
  console.log(line);
}
function head(text) {
  lines.push(text);
  console.log(text);
}
const tick = (ms = 10) => new Promise((resolve) => setTimeout(resolve, ms));

// ---------------------------------------------------------------------------
// 1) 流程模块：两条来源都写状态；带进度条的那条路结束一定撤条
// ---------------------------------------------------------------------------
head('\n1) 流程模块（js/romload.js）');
{
  const { createRomLoader } = await import('../js/romload.js');
  const bytes = new Uint8Array([1, 2, 3, 4]);

  const make = (fetchBundled, readLocalFile) => {
    const calls = [];
    const loader = createRomLoader({
      fetchBundled,
      readLocalFile,
      apply: async (b, source, name) => { calls.push({ kind: 'apply', b, source, name }); },
      indicator: {
        show: (phase) => calls.push({ kind: 'show', label: phase.label }),
        hide: () => calls.push({ kind: 'hide' }),
        showError: (text) => calls.push({ kind: 'showError', text }),
      },
    });
    return { loader, calls };
  };

  // 内置 ROM
  {
    const { loader, calls } = make(async () => bytes, async () => bytes);
    const out = await loader.loadBundled(() => {});
    const applied = calls.find((c) => c.kind === 'apply');
    check('内置 ROM：写状态被调用了一次', calls.filter((c) => c.kind === 'apply').length === 1);
    check('内置 ROM：写的是同一份字节', !!applied && applied.b === bytes);
    check('内置 ROM：来源标成 bundled', !!applied && applied.source === 'bundled', applied && applied.source);
    check('内置 ROM：名字是 base.gba', !!applied && applied.name === 'base.gba', applied && applied.name);
    check('内置 ROM：返回字节', out === bytes);
    check('门禁那条路（bar: false）不碰顶栏指示器',
      !calls.some((c) => c.kind === 'show' || c.kind === 'hide' || c.kind === 'showError'),
      calls.map((c) => c.kind).join(' / '));
  }

  // 本地文件
  {
    const { loader, calls } = make(async () => bytes, async () => bytes);
    await loader.loadFile({ name: 'local.gba' });
    const applied = calls.find((c) => c.kind === 'apply');
    check('本地文件：写状态被调用了一次', calls.filter((c) => c.kind === 'apply').length === 1);
    check('本地文件：来源标成 file', !!applied && applied.source === 'file', applied && applied.source);
    check('本地文件：名字取文件名', !!applied && applied.name === 'local.gba', applied && applied.name);
  }

  // 载入状态条那条路（bar: true）：结束时进度条必须撤掉
  {
    const { loader, calls } = make(async () => bytes, async () => bytes);
    await loader.loadBundled(null, { bar: true });
    check('带进度条的那条路：开始时显示了进度条',
      calls.some((c) => c.kind === 'show'), calls.map((c) => c.kind).join(' / '));
    check('带进度条的那条路：**结束时把进度条撤掉了**',
      calls.some((c) => c.kind === 'hide'), calls.map((c) => c.kind).join(' / '));
    const last = calls[calls.length - 1];
    check('撤条是最后一步（撤完就没事了）', last && last.kind === 'hide',
      last ? last.kind : '没有调用');
  }

  // 失败：进度条留在屏幕上并变红，错误继续往外抛
  {
    const { loader, calls } = make(async () => { throw new Error('内置 ROM 取不到'); },
      async () => bytes);
    let thrown = null;
    try {
      await loader.loadBundled(null, { bar: true });
    } catch (err) {
      thrown = err;
    }
    check('失败：错误往外抛', !!thrown && thrown.message === '内置 ROM 取不到',
      thrown ? thrown.message : '没有抛');
    check('失败：进度条留在屏幕上并报错',
      calls.some((c) => c.kind === 'showError' && String(c.text).includes('内置 ROM 取不到')),
      calls.map((c) => c.kind).join(' / '));
    check('失败：**没有**撤条（要让作者看得见没载入成功）',
      !calls.some((c) => c.kind === 'hide'), calls.map((c) => c.kind).join(' / '));
    check('失败：不写状态',
      !calls.some((c) => c.kind === 'apply'), calls.map((c) => c.kind).join(' / '));
  }

  // 取不到字节
  {
    const { loader, calls } = make(async () => null, async () => bytes);
    let thrown = null;
    try {
      await loader.loadBundled(null, { bar: true });
    } catch (err) {
      thrown = err;
    }
    check('一个字节都没有 ⇒ 报错', !!thrown && /没有读到任何字节/.test(thrown.message),
      thrown ? thrown.message : '没有抛');
    check('一个字节都没有 ⇒ 不写状态',
      !calls.some((c) => c.kind === 'apply'), calls.map((c) => c.kind).join(' / '));
  }
}

// ---------------------------------------------------------------------------
// 桩：一个够用的 DOM + window + fetch
// ---------------------------------------------------------------------------
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
  insertBefore(node, ref) {
    const at = ref ? this.children.indexOf(ref) : -1;
    if (at < 0) return this.appendChild(node);
    this.children.splice(at, 0, node);
    if (node) node.parentNode = this;
    return node;
  }
  removeChild(node) {
    const at = this.children.indexOf(node);
    if (at >= 0) this.children.splice(at, 1);
    if (node) node.parentNode = null;
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
  removeAttribute(name) { delete this.attributes[name]; }
  hasAttribute(name) { return name in this.attributes; }
  querySelector() { return null; }
  querySelectorAll() { return []; }
  focus() { document.activeElement = this; }
  blur() { if (document.activeElement === this) document.activeElement = null; }
  /** 点一下：把 'click' 的监听器跑一遍。 */
  click() {
    const event = { type: 'click', target: this, preventDefault() {}, stopPropagation() {} };
    for (const fn of [...(this.listeners.click || [])]) fn(event);
  }
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

const packBytes = readFileSync(packPath);
const romBytes = readFileSync(romPath);

/**
 * 装一套 DOM / window / fetch 的桩。
 *
 * @param {object} options
 * @param {boolean} [options.baseGbaFailsFirst] 内置 ROM 的**第一次**取不到（之后能取到）
 */
function installWorld(options = {}) {
  const byId = new Map();
  const windowListeners = new Map();
  const stats = { baseGba: 0 };

  const body = new StubNode('body');

  const windowStub = {
    location: { hash: '' },
    listeners: {},
    addEventListener(name, fn) { (this.listeners[name] ||= []).push(fn); },
    removeEventListener(name, fn) {
      const list = this.listeners[name] || [];
      const at = list.indexOf(fn);
      if (at >= 0) list.splice(at, 1);
    },
    dispatch(type, data) {
      for (const fn of [...(this.listeners[type] || [])]) fn({ type, data });
    },
  };

  const documentStub = {
    activeElement: null,
    body,
    listeners: {},
    createElement(tag) {
      const node = new StubNode(tag);
      if (String(tag).toLowerCase() === 'iframe') {
        // 内置 ROM 的加载文档：真浏览器里它回一条 postMessage。
        // 这里**总是回一条失败** —— 于是流程会退到 fetch 候选那条路，
        // 测试就能精确控制「内置 ROM 第几次能取到」。
        node.contentWindow = {
          postMessage() {
            setTimeout(() => windowStub.dispatch('message', {
              source: 'rom-loader', state: 'error', payload: '桩：加载文档失败',
            }), 0);
          },
        };
      }
      return node;
    },
    createTextNode(text) { return { __text: String(text), textContent: String(text), nodeType: 3 }; },
    getElementById(id) {
      if (!byId.has(id)) byId.set(id, new StubNode('div'));
      return byId.get(id);
    },
    querySelector() { return null; },
    querySelectorAll() { return []; },
    addEventListener(name, fn) { (this.listeners[name] ||= []).push(fn); },
    removeEventListener(name, fn) {
      const list = this.listeners[name] || [];
      const at = list.indexOf(fn);
      if (at >= 0) list.splice(at, 1);
    },
  };

  // iframe 挂上去之后触发它的 'load'（真浏览器里也是这个顺序）。
  const bodyAppend = body.appendChild.bind(body);
  body.appendChild = (node) => {
    const out = bodyAppend(node);
    if (node && node.tagName === 'IFRAME') {
      setTimeout(() => {
        for (const fn of [...(node.listeners.load || [])]) fn({ type: 'load', target: node });
      }, 0);
    }
    return out;
  };

  const notFound = () => ({
    ok: false, status: 404, body: null, headers: { get: () => null },
    arrayBuffer: async () => new ArrayBuffer(0),
  });
  const found = (bytes) => ({
    ok: true, status: 200, body: null, headers: { get: () => null },
    arrayBuffer: async () => bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength),
  });

  async function fetchStub(url) {
    const u = String(url);
    if (u.includes('pack.min.json.gz')) return notFound();
    if (u.includes('/content/pack.json')) return found(packBytes);
    if (u.includes('base-rom.bin.gz')) return notFound();
    if (u.includes('base.gba')) {
      stats.baseGba += 1;
      if (options.baseGbaFailsFirst && stats.baseGba === 1) return notFound();
      return found(romBytes);
    }
    return notFound();
  }

  globalThis.document = documentStub;
  globalThis.window = windowStub;
  globalThis.fetch = fetchStub;
  // app.js 用的是裸 `location.hash`（浏览器全局），Node 里没有。
  globalThis.location = windowStub.location;

  return { documentStub, windowStub, body, byId, stats };
}

/** 门禁窗口（body 的最后一个子节点）。 */
function gateOverlay(body) {
  return body.children.find((n) => String(n.className).includes('rom-gate-overlay'));
}
function buttonByText(root, text) {
  return root.descendants().find((n) => n.tagName === 'BUTTON'
    && String(n.textContent).trim() === text);
}
async function waitFor(predicate, timeoutMs = 30000, label = '条件') {
  const deadline = Date.now() + timeoutMs;
  for (;;) {
    const value = predicate();
    if (value) return value;
    if (Date.now() > deadline) throw new Error(`等了 ${timeoutMs} 毫秒还没等到：${label}`);
    await tick(20);
  }
}

// ---------------------------------------------------------------------------
// 2) 端到端：门禁里点「载入内置 ROM」⇒ 编辑器里真的有 ROM（BUG-1）
// ---------------------------------------------------------------------------
head('\n2) 端到端：门禁里选「载入内置 ROM」');
{
  const world = installWorld();
  // app.js 是 ESM 模块：用查询串区分实例，两段端到端各跑一份干净的。
  const app = await import('../js/app.js?case=gate');

  const overlay = await waitFor(() => gateOverlay(world.body), 30000, '门禁窗口');
  check('门禁升起来了', !!overlay);

  const bundledButton = buttonByText(overlay, '载入内置 ROM');
  check('门禁里有「载入内置 ROM」', !!bundledButton);
  check('门禁是必需模式（关不掉）', !buttonByText(overlay, '取消'));

  bundledButton.click();

  // 门禁关掉 ⇒ 内置 ROM 真的取到并写进了状态。
  await waitFor(() => !gateOverlay(world.body), 60000, '门禁关闭');
  check('门禁关掉了（内置 ROM 取到了）', !gateOverlay(world.body));

  check('BUG-1：**编辑器里真的有 ROM 了**', !!app.state.rom,
    app.state.rom ? `${app.state.rom.length.toLocaleString()} 字节` : 'state.rom 还是空的');
  check('BUG-1：ROM 来源标成 bundled', app.state.romSource === 'bundled',
    String(app.state.romSource));
  check('BUG-1：ROM 名字是 base.gba', app.state.romName === 'base.gba', String(app.state.romName));

  const slotRom = world.byId.get('slot-rom');
  const slotText = slotRom ? slotRom.textContent : '';
  check('BUG-1：载入状态条上有了 √', slotText.includes('√'), slotText);
  check('BUG-1：载入状态条上写着 ROM 的大小',
    slotText.includes(romBytes.length.toLocaleString()), slotText);
  check('BUG-1：载入状态条上**不再**有「木叶战记熊组汉化版原版」按钮',
    !slotText.includes('木叶战记熊组汉化版原版'), slotText);

  const progress = world.byId.get('load-progress');
  check('顶栏的载入进度条是收起来的',
    !!progress && progress.classList.contains('hidden'),
    progress ? progress.className : '没有进度条元素');
}

// ---------------------------------------------------------------------------
// 3) 端到端：载入状态条那条路 ⇒ 载入完成后顶栏进度条撤掉（BUG-2）
//
//    复现用户看到的顺序：门禁里那次内置 ROM 没成 ⇒ 编辑器里没有 ROM ⇒
//    于是去点载入状态条上的【木叶战记熊组汉化版原版】。
//    这里让**第一次**取内置 ROM 失败（门禁如实报错、窗口留着），
//    第二次（载入状态条那条）成功 —— 于是载入状态条上的按钮还在，正好能点。
// ---------------------------------------------------------------------------
head('\n3) 端到端：载入状态条那条路');
{
  const world = installWorld({ baseGbaFailsFirst: true });
  const app = await import('../js/app.js?case=loadbar');

  const overlay = await waitFor(() => gateOverlay(world.body), 30000, '门禁窗口');
  check('门禁升起来了', !!overlay);

  // 门禁里点「载入内置 ROM」—— 这次内置 ROM 取不到。
  buttonByText(overlay, '载入内置 ROM').click();
  await waitFor(() => {
    const err = overlay.descendants().find((n) => String(n.className).includes('rom-gate-error'));
    return err && !err.classList.contains('hidden');
  }, 60000, '门禁里的错误');
  check('内置 ROM 取不到 ⇒ 门禁不关、窗口里报错', !!gateOverlay(world.body));
  check('内置 ROM 取不到 ⇒ 编辑器里没有 ROM', !app.state.rom);

  const slotRom = world.byId.get('slot-rom');
  const bundledButton = slotRom.descendants().find((n) => n.tagName === 'BUTTON'
    && String(n.textContent).includes('木叶战记熊组汉化版原版'));
  check('载入状态条上有【木叶战记熊组汉化版原版】按钮', !!bundledButton);

  // 门禁挡着下面的内容（这是**设计**：`inert` + 遮罩，verify_rom_gate.mjs 负责断），
  // 这里要测的是载入状态条那条路自己的进度条生命周期 ⇒ 直接点它。
  bundledButton.click();

  // 完成的信号是**载入成功的 toast** —— 它在整条流程（写状态 → 撤进度条）之后才出现。
  // （不能只等 `state.rom`：那个字段在流程开头就设好了。）
  await waitFor(() => world.body.descendants().some((n) =>
    String(n.className).includes('toast')
    && String(n.textContent).includes('内置原版 ROM 已载入')), 60000, '载入成功的提示');

  check('BUG-2：ROM 这次真的载入了', !!app.state.rom,
    app.state.rom ? `${app.state.rom.length.toLocaleString()} 字节` : 'state.rom 还是空的');

  const progress = world.byId.get('load-progress');
  check('BUG-2：顶栏的「加载中」滚动条**撤掉了**',
    !!progress && progress.classList.contains('hidden'),
    progress ? `class="${progress.className}"` : '没有进度条元素');
  const fill = world.byId.get('load-progress-fill');
  check('BUG-2：进度条没有停在「不确定进度」的动画态',
    !!fill && !fill.classList.contains('indeterminate'),
    fill ? `class="${fill.className}"` : '没有进度条元素');

  const slotText = world.byId.get('slot-rom').textContent;
  check('BUG-2：载入状态条上有了 √', slotText.includes('√'), slotText);
  check('BUG-2：载入状态条上不再有【木叶战记熊组汉化版原版】按钮',
    !slotText.includes('木叶战记熊组汉化版原版'), slotText);
}

const summary = failures === 0
  ? `全部通过（${lines.filter((l) => l.includes('[PASS]')).length} 条断言）`
  : `${failures} 项失败`;
lines.push('');
lines.push(summary);
writeFileSync(join(repoRoot, 'build', 'rom-load-verify.txt'), lines.join('\n') + '\n', 'utf8');
console.log('');
console.log(summary);
// 内置 ROM 的加载文档留下过几个未清掉的定时器（真浏览器里也一样）—— 直接退出。
process.exit(failures === 0 ? 0 : 1);
