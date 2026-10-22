// Shared building blocks for the per-domain module views.
//
// Every domain view is the same shape: a short introduction, then a list of
// the structures and text tables that belong to that domain.  Clicking one
// opens the generic editor for it.  Because the generic editor is driven by
// the content pack's own metadata, a structure becomes editable the moment
// the exporter describes it — no per-domain UI code.

import { el, clear, formatOffset, toast } from '../ui.js';
import { StructureEditor, TextTableEditor } from '../editors.js';

export function backButton(ctx, label) {
  return el('button', {
    class: 'btn btn-ghost',
    text: '← 返回' + (label || ''),
    onclick: () => {
      ctx.state.view.panel = null;
      ctx.render();
    },
  });
}

/**
 * The big "推荐入口" card of a domain.
 *
 * It answers "从哪儿下手" in one click: the author lands directly in the
 * table (or per-stage view) that the domain is really about.
 */
export function entryCard(ctx, options) {
  const actions = [];
  if (options.panel) {
    actions.push(el('button', {
      class: 'btn btn-primary',
      text: options.actionLabel || '去编辑',
      onclick: () => ctx.openPanel(options.panel.kind, options.panel.id),
    }));
  }
  if (options.onPick) actions.push(options.onPick);
  return el('div', { class: 'stat entry-card' }, [
    el('div', { class: 'stat-label', text: options.title }),
    el('div', { class: 'stat-value', style: { fontSize: '15px' }, text: options.headline }),
    el('div', { class: 'stat-hint', text: options.desc }),
    actions.length ? el('div', { class: 'entry-actions' }, actions) : null,
  ]);
}

/**
 * Render the index of one domain.
 *
 * The domain index answers three questions, in this order:
 *   1. **推荐入口** —— where should I start? (the per-stage / per-character
 *      views, not the generic table editors)
 *   2. **本域可编辑内容** —— every table of this domain, with what kind of
 *      editing it takes, whether the text can grow, and whether it was changed
 *   3. **跨域引用** —— where does this domain's data point to?
 *
 * Every table of the domain is listed, even the ones the module does not
 * mention: a table that cannot be reached from its own domain is a table the
 * author cannot edit.
 *
 * @param {HTMLElement} container
 * @param {object} ctx
 * @param {object} options { title, intro, module, primary, extra, structures, texts, subtitle }
 */
export function renderDomainIndex(container, ctx, options) {
  clear(container);
  const head = el('div', { class: 'panel-head' }, [
    el('div', {}, [
      el('h2', { text: options.title }),
      el('div', { class: 'panel-sub' }, options.subtitle || []),
    ]),
  ]);
  container.appendChild(head);
  if (options.intro) {
    container.appendChild(el('p', { class: 'section-note', text: options.intro }));
  }

  // --- 1. 推荐入口 ------------------------------------------------------
  if (options.primary) {
    container.appendChild(el('div', { class: 'section' }, [
      el('h3', { text: '推荐入口' }),
      el('div', { class: 'card-grid' }, [options.primary, options.secondary].filter(Boolean)),
    ]));
  }

  // --- 2. 本域可编辑内容 ------------------------------------------------
  const rows = domainTableRows(ctx, options);
  if (rows.length) {
    const tableEl = el('table', { class: 'grid domain-tables' }, [
      el('thead', {}, [el('tr', {}, [
        el('th', { text: '表' }),
        el('th', { class: 'col-num', text: '条数' }),
        el('th', { text: '字段' }),
        el('th', { text: '改法' }),
        el('th', { text: '长度策略' }),
        el('th', { class: 'col-num', text: '已改' }),
        el('th', { text: '入口' }),
      ])]),
      el('tbody', {}, rows),
    ]);
    // 几张表合成一行时，行数会少于表数 —— 所以把「覆盖了几张表」记在
    // data 属性上，自检按这个数判（可达性），不按行数判。
    tableEl.dataset.covered = String(domainCoverage(ctx, options));
    container.appendChild(el('div', { class: 'section' }, [
      el('h3', { text: '本域可编辑内容' }),
      el('div', { class: 'table-wrap' }, [tableEl]),
    ]));
  }

  // --- 3. 其它内容（域自带的只读一览） -----------------------------------
  // 折叠起来：本域可编辑内容才是正事，一览是参考。
  if (options.extra) {
    container.appendChild(el('details', { class: 'domain-extra' }, [
      el('summary', { text: '一览（只读参考）' }),
      options.extra,
    ]));
  }
}

/**
 * How many tables of this domain the home page actually covers.
 *
 * 几张表合成一行时，行数 ≠ 表数；可达性要按「覆盖了几张表」算。
 */
function domainCoverage(ctx, options) {
  const pack = ctx.pack;
  const module = options.module;
  const grouped = new Set();
  for (const group of options.groups || []) {
    for (const id of group.tables || []) grouped.add(id);
  }
  let n = 0;
  for (const s of pack.structures) {
    const wanted = new Set(options.structures || []);
    if (grouped.has(s.id)) { n += 1; continue; }
    if (wanted.has(s.id) || (module && s.module === module)) n += 1;
  }
  for (const t of pack.texts) {
    if (grouped.has(t.id)) { n += 1; continue; }
    const wanted = new Set(options.texts || []);
    if (wanted.has(t.id) || (module && t.module === module)) n += 1;
  }
  return n;
}

/**
 * One row per editable table of this domain.
 *
 * The module's own list comes first (it knows what matters), and every
 * remaining table of the domain is appended — nothing is left unreachable.
 *
 * `options.groups` 让几张表**合成一行**：它们本来就是同一个「主对象」的
 * 几个侧面（任务 = 索引表 + 标题表 + 说明表 + 提示表），
 * 分成四行摆着会让作者以为要分别进四张表 —— 那是细碎，不是清楚。
 */
function domainTableRows(ctx, options) {
  const pack = ctx.pack;
  const module = options.module;
  const grouped = options.groups || [];
  const groupedIds = new Set();
  for (const group of grouped) {
    for (const id of group.tables || []) groupedIds.add(id);
  }
  const wanted = new Set(options.structures || []);
  const structures = pack.structures.filter((s) =>
    !groupedIds.has(s.id) &&
    (wanted.has(s.id) || (module && s.module === module)));
  const texts = pack.texts.filter((t) =>
    !groupedIds.has(t.id) &&
    ((options.texts || []).includes(t.id) || (module && t.module === module)));

  const rows = [];

  // --- 分组行：几张表合成一个「主对象」视图 ------------------------------
  for (const group of grouped) {
    const members = [
      ...pack.structures.filter((s) => (group.tables || []).includes(s.id)),
      ...pack.texts.filter((t) => (group.tables || []).includes(t.id)),
    ];
    if (!members.length) continue;
    const count = members.reduce((n, m) => n + (m.entry_count || m.count || 0), 0);
    const known = members.reduce((n, m) =>
      n + (m.fields || []).filter((f) => f.type !== 'hex').length, 0);
    const texts = members.reduce((n, m) =>
      n + (m.fields ? 0 : (m.count || 0)), 0);
    const changed = members.reduce((n, m) =>
      n + (m.fields ? pack.changedCountIn(m) : pack.changedCountInTable(m)), 0);
    rows.push(el('tr', { class: changed ? 'changed' : '' }, [
      el('td', {}, [
        el('div', { text: group.label }),
        el('div', {
          class: 'stat-hint',
          text: `由 ${members.map((m) => m.label || m.id).join(' / ')} 合成`,
        }),
      ]),
      el('td', { class: 'col-num', text: String(count) }),
      el('td', {
        class: 'text-cell',
        text: `${known} 个字段${texts ? ` / ${texts} 条文本` : ''} / ${members.length} 张表`,
      }),
      el('td', {}, [el('span', {
        class: 'pill pill-edit',
        text: group.method || '按主对象改',
      })]),
      el('td', { text: group.strategy || '定宽写回' }),
      el('td', { class: 'col-num' }, [changed
        ? el('span', { class: 'pill pill-changed', text: `● ${changed}` })
        : el('span', { class: 'pill', text: '—' })]),
      el('td', {}, [el('button', {
        class: 'btn btn-tiny',
        text: group.action || '打开',
        onclick: () => {
          if (group.onPick) {
            group.onPick(ctx);
            return;
          }
          ctx.openPanel(group.kind, group.id || group.kind, group.params || {});
        },
      })]),
    ]));
  }

  for (const structure of structures) {
    const known = (structure.fields || []).filter((f) => f.type !== 'hex').length;
    const filler = (structure.fields || []).length - known;
    const changed = pack.changedCountIn(structure);
    rows.push(el('tr', { class: changed ? 'changed' : '' }, [
      el('td', { text: structure.label || structure.id }),
      el('td', { class: 'col-num', text: String(structure.entry_count) }),
      el('td', { class: 'text-cell', text: `${known} 已知${filler ? ` + ${filler} 原始字节` : ''}` }),
      el('td', {}, [el('span', {
        class: 'pill ' + (structure.raw_only ? 'pill-raw' : 'pill-edit'),
        text: structure.raw_only ? '原始字节（语义未证）' : '直接改',
      })]),
      el('td', { text: structure.raw_only ? '字节可改（原始字节）' : '定宽写回' }),
      el('td', { class: 'col-num' }, [changed
        ? el('span', { class: 'pill pill-changed', text: `● ${changed}` })
        : el('span', { class: 'pill', text: '—' })]),
      el('td', {}, [el('button', {
        class: 'btn btn-tiny',
        text: '编辑',
        onclick: () => ctx.openPanel('structure', structure.id),
      })]),
    ]));
  }
  for (const table of texts) {
    const changed = pack.changedCountInTable(table);
    rows.push(el('tr', { class: changed ? 'changed' : '' }, [
      el('td', { text: table.label || table.id }),
      el('td', { class: 'col-num', text: String(table.count) }),
      el('td', { class: 'text-cell', text: `${table.count} 条文本` }),
      el('td', {}, [el('span', { class: 'pill pill-text', text: '文本' })]),
      el('td', { text: table.relocatable ? '可重定位（可变长）' : '等长改写' }),
      el('td', { class: 'col-num' }, [changed
        ? el('span', { class: 'pill pill-changed', text: `● ${changed}` })
        : el('span', { class: 'pill', text: '—' })]),
      el('td', {}, [el('button', {
        class: 'btn btn-tiny',
        text: '编辑',
        onclick: () => ctx.openPanel('text', table.id),
      })]),
    ]));
  }
  return rows;
}

/** Render the editor for one structure or text table. */
export function renderPanel(container, ctx, kind, id, params) {
  clear(container);
  container.appendChild(el('div', { style: { marginBottom: '12px' } }, [
    backButton(ctx),
  ]));
  if (kind === 'structure') {
    const structure = ctx.pack.structure(id);
    if (!structure) {
      container.appendChild(el('div', { class: 'empty', text: '找不到结构 ' + id }));
      return;
    }
    const editor = new StructureEditor(ctx.pack, structure, {
      onChange: ctx.onChange,
      onJump: ctx.onJump,
    });
    editor.render(container);
    const recordId = params && params.recordId;
    if (recordId !== undefined && recordId !== null) {
      const record = (structure.records || []).find((r) => r.id === recordId);
      if (record) editor.openDetail(record);
      else toast(`这张表里没有记录 ${recordId}`, 'error');
    }
  } else {
    const table = ctx.pack.textTable(id);
    if (!table) {
      container.appendChild(el('div', { class: 'empty', text: '找不到文本表 ' + id }));
      return;
    }
    const editor = new TextTableEditor(ctx.pack, table, {
      onChange: ctx.onChange,
      onJump: ctx.onJump,
    });
    editor.render(container);
    const recordId = params && params.recordId;
    if (recordId !== undefined && recordId !== null) {
      const record = (table.records || []).find((r) => r.id === recordId);
      if (record) editor.openDetail(record);
      else toast(`这张表里没有记录 ${recordId}`, 'error');
    }
  }
}

/** A small input that writes one story-VM operand back into the pack. */
export function operandInput(ctx, operand) {
  const commit = (value) => {
    ctx.pack.setScriptOperand(operand, value);
    ctx.onChange();
    toast(`已改写 0x${operand.rom_offset.toString(16).toUpperCase()}`);
  };
  if (operand.size === 1) {
    return el('input', {
      class: 'num-input',
      type: 'text',
      style: { width: '70px' },
      value: String(operand.value),
      onchange: (e) => {
        const value = Number(e.target.value);
        if (!Number.isFinite(value) || value < 0 || value > 255) {
          toast('请输入 0–255', 'error');
          return;
        }
        commit(value);
      },
    });
  }
  if (operand.size === 2) {
    return el('input', {
      class: 'num-input',
      type: 'text',
      style: { width: '70px' },
      value: String(operand.value),
      onchange: (e) => {
        const value = Number(e.target.value);
        if (!Number.isFinite(value) || value < 0 || value > 0xffff) {
          toast('请输入 0–65535', 'error');
          return;
        }
        commit(value);
      },
    });
  }
  return el('input', {
    class: 'num-input',
    type: 'text',
    style: { width: '90px' },
    value: String(operand.value),
    onchange: (e) => {
      const value = String(e.target.value).replace(/[^0-9a-fA-F]/g, '');
      if (value.length !== operand.size * 2) {
        toast(`该字段固定 ${operand.size} 字节（${operand.size * 2} 个十六进制字符）`, 'error');
        return;
      }
      commit(value);
    },
  });
}

/**
 * 剧情脚本的一个定宽操作数改过没有。
 *
 * `operand.value` 是**就地改**的当前值，原值留在 `before_hex` 里 ——
 * 所以判定方式是「当前值编码出来的字节」与 `before_hex` 比。
 * 「改过又改回去」不算改。
 *
 * @param {object} operand
 * @returns {boolean}
 */
export function operandChanged(operand) {
  if (!operand) return false;
  const before = String(operand.before_hex || '').toLowerCase();
  if (!before) return false;
  let after;
  if (operand.size === 1) {
    after = (Number(operand.value) & 0xff).toString(16).padStart(2, '0');
  } else if (operand.size === 2) {
    const v = Number(operand.value) & 0xffff;
    after = (v & 0xff).toString(16).padStart(2, '0')
      + ((v >> 8) & 0xff).toString(16).padStart(2, '0');
  } else {
    after = String(operand.value).replace(/[^0-9a-fA-F]/g, '').toLowerCase();
  }
  return after !== before;
}

/**
 * A link that opens the same item in the generic table editor.
 *
 * The stage view and the table view are two roads to the same data; the link
 * makes that explicit, so the author can check the change in the table (or
 * make a change the stage view does not offer) without hunting for the id.
 */
export function openInTable(ctx, structureId, recordId, label) {
  return el('button', {
    class: 'btn btn-tiny',
    text: label || '在通用表格中打开',
    title: `打开 ${structureId} 的第 ${recordId} 条`,
    onclick: () => ctx.openPanel('structure', structureId, { recordId }),
  });
}

/**
 * A link that opens a record **in another domain**.
 *
 * The record is one object in the content pack, so the domain only decides
 * where the author lands: the table editor shows the same bytes.
 */
export function openInModule(ctx, moduleId, kind, id, params, label) {
  const recordId = params && params.recordId;
  return el('button', {
    class: 'btn btn-tiny',
    text: label || '在通用表格中打开',
    title: `打开 ${id} 的第 ${recordId} 条`,
    onclick: () => {
      if (moduleId && ctx.goModule) ctx.goModule(moduleId);
      ctx.openPanel(kind, id, params);
    },
  });
}

// ---------------------------------------------------------------------------
// 战斗域共用的常量与工具
// ---------------------------------------------------------------------------

/**
 * 战斗域几张表的布局常量。
 *
 * 关卡视图与战场地图视图读的是同一批记录（编成矩阵 / 战场物件 / 战场布置），
 * 所以偏移量只留**这一处**真相：两边各写一份，迟早会漂。
 */
export const BATTLE_LAYOUT = {
  STAGE_COUNT: 47,
  VARIANT_COUNT: 3,
  GROUP_STRIDE: 0x1aac,
  VARIANT_STRIDE: 0x8e4,
  SLOT_STRIDE: 0xb8,
  ACTORS_BASE: 0x5461c4,
  MAP_BASE: 0x53d910,
  RULES_BASE: 0x594758,
  RULE_STAGE_STRIDE: 0xcc,
  RULE_SUB_STRIDE: 0x44,
  OBJECT_OFFSET: 0x8a4,
  OBJECT_COUNT: 16,
};

/**
 * How many records of this stage (and variant) have been changed.
 *
 * The count comes from the **byte** comparison, so "changed and changed back"
 * does not count — and it is the same judgement the generic table editor
 * makes, so the two views never disagree.
 */
export function stageChangeCount(ctx, stage, variant) {
  const pack = ctx.pack;
  let n = 0;
  const actorBase = BATTLE_LAYOUT.ACTORS_BASE + stage * BATTLE_LAYOUT.GROUP_STRIDE +
    variant * BATTLE_LAYOUT.VARIANT_STRIDE + 4;
  const objectBase = actorBase - 4 + BATTLE_LAYOUT.OBJECT_OFFSET;
  const ruleOffset = BATTLE_LAYOUT.RULES_BASE + stage * BATTLE_LAYOUT.RULE_STAGE_STRIDE +
    variant * BATTLE_LAYOUT.RULE_SUB_STRIDE;
  for (const [id, offsets] of [
    ['battle_actors', Array.from({ length: 12 }, (_, s) => actorBase + s * BATTLE_LAYOUT.SLOT_STRIDE)],
    ['battle_map_objects', Array.from({ length: BATTLE_LAYOUT.OBJECT_COUNT },
      (_, o) => objectBase + o * 4)],
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
      if (binding.rule !== stage * BATTLE_LAYOUT.VARIANT_COUNT + variant) continue;
      if (changed.has(binding.text_id)) n += 1;
    }
  }
  return n;
}

/**
 * The camp of one battle slot.
 *
 * The camp is bit 0 of `unit_flags` — the byte at +0x01 is *not* read by the
 * formation path, so this control rewrites the flag instead.
 *
 * 关卡视图与战场地图视图共用这一个控件：阵营只有一处真相。
 */
export function sideCell(ctx, structure, record, values) {
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
 * 战场地图的素材缺失提示条。
 *
 * 素材是**只读上下文**：缺了它，地图视图照常打开（只显示格线与标记），
 * 编辑功能一条不少（物件 / 角色 / 底图 id 都在内容包里）。
 */
export function mapAssetNotice(message, file, onRetry) {
  return el('div', { class: 'map-asset-notice' }, [
    el('span', { class: 'map-asset-notice-text', text: message }),
    file ? el('span', { class: 'stat-hint', text: `素材文件：${file}` }) : null,
    onRetry
      ? el('button', {
        class: 'btn btn-tiny',
        text: '重新载入素材',
        onclick: onRetry,
      })
      : null,
  ]);
}

/** A small read-only summary table used by several domains. */
export function summaryTable(rows) {
  const table = el('table', { class: 'grid' });
  const head = el('tr');
  for (const cell of rows.head) head.appendChild(el('th', { text: cell }));
  table.appendChild(el('thead', {}, [head]));
  const body = el('tbody');
  for (const row of rows.body) {
    const tr = el('tr');
    row.forEach((cell, i) => {
      const isNode = cell && typeof cell === 'object' && cell.nodeType === 1;
      tr.appendChild(el('td', {
        class: i === 0 ? 'col-id' : '',
        text: isNode ? '' : (cell === null || cell === undefined ? '' : String(cell)),
      }, isNode ? [cell] : []));
    });
    body.appendChild(tr);
  }
  table.appendChild(body);
  return el('div', { class: 'table-wrap' }, [table]);
}
