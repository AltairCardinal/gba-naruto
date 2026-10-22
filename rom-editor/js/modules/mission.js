// 统一的任务编辑视图。
//
// 用户原话：「光一个任务表就分了索引、标题、说明、提示表来呈现，过于细碎繁琐，
// 应当按统一的任务编辑来呈现，**然后按索引表列出**，将其他表的内容都作为字段呈现。」
//
// 任务其实是**一个**东西：一条任务 = 标题 + 说明 + 提示 + 奖励。
// 仓库里它被拆成四张表（任务索引表 + 标题表 + 说明表 + 提示表），
// 因为 ROM 就是这么存的（索引表给出基址，三张文本表各存一段话）。
// 存储怎么拆是 ROM 的事，**编辑时不该拆** —— 作者要的是一个任务。
//
// 所以：
//   左边列表 = 任务索引表的每一条（一行 = 一关，含它的标题摘要）
//   右边详情 = 头部（第几关 / 基址）留在卡片外面，
//              内容按类分五张卡片：基址 / 标题 / 说明 / 提示 / 奖励
//
// 以前右边是一条长面板：基址 → 三个子任务（标题 / 说明 / 提示 + 奖励），
// 改「说明」得先滚过基址与三张标题。现在五张卡片竖着排在同一个滚动页面里 ——
// 往下滚就是全部，不用在一堆页签里来回切；卡片头的角标是
// 「这一类改了几处」（按字节判定，与通用表格编辑器同一套口径）。
//
// 写回仍然只走内容包已有的通路（pack.setText / pack.setValue），
// 语义只从内容包取（mission_index 的基址、文本表的容量、奖励表的字段）。

import { el, clear, toast } from '../ui.js';
import { fieldControl } from '../fields.js';
import { arraysIn, renderArrayTable } from '../slots.js';
import { missionIndexOwners } from '../xref.js';
import { splitPane } from '../split.js';
import { CardStack } from '../cards.js';
import { backButton } from './common.js';

/** 任务文本表：标题 / 说明 / 提示。 */
export const MISSION_TEXTS = [
  ['标题', 'mission_titles'],
  ['说明', 'mission_descriptions'],
  ['提示', 'mission_hints'],
];

/** 一关几个子任务。 */
export const MISSION_SUBS = 3;

/** 任务索引表给出的基址。 */
export function missionBase(pack, stage) {
  const index = pack.structure('mission_index');
  if (!index) return null;
  const record = index.records[stage];
  if (!record || !record.values) return null;
  const value = record.values.value;
  return value === null || value === undefined ? null : value;
}

/**
 * 一格任务文案：输入框 + 当前文本 + 归属脚注。
 *
 * 脚注三件事：这一格在文本表里的下标、这个下标同时属于哪几关、
 * 这段字被几处共用（改一处会一起变）。
 */
export function missionTextCell(ctx, table, slot, label, owners, stage, sub, options = {}) {
  if (!table) {
    return el('div', { class: 'route-text-cell' }, [
      el('div', { class: 'stat-hint', text: '（没有这张文本表）' }),
    ]);
  }
  const record = table.records[slot];
  if (!record) {
    return el('div', { class: 'route-text-cell' }, [
      el('div', { class: 'stat-hint', text: '（这一格没有文本）' }),
    ]);
  }
  const preview = el('div', { class: 'route-text-preview' });
  const update = () => {
    const bytes = ctx.pack.font.encodedLength(record.text || '');
    preview.textContent = `${displayText(record.text)} · ${bytes} 字节`;
  };
  update();
  const input = el('input', {
    class: 'text-input-inline',
    type: 'text',
    spellcheck: 'false',
    value: record.text || '',
    onchange: (e) => {
      const value = e.target.value;
      const missing = ctx.pack.font.missingCharacters(value);
      if (missing.length) {
        toast(`字库里没有这些字：${missing.join(' ')}`, 'error');
        e.target.value = record.text || '';
        return;
      }
      ctx.pack.setText(table, record, value);
      ctx.onChange();
      update();
      const shared = (record.shared_with || []).length + 1;
      toast(shared > 1
        ? `已改写${table.label} #${slot} · 这段字被 ${shared} 处共用，已一起改`
        : `已改写${table.label} #${slot}`);
      if (options.onChanged) options.onChanged();
    },
  });
  if (options.isTitle && options.titleInputs) options.titleInputs.push(input);
  return el('div', { class: 'route-text-cell' }, [
    input,
    preview,
    el('div', {
      class: 'shared-note',
      text: slotFootnote('文本表下标', slot, owners, stage, sub, record),
    }),
  ]);
}

/**
 * 槽位的归属脚注。
 *
 * 归属用 mission_index 算（xref.js::missionIndexOwners）：下标不是
 * 3 × (关卡 − 1)，有一批槽位被好几关共用。
 */
export function slotFootnote(label, slot, owners, stage, sub, record) {
  const parts = [`${label} #${slot}`];
  const list = owners.get(slot) || [];
  const others = list.filter((o) => !(o.stage === stage && o.sub === sub));
  if (others.length) {
    parts.push(`同时是${others.map((o) => `第 ${o.stage} 关子 ${o.sub}`).join('、')}`);
  }
  if (record && (record.shared_with || []).length) {
    parts.push(`这段字被 ${record.shared_with.length + 1} 处共用，改一处会一起变`);
  }
  return parts.join(' · ');
}

/** 文本里的换行显示成 ↵。 */
export function displayText(text) {
  if (!text) return '（空）';
  return String(text).replace(/\n/g, '↵');
}

// ---------------------------------------------------------------------------
// 统一任务视图
// ---------------------------------------------------------------------------

export function renderMission(container, ctx, params = {}) {
  new MissionView(ctx, params).render(container);
}

class MissionView {
  constructor(ctx, params) {
    this.ctx = ctx;
    this.pack = ctx.pack;
    this.index = this.pack.structure('mission_index');
    this.rewards = this.pack.structure('reward_table');
    this.owners = missionIndexOwners(this.pack);
    this.stage = this.pickStage(params);
    this.titleInputs = [];
    this.refreshers = [];
  }

  pickStage(params) {
    const wanted = params && params.stage !== undefined && params.stage !== null
      ? Number(params.stage) : null;
    if (wanted !== null && this.index && (this.index.records || [])[wanted]) return wanted;
    if (this.index && (this.index.records || []).length) {
      // 默认打开第一个有任务内容的关卡。
      for (const record of this.index.records) {
        const base = record.values ? record.values.value : null;
        if (base === null || base === undefined) continue;
        const titles = this.pack.textTable('mission_titles');
        if (titles && titles.records[base] && titles.records[base].text) return record.id;
      }
      return this.index.records[0].id;
    }
    return 0;
  }

  render(container) {
    clear(container);
    const ctx = this.ctx;
    container.appendChild(el('div', { style: { marginBottom: '12px' } }, [
      backButton(ctx, '剧情路线'),
    ]));
    container.appendChild(el('div', { class: 'panel-head' }, [
      el('div', {}, [
        el('h2', { text: '任务' }),
        el('div', { class: 'panel-sub' }, [
          el('span', { text: '索引表 / 标题表 / 说明表 / 提示表 —— 合成一个任务来改' }),
          el('span', { text: `${(this.index ? this.index.entry_count : 0)} 关` }),
        ]),
      ]),
    ]));
    container.appendChild(el('p', { class: 'section-note', text: [
      '左边按任务索引表列出（一行 = 一关）；右边是这一关的头部，',
      '下面五张卡片依次是：基址 / 标题 / 说明 / 提示 / 奖励 —— 全都同时可见，往下滚就是全部。',
      'ROM 里它们确实是四张表（索引表给基址，三张文本表各存一段话），',
      '但改的时候它们是一个东西。',
    ] }));

    this.listWrap = el('div', { class: 'table-wrap' });
    this.detailWrap = el('div', { class: 'detail-panel' });
    container.appendChild(splitPane(this.listWrap, this.detailWrap, {
      key: 'editor.mission',
    }));
    // 右侧面板：头部（第几关 / 基址）留在卡片外面，
    // 内容按类分五张卡片 —— 全部同时可见，不用在一条长面板里上下找。
    // 卡片堆**只建一次**：换关卡时只 refresh。
    this.headHost = el('div', { class: 'mission-detail-head' });
    this.detailWrap.appendChild(this.headHost);
    this.cards = new CardStack(this.missionCards(), { pack: this.pack });
    this.detailWrap.appendChild(this.cards.element);
    this.renderList();
    this.renderDetail();
  }

  /** 左边：索引表的每一条（一关）。 */
  renderList() {
    const wrap = this.listWrap;
    clear(wrap);
    if (!this.index) {
      wrap.appendChild(el('div', { class: 'empty', text: '内容包里没有任务索引表。' }));
      return;
    }
    const titles = this.pack.textTable('mission_titles');
    const table = el('table', { class: 'grid' });
    table.appendChild(el('thead', {}, [el('tr', {}, [
      el('th', { class: 'col-id', text: '#' }),
      el('th', { text: '关卡' }),
      el('th', { text: '标题摘要' }),
      el('th', { class: 'col-num', text: '已改' }),
    ])]));
    const body = el('tbody');
    for (const record of this.index.records || []) {
      const stage = record.id;
      const base = record.values ? record.values.value : null;
      let summary = '—';
      if (base !== null && base !== undefined && titles && titles.records[base]) {
        summary = displayText(titles.records[base].text);
        if (summary.length > 22) summary = summary.slice(0, 22) + '…';
      }
      const changed = this.stageChanged(stage);
      body.appendChild(el('tr', {
        class: (this.stage === stage ? 'selected ' : '') + (changed ? 'changed' : ''),
        onclick: () => {
          this.stage = stage;
          this.renderList();
          this.renderDetail();
        },
      }, [
        el('td', { class: 'col-id', text: String(stage) }),
        el('td', { text: `第 ${stage} 关` }),
        el('td', { class: 'text-cell', text: summary }),
        el('td', { class: 'col-num', text: changed ? `● ${changed}` : '—' }),
      ]));
    }
    table.appendChild(body);
    wrap.appendChild(table);
  }

  /**
   * 这一关改了几处（文本 + 奖励）。
   *
   * 与卡片角标用的是同一套判定 —— 左边列表的总数 = 三张文本卡片 + 奖励卡片之和。
   */
  stageChanged(stage) {
    let n = 0;
    for (const [, id] of MISSION_TEXTS) {
      n += this.textChanged(id, stage) || 0;
    }
    n += this.rewardChanged(stage) || 0;
    return n;
  }

  /**
   * 这张结构表里改过的记录（rom_offset 集合）。
   *
   * 判定走 pack.changedStructureRecords —— 与通用表格编辑器同一套口径
   * （按字节比，改过又改回去不算改）。
   */
  changedOffsets(structure) {
    const out = new Set();
    if (!structure) return out;
    for (const record of this.pack.changedStructureRecords(structure)) {
      out.add(record.rom_offset);
    }
    return out;
  }

  /** 基址那一张卡片改了几处（索引表里这一关的那一格）。 */
  baseChanged(stage = this.stage) {
    const record = this.index ? (this.index.records || [])[stage] : null;
    if (!record) return null;
    return this.changedOffsets(this.index).has(record.rom_offset) ? '1' : null;
  }

  /** 文本表那一张卡片改了几处（这一关的三个槽）。 */
  textChanged(tableId, stage = this.stage) {
    const base = missionBase(this.pack, stage);
    if (base === null) return null;
    const table = this.pack.textTable(tableId);
    if (!table) return null;
    const changed = new Set(this.pack.changedTextRecords(table).map((r) => r.id));
    let n = 0;
    for (let u = 0; u < MISSION_SUBS; u++) {
      if (changed.has(base + u)) n += 1;
    }
    return n || null;
  }

  /** 奖励那一张卡片改了几处（这一关的三份奖励）。 */
  rewardChanged(stage = this.stage) {
    const base = missionBase(this.pack, stage);
    if (base === null || !this.rewards) return null;
    const changed = this.changedOffsets(this.rewards);
    let n = 0;
    for (let u = 0; u < MISSION_SUBS; u++) {
      const record = (this.rewards.records || []).find((r) => r.id === base + u);
      if (!record) continue;
      if (changed.has(record.rom_offset)) n += 1;
    }
    return n || null;
  }

  /**
   * 右侧的五张卡片：基址 / 标题 / 说明 / 提示 / 奖励。
   *
   * 一关 = 基址 + 三张文本表 + 三份奖励。以前这些全堆在一条长面板里，
   * 改「说明」得先滚过基址与三张标题 —— 现在一类一张卡片，
   * 卡片头的角标是「这一类改了几处」。
   */
  missionCards() {
    return [
      {
        id: 'base',
        label: '基址',
        hint: '本关的基址（任务索引表那一格）—— 改它会换掉整关的任务与奖励',
        badge: () => this.baseChanged(),
        render: () => this.renderBaseCard(),
      },
      {
        id: 'titles',
        label: '标题',
        hint: '任务标题表：三个子任务的标题',
        badge: () => this.textChanged('mission_titles'),
        render: () => this.renderTextCard('标题', 'mission_titles'),
      },
      {
        id: 'descriptions',
        label: '说明',
        hint: '任务说明表：三个子任务的说明',
        badge: () => this.textChanged('mission_descriptions'),
        render: () => this.renderTextCard('说明', 'mission_descriptions'),
      },
      {
        id: 'hints',
        label: '提示',
        hint: '任务提示表：三个子任务的提示',
        badge: () => this.textChanged('mission_hints'),
        render: () => this.renderTextCard('提示', 'mission_hints'),
      },
      {
        id: 'rewards',
        label: '奖励',
        hint: '本关的三份奖励：金币 / 强化点 / 等级门槛 + 8 个掉落位',
        badge: () => this.rewardChanged(),
        render: () => this.renderRewardCard(),
      },
    ];
  }

  /** 右边：头部（第几关 / 基址）留在卡片外面，内容在下面五张卡片里。 */
  renderDetail() {
    const host = this.headHost;
    clear(host);
    // 卡片内容每次重画都从零开始收（刷新器与标题输入框）。
    this.refreshers = [];
    this.titleInputs = [];
    const stage = this.stage;
    const base = missionBase(this.pack, stage);

    host.appendChild(el('div', { class: 'detail-head' }, [
      el('h3', { text: `第 ${stage} 关` }),
    ]));
    host.appendChild(el('div', { class: 'detail-sub' }, [
      el('span', { text: `索引表第 ${stage} 条` }),
      el('span', { text: base === null ? '没有基址' : `基址 #${base}` }),
    ]));

    this.cards.refresh();
  }

  /** 基址那一张：索引表里这一关的那一格。 */
  renderBaseCard() {
    const indexRecord = this.index ? (this.index.records || [])[this.stage] : null;
    if (!indexRecord) {
      return el('div', { class: 'empty', text: '内容包里没有任务索引表。' });
    }
    const field = (this.index.fields || []).find((f) => f.key === 'value');
    if (!field) {
      return el('div', { class: 'empty', text: '任务索引表里没有「基址」这一格。' });
    }
    const { node } = fieldControl(this.fieldCtx(), this.index, indexRecord, field);
    return el('div', { class: 'mission-index' }, [
      el('div', { class: 'field-label' }, [
        el('span', { text: '本关的基址（索引表）' }),
      ]),
      node,
      el('div', {
        class: 'shared-note',
        text: '改这一格，这一关就会改用新的三组文本与三份奖励。',
      }),
    ]);
  }

  /**
   * 三张任务文本表各一张卡片：这张卡片装三个子任务的这张表的文案。
   */
  renderTextCard(label, tableId) {
    const stage = this.stage;
    const base = missionBase(this.pack, stage);
    if (base === null) {
      return el('div', { class: 'empty', text: '任务索引表里没有这一关。' });
    }
    const table = this.pack.textTable(tableId);
    const wrap = el('div', { class: 'mission-texts' });
    for (let u = 0; u < MISSION_SUBS; u++) {
      const slot = base + u;
      const cell = missionTextCell(this.ctx, table, slot, label, this.owners, stage, u, {
        isTitle: tableId === 'mission_titles',
        titleInputs: this.titleInputs,
        onChanged: () => {
          this.renderList();
          this.refreshBadges();
        },
      });
      wrap.appendChild(el('div', { class: 'mission-sub' }, [
        el('h4', { class: 'route-sub', text: `子任务 ${u + 1}` }),
        el('div', { class: 'mission-text-field' }, [
          el('span', { class: 'operand-label', text: label }),
          cell,
        ]),
      ]));
    }
    return wrap;
  }

  /** 奖励那一张：三个子任务各一份奖励。 */
  renderRewardCard() {
    const stage = this.stage;
    const base = missionBase(this.pack, stage);
    if (base === null) {
      return el('div', { class: 'empty', text: '任务索引表里没有这一关。' });
    }
    const wrap = el('div', { class: 'mission-rewards' });
    for (let u = 0; u < MISSION_SUBS; u++) {
      const block = el('div', { class: 'mission-sub' });
      block.appendChild(el('h4', { class: 'route-sub', text: `子任务 ${u + 1}` }));
      const reward = this.renderReward(base + u, stage, u);
      if (reward) block.appendChild(reward);
      wrap.appendChild(block);
    }
    return wrap;
  }

  /** 子任务的奖励：金币 / 强化点 / 等级门槛 + 8 个掉落位。 */
  renderReward(slot, stage, sub) {
    const rewards = this.rewards;
    if (!rewards) return null;
    const record = (rewards.records || []).find((r) => r.id === slot);
    if (!record) return null;

    const fieldCtx = this.fieldCtx();
    const numbers = el('div', { class: 'route-reward-numbers' });
    for (const key of ['gold', 'upgrade_points', 'tier']) {
      const field = (rewards.fields || []).find((f) => f.key === key);
      if (!field) continue;
      const { node } = fieldControl(fieldCtx, rewards, record, field);
      numbers.appendChild(el('div', { class: 'route-reward-field' }, [
        el('span', { class: 'operand-label', text: field.label || key }),
        node,
      ]));
    }
    const node = el('div', { class: 'route-reward' }, [
      el('div', { class: 'route-sub', text: '奖励' }),
      numbers,
    ]);

    const arrays = arraysIn(rewards.fields || []);
    const slotArray = arrays.find((a) => a.name === 'slots') || null;
    if (slotArray) {
      node.appendChild(el('div', { class: 'route-reward-drops' }, [
        el('div', { class: 'route-sub', text: '掉落位（8 位，0 表示列表结束）' }),
        renderArrayTable(fieldCtx, rewards, record, slotArray),
      ]));
    }
    node.appendChild(el('div', { class: 'route-reward-foot' }, [
      el('span', {
        class: 'shared-note',
        text: slotFootnote('奖励表', slot, this.owners, stage, sub, null),
      }),
    ]));
    return node;
  }

  /**
   * 重算卡片头上的角标。
   *
   * 角标是按当前数据算的（card.badge）—— setBadge(id, null) 清掉覆盖后，
   * 角标就回到「这一类改了几处」的真实值。
   */
  refreshBadges() {
    if (!this.cards) return;
    for (const card of this.cards.cards) this.cards.setBadge(card.id, null);
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
        // 先重画左边（已改数与角标都从这里的数据来）。
        this.renderList();
        const key = field && typeof field.key === 'string' ? field.key : '';
        // 改基址会换掉整关的任务与奖励；改道具类别要重画物品下拉 ——
        // 这两种都得整页重画，其余只更新角标（免得输入框被换掉、焦点就没了）。
        if (structure === this.index || key.endsWith('_category')) {
          this.renderDetail();
        } else {
          this.refreshBadges();
        }
      },
    };
  }
}
