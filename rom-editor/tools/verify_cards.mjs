// 卡片机制的无头验收（第十轮）。
//
// 第九轮做的是页签，作者的原话是：
//   「不要用页签了，改成同一个滚动页面中纵向排列的的卡片」
// （规格见 notes/specs/human-readable-cards-20261022.md）。
//
// 这一轮的门禁跟着换说法 —— 旧门禁断言的「页签条 / 懒渲染 / 切页签 /
// 当前页高亮」在卡片这套机制里**全都不成立**：
//   * 卡片没有「当前页」，所以没有高亮；
//   * 卡片全都渲染出来，所以没有懒渲染；
//   * 卡片**不互斥** —— 所有卡片的内容**同时**在 DOM 里
//     （这是与页签最大的不同，也是这一轮的核心诉求）。
//
// 断言清单：
//   1. 每个域的右侧有卡片堆（.card-stack），里面每张卡片是 .editor-card；
//   2. 卡片头的标题都对（依次是规格 §5「各域的卡片清单」那一列）；
//   3. 所有卡片的内容同时在 DOM 里（一张都不许藏）；
//   4. 每张卡片各有自己的角标（.card-badge）—— 改一处只亮对应那一张；
//   5. 通用机制 CardStack 自己：一次全渲染、角标跟内容包变。
//
// 用法：node rom-editor/tools/verify_cards.mjs
import { readFileSync, readdirSync, statSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join, relative } from 'node:path';

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
      _props: {},
      setProperty(name, value) { this._props[name] = String(value); },
      getPropertyValue(name) { return this._props[name] || ''; },
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
  getBoundingClientRect() { return { left: 0, top: 0, right: 0, bottom: 0, width: 0, height: 0 }; }
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
globalThis.localStorage = {
  _data: new Map(),
  getItem(k) { return this._data.has(k) ? this._data.get(k) : null; },
  setItem(k, v) { this._data.set(k, String(v)); },
  removeItem(k) { this._data.delete(k); },
};

const here = dirname(fileURLToPath(import.meta.url));
const editorRoot = join(here, '..');
const repoRoot = join(here, '..', '..');

const { ContentPack } = await import('../js/pack.js');
const { setDefaultPack } = await import('../js/cards.js');
const packData = JSON.parse(readFileSync(join(editorRoot, 'content', 'pack.json'), 'utf8'));
const pack = ContentPack.fromJSON(packData);
setDefaultPack(pack);

let failures = 0;
function check(name, ok, detail = '') {
  if (!ok) failures += 1;
  console.log(`  [${ok ? 'PASS' : 'FAIL'}] ${name}${detail ? ' — ' + detail : ''}`);
}

// --- 找卡片 ----------------------------------------------------------------
const byClass = (host, name) =>
  host.descendants().filter((n) => String(n.className || '').split(/\s+/).includes(name));

/** 卡片堆（.card-stack）—— 右侧面板装卡片的那一摞。 */
const cardStacks = (host) => byClass(host, 'card-stack');
/** 卡片（.editor-card）—— 每一类配置一张。 */
const cardsOf = (host) => byClass(host, 'editor-card');
/** 卡片头的标题。 */
const cardTitle = (card) => {
  const node = byClass(card, 'editor-card-title')[0];
  return node ? String(node.textContent || '').trim() : '';
};
/** 卡片体（装内容的那一格）。 */
const cardBody = (card) => byClass(card, 'editor-card-body')[0] || null;
/** 卡片自己的角标（这一类改了几处）。 */
const cardBadges = (card) => byClass(card, 'card-badge');
/** 节点往上找最近的一张卡片（角标必须长在某张卡片里）。 */
function closestCard(node) {
  let cur = node && node.parentNode;
  while (cur) {
    if (String(cur.className || '').split(/\s+/).includes('editor-card')) return cur;
    cur = cur.parentNode;
  }
  return null;
}
/** 这张卡片（或它的祖先）是不是被藏起来了。 */
function isHidden(node) {
  let cur = node;
  while (cur) {
    if (cur.classList && cur.classList.contains('hidden')) return true;
    if (cur.style && cur.style.display === 'none') return true;
    cur = cur.parentNode;
  }
  return false;
}
/** 有角标（亮着）的卡片标题。 */
const litCards = (host) => cardsOf(host)
  .filter((card) => cardBadges(card).length > 0)
  .map(cardTitle);

// --- 每个域的卡片清单（规格 §5）-------------------------------------------
//
// 一条期望可以写成字符串，也可以写成数组（几个都认）。
// 有两格规格自己前后不一致，所以各认两个名字：
//   * 忍具的第二张卡：规格 §5 写「未解字节」，但第九轮的实现是「记录字段」
//     （§5 抄的是 notes/rom-editor-20261021.md §6.13.4 那张更早的表），
//     而 §2.3 又说「label 保持」；
//   * 忍术的第二张卡：规格 §5 写「成长」，但 §3.3 的例子把卡片头写成
//     「随等级成长的属性」（那一节讲的就是这张卡）。
// 别的名字不认 —— 卡片改名（=作者看不懂了）要被抓出来。
const JUTSU_GROWTH_CARD = ['成长', '随等级成长的属性'];
const DOMAINS = {
  battle: ['战场布置', '战场物件', '角色出生点', '胜负条件', '剧情触发'],
  routeStage: ['任务文案', '本关奖励'],
  mission: ['基址', '标题', '说明', '提示', '奖励'],
  scene: ['战前', '战后', '逻辑', '事件'],
  font: ['字形段', '字宽'],
  character: ['属性', '成长', '特性', '忍术槽', '技能槽', '道具槽', '头像'],
  item: ['名字', ['记录字段', '未解字节'], '掉落位置'],
  reward: ['金币', '强化点', '等级门槛', '掉落位'],
  jutsu: ['名字', JUTSU_GROWTH_CARD, '记录'],
  audio: ['描述符', '谁指向它', '播放入口'],
  wiring: ['指向哪', '换成哪一份', '改动后果'],
  memory: ['内存分配', '邻接关系'],
  structureTable: ['字段', '来源'],
  textTable: ['文本', '来源'],
};

/**
 * 验一个域的右侧面板：卡片堆、卡片标题、内容同时在 DOM 里、角标各归各的。
 *
 * @param {string} label    域的名字（报服用）
 * @param {Function} render 渲染函数
 * @param {Array} expected  预期的卡片标题
 * @returns {?object} {host, cards}（渲染失败时是 null）
 */
function checkDomain(label, render, expected) {
  const host = new StubNode('div');
  let error = null;
  try {
    render(host);
  } catch (err) {
    error = err;
  }
  check(`${label}：视图渲染成功`, !error, error ? String(error.message) : '');
  if (error) return null;

  // 1) 右侧有卡片堆
  const stacks = cardStacks(host);
  check(`${label}：右侧有卡片堆（.card-stack）`, stacks.length >= 1, `${stacks.length} 个`);

  // 2) 里面每张卡片是 .editor-card
  const cards = cardsOf(host);
  check(`${label}：卡片是 .editor-card`, cards.length >= 1, `${cards.length} 张`);

  // 3) 卡片头的标题都在（依次是规格 §5 那一列）
  const titles = cards.map(cardTitle);
  const allowed = [];
  for (const want of expected) {
    const accepts = Array.isArray(want) ? want : [want];
    allowed.push(...accepts);
    check(`${label}：有「${accepts[0]}」这张卡片`, titles.some((t) => accepts.includes(t)),
      titles.join(' / '));
  }
  const extra = titles.filter((t) => !allowed.includes(t));
  check(`${label}：没有清单以外的卡片`, extra.length === 0, extra.join(' / '));
  check(`${label}：卡片数量与清单一致`, cards.length === expected.length,
    `${cards.length} 张 / 清单 ${expected.length} 张`);

  // 4) 所有卡片的内容同时在 DOM 里（卡片不互斥 —— 这是与页签最大的不同）
  let withContent = 0;
  for (const card of cards) {
    const title = cardTitle(card) || '（没标题）';
    const body = cardBody(card);
    const content = body ? body.children.filter((c) => c && c.nodeType === 1) : [];
    if (content.length) withContent += 1;
    check(`${label}：「${title}」卡片有内容`, content.length > 0, `${content.length} 个节点`);
    check(`${label}：「${title}」卡片没渲染出错`,
      !String(card.textContent || '').includes('渲染出错'));
    check(`${label}：「${title}」卡片没被藏起来`, !isHidden(card));
  }
  check(`${label}：所有卡片的内容同时在 DOM 里`, withContent === cards.length && cards.length > 0,
    `${withContent}/${cards.length} 张有内容`);

  // 5) 角标各归各的：一张卡片最多一个角标，角标必须长在某张卡片里
  const badges = byClass(host, 'card-badge');
  const stray = badges.filter((b) => !closestCard(b));
  check(`${label}：角标都长在各自的卡片里`, stray.length === 0,
    `${badges.length} 个角标，${stray.length} 个没归属`);
  const multi = cards.filter((c) => cardBadges(c).length > 1);
  check(`${label}：一张卡片最多一个角标`, multi.length === 0, multi.map(cardTitle).join(' / '));
  const blank = badges.filter((b) => !String(b.textContent || '').trim());
  check(`${label}：角标有字`, blank.length === 0, `${blank.length} 个空角标`);

  return { host, cards };
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

console.log('1) 战斗域：战场地图是主界面，右侧卡片收纳这一关的全部配置');
{
  const { renderBattleMap } = await import('../js/modules/battle-map.js');
  checkDomain('战斗', (host) => renderBattleMap(host, ctx, 40, 0), DOMAINS.battle);
}

console.log('\n2) 剧情路线域：工作台是主界面，右侧卡片收纳这一关的其它配置');
{
  const { renderStage } = await import('../js/modules/route.js');
  checkDomain('路线工作台', (host) => renderStage(host, ctx, 40), DOMAINS.routeStage);
  const { renderMission } = await import('../js/modules/mission.js');
  checkDomain('任务视图', (host) => renderMission(host, ctx, {}), DOMAINS.mission);
}

console.log('\n3) 剧情与对白域：场景与字库');
{
  const { renderScene, renderFont } = await import('../js/modules/scene.js');
  checkDomain('场景', (host) => renderScene(host, ctx, {}), DOMAINS.scene);
  checkDomain('字库', (host) => renderFont(host, ctx, {}), DOMAINS.font);
}

console.log('\n4) 角色域');
{
  const { renderCharacter } = await import('../js/modules/character.js');
  checkDomain('角色', (host) => renderCharacter(host, ctx, {}), DOMAINS.character);
}

console.log('\n5) 道具域：忍具与奖励');
{
  const { renderItem, renderReward } = await import('../js/modules/item.js');
  checkDomain('忍具', (host) => renderItem(host, ctx, {}), DOMAINS.item);
  checkDomain('奖励', (host) => renderReward(host, ctx, {}), DOMAINS.reward);
}

console.log('\n6) 忍术域');
{
  const { renderJutsu } = await import('../js/modules/jutsu.js');
  checkDomain('忍术', (host) => renderJutsu(host, ctx, {}), DOMAINS.jutsu);
}

console.log('\n7) 音频域');
{
  const { renderAudioStructure } = await import('../js/modules/audio-workspace.js');
  checkDomain('音效工作台',
    (host) => renderAudioStructure(host, ctx, 'audio_song_1', {}),
    DOMAINS.audio);
}

console.log('\n8) 素材与资源域');
{
  const { renderWiring } = await import('../js/modules/assets-wiring.js');
  const { renderMemoryMap } = await import('../js/modules/assets-memory.js');
  checkDomain('接线总表', (host) => renderWiring(host, ctx, {}), DOMAINS.wiring);
  checkDomain('EWRAM 内存图', (host) => renderMemoryMap(host, ctx, {}), DOMAINS.memory);
}

console.log('\n9) 通用编辑器（兜底）：结构表与文本表');
{
  const { StructureEditor, TextTableEditor } = await import('../js/editors.js');
  const structure = pack.structure('jutsu_record');
  const editor = new StructureEditor(pack, structure, { onChange() {}, onJump() {} });
  checkDomain('结构表编辑器', (host) => {
    editor.render(host);
    const first = (editor.records || [])[0];
    if (first) editor.openDetail(first);
  }, DOMAINS.structureTable);

  const table = pack.textTable('jutsu_names');
  const textEditor = new TextTableEditor(pack, table, { onChange() {}, onJump() {} });
  checkDomain('文本表编辑器', (host) => {
    textEditor.render(host);
    const first = (textEditor.records || [])[0];
    if (first) textEditor.openDetail(first);
  }, DOMAINS.textTable);
}

console.log('\n10) 角标：改一处只亮对应那一张');
{
  // 忍术域：改「成长」组里的一个字段，只有「成长」那张卡片亮角标。
  const { renderJutsu } = await import('../js/modules/jutsu.js');
  const host = new StubNode('div');
  renderJutsu(host, ctx, {});
  check('忍术：改之前没有卡片亮着', litCards(host).length === 0, litCards(host).join(' / '));

  const structure = pack.structure('jutsu_record');
  const field = (structure.fields || []).find((f) => f.group === '成长' && f.type !== 'hex');
  const records = (structure.records || []).filter((r) => r.values && field.key in r.values);
  const before = records.map((r) => r.values[field.key]);
  records.forEach((r) => {
    pack.setValue(structure, r, field.key, ((Number(r.values[field.key]) || 0) + 1) & 0xff);
  });
  const lit = litCards(host);
  check('忍术：改一处只有一张卡片亮着', lit.length === 1, lit.join(' / '));
  check('忍术：亮的是「成长」那张卡片', JUTSU_GROWTH_CARD.includes(lit[0]), lit.join(' / '));
  // 还原（内容包是共享的，别把改动留给后面的人）
  records.forEach((r, i) => pack.setValue(structure, r, field.key, before[i]));
  check('忍术：还原之后没有卡片亮着', litCards(host).length === 0, litCards(host).join(' / '));
}

console.log('\n11) 通用机制：卡片堆自己');
{
  const { CardStack } = await import('../js/cards.js');
  const host = new StubNode('div');
  let built = 0;
  const stack = new CardStack([
    { id: 'a', label: '甲', render: () => { built += 1; return new StubNode('div'); } },
    { id: 'b', label: '乙', render: () => { built += 1; return new StubNode('div'); } },
  ], { pack });
  host.appendChild(stack.element);

  // 卡片**没有懒渲染**：两张卡一次全建出来
  check('两张卡片一次全渲染出来（没有懒渲染）', built === 2, `构建了 ${built} 次`);
  const cards = cardsOf(host);
  check('两张卡片都在 DOM 里', cards.length === 2, `${cards.length} 张`);
  check('卡片标题各是甲 / 乙', cards.map(cardTitle).join('、') === '甲、乙',
    cards.map(cardTitle).join('、'));

  // 角标：各有各的 —— 改一处只亮那一张
  stack.setBadge('a', '1');
  const after = cardsOf(host);
  const a = after.find((c) => cardTitle(c) === '甲');
  const b = after.find((c) => cardTitle(c) === '乙');
  check('甲有角标', cardBadges(a).length === 1, `${cardBadges(a).length} 个`);
  check('乙没有角标', cardBadges(b).length === 0, `${cardBadges(b).length} 个`);
  check('角标写的是 1', String(cardBadges(a)[0]?.textContent || '') === '1',
    String(cardBadges(a)[0]?.textContent || ''));

  // 角标跟着内容包走
  const structure = pack.structure('jutsu_record');
  const record = (structure.records || [])[3];
  const key = 'growth_amount';
  const original = record.values[key];
  const counter = new CardStack([
    {
      id: 'a',
      label: '甲',
      badge: () => String(pack.changedCount()),
      render: () => new StubNode('div'),
    },
    { id: 'b', label: '乙', render: () => new StubNode('div') },
  ], { pack });
  const counterHost = new StubNode('div');
  counterHost.appendChild(counter.element);
  const changedBefore = pack.changedCount();
  pack.setValue(structure, record, key, ((Number(original) || 0) + 1) & 0xff);
  check('内容包改了以后改动数 +1', pack.changedCount() === changedBefore + 1,
    `${changedBefore} → ${pack.changedCount()}`);
  const badgeText = String((cardBadges(cardsOf(counterHost).find((c) => cardTitle(c) === '甲'))[0] || {}).textContent || '');
  check('角标跟着内容包变', badgeText === String(pack.changedCount()), badgeText);
  pack.setValue(structure, record, key, original);
  stack.dispose();
  counter.dispose();
}

console.log('\n12) 旧页签机制不用了');
{
  const jsRoot = join(editorRoot, 'js');
  const walk = (dir) => {
    const out = [];
    for (const name of readdirSync(dir)) {
      const path = join(dir, name);
      if (statSync(path).isDirectory()) out.push(...walk(path));
      else if (name.endsWith('.js')) out.push(path);
    }
    return out;
  };
  const hits = [];
  for (const file of walk(jsRoot)) {
    const rel = relative(jsRoot, file).replace(/\\/g, '/');
    if (rel === 'tabs.js') continue;
    const text = readFileSync(file, 'utf8');
    if (/TabPanel|tabPanel|tab-panel|tab-bar|tab-btn|tab-body|tab-badge/.test(text)) {
      hits.push(rel);
    }
  }
  check('各域不再用页签机制', hits.length === 0, hits.join('、'));
  check('页签机制的文件已删除（js/tabs.js）', !existsSync(join(jsRoot, 'tabs.js')),
    existsSync(join(jsRoot, 'tabs.js')) ? '还在 —— 页签不用了，删掉它（规格 §2.3）' : '已删');
}

console.log(failures ? `\n${failures} 项未通过` : '\n全部通过');
process.exit(failures ? 1 : 0);
