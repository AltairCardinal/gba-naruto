// 战斗：战场布置 / 角色出生点 / 战斗中的剧情与角色出生 / 战斗目标
import { el, clear, formatOffset } from '../ui.js';
import { renderDomainIndex, renderPanel, summaryTable, operandInput } from './common.js';

const STAGE_COUNT = 47;
const VARIANT_COUNT = 3;
const GROUP_STRIDE = 0x1aac;
const VARIANT_STRIDE = 0x8e4;
const SLOT_STRIDE = 0xb8;
const ACTORS_BASE = 0x5461c4;
const MAP_BASE = 0x53d910;
const RULES_BASE = 0x594758;
const RULE_STAGE_STRIDE = 0xcc;
const RULE_SUB_STRIDE = 0x44;
const OBJECT_OFFSET = 0x8a4;
const OBJECT_COUNT = 16;

const CONDITION_TYPES = {
  1: '全灭敌方 / 覆灭己方',
  2: '指定角色仍在场上',
  3: '指定角色离场',
  6: '获得道具',
  7: '剩余 HP 比较',
  8: '击杀数比较',
  9: '收集数比较',
};

const OBJECT_TYPES = {
  0: '空', 1: '忍具', 2: '强化素材', 3: '专属修行卷轴',
  4: '认识卡', 5: '机关宝箱', 6: '特殊机关', 7: '剧情物件',
};

export function renderBattle(container, ctx) {
  const panel = ctx.state.view.panel;
  if (panel) {
    if (panel.kind === 'stage') {
      return renderStage(container, ctx, panel.params.stage, panel.params.variant);
    }
    const { kind, id } = panel;
    return renderPanel(container, ctx, kind, id);
  }

  const pack = ctx.pack;
  const extra = el('div', { class: 'section' }, [
    el('h3', { text: '按关卡查看战斗' }),
    el('p', { class: 'section-note' }, [
      '原生链路：关卡 id N → 战场描述符 map_table[N] → 编成矩阵 battle_actors[N][变体] → ',
      '战斗目标 battle_rules[N][变体] → 战场事件剧本 story_logic_root[N] / story_events_root[N]。',
      '选一个关卡看完整的四件套。',
    ]),
    stagePicker(ctx),
  ]);

  renderDomainIndex(container, ctx, {
    title: '战斗',
    subtitle: [
      el('span', { text: '战场描述符 ROM 0x53D910（47 条）' }),
      el('span', { text: '编成矩阵 ROM 0x5461C4（47×3×12）' }),
      el('span', { text: '战斗目标 ROM 0x594758（47×3）' }),
    ],
    intro:
      '战斗模块把四张表按原生 id 串起来：战场布置（32 字节描述符，六个 LZ77 资源指针 + 底图 id）、' +
      '角色出生点（编成矩阵，每槽 0xB8 字节，含角色 id / 阵营 / X / Y / 等级）、' +
      '战斗中的剧情与角色出生（战场事件逻辑与事件表两根根指针，剧本里的 0x22 指令从编成矩阵里拉人）、' +
      '战斗目标（回合上限 + 4 条胜利条件 + 4 条失败条件）。',
    extra,
    structures: ['map_table', 'battle_actors', 'battle_map_objects', 'battle_rules',
      'battle_encounter_records', 'level_blocks', 'object_descriptors', 'sprite_action_table'],
    texts: [],
  });
}

function stagePicker(ctx) {
  const select = el('select', {
    class: 'search',
    onchange: (e) => {
      ctx.openPanel('stage', 'stage', {
        stage: Number(e.target.value),
        variant: 0,
      });
    },
  });
  for (let s = 1; s <= 46; s++) {
    select.appendChild(el('option', { value: String(s), text: `第 ${s} 关` }));
  }
  return el('div', { class: 'hex-controls' }, [
    el('span', { text: '选择关卡：' }), select,
    el('span', { class: 'stat-hint', text: '（1–46 为有效关卡）' }),
  ]);
}

export function renderStage(container, ctx, stage, variant) {
  clear(container);
  const pack = ctx.pack;
  container.appendChild(el('div', { style: { marginBottom: '12px' } }, [
    el('button', {
      class: 'btn btn-ghost', text: '← 返回战斗',
      onclick: () => { ctx.state.view.panel = null; ctx.render(); },
    }),
  ]));

  const stageSelect = el('select', {
    class: 'search',
    onchange: (e) => {
      ctx.openPanel('stage', 'stage', { stage: Number(e.target.value), variant });
    },
  });
  for (let s = 1; s <= 46; s++) {
    stageSelect.appendChild(el('option', {
      value: String(s), text: `第 ${s} 关`, selected: s === stage,
    }));
  }
  const variantSelect = el('select', {
    class: 'search',
    onchange: (e) => {
      ctx.openPanel('stage', 'stage', { stage, variant: Number(e.target.value) });
    },
  });
  for (let v = 0; v < VARIANT_COUNT; v++) {
    variantSelect.appendChild(el('option', {
      value: String(v), text: `变体 ${v}`, selected: v === variant,
    }));
  }
  container.appendChild(el('div', { class: 'panel-head' }, [
    el('div', {}, [
      el('h2', { text: `第 ${stage} 关 · 变体 ${variant}` }),
      el('div', { class: 'panel-sub' }, [
        el('span', { text: `战场描述符 0x${(MAP_BASE + stage * 32).toString(16).toUpperCase()}` }),
        el('span', { text: `编成组 0x${(ACTORS_BASE + stage * GROUP_STRIDE).toString(16).toUpperCase()}` }),
        el('span', { text: `目标记录 0x${(RULES_BASE + stage * RULE_STAGE_STRIDE + variant * RULE_SUB_STRIDE).toString(16).toUpperCase()}` }),
      ]),
    ]),
    el('div', { class: 'panel-tools' }, [stageSelect, variantSelect]),
  ]));

  // --- 战场布置 --------------------------------------------------------
  const map = pack.structure('map_table');
  const mapRecord = map ? map.records[stage] : null;
  if (mapRecord) {
    const v = mapRecord.values;
    const tilesX = v.raw_width >> 2;
    const tilesY = v.raw_height >> 1;
    container.appendChild(section('战场布置', 'map_table', [
      ['图块尺寸', `${tilesX} × ${tilesY}`, `原始 ${v.raw_width} × ${v.raw_height}`],
      ['图块图形', ptrText(v.tile_gfx_ptr), 'LZ77 4bpp'],
      ['调色板', ptrText(v.palette_ptr), 'LZ77 384 字节'],
      ['图层 0', ptrText(v.layer0_ptr), 'LZ77 tilemap'],
      ['图层 1', ptrText(v.layer1_ptr), v.layer1_ptr ? 'LZ77 tilemap' : 'NULL —— 本关无第二层'],
      ['组合图块表', ptrText(v.metatile_ptr), 'LZ77，8 字节/项'],
      ['通行值表', ptrText(v.terrain_ptr), 'LZ77，每格 u16'],
      ['剧情底图 id', v.background_id, '指向底图表 0x59903C'],
    ]));
  }

  // --- 角色出生点 ------------------------------------------------------
  const actors = pack.structure('battle_actors');
  const names = pack.textTable('character_names');
  const actorRows = { head: ['槽', '角色id', '姓名', '阵营', 'X', 'Y', '朝向', '等级', '标志'], body: [] };
  if (actors) {
    const base = ACTORS_BASE + stage * GROUP_STRIDE + variant * VARIANT_STRIDE + 4;
    for (let s = 0; s < 12; s++) {
      const record = actors.records.find((r) => r.rom_offset === base + s * SLOT_STRIDE);
      if (!record) continue;
      const v = record.values;
      const name = names && names.records[v.character_id] ? names.records[v.character_id].text : '';
      actorRows.body.push([
        s, v.character_id, name || '（空）',
        (v.unit_flags & 1) ? '敌方' : '我方',
        v.x, v.y, v.facing, v.level,
        '0x' + (v.unit_flags >>> 0).toString(16).toUpperCase().padStart(8, '0'),
      ]);
    }
  }
  container.appendChild(el('div', { class: 'section' }, [
    el('h3', { text: '角色出生点' }),
    el('p', { class: 'section-note' }, [
      '编成矩阵每关 × 每变体 12 个槽位。阵营取自标志位 bit0（编成路径不读 +0x01 那个字节）。' +
      'X/Y 是格坐标，与战场的图块尺寸（' +
      (mapRecord ? `${mapRecord.values.raw_width >> 2} × ${mapRecord.values.raw_height >> 1}` : '—') +
      '）对应。',
    ]),
    summaryTable(actorRows),
  ]));

  // --- 战场物件 --------------------------------------------------------
  const objects = pack.structure('battle_map_objects');
  const objectRows = { head: ['#', '类型', '触发目标', 'X', 'Y'], body: [] };
  if (objects) {
    const base = ACTORS_BASE + stage * GROUP_STRIDE + variant * VARIANT_STRIDE + OBJECT_OFFSET;
    for (let o = 0; o < OBJECT_COUNT; o++) {
      const record = objects.records.find((r) => r.rom_offset === base + o * 4);
      if (!record) continue;
      const v = record.values;
      if (v.type === 0 && v.target === 0 && v.x === 0 && v.y === 0) continue;
      objectRows.body.push([
        o, OBJECT_TYPES[v.type] || v.type, v.target, v.x, v.y,
      ]);
    }
  }
  container.appendChild(el('div', { class: 'section' }, [
    el('h3', { text: '战场物件（可拾取 / 可触发）' }),
    el('p', { class: 'section-note' }, [
      '物件由「类型」决定外观与音效，由「触发目标」决定触发的剧本（13 项效果表，target 9 是计数装置）。',
    ]),
    summaryTable(objectRows),
  ]));

  // --- 战斗目标 --------------------------------------------------------
  const rules = pack.structure('battle_rules');
  const ruleRecord = rules
    ? rules.records.find((r) => r.rom_offset === RULES_BASE + stage * RULE_STAGE_STRIDE + variant * RULE_SUB_STRIDE)
    : null;
  if (ruleRecord) {
    const v = ruleRecord.values;
    const rows = { head: ['条件', '类型', '参数A', '参数B', '说明文本地址'], body: [] };
    for (let g = 0; g < 2; g++) {
      for (let k = 0; k < 4; k++) {
        const label = g === 0 ? `胜利 ${k + 1}` : `失败 ${k + 1}`;
        const type = v[`g${g}_${k}_type`];
        if (type === 0 && v[`g${g}_${k}_a`] === 0 && v[`g${g}_${k}_b`] === 0) continue;
        rows.body.push([
          label,
          `${type} · ${CONDITION_TYPES[type] || '未知'}`,
          v[`g${g}_${k}_a`],
          v[`g${g}_${k}_b`],
          ptrText(v[`g${g}_${k}_text_ptr`]),
        ]);
      }
    }
    container.appendChild(el('div', { class: 'section' }, [
      el('h3', { text: '战斗目标' }),
      el('p', { class: 'section-note' }, [
        `回合上限：${v.turn_limit === 0 ? '无限制' : v.turn_limit}。`,
        '每条记录 4 个胜利条件 + 4 个失败条件；类型 2 的原生行为是「回合耗尽」而不是数据写的「指定角色在场」。',
      ]),
      summaryTable(rows),
    ]));
  }

  // --- 战斗中的剧情与角色出生 -------------------------------------------
  const logic = pack.structure('story_logic_root');
  const events = pack.structure('story_events_root');
  const before = pack.structure('story_before_root');
  const after = pack.structure('story_after_root');
  const scriptRows = { head: ['剧本', '根表', '本关脚本首地址'], body: [] };
  for (const [label, structure] of [
    ['战前剧情', before], ['战后剧情', after],
    ['战场事件逻辑', logic], ['战场事件表', events],
  ]) {
    if (!structure) continue;
    const record = structure.records[stage];
    if (!record) continue;
    scriptRows.body.push([
      label, structure.label, ptrText(record.values.ptr),
    ]);
  }
  container.appendChild(el('div', { class: 'section' }, [
    el('h3', { text: '战斗过程中触发的剧情与角色出生' }),
    el('p', { class: 'section-note' }, [
      '战斗中的剧情由「战场事件逻辑」与「战场事件表」两根根指针定位到本关的剧本。' +
      '剧本里的 0x22 指令「把角色加入战斗配置」会按关卡 id 与变体 id 定位到上面的编成矩阵，' +
      '扫描 12 个槽位找到角色 id 匹配的条目，取出等级并把模板拷进战斗单位。' +
      '因此**在编成矩阵里改角色 id / 等级 / 出生点，就等于改了战斗中谁出场、在哪出现**。',
    ]),
    summaryTable(scriptRows),
  ]));

  // 本关战斗剧本里可改的定宽操作数
  const operandRows = { head: ['指令', '含义', '当前值'], body: [] };
  for (const script of pack.scripts || []) {
    if (script.scene !== stage) continue;
    if (script.root !== 'logic' && script.root !== 'events') continue;
    for (const operand of script.operands || []) {
      operandRows.body.push([
        '0x' + operand.opcode.toString(16).toUpperCase(),
        operand.label,
        operandInput(ctx, operand),
      ]);
    }
  }
  if (operandRows.body.length) {
    container.appendChild(el('div', { class: 'section' }, [
      el('h3', { text: '本关战斗剧本里可改的操作数' }),
      el('p', { class: 'section-note' }, [
        '0x1E 决定本关载入哪张地图，0x1F 决定用哪个子配置，0x23 决定队员，' +
        '0x22 是「把角色加入战斗配置」。这些操作数都是定宽的，改它们是原地写，' +
        '不会让脚本里的分支目标失效。',
      ]),
      summaryTable(operandRows),
    ]));
  }
}

function section(title, structureId, rows) {
  return el('div', { class: 'section' }, [
    el('h3', { text: title }),
    el('div', { class: 'kv' }, rows.flatMap(([k, v, hint]) => [
      el('dt', { text: k }),
      el('dd', { text: v === null || v === undefined ? '—' : String(v) + (hint ? `  (${hint})` : '') }),
    ])),
  ]);
}

function ptrText(value) {
  if (!value) return 'NULL';
  return '0x' + (value >>> 0).toString(16).toUpperCase();
}
