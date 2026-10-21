// 战斗：战场布置 / 角色出生点 / 战斗中的剧情与角色出生 / 战斗目标
import { el, clear, formatOffset, toast } from '../ui.js';
import { renderDomainIndex, renderPanel, summaryTable, operandInput, openInTable } from './common.js';
import { fieldControl } from '../fields.js';

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

/**
 * 条件类型的原版语义。
 *
 * 语义来源见 notes/battle-tables.md §1.1（原版说明文字）与 §1.1.1
 * （类型 2 / 3 的原生断点定案）。
 */
const CONDITION_TYPES = {
  1: '全灭敌方（a=1）/ 我方全灭（a=0）',
  2: '回合用尽 —— 原生根本不读 a/b',
  3: '指定角色已离场',
  6: '获得指定道具',
  7: '剩余体力比较',
  8: '击杀数比较',
  9: '收集物数量比较',
};

/** 每个类型里 a / b 两个字节的原生含义。 */
const CONDITION_PARAMS = {
  1: { a: '阵营（1=胜 / 0=负）', b: '未用' },
  2: { a: '冗余：原生不读', b: '冗余：原生不读' },
  3: { a: '阵营（0=我方 / 1=敌方）', b: '角色 id' },
  6: { a: '道具序号', b: '未用' },
  7: { a: '阵营（0=我方 / 1=对方）', b: '未用' },
  8: { a: '阵营（0=我方 / 1=对方）', b: '未用' },
  9: { a: '阵营（0=我方 / 1=对方）', b: '未用' },
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
    const { kind, id, params } = panel;
    return renderPanel(container, ctx, kind, id, params);
  }

  const pack = ctx.pack;
  // 推荐入口：按关卡看一整关的四件套（这才是作者真正会走的路）。
  const primary = el('div', { class: 'stat entry-card' }, [
    el('div', { class: 'stat-label', text: '按关卡改' }),
    el('div', { class: 'stat-value', style: { fontSize: '14px' }, text: '47 关 × 3 变体' }),
    el('div', {
      class: 'stat-hint',
      text: '一屏看全：战场布置、角色出生点、战场物件、战斗目标、战斗中的剧情。' +
        '出生点与战斗目标可以就地改。',
    }),
    stagePicker(ctx),
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
      '战斗中的剧情与角色出生（战场事件逻辑与事件表两根根指针，剧本里的 0x22 指令从编成矩阵里拉人）、' +
      '战斗目标（回合上限 + 4 条胜利条件 + 4 条失败条件）。',
    primary,
    structures: ['map_table', 'battle_actors', 'battle_map_objects', 'battle_rules',
      'battle_encounter_records', 'level_blocks', 'object_descriptors', 'sprite_action_table'],
    texts: ['battle_objectives'],
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
        // 本关改了几处 —— 与通用表格共用同一个包对象，两边看到的数一致。
        el('span', {
          class: 'stat-hint',
          text: stageChangeCount(ctx, stage, variant)
            ? `本关已改 ${stageChangeCount(ctx, stage, variant)} 处`
            : '本关还没有改动',
        }),
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
    container.appendChild(el('div', { class: 'section' }, [
      el('h3', { text: '战场布置' }),
      el('div', { class: 'kv' }, [
        el('dt', { text: '图块尺寸' }),
        el('dd', { text: `${tilesX} × ${tilesY} 格（原始 ${v.raw_width} × ${v.raw_height}）` }),
        el('dt', { text: '剧情底图 id' }),
        el('dd', { text: `${v.background_id}（底图表 0x59903C）` }),
        el('dt', { text: '图块图形' }),
        el('dd', { text: `${ptrText(v.tile_gfx_ptr)} · LZ77 4bpp 图形` }),
        el('dt', { text: '调色板' }),
        el('dd', { text: `${ptrText(v.palette_ptr)} · LZ77 384 字节` }),
        el('dt', { text: '图层 0' }),
        el('dd', { text: `${ptrText(v.layer0_ptr)} · LZ77 tilemap` }),
        el('dt', { text: '图层 1' }),
        el('dd', { text: v.layer1_ptr ? `${ptrText(v.layer1_ptr)} · LZ77 tilemap` : 'NULL —— 本关无第二层' }),
        el('dt', { text: '组合图块表' }),
        el('dd', { text: `${ptrText(v.metatile_ptr)} · LZ77，8 字节/项` }),
        el('dt', { text: '通行值表' }),
        el('dd', { text: `${ptrText(v.terrain_ptr)} · LZ77，每格 u16` }),
      ]),
      el('p', { class: 'section-note' }, [
        '这六个资源指针指向 **LZ77 压缩载荷**，编辑器里没有与原版逐字节一致的压缩器，' +
        '所以载荷本身改不了；能改的是指针（把指针指向别的资源，等于手工接线）。',
      ]),
      el('div', { class: 'entry-actions' }, [
        openInTable(ctx, 'map_table', stage, `在通用表格中打开战场布置（第 ${stage} 关）`),
      ]),
    ]));
  }

  // --- 角色出生点 ------------------------------------------------------
  const actors = pack.structure('battle_actors');
  const names = pack.textTable('character_names');
  const actorRows = { head: ['槽', '角色id', '姓名', '阵营', 'X', 'Y', '朝向', '等级', '标志', '↗'], body: [] };
  if (actors) {
    const base = ACTORS_BASE + stage * GROUP_STRIDE + variant * VARIANT_STRIDE + 4;
    for (let s = 0; s < 12; s++) {
      const record = actors.records.find((r) => r.rom_offset === base + s * SLOT_STRIDE);
      if (!record) continue;
      const v = record.values;
      const name = names && names.records[v.character_id] ? names.records[v.character_id].text : '';
      actorRows.body.push([
        s,
        numCell(ctx, actors, record, 'character_id', v.character_id),
        name || '（空）',
        sideCell(ctx, actors, record, v),
        numCell(ctx, actors, record, 'x', v.x),
        numCell(ctx, actors, record, 'y', v.y),
        numCell(ctx, actors, record, 'facing', v.facing),
        numCell(ctx, actors, record, 'level', v.level),
        '0x' + (v.unit_flags >>> 0).toString(16).toUpperCase().padStart(8, '0'),
        openInTable(ctx, 'battle_actors', record.id, '↗'),
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
      '角色 id / 阵营 / X / Y / 朝向 / 等级都可以直接改（剧本里的 0x22「把角色加入战斗配置」' +
      '就是从这里取角色与等级，所以改这里等于改战斗中谁出场、在哪出现、几级）。',
      '每行末尾的 ↗ 可以在通用表格里打开同一条记录。',
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
      // 空槽也列出来：只显示用掉的那几个，作者就分不清
      // 「这里本来就没有」和「我刚把它清空了」。
      objectRows.body.push([
        o,
        v.type === 0 && v.target === 0 && v.x === 0 && v.y === 0
          ? el('span', { class: 'stat-hint', text: '（空）' })
          : (OBJECT_TYPES[v.type] || v.type),
        numCell(ctx, objects, record, 'target', v.target),
        numCell(ctx, objects, record, 'x', v.x),
        numCell(ctx, objects, record, 'y', v.y),
      ]);
    }
  }
  container.appendChild(el('div', { class: 'section' }, [
    el('h3', { text: '战场物件（可拾取 / 可触发）' }),
    el('p', { class: 'section-note' }, [
      '物件由「类型」决定外观与音效，由「触发目标」决定触发的剧本（13 项效果表，target 9 是计数装置）。',
      '触发目标与 X/Y 可以直接改。',
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
    const objectiveTable = pack.textTable('battle_objectives');
    const objectiveTexts = objectiveBindings(objectiveTable);
    const rows = { head: ['条件', '类型', '参数A', '参数B', '说明文字（可直接改）'], body: [] };
    for (let g = 0; g < 2; g++) {
      for (let k = 0; k < 4; k++) {
        const label = g === 0 ? `胜利 ${k + 1}` : `失败 ${k + 1}`;
        const type = v[`g${g}_${k}_type`];
        if (type === 0 && v[`g${g}_${k}_a`] === 0 && v[`g${g}_${k}_b`] === 0) continue;
        const params = CONDITION_PARAMS[type] || { a: '未用', b: '未用' };
        const typeField = (rules.fields || []).find((f) => f.key === `g${g}_${k}_type`);
        const aField = (rules.fields || []).find((f) => f.key === `g${g}_${k}_a`);
        const bField = (rules.fields || []).find((f) => f.key === `g${g}_${k}_b`);
        rows.body.push([
          label,
          // 类型用**内容包自带的取值域**渲染成下拉（语义只有一处真相），
          // 而不是这里手写的一张表。
          typeField
            ? fieldControl({ pack, onChange: ctx.onChange }, rules, ruleRecord, typeField).node
            : `${type} · ${CONDITION_TYPES[type] || '未知'}`,
          aField
            ? el('div', {}, [
              numCell(ctx, rules, ruleRecord, aField.key, v[aField.key]),
              el('div', { class: 'stat-hint', text: params.a }),
            ])
            : paramCell(v[`g${g}_${k}_a`], params.a),
          bField
            ? el('div', {}, [
              numCell(ctx, rules, ruleRecord, bField.key, v[bField.key]),
              el('div', { class: 'stat-hint', text: params.b }),
            ])
            : paramCell(v[`g${g}_${k}_b`], params.b),
          descriptionCell(ctx, objectiveTable, objectiveTexts.get(`${ruleRecord.id}:${g}:${k}`)),
        ]);
      }
    }
    container.appendChild(el('div', { class: 'section' }, [
      el('h3', { text: '战斗目标' }),
      el('p', { class: 'section-note' }, [
        `回合上限：${v.turn_limit === 0 ? '无限制' : v.turn_limit}。`,
        '每条记录 4 个胜利条件 + 4 个失败条件；类型与参数都能直接改。',
        '类型 2 的数据写着「指定角色仍在场」，但原生代码根本不读这两个字节，',
        '它比较的是回合计数与回合上限 —— 这一版 ROM 的 type-2 实际表达的是「回合用尽」',
        '（notes/battle-tables.md §1.1.1；2026-10-21 用真实战斗读数证实 0x0202680C 就是回合计数）。',
        '类型 3 是「指定角色已离场」，a=阵营、b=角色 id。',
      ]),
      summaryTable(rows),
      el('p', { class: 'section-note' }, [
        '说明文字被代码用绝对地址引用，只能等长改写：超过原槽位长度时编辑器会拒绝并提示。',
      ]),
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
  //
  // 这里曾经**永远是空的**：筛选只留 logic / events 两类剧本，而带操作数的
  // 恰恰是 before / after 两类（logic / events 的 operands 是空数组）。
  // 于是文案写着「0x1E / 0x1F / 0x23 / 0x22 可改」，实际一处也找不到。
  const operandRows = { head: ['剧本', '指令', '含义', '当前值'], body: [] };
  for (const script of pack.scripts || []) {
    if (script.scene !== stage) continue;
    for (const operand of script.operands || []) {
      operandRows.body.push([
        script.root === 'before' ? '战前剧情'
          : script.root === 'after' ? '战后剧情'
          : script.root === 'logic' ? '战场事件逻辑' : '战场事件表',
        '0x' + operand.opcode.toString(16).toUpperCase(),
        operand.label,
        operandInput(ctx, operand),
      ]);
    }
  }
  if (operandRows.body.length) {
    container.appendChild(el('div', { class: 'section' }, [
      el('h3', { text: '本关剧情脚本里可改的操作数' }),
      el('p', { class: 'section-note' }, [
        '0x1E 决定本关载入哪张地图，0x1F 决定用哪个子配置，0x23 决定队员，' +
        '0x22 是「把角色加入战斗配置」。这些操作数都是定宽的，改它们是原地写，' +
        '不会让脚本里的分支目标失效。',
        '（带操作数的是战前/战后剧本；战场事件逻辑与事件表的指令表由原生代码消费，' +
        '仓库没有证明其字段语义，所以不列为可改。）',
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

/**
 * How many records of this stage (and variant) have been changed.
 *
 * The count comes from the **byte** comparison, so "changed and changed back"
 * does not count — and it is the same judgement the generic table editor
 * makes, so the two views never disagree.
 */
function stageChangeCount(ctx, stage, variant) {
  const pack = ctx.pack;
  let n = 0;
  const actorBase = ACTORS_BASE + stage * GROUP_STRIDE + variant * VARIANT_STRIDE + 4;
  const objectBase = actorBase - 4 + OBJECT_OFFSET;
  const ruleOffset = RULES_BASE + stage * RULE_STAGE_STRIDE + variant * RULE_SUB_STRIDE;
  for (const [id, offsets] of [
    ['battle_actors', Array.from({ length: 12 }, (_, s) => actorBase + s * SLOT_STRIDE)],
    ['battle_map_objects', Array.from({ length: OBJECT_COUNT }, (_, o) => objectBase + o * 4)],
    ['battle_rules', [ruleOffset]],
  ]) {
    const structure = pack.structure(id);
    if (!structure) continue;
    const changed = new Set(pack.changedStructureRecords(structure).map((r) => r.rom_offset));
    for (const offset of offsets) {
      if (changed.has(offset)) n += 1;
    }
  }
  const objectives = pack.textTable('battle_objectives');
  if (objectives) {
    const changed = new Set(pack.changedTextRecords(objectives).map((r) => r.id));
    for (const binding of objectives.bindings || []) {
      if (binding.rule !== stage * VARIANT_COUNT + variant) continue;
      if (changed.has(binding.text_id)) n += 1;
    }
  }
  return n;
}

/**
 * One condition parameter: the raw byte plus what that byte means here.
 */
function paramCell(value, meaning) {
  return el('div', {}, [
    el('code', { text: String(value) }),
    el('div', { class: 'stat-hint', text: meaning }),
  ]);
}

/**
 * One numeric field of a structure record, editable in place.
 *
 * The write-back follows the pack's model: only this field changes, every
 * other byte of the record stays as it was.
 */
function numCell(ctx, structure, record, key, value) {
  if (!structure || !record) return String(value);
  return el('input', {
    class: 'num-input',
    type: 'text',
    style: { width: '64px' },
    value: String(value),
    onchange: (e) => {
      const next = Number(e.target.value);
      if (!Number.isFinite(next) || next < 0 || next > 0xffff) {
        toast('请输入 0–65535', 'error');
        e.target.value = String(value);
        return;
      }
      ctx.pack.setValue(structure, record, key, next);
      ctx.onChange();
      toast(`已改写 ${structure.label} · ${key}`);
    },
  });
}

/**
 * The camp of one battle slot.
 *
 * The camp is bit 0 of `unit_flags` — the byte at +0x01 is *not* read by the
 * formation path, so this control rewrites the flag instead.
 */
function sideCell(ctx, structure, record, values) {
  if (!structure || !record) return String(values.unit_flags & 1);
  const flags = values.unit_flags >>> 0;
  const select = el('select', {
    class: 'search',
    style: { width: '76px' },
    onchange: (e) => {
      const bit = e.target.value === '敌方' ? 1 : 0;
      ctx.pack.setValue(structure, record, 'unit_flags', (flags & ~1) | bit);
      ctx.onChange();
      toast(`已改写 ${structure.label} · 阵营`);
    },
  }, [
    el('option', { value: '我方', text: '我方', selected: (flags & 1) === 0 }),
    el('option', { value: '敌方', text: '敌方', selected: (flags & 1) === 1 }),
  ]);
  return select;
}

/**
 * Map "rule record : group : index" to the sentence that describes it.
 *
 * The battle-objective text table carries the sentences; the `bindings` array
 * says which condition each sentence belongs to (several conditions share one
 * sentence, so the map is not one-to-one).
 */
function objectiveBindings(table) {
  const map = new Map();
  if (!table) return map;
  const records = table.records || [];
  for (const binding of table.bindings || []) {
    const record = records[binding.text_id];
    if (!record) continue;
    map.set(`${binding.rule}:${binding.group}:${binding.index}`, record);
  }
  return map;
}

/**
 * The battle objective's description sentence.
 *
 * The rule record holds an **absolute** pointer to the sentence the player
 * sees on the Conditions page.  The sentence itself lives in the battle
 * objective text table, so it can be shown and edited in place — but only to
 * the same byte length, because the address is baked into the ROM.
 */
function descriptionCell(ctx, textTable, record) {
  if (!record) return el('span', { class: 'stat-hint', text: '—' });
  const text = record.text ?? '';
  const used = ctx.pack.font.encodedLength(text);
  const input = el('input', {
    class: 'text-input-inline',
    type: 'text',
    value: text,
    onchange: (e) => {
      const value = e.target.value;
      const missing = ctx.pack.font.missingCharacters(value);
      if (missing.length) {
        toast(`字库里没有这些字：${missing.join(' ')}`, 'error');
        e.target.value = text;
        return;
      }
      const bytes = ctx.pack.font.encodedLength(value);
      if (record.capacity && bytes + 1 > record.capacity) {
        toast(
          `超长：需要 ${bytes + 1} 字节，槽位只有 ${record.capacity} 字节` +
          '（该说明文字被绝对地址引用，只能等长改写）',
          'error'
        );
        e.target.value = text;
        return;
      }
      ctx.pack.setText(textTable, record, value);
      ctx.onChange();
      toast('已改写战斗目标说明文字');
    },
  });
  return el('div', {}, [
    input,
    el('div', {
      class: 'stat-hint',
      text: `${used} / ${record.capacity} 字节 · ${ptrText(record.pointer)}`,
    }),
  ]);
}

function ptrText(value) {
  if (!value) return 'NULL';
  return '0x' + (value >>> 0).toString(16).toUpperCase();
}
