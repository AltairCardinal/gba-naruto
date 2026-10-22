// 剧情路线：一屏一关的「路线工作台」。
//
// 主界面是**这一关的路线走向**（左边），这一关的其它配置收在**右侧页签**里：
//   ① 任务文案 —— 3 个子任务的标题 / 说明 / 提示，就地可改
//   ② 本关奖励 —— 金币 / 强化点 / 等级门槛 + 8 个掉落位，就地可改
// 路线走向留在左边常驻：它是这一关的骨架，不该被藏进页签。
//
// 写回通路全在内容包里（pack.setText / pack.setValue / pack.setScriptOperand），
// 所以作者不用跳去别的域再自己算下标。语义只从内容包取：路线边来自
// pack.scripts[].route，槽位归属来自 mission_index（xref.js），字段取值域
// 来自 field.enum / field.relation。

import { el, clear, toast } from '../ui.js';
import {
  renderDomainIndex, renderPanel, summaryTable,
  openInModule,
} from './common.js';
import { splitPane } from '../split.js';
import { CardStack } from '../cards.js';
import { missionIndexOwners, ownerLabel } from '../xref.js';
import { arraysIn, renderArrayTable } from '../slots.js';
import { fieldControl } from '../fields.js';
import { renderMission } from './mission.js';
import {
  renderRouteGraph, STAGE_COUNT, MAX_SCENE, OP_AFTER, OP_CURSOR,
  afterSceneSet, collectEdges, scriptLabel, edgeTable,
} from './route-graph.js';

export { renderRouteGraph };

/** 剧情脚本根表：本关四个剧本的首地址。 */
const SCRIPT_ROOTS = [
  ['战前剧情（before）', 'story_before_root'],
  ['战后剧情（after）', 'story_after_root'],
  ['战场事件逻辑', 'story_logic_root'],
  ['战场事件表', 'story_events_root'],
];

/** 任务文本表：标题 / 说明 / 提示。 */
const MISSION_TEXTS = [
  ['标题', 'mission_titles'],
  ['说明', 'mission_descriptions'],
  ['提示', 'mission_hints'],
];

export function renderRoute(container, ctx) {
  const panel = ctx.state.view.panel;
  if (panel) {
    if (panel.kind === 'stage') {
      return renderStage(container, ctx, panel.params.stage);
    }
    if (panel.kind === 'graph') {
      return renderRouteGraph(container, ctx);
    }
    if (panel.kind === 'mission') {
      return renderMission(container, ctx, panel.params || {});
    }
    const { kind, id, params } = panel;
    return renderPanel(container, ctx, kind, id, params);
  }

  const pack = ctx.pack;
  const edges = collectEdges(pack);
  const primary = el('div', { class: 'stat entry-card' }, [
    el('div', { class: 'stat-label', text: '按关卡改' }),
    el('div', { class: 'stat-value', style: { fontSize: '14px' }, text: `${STAGE_COUNT} 关的完整一环` }),
    el('div', {
      class: 'stat-hint',
      text: '一屏看全：战前剧情 → 战场 → 战后剧情、任务文案、奖励。',
    }),
    el('div', { class: 'entry-actions' }, [
      el('button', {
        class: 'btn btn-primary',
        text: '打开第 1 关',
        onclick: () => ctx.openPanel('stage', 'stage', { stage: 1 }),
      }),
    ]),
    stagePicker(ctx),
  ]);
  const secondary = el('div', { class: 'stat entry-card' }, [
    el('div', { class: 'stat-label', text: '整条路线' }),
    el('div', { class: 'stat-value', style: { fontSize: '14px' }, text: `${edges.length} 条路线边` }),
    el('div', {
      class: 'stat-hint',
      text: '每一关的出边、谁会跳到这一关，以及全游戏的路线边一览。',
    }),
    el('div', { class: 'entry-actions' }, [
      el('button', {
        class: 'btn',
        text: '看整条路线',
        onclick: () => ctx.openPanel('graph', 'graph', {}),
      }),
    ]),
  ]);

  renderDomainIndex(container, ctx, {
    module: 'route',
    title: '剧情路线',
    subtitle: [
      el('span', { text: '剧情脚本根表 ROM 0x060C74 / 0x060D54' }),
      el('span', { text: '任务索引 ROM 0x348DAC' }),
      el('span', { text: '任务文本表 ROM 0x59AA5C 等' }),
    ],
    intro:
      '剧情路线模块把散落在几张表里的「关卡」信息并成一条可读的路线：' +
      '战前/战后剧情脚本的指针、任务标题/说明/提示、以及该关卡的三个奖励条目。' +
      '按关卡打开工作台，任务文案与奖励都能就地改；' +
      '要单独改任务，切到「任务」视图 —— 四张任务表在那边合成一个任务来改。',
    primary,
    secondary,
    // 任务：索引表 + 标题表 + 说明表 + 提示表 **合成一个「任务」视图**。
    // 分成四行摆着，作者会以为要分别进四张表 —— 那是细碎，不是清楚。
    groups: [{
      label: '任务（索引表 + 标题表 + 说明表 + 提示表）',
      tables: ['mission_index', 'mission_titles', 'mission_descriptions', 'mission_hints'],
      method: '按关卡改（一个任务一起改）',
      strategy: '文本可重定位 / 奖励定宽写回',
      action: '打开任务',
      onPick: (c) => c.openPanel('mission', '任务', {}),
    }],
    structures: ['story_before_root', 'story_after_root'],
    texts: [],
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

// ---------------------------------------------------------------------------
// 关卡工作台
// ---------------------------------------------------------------------------

export function renderStage(container, ctx, stage) {
  clear(container);
  const root = el('div', { class: 'route-workbench', tabindex: '-1' });
  container.appendChild(root);

  // 工作台自己维护的少量状态：标题输入框（键盘 1/2/3 要聚焦）、卡片堆。
  const view = { titleInputs: [], cards: null };

  // 改完奖励要重画奖励那一块（改类别会让物品下拉换一批选项）。
  const paintRewards = () => {
    if (view.cards) view.cards.refresh();
  };

  const cards = new CardStack([
    {
      id: 'mission',
      label: '任务文案',
      hint: '3 个子任务的标题 / 说明 / 提示',
      badge: () => missionChanged(ctx, stage),
      render: () => missionSection(ctx, stage, view),
    },
    {
      id: 'reward',
      label: '本关奖励',
      hint: '金币 / 强化点 / 等级门槛 + 8 个掉落位',
      badge: () => rewardChanged(ctx, stage),
      render: () => rewardSection(ctx, stage, view, paintRewards),
    },
  ], { pack: ctx.pack });
  view.cards = cards;

  const paint = () => {
    clear(root);
    view.titleInputs = [];
    root.appendChild(stageBar(ctx, stage));
    // 左边是主界面：这一关的路线走向常驻可见。
    // 右边是卡片：任务文案与本关奖励。
    root.appendChild(splitPane(
      el('div', { class: 'route-main' }, [routeSection(ctx, stage)]),
      el('div', { class: 'route-side' }, [cards.element]),
      { key: 'editor.route.stage', defaultWidth: 460 }
    ));
    cards.refresh();
  };
  paint();

  // 键盘：焦点落在工作台容器上时生效（不改 app.js 的全局流程）。
  const onKey = (e) => handleKey(e, ctx, stage, view);
  root.addEventListener('keydown', onKey);
  installContainerKey(container, root, ctx, onKey);
  if (typeof root.focus === 'function') root.focus();
}

/**
 * 这一关的任务文案改了几处（按字节判定）。
 */
function missionChanged(ctx, stage) {
  const pack = ctx.pack;
  const base = missionBase(pack, stage);
  if (base === null) return null;
  let n = 0;
  for (const [, id] of MISSION_TEXTS) {
    const table = pack.textTable(id);
    if (!table) continue;
    const changed = new Set(pack.changedTextRecords(table).map((r) => r.id));
    for (let u = 0; u < 3; u += 1) {
      if (changed.has(base + u)) n += 1;
    }
  }
  return n || null;
}

/**
 * 这一关的奖励改了几处（按字节判定）。
 */
function rewardChanged(ctx, stage) {
  const pack = ctx.pack;
  const base = missionBase(pack, stage);
  const rewards = pack.structure('reward_table');
  if (base === null || !rewards) return null;
  const changed = new Set(pack.changedStructureRecords(rewards).map((r) => r.id));
  let n = 0;
  for (let u = 0; u < 3; u += 1) {
    if (changed.has(base + u)) n += 1;
  }
  return n || null;
}

/**
 * 容器上也挂一份 keydown（有些宿主只在容器上派发事件）。
 *
 * 换域之后这个监听还留在容器上，所以每次进关卡视图先把上一个摘掉，
 * 并且只在「当前确实是剧情路线的关卡视图」时才动手。
 */
let installedKey = null;
function installContainerKey(container, root, ctx, onKey) {
  if (installedKey) {
    const old = installedKey;
    if (typeof old.container.removeEventListener === 'function') {
      old.container.removeEventListener('keydown', old.handler);
    }
  }
  const handler = (e) => {
    if (!isRouteStageView(ctx)) return;
    const target = e && e.target;
    if (target && target !== root && !isInside(target, root)) return;
    onKey(e);
  };
  installedKey = { container, handler };
  container.addEventListener('keydown', handler);
}

function isRouteStageView(ctx) {
  const view = ctx && ctx.state && ctx.state.view;
  if (!view) return false;
  if (view.module && view.module !== 'route') return false;
  const panel = view.panel;
  return !!panel && panel.kind === 'stage';
}

function isInside(node, root) {
  let cur = node;
  while (cur) {
    if (cur === root) return true;
    cur = cur.parentNode;
  }
  return false;
}

function isTextEntry(node) {
  if (!node) return false;
  const tag = String(node.tagName || '').toUpperCase();
  return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT';
}

function handleKey(e, ctx, stage, view) {
  if (!e) return;
  const key = e.key;
  if (key === 'Escape') {
    swallow(e);
    goHome(ctx);
    return;
  }
  // 焦点在输入框里时不抢键（Ctrl+Z 之类的全局键更不能抢）。
  if (isTextEntry(e.target)) return;
  if (key === ']' || key === 'ArrowRight') {
    swallow(e);
    gotoStage(ctx, stage + 1);
    return;
  }
  if (key === '[' || key === 'ArrowLeft') {
    swallow(e);
    gotoStage(ctx, stage - 1);
    return;
  }
  if (key === 'g' || key === 'G') {
    swallow(e);
    openGraph(ctx);
    return;
  }
  if (key === '1' || key === '2' || key === '3') {
    swallow(e);
    // 标题输入框在「任务文案」那张卡片里 —— 卡片全都可见，直接聚焦就行。
    const input = view.titleInputs[Number(key) - 1];
    if (input && typeof input.focus === 'function') input.focus();
  }
}

/**
 * 吃掉这个键。
 *
 * 只对**本视图自己处理**的键调用：Ctrl+Z 是 app.js 在 document 上接的全局
 * 撤销，拦掉它作者就没法撤销了。
 */
function swallow(e) {
  if (typeof e.preventDefault === 'function') e.preventDefault();
  if (typeof e.stopPropagation === 'function') e.stopPropagation();
}

function gotoStage(ctx, stage) {
  if (!Number.isFinite(stage) || stage < 1 || stage > STAGE_COUNT) return;
  ctx.openPanel('stage', 'stage', { stage });
}

function openGraph(ctx) {
  ctx.openPanel('graph', 'graph', {});
}

function goHome(ctx) {
  if (ctx.goModule) {
    ctx.goModule('route');
    return;
  }
  ctx.state.view.panel = null;
  ctx.render();
}

// ---------------------------------------------------------------------------
// ① 关卡条
// ---------------------------------------------------------------------------

function stageBar(ctx, stage) {
  const bar = el('div', { class: 'stage-bar' });
  bar.appendChild(el('button', {
    class: 'btn btn-ghost',
    text: '← 上一关',
    disabled: stage <= 1,
    onclick: () => gotoStage(ctx, stage - 1),
  }));

  const select = el('select', {
    class: 'search',
    onchange: (e) => gotoStage(ctx, Number(e.target.value)),
  });
  for (let s = 1; s <= STAGE_COUNT; s++) {
    select.appendChild(el('option', {
      value: String(s), text: `第 ${s} 关`, selected: s === stage,
    }));
  }
  bar.appendChild(select);

  bar.appendChild(el('button', {
    class: 'btn btn-ghost',
    text: '下一关 →',
    disabled: stage >= STAGE_COUNT,
    onclick: () => gotoStage(ctx, stage + 1),
  }));
  bar.appendChild(routeMap(ctx, stage));
  bar.appendChild(el('button', {
    class: 'btn',
    text: '整条路线总览',
    onclick: () => openGraph(ctx),
  }));

  const count = stageChangeCount(ctx, stage);
  bar.appendChild(el('div', {
    class: 'stage-bar-count',
    text: count.total
      ? `本关已改 ${count.total} 处（${count.parts.join(' · ')}）`
      : '本关还没改过',
  }));
  return bar;
}

/** 缩略路线点：当前关前后各三关，点一下就跳过去。 */
function routeMap(ctx, stage) {
  const map = el('div', { class: 'route-map' });
  const from = Math.max(1, stage - 3);
  const to = Math.min(STAGE_COUNT, stage + 3);
  if (from > 1) map.appendChild(el('span', { class: 'route-dot-gap', text: '‹' }));
  for (let s = from; s <= to; s++) {
    map.appendChild(el('button', {
      class: 'route-dot' + (s === stage ? ' current' : ''),
      text: s === stage ? '◆' : '●',
      title: `第 ${s} 关`,
      onclick: () => gotoStage(ctx, s),
    }));
  }
  if (to < STAGE_COUNT) map.appendChild(el('span', { class: 'route-dot-gap', text: '›' }));
  return map;
}

/**
 * 本关改了几处。
 *
 * 判定走的是**字节比较**（pack.changedStructureRecords / changedTextRecords），
 * 所以「改了又改回来」不算数；剧本操作数走补丁表（before_hex ≠ after_hex）。
 */
function stageChangeCount(ctx, stage) {
  const pack = ctx.pack;
  const base = missionBase(pack, stage);
  const parts = [];
  let total = 0;

  let task = 0;
  for (const [, id] of MISSION_TEXTS) {
    const table = pack.textTable(id);
    if (!table) continue;
    const changed = new Set(pack.changedTextRecords(table).map((r) => r.id));
    for (let u = 0; u < 3; u++) {
      if (base !== null && changed.has(base + u)) task += 1;
    }
  }
  if (task) parts.push(`任务 ${task}`);

  let reward = 0;
  const rewards = pack.structure('reward_table');
  if (rewards && base !== null) {
    const changed = new Set(pack.changedStructureRecords(rewards).map((r) => r.id));
    for (let u = 0; u < 3; u++) {
      if (changed.has(base + u)) reward += 1;
    }
  }
  if (reward) parts.push(`奖励 ${reward}`);

  let next = 0;
  let other = 0;
  for (const script of pack.scripts || []) {
    if (script.scene !== stage) continue;
    for (const operand of script.operands || []) {
      if (!operandChanged(pack, operand)) continue;
      if (operand.opcode === OP_AFTER || operand.opcode === OP_CURSOR) next += 1;
      else other += 1;
    }
  }
  if (next) parts.push(`下一场景 ${next}`);
  if (other) parts.push(`操作数 ${other}`);

  total = task + reward + next + other;
  return { total, parts };
}

/** 这个操作数所在的字节被改过吗。 */
function operandChanged(pack, operand) {
  for (const patch of pack.patches || []) {
    const after = patch.after_hex || '';
    if (!after) continue;
    const length = after.length / 2;
    if (operand.rom_offset < patch.offset) continue;
    if (operand.rom_offset >= patch.offset + length) continue;
    if (after !== (patch.before_hex || '')) return true;
  }
  return false;
}

// ---------------------------------------------------------------------------
// ① 路线走向
// ---------------------------------------------------------------------------

function routeSection(ctx, stage) {
  const pack = ctx.pack;
  const afterSet = afterSceneSet(pack);
  const edges = collectEdges(pack);
  const outEdges = edges.filter((e) => e.script.scene === stage);
  const inEdges = edges.filter((e) => e.edge.scene === stage);

  const section = el('div', { class: 'section' });
  section.appendChild(el('h3', { text: '路线走向（剧情脚本里的「下一场景」）' }));
  section.appendChild(el('p', { class: 'section-note', text: [
    '剧情路线由剧情脚本里的两条指令连起来：0x16 = 转到 after 剧本并记住下一场景；',
    '0x1A = 直接推进路线游标。',
    '路线边不在表里，它们是剧情脚本里的指令；这些操作数是定宽的，改它们不会移动任何字节。',
  ] }));

  // 本关四个剧本的首地址
  const pointers = [];
  for (const [label, id] of SCRIPT_ROOTS) {
    const structure = pack.structure(id);
    const record = structure ? structure.records[stage] : null;
    pointers.push(`${label} ${record ? ptrText(record.values.ptr) : '—'}`);
  }
  section.appendChild(el('div', { class: 'kv' }, [
    el('dt', { text: '本关剧本' }),
    el('dd', { text: pointers.join(' · ') }),
  ]));

  // 本关出边
  section.appendChild(el('h4', { class: 'route-sub', text: `本关出边（${outEdges.length} 条）` }));
  if (outEdges.length) {
    section.appendChild(edgeTable(ctx, outEdges, afterSet));
  } else {
    section.appendChild(el('div', { class: 'empty', text: '本关的剧本里没有路线指令。' }));
  }

  // 谁会跳到本关
  section.appendChild(el('h4', { class: 'route-sub', text: `谁会跳到本关（${inEdges.length} 条）` }));
  if (inEdges.length) {
    section.appendChild(edgeTable(ctx, inEdges, afterSet));
  } else {
    section.appendChild(el('div', {
      class: 'empty',
      text: '还没有别的关卡跳到本关——本关靠顺序推进到达。',
    }));
  }

  // 本关的下一场景 / 相位标志
  section.appendChild(el('h4', { class: 'route-sub', text: '本关的下一场景' }));
  const operandRows = [];
  for (const script of pack.scripts || []) {
    if (script.scene !== stage) continue;
    for (const edge of script.route || []) {
      if (edge.op !== OP_AFTER && edge.op !== OP_CURSOR) continue;
      const sceneOperand = (script.operands || []).find(
        (o) => o.rom_offset === edge.scene_rom_offset
      );
      if (!sceneOperand) continue;
      const flagOperand = (script.operands || []).find(
        (o) => o.rom_offset === edge.scene_rom_offset + 1
      );
      operandRows.push(el('div', { class: 'route-operand-row' }, [
        el('span', { class: 'operand-label', text: scriptLabel(script) }),
        el('span', { class: 'route-operand-name', text: '下一场景 id' }),
        sceneSelect(ctx, sceneOperand, afterSet),
        flagOperand ? el('span', { class: 'route-operand-name', text: '相位标志' }) : null,
        flagOperand ? flagSelect(ctx, flagOperand) : null,
        el('span', {
          class: 'stat-hint',
          text: `ROM 0x${Number(sceneOperand.rom_offset).toString(16).toUpperCase()}`,
        }),
      ]));
    }
  }
  if (operandRows.length) {
    section.appendChild(el('div', { class: 'route-operands' }, operandRows));
  } else {
    section.appendChild(el('div', { class: 'empty', text: '本关没有可改的「下一场景」操作数。' }));
  }

  // 全游戏一览（默认折叠）
  const afterCount = edges.filter((e) => e.edge.op === OP_AFTER).length;
  const afterZero = edges.filter((e) => e.edge.op === OP_AFTER && e.edge.scene === 0).length;
  section.appendChild(el('details', { class: 'route-all-edges' }, [
    el('summary', { text: `一览（全部 ${edges.length} 条路线边）` }),
    el('p', { class: 'section-note', text: [
      `${afterCount} 处 0x16 指令里 ${afterZero} 处的目标是 0；`,
      '仓库只证明了 0x16 会切到 after 剧本并把场景号写进 state[0x1A]，',
      '没有证明 0 等于「留在本关」。',
    ] }),
    edgeTable(ctx, edges, afterSet),
  ]));

  return section;
}

/**
 * 「下一场景 id」下拉。
 *
 * 选项只列 `story_after_root` 里指针非空、场景号落在 1..55 的场景；
 * 当前值不在表内时补一项，免得作者看见一个空白的当前值。
 */
function sceneSelect(ctx, operand, afterSet) {
  const current = Number(operand.value);
  const select = el('select', {
    class: 'search',
    onchange: (e) => {
      const next = Number(e.target.value);
      if (!Number.isFinite(next) || next < 0 || next > MAX_SCENE) {
        toast(`场景号只能是 0–${MAX_SCENE}，第 ${MAX_SCENE + 1} 号没有剧本。`, 'error');
        e.target.value = String(current);
        return;
      }
      commitOperand(ctx, operand, next);
      toast(`已改写 0x${Number(operand.rom_offset).toString(16).toUpperCase()} · 下一场景 ${next}`);
    },
  });
  select.appendChild(el('option', {
    value: '0', text: '0 · 场景 0', selected: current === 0,
  }));
  for (const n of [...afterSet].sort((a, b) => a - b)) {
    select.appendChild(el('option', {
      value: String(n), text: `${n} · 第 ${n} 关 · after 剧本`, selected: current === n,
    }));
  }
  if (current !== 0 && !afterSet.has(current)) {
    select.appendChild(el('option', {
      value: String(current),
      text: `${current} · 当前值（该场景没有 after 剧本）`,
      selected: true,
    }));
  }
  return select;
}

/**
 * 「相位标志」下拉（0x1A 的第二个操作数）。
 *
 * 0 是「普通推进」，非 0 是「带相位」（state[0x18] = 标志 + 1）。
 */
function flagSelect(ctx, operand) {
  const current = Number(operand.value);
  const nonZero = current !== 0 ? current : 1;
  const select = el('select', {
    class: 'search',
    onchange: (e) => {
      const next = Number(e.target.value);
      if (!Number.isFinite(next) || next < 0 || next > 0xff) {
        toast('相位标志只能是 0–255', 'error');
        e.target.value = String(current);
        return;
      }
      commitOperand(ctx, operand, next);
      toast(`已改写 0x${Number(operand.rom_offset).toString(16).toUpperCase()} · 相位标志 ${next}`);
    },
  });
  select.appendChild(el('option', {
    value: '0', text: '0 · 普通推进', selected: current === 0,
  }));
  select.appendChild(el('option', {
    value: String(nonZero),
    text: '非 0 · 带相位（state[0x18] = 标志+1）',
    selected: current !== 0,
  }));
  return select;
}

// ---------------------------------------------------------------------------
// ② 任务文案
// ---------------------------------------------------------------------------

function missionSection(ctx, stage, view) {
  const pack = ctx.pack;
  const base = missionBase(pack, stage);
  const owners = missionIndexOwners(pack);

  // 页签是懒渲染的：这一页每次被构建时，标题输入框要重新收集一遍
  // （键盘 1/2/3 靠它聚焦）。
  view.titleInputs = [];

  const section = el('div', { class: 'section' });
  section.appendChild(el('h3', { text: '任务文案（标题 / 说明 / 提示）' }));
  section.appendChild(el('p', { class: 'section-note', text: [
    '每关 3 个子任务，任务文本表下标 = 任务索引表[关卡] + 子编号。',
    '文本由指针表驱动，改长会在构建时重定位并改写指针。',
  ] }));

  if (base === null) {
    section.appendChild(el('div', { class: 'empty', text: '任务索引表里没有这一关。' }));
    return section;
  }

  const rows = { head: ['子任务', '标题', '说明', '提示'], body: [] };
  for (let u = 0; u < 3; u++) {
    const slot = base + u;
    const cells = MISSION_TEXTS.map(([label, id]) => {
      const table = pack.textTable(id);
      return missionTextCell(ctx, table, slot, label, owners, stage, u, view, id === 'mission_titles');
    });
    rows.body.push([`子 ${u + 1}`, ...cells]);
  }
  section.appendChild(summaryTable(rows));
  return section;
}

/**
 * 一格任务文案：输入框 + 当前文本 + 归属脚注。
 *
 * 脚注三件事：这一格在文本表里的下标、这个下标同时属于哪几关、
 * 这段字被几处共用（改一处会一起变）。
 */
function missionTextCell(ctx, table, slot, label, owners, stage, sub, view, isTitle) {
  if (!table) {
    return el('div', { class: 'route-text-cell' }, [
      el('div', { class: 'stat-hint', text: '（没有这张文本表）' }),
    ]);
  }
  const record = table.records[slot];
  if (!record) {
    return el('div', { class: 'route-text-cell' }, [
      el('div', { class: 'stat-hint', text: '（这一格没有文本）' }),
    ]);
  }
  const preview = el('div', { class: 'route-text-preview' });
  const update = () => {
    const bytes = ctx.pack.font.encodedLength(record.text || '');
    preview.textContent = `${displayText(record.text)} · ${bytes} 字节`;
  };
  update();
  const input = el('input', {
    class: 'text-input-inline',
    type: 'text',
    spellcheck: 'false',
    value: record.text || '',
    onchange: (e) => {
      const value = e.target.value;
      const missing = ctx.pack.font.missingCharacters(value);
      if (missing.length) {
        toast(`字库里没有这些字：${missing.join(' ')}`, 'error');
        e.target.value = record.text || '';
        return;
      }
      ctx.pack.setText(table, record, value);
      ctx.onChange();
      update();
      const shared = (record.shared_with || []).length + 1;
      toast(shared > 1
        ? `已改写${table.label} #${slot} · 这段字被 ${shared} 处共用，已一起改`
        : `已改写${table.label} #${slot}`);
    },
  });
  if (isTitle) view.titleInputs.push(input);
  return el('div', { class: 'route-text-cell' }, [
    input,
    preview,
    el('div', {
      class: 'shared-note',
      text: slotFootnote('文本表下标', slot, owners, stage, sub, record),
    }),
  ]);
}

/**
 * 槽位的归属脚注。
 *
 * 归属用 mission_index 算（xref.js::missionIndexOwners）：下标不是
 * 3 × (关卡 − 1)，有一批槽位被好几关共用。
 */
function slotFootnote(label, slot, owners, stage, sub, record) {
  const parts = [`${label} #${slot}`];
  const list = owners.get(slot) || [];
  const others = list.filter((o) => !(o.stage === stage && o.sub === sub));
  if (others.length) {
    parts.push(`同时是${others.map(ownerLabel).join('、')}`);
  }
  const shared = (record && record.shared_with) || [];
  if (shared.length) {
    parts.push(`这段字被 ${shared.length + 1} 处共用，改一处会一起变`);
  } else if (list.length > 1) {
    parts.push(`这格被 ${list.length} 处共用（这几关共用同一格），改一处会一起变`);
  }
  return parts.join(' · ');
}

/** 空值与全角空格的显示文案。 */
function displayText(text) {
  const value = text === null || text === undefined ? '' : String(text);
  if (!value) return '（空）';
  if (/^[\u3000 ]+$/.test(value)) return '（全角空格）';
  return value;
}

// ---------------------------------------------------------------------------
// ③ 本关奖励
// ---------------------------------------------------------------------------

function rewardSection(ctx, stage, view, paintRewards) {
  const pack = ctx.pack;
  const base = missionBase(pack, stage);
  const rewards = pack.structure('reward_table');
  const owners = missionIndexOwners(pack);

  const host = el('div', { class: 'section' });
  host.appendChild(el('h3', { text: '本关奖励' }));
  host.appendChild(el('p', { class: 'section-note', text: [
    '任务索引表给出该关三个奖励在奖励表里的下标起点。',
    '奖励表每条 24 字节：金币、强化点、等级门槛，以及 8 个掉落位（类别 + 物品 id，0 表示列表结束）。',
  ] }));

  if (base === null || !rewards) {
    host.appendChild(el('div', { class: 'empty', text: '没有这一关的奖励。' }));
    return host;
  }

  // 字段控件的上下文：改完类别要把物品下拉重画一次。
  const refreshers = [];
  const fieldCtx = {
    pack: ctx.pack,
    onChange: ctx.onChange,
    onJump: ctx.onJump,
    registerRefresh: (fn) => refreshers.push(fn),
    onCommit: (structure, record, field) => {
      for (const fn of refreshers) fn();
      if (field && typeof field.key === 'string' && field.key.endsWith('_category')) {
        paintRewards();
      }
    },
  };
  const arrays = arraysIn(rewards.fields || []);
  const slotArray = arrays.find((a) => a.name === 'slots') || null;

  for (let u = 0; u < 3; u++) {
    const slot = base + u;
    const record = rewards.records.find((r) => r.id === slot);
    if (!record) continue;
    const block = el('div', { class: 'route-reward' });
    block.appendChild(el('h4', { class: 'route-sub', text: `子奖励 ${u + 1}` }));

    const numbers = el('div', { class: 'route-reward-numbers' });
    for (const key of ['gold', 'upgrade_points', 'tier']) {
      const field = (rewards.fields || []).find((f) => f.key === key);
      if (!field) continue;
      const { node } = fieldControl(fieldCtx, rewards, record, field);
      numbers.appendChild(el('div', { class: 'route-reward-field' }, [
        el('span', { class: 'operand-label', text: field.label || key }),
        node,
      ]));
    }
    block.appendChild(numbers);

    if (slotArray) {
      block.appendChild(el('div', { class: 'route-reward-drops' }, [
        el('div', { class: 'route-sub', text: '掉落位（8 位，0 表示列表结束）' }),
        renderArrayTable(fieldCtx, rewards, record, slotArray),
      ]));
    }

    block.appendChild(el('div', { class: 'route-reward-foot' }, [
      el('span', {
        class: 'shared-note',
        text: slotFootnote('奖励表', slot, owners, stage, u, null),
      }),
      openInModule(ctx, 'items', 'structure', 'reward_table', { recordId: slot },
        '在道具域打开这一条'),
    ]));
    host.appendChild(block);
  }
  return host;
}

// ---------------------------------------------------------------------------
// 小工具
// ---------------------------------------------------------------------------

/**
 * 改一个剧本操作数，并把「撤销」也接上。
 *
 * 撤销记录由 `pack.setScriptOperand` 自己写：它知道改之前补丁长什么样，
 * 所以撤销时既把操作数恢复成原值，也把补丁的 after_hex 恢复回去 ——
 * 否则撤销之后 ROM 里还是新值，改动计数也不会回落。
 */
function commitOperand(ctx, operand, value) {
  const before = Number(operand.value);
  if (before === value) return;
  ctx.pack.setScriptOperand(operand, value);
  ctx.onChange();
}

/** 本关三个子任务在文本表/奖励表里的起点。 */
function missionBase(pack, stage) {
  const index = pack.structure('mission_index');
  if (!index) return null;
  const record = index.records[stage];
  if (!record || !record.values) return null;
  const value = record.values.value;
  return value === null || value === undefined ? null : value;
}

function ptrText(value) {
  if (!value) return 'NULL';
  return '0x' + (value >>> 0).toString(16).toUpperCase();
}
