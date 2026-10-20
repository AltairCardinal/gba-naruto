// 剧情路线：关卡顺序、每关的剧情、任务文本与奖励
import { el, clear } from '../ui.js';
import { renderDomainIndex, renderPanel, summaryTable } from './common.js';

const STAGE_COUNT = 46;
const MAP_BASE = 0x53d910;
const REWARD_BASE = 0x59eae0;

const REWARD_CATEGORIES = ['忍具', '强化素材', '认识卡', '技能'];

export function renderRoute(container, ctx) {
  const panel = ctx.state.view.panel;
  if (panel) {
    if (panel.kind === 'stage') {
      return renderStage(container, ctx, panel.params.stage);
    }
    const { kind, id } = panel;
    return renderPanel(container, ctx, kind, id);
  }

  const pack = ctx.pack;
  const extra = el('div', { class: 'section' }, [
    el('h3', { text: '按关卡查看剧情路线' }),
    el('p', { class: 'section-note' }, [
      '一条路线 = 一串关卡。每关的「战前剧情 → 战场 → 战后剧情」由剧情脚本根表的三组指针串起，' +
      '任务文本与关卡奖励由任务索引表指向奖励表。选一个关卡看完整的一环。',
    ]),
    stagePicker(ctx),
  ]);

  renderDomainIndex(container, ctx, {
    title: '剧情路线',
    subtitle: [
      el('span', { text: '剧情脚本根表 ROM 0x060C74 / 0x060D54' }),
      el('span', { text: '任务索引 ROM 0x348DAC' }),
      el('span', { text: '任务文本表 ROM 0x59AA5C 等' }),
    ],
    intro:
      '剧情路线模块把散落在四张表里的「关卡」信息并成一条可读的路线：' +
      '战前/战后剧情脚本的指针、任务标题/说明/提示、以及该关卡的三个奖励条目。',
    extra,
    structures: ['mission_index', 'story_before_root', 'story_after_root'],
    texts: ['mission_titles', 'mission_descriptions', 'mission_hints'],
  });
}

function stagePicker(ctx) {
  const select = el('select', {
    class: 'search',
    onchange: (e) => {
      ctx.openPanel('stage', 'stage', { stage: Number(e.target.value) });
    },
  });
  for (let s = 1; s <= STAGE_COUNT; s++) {
    select.appendChild(el('option', { value: String(s), text: `第 ${s} 关` }));
  }
  return el('div', { class: 'hex-controls' }, [
    el('span', { text: '选择关卡：' }), select,
  ]);
}

function renderStage(container, ctx, stage) {
  clear(container);
  const pack = ctx.pack;
  container.appendChild(el('div', { style: { marginBottom: '12px' } }, [
    el('button', {
      class: 'btn btn-ghost', text: '← 返回剧情路线',
      onclick: () => { ctx.state.view.panel = null; ctx.render(); },
    }),
  ]));

  const select = el('select', {
    class: 'search',
    onchange: (e) => ctx.openPanel('stage', 'stage', { stage: Number(e.target.value) }),
  });
  for (let s = 1; s <= STAGE_COUNT; s++) {
    select.appendChild(el('option', {
      value: String(s), text: `第 ${s} 关`, selected: s === stage,
    }));
  }
  container.appendChild(el('div', { class: 'panel-head' }, [
    el('div', {}, [
      el('h2', { text: `第 ${stage} 关` }),
      el('div', { class: 'panel-sub' }, [
        el('span', { text: `战场描述符 0x${(MAP_BASE + stage * 32).toString(16).toUpperCase()}` }),
      ]),
    ]),
    el('div', { class: 'panel-tools' }, [select]),
  ]));

  // --- 剧情脚本指针 ----------------------------------------------------
  const scriptRows = { head: ['剧本', '本关脚本首地址'], body: [] };
  for (const [label, id] of [
    ['战前剧情（before）', 'story_before_root'],
    ['战后剧情（after）', 'story_after_root'],
    ['战场事件逻辑', 'story_logic_root'],
    ['战场事件表', 'story_events_root'],
  ]) {
    const structure = pack.structure(id);
    if (!structure) continue;
    const record = structure.records[stage];
    scriptRows.body.push([label, record ? ptrText(record.values.ptr) : '—']);
  }
  container.appendChild(el('div', { class: 'section' }, [
    el('h3', { text: '剧情脚本' }),
    scriptTable(scriptRows),
  ]));

  // --- 任务文本 --------------------------------------------------------
  const titleTable = pack.textTable('mission_titles');
  const descTable = pack.textTable('mission_descriptions');
  const hintTable = pack.textTable('mission_hints');
  const indexStructure = pack.structure('mission_index');
  const baseIndex = indexStructure && indexStructure.records[stage]
    ? indexStructure.records[stage].values.value
    : null;
  const textRows = { head: ['子编号', '文本表下标', '标题', '说明', '提示'], body: [] };
  if (baseIndex !== null) {
    for (let u = 0; u < 3; u++) {
      const slot = baseIndex + u;
      textRows.body.push([
        u,
        slot,
        pick(titleTable, slot),
        pick(descTable, slot),
        pick(hintTable, slot),
      ]);
    }
  }
  container.appendChild(el('div', { class: 'section' }, [
    el('h3', { text: '任务文本' }),
    el('p', { class: 'section-note' }, [
      '任务文本表有 112 个槽位，下标 = 任务索引表[关卡] + 子编号（0..2）；',
      '本关的起点是 ' + (baseIndex === null ? '—' : baseIndex) + '。',
      '文本由指针表驱动，改写时可以改变长度（构建时重定位并改写指针）。',
    ]),
    scriptTable(textRows),
  ]));

  // --- 奖励 ------------------------------------------------------------
  const index = pack.structure('mission_index');
  const rewards = pack.structure('reward_table');
  const itemNames = pack.textTable('ninjutsu_names');
  const materialNames = pack.textTable('material_names');
  const charNames = pack.textTable('character_names');
  const trainingNames = pack.textTable('training_names');
  const rewardRows = { head: ['子奖励', '金币', '强化点', '等级门槛', '掉落'], body: [] };
  if (index && rewards) {
    const base = index.records[stage] ? index.records[stage].values.value : 0;
    for (let u = 0; u < 3; u++) {
      const index_ = base + u;
      const record = rewards.records.find((r) => r.id === index_);
      if (!record) continue;
      const v = record.values;
      const drops = [];
      for (let k = 0; k < 8; k++) {
        const itemId = v[`slot${k}_item`];
        if (!itemId) break;
        const cat = v[`slot${k}_category`];
        drops.push(`${REWARD_CATEGORIES[cat] || '类别' + cat} #${itemId} ${nameOf(cat, itemId)}`);
      }
      rewardRows.body.push([
        `子 ${u + 1}（表下标 ${index_}）`, v.gold, v.upgrade_points, v.tier,
        drops.join('、') || '（无）',
      ]);
    }
  }
  container.appendChild(el('div', { class: 'section' }, [
    el('h3', { text: '本关奖励' }),
    el('p', { class: 'section-note' }, [
      '任务索引表给出该关三个奖励在奖励表里的下标起点，奖励表每条 24 字节：' +
      '金币、强化点、等级门槛，以及 8 个掉落位（低字节是类别、高字节是物品 id，0 表示列表结束）。',
    ]),
    scriptTable(rewardRows),
  ]));

  function nameOf(cat, id) {
    if (cat === 0 && itemNames) return (itemNames.records[id]?.text) || '';
    if (cat === 1 && materialNames) return (materialNames.records[id]?.text) || '';
    if (cat === 2 && charNames) return (charNames.records[id]?.text) || '';
    if (cat === 3 && trainingNames) return (trainingNames.records[id]?.text) || '';
    return '';
  }
}

function scriptTable(rows) {
  return summaryTable(rows);
}

function pick(table, slot) {
  if (!table) return '—';
  const record = table.records[slot];
  if (!record) return '—';
  return record.text ? record.text : '（空）';
}

function ptrText(value) {
  if (!value) return 'NULL';
  return '0x' + (value >>> 0).toString(16).toUpperCase();
}
