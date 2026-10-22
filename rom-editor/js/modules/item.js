// 道具域的统一编辑视图：忍具与奖励。
//
// 用户原话：「光一个任务表就分了索引、标题、说明、提示表来呈现，过于细碎繁琐，
// 应当按统一的任务编辑来呈现，然后按索引表列出，将其他表的内容都作为字段呈现。
// 其他模块也要做同样思路的修改」
//
// 道具域有两个「主对象」：
//
//   忍具 = 记录表的一行 + 忍具名表里的名字 + 它在哪几关掉落（奖励表引用它）
//   奖励 = 奖励表的一行 = 某一关的某一个子奖励
//
// ROM 里它们分开放：忍具本体在道具/忍具记录表（16 字节），名字在忍具名表，
// 掉落关系在奖励表的 8 个掉落位里。存储怎么拆是 ROM 的事，编辑时不该拆。
//
// 所以：
//   左边列表 = 记录表 / 奖励表的每一条（一行 = 一个忍具 / 一条奖励）
//   右边详情 = 这个忍具的名字、它的未解字节、它在哪几关掉落
//              这条奖励的金币 / 强化点 / 等级门槛与 8 个掉落位
//
// 写回仍然只走内容包已有的通路（pack.setValue / pack.setText），
// 语义只从内容包取（记录表的字段表、奖励表的 enum 与 relation、
// 任务索引表给出的关卡归属）。

import { el, clear, toast } from '../ui.js';
import { base64ToBytes, bytesToBase64 } from '../bytes.js';
import { fieldControl, enumLabel } from '../fields.js';
import { arraysIn, renderArrayTable } from '../slots.js';
import { missionIndexOwners, ownerLabel } from '../xref.js';
import { idSpace } from '../idspace.js';
import { splitPane } from '../split.js';
import { backButton, summaryTable } from './common.js';

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
 * 奖励表里所有**引用了这个忍具**的行。
 *
 * 掉落位是「类别 + 物品 id」：类别决定这个 id 该去哪张名字表查名字。
 * 哪一类表示忍具，从内容包的 relation.categories 里读，不写死。
 */
export function rewardRowsForItem(pack, itemId) {
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
      if (values[idField.key] !== itemId) continue;
      // 列表结束的那一格不是掉落。
      const end = dropEndMarker(idField);
      if (end !== null && values[idField.key] === end) continue;
      out.push({ record, index, categoryField: catField, itemField: idField });
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

  /** 这条记录里那些语义未证的字节（内容包把它们描述成 hex 字段）。 */
  byteFields() {
    return ((this.records && this.records.fields) || []).filter((f) => f.type === 'hex');
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
      '右边是它的名字、它自己的那串未解字节，以及它在哪几关掉落' +
      '（奖励表里引用它的那些行，点一下就跳过去 —— 掉落关系改在奖励那一侧）。' }));

    this.listWrap = el('div', { class: 'table-wrap' });
    this.detailWrap = el('div', { class: 'detail-panel' });
    container.appendChild(splitPane(this.listWrap, this.detailWrap, {
      key: 'editor.item',
      wide: true,
    }));
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
      el('th', { class: 'col-num', text: '已改' }),
    ])]));
    const body = el('tbody');
    const drops = this.dropIndex();
    for (const record of this.records.records || []) {
      const name = itemName(this.names, record.id);
      const dropRows = drops.get(record.id) || [];
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
        el('td', { class: 'col-num', text: changes ? `● ${changes}` : '—' }),
      ]));
    }
    table.appendChild(body);
    wrap.appendChild(table);
  }

  /** 右边：这个忍具。 */
  renderDetail() {
    const host = this.detailWrap;
    clear(host);
    const record = ((this.records && this.records.records) || [])
      .find((r) => r.id === this.id);
    if (!record) {
      host.appendChild(el('div', { class: 'empty', text: '找不到这个忍具。' }));
      return;
    }
    const name = itemName(this.names, record.id);
    const bytes = this.byteFields().length;

    host.appendChild(el('div', { class: 'detail-head' }, [
      el('h3', { text: name ? `${name}（#${record.id}）` : `忍具 #${record.id}` }),
    ]));
    host.appendChild(el('div', { class: 'detail-sub' }, [
      el('span', { text: `记录表第 ${record.id} 条` }),
      el('span', { text: this.names ? `名表第 ${record.id} 条` : '没有忍具名表' }),
      el('span', { text: `${bytes} 字节语义未证` }),
    ]));

    this.renderName(host, record);
    this.renderRecord(host, record);
    this.renderDrops(host, record);
  }

  /** 名字（忍具名表里的那条文本）。 */
  renderName(host, record) {
    const ctx = this.ctx;
    const block = el('div', { class: 'item-block' });
    block.appendChild(el('div', { class: 'field-label' }, [
      el('span', { text: '名字（忍具名表）' }),
    ]));
    const textRecord = this.names && (this.names.records || [])[record.id];
    if (!textRecord) {
      block.appendChild(el('div', { class: 'stat-hint', text: '名表里没有这一条。' }));
      host.appendChild(block);
      return;
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
    host.appendChild(block);
  }

  /** 这个忍具自己的记录：语义未证的那串字节。 */
  renderRecord(host, record) {
    const ctx = this.ctx;
    const fields = this.byteFields();
    const values = record.values || {};
    const original = fields.map((f) => String(values[f.key] || '')).join('');

    const block = el('div', { class: 'item-block' });
    block.appendChild(el('div', { class: 'field-label' }, [
      el('span', { text: '这个忍具的记录（未解字节）' }),
    ]));
    block.appendChild(el('p', { class: 'section-note', text:
      `记录表每条 ${fields.length} 字节，仓库里没有任何一处证明过这 ${fields.length} 个字节` +
      '分别是什么，所以只能按原始字节改 —— 这里不替它编字段名。' }));
    block.appendChild(el('textarea', {
      class: 'hex-input',
      rows: 2,
      spellcheck: 'false',
      value: original,
      onchange: (e) => {
        const clean = String(e.target.value).replace(/[^0-9a-fA-F]/g, '').toLowerCase();
        if (clean.length !== fields.length * 2) {
          toast(`这条记录固定 ${fields.length} 字节（${fields.length * 2} 个十六进制字符）`, 'error');
          e.target.value = original;
          return;
        }
        fields.forEach((f, i) => {
          this.pack.setValue(this.records, record, f.key, clean.substr(i * 2, 2));
        });
        ctx.onChange();
        this.renderList();
        this.renderDetail();
        toast(`已改写${this.records.label} #${record.id}`);
      },
    }));
    const rows = { head: ['字节', '当前值'], body: [] };
    for (const f of fields) {
      rows.body.push([f.label || f.key, String(values[f.key] || '').toUpperCase()]);
    }
    block.appendChild(el('details', { class: 'item-bytes' }, [
      el('summary', { text: `逐字节看（${fields.length} 字节，语义未证）` }),
      summaryTable(rows),
    ]));
    host.appendChild(block);
  }

  /** 它在哪几关掉落（奖励表里引用它的那些行）。 */
  renderDrops(host, record) {
    const ctx = this.ctx;
    const block = el('div', { class: 'item-block' });
    block.appendChild(el('div', { class: 'field-label' }, [
      el('span', { text: '它在哪几关掉落' }),
    ]));
    const rows = this.dropIndex().get(record.id) || [];
    if (!rows.length) {
      block.appendChild(el('div', {
        class: 'stat-hint',
        text: '奖励表里没有哪一行掉这个忍具 —— 它的 id 没出现在任何掉落位里。',
      }));
      host.appendChild(block);
      return;
    }
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
      body.appendChild(el('tr', {}, [
        el('td', { class: 'col-id', text: String(row.index + 1) }),
        el('td', { class: 'text-cell', text: rewardOwnerText(owners, row.record.id) }),
        el('td', { text: category === null ? String(values[row.categoryField.key]) : category }),
        el('td', { text: String(values[row.itemField.key]) }),
        el('td', {}, [
          el('span', {
            class: 'xref-link',
            text: '跳到这条奖励 →',
            onclick: () => {
              // 先记住落点：hash 往返会把面板参数冲掉。
              lastRewardId = row.record.id;
              ctx.openPanel('reward', '奖励', { recordId: row.record.id });
            },
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
      ]));
    }
    table.appendChild(body);
    block.appendChild(el('div', { class: 'table-wrap' }, [table]));
    block.appendChild(el('div', {
      class: 'item-note',
      text: '掉落关系改在奖励那一侧：掉落位与金币都改在奖励表里。',
    }));
    host.appendChild(block);
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
    this.refreshers = [];
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
      '右边是这一条的金币 / 强化点 / 等级门槛与 8 个掉落位（类别 + 物品），全部就地改。' }));

    this.listWrap = el('div', { class: 'table-wrap' });
    this.detailWrap = el('div', { class: 'detail-panel' });
    container.appendChild(splitPane(this.listWrap, this.detailWrap, {
      key: 'editor.reward',
      wide: true,
    }));
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

  /** 右边：这一条奖励。 */
  renderDetail() {
    const host = this.detailWrap;
    clear(host);
    this.refreshers = [];
    const record = ((this.rewards && this.rewards.records) || [])
      .find((r) => r.id === this.id);
    if (!record) {
      host.appendChild(el('div', { class: 'empty', text: '找不到这条奖励。' }));
      return;
    }
    const owners = this.owners.get(record.id) || [];

    host.appendChild(el('div', { class: 'detail-head' }, [
      el('h3', { text: `奖励 #${record.id}` }),
    ]));
    host.appendChild(el('div', { class: 'detail-sub' }, [
      el('span', { text: owners.length ? rewardOwnerText(this.owners, record.id) : '没有被关卡引用' }),
      el('span', { text: `奖励表第 ${record.id} 条` }),
    ]));

    this.renderNumbers(host, record);
    this.renderDrops(host, record);
    this.renderFoot(host, record, owners);
  }

  /** 金币 / 强化点 / 等级门槛。 */
  renderNumbers(host, record) {
    const block = el('div', { class: 'item-block' });
    block.appendChild(el('div', { class: 'field-label' }, [
      el('span', { text: '这一条给什么' }),
    ]));
    const row = el('div', { class: 'item-numbers' });
    for (const field of this.numbers) {
      const { node, hint } = fieldControl(this.fieldCtx(), this.rewards, record, field);
      const cell = el('div', { class: 'item-number' }, [
        el('span', { class: 'operand-label', text: field.label || field.key }),
        node,
      ]);
      if (hint && hint.length) {
        cell.appendChild(el('div', { class: 'field-hint', text: hint.join(' · ') }));
      }
      row.appendChild(cell);
    }
    block.appendChild(row);
    host.appendChild(block);
  }

  /** 8 个掉落位（类别 + 物品）。 */
  renderDrops(host, record) {
    const array = rewardSlotArray(this.rewards);
    if (!array) return;
    const block = el('div', { class: 'item-block' });
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
    host.appendChild(block);
  }

  /** 归属脚注：这一条是哪几关的奖励。 */
  renderFoot(host, record, owners) {
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
    host.appendChild(el('div', { class: 'item-note', text: parts.join('') }));
  }

  /** 字段控件的上下文：改完类别要把物品下拉重画一次。 */
  fieldCtx() {
    const ctx = this.ctx;
    return {
      pack: ctx.pack,
      onChange: ctx.onChange,
      onJump: ctx.onJump,
      registerRefresh: (fn) => this.refreshers.push(fn),
      onCommit: (structure, record, field) => {
        for (const fn of this.refreshers) fn();
        if (field && typeof field.key === 'string' && field.key.endsWith('_category')) {
          this.renderDetail();
        }
        this.renderList();
      },
    };
  }
}
