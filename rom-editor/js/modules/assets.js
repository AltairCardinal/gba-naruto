// 素材与资源：数据指针表与图块/精灵资源记录表
//
// 这些表在 ROM 里已被证实（tools/table_registry.py 标 verified=True），
// 但它们指向的**资源本体**（LZ77 图形、调色板、图块）不在包里——
// 仓库里没有与原版逐字节一致的 LZ77 压缩器，见 docs/rom-editor.md §7。
import { el } from '../ui.js';
import { renderDomainIndex, renderPanel, summaryTable, entryCard } from './common.js';

export function renderAssets(container, ctx) {
  const panel = ctx.state.view.panel;
  if (panel) {
    const { kind, id } = panel;
    return renderPanel(container, ctx, kind, id);
  }

  const pack = ctx.pack;
  const tableA = pack.structure('data_pointer_table_a');
  const tableB = pack.structure('data_pointer_table_b');

  const rows = { head: ['表', '下标', '指针'], body: [] };
  for (const [label, structure] of [['A', tableA], ['B', tableB]]) {
    if (!structure) continue;
    for (const record of structure.records) {
      if (!record.values.ptr) continue;
      rows.body.push([
        label,
        record.id,
        '0x' + (record.values.ptr >>> 0).toString(16).toUpperCase(),
      ]);
    }
  }

  const extra = el('div', { class: 'section' }, [
    el('h3', { text: '数据指针表' }),
    el('p', { class: 'section-note' }, [
      '这两张表是纯指针表：表里只有地址，资源本体在别处。',
      '改指针等于改「用哪份资源」，但**资源内容本身**要另走导入流程。',
    ]),
    summaryTable(rows),
  ]);

  const primary = entryCard(ctx, {
    title: '按指针表改',
    headline: '两张 u32 指针表',
    desc: '指针表负责「指向哪份资源」；资源本体是 LZ77 压缩载荷，' +
      '仓库里没有与原版逐字节一致的压缩器，所以只能改指针。',
    panel: { kind: 'structure', id: 'data_pointer_table_a' },
    actionLabel: '去改指针表',
  });

  renderDomainIndex(container, ctx, {
    primary,
    module: 'assets',
    title: '素材与资源',
    subtitle: [
      el('span', { text: '数据指针表 A ROM 0x5A143C（46 项）' }),
      el('span', { text: '数据指针表 B ROM 0x5A2034（90 项）' }),
      el('span', { text: '资源记录表 ROM 0x5A320C（79 条）' }),
      el('span', { text: 'WRAM 分配表 ROM 0x53D848（10 组）' }),
    ],
    intro:
      '资源类表：指针表负责「指向哪份」，资源记录表负责「图块与脚本的组合」。' +
      '两者都只呈现指针层，载荷层的改写受限于仓库里缺失的逐字节一致 LZ77 压缩器。',
    extra,
    structures: ['data_pointer_table_a', 'data_pointer_table_b', 'tile_asset_records',
      'wram_allocation'],
    texts: [],
  });
}
