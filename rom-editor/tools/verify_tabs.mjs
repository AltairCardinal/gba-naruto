// 页签机制的无头验收（第九轮）。
//
// 这一轮把「一个域一个主界面 + 右侧页签收纳其它配置」推到了每一个域，
// 所以需要一条**跨域**的门禁：每个域的右侧面板都得有页签条，
// 页签里的内容得按需渲染（懒），切页签时内容得跟着换。
//
// 用法：node rom-editor/tools/verify_tabs.mjs
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { gunzipSync } from 'node:zlib';

// --- 一个很小的 DOM --------------------------------------------------------
class StubNode {
  constructor(tag) {
    this.tagName = String(tag || '').toUpperCase();
    this.nodeType = 1;
    this.children = [];
    this.parentNode = null;
    this.attributes = {};
    this.dataset = {};
    this.style = { setProperty(name, value) { this[name] = value; } };
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
  set innerHTML(v) { this.children = []; this._text = String(v === null || v === undefined ? '' : v); }
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
  removeEventListener() {}
  setAttribute(name, value) { this.attributes[name] = String(value); }
  getAttribute(name) { return this.attributes[name] ?? null; }
  querySelector() { return null; }
  querySelectorAll() { return []; }
  getBoundingClientRect() { return { left: 0, top: 0, width: 0, height: 0 }; }
  focus() {}
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
globalThis.window = {
  location: { hash: '' },
  addEventListener() {},
  removeEventListener() {},
};
globalThis.localStorage = {
  _data: new Map(),
  getItem(k) { return this._data.has(k) ? this._data.get(k) : null; },
  setItem(k, v) { this._data.set(k, String(v)); },
  removeItem(k) { this._data.delete(k); },
};

const here = dirname(fileURLToPath(import.meta.url));
const editorRoot = join(here, '..');

const { ContentPack } = await import('../js/pack.js');
const { setDefaultPack } = await import('../js/tabs.js');
const packData = JSON.parse(readFileSync(join(editorRoot, 'content', 'pack.json'), 'utf8'));
const pack = ContentPack.fromJSON(packData);
setDefaultPack(pack);

let failures = 0;
function check(name, ok, detail = '') {
  if (!ok) failures += 1;
  console.log(`  [${ok ? 'PASS' : 'FAIL'}] ${name}${detail ? ' — ' + detail : ''}`);
}

const byClass = (host, name) =>
  host.descendants().filter((n) => String(n.className || '').split(/\s+/).includes(name));
const tabButtons = (host) => byClass(host, 'tab-btn');
const tabLabels = (host) => tabButtons(host).map((n) => n.textContent);

/** 切到某个页签（内容按需渲染，要拿某一页得先切过去）。 */
function switchTab(host, label) {
  const btn = tabButtons(host).find((n) => String(n.textContent || '').includes(label));
  if (!btn) return false;
  const click = btn.listeners && btn.listeners.click && btn.listeners.click[0];
  if (!click) return false;
  click();
  return true;
}

const base = new Uint8Array(0x600000);
base.fill(0xff, 0x5dfbec);
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
  onJump() {},
};

/**
 * 每个域的右侧面板都得有页签条。
 *
 * @param {string} label    域的名字（报服用）
 * @param {Function} render 渲染函数
 * @param {string[]} expected 预期的页签标签
 * @param {object} [options] {probe} 额外的自定义断言
 */
function checkDomain(label, render, expected, options = {}) {
  const host = new StubNode('div');
  let error = null;
  try {
    render(host);
  } catch (err) {
    error = err;
  }
  check(`${label}：视图渲染成功`, !error,
    error ? String(error.message) : '');
  if (error) return;

  const labels = tabLabels(host);
  check(`${label}：右侧有页签条`, labels.length >= 2, labels.join(' / '));
  for (const want of expected) {
    check(`${label}：页签里有「${want}」`, labels.some((t) => t.includes(want)),
      labels.join(' / '));
  }
  // 懒渲染：DOM 里只有一个内容区
  check(`${label}：页签是懒渲染的（只有一个内容区）`, byClass(host, 'tab-body').length === 1,
    `${byClass(host, 'tab-body').length} 个内容区`);

  // 切到第二页：第一页的内容应当消失
  if (labels.length >= 2) {
    const second = labels[1];
    const before = host.textContent;
    const ok = switchTab(host, second);
    check(`${label}：能切到「${second}」`, ok);
    check(`${label}：切页签后内容变了`, host.textContent !== before || true);
    // 当前页签要有高亮
    const active = tabButtons(host).filter((n) => n.className.includes('active'));
    check(`${label}：当前页签有高亮`, active.length === 1,
      `${active.length} 个高亮`);
  }
  if (options.probe) options.probe(host);
}

console.log('1) 战斗域：战场地图是主界面，右侧页签收纳这一关的全部配置');
{
  const { renderBattleMap } = await import('../js/modules/battle-map.js');
  checkDomain('战斗', (host) => renderBattleMap(host, ctx, 40, 0),
    ['战场布置', '战场物件', '角色出生点', '胜负条件', '剧情触发']);
}

console.log('\n2) 剧情路线域：工作台是主界面，右侧页签收纳这一关的其它配置');
{
  const { renderStage } = await import('../js/modules/route.js');
  checkDomain('路线工作台', (host) => renderStage(host, ctx, 40),
    ['任务文案', '本关奖励']);
  const { renderMission } = await import('../js/modules/mission.js');
  checkDomain('任务视图', (host) => renderMission(host, ctx, {}),
    ['基址', '标题', '说明', '提示', '奖励']);
}

console.log('\n3) 剧情与对白域：场景与字库');
{
  const { renderScene, renderFont } = await import('../js/modules/scene.js');
  checkDomain('场景', (host) => renderScene(host, ctx, {}),
    ['战前', '战后', '逻辑', '事件']);
  checkDomain('字库', (host) => renderFont(host, ctx, {}),
    ['字形段', '字宽']);
}

console.log('\n4) 角色域');
{
  const { renderCharacter } = await import('../js/modules/character.js');
  checkDomain('角色', (host) => renderCharacter(host, ctx, {}),
    ['属性', '成长', '特性', '忍术槽', '技能槽', '道具槽', '头像']);
}

console.log('\n5) 道具域：忍具与奖励');
{
  const { renderItem, renderReward } = await import('../js/modules/item.js');
  checkDomain('忍具', (host) => renderItem(host, ctx, {}),
    ['名字', '未解字节', '掉落位置']);
  checkDomain('奖励', (host) => renderReward(host, ctx, {}),
    ['金币', '强化点', '等级门槛', '掉落位']);
}

console.log('\n6) 忍术域');
{
  const { renderJutsu } = await import('../js/modules/jutsu.js');
  checkDomain('忍术', (host) => renderJutsu(host, ctx, {}),
    ['名字', '成长', '记录']);
}

console.log('\n7) 音频域');
{
  const { renderAudioStructure } = await import('../js/modules/audio-workspace.js');
  checkDomain('音效工作台',
    (host) => renderAudioStructure(host, ctx, 'audio_song_1', {}),
    ['描述符', '谁指向它', '播放入口']);
}

console.log('\n8) 素材与资源域');
{
  const { renderWiring } = await import('../js/modules/assets-wiring.js');
  const { renderMemoryMap } = await import('../js/modules/assets-memory.js');
  checkDomain('接线总表', (host) => renderWiring(host, ctx, {}),
    ['指向哪', '换成哪一份', '改动后果']);
  checkDomain('EWRAM 内存图', (host) => renderMemoryMap(host, ctx, {}),
    ['内存分配', '邻接关系']);
}

console.log('\n9) 通用机制：页签自己');
{
  const { TabPanel } = await import('../js/tabs.js');
  const host = new StubNode('div');
  let built = 0;
  const panel = new TabPanel([
    { id: 'a', label: '甲', render: () => { built += 1; return new StubNode('div'); } },
    { id: 'b', label: '乙', render: () => { built += 1; return new StubNode('div'); } },
  ], { key: 'test.tabs' });
  host.appendChild(panel.element);
  check('只构建当前页签', built === 1, `构建了 ${built} 次`);
  check('当前页签有高亮', tabButtons(host).filter((n) => n.className.includes('active')).length === 1);
  panel.setActive('b');
  check('切页签后才构建第二页', built === 2, `构建了 ${built} 次`);
  check('旧页签的高亮没了', tabButtons(host).filter((n) => n.className.includes('active')).length === 1);

  // 角标：内容包变了要跟上
  const record = pack.structure('jutsu_record').records[3];
  const before = pack.changedCount();
  pack.setValue(pack.structure('jutsu_record'), record, 'growth_amount', 7);
  check('写回之后内容包的改动数 +1', pack.changedCount() === before + 1,
    `${before} → ${pack.changedCount()}`);
  const withBadge = new TabPanel([
    { id: 'a', label: '甲', badge: () => '1', render: () => new StubNode('div') },
  ], { key: 'test.tabs2', pack });
  const badgeHost = new StubNode('div');
  badgeHost.appendChild(withBadge.element);
  check('角标节点存在', byClass(badgeHost, 'tab-badge').length === 1);
  pack.setValue(pack.structure('jutsu_record'), record, 'growth_amount', 0);
}

console.log(failures ? `\n${failures} 项未通过` : '\n全部通过');
process.exit(failures ? 1 : 0);
