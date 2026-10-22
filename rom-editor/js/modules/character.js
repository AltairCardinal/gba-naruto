// 统一的角色编辑视图。
//
// 用户原话：「光一个任务表就分了索引、标题、说明、提示表来呈现，过于细碎繁琐，
// 应当按统一的任务编辑来呈现，然后按索引表列出，将其他表的内容都作为字段呈现。
// 其他模块也要做同样思路的修改」
//
// 角色也一样：一个角色在 ROM 里被拆成五张表 ——
//   角色定义表     属性（12 字节头）+ 忍术槽 + 技能槽 + 道具槽
//   逐角色成长表   同号 ⇒ 每一级长多少
//   角色特性表     每个技能自己的参数（效果类型 / 基础值 / 次要值 / 每级成长 / 附加属性）
//   头像指针表     5 个表情 × 图像 / 调色板
//   头像拼块表     头像由哪几块拼起来
// 存储怎么拆是 ROM 的事，编辑时不该拆 —— 作者要的是一个角色。
//
// 所以：
//   左边列表 = 角色定义表的每一条（一行 = 一个角色）
//   右边详情 = 这个角色的各个侧面，每一段都能直接改
//
// 右边是**页签**：头部（角色名 / 来自哪张表 / 已改几处 / 跳转条）留在页签外面，
// 内容按类分页 —— 属性 / 成长 / 特性 / 忍术槽 / 技能槽 / 道具槽 / 头像。
// 以前这七段竖着堆在一起，是一条看不到头的长滚动：改「头像」得先滚过「忍术槽」。
// 每个页签有角标：这一类改了几处（按字节判定，改了又改回去不算）。
//
// 写回仍然只走内容包已有的通路（pack.setValue），
// 语义只从内容包取：id 关系来自 structure.id_relation，
// 字段取值域来自 field.enum / field.relation，名字来自 textTable。

import { el, clear, toast } from '../ui.js';
import { fieldControl, fieldHint, originalValue, idRelationName } from '../fields.js';
import { arraysIn, arrayFields, renderArrayTable } from '../slots.js';
import { splitPane } from '../split.js';
import { TabPanel } from '../tabs.js';
import { backButton } from './common.js';

/** 一个角色由哪几张表构成（表 id 都在内容包里）。 */
export const CHARACTER_TABLES = {
  template: 'character_template',
  growth: 'per_character_stats',
  perks: 'character_perks',
  portrait: 'portrait_table',
  pieces: 'portrait_pieces',
};

/** 角色定义表里「体力基础」那一格（列表摘要用；找不到就退回这个 key）。 */
const HP_FIELD = 'hp_base';

/** 角色定义表里「攻击力」那一格（列表摘要用）。 */
const ATK_LABEL = '攻击力';

/** 角色名（内容包里的 id 关系：角色定义表 ↔ 人物名表）。 */
export function characterName(pack, structure, record) {
  return idRelationName(pack, structure, record) || `（无名 #${record.id}）`;
}

/**
 * 「恒为 0」「未解」的占位字节不占版面。
 *
 * 它们在内容包里原样保留（写回照样是定宽），只是不值得占一格输入框。
 */
function substantiveFields(fields) {
  return (fields || []).filter((f) =>
    !/^(未使用|未解字节)/.test(String(f.label || '')));
}

/** 槽位表里去掉「填充」那一列（每槽 1 字节，恒为 0）。 */
function withoutPadding(array) {
  if (!array) return null;
  const items = (array.items || []).filter((item) => item !== 'pad');
  const rows = new Map();
  for (const [index, row] of array.rows) {
    const copy = {};
    for (const item of items) copy[item] = row[item];
    rows.set(index, copy);
  }
  return { name: array.name, items, rows, base: array.base };
}

/** 按标签找字段（中文标签来自内容包）；找不到就按 key 找。 */
function fieldByLabel(structure, label, key) {
  const fields = (structure && structure.fields) || [];
  return fields.find((f) => String(f.label || '').trim() === label) ||
    fields.find((f) => f.key === key) || null;
}

// ---------------------------------------------------------------------------
// 统一角色视图
// ---------------------------------------------------------------------------

export function renderCharacter(container, ctx, params = {}) {
  new CharacterView(ctx, params).render(container);
}

class CharacterView {
  constructor(ctx, params) {
    this.ctx = ctx;
    this.pack = ctx.pack;
    this.template = this.pack.structure(CHARACTER_TABLES.template);
    this.growth = this.pack.structure(CHARACTER_TABLES.growth);
    this.perks = this.pack.structure(CHARACTER_TABLES.perks);
    this.portrait = this.pack.structure(CHARACTER_TABLES.portrait);
    this.pieces = this.pack.structure(CHARACTER_TABLES.pieces);
    this.arrays = this.template ? arraysIn(this.template.fields) : [];
    this.refreshers = [];
    this.changedCache = null;
    this.tabs = null;
    this.pick = this.pickCharacter(params);
  }

  /** 要打开哪个角色：地址里指定的优先，否则第一个有体力的。 */
  pickCharacter(params) {
    const records = this.records();
    const wanted = params && params.character !== undefined && params.character !== null
      ? Number(params.character) : null;
    if (wanted !== null && Number.isFinite(wanted)) {
      const hit = records.find((r) => r.id === wanted);
      if (hit) return hit.id;
    }
    const hp = fieldByLabel(this.template, '体力（HP）基础', HP_FIELD);
    for (const record of records) {
      const value = hp ? (record.values || {})[hp.key] : null;
      if (value) return record.id;
    }
    return records.length ? records[0].id : 0;
  }

  records() {
    return (this.template && this.template.records) || [];
  }

  render(container) {
    clear(container);
    container.appendChild(el('div', { style: { marginBottom: '12px' } }, [
      backButton(this.ctx, '角色属性与技能'),
    ]));
    container.appendChild(el('div', { class: 'panel-head' }, [
      el('div', {}, [
        el('h2', { text: '角色' }),
        el('div', { class: 'panel-sub' }, [
          el('span', { text: '一个角色 = 定义表 + 成长表 + 特性表 + 头像表 + 拼块表' }),
          el('span', { text: `${this.records().length} 个角色` }),
        ]),
      ]),
    ]));
    container.appendChild(el('p', { class: 'section-note', text: [
      '左边按角色定义表列出（一行 = 一个角色）；右边是这个角色的各个侧面：',
      '属性、成长、每个技能的参数、忍术槽、技能槽、道具槽与头像，都能就地改。',
      'ROM 里它们是五张表，改的时候它们是一个角色。',
    ] }));

    this.listWrap = el('div', { class: 'table-wrap' });
    this.detailWrap = el('div', { class: 'detail-panel' });
    // 页签面板要活过 renderDetail() 的 clear()：头部与页签分装在两个容器里，
    // clear 只清头部那一个。
    this.detailTop = el('div', { class: 'detail-top' });
    this.detailTabs = el('div', { class: 'detail-tabs' });
    this.detailWrap.appendChild(this.detailTop);
    this.detailWrap.appendChild(this.detailTabs);
    container.appendChild(splitPane(this.listWrap, this.detailWrap, {
      key: 'editor.character',
      wide: true,
    }));
    this.renderList();
    this.renderDetail();
  }

  // --- 左边：角色定义表的每一条 -------------------------------------------

  renderList() {
    const wrap = this.listWrap;
    clear(wrap);
    const records = this.records();
    if (!records.length) {
      wrap.appendChild(el('div', { class: 'empty', text: '内容包里没有角色定义表。' }));
      return;
    }
    const hp = fieldByLabel(this.template, '体力（HP）基础', HP_FIELD);
    const atk = fieldByLabel(this.template, ATK_LABEL, 'stat_a');
    const table = el('table', { class: 'grid char-list' });
    table.appendChild(el('thead', {}, [el('tr', {}, [
      el('th', { class: 'col-id', text: '#' }),
      el('th', { text: '角色' }),
      el('th', { text: '体力 · 攻' }),
      el('th', { class: 'col-num', text: '已改' }),
    ])]));
    const body = el('tbody');
    for (const record of records) {
      const values = record.values || {};
      const changed = this.characterChanged(record.id);
      const summary = [
        hp ? values[hp.key] : '',
        atk ? values[atk.key] : '',
      ].filter((v) => v !== undefined && v !== null && v !== '').join(' · ');
      body.appendChild(el('tr', {
        class: (this.pick === record.id ? 'selected ' : '') + (changed ? 'changed' : ''),
        onclick: () => {
          this.pick = record.id;
          this.renderList();
          this.renderDetail();
        },
      }, [
        el('td', { class: 'col-id', text: String(record.id) }),
        el('td', { class: 'char-name', text: characterName(this.pack, this.template, record) }),
        el('td', { class: 'col-num', text: summary || '—' }),
        el('td', { class: 'col-num', text: changed ? `● ${changed}` : '—' }),
      ]));
    }
    table.appendChild(body);
    wrap.appendChild(table);
  }

  /** 这个角色改了几处（它的四张侧面表 + 它用到的技能参数）。 */
  characterChanged(id) {
    const changed = this.changedIds();
    let n = 0;
    if (changed.template.has(id)) n += 1;
    if (changed.growth.has(id)) n += 1;
    if (changed.portrait.has(id)) n += 1;
    for (const perkId of this.skillIds(id)) {
      if (changed.perks.has(perkId)) n += 1;
    }
    return n;
  }

  /** 每张表里哪些记录改过了（缓存到下一次改动为止）。 */
  changedIds() {
    if (this.changedCache) return this.changedCache;
    const ids = (structure) => new Set(
      this.pack.changedStructureRecords(structure).map((r) => r.id));
    this.changedCache = {
      template: ids(this.template),
      growth: ids(this.growth),
      perks: ids(this.perks),
      portrait: ids(this.portrait),
      pieces: ids(this.pieces),
    };
    return this.changedCache;
  }

  /** 这个角色用到的技能 id（技能槽里的 id，0 是空槽）。 */
  skillIds(characterId) {
    const record = this.records().find((r) => r.id === characterId);
    if (!record) return [];
    const array = this.arrayOf('training');
    if (!array) return [];
    const ids = [];
    for (const row of array.rows.values()) {
      const field = row.id;
      if (!field) continue;
      const value = (record.values || {})[field.key];
      if (value === undefined || value === null || !value) continue;
      if (!ids.includes(value)) ids.push(value);
    }
    return ids;
  }

  // --- 右边：这个角色的各个侧面 -------------------------------------------

  renderDetail() {
    const record = this.pickRecord();
    if (!record) {
      clear(this.detailTop);
      this.detailTop.appendChild(el('div', { class: 'empty', text: '内容包里没有角色定义表。' }));
      return;
    }
    this.renderHead(record);

    // 内容进页签。页签面板只装一次：换角色只 refresh，
    // 这样「停在哪一页」与记住的页签都还在。
    if (!this.tabs) {
      this.tabs = new TabPanel(this.tabSpecs(), { key: 'editor.character', pack: this.pack });
      this.detailTabs.appendChild(this.tabs.element);
    } else {
      this.refreshTabs();
    }
  }

  /** 头部：角色名 / 来自哪张表 / 改了几处 / 跳转条（留在页签外面）。 */
  renderHead(record) {
    const top = this.detailTop;
    clear(top);
    if (!record) return;
    top.appendChild(el('div', { class: 'detail-head' }, [
      el('h3', { text: characterName(this.pack, this.template, record) }),
    ]));
    top.appendChild(el('div', { class: 'detail-sub' }, [
      el('span', { text: `角色定义表 #${record.id}` }),
      el('span', { text: `已改 ${this.characterChanged(record.id)} 处` }),
    ]));
    top.appendChild(this.jumpBar(record));
  }

  /** 当前选中的那个角色（记录）。 */
  pickRecord() {
    return this.records().find((r) => r.id === this.pick) || null;
  }

  /**
   * 右侧面板的页签。
   *
   * 内容按类分 —— 属性 / 成长 / 特性 / 忍术槽 / 技能槽 / 道具槽 / 头像。
   * 页签 id 用英文，label 用中文；key 记住上次停在哪一页。
   */
  tabSpecs() {
    return [
      {
        id: 'attributes',
        label: '属性',
        hint: '角色定义表的头 12 字节：六项属性、副属性与体力基础',
        badge: () => this.badgeAttributes(),
        render: () => this.tabContent(() => this.renderAttributes(this.pickRecord())),
      },
      {
        id: 'growth',
        label: '成长',
        hint: '逐角色成长表里同号的那一条：每一级涨多少',
        badge: () => this.badgeGrowth(),
        render: () => this.tabContent(() => this.renderGrowth(this.pickRecord())),
      },
      {
        id: 'perks',
        label: '特性',
        hint: '这个角色用到的每个技能，在角色特性表里的参数',
        badge: () => this.badgePerks(),
        render: () => this.tabContent(() => this.renderPerks(this.pickRecord())),
      },
      {
        id: 'jutsu',
        label: '忍术槽',
        hint: '角色定义表里的忍术槽：忍术 id / 等级值 / 解锁等级',
        badge: () => this.badgeSlots('jutsu'),
        render: () => this.tabContent(() => this.renderSlots(this.pickRecord(), 'jutsu', '忍术列表',
          '角色定义表里的忍术槽：忍术 id / 等级值 / 解锁等级。忍术 id 就是忍术名表的下标。')),
      },
      {
        id: 'training',
        label: '技能槽',
        hint: '角色定义表里的技能槽：技能 id / 等级值 / 解锁等级',
        badge: () => this.badgeSlots('training'),
        render: () => this.tabContent(() => this.renderSlots(this.pickRecord(), 'training', '技能列表',
          '角色定义表里的技能槽：技能 id / 等级值 / 解锁等级。技能 id 就是技能名表与角色特性表的下标。')),
      },
      {
        id: 'items',
        label: '道具槽',
        hint: '角色定义表里的忍具槽：每一格是一个忍具 id',
        badge: () => this.badgeSlots('items'),
        render: () => this.tabContent(() => this.renderSlots(this.pickRecord(), 'items', '道具槽',
          '角色定义表里的忍具槽：每一格是一个忍具 id（0 是空槽）。')),
      },
      {
        id: 'portrait',
        label: '头像',
        hint: '头像指针表里同号的那一条 + 头像拼块表',
        badge: () => this.badgePortrait(),
        render: () => this.tabContent(() => this.renderPortrait(this.pickRecord())),
      },
    ];
  }

  /** 页签内容：重建时把「刷新器」清一遍（上一页的已经不在 DOM 里了）。 */
  tabContent(build) {
    this.refreshers = [];
    return build();
  }

  /** 刷新当前页签（内容 + 角标）—— 换角色 / 恢复原值后调。 */
  refreshTabs() {
    if (!this.tabs) return;
    const host = this.detailWrap;
    const top = host && Number.isFinite(host.scrollTop) ? host.scrollTop : 0;
    this.tabs.refresh();
    // 内容是重建的，滚动位置放回去 —— 改一格不用从头滚。
    if (host && Number.isFinite(host.scrollTop)) host.scrollTop = top;
  }

  /**
   * 只重算角标，不重建内容。
   *
   * 内容重建会把作者正在编辑的输入框换掉（焦点就没了）——
   * 所以改完一格只重画页签条：setBadge(id, null) 清掉角标覆盖，
   * 角标于是按当前数据重算。
   */
  refreshBadges() {
    if (!this.tabs) return;
    for (const tab of this.tabs.tabs) this.tabs.setBadge(tab.id, null);
    // 页签条重画了，高亮要标回去（同一个 id，不重建内容）。
    this.tabs.setActive(this.tabs.active);
  }

  // --- 页签角标：这一类改了几处 -------------------------------------------

  /**
   * 角标：这一类改了几处。
   *
   * 判定按**字节**来：`changedIds()` 里的集合来自
   * `pack.changedStructureRecords()`（比较记录的原始字节），
   * 所以「改了又改回去」不算数。
   *
   * 属性 / 忍术槽 / 技能槽 / 道具槽 都在角色定义表的**同一条记录**里
   * （rom_offset 相同），所以再按字段细一次 ——
   * 否则改一项属性会让四个页签一起亮。
   */

  /** 属性那一类。 */
  badgeAttributes() {
    const record = this.pickRecord();
    if (!record) return null;
    if (!this.changedIds().template.has(record.id)) return null;
    const { head, rest } = this.headFields();
    return this.fieldsChanged(this.template, record, head.concat(rest)) || null;
  }

  /** 成长那一类（逐角色成长表里同号的那一条）。 */
  badgeGrowth() {
    const record = this.pickRecord();
    if (!record || !this.growth) return null;
    if (!this.changedIds().growth.has(record.id)) return null;
    const target = (this.growth.records || []).find((r) => r.id === record.id);
    if (!target) return null;
    return this.fieldsChanged(this.growth, target, substantiveFields(this.growth.fields)) || null;
  }

  /** 特性那一类（这个角色用到的每个技能）。 */
  badgePerks() {
    const record = this.pickRecord();
    if (!record || !this.perks) return null;
    const changed = this.changedIds();
    const fields = substantiveFields(this.perks.fields);
    let n = 0;
    for (const skillId of this.skillIds(record.id)) {
      if (!changed.perks.has(skillId)) continue;
      const perk = (this.perks.records || []).find((r) => r.id === skillId);
      if (!perk) continue;
      if (this.fieldsChanged(this.perks, perk, fields)) n += 1;
    }
    return n || null;
  }

  /** 槽位那一类（忍术 / 技能 / 道具 —— 都在角色定义表的那一条记录里）。 */
  badgeSlots(name) {
    const record = this.pickRecord();
    if (!record) return null;
    if (!this.changedIds().template.has(record.id)) return null;
    return this.fieldsChanged(this.template, record, this.arrayFieldsOf(name)) || null;
  }

  /** 头像那一类（头像指针表同号的那一条 + 所有角色共用的拼块）。 */
  badgePortrait() {
    const record = this.pickRecord();
    if (!record) return null;
    const changed = this.changedIds();
    let n = 0;
    if (this.portrait && changed.portrait.has(record.id)) {
      const target = (this.portrait.records || []).find((r) => r.id === record.id);
      if (target && this.fieldsChanged(this.portrait, target, this.portrait.fields || [])) n += 1;
    }
    if (this.pieces) {
      // 拼块是所有角色共用的一份，改一处全体生效 —— 也算在头像这一页。
      for (const piece of this.pieces.records || []) {
        if (changed.pieces.has(piece.id)) n += 1;
      }
    }
    return n || null;
  }

  /** 这几个字段里有几处改了（和记录里的原始字节比）。 */
  fieldsChanged(structure, record, fields) {
    if (!structure || !record) return 0;
    const values = record.values || {};
    let n = 0;
    for (const field of fields || []) {
      const original = originalValue(structure, record, field);
      if (JSON.stringify(original) !== JSON.stringify(values[field.key])) n += 1;
    }
    return n;
  }

  /** 角色定义表里某个重复槽位组的字段（去掉恒为 0 的填充字节）。 */
  arrayFieldsOf(name) {
    const array = this.arrayOf(name);
    if (!array) return [];
    const out = [];
    for (const row of array.rows.values()) {
      for (const [item, field] of Object.entries(row)) {
        if (item === 'pad') continue;
        out.push(field);
      }
    }
    return out;
  }

  /** 跳到同一份数据的通用表格视图（改名字、逐表核对）。 */
  jumpBar(record) {
    const bar = el('div', { class: 'char-jumps' });
    const add = (label, target) => {
      if (!this.ctx.onJump || !target) return;
      bar.appendChild(el('button', {
        class: 'btn btn-tiny',
        text: label,
        onclick: () => this.ctx.onJump(target),
      }));
    };
    const namesId = this.template && this.template.id_relation
      ? this.template.id_relation.table : null;
    const names = namesId ? this.pack.textTable(namesId) : null;
    if (names) {
      add('人物名表（改名字）', {
        module: names.module, kind: 'text', id: names.id,
        recordId: record.id, label: names.label || names.id,
      });
    }
    const addStructure = (structure, label) => {
      if (!structure) return;
      add(label, {
        module: structure.module, kind: 'structure', id: structure.id,
        recordId: record.id, label: structure.label || structure.id,
      });
    };
    addStructure(this.template, '角色定义表');
    addStructure(this.growth, '逐角色成长表');
    addStructure(this.portrait, '头像指针表');
    return bar;
  }

  /** ① 属性：角色定义表的 12 字节头。 */
  renderAttributes(record) {
    const section = this.section('属性',
      '角色定义表的头 12 字节：六项属性、副属性与体力基础（两个恒定的标志字节也在里头）。');
    const { head, rest } = this.headFields();
    if (!head.length) {
      section.appendChild(el('div', { class: 'empty', text: '这张表没有解出字段。' }));
    }
    for (const field of head) {
      section.appendChild(this.renderField(this.template, record, field));
    }
    if (rest.length) {
      // 记录末尾还有没解码的字节 —— 归在这一段末尾，但要说清它不在头里。
      section.appendChild(el('div', { class: 'slot-caption', text: '记录末尾的未解字节' }));
      for (const field of rest) {
        section.appendChild(this.renderField(this.template, record, field));
      }
    }
    return section;
  }

  /**
   * 头 = 第一个重复槽位之前的字段（槽位从第 12 字节开始）。
   *
   * 记录末尾那些没解码的字节不属于头，单独列出来。
   */
  headFields() {
    if (!this.template) return { head: [], rest: [] };
    const inArray = arrayFields(this.arrays);
    let firstSlot = Infinity;
    for (const array of this.arrays) {
      for (const row of array.rows.values()) {
        for (const field of Object.values(row)) {
          if (typeof field.offset === 'number' && field.offset < firstSlot) {
            firstSlot = field.offset;
          }
        }
      }
    }
    const head = [];
    const rest = [];
    for (const field of this.template.fields || []) {
      if (inArray.has(field)) continue;
      if (typeof field.offset === 'number' && field.offset < firstSlot) head.push(field);
      else rest.push(field);
    }
    return { head, rest };
  }

  /** ② 成长：逐角色成长表里同号的那一条。 */
  renderGrowth(record) {
    const section = this.section('成长',
      '逐角色成长表里与这个角色同号的那一条：每一级涨多少。');
    if (!this.growth) {
      section.appendChild(el('div', { class: 'empty', text: '内容包里没有逐角色成长表。' }));
      return section;
    }
    const target = (this.growth.records || []).find((r) => r.id === record.id);
    if (!target) {
      section.appendChild(el('div', { class: 'empty', text: '成长表里没有这个角色。' }));
      return section;
    }
    for (const field of substantiveFields(this.growth.fields)) {
      section.appendChild(this.renderField(this.growth, target, field));
    }
    return section;
  }

  /** ③ 特性（技能）：这个角色用到的每个技能，在特性表里的参数。 */
  renderPerks(record) {
    const section = this.section('特性（技能）',
      '技能的参数（效果类型 / 基础值 / 次要值 / 每级成长 / 附加属性）住在角色特性表里，' +
      '它的 id 与技能名表同号 —— 这里列的是这个角色用到的每个技能。');
    if (!this.perks) {
      section.appendChild(el('div', { class: 'empty', text: '内容包里没有角色特性表。' }));
      return section;
    }
    const skills = this.skillIds(record.id);
    if (!skills.length) {
      section.appendChild(el('div', { class: 'empty', text: '这个角色的技能槽是空的。' }));
      return section;
    }
    const fields = substantiveFields(this.perks.fields);
    const table = el('table', { class: 'grid grid-slots char-perks' });
    table.appendChild(el('thead', {}, [el('tr', {}, [
      el('th', { class: 'col-id', text: '技能' }),
      ...fields.map((f) => el('th', { text: f.label || f.key })),
    ])]));
    const body = el('tbody');
    for (const skillId of skills) {
      const perk = (this.perks.records || []).find((r) => r.id === skillId);
      if (!perk) continue;
      const name = idRelationName(this.pack, this.perks, perk);
      const tr = el('tr', {});
      tr.appendChild(el('td', { class: 'col-id', text: `${skillId}${name ? ' · ' + name : ''}` }));
      for (const field of fields) {
        tr.appendChild(this.slotCell(this.perks, perk, field));
      }
      body.appendChild(tr);
    }
    table.appendChild(body);
    section.appendChild(el('div', { class: 'slot-table' }, [table]));
    return section;
  }

  /** ④⑤⑥ 槽位：忍术 / 技能 / 道具（重复槽位成表，不是一堆输入框）。 */
  renderSlots(record, name, title, note) {
    const section = this.section(title, note);
    const array = this.arrayOf(name);
    if (!array) {
      section.appendChild(el('div', { class: 'empty', text: `这张表里没有${title}。` }));
      return section;
    }
    section.appendChild(el('div', { class: 'slot-block' }, [
      el('div', { class: 'slot-caption', text: `${title}（${array.rows.size} 槽，每槽另有 1 字节填充，已省略）` }),
      renderArrayTable(this.fieldCtx(), this.template, record, withoutPadding(array)),
    ]));
    return section;
  }

  /** ⑦ 头像：头像指针表里同号的那一条 + 头像拼块表。 */
  renderPortrait(record) {
    const section = this.section('头像',
      '头像指针表里与这个角色同号的那一条：5 个表情，每个表情一张图 + 一张调色板。');
    if (!this.portrait) {
      section.appendChild(el('div', { class: 'empty', text: '内容包里没有头像指针表。' }));
      return section;
    }
    const target = (this.portrait.records || []).find((r) => r.id === record.id);
    if (!target) {
      section.appendChild(el('div', { class: 'empty', text: '头像指针表里没有这个角色。' }));
      return section;
    }
    const expr = arraysIn(this.portrait.fields).find((a) => a.name === 'expr');
    if (!expr) {
      section.appendChild(el('div', { class: 'empty', text: '头像指针表里没有表情槽。' }));
    } else {
      section.appendChild(el('div', { class: 'slot-block' }, [
        el('div', { class: 'slot-caption', text: `表情（${expr.rows.size} 个）` }),
        renderArrayTable(this.fieldCtx(), this.portrait, target, expr),
      ]));
    }
    this.renderPieces(section);
    return section;
  }

  /** 头像拼块表：所有角色共用这一份拼块，改一处全体生效。 */
  renderPieces(section) {
    if (!this.pieces) return;
    const fields = (this.pieces.fields || []);
    const table = el('table', { class: 'grid grid-slots char-pieces' });
    table.appendChild(el('thead', {}, [el('tr', {}, [
      el('th', { class: 'col-id', text: '拼块' }),
      ...fields.map((f) => el('th', { text: f.label || f.key })),
    ])]));
    const body = el('tbody');
    for (const record of this.pieces.records || []) {
      const tr = el('tr', {});
      tr.appendChild(el('td', { class: 'col-id', text: String(record.id) }));
      for (const field of fields) {
        tr.appendChild(this.slotCell(this.pieces, record, field));
      }
      body.appendChild(tr);
    }
    table.appendChild(body);
    section.appendChild(el('div', { class: 'slot-block' }, [
      el('div', {
        class: 'slot-caption',
        text: `头像拼块（${(this.pieces.records || []).length} 块，所有角色共用这一份）`,
      }),
      el('div', { class: 'slot-table' }, [table]),
    ]));
  }

  // --- 字段与格子 ---------------------------------------------------------

  /** 一个字段：标签 + 控件 + 说明 + 跳转链接（能直接改）。 */
  renderField(structure, record, field) {
    const wrapper = el('div', { class: 'field' });
    const label = el('label', { class: 'field-label' }, [
      el('span', { text: field.label || field.key }),
    ]);
    const marker = el('span', { class: 'tag tag-warn', text: '已改' });
    const restore = el('button', {
      class: 'btn btn-tiny',
      text: '↺',
      title: '把这个字段恢复成原值',
      onclick: () => {
        const original = originalValue(structure, record, field);
        this.pack.setValue(structure, record, field.key, original);
        this.ctx.onChange();
        this.changedCache = null;
        this.renderDetail();
        toast(`已恢复「${field.label || field.key}」的原值 ${original}`);
      },
    });
    label.appendChild(marker);
    label.appendChild(restore);

    const { node, link, links } = fieldControl(this.fieldCtx(), structure, record, field);
    const hintLine = el('div', { class: 'field-hint' });
    const refresh = () => {
      const original = originalValue(structure, record, field);
      const current = (record.values || {})[field.key];
      const changed = JSON.stringify(original) !== JSON.stringify(current);
      wrapper.classList.toggle('field-changed', changed);
      marker.classList.toggle('hidden', !changed);
      restore.classList.toggle('hidden', !changed);
      const lines = fieldHint(this.pack, structure, record, field);
      if (changed) lines.push(`原值 ${original}`);
      hintLine.textContent = lines.join(' · ');
    };
    this.refreshers.push(refresh);
    refresh();

    wrapper.appendChild(label);
    wrapper.appendChild(node);
    wrapper.appendChild(hintLine);
    if (link) {
      // 同一个 id 在几张表里指的是同一个东西：技能槽除了技能名表，
      // 还要能跳到角色特性表（技能自己的参数在那儿）。
      wrapper.appendChild(el('div', { class: 'field-link' },
        links && links.length ? links : [link]));
    }
    return wrapper;
  }

  /** 表里的一格：控件 + 说明 + 跳转链接。 */
  slotCell(structure, record, field) {
    const { node, link, links } = fieldControl(this.fieldCtx(), structure, record, field);
    const cell = el('td', { class: 'slot-cell' }, [node]);
    const hintLine = el('div', { class: 'field-hint' });
    const refresh = () => {
      hintLine.textContent = fieldHint(this.pack, structure, record, field).join(' · ');
    };
    refresh();
    this.refreshers.push(refresh);
    cell.appendChild(hintLine);
    if (link) {
      cell.appendChild(el('div', { class: 'field-link' },
        links && links.length ? links : [link]));
    }
    return cell;
  }

  /** 一个小节。 */
  section(title, note) {
    const node = el('div', { class: 'section' });
    node.appendChild(el('h3', { text: title }));
    if (note) node.appendChild(el('p', { class: 'section-note', text: note }));
    return node;
  }

  /** 角色定义表里的一个重复槽位组。 */
  arrayOf(name) {
    return this.arrays.find((a) => a.name === name) || null;
  }

  /** 字段控件的上下文：改完要刷新说明行、左边的已改计数与页签角标。 */
  fieldCtx() {
    return {
      pack: this.pack,
      onChange: this.ctx.onChange,
      onJump: this.ctx.onJump,
      registerRefresh: (fn) => this.refreshers.push(fn),
      onCommit: () => {
        this.changedCache = null;
        // 头部（「已改 N 处」）与页签角标都要跟上这次改动 ——
        // 但**不重建页签内容**：重建会把作者正在编辑的输入框换掉，焦点就没了。
        this.renderHead(this.pickRecord());
        this.refreshBadges();
        for (const fn of this.refreshers) fn();
        this.renderList();
      },
    };
  }
}
