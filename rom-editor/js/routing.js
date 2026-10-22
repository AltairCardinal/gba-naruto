// URL routing: the hash is the single source of truth for "where am I".
//
//   #overview                                   概览
//   #route                                      剧情路线
//   #route/stage/3                              剧情路线的第 3 关
//   #battle/stage/40/0                          战斗的第 40 关、变体 0
//   #characters/structure/character_template/1   角色定义表的第 1 条
//   #characters/text/dialogue_slots/12           对白槽位表的第 12 条
//
// 表格与记录级也能寻址，浏览器后退键才是在编辑器里后退，而不是退出编辑器。

/** The domains the editor knows about (must match app.js::MODULES). */
export const DOMAIN_IDS = [
  'overview', 'story', 'items', 'characters', 'ninjutsu', 'battle', 'route',
  'audio', 'assets', 'raw',
];

/**
 * Sub-views that are not tables but whole panels of one domain.
 *
 * The domain dispatches on `kind`; `id` is the Chinese label the
 * breadcrumb shows.  Listing them here makes those panels deep-linkable
 * (`#assets/wiring`) and lets the browser Back button work inside the
 * editor instead of leaving it.
 */
export const SUBVIEW_LABELS = {
  wiring: '接线表',
  records: '资源记录表',
  memory: 'EWRAM 内存图',
  overview: '指针接线总表',
  mission: '任务',
  item: '忍具',
  reward: '奖励',
  scene: '场景',
  font: '字库',
  character: '角色',
  jutsu: '忍术',
};

/**
 * Parse a hash into { module, panel }.
 *
 * @param {string} hash  e.g. "#battle/stage/40/0"
 */
export function parseHash(hash) {
  const raw = String(hash || '').replace(/^#/, '');
  if (!raw) return { module: 'overview', panel: null };
  const parts = raw.split('/');
  const module = DOMAIN_IDS.includes(parts[0]) ? parts[0] : 'overview';
  if (parts[1] === 'stage') {
    const stage = Number(parts[2]);
    const variant = Number(parts[3]);
    // 战斗域的「关卡视图」已经并进战场地图：老深链 `#battle/stage/40/0`
    // 仍然能开，但要开的是**地图**（战场地图是战斗域的主界面）。
    const kind = module === 'battle' ? 'map' : 'stage';
    return {
      module,
      panel: {
        kind,
        id: kind,
        // 以前写的是 `Number(parts[2]) || 1`：第 0 关会被解析成第 1 关。
        params: {
          stage: Number.isFinite(stage) ? stage : 1,
          variant: Number.isFinite(variant) ? variant : 0,
        },
      },
    };
  }
  if (parts[1] === 'graph') {
    // 「整条路线总览」这类整域视图。
    return { module, panel: { kind: 'graph', id: 'graph', params: {} } };
  }
  if (parts[1] && SUBVIEW_LABELS[parts[1]]) {
    // 域内的整块面板（接线表 / 内存图 / …）。
    return {
      module,
      panel: { kind: parts[1], id: SUBVIEW_LABELS[parts[1]], params: {} },
    };
  }
  if (parts[1] === 'map') {
    // 战场地图：#battle/map/<关卡>/<变体>
    const stage = Number(parts[2]);
    const variant = Number(parts[3]);
    return {
      module,
      panel: {
        kind: 'map',
        id: 'map',
        params: {
          stage: Number.isFinite(stage) ? stage : 1,
          variant: Number.isFinite(variant) ? variant : 0,
        },
      },
    };
  }
  if (parts[1] === 'offset' && parts[2]) {
    // 「原始字节」按地址打开：#raw/offset/0x5A15C0
    const offset = parseInt(String(parts[2]).replace(/^0x/i, ''), 16);
    return {
      module,
      panel: {
        kind: 'raw-offset',
        id: 'raw',
        params: { offset: Number.isFinite(offset) ? offset : 0 },
      },
    };
  }
  if ((parts[1] === 'structure' || parts[1] === 'text') && parts[2]) {
    const recordId = parts[3] !== undefined ? Number(parts[3]) : null;
    return {
      module,
      panel: {
        kind: parts[1],
        id: parts[2],
        params: recordId === null || Number.isNaN(recordId) ? {} : { recordId },
      },
    };
  }
  if (parts[1] === 'script' && parts[2]) {
    return {
      module,
      panel: {
        kind: 'script',
        id: 'script',
        params: { root: parts[2], scene: Number(parts[3]) || 1 },
      },
    };
  }
  if (parts[1] === 'dialogue' && parts[2]) {
    // 可视化对白编辑器：#story/dialogue/<before|after|logic|events>/<场景>
    return {
      module,
      panel: {
        kind: 'dialogue',
        id: '对白',
        params: { root: parts[2], scene: Number(parts[3]) || 1 },
      },
    };
  }
  return { module, panel: null };
}

/**
 * The hash that describes a view.
 *
 * @param {{module: string, panel: ?object}} view
 * @returns {string}
 */
export function hashFor(view) {
  const module = view && view.module ? view.module : 'overview';
  const panel = view && view.panel;
  if (!panel) return `#${module}`;
  if (panel.kind === 'stage') {
    const { stage, variant } = panel.params || {};
    // 战斗域的关卡视图已经并进战场地图，地址统一成 `#battle/map/…`。
    if (module === 'battle') return `#${module}/map/${stage ?? 1}/${variant || 0}`;
    return `#${module}/stage/${stage}/${variant || 0}`;
  }
  if (panel.kind === 'structure' || panel.kind === 'text') {
    const recordId = panel.params && panel.params.recordId;
    return `#${module}/${panel.kind}/${panel.id}` +
      (recordId === null || recordId === undefined ? '' : `/${recordId}`);
  }
  if (panel.kind === 'script') {
    const { root, scene } = panel.params || {};
    return `#${module}/script/${root || 'before'}/${scene || 1}`;
  }
  if (panel.kind === 'dialogue') {
    const { root, scene } = panel.params || {};
    return `#${module}/dialogue/${root || 'before'}/${scene || 1}`;
  }
  if (panel.kind === 'graph') {
    return `#${module}/graph`;
  }
  if (SUBVIEW_LABELS[panel.kind]) {
    return `#${module}/${panel.kind}`;
  }
  if (panel.kind === 'map') {
    const { stage, variant } = panel.params || {};
    return `#${module}/map/${stage ?? 1}/${variant ?? 0}`;
  }
  if (panel.kind === 'raw-offset') {
    const offset = (panel.params && panel.params.offset) || 0;
    return `#${module}/offset/0x${(offset >>> 0).toString(16).toUpperCase()}`;
  }
  return `#${module}`;
}
