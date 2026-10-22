// 整条路线总览（#route/graph）与路线边的公共件。
//
// 路线边不是表里的行，而是**剧情脚本里的两条指令**：
//   0x16 —— 转到 after 剧本并记住下一场景
//   0x1A —— 直接推进路线游标
// 内容包把这两条指令的落点记在 pack.scripts[].route 里（每条边带 op /
// scene / flag / scene_rom_offset），这个模块把它们收成一张可点的总览表，
// 顺便给关卡工作台提供同一套「目标 / 走向」文案。

import { el, clear } from '../ui.js';
import { backButton, summaryTable } from './common.js';

/** 关卡数（任务索引表 0..47，其中 1..46 是有效关卡）。 */
export const STAGE_COUNT = 46;

/** 合法场景号：story_before_root / story_after_root 各 56 槽，场景 1..55。 */
export const MAX_SCENE = 55;

/** 剧情脚本里的两条路线指令。 */
export const OP_AFTER = 0x16;
export const OP_CURSOR = 0x1a;

const SCRIPT_ROOTS = {
  before: '战前剧情',
  after: '战后剧情',
  logic: '战场事件逻辑',
  events: '战场事件表',
};

/** 「战前剧情（第 40 关）」 */
export function scriptLabel(script) {
  const root = SCRIPT_ROOTS[script.root] || script.root;
  return `${root}（第 ${script.scene} 关）`;
}

/** 指令的「走向」：0x16 转到 after 剧本，0x1A 推进路线游标。 */
export function edgeDirection(edge) {
  if (edge.op === OP_AFTER) return '转到 after 剧本';
  if (edge.op === OP_CURSOR) return '推进路线游标';
  return '未知指令';
}

/** 「0x16」 */
export function opText(op) {
  return '0x' + Number(op).toString(16).toUpperCase().padStart(2, '0');
}

/**
 * 哪些场景有 after 剧本。
 *
 * 只认 `story_after_root` 里指针非空的槽位：指针为空 = 那个场景没有
 * after 剧本，下拉里就不该出现它。
 */
export function afterSceneSet(pack) {
  const root = pack.structure('story_after_root');
  const out = new Set();
  for (let n = 1; n <= MAX_SCENE; n++) {
    const record = root ? root.records[n] : null;
    if (!record) continue;
    const ptr = record.values ? record.values.ptr : 0;
    if (!ptr) continue;
    out.add(n);
  }
  return out;
}

/** 全游戏的路线边，每条边带上它的来源剧本。 */
export function collectEdges(pack) {
  const out = [];
  for (const script of pack.scripts || []) {
    for (const edge of script.route || []) {
      out.push({ script, edge });
    }
  }
  return out;
}

/** 目标场景的文字：after 剧本在不在，决定说「after 剧本」还是「无 after 剧本」。 */
export function targetText(scene, afterSet) {
  if (scene === 0) return '0 · 场景 0';
  if (afterSet.has(scene)) return `第 ${scene} 关 · after 剧本`;
  return `第 ${scene} 关 · 无 after 剧本`;
}

/** 可点的「目标」：跳到那一关。 */
export function targetLink(ctx, scene, afterSet) {
  return el('span', {
    class: 'xref-link',
    text: targetText(scene, afterSet),
    title: `跳到第 ${scene} 关`,
    onclick: () => ctx.openPanel('stage', 'stage', { stage: scene }),
  });
}

/** 一张路线边表：来源剧本 | 指令 | 走向 | 目标 | 相位标志 | ROM 地址 */
export function edgeTable(ctx, edges, afterSet) {
  const rows = { head: ['来源剧本', '指令', '走向', '目标', '相位标志', 'ROM 地址'], body: [] };
  for (const { script, edge } of edges) {
    rows.body.push([
      scriptLabel(script),
      opText(edge.op),
      edgeDirection(edge),
      targetLink(ctx, edge.scene, afterSet),
      edge.flag === null || edge.flag === undefined ? '—' : String(edge.flag),
      '0x' + Number(edge.scene_rom_offset).toString(16).toUpperCase(),
    ]);
  }
  return summaryTable(rows);
}

/**
 * 整条路线总览：一屏看全 46 关的出边/入边，以及全部路线边。
 */
export function renderRouteGraph(container, ctx) {
  clear(container);
  const pack = ctx.pack;
  const afterSet = afterSceneSet(pack);
  const edges = collectEdges(pack);
  const afterCount = edges.filter((e) => e.edge.op === OP_AFTER).length;
  const cursorCount = edges.filter((e) => e.edge.op === OP_CURSOR).length;

  container.appendChild(el('div', { style: { marginBottom: '12px' } }, [
    backButton(ctx, '剧情路线'),
  ]));

  container.appendChild(el('div', { class: 'panel-head' }, [
    el('div', {}, [
      el('h2', { text: '整条路线总览' }),
      el('div', { class: 'panel-sub' }, [
        el('span', { text: `全游戏 ${edges.length} 条路线边` }),
        el('span', { text: `0x16 ${afterCount} 处 · 0x1A ${cursorCount} 处` }),
      ]),
    ]),
  ]));
  container.appendChild(el('p', { class: 'section-note', text: [
    '路线边不在表里，它们是剧情脚本里的两条指令：0x16 = 转到 after 剧本并记住下一场景；',
    '0x1A = 直接推进路线游标。点「目标」可以跳到那一关。',
  ] }));

  // --- 每一关的出边与入边 ------------------------------------------------
  const stageRows = { head: ['关卡', '出边', '入边', '跳向', 'ROM 地址'], body: [] };
  for (let s = 1; s <= STAGE_COUNT; s++) {
    const out = edges.filter((e) => e.script.scene === s);
    const into = edges.filter((e) => e.edge.scene === s);
    if (!out.length && !into.length) continue;
    const targets = out.map((e) => targetText(e.edge.scene, afterSet));
    stageRows.body.push([
      el('span', {
        class: 'xref-link',
        text: `第 ${s} 关`,
        onclick: () => ctx.openPanel('stage', 'stage', { stage: s }),
      }),
      String(out.length),
      String(into.length),
      targets.join('、') || '—',
      out.length ? '0x' + Number(out[0].edge.scene_rom_offset).toString(16).toUpperCase() : '—',
    ]);
  }
  container.appendChild(el('div', { class: 'section' }, [
    el('h3', { text: '每一关的出边与入边' }),
    summaryTable(stageRows),
  ]));

  // --- 全部路线边 --------------------------------------------------------
  container.appendChild(el('div', { class: 'section' }, [
    el('h3', { text: `全部路线边（${edges.length} 条）` }),
    edgeTable(ctx, edges, afterSet),
  ]));
}
