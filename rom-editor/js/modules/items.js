// 道具
//
// 道具域有两个「主对象」，各有一个统一视图（见 modules/item.js）：
//   忍具 = 记录表的一行 + 忍具名表里的名字 + 它在哪几关掉落
//   奖励 = 奖励表的一行 = 某一关的某一个子奖励
//
// 首页不再把它们拆成四张表各摆一行，而是按主对象合成入口；
// 强化素材名表是独立内容（它有自己的 18 个名字），保持独立行。
import { el } from '../ui.js';
import { renderDomainIndex, renderPanel, summaryTable, entryCard } from './common.js';
import { renderItem, renderReward } from './item.js';

export function renderItems(container, ctx) {
  if (ctx.state.view.panel) {
    const { kind, id, params } = ctx.state.view.panel;
    if (kind === 'item') return renderItem(container, ctx, params || {});
    if (kind === 'reward') return renderReward(container, ctx, params || {});
    return renderPanel(container, ctx, kind, id, params);
  }

  const pack = ctx.pack;
  const items = pack.structure('item_record');
  const reward = pack.structure('reward_table');
  const names = pack.textTable('ninjutsu_names');
  const materials = pack.textTable('material_names');

  const primary = entryCard(ctx, {
    title: '按忍具改',
    headline: `${items ? items.entry_count : 0} 个忍具`,
    desc: '一个忍具 = 记录表的一行 + 忍具名表里的名字 + 它在哪几关掉落。' +
      '记录表那 16 个字节**每一格都有原生代码依据**（2026-10-22 逐字节普查）：' +
      '被读到的格子写明是哪段代码、读成什么宽度，原生代码不读的写「保留」；' +
      '掉落关系改在奖励那一侧，点一下就跳过去。',
    panel: { kind: 'item', id: '忍具' },
    actionLabel: '打开忍具',
  });

  const secondary = entryCard(ctx, {
    title: '按奖励改',
    headline: `${reward ? reward.entry_count : 0} 条奖励`,
    desc: '奖励表一行 = 某一关的某一个子奖励：金币、强化点、等级门槛与 8 个掉落位。' +
      '哪一关用这一条由任务索引表给出，不用自己算下标。',
    panel: { kind: 'reward', id: '奖励' },
    actionLabel: '打开奖励',
  });

  const extra = el('div', { class: 'section' }, [
    el('h3', { text: '强化素材名表（一览，只读参考）' }),
    el('p', { class: 'section-note', text:
      '强化素材是独立内容，不进忍具视图：奖励表的掉落位里「强化素材」这一类用的就是它的下标。' +
      '它自己在上面的表里改。' }),
    materialTable(materials),
  ]);

  renderDomainIndex(container, ctx, {
    primary,
    secondary,
    module: 'items',
    title: '道具',
    subtitle: [
      el('span', { text: `道具记录表 ROM ${romAddress(items)}` }),
      el('span', { text: `忍具名表 ROM ${romAddress(names)}` }),
      el('span', { text: `奖励表 ROM ${romAddress(reward)}` }),
    ],
    intro:
      '道具模块覆盖两件事：忍具本体（记录表的一行 + 忍具名表里的名字 + 它在哪几关掉落），' +
      '以及关卡奖励（奖励表的一行 = 某一关的某一个子奖励）。' +
      '两件事各有自己的统一视图：左边按记录表 / 奖励表列出，右边把同一 id 空间里的其它表作为字段呈现。',
    extra,
    // 忍具与奖励各是**一个**主对象：分成四张表各摆一行，作者会以为要分别进四张表
    // —— 那是细碎，不是清楚。
    groups: [{
      label: '忍具（记录表 + 名表）',
      tables: ['item_record', 'ninjutsu_names'],
      method: '按忍具改',
      strategy: '定宽写回',
      action: '打开忍具',
      onPick: (c) => c.openPanel('item', '忍具', {}),
    }, {
      label: '奖励表（每关的三个子奖励）',
      tables: ['reward_table'],
      method: '按奖励改',
      strategy: '定宽写回',
      action: '打开奖励',
      onPick: (c) => c.openPanel('reward', '奖励', {}),
    }],
    structures: ['item_record', 'reward_table'],
    texts: ['ninjutsu_names', 'material_names'],
  });
}

/** 表在 ROM 里的位置（地址从内容包取，不写死）。 */
function romAddress(table) {
  const offset = table && (table.rom_offset !== undefined ? table.rom_offset : table.pointer_table_offset);
  if (offset === undefined || offset === null) return '—';
  return '0x' + (offset >>> 0).toString(16).toUpperCase();
}

/** 强化素材的名字一览（只读参考，改它请用上面的表）。 */
function materialTable(table) {
  const rows = { head: ['id', '素材名'], body: [] };
  for (const record of (table && table.records) || []) {
    rows.body.push([record.id, record.text || '（空）']);
  }
  return summaryTable(rows);
}
