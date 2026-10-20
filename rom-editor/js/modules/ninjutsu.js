// 忍术
import { el } from '../ui.js';
import { renderDomainIndex, renderPanel, summaryTable } from './common.js';

export function renderNinjutsu(container, ctx) {
  const panel = ctx.state.view.panel;
  if (panel) {
    const { kind, id } = panel;
    return renderPanel(container, ctx, kind, id);
  }

  const pack = ctx.pack;
  const record = pack.structure('jutsu_record');
  const names = pack.textTable('jutsu_names');

  const rows = { head: ['id', '忍术名', '成长目标', '每级成长量', '标志位'], body: [] };
  if (record && names) {
    for (const r of record.records) {
      const v = r.values;
      const name = names.records[r.id];
      const growthTargets = [];
      for (let i = 0; i < 6; i++) {
        if (v[`grow_${i}`]) growthTargets.push(`成长${i + 1}=${v[`grow_${i}`]}`);
      }
      rows.body.push([
        r.id,
        name && name.text ? name.text : '（空）',
        v.growth_type === 0 || v.growth_type === 7 ? '不成长' : `目标${v.growth_type}`,
        v.growth_amount,
        '0x' + (v.flags >>> 0).toString(16).toUpperCase().padStart(4, '0'),
      ]);
    }
  }

  const extra = el('div', { class: 'section' }, [
    el('h3', { text: '忍术一览（记录 × 名称）' }),
    el('p', { class: 'section-note' }, [
      '忍术记录表 0x545458 共 87 条，下标即忍术 id，与忍术名表 0x59937C 同号。',
      '角色定义表里的 15 个忍术槽按 id 引用这张表。',
    ]),
    summaryTable(rows),
  ]);

  renderDomainIndex(container, ctx, {
    title: '忍术',
    subtitle: [
      el('span', { text: '忍术记录表 ROM 0x545458（87 条）' }),
      el('span', { text: '忍术名表 ROM 0x59937C（87 条）' }),
    ],
    intro:
      '忍术记录每条 16 字节：六个随等级成长的字节属性 + 一个成长目标选择子 + 每级成长量。' +
      '名表由指针表驱动，改名可以改变长度。',
    extra,
    structures: ['jutsu_record'],
    texts: ['jutsu_names'],
  });
}
