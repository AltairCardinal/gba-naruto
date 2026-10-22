// 角色属性与技能
//
// 一个角色在 ROM 里被拆成五张表（角色定义表 / 逐角色成长表 / 角色特性表 /
// 头像指针表 / 头像拼块表），名字另有两张表。这里把它们合成一个「角色」视图：
// 左边按角色列出，右边是这个角色的各个侧面（详见 modules/character.js）。
import { el } from '../ui.js';
import { renderDomainIndex, renderPanel, summaryTable, entryCard } from './common.js';
import { renderCharacter } from './character.js';
import { arraysIn } from '../slots.js';

export function renderCharacters(container, ctx) {
  const panel = ctx.state.view.panel;
  if (panel) {
    if (panel.kind === 'character') {
      return renderCharacter(container, ctx, panel.params || {});
    }
    const { kind, id, params } = panel;
    return renderPanel(container, ctx, kind, id, params);
  }

  const pack = ctx.pack;
  const template = pack.structure('character_template');
  const growth = pack.structure('per_character_stats');
  const names = pack.textTable('character_names');

  const extra = el('div', { class: 'section' }, [
    el('h3', { text: '角色一览' }),
    el('p', { class: 'section-note' }, [
      '角色定义表（0x54241C）的槽位：第 0 条是空槽，其余每条是一个角色，与人物名表一一对应。',
      '下表把名字、基础属性、HP 与成长表并到一起（只读参考，改请用上面的角色视图）。',
    ]),
    summaryTable(characterRows(ctx)),
  ]);

  const primary = entryCard(ctx, {
    title: '按角色改',
    headline: `${(template ? template.entry_count : 0)} 个角色槽位`,
    desc: '一个角色 = 属性 + 成长 + 每个技能的参数 + 忍术槽 + 技能槽 + 道具槽 + 头像。' +
      '五张表合成一个角色来改，改一处就是改这个角色。',
    onPick: el('button', {
      class: 'btn btn-primary',
      text: '打开角色',
      onclick: () => ctx.openPanel('character', '角色', {}),
    }),
  });

  const secondary = entryCard(ctx, {
    title: '角色定义表',
    headline: '通用表格视图',
    desc: '按分组折叠的原始表视图：适合核对每一条槽位，或改那些还没进角色视图的字节。',
    panel: { kind: 'structure', id: 'character_template' },
    actionLabel: '去改角色定义表',
  });

  renderDomainIndex(container, ctx, {
    primary,
    secondary,
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
      '技能槽的 id 同时是特性表（0x5459C8）与技能名表（0x5A7060）的下标。' +
      '按角色打开视图，属性、成长、技能的参数、头像都在一个角色里一起改。',
    extra,
    // 角色：定义表 + 成长表 + 特性表 + 头像表 + 拼块表 **合成一个「角色」视图**。
    // 分成五行摆着，作者会以为要分别进五张表 —— 那是细碎，不是清楚。
    groups: [{
      label: '角色（定义表 / 成长表 / 特性表 / 头像表 / 拼块表）',
      tables: ['character_template', 'per_character_stats', 'character_perks',
        'portrait_table', 'portrait_pieces'],
      method: '按角色改（一个角色一起改）',
      strategy: '定宽写回',
      action: '打开角色',
      onPick: (c) => c.openPanel('character', '角色', {}),
    }],
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
  // 忍术槽的个数从内容包的重复槽位里取，不写死。
  const jutsuArray = arraysIn(template.fields).find((a) => a.name === 'jutsu');
  const jutsuSlots = jutsuArray ? jutsuArray.rows.size : 0;
  for (const record of template.records) {
    if (record.id === 0) continue;
    const v = record.values;
    const name = names && names.records[record.id] ? names.records[record.id].text : '';
    const grow = growth && growth.records[record.id] ? growth.records[record.id].values.hp_gain : '';
    let jutsu = 0;
    for (let i = 0; i < jutsuSlots; i++) {
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
