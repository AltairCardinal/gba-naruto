// 忍术：一个忍术 = 记录表的一行 + 忍术名表里的名字。
//
// 以前域首页把这两张表摆成两行，作者得自己知道「它们是同一个 id 空间」。
// 现在合成一个统一视图：左边按忍术 id 列出，右边分页签改同一件事的几个侧面。
import { el, clear, toast } from '../ui.js';
import { splitPane } from '../split.js';
import { TabPanel } from '../tabs.js';
import { bytesToHex, base64ToBytes } from '../bytes.js';
import { backButton } from './common.js';
import { fieldControl } from '../fields.js';

/** 上一次看的忍术（hash 往返会丢掉参数，靠它记住）。 */
let lastJutsuId = null;

/**
 * 忍术统一视图。
 *
 * @param {HTMLElement} container
 * @param {object} ctx
 * @param {object} [params]
 */
export function renderJutsu(container, ctx, params = {}) {
  new JutsuView(ctx, params).render(container);
}

class JutsuView {
  constructor(ctx, params) {
    this.ctx = ctx;
    this.pack = ctx.pack;
    this.records = this.pack.structure('jutsu_record');
    this.names = this.pack.textTable('jutsu_names');
    this.id = this.pickId(params);
  }

  pickId(params) {
    const list = (this.records && this.records.records) || [];
    const wanted = params && params.jutsuId !== undefined && params.jutsuId !== null
      ? Number(params.jutsuId) : null;
    if (wanted !== null && list.some((r) => r.id === wanted)) {
      lastJutsuId = wanted;
      return wanted;
    }
    if (lastJutsuId !== null && list.some((r) => r.id === lastJutsuId)) return lastJutsuId;
    // 默认落在第一个有名字的忍术上（下标 0 在名表里是占位）。
    for (const record of list) {
      if (this.nameOf(record.id)) return record.id;
    }
    return list.length ? list[0].id : 0;
  }

  nameOf(id) {
    const record = this.names && (this.names.records || [])[id];
    return record && record.text ? record.text : '';
  }

  currentRecord() {
    const list = (this.records && this.records.records) || [];
    return list.find((r) => r.id === this.id) || null;
  }

  /** 字段按内容包的 group 分组 —— 语义只有一处真相，不在这里写死字段名。 */
  fieldsIn(group) {
    return ((this.records && this.records.fields) || []).filter((f) => f.group === group);
  }

  /** 这个忍术改了几处（记录 + 名字）。 */
  changedCount() {
    const record = this.currentRecord();
    let n = 0;
    if (this.recordChanged(record)) n += 1;
    const nameRecord = this.names && (this.names.records || [])[this.id];
    if (nameRecord && nameRecord.text !== undefined
        && nameRecord.text !== nameRecord.original_text) n += 1;
    return n;
  }

  render(container) {
    clear(container);
    const ctx = this.ctx;
    container.appendChild(el('div', { style: { marginBottom: '12px' } }, [
      backButton(ctx, '忍术'),
    ]));
    container.appendChild(el('div', { class: 'panel-head' }, [
      el('div', {}, [
        el('h2', { text: '忍术' }),
        el('div', { class: 'panel-sub' }, [
          el('span', { text: '忍术记录表 0x545458 + 忍术名表 0x59937C —— 合成一个忍术来改' }),
          el('span', { text: `${(this.records ? this.records.entry_count : 0)} 个忍术` }),
        ]),
      ]),
    ]));
    container.appendChild(el('p', { class: 'section-note', text:
      '左边按忍术记录表列出（一行 = 一个忍术）；' +
      '右边分三个页签：名字（忍术名表，可改长 —— 名字表由指针表驱动）、' +
      '成长（成长目标与六个成长字节）、记录（类别 / 等级 / 消耗 / 标志位等）。' }));

    this.listWrap = el('div', { class: 'table-wrap' });
    this.detailWrap = el('div', { class: 'detail-panel' });
    // 头部每次重画；页签面板常驻在另一个容器里 —— clear() 不到它，
    // 所以切页签、换忍术时页签选择都还在。
    this.detailHead = el('div', { class: 'detail-head-area' });
    this.detailTabs = el('div', { class: 'detail-tab-area' });
    this.detailWrap.appendChild(this.detailHead);
    this.detailWrap.appendChild(this.detailTabs);
    container.appendChild(splitPane(this.listWrap, this.detailWrap, {
      key: 'editor.jutsu',
      wide: true,
    }));

    this.tabs = new TabPanel([
      {
        id: 'name',
        label: '名字',
        hint: '忍术名表里的那一条文本',
        badge: () => this.nameBadge(),
        render: () => this.renderName(),
      },
      {
        id: 'growth',
        label: '成长',
        hint: '成长目标、每级成长量与六个成长字节',
        badge: () => this.growthBadge(),
        render: () => this.renderFields('成长'),
      },
      {
        id: 'record',
        label: '记录',
        hint: '类别 / 等级 / 消耗 / 标志位，以及标「保留」的那些字节',
        badge: () => this.recordBadge(),
        render: () => this.renderFields('记录'),
      },
    ], { key: 'editor.jutsu', pack: this.pack });

    // 页签面板只挂一次（clear() 不到它 —— 它在 detailTabs 容器里）。
    this.detailTabs.appendChild(this.tabs.element);

    this.renderList();
    this.renderDetail();
  }

  /** 左边：忍术记录表的每一条（一个忍术）。 */
  renderList() {
    const wrap = this.listWrap;
    clear(wrap);
    if (!this.records) {
      wrap.appendChild(el('div', { class: 'empty', text: '内容包里没有忍术记录表。' }));
      return;
    }
    const table = el('table', { class: 'grid' });
    table.appendChild(el('thead', {}, [el('tr', {}, [
      el('th', { class: 'col-id', text: '#' }),
      el('th', { text: '忍术名' }),
      el('th', { text: '成长目标' }),
      el('th', { class: 'col-num', text: '已改' }),
    ])]));
    const body = el('tbody');
    for (const record of this.records.records || []) {
      const v = record.values || {};
      const growthField = (this.records.fields || []).find((f) => f.key === 'growth_type');
      const enumText = growthField && growthField.enum
        ? (growthField.enum[v.growth_type] || String(v.growth_type))
        : String(v.growth_type);
      const changes = this.countFor(record);
      body.appendChild(el('tr', {
        class: (this.id === record.id ? 'selected ' : '') + (changes ? 'changed' : ''),
        onclick: () => {
          this.id = record.id;
          lastJutsuId = record.id;
          this.renderList();
          this.renderDetail();
        },
      }, [
        el('td', { class: 'col-id', text: String(record.id) }),
        el('td', { class: 'text-cell', text: this.nameOf(record.id) || '（空）' }),
        el('td', { text: enumText }),
        el('td', { class: 'col-num', text: changes ? `● ${changes}` : '—' }),
      ]));
    }
    table.appendChild(body);
    wrap.appendChild(table);
  }

  /** 某一个忍术改了几处（记录 + 名字）。 */
  countFor(record) {
    let n = 0;
    if (this.recordChanged(record)) n += 1;
    const nameRecord = this.names && (this.names.records || [])[record.id];
    if (nameRecord && nameRecord.text !== undefined
        && nameRecord.text !== nameRecord.original_text) n += 1;
    return n;
  }

  /** 这条记录的字节和原始字节不一样吗（改了又改回来不算改动）。 */
  recordChanged(record) {
    if (!record) return false;
    const bytes = this.pack.recordBytes(this.records, record);
    const raw = bytesToHex(base64ToBytes(record.raw || ''));
    return bytesToHex(bytes) !== raw;
  }

  renderDetail() {
    const host = this.detailHead;
    clear(host);
    const record = this.currentRecord();
    if (!record) {
      host.appendChild(el('div', { class: 'empty', text: '内容包里没有忍术记录表。' }));
      return;
    }
    host.appendChild(el('div', { class: 'detail-head' }, [
      el('h3', { text: this.nameOf(record.id) || `忍术 #${record.id}` }),
    ]));
    host.appendChild(el('div', { class: 'detail-sub' }, [
      el('span', { text: `忍术记录表 #${record.id}` }),
      el('span', { text: `已改 ${this.changedCount()} 处` }),
    ]));
    this.tabs.refresh();
  }

  // --- 页签内容 -------------------------------------------------------------

  nameBadge() {
    const nameRecord = this.names && (this.names.records || [])[this.id];
    if (!nameRecord) return null;
    return nameRecord.text !== nameRecord.original_text ? '1' : null;
  }

  growthBadge() {
    const record = this.currentRecord();
    if (!record) return null;
    const fields = this.fieldsIn('成长');
    return this.fieldsChanged(record, fields) ? '1' : null;
  }

  recordBadge() {
    const record = this.currentRecord();
    if (!record) return null;
    const fields = this.fieldsIn('记录');
    return this.fieldsChanged(record, fields) ? '1' : null;
  }

  /** 这一组字段里有没有被改过的（按字节判定）。 */
  fieldsChanged(record, fields) {
    const bytes = this.pack.recordBytes(this.records, record);
    const original = bytesToHex(base64ToBytes(record.raw || ''));
    for (const field of fields) {
      const offset = field.offset;
      if (offset === undefined || offset === null) continue;
      const size = field.size || 1;
      const slice = bytesToHex(bytes.slice(offset, offset + size));
      if (slice !== original.slice(offset * 2, (offset + size) * 2)) return true;
    }
    return false;
  }

  renderName() {
    const record = this.currentRecord();
    const nameRecord = this.names && (this.names.records || [])[this.id];
    const section = el('div', { class: 'section' }, [
      el('h3', { text: '忍术名' }),
    ]);
    if (!nameRecord) {
      section.appendChild(el('div', { class: 'empty', text: '忍术名表里没有这一条。' }));
      return section;
    }
    const used = this.pack.font.encodedLength(nameRecord.text || '');
    const input = el('input', {
      class: 'text-input',
      type: 'text',
      value: nameRecord.text || '',
      onchange: (e) => {
        const value = e.target.value;
        const missing = this.pack.font.missingCharacters(value);
        if (missing.length) {
          toast(`字库里没有这些字：${missing.join(' ')}`, 'error');
          e.target.value = nameRecord.text || '';
          return;
        }
        this.pack.setText(this.names, nameRecord, value);
        this.ctx.onChange();
        toast('已改写忍术名');
        this.renderList();
        this.renderDetail();
      },
    });
    section.appendChild(el('div', { class: 'field' }, [
      el('div', { class: 'field-label' }, [
        el('span', { text: '名字' }),
        el('span', { class: 'field-offset', text: `文本表下标 #${this.id}` }),
      ]),
      input,
      el('div', {
        class: 'field-hint',
        text: `${used} 字节 · 名字表由指针表驱动，改长会在构建时重定位并改写指针`,
      }),
    ]));
    section.appendChild(el('p', { class: 'section-note' }, [
      '忍术记录表与忍术名表是**同一个 id 空间**（内容包的 id_relation 写着）—— ' +
      '下标就是忍术 id，角色定义表里的忍术槽引用的就是这张表的 id。',
    ]));
    return section;
  }

  renderFields(group) {
    const record = this.currentRecord();
    const section = el('div', { class: 'section' }, [
      el('h3', { text: group === '成长' ? '成长' : '记录' }),
    ]);
    if (!record) {
      section.appendChild(el('div', { class: 'empty', text: '内容包里没有忍术记录表。' }));
      return section;
    }
    const fields = this.fieldsIn(group);
    if (!fields.length) {
      section.appendChild(el('div', { class: 'empty', text: `内容包里没有「${group}」这一组字段。` }));
      return section;
    }
    const fieldCtx = {
      pack: this.pack,
      onChange: this.ctx.onChange,
      onJump: this.ctx.onJump,
      registerRefresh: () => {},
      onCommit: () => {},
    };
    for (const field of fields) {
      const { node } = fieldControl(fieldCtx, this.records, record, field);
      section.appendChild(el('div', { class: 'field' }, [
        el('div', { class: 'field-label' }, [
          el('span', { text: field.label || field.key }),
          el('span', { class: 'field-offset', text: `+0x${Number(field.offset).toString(16).toUpperCase()}` }),
        ]),
        node,
        field.desc ? el('div', { class: 'field-hint', text: field.desc }) : null,
      ]));
    }
    if (group === '成长') {
      section.appendChild(el('p', { class: 'section-note' }, [
        '「成长目标」选中的是下面六个字节里的哪一个（1..6）；' +
        '「每级成长量」是每升一级加多少。',
        '类型 0 与 7 都表示「不成长」。',
      ]));
    } else {
      section.appendChild(el('p', { class: 'section-note' }, [
        '「类别」「等级」是原生代码搬进「已习得忍术」表项的那两格；' +
        '「消耗」是选这一招要花的费用（槽位 +0x0A 参与累计与上限比较）。',
        '标「保留」的两格是**原生代码根本不读**的（87 条恒为 0）—— 只读，改了不起作用。',
        '「标志位」的高字节在仓库里另被标为「未解」，低字节的位域含义也未证。',
      ]));
    }
    return section;
  }
}
