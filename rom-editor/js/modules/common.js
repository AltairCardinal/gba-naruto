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
    container.appendChild(el('div', { class: 'section' }, [
      el('h3', { text: '本域可编辑内容' }),
      el('div', { class: 'table-wrap' }, [el('table', { class: 'grid domain-tables' }, [
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
      ])]),
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
 * One row per editable table of this domain.
 *
 * The module's own list comes first (it knows what matters), and every
 * remaining table of the domain is appended — nothing is left unreachable.
 */
function domainTableRows(ctx, options) {
  const pack = ctx.pack;
  const module = options.module;
  const wanted = new Set(options.structures || []);
  const structures = pack.structures.filter((s) =>
    wanted.has(s.id) || (module && s.module === module));
  const texts = pack.texts.filter((t) =>
    (options.texts || []).includes(t.id) || (module && t.module === module));

  const rows = [];
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
