// 战斗：战场地图是主界面，右侧页签收纳这一关的其它配置。
//
// 这一关的东西散在四张表里：战场布置（map_table）、角色出生点（battle_actors）、
// 战场物件（battle_map_objects）、战斗目标（battle_rules），
// 外加两根定位战场事件剧本的根指针（story_logic_root / story_events_root）。
//
// 以前它们在「关卡视图」那一长条页面里，作者要在关卡视图与地图之间来回跳。
// 现在**地图是主界面**，右侧页签按类收纳：
// 战场布置 / 战场物件 / 角色出生点 / 胜负条件 / 剧情触发。
import { el } from '../ui.js';
import { renderDomainIndex, renderPanel } from './common.js';
import { renderBattleMap } from './battle-map.js';

/**
 * 战斗域的入口。
 *
 * `panel.kind === 'stage'` 是旧路由（`#battle/stage/40/0`）——
 * 它现在**渲染同一个地图界面**，老深链不会失效。
 */
export function renderBattle(container, ctx) {
  const panel = ctx.state.view.panel;
  if (panel) {
    if (panel.kind === 'stage' || panel.kind === 'map') {
      return renderBattleMap(container, ctx, panel.params.stage, panel.params.variant);
    }
    const { kind, id, params } = panel;
    return renderPanel(container, ctx, kind, id, params);
  }

  // 域首页卡片里的「打开战场地图」跟着上面的关卡下拉走。
  let pickedStage = 1;
  let pickedVariant = 0;
  // 推荐入口：直接进地图（这才是作者真正会走的那条路）。
  const primary = el('div', { class: 'stat entry-card' }, [
    el('div', { class: 'stat-label', text: '按关卡改' }),
    el('div', { class: 'stat-value', style: { fontSize: '14px' }, text: '47 关 × 3 变体' }),
    el('div', {
      class: 'stat-hint',
      text: '战场地图是主界面：左边看着地图，右边按页签改这一关的战场布置、' +
        '战场物件、角色出生点、胜负条件与剧情触发。',
    }),
    stagePicker(ctx, (stage, variant) => { pickedStage = stage; pickedVariant = variant; }),
    el('div', { class: 'entry-actions' }, [
      el('button', {
        class: 'btn btn-primary',
        text: '打开战场地图',
        title: '看这一关的战场长什么样，并在地图上直接布置物件与角色',
        onclick: () => ctx.openPanel('map', 'map', { stage: pickedStage, variant: pickedVariant }),
      }),
    ]),
  ]);

  renderDomainIndex(container, ctx, {
    title: '战斗',
    module: 'battle',
    subtitle: [
      el('span', { text: '战场描述符 ROM 0x53D910（47 条）' }),
      el('span', { text: '编成矩阵 ROM 0x5461C4（47×3×12）' }),
      el('span', { text: '战斗目标 ROM 0x594758（47×3）' }),
    ],
    intro:
      '战斗模块把四张表按原生 id 串起来：战场布置（32 字节描述符，六个 LZ77 资源指针 + 底图 id）、' +
      '角色出生点（编成矩阵，每槽 0xB8 字节，含角色 id / 阵营 / X / Y / 等级）、' +
      '战场物件（16 个槽，类别 + 触发目标 + 格坐标）、' +
      '战斗目标（回合上限 + 4 条胜利条件 + 4 条失败条件）、' +
      '以及两根定位战场事件剧本的根指针。',
    primary,
    // 战场地图把四张按关卡的表收进一个界面，所以域首页不再把它们拆成四行。
    groups: [{
      label: '一关的战斗（战场地图）',
      tables: ['map_table', 'battle_actors', 'battle_map_objects', 'battle_rules'],
      method: '按关卡改',
      strategy: '定宽写回',
      action: '打开战场地图',
      onPick: (c) => c.openPanel('map', 'map', { stage: 1, variant: 0 }),
    }],
    structures: ['battle_encounter_records', 'level_blocks', 'object_descriptors',
      'sprite_action_table', 'unit_slot_remap', 'unit_delta_table',
      'battle_handler_table', 'sprite_frame_descriptors', 'pickup_dispatch',
      'story_logic_root', 'story_events_root'],
    texts: ['battle_objectives'],
  });
}

/** 关卡 + 变体的选择器（域首页用）。 */
function stagePicker(ctx, onPick) {
  const stageSelect = el('select', {
    class: 'search',
    onchange: (e) => {
      const stage = Number(e.target.value);
      if (onPick) onPick(stage, 0);
      ctx.openPanel('map', 'map', { stage, variant: 0 });
    },
  });
  for (let s = 1; s <= 46; s += 1) {
    stageSelect.appendChild(el('option', { value: String(s), text: `第 ${s} 关` }));
  }
  const variantSelect = el('select', {
    class: 'search',
    onchange: (e) => {
      const variant = Number(e.target.value);
      const stage = Number(stageSelect.value);
      if (onPick) onPick(stage, variant);
      ctx.openPanel('map', 'map', { stage, variant });
    },
  });
  for (let v = 0; v < 3; v += 1) {
    variantSelect.appendChild(el('option', { value: String(v), text: `变体 ${v}` }));
  }
  return el('div', { class: 'hex-controls' }, [
    el('span', { text: '关卡：' }), stageSelect,
    el('span', { text: '变体：' }), variantSelect,
    el('span', { class: 'stat-hint', text: '（1–46 为有效关卡）' }),
  ]);
}
