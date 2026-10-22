// 素材与资源域：域首页 + 三个任务入口。
//
// 这一域的结论只有一句，而且常驻在首页：**改指针能换资源，载荷本身动不了。**
// 三个入口分别对应三件真能做的事：
//   ① 把某个指针换到别处 → 接线表（两张指针表）
//   ② 看图块 / 精灵资源记录 → 记录表（79 条 × 9 个指针槽）
//   ③ 改某个子系统分到多少内存 → EWRAM 内存条带
//
// 写回只走 pack.setValue；原始字节那一侧不碰。

import { el, clear, formatOffset, clickableArea } from '../ui.js';
import { entryCard, renderPanel } from './common.js';
import { SUBVIEW_LABELS } from '../routing.js';
import {
  PTR_TABLE_A, PTR_TABLE_B, TILE_RECORDS,
  renderWiring, renderAssetRecords, renderPointerOverview,
  pointerOverviewSection, comboStats, hex32,
} from './assets-wiring.js';
import { renderMemoryMap, memoryStats } from './assets-memory.js';

/** 结论横幅（常驻，不折叠）。 */
const BANNER = [
  '结论：改指针能换资源，载荷本身动不了。',
  '这一块的指针决定「用哪一份资源」。指向的图块、调色板、脚本是 ROM 里已经压好/排好的字节，'
  + '编辑器能改的只有「用哪一份」——仓库里只有纯字面量 LZ77 编码器'
  + '（tools/lib/lz77.py::compress_literal），没有与原版逐字节一致的压缩器，所以载荷层不可写。',
  '想改画面内容：去「原始字节」按字节改（那里是显式补丁，构建时按「原字节必须匹配」写回），'
  + '或者把指针接到另一份现成资源上。',
].join('');

export function renderAssets(container, ctx) {
  const panel = ctx.state.view.panel;
  if (panel) {
    const { kind, id, params } = panel;
    if (kind === 'wiring') return renderWiring(container, ctx, params);
    if (kind === 'records') return renderAssetRecords(container, ctx, params);
    if (kind === 'memory') return renderMemoryMap(container, ctx, params);
    if (kind === 'overview') return renderPointerOverview(container, ctx, params);
    if (kind === 'structure') {
      // 这四张表有各自的任务视图（目标摘要 / 邻接告警 / 范围校验），
      // 所以从任何入口进去，看到的都是同一个带校验的视图。
      const view = assetViewKind(ctx.pack.structure(id));
      if (view === 'wiring') {
        return renderWiring(container, ctx, {
          table: id === PTR_TABLE_B ? 'b' : 'a',
          recordId: params && params.recordId,
        });
      }
      if (view === 'records') return renderAssetRecords(container, ctx, params);
      if (view === 'memory') return renderMemoryMap(container, ctx, params);
    }
    return renderPanel(container, ctx, kind, id, params);
  }
  return renderHome(container, ctx);
}

/**
 * 打开本域的一个子视图。
 *
 * 走 `ctx.openPanel`：地址栏同步、浏览器后退键在编辑器里后退。
 * （以前这里不敢用它，是因为路由还不认识这几种面板，改写后的 hash 会在
 * hashchange 里把面板重置掉，视图刚打开就被弹回首页。现在 routing.js
 * 的 SUBVIEW_LABELS 认识它们了。）
 *
 * 面板 id 用中文标签：app.js 的面包屑直接拿它显示（「素材与资源 / 接线表」）。
 */
function openSubView(ctx, kind, params) {
  const id = SUBVIEW_LABELS[kind] || kind;
  if (ctx.openPanel) {
    ctx.openPanel(kind, id, params || {});
    // 无头自检的 openPanel 是空实现，所以这里也直接写一次面板状态。
    if (!ctx.state.view.panel || ctx.state.view.panel.kind !== kind) {
      ctx.state.view.panel = { kind, id, params: params || {} };
      if (ctx.render) ctx.render();
    }
    return;
  }
  ctx.state.view.panel = { kind, id, params: params || {} };
  if (ctx.render) ctx.render();
}

/** 这张表属于哪个任务视图（看字段，不看表名）。 */
function assetViewKind(structure) {
  if (!structure) return null;
  const fields = structure.fields || [];
  if (!fields.length) return null;
  if (fields.some((f) => f.type === 'u32' && /addr/i.test(f.key))) return 'memory';
  if (fields.every((f) => f.type === 'ptr')) return 'wiring';
  if (fields.some((f) => f.type === 'ptr')) return 'records';
  return null;
}

/** 这一列「改法」怎么写：结论式，不是一律「直接改」。 */
function editMethod(structure) {
  const view = assetViewKind(structure);
  if (view === 'wiring' || view === 'records') return '改指针（载荷不可改）';
  if (view === 'memory') return '改地址 / 大小（无运行时校验）';
  return '直接改';
}

const VIEW_ENTRY = {
  wiring: { label: '打开接线表', kind: 'wiring' },
  records: { label: '打开记录表', kind: 'records' },
  memory: { label: '打开内存图', kind: 'memory' },
};

function renderHome(container, ctx) {
  const pack = ctx.pack;
  clear(container);

  const tableA = pack.structure(PTR_TABLE_A);
  const tableB = pack.structure(PTR_TABLE_B);
  const tiles = pack.structure(TILE_RECORDS);
  const wram = pack.structure('wram_allocation');
  const combos = comboStats(pack);
  const memory = memoryStats(pack);

  const subtitle = [];
  for (const table of [tableA, tableB, tiles, wram]) {
    if (!table) continue;
    subtitle.push(el('span', {
      text: `${table.label} ROM ${formatOffset(table.rom_offset)}（${(table.records || []).length} 条）`,
    }));
  }

  container.appendChild(el('div', { class: 'panel-head' }, [
    el('div', {}, [
      el('h2', { text: '素材与资源' }),
      el('div', { class: 'panel-sub' }, subtitle),
    ]),
  ]));

  // 结论横幅：常驻，不折叠。
  container.appendChild(el('div', { class: 'rule-note assets-banner' }, [
    el('span', { class: 'rule-title', text: '结论' }),
    el('span', { text: BANNER }),
  ]));

  // --- 三张任务卡 ------------------------------------------------------
  const cards = [];
  if (tableA && tableB) {
    cards.push(entryCard(ctx, {
      title: '把某个指针换到别处',
      headline: `两张 u32 指针表（${(tableA.records || []).length} + ${(tableB.records || []).length} 槽）`,
      desc: '改这里 = 换一个资源；载荷不动。',
      onPick: el('button', {
        class: 'btn btn-primary',
        text: '打开接线表',
        onclick: () => openSubView(ctx, 'wiring'),
      }),
    }));
  }
  if (tiles) {
    const gfxCount = comboSlotCount(pack, 'gfx');
    const scriptCount = comboSlotCount(pack, 'script');
    cards.push(entryCard(ctx, {
      title: '看图块 / 精灵资源记录',
      headline: `${(tiles.records || []).length} 条 × ${tiles.entry_size || 0} 字节`,
      desc: `${gfxCount} 个图块指针 + ${scriptCount} 个脚本指针。`
        + `${(tiles.records || []).length} 条里只有 ${combos.gfxKinds} 种不同的图块组合。`,
      onPick: el('button', {
        class: 'btn btn-primary',
        text: '打开记录表',
        onclick: () => openSubView(ctx, 'records'),
      }),
    }));
  }
  if (wram) {
    cards.push(entryCard(ctx, {
      title: '改某个子系统分到多少内存',
      headline: `${memory.rows} 行里只有 ${memory.segments} 段不同的 EWRAM`,
      desc: '改大小会直接改动运行时内存布局。',
      onPick: el('button', {
        class: 'btn btn-primary',
        text: '打开内存图',
        onclick: () => openSubView(ctx, 'memory'),
      }),
    }));
  }
  container.appendChild(el('div', { class: 'section' }, [
    el('h3', { text: '从哪儿下手' }),
    el('div', { class: 'card-grid' }, cards),
  ]));

  // --- 本域可编辑内容 --------------------------------------------------
  container.appendChild(renderEditableTable(ctx));

  // --- 指针接线总表 ----------------------------------------------------
  container.appendChild(pointerOverviewSection(ctx));
}

/** 一个重复槽位数组有几个槽（6 个图块指针 / 3 个脚本指针）。 */
function comboSlotCount(pack, name) {
  const table = pack.structure(TILE_RECORDS);
  if (!table) return 0;
  const arrays = (table.fields || []).filter((f) => f.array === name);
  const indexes = new Set(arrays.map((f) => f.index));
  return indexes.size;
}

/** 「本域可编辑内容」表：改法一列写结论，不写「直接改」。 */
function renderEditableTable(ctx) {
  const pack = ctx.pack;
  const section = el('div', { class: 'section' });
  section.appendChild(el('h3', { text: '本域可编辑内容' }));
  const rows = [];
  for (const structure of pack.structures.filter((s) => s.module === 'assets')) {
    const fields = structure.fields || [];
    const known = fields.filter((f) => f.type !== 'hex').length;
    const filler = fields.length - known;
    const changed = pack.changedCountIn(structure);
    const view = assetViewKind(structure);
    const entry = view ? VIEW_ENTRY[view] : null;
    const open = () => {
      if (entry) openSubView(ctx, entry.kind);
      else if (ctx.openPanel) ctx.openPanel('structure', structure.id);
    };
    const row = el('tr', { class: changed ? 'changed' : '' }, [
      el('td', { text: structure.label || structure.id }),
      el('td', { class: 'col-num', text: String((structure.records || []).length) }),
      el('td', { class: 'text-cell', text: `${known} 已知${filler ? ` + ${filler} 原始字节` : ''}` }),
      el('td', {}, [el('span', {
        class: 'pill ' + (view === 'memory' ? 'pill-warn' : 'pill-edit'),
        text: editMethod(structure),
      })]),
      el('td', { text: `定宽写回（${structure.entry_size || 0} 字节/条）` }),
      el('td', { class: 'col-num' }, [changed
        ? el('span', { class: 'pill pill-changed', text: `● ${changed}` })
        : el('span', { class: 'pill', text: '—' })]),
      el('td', {}, [el('button', {
        class: 'btn btn-tiny',
        text: entry ? entry.label : '编辑',
        onclick: open,
      })]),
    ]);
    // 整行都能进 —— 不用瞄准那个小按钮。
    clickableArea(row, open);
    rows.push(row);
  }
  section.appendChild(el('div', { class: 'table-wrap' }, [
    el('table', { class: 'grid domain-tables' }, [
      el('thead', {}, [el('tr', {}, [
        el('th', { text: '表' }),
        el('th', { class: 'col-num', text: '条数' }),
        el('th', { text: '字段' }),
        el('th', { text: '改法' }),
        el('th', { text: '长度策略' }),
        el('th', { class: 'col-num', text: '已改' }),
        el('th', { text: '入口' }),
      ])]),
      el('tbody', {}, rows),
    ]),
  ]));
  return section;
}
