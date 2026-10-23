// 道具域的统一编辑视图：忍具与奖励。
//
// 用户原话：「光一个任务表就分了索引、标题、说明、提示表来呈现，过于细碎繁琐，
// 应当按统一的任务编辑来呈现，然后按索引表列出，将其他表的内容都作为字段呈现。
// 其他模块也要做同样思路的修改」
//
// 道具域有两个「主对象」：
//
//   忍具 = 记录表的一行 + 忍具名表里的名字 + 它出现在哪里
//          （奖励表里哪几关掉它 + 哪些角色装备它）
//   奖励 = 奖励表的一行 = 某一关的某一个子奖励
//
// ROM 里它们分开放：忍具本体在道具/忍具记录表（16 字节），名字在忍具名表，
// 掉落关系在奖励表的 8 个掉落位里。存储怎么拆是 ROM 的事，编辑时不该拆。
//
// 所以：
//   左边列表 = 记录表 / 奖励表的每一条（一行 = 一个忍具 / 一条奖励）
//   右边详情 = 这个忍具的名字、它的记录字段（16 字节，每格都有原生代码依据）、它在哪几关掉落
//              这条奖励的金币 / 强化点 / 等级门槛与 8 个掉落位
//
// 写回仍然只走内容包已有的通路（pack.setValue / pack.setText），
// 语义只从内容包取（记录表的字段表、奖励表的 enum 与 relation、
// 任务索引表给出的关卡归属）。

import { el, clear, toast, clickableArea } from '../ui.js';
import { base64ToBytes, bytesToBase64 } from '../bytes.js';
import { fieldControl, enumLabel } from '../fields.js';
import { arraysIn, renderArrayTable } from '../slots.js';
import { missionIndexOwners, ownerLabel } from '../xref.js';
import { idSpace } from '../idspace.js';
import { splitPane } from '../split.js';
import { CardStack } from '../cards.js';
import { backButton, summaryTable } from './common.js';
import { characterName } from './character.js';

// ---------------------------------------------------------------------------
// 从内容包读出来的事实
// ---------------------------------------------------------------------------

/** 这条记录现在的字节和原始字节不一样吗（改了又改回来不算改动）。 */
export function recordChanged(pack, structure, record) {
  if (!structure || !record) return false;
  const bytes = pack.recordBytes(structure, record);
  const raw = base64ToBytes(record.raw || '');
  return bytesToBase64(bytes) !== bytesToBase64(raw);
}

/** 这条文本现在和原文不一样吗。 */
export function textChanged(table, id) {
  const record = table && (table.records || [])[id];
  return !!(record && record.text !== undefined && record.text !== record.original_text);
}

/**
 * 这个**字段**的字节现在和原版不一样吗（改了又改回来不算改动）。
 *
 * 判定口径与通用表格编辑器同一套：拿重新编码后的字节和原始字节比，
 * 这里只看这个字段占的那几个字节 —— 所以一页里改了金币，
 * 只有「金币」那一页亮角标，别的一页不亮。
 */
export function fieldChanged(pack, structure, record, field) {
  if (!pack || !structure || !record || !field) return false;
  const offset = field.offset;
  if (offset === undefined || offset === null) return false;
  const size = field.size || 1;
  const now = pack.recordBytes(structure, record);
  const raw = base64ToBytes(record.raw || '');
  if (now.length < offset + size || raw.length < offset + size) return false;
  for (let i = 0; i < size; i += 1) {
    if (now[offset + i] !== raw[offset + i]) return true;
  }
  return false;
}

/**
 * 忍具名表：与道具/忍具记录表**同一个 id 空间**的那张文本表。
 *
 * 记录表自己写着 id_relation（记录下标就是那张表的 id），
 * 但反方向（名表 → 记录表）要靠 idSpace 把整个空间列出来。
 */
export function itemNameTable(pack) {
  const record = pack.structure('item_record');
  if (!record) return null;
  for (const id of idSpace(pack, record.id)) {
    const table = pack.textTable(id);
    if (table) return table;
  }
  return null;
}

/** 忍具的名字（名表里那条）。 */
export function itemName(names, id) {
  const record = names && (names.records || [])[id];
  return record && record.text ? record.text : '';
}

/** 奖励表里的掉落位数组（array="slots"）。 */
export function rewardSlotArray(rewards) {
  const arrays = arraysIn(rewards ? rewards.fields || [] : []);
  return arrays.find((a) => a.name === 'slots') || null;
}

/**
 * 奖励表一行的几个数字字段（金币 / 强化点 / 等级门槛）。
 *
 * 它们是这张表里唯一**不是重复槽**的定宽数字字段 —— 语义取自内容包的
 * 字段表，不在这里写死字段名。
 */
export function rewardNumberFields(rewards) {
  return ((rewards && rewards.fields) || [])
    .filter((f) => !f.array && (f.type === 'u16' || f.type === 's16'));
}

/**
 * 掉落位里「物品 id 等于几」表示列表结束。
 *
 * 内容包把这个语义写在字段说明里（「该类别的名称表下标；0 = 列表结束」），
 * 所以这里从说明里读，不在代码里写死一个数字。
 *
 * 这一条很重要：0 既是「列表结束」，也是忍具名表里的占位下标。
 * 当成真的掉落，占位忍具会显示「掉了 568 次」—— 那是假的。
 */
export function dropEndMarker(field) {
  const desc = String((field && field.desc) || '');
  const hit = desc.match(/(\d+)\s*=\s*列表结束/);
  return hit ? Number(hit[1]) : null;
}

/**
 * 掉落位里，哪一个类别值表示这张名字表。
 *
 * 类别 → 名字表的对应是内容包写在 relation.categories 里的（ROM 自带的
 * 4 槽指针表 0x0859F5E0 证明了它），所以这里从内容包读。
 */
export function categoryForTable(rewards, tableId) {
  const array = rewardSlotArray(rewards);
  if (!array) return null;
  for (const row of array.rows.values()) {
    const idField = Object.values(row)
      .find((f) => f.relation && f.relation.kind === 'by_category');
    if (!idField) continue;
    const categories = idField.relation.categories || {};
    for (const [value, id] of Object.entries(categories)) {
      if (id === tableId) return Number(value);
    }
    break;
  }
  return null;
}

/**
 * 奖励表里所有**类别是忍具**的掉落位（非零、非「列表结束」）。
 *
 * 这是一次全表扫描 —— 94 个忍具逐个查会扫 94 遍，
 * 而奖励表只有 112 行 × 8 个掉落位，一次扫完再分桶更快。
 */
export function itemDropSlots(pack) {
  const rewards = pack.structure('reward_table');
  const names = itemNameTable(pack);
  if (!rewards || !names) return [];
  const array = rewardSlotArray(rewards);
  if (!array) return [];
  const category = categoryForTable(rewards, names.id);
  if (category === null) return [];

  const out = [];
  for (const record of rewards.records || []) {
    const values = record.values || {};
    for (const [index, row] of array.rows) {
      const fields = Object.values(row);
      const catField = fields.find((f) => f.item === 'category');
      const idField = fields.find((f) => f.relation && f.relation.kind === 'by_category');
      if (!catField || !idField) continue;
      if (values[catField.key] !== category) continue;
      const itemId = values[idField.key];
      // 列表结束的那一格不是掉落；0 是占位。
      const end = dropEndMarker(idField);
      if (end !== null && itemId === end) continue;
      if (!itemId) continue;
      out.push({ record, index, categoryField: catField, itemField: idField, itemId });
    }
  }
  return out;
}

/**
 * 奖励表里所有**引用了这个忍具**的行。
 *
 * 掉落位是「类别 + 物品 id」：类别决定这个 id 该去哪张名字表查名字。
 * 哪一类表示忍具，从内容包的 relation.categories 里读，不写死。
 */
export function rewardRowsForItem(pack, itemId) {
  return itemDropSlots(pack)
    .filter((row) => row.itemId === itemId)
    .map((row) => ({
      record: row.record,
      index: row.index,
      categoryField: row.categoryField,
      itemField: row.itemField,
    }));
}

/**
 * 会作为奖励掉出来的忍具（id → 掉落的处数）。
 *
 * 用来说明「为什么大多数忍具没有掉落」——
 * 94 个忍具里只有 8 个真的会被奖励发出去，
 * 其余的**不是数据缺失**，是原版就这么设计的。
 */
export function droppedItemCounts(pack) {
  const counts = new Map();
  for (const row of itemDropSlots(pack)) {
    counts.set(row.itemId, (counts.get(row.itemId) || 0) + 1);
  }
  return counts;
}

/**
 * 谁装备着这个忍具（角色定义表的道具槽）。
 *
 * 依据内容包里字段的 relation：relation.table 指到忍具名表的那一格，
 * 就是「这个角色带着这个忍具」。不按字段名硬找。
 *
 * 0 要排除两次：忍具名表第 0 条是占位（不是一个真的忍具），
 * 道具槽里的 0 是**空槽**（字段说明写着「0 = 空」）——
 * 不排除的话，每个角色的 9 个空槽都会算成「装备了 0 号忍具」。
 */
export function characterSlotsForItem(pack, itemId) {
  if (!itemId) return [];
  const chars = pack.structure('character_template');
  const names = itemNameTable(pack);
  if (!chars || !names) return [];
  const slots = (chars.fields || []).filter((f) =>
    f.relation && f.relation.table === names.id && f.item === 'id');
  const out = [];
  for (const record of chars.records || []) {
    const values = record.values || {};
    for (const field of slots) {
      const value = values[field.key];
      if (!value || value !== itemId) continue;
      out.push({ record, field });
    }
  }
  return out;
}

/** 这一条奖励掉的忍具（类别是忍具、且不是「列表结束」的那几格）。 */
export function rewardDropsOfItem(pack, record) {
  const rewards = pack.structure('reward_table');
  const names = itemNameTable(pack);
  if (!rewards || !names || !record) return [];
  const array = rewardSlotArray(rewards);
  if (!array) return [];
  const category = categoryForTable(rewards, names.id);
  if (category === null) return [];
  const values = record.values || {};
  const out = [];
  for (const [index, row] of array.rows) {
    const fields = Object.values(row);
    const catField = fields.find((f) => f.item === 'category');
    const idField = fields.find((f) => f.relation && f.relation.kind === 'by_category');
    if (!catField || !idField) continue;
    if (values[catField.key] !== category) continue;
    const end = dropEndMarker(idField);
    if (end !== null && values[idField.key] === end) continue;
    out.push({ index, itemId: values[idField.key] });
  }
  return out;
}

/** 这一条奖励是哪几关给的（任务索引表说的，不是算出来的）。 */
export function rewardOwnerText(owners, id) {
  const list = owners.get(id) || [];
  if (!list.length) return '没有被任何关卡引用';
  return list.map((o) => ownerLabel(o)).join('、');
}

// ---------------------------------------------------------------------------
// 忍具视图
// ---------------------------------------------------------------------------

// 面板参数在 hash 往返里会丢（#items/reward 记不下第几条），
// 所以两个视图各自记住上一次看的条目 —— 跳转才不会跳回默认那条。
let lastItemId = null;
let lastRewardId = null;

export function renderItem(container, ctx, params = {}) {
  new ItemView(ctx, params).render(container);
}

class ItemView {
  constructor(ctx, params) {
    this.ctx = ctx;
    this.pack = ctx.pack;
    this.records = this.pack.structure('item_record');
    this.names = itemNameTable(this.pack);
    this.id = this.pickId(params);
    // 「刷新器」按卡片分桶：卡片全都同时在页面上，每张卡片重建时
    // 只清自己那一桶（见 cardContent）。
    this.refreshers = new Map();
    this.currentCard = null;
    this.cards = null;
    this.cardsMounted = false;
  }

  pickId(params) {
    const list = (this.records && this.records.records) || [];
    const wanted = params && params.itemId !== undefined && params.itemId !== null
      ? Number(params.itemId) : null;
    if (wanted !== null && list.some((r) => r.id === wanted)) {
      lastItemId = wanted;
      return wanted;
    }
    // hash 往返丢掉了参数，就用上一次看的那个。
    if (lastItemId !== null && list.some((r) => r.id === lastItemId)) return lastItemId;
    // 默认落在**真的掉在某一关**的那个忍具上 —— 下标 0 在名表里是占位。
    const drops = this.dropIndex();
    for (const [id, rows] of drops) return id;
    return list.length ? list[0].id : 0;
  }

  /** 每个忍具掉在哪几条奖励里（按忍具 id 索引）。 */
  dropIndex() {
    if (this.drops) return this.drops;
    const map = new Map();
    for (const record of (this.records && this.records.records) || []) {
      const rows = rewardRowsForItem(this.pack, record.id);
      if (rows.length) map.set(record.id, rows);
    }
    this.drops = map;
    return map;
  }

  /** 记录表里**每一个**字段（2026-10-22 起这 16 格都有名字与依据了）。 */
  recordFields() {
    return ((this.records && this.records.fields) || []).filter((f) => f.type !== 'hex');
  }

  /** 字段控件的上下文：改完一个字段要重画列表（改动角标）并刷新卡片角标。 */
  fieldCtx() {
    const ctx = this.ctx;
    return {
      pack: ctx.pack,
      onChange: ctx.onChange,
      onJump: ctx.onJump,
      registerRefresh: (fn) => this.addRefresher(fn),
      onCommit: () => {
        this.runRefreshers();
        this.renderList();
        this.refreshCards();
      },
    };
  }

  render(container) {
    clear(container);
    const ctx = this.ctx;
    container.appendChild(el('div', { style: { marginBottom: '12px' } }, [
      backButton(ctx, '道具'),
    ]));
    container.appendChild(el('div', { class: 'panel-head' }, [
      el('div', {}, [
        el('h2', { text: '忍具' }),
        el('div', { class: 'panel-sub' }, [
          el('span', { text: '道具/忍具记录表 + 忍具名表 —— 合成一个忍具来改' }),
          el('span', { text: `${(this.records ? this.records.entry_count : 0)} 个忍具` }),
        ]),
      ]),
    ]));
    container.appendChild(el('p', { class: 'section-note', text:
      '左边按道具/忍具记录表列出（一行 = 一个忍具）；' +
      '右边是三张卡片：名字（忍具名表）、记录字段（记录表那 16 个字节，每格都有原生代码依据）、' +
      '出现在哪里（奖励表里掉它的地方 + 装备着它的角色，点一下就跳过去 —— ' +
      '掉落关系改在奖励那一侧，装备关系改在角色那一侧）。' +
      '三张卡片都在页面上，往下滚就是全部。' }));

    this.listWrap = el('div', { class: 'table-wrap' });
    this.detailWrap = el('div', { class: 'detail-panel' });
    // 头部每次重画；卡片堆常驻在另一个容器里 —— clear() 不到它，
    // 所以换忍具时卡片还是那几张。
    this.detailHead = el('div', { class: 'detail-head-area' });
    this.detailCards = el('div', { class: 'detail-cards' });
    this.detailWrap.appendChild(this.detailHead);
    this.detailWrap.appendChild(this.detailCards);
    container.appendChild(splitPane(this.listWrap, this.detailWrap, {
      key: 'editor.item',
      wide: true,
    }));
    this.cards = new CardStack([
      {
        id: 'name',
        label: '名字',
        hint: '忍具名表里的那一条文本',
        badge: () => this.nameBadge(),
        render: () => this.cardContent('name', () => this.renderName(this.currentRecord())),
      },
      {
        id: 'bytes',
        label: '记录字段',
        hint: '记录表那 16 个字节：每一格都标了它在 ROM 里的作用'
          + '（原生代码不读的标「保留」，只到取值分布的标「（推定）」）',
        badge: () => this.bytesBadge(),
        render: () => this.cardContent('bytes', () => this.renderRecord(this.currentRecord())),
      },
      {
        id: 'drops',
        label: '出现在哪里',
        hint: '奖励表里掉它的地方 + 装备着它的角色（两个地方的改动都在这一页里数）',
        badge: () => this.dropsBadge(),
        render: () => this.cardContent('drops', () => this.renderDrops(this.currentRecord())),
      },
    ], { pack: this.pack });
    this.renderList();
    this.renderDetail();
  }

  /** 左边：记录表的每一条（一个忍具）。 */
  renderList() {
    const wrap = this.listWrap;
    clear(wrap);
    if (!this.records) {
      wrap.appendChild(el('div', { class: 'empty', text: '内容包里没有道具/忍具记录表。' }));
      return;
    }
    const table = el('table', { class: 'grid' });
    table.appendChild(el('thead', {}, [el('tr', {}, [
      el('th', { class: 'col-id', text: '#' }),
      el('th', { text: '忍具名' }),
      el('th', { class: 'col-num', text: '掉落' }),
      el('th', { class: 'col-num', text: '装备' }),
      el('th', { class: 'col-num', text: '已改' }),
    ])]));
    const body = el('tbody');
    const drops = this.dropIndex();
    for (const record of this.records.records || []) {
      const name = itemName(this.names, record.id);
      const dropRows = drops.get(record.id) || [];
      const equipped = characterSlotsForItem(this.pack, record.id);
      let changes = 0;
      if (recordChanged(this.pack, this.records, record)) changes += 1;
      if (textChanged(this.names, record.id)) changes += 1;
      body.appendChild(el('tr', {
        class: (this.id === record.id ? 'selected ' : '') + (changes ? 'changed' : ''),
        onclick: () => {
          this.id = record.id;
          lastItemId = record.id;
          this.renderList();
          this.renderDetail();
        },
      }, [
        el('td', { class: 'col-id', text: String(record.id) }),
        el('td', { class: 'text-cell', text: name || '（空）' }),
        el('td', { class: 'col-num', text: dropRows.length ? `${dropRows.length} 处` : '—' }),
        el('td', { class: 'col-num', text: equipped.length ? `${equipped.length} 人` : '—' }),
        el('td', { class: 'col-num', text: changes ? `● ${changes}` : '—' }),
      ]));
    }
    table.appendChild(body);
    wrap.appendChild(table);
  }

  /** 现在看的那条记录。 */
  currentRecord() {
    return ((this.records && this.records.records) || [])
      .find((r) => r.id === this.id) || null;
  }

  /** 卡片堆常驻在 detailCards 里 —— 它自己管内容，这里只管挂不挂。 */
  mountCards() {
    if (this.cardsMounted) return;
    this.detailCards.appendChild(this.cards.element);
    this.cardsMounted = true;
  }

  /** 找不到记录时把卡片收起来（下次有记录了再挂回去）。 */
  unmountCards() {
    if (!this.cardsMounted) return;
    clear(this.detailCards);
    this.cardsMounted = false;
  }

  /** 右边：这个忍具。头部在外面，内容按类分成卡片。 */
  renderDetail() {
    const record = this.currentRecord();
    clear(this.detailHead);
    if (!record) {
      this.detailHead.appendChild(el('div', { class: 'empty', text: '找不到这个忍具。' }));
      this.unmountCards();
      return;
    }
    const name = itemName(this.names, record.id);
    const fields = this.recordFields();
    const bytes = fields.length;
    const reserved = fields.filter((f) => f.not_read).length;

    this.detailHead.appendChild(el('div', { class: 'detail-head' }, [
      el('h3', { text: name ? `${name}（#${record.id}）` : `忍具 #${record.id}` }),
    ]));
    this.detailHead.appendChild(el('div', { class: 'detail-sub' }, [
      el('span', { text: `记录表第 ${record.id} 条` }),
      el('span', { text: this.names ? `名表第 ${record.id} 条` : '没有忍具名表' }),
      el('span', { text: `${bytes} 字节 · ${bytes - reserved} 格有原生代码依据，${reserved} 格保留` }),
    ]));

    this.mountCards();
    this.cards.refresh();
  }

  /**
   * 一张卡片的内容。
   *
   * 卡片全都同时在页面上，所以「刷新器」（改完一格要重画说明行的回调）
   * 是所有卡片合起来的一份 —— 但每张卡片各管各的一桶：
   * 这张卡片重建时只清它自己那一桶。
   */
  cardContent(id, build) {
    this.currentCard = id;
    this.refreshers.set(id, []);
    return build();
  }

  /** 登记一个「改完要重画」的回调（归到当前这张卡片名下）。 */
  addRefresher(fn) {
    const id = this.currentCard;
    if (!id) return;
    const bucket = this.refreshers.get(id) || [];
    bucket.push(fn);
    this.refreshers.set(id, bucket);
  }

  /** 跑一遍所有卡片的刷新器（改完一格，说明行与「已改」标记要跟上）。 */
  runRefreshers() {
    for (const bucket of this.refreshers.values()) {
      for (const fn of bucket) fn();
    }
  }

  /** 重建全部卡片的内容与角标。 */
  refreshCards() {
    if (this.cards) this.cards.refresh();
  }

  /** 名字这一类改了几处（按字节判定：文本与原文不同）。 */
  nameBadge() {
    const record = this.currentRecord();
    if (!record) return null;
    return textChanged(this.names, record.id) ? 1 : null;
  }

  /** 记录字段这一类改了几处（按字节判定：记录字节与原版不同）。 */
  bytesBadge() {
    const record = this.currentRecord();
    if (!record) return null;
    return recordChanged(this.pack, this.records, record) ? 1 : null;
  }

  /**
   * 「出现在哪里」这一类：引用它的那些奖励行 / 那些角色里有几条被改过。
   *
   * 两个地方都算 —— 这一页摆的就是它们两个。
   */
  dropsBadge() {
    const record = this.currentRecord();
    if (!record) return null;
    const rewards = this.pack.structure('reward_table');
    if (!rewards) return null;
    const changed = new Set(
      this.pack.changedStructureRecords(rewards).map((r) => r.rom_offset));
    let n = 0;
    for (const row of this.dropIndex().get(record.id) || []) {
      if (changed.has(row.record.rom_offset)) n += 1;
    }
    const chars = this.pack.structure('character_template');
    if (chars) {
      const changedChars = new Set(
        this.pack.changedStructureRecords(chars).map((r) => r.rom_offset));
      for (const slot of characterSlotsForItem(this.pack, record.id)) {
        if (changedChars.has(slot.record.rom_offset)) n += 1;
      }
    }
    return n || null;
  }

  /** 名字（忍具名表里的那条文本）。 */
  renderName(record) {
    const ctx = this.ctx;
    const block = el('div', { class: 'item-block' });
    if (!record) {
      block.appendChild(el('div', { class: 'stat-hint', text: '找不到这个忍具。' }));
      return block;
    }
    block.appendChild(el('div', { class: 'field-label' }, [
      el('span', { text: '名字（忍具名表）' }),
    ]));
    const textRecord = this.names && (this.names.records || [])[record.id];
    if (!textRecord) {
      block.appendChild(el('div', { class: 'stat-hint', text: '名表里没有这一条。' }));
      return block;
    }
    const preview = el('div', { class: 'field-hint' });
    const update = () => {
      const bytes = ctx.pack.font.encodedLength(textRecord.text || '');
      preview.textContent = `${textRecord.text || '（空）'} · ${bytes} 字节`;
    };
    update();
    const input = el('input', {
      class: 'text-input-inline',
      type: 'text',
      spellcheck: 'false',
      value: textRecord.text || '',
      onchange: (e) => {
        const value = e.target.value;
        const missing = ctx.pack.font.missingCharacters(value);
        if (missing.length) {
          toast(`字库里没有这些字：${missing.join(' ')}`, 'error');
          e.target.value = textRecord.text || '';
          return;
        }
        ctx.pack.setText(this.names, textRecord, value);
        ctx.onChange();
        this.renderList();
        this.renderDetail();
        toast(`已改写${this.names.label} #${record.id}`);
      },
    });
    block.appendChild(input);
    block.appendChild(preview);
    if (this.names && this.names.note) {
      block.appendChild(el('div', { class: 'stat-hint', text: this.names.note }));
    }
    const shared = (textRecord.shared_with || []).length + 1;
    if (shared > 1) {
      block.appendChild(el('div', {
        class: 'item-note',
        text: `这段字被 ${shared} 处共用，改一处会一起变`,
      }));
    }
    block.appendChild(el('div', { class: 'field-link' }, [
      el('span', {
        class: 'xref-link',
        text: `跳到${this.names.label} #${record.id} →`,
        onclick: () => ctx.onJump({
          module: this.names.module,
          kind: 'text',
          id: this.names.id,
          recordId: record.id,
          label: this.names.label,
        }),
      }),
    ]));
    return block;
  }

  /**
   * 这个忍具自己的记录：16 个字节，每一格都有原生代码依据。
   *
   * 2026-10-22 之前这里是一整块十六进制输入框，理由是「这 16 字节没有任何一处
   * 证明过字段含义」。现在逐字节普查过了（tools/item_record_fields.py，
   * 证据 notes/evidence/item-record-fields-20261022.md）：
   * 7 个原生读者分别读哪些格、读成什么宽度都有指令级依据；
   * 原生代码根本不读的三格（+0x01 / +0x0E / +0x0F）标「保留」并降级为只读。
   */
  renderRecord(record) {
    const ctx = this.ctx;
    const fields = this.recordFields();
    const block = el('div', { class: 'item-block' });
    if (!record) {
      block.appendChild(el('div', { class: 'stat-hint', text: '找不到这个忍具。' }));
      return block;
    }
    const values = record.values || {};

    block.appendChild(el('div', { class: 'field-label' }, [
      el('span', { text: '这个忍具的记录（16 字节）' }),
    ]));
    block.appendChild(el('p', { class: 'section-note', text:
      '每一格都标了它在 ROM 里的作用：被原生代码读到的格子写明是哪段代码、'
      + '读成什么宽度；原生代码不读的写「保留」并只读；'
      + '只到取值分布的，业务名带「（推定）」。改完会原样写回 ROM。' }));

    // 每个字段一行：名字 + 偏移 + 控件 + 说明（沿用通用结构编辑器的 .field 排版）
    const grid = el('div', { class: 'field-list' });
    for (const f of fields) {
      const wrapper = el('div', { class: 'field' });
      const label = el('div', { class: 'field-label' }, [
        el('span', { text: f.label || f.key }),
        el('span', { class: 'field-offset', text: `+0x${(f.offset || 0).toString(16).toUpperCase().padStart(2, '0')}` }),
      ]);
      wrapper.appendChild(label);

      if (f.not_read) {
        // 原生代码不读这一格：只读展示，别给输入框（改了也没有效果）。
        wrapper.appendChild(el('div', { class: 'field-hint', text:
          `当前值 ${String(values[f.key] ?? '—')} —— 原生代码不读这一格，只读。` }));
      } else {
        const { node } = fieldControl(this.fieldCtx(), this.records, record, f);
        wrapper.appendChild(node);
      }
      if (f.desc) wrapper.appendChild(el('div', { class: 'field-hint', text: f.desc }));
      grid.appendChild(wrapper);
    }
    block.appendChild(grid);

    // 原始字节还在这儿 —— 逐字节对照用
    const rows = { head: ['字段', '偏移', '当前值'], body: [] };
    for (const f of fields) {
      rows.body.push([
        f.label || f.key,
        `+0x${(f.offset || 0).toString(16).toUpperCase().padStart(2, '0')}`,
        String(values[f.key] ?? '').toUpperCase(),
      ]);
    }
    block.appendChild(el('details', { class: 'item-bytes' }, [
      el('summary', { text: `逐字节看（${fields.length} 字节）` }),
      summaryTable(rows),
    ]));
    return block;
  }

  /**
   * 它在 ROM 里被谁引用：**奖励掉落** + **角色装备**。
   *
   * 以前这一页只有掉落那一半，于是 94 个忍具里有 86 个显示
   * 「奖励表里没有哪一行掉这个忍具」—— 读起来像数据坏了，
   * 其实原版就是这么设计的（只有 8 个忍具会被奖励发出去）。
   * 现在把「谁装备着它」也摆出来：一个忍具的全部出现位置一目了然。
   */
  renderDrops(record) {
    const ctx = this.ctx;
    const block = el('div', { class: 'item-block' });
    if (!record) {
      block.appendChild(el('div', { class: 'stat-hint', text: '找不到这个忍具。' }));
      return block;
    }

    // --- 一、奖励掉落 ------------------------------------------------------
    block.appendChild(el('div', { class: 'field-label' }, [
      el('span', { text: '它在哪几关掉落' }),
    ]));
    const rows = this.dropIndex().get(record.id) || [];
    if (!rows.length) {
      block.appendChild(this.noDropsNote(record));
    } else {
      const owners = missionIndexOwners(this.pack);
      const table = el('table', { class: 'grid' });
      table.appendChild(el('thead', {}, [el('tr', {}, [
        el('th', { class: 'col-id', text: '槽' }),
        el('th', { text: '第几关' }),
        el('th', { text: '类别' }),
        el('th', { text: '物品 id' }),
        el('th', { text: '跳过去' }),
      ])]));
      const body = el('tbody');
      for (const row of rows) {
        const values = row.record.values || {};
        const category = enumLabel(row.categoryField, values[row.categoryField.key]);
        // 整行的动作 = 「跳到这条奖励」；另一个链接（在奖励表里打开）保留自己的动作。
        const openReward = () => {
          // 先记住落点：hash 往返会把面板参数冲掉。
          lastRewardId = row.record.id;
          ctx.openPanel('reward', '奖励', { recordId: row.record.id });
        };
        const tr = el('tr', {}, [
          el('td', { class: 'col-id', text: String(row.index + 1) }),
          el('td', { class: 'text-cell', text: rewardOwnerText(owners, row.record.id) }),
          el('td', { text: category === null ? String(values[row.categoryField.key]) : category }),
          el('td', { text: String(values[row.itemField.key]) }),
          el('td', {}, [
            el('span', {
              class: 'xref-link',
              text: '跳到这条奖励 →',
              onclick: openReward,
            }),
            el('span', {
              class: 'xref-link',
              text: '在奖励表里打开 →',
              onclick: () => ctx.onJump({
                module: 'items',
                kind: 'structure',
                id: 'reward_table',
                recordId: row.record.id,
                label: '奖励表',
              }),
            }),
          ]),
        ]);
        // 整行都能跳到这条奖励 —— 不用瞄准那个链接。
        clickableArea(tr, openReward);
        body.appendChild(tr);
      }
      table.appendChild(body);
      block.appendChild(el('div', { class: 'table-wrap' }, [table]));
      block.appendChild(el('div', {
        class: 'item-note',
        text: '掉落关系改在奖励那一侧：掉落位与金币都改在奖励表里。',
      }));
    }

    // --- 二、角色装备 ------------------------------------------------------
    block.appendChild(el('div', { class: 'field-label' }, [
      el('span', { text: '谁装备着它' }),
    ]));
    const equipped = characterSlotsForItem(this.pack, record.id);
    if (!equipped.length) {
      block.appendChild(el('div', {
        class: 'stat-hint',
        text: '没有角色带着它 —— 角色定义表的 9 个道具槽里没有它。',
      }));
    } else {
      const chars = this.pack.structure('character_template');
      const table = el('table', { class: 'grid' });
      table.appendChild(el('thead', {}, [el('tr', {}, [
        el('th', { text: '角色' }),
        el('th', { class: 'col-id', text: '道具槽' }),
        el('th', { text: '跳过去' }),
      ])]));
      const body = el('tbody');
      for (const slot of equipped) {
        const openCharacter = () => ctx.onJump({
          module: 'characters',
          kind: 'character',
          id: '角色',
          params: { character: slot.record.id },
          label: '角色',
        });
        const tr = el('tr', {}, [
          el('td', { class: 'text-cell', text: characterName(this.pack, chars, slot.record) }),
          el('td', { class: 'col-id', text: slot.field.label || slot.field.key }),
          el('td', {}, [
            el('span', {
              class: 'xref-link',
              text: '跳到这个角色 →',
              onclick: openCharacter,
            }),
          ]),
        ]);
        clickableArea(tr, openCharacter);
        body.appendChild(tr);
      }
      table.appendChild(body);
      block.appendChild(el('div', { class: 'table-wrap' }, [table]));
      block.appendChild(el('div', {
        class: 'item-note',
        text: '装备关系改在角色那一侧：道具槽改在角色定义表里。',
      }));
    }
    return block;
  }

  /**
   * 「它不掉在任何奖励里」这件事要说清楚**为什么**、以及**要做什么**。
   *
   * 以前这里只丢一句「奖励表里没有哪一行掉这个忍具 —— 它的 id 没出现在
   * 任何掉落位里」，读起来像数据坏了；其实 94 个忍具里只有 8 个会被
   * 奖励发出去，其余 86 个原版就是这么设计的。
   */
  noDropsNote(record) {
    const counts = this.droppedCounts();
    const total = ((this.records && this.records.records) || []).length;
    const names = [];
    for (const [id, n] of [...counts.entries()].sort((a, b) => a[0] - b[0])) {
      const name = itemName(this.names, id);
      names.push(name ? `${name}（${n} 处）` : `#${id}（${n} 处）`);
    }
    const equipped = characterSlotsForItem(this.pack, record.id).length;
    const parts = [
      '奖励表里没有任何一条奖励掉它。',
      `${total} 个忍具里只有 ${counts.size} 个会作为奖励掉出来：`
        + `${names.join('、')} —— 其余的原版就不作为奖励下发，不是数据缺失。`,
    ];
    if (!equipped) {
      parts.push('它也没有被任何角色装备 —— 整个内容包里没有一处引用它。');
    }
    parts.push('要让它掉出来：到「奖励」那一侧，在某条奖励的掉落位里选它。');
    return el('div', { class: 'rule-note rule-warn' }, [
      el('span', { class: 'rule-title', text: '原版没这么发' }),
      el('span', { text: parts.join('') }),
    ]);
  }

  /** 会作为奖励掉出来的那些忍具（id → 处数）。 */
  droppedCounts() {
    if (this.drops) return this.drops;
    this.drops = droppedItemCounts(this.pack);
    return this.drops;
  }
}

// ---------------------------------------------------------------------------
// 奖励视图
// ---------------------------------------------------------------------------

export function renderReward(container, ctx, params = {}) {
  new RewardView(ctx, params).render(container);
}

class RewardView {
  constructor(ctx, params) {
    this.ctx = ctx;
    this.pack = ctx.pack;
    this.rewards = this.pack.structure('reward_table');
    this.owners = missionIndexOwners(this.pack);
    this.numbers = rewardNumberFields(this.rewards);
    this.goldField = this.numbers[0] || null;
    this.id = this.pickId(params);
    // 「刷新器」按卡片分桶：卡片全都同时在页面上，每张卡片重建时
    // 只清自己那一桶（见 cardContent）。
    this.refreshers = new Map();
    this.currentCard = null;
    this.cards = null;
    this.cardsMounted = false;
  }

  pickId(params) {
    const list = (this.rewards && this.rewards.records) || [];
    const wanted = params && params.recordId !== undefined && params.recordId !== null
      ? Number(params.recordId) : null;
    if (wanted !== null && list.some((r) => r.id === wanted)) {
      lastRewardId = wanted;
      return wanted;
    }
    // hash 往返丢掉了参数，就用上一次看的那个。
    if (lastRewardId !== null && list.some((r) => r.id === lastRewardId)) return lastRewardId;
    // 默认落在**真的被某一关用着**的那一条上。
    for (const record of list) {
      if ((this.owners.get(record.id) || []).length) return record.id;
    }
    return list.length ? list[0].id : 0;
  }

  render(container) {
    clear(container);
    const ctx = this.ctx;
    container.appendChild(el('div', { style: { marginBottom: '12px' } }, [
      backButton(ctx, '道具'),
    ]));
    container.appendChild(el('div', { class: 'panel-head' }, [
      el('div', {}, [
        el('h2', { text: '奖励' }),
        el('div', { class: 'panel-sub' }, [
          el('span', { text: '奖励表 —— 一行 = 某一关的某一个子奖励' }),
          el('span', { text: `${(this.rewards ? this.rewards.entry_count : 0)} 条奖励` }),
        ]),
      ]),
    ]));
    container.appendChild(el('p', { class: 'section-note', text:
      '左边按奖励表列出（一行 = 一条奖励）；' +
      '右边是四张卡片：金币 / 强化点 / 等级门槛各一张，掉落位（类别 + 物品）一张，' +
      '全部就地改。四张卡片都在页面上，往下滚就是全部。' }));

    this.listWrap = el('div', { class: 'table-wrap' });
    this.detailWrap = el('div', { class: 'detail-panel' });
    // 头部与脚注每次重画；卡片堆常驻在另一个容器里 —— clear() 不到它，
    // 所以换奖励时卡片还是那几张。
    this.detailHead = el('div', { class: 'detail-head-area' });
    this.detailCards = el('div', { class: 'detail-cards' });
    this.detailFoot = el('div', { class: 'detail-foot-area' });
    this.detailWrap.appendChild(this.detailHead);
    this.detailWrap.appendChild(this.detailCards);
    this.detailWrap.appendChild(this.detailFoot);
    container.appendChild(splitPane(this.listWrap, this.detailWrap, {
      key: 'editor.reward',
      wide: true,
    }));
    this.cards = new CardStack([
      // 三个数字字段各占一张卡：它们是这张表里唯一不是重复槽的定宽数字字段。
      ...this.numbers.map((field) => ({
        id: field.key,
        label: field.label || field.key,
        hint: field.desc || (field.label || field.key),
        badge: () => this.numberBadge(field),
        render: () => this.cardContent(field.key, () => this.renderNumberField(field)),
      })),
      {
        id: 'slots',
        label: '掉落位',
        hint: '8 个掉落位：类别 + 物品（物品 id 写成 0 表示列表结束）',
        badge: () => this.slotsBadge(),
        render: () => this.cardContent('slots', () => this.renderSlots()),
      },
    ], { pack: this.pack });
    this.renderList();
    this.renderDetail();
  }

  /** 左边：奖励表的每一条。 */
  renderList() {
    const wrap = this.listWrap;
    clear(wrap);
    if (!this.rewards) {
      wrap.appendChild(el('div', { class: 'empty', text: '内容包里没有奖励表。' }));
      return;
    }
    const table = el('table', { class: 'grid' });
    table.appendChild(el('thead', {}, [el('tr', {}, [
      el('th', { class: 'col-id', text: '#' }),
      el('th', { text: '第几关的子奖励' }),
      el('th', { class: 'col-num', text: this.goldField ? this.goldField.label : '金币' }),
      el('th', { class: 'col-num', text: '已改' }),
    ])]));
    const body = el('tbody');
    for (const record of this.rewards.records || []) {
      const owners = this.owners.get(record.id) || [];
      const where = owners.length
        ? owners.map((o) => ownerLabel(o)).join('、')
        : '没有被关卡引用';
      const values = record.values || {};
      const gold = this.goldField ? values[this.goldField.key] : '';
      const changed = recordChanged(this.pack, this.rewards, record);
      body.appendChild(el('tr', {
        class: (this.id === record.id ? 'selected ' : '') + (changed ? 'changed' : ''),
        title: where,
        onclick: () => {
          this.id = record.id;
          lastRewardId = record.id;
          this.renderList();
          this.renderDetail();
        },
      }, [
        el('td', { class: 'col-id', text: String(record.id) }),
        el('td', { class: 'text-cell', text: where }),
        el('td', { class: 'col-num', text: gold === undefined ? '—' : String(gold) }),
        el('td', { class: 'col-num', text: changed ? '● 1' : '—' }),
      ]));
    }
    table.appendChild(body);
    wrap.appendChild(table);
  }

  /** 现在看的那条奖励。 */
  currentRecord() {
    return ((this.rewards && this.rewards.records) || [])
      .find((r) => r.id === this.id) || null;
  }

  /** 卡片堆常驻在 detailCards 里 —— 它自己管内容，这里只管挂不挂。 */
  mountCards() {
    if (this.cardsMounted) return;
    this.detailCards.appendChild(this.cards.element);
    this.cardsMounted = true;
  }

  /** 找不到记录时把卡片收起来（下次有记录了再挂回去）。 */
  unmountCards() {
    if (!this.cardsMounted) return;
    clear(this.detailCards);
    this.cardsMounted = false;
  }

  /**
   * 一张卡片的内容。
   *
   * 卡片全都同时在页面上，所以「刷新器」（改完一格要重画说明行的回调）
   * 是所有卡片合起来的一份 —— 但每张卡片各管各的一桶：
   * 这张卡片重建时只清它自己那一桶。
   */
  cardContent(id, build) {
    this.currentCard = id;
    this.refreshers.set(id, []);
    return build();
  }

  /** 登记一个「改完要重画」的回调（归到当前这张卡片名下）。 */
  addRefresher(fn) {
    const id = this.currentCard;
    if (!id) return;
    const bucket = this.refreshers.get(id) || [];
    bucket.push(fn);
    this.refreshers.set(id, bucket);
  }

  /** 跑一遍所有卡片的刷新器（改完一格，说明行与「已改」标记要跟上）。 */
  runRefreshers() {
    for (const bucket of this.refreshers.values()) {
      for (const fn of bucket) fn();
    }
  }

  /** 右边：这一条奖励。头部在外面，内容按类分成卡片。 */
  renderDetail() {
    const record = this.currentRecord();
    clear(this.detailHead);
    clear(this.detailFoot);
    if (!record) {
      this.detailHead.appendChild(el('div', { class: 'empty', text: '找不到这条奖励。' }));
      this.unmountCards();
      return;
    }
    const owners = this.owners.get(record.id) || [];

    this.detailHead.appendChild(el('div', { class: 'detail-head' }, [
      el('h3', { text: `奖励 #${record.id}` }),
    ]));
    this.detailHead.appendChild(el('div', { class: 'detail-sub' }, [
      el('span', { text: owners.length ? rewardOwnerText(this.owners, record.id) : '没有被关卡引用' }),
      el('span', { text: `奖励表第 ${record.id} 条` }),
    ]));

    this.mountCards();
    this.cards.refresh();
    this.detailFoot.appendChild(this.renderFoot(record, owners));
  }

  /** 这个数字字段改了几处（按字节判定）。 */
  numberBadge(field) {
    const record = this.currentRecord();
    if (!record) return null;
    return fieldChanged(this.pack, this.rewards, record, field) ? 1 : null;
  }

  /** 掉落位这一类改了几处（按字节判定，一个字段算一处）。 */
  slotsBadge() {
    const record = this.currentRecord();
    if (!record) return null;
    const array = rewardSlotArray(this.rewards);
    if (!array) return null;
    let n = 0;
    for (const row of array.rows.values()) {
      for (const field of Object.values(row)) {
        if (fieldChanged(this.pack, this.rewards, record, field)) n += 1;
      }
    }
    return n || null;
  }

  /** 一个数字字段（金币 / 强化点 / 等级门槛）—— 一页一个。 */
  renderNumberField(field) {
    const record = this.currentRecord();
    const block = el('div', { class: 'item-block' });
    block.appendChild(el('div', { class: 'field-label' }, [
      el('span', { text: field.label || field.key }),
    ]));
    if (!record) {
      block.appendChild(el('div', { class: 'stat-hint', text: '找不到这条奖励。' }));
      return block;
    }
    const row = el('div', { class: 'item-numbers' });
    const { node, hint } = fieldControl(this.fieldCtx(), this.rewards, record, field);
    const cell = el('div', { class: 'item-number' }, [
      el('span', { class: 'operand-label', text: field.label || field.key }),
      node,
    ]);
    if (hint && hint.length) {
      cell.appendChild(el('div', { class: 'field-hint', text: hint.join(' · ') }));
    }
    row.appendChild(cell);
    block.appendChild(row);
    return block;
  }

  /** 8 个掉落位（类别 + 物品）。 */
  renderSlots() {
    const record = this.currentRecord();
    const array = rewardSlotArray(this.rewards);
    const block = el('div', { class: 'item-block' });
    if (!record) {
      block.appendChild(el('div', { class: 'stat-hint', text: '找不到这条奖励。' }));
      return block;
    }
    if (!array) {
      block.appendChild(el('div', { class: 'stat-hint', text: '奖励表里没有掉落位。' }));
      return block;
    }
    block.appendChild(el('div', { class: 'field-label' }, [
      el('span', { text: '掉落位（0 表示列表结束）' }),
    ]));
    block.appendChild(renderArrayTable(this.fieldCtx(), this.rewards, record, array));
    // 「0 = 列表结束」是内容包写在字段说明里的，这里如实告诉作者。
    const idField = Object.values((array.rows.values().next().value || {}))
      .find((f) => f.relation && f.relation.kind === 'by_category');
    const end = dropEndMarker(idField);
    if (end !== null) {
      block.appendChild(el('div', {
        class: 'item-note',
        text: `物品 id 写成 ${end} 表示这一串掉落位到此结束，后面几格只是占位。`,
      }));
    }
    // 反向一跳：这一条掉的忍具，能直接跳到那个忍具的视图。
    const drops = rewardDropsOfItem(this.pack, record);
    if (drops.length) {
      const links = drops.map((drop) => el('span', {
        class: 'xref-link',
        text: `跳到忍具 #${drop.itemId} →`,
        onclick: () => {
          lastItemId = drop.itemId;
          this.ctx.openPanel('item', '忍具', { itemId: drop.itemId });
        },
      }));
      block.appendChild(el('div', { class: 'field-link' }, [
        el('span', { class: 'stat-hint', text: '这一条掉的忍具：' }),
        ...links,
      ]));
    }
    return block;
  }

  /** 归属脚注：这一条是哪几关的奖励。 */
  renderFoot(record, owners) {
    const parts = [];
    if (owners.length) {
      parts.push(`这一条是 ${ownerLabel(owners[0])} 的奖励。`);
      const others = owners.slice(1);
      if (others.length) {
        parts.push(`同时也是 ${others.map((o) => ownerLabel(o)).join('、')} 的奖励，` +
          '这几关共用同一行，改一处会一起变。');
      }
    } else {
      parts.push('没有哪一关用这一条 —— 它在 ROM 里是备着的。');
    }
    return el('div', { class: 'item-note', text: parts.join('') });
  }

  /** 字段控件的上下文：改完类别要把物品下拉重画一次。 */
  fieldCtx() {
    const ctx = this.ctx;
    return {
      pack: ctx.pack,
      onChange: ctx.onChange,
      onJump: ctx.onJump,
      registerRefresh: (fn) => this.addRefresher(fn),
      onCommit: (structure, record, field) => {
        this.runRefreshers();
        if (field && typeof field.key === 'string' && field.key.endsWith('_category')) {
          // 类别变了：掉落位那一张卡片要整个重画（物品下拉的候选换了）。
          this.renderDetail();
        } else {
          this.refreshCards();
        }
        this.renderList();
      },
    };
  }

  /** 重建全部卡片的内容与角标。 */
  refreshCards() {
    if (this.cards) this.cards.refresh();
  }
}
