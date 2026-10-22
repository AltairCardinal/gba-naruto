// 素材与资源域：EWRAM 内存条带。
//
// 这一张表决定每个子系统分到多少 EWRAM。改地址或大小 = 直接改运行时内存布局，
// 仓库里没有任何运行时校验能替你兜底，所以这里把三件事摆在明面上：
// 内存段怎么排、哪几行其实是同一块、改大会不会压到下一段。

import { el, clear, formatOffset, toast } from '../ui.js';
import { base64ToBytes, bytesToBase64 } from '../bytes.js';
import { originalValue } from '../fields.js';
import { backButton } from './common.js';
import { splitPane } from '../split.js';
import { TabPanel } from '../tabs.js';
import { WRAM_ALLOCATION, hex32 } from './assets-wiring.js';

/** EWRAM 的合法范围（GBA 的 EWRAM 是 0x02000000–0x0203FFFF）。 */
export const EWRAM_BASE = 0x02000000;
export const EWRAM_END = 0x0203ffff;
const EWRAM_SIZE = EWRAM_END - EWRAM_BASE + 1;

const ADDR_FIELD = 'wram_addr';
const SIZE_FIELD = 'alloc_size';

export function renderMemoryMap(container, ctx, params = {}) {
  new MemoryView(ctx, params).render(container);
}

/** 十六进制地址框里的文本 → 数值（0x 前缀或含 A-F 就算十六进制）。 */
function parseAddress(text) {
  const raw = String(text === null || text === undefined ? '' : text).trim();
  if (!raw) return null;
  const looksHex = /^0x/i.test(raw) || (/^[0-9a-fA-F]+$/.test(raw) && /[a-fA-F]/.test(raw));
  const value = looksHex ? parseInt(raw.replace(/^0x/i, ''), 16) : Number(raw);
  return Number.isFinite(value) ? value : null;
}

/** 字节数框里的文本 → 数值（十进制为主，0x 前缀按十六进制）。 */
function parseSize(text) {
  const raw = String(text === null || text === undefined ? '' : text).trim();
  if (!raw) return null;
  const value = /^0x/i.test(raw) ? parseInt(raw.replace(/^0x/i, ''), 16) : Number(raw);
  return Number.isFinite(value) ? value : null;
}

/**
 * 这一域的内存数字（行数、段数）——从内容包算出来，不写死。
 *
 * @returns {{rows: number, segments: number}}
 */
export function memoryStats(pack) {
  const table = pack.structure(WRAM_ALLOCATION);
  const records = (table && table.records) || [];
  const seen = new Set();
  for (const record of records) {
    const addr = record.values ? record.values[ADDR_FIELD] : undefined;
    const size = record.values ? record.values[SIZE_FIELD] : undefined;
    if (addr === undefined || size === undefined) continue;
    seen.add(`${addr}:${size}`);
  }
  return { rows: records.length, segments: seen.size };
}

class MemoryView {
  constructor(ctx, params) {
    this.ctx = ctx;
    this.pack = ctx.pack;
    this.table = ctx.pack.structure(WRAM_ALLOCATION);
    this.selected = null;

    const wanted = params && params.recordId !== undefined && params.recordId !== null
      ? Number(params.recordId)
      : null;
    const records = (this.table && this.table.records) || [];
    const record = wanted === null ? records[0] : records.find((r) => r.id === wanted);
    if (record) this.selected = record;
  }

  /** 一行记录的名字：内容包给了名字就用，没给就写「未命名」（不臆造）。 */
  recordName(record) {
    return record && record.label ? record.label : '未命名';
  }

  /** 不同的内存段：起始地址 + 大小相同 ⇒ 同一段。 */
  segments() {
    const records = (this.table && this.table.records) || [];
    const map = new Map();
    for (const record of records) {
      const addr = record.values ? record.values[ADDR_FIELD] : undefined;
      const size = record.values ? record.values[SIZE_FIELD] : undefined;
      if (addr === undefined || size === undefined) continue;
      const key = `${addr}:${size}`;
      if (!map.has(key)) {
        map.set(key, {
          addr,
          size,
          end: addr + size,
          records: [],
        });
      }
      map.get(key).records.push(record);
    }
    return [...map.values()].sort((a, b) => a.addr - b.addr || a.size - b.size);
  }

  /** 下一段：地址严格更大的那一段（同一地址的两段是叠着的，不是相邻）。 */
  neighbour(segment) {
    const segments = this.segments();
    const next = segments.find((s) => s.addr > segment.addr);
    return next || null;
  }

  /**
   * 这一行属于哪一段。
   *
   * 先按地址找：改了大小之后这一行就与别的行不是同一段了，
   * 但它占的还是那块地址，邻接关系还得看得见。
   */
  segmentOf(record) {
    if (!record) return null;
    const addr = record.values[ADDR_FIELD];
    const size = record.values[SIZE_FIELD];
    const at = this.segments().filter((s) => s.addr === addr);
    if (!at.length) return null;
    return at.find((s) => s.size === size) || at[0];
  }

  render(container) {
    clear(container);
    const ctx = this.ctx;
    if (!this.table) {
      container.appendChild(el('div', { class: 'empty', text: '内容包里没有 WRAM 分配表' }));
      return;
    }
    container.appendChild(el('div', { style: { marginBottom: '12px' } }, [
      backButton(ctx, '素材与资源'),
    ]));

    const records = this.table.records || [];
    const segments = this.segments();
    const consumers = (this.table.consumers || []).map((c) => String(c).toUpperCase());

    container.appendChild(el('div', { class: 'panel-head' }, [
      el('div', {}, [
        el('h2', { text: this.table.label || 'WRAM 分配表' }),
        el('div', { class: 'panel-sub' }, [
          el('span', { text: `ROM ${formatOffset(this.table.rom_offset)}` }),
          el('span', { text: `${records.length} 行` }),
          el('span', { text: `${segments.length} 段不同的 EWRAM` }),
          consumers.length ? el('span', { text: `原生读者 ${consumers.join(' / ')}` }) : null,
        ]),
      ]),
    ]));

    container.appendChild(el('div', { class: 'rule-note' }, [
      el('span', { class: 'rule-title', text: '结论' }),
      el('span', { text: this.bannerText(records, segments) }),
    ]));

    this.bandWrap = el('div', { class: 'wram-band' });
    container.appendChild(this.bandWrap);
    this.renderBand();

    this.listWrap = el('div', { class: 'table-wrap' });
    this.detailWrap = el('div', { class: 'detail-panel wide' });
    container.appendChild(splitPane(this.listWrap, this.detailWrap, {
      key: 'editor.assets.memory', wide: true,
    }));
    // 右侧面板：头部（哪一行 / 改没改）留在页签外面，内容按类分两页签。
    // 页签面板要活过 renderDetail() 的 clear()：头部与页签分装在两个容器里，
    // clear 只清头部那一个。页签面板**只建一次** —— 换一行只 refresh，
    // 页签选择与记住的页签都还在。
    this.detailTop = el('div', { class: 'detail-top' });
    this.detailTabs = el('div', { class: 'detail-tabs' });
    this.detailWrap.appendChild(this.detailTop);
    this.detailWrap.appendChild(this.detailTabs);
    this.tabs = new TabPanel(this.tabSpecs(), {
      key: 'editor.assets.memory',
      pack: this.pack,
    });
    this.detailTabs.appendChild(this.tabs.element);
    this.renderList();
    this.renderDetail();
  }

  /** 横幅里的数字全部从内容包算出来，不写死。 */
  bannerText(records, segments) {
    const shared = segments.filter((s) => s.records.length > 1);
    const parts = shared.map((segment) => {
      const ids = segment.records.map((r) => '#' + r.id).join(' / ');
      const name = this.recordName(segment.records[0]);
      return `${ids} 是同一块（${name} ${hex32(segment.addr)}，`
        + `${segment.size.toLocaleString('en-US')} 字节）`;
    });
    const dup = parts.length ? parts.join('，') + '。' : '没有两行指向同一块。';
    return '结论：这张表决定每个子系统分到多少 EWRAM，编辑器不会替你判断对错。'
      + `${records.length} 行里只有 ${segments.length} 段不同的内存：${dup}`
      + '改地址或大小 = 直接改运行时内存布局，仓库里没有任何运行时校验能替你兜底。';
  }

  // --- 内存条带 ---------------------------------------------------------

  renderBand() {
    clear(this.bandWrap);
    const segments = this.segments();
    const track = el('div', { class: 'wram-track' });
    let cursor = EWRAM_BASE;
    for (const segment of segments) {
      if (segment.addr > cursor) {
        track.appendChild(this.gapNode(cursor, segment.addr));
      }
      track.appendChild(this.segmentNode(segment));
      cursor = Math.max(cursor, segment.end);
    }
    if (cursor < EWRAM_BASE + EWRAM_SIZE) {
      track.appendChild(this.gapNode(cursor, EWRAM_BASE + EWRAM_SIZE));
    }
    this.bandWrap.appendChild(el('div', { class: 'wram-axis' }, [
      el('span', { text: hex32(EWRAM_BASE) }),
      el('span', { text: 'EWRAM 内存条带' }),
      el('span', { text: hex32(EWRAM_END) }),
    ]));
    this.bandWrap.appendChild(track);
  }

  gapNode(from, to) {
    const size = Math.max(0, to - from);
    const left = ((from - EWRAM_BASE) / EWRAM_SIZE) * 100;
    const width = (size / EWRAM_SIZE) * 100;
    return el('div', {
      class: 'wram-gap',
      style: { left: left + '%', width: width + '%' },
      title: `未分配 ${size} 字节（0x${size.toString(16).toUpperCase()}）`
        + ` · ${hex32(from)} – ${hex32(to - 1)}`,
      text: `未分配 0x${size.toString(16).toUpperCase()} 字节`,
    });
  }

  segmentNode(segment) {
    const left = ((segment.addr - EWRAM_BASE) / EWRAM_SIZE) * 100;
    const width = (segment.size / EWRAM_SIZE) * 100;
    const ids = segment.records.map((r) => '#' + r.id).join(' ');
    const name = this.recordName(segment.records[0]);
    const overlap = this.overlapBytes(segment, segment.size);
    const classes = ['wram-seg'];
    if (segment.records.length > 1) classes.push('dup');
    if (overlap > 0) classes.push('overlap');
    return el('div', {
      class: classes.join(' '),
      style: { left: left + '%', width: width + '%' },
      title: `${ids} · ${name} · ${hex32(segment.addr)} 起 ${segment.size} 字节`,
      text: `${ids} · ${name}`,
      onclick: () => {
        this.selected = segment.records[0];
        this.renderList();
        this.renderDetail();
      },
    });
  }

  /** 段尾越过下一段多少字节（0 = 没压到）。 */
  overlapBytes(segment, size) {
    const next = this.neighbour(segment);
    if (!next) return 0;
    const end = segment.addr + size;
    return end > next.addr ? end - next.addr : 0;
  }

  // --- 左列表 ------------------------------------------------------------

  renderList() {
    clear(this.listWrap);
    const records = (this.table && this.table.records) || [];
    const segments = this.segments();
    const body = el('tbody');
    for (const record of records) {
      const addr = record.values[ADDR_FIELD];
      const size = record.values[SIZE_FIELD];
      const end = addr + size;
      const segment = this.segmentOf(record);
      const twins = segment ? segment.records.filter((r) => r !== record) : [];
      const changed = this.recordChanged(record);
      const selected = this.selected === record;
      body.appendChild(el('tr', {
        class: (selected ? 'selected' : '') + (changed ? ' changed' : ''),
        onclick: () => {
          this.selected = record;
          this.renderList();
          this.renderDetail();
        },
      }, [
        el('td', { class: 'col-id', text: '#' + record.id }),
        el('td', { class: 'mono', text: hex32(addr) }),
        el('td', { class: 'col-num', text: String(size) }),
        el('td', { class: 'mono', text: hex32(end) }),
        el('td', { text: twins.length ? `与 ${twins.map((r) => '#' + r.id).join(' / ')} 同一块` : '—' }),
        el('td', { text: changed ? '已改' : '—' }),
      ]));
    }
    this.listWrap.appendChild(el('div', { class: 'slot-caption', text: `WRAM 分配表（${segments.length} 段）` }));
    this.listWrap.appendChild(el('table', { class: 'grid' }, [
      el('thead', {}, [el('tr', {}, [
        el('th', { class: 'col-id', text: '下标' }),
        el('th', { text: '起始地址' }),
        el('th', { class: 'col-num', text: '大小' }),
        el('th', { text: '结束地址' }),
        el('th', { text: '与谁重复' }),
        el('th', { text: '状态' }),
      ])]),
      body,
    ]));
  }

  recordChanged(record) {
    const bytes = this.pack.recordBytes(this.table, record);
    const raw = base64ToBytes(record.raw || '');
    return bytesToBase64(bytes) !== bytesToBase64(raw);
  }

  // --- 右详情 ------------------------------------------------------------

  /**
   * 右边：头部（哪一行 / 改没改）留在页签外面，内容在页签里。
   *
   * clear() 只清头部那一个容器 —— 页签面板在另一个容器里，不会被清掉。
   */
  renderDetail() {
    const host = this.detailTop;
    clear(host);
    const record = this.selected;
    if (!record) {
      // 没选中：提示放在页签内容里（tabContent 认得这个情况）。
      this.tabs.refresh();
      return;
    }
    const records = this.table.records || [];

    host.appendChild(el('div', { class: 'detail-head' }, [
      el('h3', { text: `${this.table.label} · #${record.id}` }),
      el('div', { class: 'detail-nav' }, [
        el('button', {
          class: 'btn btn-tiny', text: '← 上一条',
          onclick: () => this.step(-1),
        }),
        el('button', {
          class: 'btn btn-tiny', text: '下一条 →',
          onclick: () => this.step(1),
        }),
        el('button', {
          class: 'btn btn-ghost', text: '✕',
          onclick: () => {
            this.selected = null;
            this.renderList();
            this.renderDetail();
          },
        }),
      ]),
    ]));

    host.appendChild(el('div', { class: 'detail-sub' }, [
      el('span', { text: `ROM ${formatOffset(record.rom_offset)}` }),
      el('span', { text: `第 ${record.id + 1} / ${records.length} 条` }),
      el('span', { text: this.recordName(record) }),
      this.recordChanged(record)
        ? el('span', { class: 'tag tag-warn', text: '已改动' })
        : null,
    ]));

    // 内容在页签里：换一行只重建当前那一页，
    // 页签选择与记住的页签都还在。
    this.tabs.refresh();
  }

  /**
   * 右侧面板的两个页签。
   *
   * 这一行内存的两个侧面：它占哪一段（地址 + 大小）/ 它与前后两段挨不挨着。
   * 页签 id 用英文，label 用中文；key 记住上次停在哪一页。
   */
  tabSpecs() {
    return [
      {
        id: 'allocation',
        label: '内存分配',
        hint: '这一行的起始地址与分配大小，以及原值',
        badge: () => this.rowChanged(),
        render: () => this.tabContent(() => this.renderAllocationTab()),
      },
      {
        id: 'neighbors',
        label: '邻接关系',
        hint: '这一段与下一段挨不挨着、会不会压到、是不是同一块',
        render: () => this.tabContent(() => this.renderNeighborsTab()),
      },
    ];
  }

  /** 页签内容：没选中记录时给一句提示，选中了才建那一页。 */
  tabContent(build) {
    if (!this.selected) {
      return el('div', { class: 'empty', text: '在左边点一行，或点条带上的一段' });
    }
    return build();
  }

  /**
   * 这一行改没改（按字节判定，与通用表格编辑器同一套）。
   *
   * 走 pack.changedStructureRecords 的 rom_offset 集合 ——
   * 改过又改回去不算改。
   */
  rowChanged() {
    const record = this.selected;
    if (!record) return null;
    const changed = new Set(
      this.pack.changedStructureRecords(this.table).map((r) => r.rom_offset));
    return changed.has(record.rom_offset) ? '1' : null;
  }

  /** 「内存分配」那一页：起始地址 + 分配大小 + 结束地址 + 原值。 */
  renderAllocationTab() {
    const record = this.selected;
    const addr = record.values[ADDR_FIELD];
    const size = record.values[SIZE_FIELD];

    this.sizeInput = el('input', {
      class: 'num-input wram-size',
      type: 'text',
      spellcheck: 'false',
      value: String(size),
      oninput: (e) => {
        // 边打边算：还没提交也能看见会不会压到下一段。
        const draft = parseSize(e.target.value);
        this.updateWarnings(draft === null ? size : draft);
      },
      onchange: (e) => {
        const draft = parseSize(e.target.value);
        if (draft === null || draft < 0) {
          toast('请输入字节数', 'error');
          e.target.value = String(size);
          this.updateWarnings(size);
          return;
        }
        this.commitSize(draft);
      },
    });

    this.addrInput = el('input', {
      class: 'num-input wram-addr',
      type: 'text',
      spellcheck: 'false',
      value: hex32(addr),
      onchange: (e) => {
        const draft = parseAddress(e.target.value);
        if (draft === null) {
          toast('请输入十六进制地址', 'error');
          e.target.value = hex32(addr);
          return;
        }
        if (draft < EWRAM_BASE || draft > EWRAM_END) {
          // 越界当场拒绝，不写回。
          toast('EWRAM 地址必须落在 0x02000000–0x0203FFFF', 'error');
          e.target.value = hex32(addr);
          return;
        }
        this.commitAddress(draft);
      },
    });

    this.endLine = el('div', { class: 'field-hint' });
    this.originLine = el('div', { class: 'field-hint' });

    const group = el('div', { class: 'group' }, [
      el('div', { class: 'group-head' }, [
        el('span', { class: 'group-name', text: '内存分配' }),
      ]),
      el('div', { class: 'group-body' }, [
        el('div', { class: 'field' }, [
          el('label', { class: 'field-label' }, [
            el('span', { text: '起始地址（十六进制）' }),
          ]),
          this.addrInput,
          el('div', {
            class: 'field-hint',
            text: 'EWRAM 地址必须落在 0x02000000–0x0203FFFF',
          }),
        ]),
        el('div', { class: 'field' }, [
          el('label', { class: 'field-label' }, [
            el('span', { text: '分配大小（字节）' }),
          ]),
          this.sizeInput,
          el('div', { class: 'field-hint', text: `当前 ${size} 字节（${hex32(size)}）` }),
        ]),
        this.endLine,
        this.originLine,
        el('div', { class: 'field-actions' }, [
          el('button', {
            class: 'btn btn-tiny', text: '↺ 恢复原值',
            onclick: () => this.restore(),
          }),
        ]),
      ]),
    ]);
    this.updateAllocationLines(size);
    return group;
  }

  /** 「邻接关系」那一页：这一段与下一段挨不挨着、会不会压到。 */
  renderNeighborsTab() {
    const record = this.selected;
    this.warnBox = el('div', { class: 'consequence' });
    const group = el('div', { class: 'group' }, [
      el('div', { class: 'group-head' }, [
        el('span', { class: 'group-name', text: '这一段的邻接关系' }),
      ]),
      el('div', { class: 'group-body' }, [this.warnBox]),
    ]);
    this.updateNeighborWarnings(record.values[SIZE_FIELD]);
    return group;
  }

  /** 结束地址 / 原值。 */
  updateAllocationLines(size) {
    const record = this.selected;
    if (!record) return;
    const addr = record.values[ADDR_FIELD];

    if (this.endLine) {
      this.endLine.textContent = `结束地址 ${hex32(addr + size)}`;
    }
    if (this.originLine) {
      const originalSize = record.values[SIZE_FIELD];
      const originalAddr = record.values[ADDR_FIELD];
      this.originLine.textContent = originalAddr === addr && originalSize === size
        ? `原值 ${hex32(originalAddr)} / ${originalSize} 字节`
        : `原值 ${hex32(originalAddr)} / ${originalSize} 字节 → 现在 ${hex32(addr)} / ${size} 字节`;
    }
  }

  /** 邻接与覆盖告警。 */
  updateNeighborWarnings(size) {
    const record = this.selected;
    if (!record || !this.warnBox) return;
    const addr = record.values[ADDR_FIELD];
    const segment = this.segmentOf(record);
    const end = addr + size;

    this.warnBox.textContent = '';
    const lines = [];
    if (segment) {
      const next = this.neighbour(segment);
      if (next) {
        const nextLabel = '#' + next.records[0].id;
        const nextTwins = next.records.length > 1
          ? `（${next.records.map((r) => '#' + r.id).join(' / ')} 是同一块）`
          : '';
        const nextName = this.recordName(next.records[0]);
        if (next.addr === end) {
          lines.push(`下一段：${nextLabel}（${nextName}）从 ${hex32(next.addr)} 开始 —— 与本段紧挨着，没有空隙。${nextTwins}`);
        } else if (next.addr > end) {
          const gap = next.addr - end;
          lines.push(`下一段：${nextLabel}（${nextName}）从 ${hex32(next.addr)} 开始 —— 中间空着 ${gap} 字节。${nextTwins}`);
        } else {
          const over = end - next.addr;
          lines.push(`⚠ 本段已经压到 ${nextLabel}（从 ${hex32(next.addr)} 开始）的前 ${over} 字节。${nextTwins}`);
        }
        const overlap = end > next.addr ? end - next.addr : 0;
        if (overlap > 0) {
          lines.push(`⚠ 把大小改成 ${size} 字节会压到 ${nextLabel}`
            + `（从 ${hex32(next.addr)} 开始）的前 ${overlap} 字节。`);
        }
      } else {
        lines.push('这是最后一段：后面没有别的内存段了。');
      }
      const twins = segment.records.filter((r) => r !== record);
      if (twins.length) {
        lines.push(`⚠ 本段与 ${twins.map((r) => '#' + r.id).join(' / ')} 是同一块内存`
          + `（${hex32(segment.addr)} / ${segment.size} 字节），`
          + `改它等于同时改那 ${segment.records.length} 行。`);
      }
    }
    for (const line of lines) {
      this.warnBox.appendChild(el('div', { class: 'consequence-line', text: line }));
    }
  }

  /** 结束地址 / 原值 / 邻接与覆盖告警。 */
  updateWarnings(size) {
    this.updateAllocationLines(size);
    this.updateNeighborWarnings(size);
  }

  commitSize(size) {
    const record = this.selected;
    if (!record) return;
    this.pack.setValue(this.table, record, SIZE_FIELD, size);
    if (this.ctx.onChange) this.ctx.onChange();
    if (this.sizeInput) this.sizeInput.value = String(size);
    this.renderBand();
    this.renderList();
    this.updateWarnings(size);
    toast(`已改：${this.table.label} #${record.id} 的大小 ${record.values[SIZE_FIELD]} → ${size} 字节`);
  }

  commitAddress(addr) {
    const record = this.selected;
    if (!record) return;
    this.pack.setValue(this.table, record, ADDR_FIELD, addr);
    if (this.ctx.onChange) this.ctx.onChange();
    if (this.addrInput) this.addrInput.value = hex32(addr);
    this.renderBand();
    this.renderList();
    this.renderDetail();
    toast(`已改：${this.table.label} #${record.id} 的起始地址 → ${hex32(addr)}`);
  }

  restore() {
    const record = this.selected;
    if (!record) return;
    const addrField = (this.table.fields || []).find((f) => f.key === ADDR_FIELD);
    const sizeField = (this.table.fields || []).find((f) => f.key === SIZE_FIELD);
    const addr = originalValue(this.table, record, addrField);
    const size = originalValue(this.table, record, sizeField);
    this.pack.setValue(this.table, record, ADDR_FIELD, addr >>> 0);
    this.pack.setValue(this.table, record, SIZE_FIELD, size >>> 0);
    if (this.ctx.onChange) this.ctx.onChange();
    this.renderBand();
    this.renderList();
    this.renderDetail();
    toast(`已恢复 ${this.table.label} #${record.id} 的原值`);
  }

  step(delta) {
    const record = this.selected;
    if (!record) return;
    const records = this.table.records || [];
    const at = records.indexOf(record);
    const next = records[at + delta];
    if (!next) {
      toast(delta > 0 ? '已经是最后一条了' : '已经是第一条了', 'error');
      return;
    }
    this.selected = next;
    this.renderList();
    this.renderDetail();
  }
}
