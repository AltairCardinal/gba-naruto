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
    return {
      module,
      panel: {
        kind: 'stage',
        id: 'stage',
        params: { stage: Number(parts[2]) || 1, variant: Number(parts[3]) || 0 },
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
  return `#${module}`;
}
