// 道具域统一视图（忍具 / 奖励）的无头验收脚本。
//
// 对应用户反馈：「应当按统一的任务编辑来呈现，然后按索引表列出，
// 将其他表的内容都作为字段呈现」—— 道具域照着做了一遍，这里验一遍。
//
// 右侧面板是**卡片**（见 notes/specs/human-readable-cards-20261022.md）：
//   忍具 = 名字 / 记录字段 / 掉落位置
//   奖励 = 金币 / 强化点 / 等级门槛 / 掉落位
// 卡片**不互斥**：所有卡片的内容同时在 DOM 里（这是与页签最大的不同）。
//
// 用法：node rom-editor/tools/verify_item_view.mjs
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
// 这个脚本住在 rom-editor/tools/，所以仓库根在两级之上。
const repoRoot = join(here, '..', '..');
const packPath = join(repoRoot, 'rom-editor', 'content', 'pack.json');

const { ContentPack } = await import('../js/pack.js');
const { renderItems } = await import('../js/modules/items.js');
const {
  rewardRowsForItem, rewardNumberFields, rewardSlotArray, itemNameTable,
} = await import('../js/modules/item.js');

let failures = 0;
function check(name, ok, detail = '') {
  if (!ok) failures += 1;
  console.log(`  [${ok ? 'PASS' : 'FAIL'}] ${name}${detail ? ' — ' + detail : ''}`);
}

const packData = JSON.parse(readFileSync(packPath, 'utf8'));
const pack = ContentPack.fromJSON(packData);
const opened = [];
const jumps = [];

function makeCtx(target) {
  return {
    pack: target,
    rom: new Uint8Array(0),
    baseRom: new Uint8Array(0),
    state: { view: { panel: null } },
    onChange() {},
    openPanel(kind, id, params) { opened.push({ kind, id, params }); },
    goModule() {},
    render() {},
    setStatus() {},
    onJump(target) { jumps.push(target); },
  };
}

const ctx = makeCtx(pack);

/** 渲染道具域的某个面板。 */
function renderPanel(panel, target = ctx) {
  const host = new StubNode('div');
  target.state.view = { panel };
  renderItems(host, target);
  return host;
}

/** 分栏：左边是列表，右边是详情。 */
function panes(host) {
  const split = host.descendants()
    .find((n) => String(n.className || '').split(/\s+/).includes('split'));
  if (!split) return null;
  return { list: split.children[0], detail: split.children[2] };
}

/** 表格的正文行（跳过表头行）。 */
function bodyRows(node) {
  const tbodies = node.descendants().filter((n) => n.tagName === 'TBODY');
  if (!tbodies.length) return [];
  return tbodies[0].children.filter((n) => n.tagName === 'TR');
}

/** 带 class 的节点。 */
function byClass(node, name) {
  return node.descendants()
    .filter((n) => String(n.className || '').split(/\s+/).includes(name));
}

/**
 * 卡片堆（.card-stack）—— 右侧面板装卡片的那一摞。
 */
function cardStacks(node) {
  return byClass(node, 'card-stack');
}

/** 卡片（.editor-card）—— 每一类配置一张。 */
function cardsOf(node) {
  return byClass(node, 'editor-card');
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
function cardByTitle(node, title) {
  return cardsOf(node).find((c) => cardTitle(c) === title) || null;
}

/** 某张卡片上的角标文字（没有角标就是 null）。 */
function cardBadge(node, title) {
  const card = cardByTitle(node, title);
  if (!card) return null;
  const badge = byClass(card, 'card-badge')[0];
  return badge ? String(badge.textContent || '') : null;
}

/** 某张卡片里的文字。 */
function cardText(node, title) {
  const card = cardByTitle(node, title);
  return card ? String(card.textContent || '') : '';
}

const items = pack.structure('item_record');
const rewards = pack.structure('reward_table');
const names = itemNameTable(pack);

console.log('1) 忍具视图：左边按记录表列出');
{
  const host = renderPanel({ kind: 'item', id: '忍具', params: {} });
  const panesOf = panes(host);
  check('忍具视图渲染出来了', !!panesOf && !!panesOf.list && !!panesOf.detail,
    panesOf ? '有列表与详情' : '没有分栏');
  const rows = panesOf ? bodyRows(panesOf.list) : [];
  check('左边列表行数 = 记录表条数',
    rows.length === items.entry_count,
    `${rows.length} 行（记录表 ${items.entry_count} 条）`);
  const text = panesOf ? panesOf.detail.textContent : '';
  check('详情写明这 16 个字节各自有多少格有据、几格保留',
    /有原生代码依据/.test(text) && /格保留/.test(text),
    (text.match(/[^·]{0,30}有原生代码依据[^·]{0,20}/) || [''])[0]);
  // 「记录字段」那张卡片：每一格都有名字与依据。
  const bytesCard = cardByTitle(panesOf.detail, '记录字段');
  const bytesText = bytesCard && cardBody(bytesCard) ? cardBody(bytesCard).textContent : '';
  check('记录字段卡片给出的是**字段名**而不是「未解字节」',
    !/未解字节/.test(bytesText) && /效果数值/.test(bytesText),
    (bytesText.match(/[^·]{0,20}效果数值[^·]{0,14}/) || [''])[0]);
  check('原生代码不读的三格标「保留」',
    /保留/.test(bytesText),
    (bytesText.match(/[^·]{0,10}保留[^·]{0,10}/) || [''])[0]);
}

console.log('\n2) 奖励视图：左边按奖励表列出');
{
  const host = renderPanel({ kind: 'reward', id: '奖励', params: {} });
  const panesOf = panes(host);
  check('奖励视图渲染出来了', !!panesOf && !!panesOf.list && !!panesOf.detail,
    panesOf ? '有列表与详情' : '没有分栏');
  const rows = panesOf ? bodyRows(panesOf.list) : [];
  check('左边列表行数 = 奖励表条数',
    rows.length === rewards.entry_count,
    `${rows.length} 行（奖励表 ${rewards.entry_count} 条）`);
}

console.log('\n3) 奖励详情：金币 / 强化点 / 等级门槛 + 8 个掉落位');
{
  const host = renderPanel({ kind: 'reward', id: '奖励', params: {} });
  const detail = panes(host).detail;
  const text = detail.textContent;
  const numbers = rewardNumberFields(rewards);
  check('详情里有金币 / 强化点 / 等级门槛',
    numbers.length === 3 && numbers.every((f) => text.includes(f.label)),
    numbers.map((f) => f.label).join('、'));
  // 掉落位在「掉落位」那张卡片里。
  const slotsCard = cardByTitle(detail, '掉落位');
  const slotTables = slotsCard ? byClass(slotsCard, 'grid-slots') : [];
  const slotRows = slotTables.length ? bodyRows(slotTables[0]) : [];
  check('详情里有 8 个掉落位',
    slotRows.length === 8,
    `${slotRows.length} 行`);
  const selects = slotTables.length
    ? slotTables[0].descendants().filter((n) => n.tagName === 'SELECT')
    : [];
  check('掉落位可改（类别与物品都是下拉）',
    selects.length >= 16,
    `${selects.length} 个下拉`);
}

console.log('\n4) 改一个字段 → 改动计数 +1，改回原值 → 回落');
{
  const fresh = ContentPack.fromJSON(packData);
  const freshCtx = makeCtx(fresh);
  const host = renderPanel({ kind: 'reward', id: '奖励', params: {} }, freshCtx);
  const detail = panes(host).detail;
  const goldCard = cardByTitle(detail, '金币');
  const cells = goldCard ? byClass(goldCard, 'item-number') : [];
  const goldInput = cells.length
    ? cells[0].descendants().find((n) => n.tagName === 'INPUT')
    : null;
  check('金币那一格是输入框', !!goldInput, goldInput ? `当前值 ${goldInput.value}` : '没有输入框');
  const original = goldInput.value;
  const before = fresh.changedCount();
  goldInput.listeners.change[0]({ target: { value: String(Number(original) + 1) } });
  const after = fresh.changedCount();
  check('改一个字段后改动计数 +1', after === before + 1, `${before} → ${after}`);
  goldInput.listeners.change[0]({ target: { value: original } });
  const back = fresh.changedCount();
  check('改回原值后改动计数回落', back === before, `${after} → ${back}`);
}

console.log('\n5) 这一条奖励说得出是哪几关子几的');
{
  const host = renderPanel({ kind: 'reward', id: '奖励', params: {} });
  const detail = panes(host).detail;
  const notes = byClass(detail, 'item-note');
  const noteText = notes.map((n) => n.textContent).join(' | ');
  check('详情脚注写明「第 N 关子 M 的奖励」',
    /第 \d+ 关子 \d+ 的奖励/.test(noteText),
    noteText.slice(0, 80));
  const rows = bodyRows(panes(host).list);
  const firstCell = rows.length ? rows[0].children[1].textContent : '';
  check('列表里那一行也写明是哪几关的子奖励',
    /第 \d+ 关子 \d+/.test(firstCell),
    firstCell);
  // 归属是任务索引表给的，不是算出来的。
  const { missionIndexOwners } = await import('../js/xref.js');
  const owners = missionIndexOwners(pack);
  const shared = [...owners.entries()].filter(([, list]) => list.length > 1);
  check('奖励表里确实有被好几关共用的行', shared.length > 0,
    `${shared.length} 行被共用（例：下标 ${shared[0] ? shared[0][0] : '—'}）`);
}

console.log('\n6) 忍具详情：它在哪几关掉落，且能跳过去');
{
  const host = renderPanel({ kind: 'item', id: '忍具', params: {} });
  const detail = panes(host).detail;
  // 掉落位置在「掉落位置」那张卡片里。
  const dropsCard = cardByTitle(detail, '掉落位置');
  const text = dropsCard ? dropsCard.textContent : '';
  check('详情里有「它在哪几关掉落」', text.includes('它在哪几关掉落'), '');
  // 默认落在真的掉在某一关的那个忍具上。
  let picked = null;
  for (const record of items.records) {
    if (rewardRowsForItem(pack, record.id).length) { picked = record; break; }
  }
  const drops = rewardRowsForItem(pack, picked.id);
  check('默认选中的忍具真的被某条奖励引用', drops.length > 0,
    `#${picked.id} · ${drops.length} 处`);
  const jumpLinks = dropsCard
    ? byClass(dropsCard, 'xref-link').filter((n) => n.textContent.includes('跳到这条奖励'))
    : [];
  check('掉落那一行能跳到奖励', jumpLinks.length > 0,
    `${jumpLinks.length} 个跳转`);
  opened.length = 0;
  // 用最后一行：它的下标与默认选中的那条不同，测出来才有意义。
  const targetId = drops[drops.length - 1].record.id;
  jumpLinks[jumpLinks.length - 1].listeners.click[0]({ target: {} });
  check('点它会打开奖励视图并定位到那一条',
    opened.length === 1 && opened[0].kind === 'reward' &&
    opened[0].params && opened[0].params.recordId === targetId,
    JSON.stringify(opened[0] || {}));
  // hash 往返会把面板参数冲掉（#items/reward 记不下第几条），
  // 落点不能因此跳回默认那条。
  const host2 = renderPanel({ kind: 'reward', id: '奖励', params: {} });
  const selected = bodyRows(panes(host2).list)
    .find((tr) => String(tr.className || '').split(/\s+/).includes('selected'));
  check('hash 往返之后仍落在同一条奖励上',
    !!selected && selected.children[0].textContent === String(targetId),
    selected ? `选中 #${selected.children[0].textContent}（应为 ${targetId}）` : '没有选中行');
}

console.log('\n7) 奖励 → 忍具 的反向跳转');
{
  const host = renderPanel({ kind: 'reward', id: '奖励', params: {} });
  const detail = panes(host).detail;
  // 反向跳转在「掉落位」那张卡片里。
  const slotsCard = cardByTitle(detail, '掉落位');
  const links = slotsCard
    ? byClass(slotsCard, 'xref-link').filter((n) => n.textContent.includes('跳到忍具'))
    : [];
  check('奖励详情里有跳到忍具的链接', links.length > 0, `${links.length} 个`);
  opened.length = 0;
  links[0].listeners.click[0]({ target: {} });
  check('点它会打开忍具视图并定位到那个忍具',
    opened.length === 1 && opened[0].kind === 'item' &&
    opened[0].params && opened[0].params.itemId !== undefined,
    JSON.stringify(opened[0] || {}));
}

console.log('\n8) 域首页：忍具与奖励各一个入口，强化素材仍是独立行');
{
  const host = renderPanel(null);
  const text = host.textContent;
  check('首页有忍具入口', text.includes('忍具（记录表 + 名表）'), '');
  check('首页有奖励入口', text.includes('奖励表（每关的三个子奖励）'), '');
  check('强化素材名表仍是独立的一行', text.includes('强化素材名表'), '');
  check('页面文本里没有字面星号', !text.includes('**'),
    text.includes('**') ? '还有星号' : '没有');
}

console.log('\n9) 页面文本里没有字面星号（两个视图）');
{
  for (const panel of [{ kind: 'item', id: '忍具', params: {} }, { kind: 'reward', id: '奖励', params: {} }]) {
    const host = renderPanel(panel);
    const text = host.textContent || '';
    check(`${panel.kind} 视图没有字面星号`, !text.includes('**'),
      text.includes('**') ? '还有星号' : '没有');
  }
}

console.log('\n10) 右侧面板卡片化：卡片堆、卡片头、所有卡片同时在 DOM 里');
{
  // --- 忍具视图 ---
  const host = renderPanel({ kind: 'item', id: '忍具', params: {} });
  const detail = panes(host).detail;
  check('忍具视图右侧有卡片堆', cardStacks(detail).length === 1,
    `${cardStacks(detail).length} 个`);
  const labels = cardsOf(detail).map(cardTitle);
  check('忍具视图的卡片就是那三张（依次）',
    JSON.stringify(labels) === JSON.stringify(['名字', '记录字段', '掉落位置']),
    labels.join(' / '));

  // 卡片不互斥：三张卡片的内容**同时**在 DOM 里。
  check('「名字」那张卡片的内容在 DOM 里',
    cardText(detail, '名字').includes('名字（忍具名表）'));
  check('「记录字段」那张卡片的内容同时在 DOM 里',
    cardText(detail, '记录字段').includes('逐字节看'));
  check('「掉落位置」那张卡片的内容同时在 DOM 里',
    cardText(detail, '掉落位置').includes('它在哪几关掉落'));
  check('三张卡片的内容都在（不再互斥）',
    cardText(detail, '名字').includes('名字（忍具名表）')
    && cardText(detail, '记录字段').includes('逐字节看')
    && cardText(detail, '掉落位置').includes('它在哪几关掉落'));

  // --- 奖励视图 ---
  const host2 = renderPanel({ kind: 'reward', id: '奖励', params: {} });
  const detail2 = panes(host2).detail;
  check('奖励视图右侧有卡片堆', cardStacks(detail2).length === 1,
    `${cardStacks(detail2).length} 个`);
  const labels2 = cardsOf(detail2).map(cardTitle);
  check('奖励视图的卡片就是那四张（依次）',
    JSON.stringify(labels2) === JSON.stringify(['金币', '强化点', '等级门槛', '掉落位']),
    labels2.join(' / '));
  for (const want of ['金币', '强化点', '等级门槛', '掉落位']) {
    check(`奖励视图有「${want}」这张卡片`, labels2.includes(want), labels2.join(' / '));
  }

  // 四张卡片的内容同时在 DOM 里
  check('「金币」那张卡片的内容在 DOM 里', byClass(cardByTitle(detail2, '金币') || detail2, 'item-number').length === 1);
  check('「掉落位」那张卡片的内容同时在 DOM 里',
    byClass(cardByTitle(detail2, '掉落位') || detail2, 'grid-slots').length === 1);
  check('「金币」与「掉落位」两张卡片的内容**都在**（不再互斥）',
    byClass(cardByTitle(detail2, '金币') || detail2, 'item-number').length === 1
    && byClass(cardByTitle(detail2, '掉落位') || detail2, 'grid-slots').length === 1);
}

console.log('\n11) 卡片角标：改了哪一类，哪张卡片就亮');
{
  const fresh = ContentPack.fromJSON(packData);
  const freshCtx = makeCtx(fresh);
  const host = renderPanel({ kind: 'reward', id: '奖励', params: {} }, freshCtx);
  const detail = panes(host).detail;
  check('没改过的时候没有角标', cardBadge(detail, '金币') === null,
    `角标 = ${cardBadge(detail, '金币')}`);
  const goldCard = cardByTitle(detail, '金币');
  const cell = goldCard ? byClass(goldCard, 'item-number')[0] : null;
  const input = cell ? cell.descendants().find((n) => n.tagName === 'INPUT') : null;
  check('金币那张卡片有输入框', !!input, input ? `当前值 ${input.value}` : '没有输入框');
  if (input) {
    input.listeners.change[0]({ target: { value: String(Number(input.value) + 1) } });
    check('改了金币以后「金币」那张卡片亮角标', cardBadge(detail, '金币') !== null,
      `角标 = ${cardBadge(detail, '金币')}`);
    check('没动过的「强化点」那张卡片没有角标', cardBadge(detail, '强化点') === null,
      `角标 = ${cardBadge(detail, '强化点')}`);
    check('没动过的「掉落位」那张卡片没有角标', cardBadge(detail, '掉落位') === null,
      `角标 = ${cardBadge(detail, '掉落位')}`);
  }
}

console.log('\n12) 改掉落位的类别 → 那张卡片里的物品下拉跟着换');
{
  const fresh = ContentPack.fromJSON(packData);
  const freshCtx = makeCtx(fresh);
  const host = renderPanel({ kind: 'reward', id: '奖励', params: {} }, freshCtx);
  const detail = panes(host).detail;
  // 卡片会重建（类别变了要整个重画），所以每次都重新找那张卡片。
  const selectsOf = () => {
    const card = cardByTitle(detail, '掉落位');
    const table = card ? byClass(card, 'grid-slots')[0] : null;
    return table ? table.descendants().filter((n) => n.tagName === 'SELECT') : [];
  };
  const list = selectsOf();
  const catSelect = list[0];
  const itemSelect = list[1];
  check('掉落位第一个槽有类别与物品两个下拉', !!catSelect && !!itemSelect, `${list.length} 个下拉`);
  if (catSelect && itemSelect) {
    // 类别 0 = 忍具（ninjutsu_names）；换成 1 = 强化素材（material_names）。
    const before = itemSelect.children.length;
    catSelect.listeners.change[0]({ target: { value: '1' } });
    const after = selectsOf()[1];
    const materialTable = fresh.textTable('material_names');
    check('改了类别以后物品下拉的候选换成了新类别那张名字表',
      !!after && after.children.length === materialTable.records.length
      && after.children.length !== before,
      `${before} → ${after ? after.children.length : '?'} 个候选（强化素材名表 ${materialTable.records.length} 条）`);
  }
}

console.log('\n13) 忍具记录字段：改一格能走完整条写回通路（不报错）');
{
  // 这一条断的是「改完一格不炸」：记录字段的写回通路要一路走到卡片重建。
  const fresh = ContentPack.fromJSON(packData);
  const freshCtx = makeCtx(fresh);
  const host = renderPanel({ kind: 'item', id: '忍具', params: {} }, freshCtx);
  const detail = panes(host).detail;
  const bytesCard = cardByTitle(detail, '记录字段');
  const inputs = bytesCard ? bytesCard.descendants().filter((n) => n.tagName === 'INPUT') : [];
  // 「保留」那几格是只读的（disabled），挑一个能改的。
  const input = inputs.find((n) => n.getAttribute('disabled') === null
    && /^\d+$/.test(String(n.value)) && Number(n.value) < 200);
  check('「记录字段」那张卡片里有一个能改的输入框', !!input,
    input ? `当前值 ${input.value}` : `只有 ${inputs.length} 个输入框`);
  if (input) {
    const before = fresh.changedCount();
    let error = null;
    try {
      input.listeners.change[0]({ target: { value: String(Number(input.value) + 1) } });
    } catch (err) {
      error = err;
    }
    check('改这一格不报错（写回通路是完整的）', !error,
      error ? String(error.message) : '');
    check('改这一格后改动计数 +1', fresh.changedCount() === before + 1,
      `${before} → ${fresh.changedCount()}`);
    check('改完之后三张卡片的内容还在 DOM 里',
      cardsOf(detail).length === 3
      && cardText(detail, '记录字段').includes('逐字节看')
      && cardText(detail, '掉落位置').includes('它在哪几关掉落'));
  }
}

console.log(failures ? `\n${failures} 项未通过` : '\n全部通过');
process.exit(failures ? 1 : 0);
