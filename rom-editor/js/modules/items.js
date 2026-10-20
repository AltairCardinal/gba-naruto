// 道具
import { el } from '../ui.js';
import { renderDomainIndex, renderPanel, summaryTable } from './common.js';

export function renderItems(container, ctx) {
  if (ctx.state.view.panel) {
    const { kind, id } = ctx.state.view.panel;
    return renderPanel(container, ctx, kind, id);
  }

  const pack = ctx.pack;
  const items = pack.structure('item_record');
  const reward = pack.structure('reward_table');
  const names = pack.textTable('ninjutsu_names');

  // 把「道具记录 × 忍具名表」并成一张作者真正想看的表
  const rows = { head: ['id', '名称', '原始字节（语义未解）'], body: [] };
  if (items && names) {
    for (const record of items.records) {
      const name = names.records[record.id];
      rows.body.push([
        record.id,
        name && name.text ? name.text : '（空）',
        (record.values.raw_00 || '') + ' ' + (record.values.raw_01 || '') + ' ' +
          (record.values.raw_02 || '') + ' …',
      ]);
    }
  }

  const extra = el('div', { class: 'section' }, [
    el('h3', { text: '道具一览（记录 × 名称）' }),
    el('p', { class: 'section-note' }, [
      '道具记录表的 16 个字节在仓库里**没有任何一处证明过字段含义**，所以这里只按原始字节呈现。',
      '名称取自忍具名表（0x599634），二者同为 94 条、下标一一对应。',
    ]),
    summaryTable(rows),
  ]);

  renderDomainIndex(container, ctx, {
    title: '道具',
    subtitle: [
      el('span', { text: '道具记录表 ROM 0x545BE4' }),
      el('span', { text: '忍具名表 ROM 0x599634' }),
      el('span', { text: '奖励表 ROM 0x59EAE0' }),
    ],
    intro:
      '道具模块覆盖三件事：道具本体（94 条 16 字节记录）、道具名称与强化素材名称' +
      '（指针表驱动，可变长），以及关卡奖励表（112 条，含金币、强化点、等级门槛与 8 个道具掉落位）。',
    extra,
    structures: ['item_record', 'reward_table'],
    texts: ['ninjutsu_names', 'material_names'],
  });
}
