// 角色属性与技能
import { el, clear, formatOffset } from '../ui.js';
import { renderDomainIndex, renderPanel, summaryTable, entryCard } from './common.js';

export function renderCharacters(container, ctx) {
  const panel = ctx.state.view.panel;
  if (panel) {
    const { kind, id } = panel;
    return renderPanel(container, ctx, kind, id);
  }

  const pack = ctx.pack;
  const template = pack.structure('character_template');
  const growth = pack.structure('per_character_stats');
  const perks = pack.structure('character_perks');
  const names = pack.textTable('character_names');
  const training = pack.textTable('training_names');

  const extra = el('div', { class: 'section' }, [
    el('h3', { text: '角色一览' }),
    el('p', { class: 'section-note' }, [
      '角色定义表（0x54241C）63 个槽位：0 是空槽，1..62 是有效角色，与人物名表一一对应。',
      '下表把名字、基础属性、HP 与成长表并到一起。',
    ]),
    summaryTable(characterRows(ctx)),
  ]);

  const primary = entryCard(ctx, {
    title: '按角色改',
    headline: '62 个角色',
    desc: '角色定义表：基础属性 + 15 个忍术槽 + 24 个技能槽 + 9 个道具槽。' +
      '记录按分组折叠，重复槽位是表格而不是上百个输入框。',
    panel: { kind: 'structure', id: 'character_template' },
    actionLabel: '去改角色',
  });

  renderDomainIndex(container, ctx, {
    primary,
    module: 'characters',
    title: '角色属性与技能',
    subtitle: [
      el('span', { text: '角色定义表 ROM 0x54241C' }),
      el('span', { text: '成长表 ROM 0x545068' }),
      el('span', { text: '特性表 ROM 0x5459C8' }),
    ],
    intro:
      '角色定义表每条 0xB4 字节：12 字节头部（六项属性 + 副属性 + HP）、' +
      '15 个忍术槽（id / 等级值 / 解锁等级）、24 个技能槽、9 个道具槽。' +
      '技能槽的 id 同时是特性表（0x5459C8）与技能名表（0x5A7060）的下标。',
    extra,
    structures: ['character_template', 'per_character_stats', 'character_perks',
      'portrait_table', 'portrait_pieces'],
    texts: ['character_names', 'training_names'],
  });
}

function characterRows(ctx) {
  const pack = ctx.pack;
  const template = pack.structure('character_template');
  const growth = pack.structure('per_character_stats');
  const names = pack.textTable('character_names');
  const rows = {
    head: ['id', '姓名', '属性A', '属性B', '属性C', '属性D', '属性E', '属性F',
      '副属性', 'HP', '每级HP成长', '忍术数'],
    body: [],
  };
  if (!template) return rows;
  for (const record of template.records) {
    if (record.id === 0) continue;
    const v = record.values;
    const name = names && names.records[record.id] ? names.records[record.id].text : '';
    const grow = growth && growth.records[record.id] ? growth.records[record.id].values.hp_gain : '';
    let jutsu = 0;
    for (let i = 0; i < 15; i++) {
      if (v[`jutsu_${i}_value`] !== undefined && v[`jutsu_${i}_value`] !== 0xff) jutsu += 1;
    }
    rows.body.push([
      record.id,
      name || '（无名）',
      v.stat_a, v.stat_b, v.stat_c, v.stat_d, v.stat_e, v.stat_f,
      v.aux_stat, v.hp_base, grow, jutsu,
    ]);
  }
  return rows;
}
