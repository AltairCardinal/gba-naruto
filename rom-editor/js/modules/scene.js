// 剧情与对白域的两个统一编辑视图：场景 与 字库。
//
// 用户反馈：「应当按统一的任务编辑来呈现，然后按索引表列出，将其他表的内容都作为字段呈现。」
//
// 剧情域里同一件事也被 ROM 拆成了好几张表：
//   - 四张剧情脚本根表（before / after / logic / events）其实是同一个场景的四个剧本入口；
//   - 字形段表与字宽表是同一批字形的两面（字形在 ROM 里的位置 + 每个字符的字宽）。
// 存储怎么拆是 ROM 的事，编辑时不该拆 —— 作者要的是一个场景、一个字库。
//
// 写回仍然只走内容包已有的通路（pack.setValue），
// 语义只从内容包取：根表的槽数、字形段的字段、字宽表的条数都是读出来的，不是写死的。

import { el, clear, toast } from '../ui.js';
import { base64ToBytes, bytesToBase64 } from '../bytes.js';
import { fieldControl } from '../fields.js';
import { splitPane } from '../split.js';
import { CardStack } from '../cards.js';
import { backButton } from './common.js';
import { ROOTS } from './scriptview.js';
import { SCENE_ID_NOTE, sceneLabel, sceneTag } from '../sceneid.js';

/** 四张剧情脚本根表 = 同一个场景的四个剧本入口（root id 与剧本查看器一致）。 */
export const SCENE_ROOTS = ROOTS;

/** 根表在列表里的短标签。 */
const ROOT_SHORT = {
  before: '战前',
  after: '战后',
  logic: '逻辑',
  events: '事件',
};

/** 字库的两张表（内容包里的表 id）。 */
const SEGMENT_TABLE = 'font_segments';
const WIDTH_TABLE = 'font_width_table';

// ---------------------------------------------------------------------------
// 场景视图
// ---------------------------------------------------------------------------

export function renderScene(container, ctx, params = {}) {
  new SceneView(ctx, params).render(container);
}

class SceneView {
  constructor(ctx, params) {
    this.ctx = ctx;
    this.pack = ctx.pack;
    this.roots = SCENE_ROOTS
      .map((root) => ({ ...root, table: ctx.pack.structure(root.structure) }))
      .filter((root) => root.table);
    this.refreshers = [];
    this.scenes = this.sceneNumbers();
    this.scene = this.pickScene(params);
  }

  /**
   * 场景号 = 四张根表用到的槽号。
   *
   * 0 号槽在四张表里都是空的（没有剧本），所以不算一场戏 ——
   * 这条是从数据里看出来的：四张表的第一格都没指针。
   */
  sceneNumbers() {
    const ids = new Set();
    for (const root of this.roots) {
      for (const record of root.table.records || []) ids.add(record.id);
    }
    const slotZeroEmpty = this.roots.length > 0 && this.roots.every((root) => {
      const record = (root.table.records || [])[0];
      return !!record && !(record.values || {}).ptr;
    });
    if (slotZeroEmpty) ids.delete(0);
    return [...ids].sort((a, b) => a - b);
  }

  pickScene(params) {
    const wanted = params && params.scene !== undefined && params.scene !== null
      ? Number(params.scene) : null;
    if (wanted !== null && this.scenes.includes(wanted)) return wanted;
    return this.scenes.length ? this.scenes[0] : 0;
  }

  render(container) {
    clear(container);
    const ctx = this.ctx;
    container.appendChild(el('div', { style: { marginBottom: '12px' } }, [
      backButton(ctx, '剧情与对白'),
    ]));
    container.appendChild(el('div', { class: 'panel-head' }, [
      el('div', {}, [
        el('h2', { text: '场景' }),
        el('div', { class: 'panel-sub' }, [
          el('span', { text: '四张剧情脚本根表合成一个场景' }),
          el('span', { text: `${this.scenes.length} 个场景` }),
        ]),
      ]),
    ]));
    container.appendChild(el('p', { class: 'section-note', text:
      '左边按场景号列出（槽号就是场景号）；右边是这一场的四个剧本入口 —— ' +
      '战前 / 战后 / 战场事件逻辑 / 战场事件，各占一张卡片，四个指针都能直接改，' +
      '点「看剧本」就跳到这一场的反汇编。' +
      '四张根表在 ROM 里是分开存的，但它们说的是同一场戏。' +
      SCENE_ID_NOTE }));

    this.listWrap = el('div', { class: 'table-wrap scene-list' });
    this.detailWrap = el('div', { class: 'detail-panel scene-detail' });
    container.appendChild(splitPane(this.listWrap, this.detailWrap, {
      key: 'editor.story.scene', wide: true,
    }));
    // 右侧面板：头部（场景号 / 槽号 / 改动数）留在卡片外面，
    // 四张根表 —— 也就是这一场的四个剧本入口 —— 各占一张卡片，全都同时可见。
    this.headHost = el('div', { class: 'scene-detail-head' });
    this.detailWrap.appendChild(this.headHost);
    this.cards = new CardStack(this.sceneCards(), { pack: this.pack });
    this.detailWrap.appendChild(this.cards.element);
    this.renderList();
    this.renderDetail();
  }

  /** 左边：场景号（一行 = 一场戏）。 */
  renderList() {
    const wrap = this.listWrap;
    clear(wrap);
    if (!this.scenes.length) {
      wrap.appendChild(el('div', { class: 'empty', text: '内容包里没有剧情脚本根表。' }));
      return;
    }
    const table = el('table', { class: 'grid' });
    table.appendChild(el('thead', {}, [el('tr', {}, [
      el('th', { class: 'col-id', text: '#' }),
      el('th', { text: '场景' }),
      el('th', { text: '剧本' }),
      el('th', { class: 'col-num', text: '已改' }),
    ])]));
    const body = el('tbody');
    for (const scene of this.scenes) {
      const state = this.sceneState(scene);
      body.appendChild(el('tr', {
        class: (this.scene === scene ? 'selected ' : '') + (state.changed ? 'changed' : ''),
        onclick: () => {
          this.scene = scene;
          this.renderList();
          this.renderDetail();
        },
      }, [
        el('td', { class: 'col-id', text: String(scene) }),
        el('td', { text: sceneLabel(scene) }),
        el('td', { class: 'text-cell', text: state.summary, title: state.detail }),
        el('td', { class: 'col-num', text: state.changed ? `● ${state.changed}` : '—' }),
      ]));
    }
    table.appendChild(body);
    wrap.appendChild(table);
  }

  /** 这一场有几个剧本、指针改过几处。 */
  sceneState(scene) {
    const scripts = [];
    let changed = 0;
    for (const root of this.roots) {
      const record = (root.table.records || [])[scene];
      if (!record) continue;
      if ((record.values || {}).ptr) scripts.push(ROOT_SHORT[root.id] || root.id);
      if (this.isChanged(root.table, record)) changed += 1;
    }
    return {
      summary: scripts.length ? scripts.join(' · ') : '无剧本',
      detail: scripts.length
        ? `这一场有 ${scripts.length} 个剧本：${scripts.join('、')}`
        : '这一场没有剧本',
      changed,
    };
  }

  isChanged(structure, record) {
    const bytes = this.pack.recordBytes(structure, record);
    const raw = base64ToBytes(record.raw || '');
    return bytesToBase64(bytes) !== bytesToBase64(raw);
  }

  /**
   * 右侧的四张卡片：四张根表各一张。
   *
   * 它们本来就是同一场戏的四个剧本入口 —— 战前 / 战后 / 战场事件逻辑 / 战场事件，
   * 所以一张一路：四张卡片竖着排在一起，作者改哪一路就往下滚到哪一路。
   */
  sceneCards() {
    return this.roots.map((root) => ({
      id: root.id,
      label: ROOT_SHORT[root.id] || root.label,
      hint: `${root.label} —— 这一场的剧本入口指针`,
      badge: () => this.rootChanged(root),
      render: () => this.renderRootCard(root),
    }));
  }

  /**
   * 这一路的剧本指针改过没有（按字节判定，与通用表格同一套）。
   *
   * 只看当前这一场：左边列表的「已改」是这一场的总数，
   * 角标说的是「这张卡片显示的那一条改没改」。
   */
  rootChanged(root) {
    const record = (root.table.records || [])[this.scene];
    if (!record) return null;
    const changed = new Set(this.pack.changedStructureRecords(root.table)
      .map((r) => r.rom_offset));
    return changed.has(record.rom_offset) ? '1' : null;
  }

  /** 一张卡片 = 一张根表里这一场的剧本入口。 */
  renderRootCard(root) {
    const record = (root.table.records || [])[this.scene];
    if (!record) {
      return el('div', { class: 'empty', text: '这张根表里没有这一场。' });
    }
    const field = (root.table.fields || []).find((f) => f.type === 'ptr') ||
      (root.table.fields || [])[0];
    if (!field) {
      return el('div', { class: 'empty', text: '这张根表没有可改的字段。' });
    }
    const { node, hint, link, links } = fieldControl(this.fieldCtx(), root.table, record, field);
    const all = links && links.length ? links : (link ? [link] : []);
    return el('div', { class: 'scene-ptrs' }, [
      el('div', { class: 'scene-ptr' }, [
        el('div', { class: 'field-label' }, [
          el('span', { text: root.label }),
          el('span', { class: 'field-offset', text: root.table.label || root.structure }),
        ]),
        node,
        hint && hint.length
          ? el('div', { class: 'field-hint', text: hint.join(' · ') })
          : null,
        all.length ? el('div', { class: 'field-link' }, all) : null,
        this.scriptLink(root, this.scene, record),
      ]),
    ]);
  }

  /** 右边：头部（场景号 / 槽号 / 改动数）留在卡片外面，内容在下面四张卡片里。 */
  renderDetail() {
    const host = this.headHost;
    clear(host);
    this.refreshers = [];
    const scene = this.scene;
    const state = this.sceneState(scene);

    host.appendChild(el('div', { class: 'detail-head' }, [
      el('h3', { text: sceneLabel(scene) }),
    ]));
    host.appendChild(el('div', { class: 'detail-sub' }, [
      el('span', { text: `槽号 ${scene}` }),
      el('span', { text: sceneTag(scene) }),
      el('span', { text: `${this.roots.length} 张根表` }),
      el('span', { text: state.changed ? `已改 ${state.changed} 处` : '还没有改动' }),
    ]));

    this.cards.refresh();
  }

  /** 「看这个场景的剧本」—— 跳到剧本查看器。 */
  scriptLink(root, scene, record) {
    const ptr = (record.values || {}).ptr;
    if (!ptr) {
      return el('div', { class: 'field-hint', text: '这一路没有剧本，看不了反汇编。' });
    }
    return el('div', { class: 'field-link' }, [
      el('span', {
        class: 'xref-link',
        text: `看${root.label}的剧本 →`,
        title: `打开剧本查看器：#story/script/${root.id}/${scene}`,
        onclick: () => this.ctx.onJump({
          module: 'story',
          kind: 'script',
          id: 'script',
          params: { root: root.id, scene },
        }),
      }),
    ]);
  }

  /** 字段控件的上下文：改完要把列表和详情重画一次。 */
  fieldCtx() {
    const ctx = this.ctx;
    return {
      pack: ctx.pack,
      onChange: ctx.onChange,
      onJump: ctx.onJump,
      registerRefresh: (fn) => this.refreshers.push(fn),
      onCommit: () => {
        for (const fn of this.refreshers) fn();
        this.renderList();
        this.renderDetail();
      },
    };
  }
}

// ---------------------------------------------------------------------------
// 字库视图
// ---------------------------------------------------------------------------

export function renderFont(container, ctx, params = {}) {
  new FontView(ctx, params).render(container);
}

class FontView {
  constructor(ctx, params) {
    this.ctx = ctx;
    this.pack = ctx.pack;
    this.segments = this.pack.structure(SEGMENT_TABLE);
    this.widths = this.pack.structure(WIDTH_TABLE);
    this.refreshers = [];
    this.lookupCode = null;
    this.segment = this.pickSegment(params);
  }

  pickSegment(params) {
    const wanted = params && params.segment !== undefined && params.segment !== null
      ? Number(params.segment) : null;
    const records = (this.segments && this.segments.records) || [];
    if (wanted !== null) {
      const hit = records.find((r) => r.id === wanted);
      if (hit) return wanted;
    }
    return records.length ? records[0].id : 0;
  }

  render(container) {
    clear(container);
    const ctx = this.ctx;
    container.appendChild(el('div', { style: { marginBottom: '12px' } }, [
      backButton(ctx, '剧情与对白'),
    ]));
    container.appendChild(el('div', { class: 'panel-head' }, [
      el('div', {}, [
        el('h2', { text: '字库' }),
        el('div', { class: 'panel-sub' }, [
          el('span', { text: '字形段表 + 字宽表 —— 合成一个字库来改' }),
          el('span', {
            text: `${(this.segments && this.segments.records.length) || 0} 段 · ` +
              `${(this.widths && this.widths.records.length) || 0} 个字符码`,
          }),
        ]),
      ]),
    ]));
    container.appendChild(el('p', { class: 'section-note', text:
      '左边是字形段表（一行 = 一段字形：起始码、字数、字形在 ROM 里的位置）；' +
      '右边分两张卡片：字形段是这一段的字段，字宽是字宽表 —— 字宽表按字符码索引，' +
      '字形段表只覆盖其中一部分码位，所以这里还能按字符码单独查、单独改。' }));

    this.listWrap = el('div', { class: 'table-wrap font-list' });
    this.detailWrap = el('div', { class: 'detail-panel font-detail' });
    container.appendChild(splitPane(this.listWrap, this.detailWrap, {
      key: 'editor.story.font', wide: true,
    }));
    // 右侧面板：头部（段号 / 起始码 / 字数）留在卡片外面，
    // 字形段与字宽各占一张卡片 —— 两张表说的本来就是同一批字形，全都同时可见。
    this.headHost = el('div', { class: 'font-detail-head' });
    this.detailWrap.appendChild(this.headHost);
    this.cards = new CardStack([
      {
        id: 'segments',
        label: '字形段',
        hint: '这一段的字段：起始码、字数与字形在 ROM 里的位置',
        badge: () => this.segmentChanged(),
        render: () => this.renderSegmentCard(),
      },
      {
        id: 'widths',
        label: '字宽',
        hint: '字宽表：按字符码索引，每个字符的字宽',
        badge: () => this.widthChanged(),
        render: () => this.renderWidthCard(),
      },
    ], { pack: this.pack });
    this.detailWrap.appendChild(this.cards.element);
    this.renderList();
    this.renderDetail();
  }

  /** 左边：字形段表（一行 = 一段字形）。 */
  renderList() {
    const wrap = this.listWrap;
    clear(wrap);
    const records = (this.segments && this.segments.records) || [];
    if (!records.length) {
      wrap.appendChild(el('div', { class: 'empty', text: '内容包里没有字形段表。' }));
      return;
    }
    const table = el('table', { class: 'grid' });
    table.appendChild(el('thead', {}, [el('tr', {}, [
      el('th', { class: 'col-id', text: '段' }),
      el('th', { text: '起始码' }),
      el('th', { class: 'col-num', text: '字数' }),
      el('th', { text: '字形位置' }),
      el('th', { class: 'col-num', text: '已改' }),
    ])]));
    const body = el('tbody');
    for (const record of records) {
      const values = record.values || {};
      const changed = this.isChanged(this.segments, record);
      body.appendChild(el('tr', {
        class: (this.segment === record.id ? 'selected ' : '') + (changed ? 'changed' : ''),
        onclick: () => {
          this.segment = record.id;
          this.lookupCode = null;
          this.renderList();
          this.renderDetail();
        },
      }, [
        el('td', { class: 'col-id', text: String(record.id) }),
        el('td', { text: hexCode(values.start_code) }),
        el('td', { class: 'col-num', text: String(values.count ?? 0) }),
        el('td', { class: 'text-cell', text: this.segmentPosition(values) }),
        el('td', { class: 'col-num', text: changed ? '● 1' : '—' }),
      ]));
    }
    table.appendChild(body);
    wrap.appendChild(table);
  }

  /** 这一段在 ROM 里的位置（字形数据指针）。 */
  segmentPosition(values) {
    const count = Number(values.count) || 0;
    if (!count) return '空段';
    const offset = Number(values.glyph_offset) || 0;
    if (!offset) return '—';
    return hexCode(offset);
  }

  isChanged(structure, record) {
    if (!structure) return false;
    const bytes = this.pack.recordBytes(structure, record);
    const raw = base64ToBytes(record.raw || '');
    return bytesToBase64(bytes) !== bytesToBase64(raw);
  }

  /** 右边：头部（段号 / 起始码 / 字数）留在卡片外面，内容在下面两张卡片里。 */
  renderDetail() {
    const host = this.headHost;
    clear(host);
    this.refreshers = [];
    const record = this.currentSegment();
    const values = (record && record.values) || {};

    host.appendChild(el('div', { class: 'detail-head' }, [
      el('h3', { text: record ? `第 ${record.id} 段` : '字形段表' }),
    ]));
    host.appendChild(el('div', { class: 'detail-sub' }, [
      el('span', { text: `起始码 ${hexCode(values.start_code)}` }),
      el('span', { text: `${values.count ?? 0} 字` }),
      el('span', { text: `字形 ${this.segmentPosition(values)}` }),
    ]));

    this.cards.refresh();
  }

  /** 字形段那一张：这一段的字段。 */
  renderSegmentCard() {
    const record = this.currentSegment();
    if (!record) {
      return el('div', { class: 'empty', text: '内容包里没有字形段表。' });
    }
    const fields = el('div', { class: 'font-seg-fields' });
    const fieldCtx = this.fieldCtx();
    for (const field of (this.segments.fields || [])) {
      const { node, hint } = fieldControl(fieldCtx, this.segments, record, field);
      fields.appendChild(el('div', { class: 'font-seg-field' }, [
        el('span', { class: 'operand-label', text: field.label || field.key }),
        node,
        hint && hint.length
          ? el('div', { class: 'field-hint', text: hint.join(' · ') })
          : null,
      ]));
    }
    return el('div', {}, [
      el('div', { class: 'font-sub', text: '这一段的字段' }),
      fields,
    ]);
  }

  /** 字宽那一张：按字符码查 + 整张字宽表。 */
  renderWidthCard() {
    const codes = this.segmentCodes();
    const wrap = el('div', {}, [
      el('div', { class: 'font-sub', text: '字宽表（按字符码索引）' }),
      el('div', { class: 'section-note', text:
        `这一段用到 ${codes.size} 个字符码（按字形码的低字节标出）。` +
        '字宽表是单字节字符码，字形段用的是双字节字形码，' +
        '两者的精确对应关系仓库尚未证明，所以只作标记用。' }),
      this.renderLookup(),
    ]);
    this.renderWidthTable(wrap, codes);
    return wrap;
  }

  /** 这一段的记录改过没有（按字节判定，与通用表格同一套）。 */
  segmentChanged() {
    const record = this.currentSegment();
    if (!record || !this.segments) return null;
    const changed = new Set(this.pack.changedStructureRecords(this.segments)
      .map((r) => r.rom_offset));
    return changed.has(record.rom_offset) ? '1' : null;
  }

  /** 字宽表里改过几条。 */
  widthChanged() {
    if (!this.widths) return null;
    const n = this.pack.changedStructureRecords(this.widths).length;
    return n ? String(n) : null;
  }

  currentSegment() {
    const records = (this.segments && this.segments.records) || [];
    return records.find((r) => r.id === this.segment) || records[0] || null;
  }

  /**
   * 这一段用到的字符码。
   *
   * 字形段里的字形码是双字节的，字宽表按单字节字符码索引 ——
   * 这里按字形码的低字节标出对应行（这个对应关系只是标记，不是证明过的语义）。
   */
  segmentCodes() {
    const out = new Set();
    const record = this.currentSegment();
    if (!record) return out;
    const values = record.values || {};
    const start = Number(values.start_code) || 0;
    const count = Number(values.count) || 0;
    for (let i = 0; i < count; i += 1) out.add((start + i) & 0xff);
    return out;
  }

  /** 「按字符码查字宽」：字宽表里的其它码位也能单独打开改。 */
  renderLookup() {
    const host = el('div', { class: 'font-lookup' });
    const field = this.widthField();
    const input = el('input', {
      class: 'num-input',
      type: 'text',
      style: { width: '72px' },
      value: this.lookupCode === null ? '' : String(this.lookupCode),
    });
    const go = el('button', {
      class: 'btn btn-tiny',
      text: '查这一码',
      onclick: () => {
        const raw = String(input.value || '').trim();
        const code = /^0x/i.test(raw) ? parseInt(raw.slice(2), 16) : Number(raw);
        if (!Number.isFinite(code) || code < 0 || code > 255) {
          toast('字符码是 0–255 的整数', 'error');
          return;
        }
        this.lookupCode = code;
        this.renderDetail();
        const hit = this.detailWrap && this.detailWrap.querySelector
          ? this.detailWrap.querySelector('.lookup-hit')
          : null;
        if (hit && hit.scrollIntoView) hit.scrollIntoView({ block: 'center' });
      },
    });
    const picked = this.lookupRecord();
    host.appendChild(el('span', { class: 'operand-label', text: '按字符码查字宽' }));
    host.appendChild(input);
    host.appendChild(go);
    if (picked && field) {
      const { node } = fieldControl(this.fieldCtx(), this.widths, picked, field);
      host.appendChild(el('span', {
        class: 'stat-hint',
        text: `字符码 ${this.lookupCode} 的字宽`,
      }));
      host.appendChild(node);
    }
    return host;
  }

  lookupRecord() {
    if (this.lookupCode === null || !this.widths) return null;
    return (this.widths.records || []).find((r) => r.id === this.lookupCode) || null;
  }

  /** 字宽表里那个「宽」字段（取内容包里第一个非原始字节的字段）。 */
  widthField() {
    const fields = (this.widths && this.widths.fields) || [];
    return fields.find((f) => f.type !== 'hex') || fields[0] || null;
  }

  /** 字宽表：一行一个字符码，字宽可直接改。 */
  renderWidthTable(host, codes) {
    const table = this.widths;
    if (!table) {
      host.appendChild(el('div', { class: 'empty', text: '内容包里没有字宽表。' }));
      return;
    }
    const field = this.widthField();
    if (!field) {
      host.appendChild(el('div', { class: 'empty', text: '字宽表没有可改的字段。' }));
      return;
    }
    const fieldCtx = this.fieldCtx();
    const grid = el('table', { class: 'grid font-width-table' });
    grid.appendChild(el('thead', {}, [el('tr', {}, [
      el('th', { class: 'col-id', text: '字符码' }),
      el('th', { text: '字宽' }),
      el('th', { text: '归属' }),
    ])]));
    const body = el('tbody');
    for (const record of table.records || []) {
      const mine = codes.has(record.id);
      const classes = [];
      if (mine) classes.push('width-hit');
      if (this.lookupCode === record.id) classes.push('lookup-hit');
      body.appendChild(el('tr', { class: classes.join(' ') }, [
        el('td', { class: 'col-id', text: String(record.id) }),
        el('td', { class: 'slot-cell' }, [
          fieldControl(fieldCtx, table, record, field).node,
        ]),
        el('td', { class: 'text-cell', text: mine ? '本段' : '' }),
      ]));
    }
    grid.appendChild(body);
    host.appendChild(el('div', { class: 'table-wrap' }, [grid]));
  }

  /** 字段控件的上下文：改完要把列表和详情重画一次。 */
  fieldCtx() {
    const ctx = this.ctx;
    return {
      pack: ctx.pack,
      onChange: ctx.onChange,
      onJump: ctx.onJump,
      registerRefresh: (fn) => this.refreshers.push(fn),
      onCommit: () => {
        for (const fn of this.refreshers) fn();
        this.renderList();
        this.renderDetail();
      },
    };
  }
}

/** 十六进制显示（补齐 4 位或 8 位）。 */
function hexCode(value) {
  const n = Number(value) || 0;
  if (n > 0xffff) return '0x' + (n >>> 0).toString(16).toUpperCase().padStart(8, '0');
  return '0x' + n.toString(16).toUpperCase().padStart(4, '0');
}
