// Shared building blocks for the per-domain module views.
//
// Every domain view is the same shape: a short introduction, then a list of
// the structures and text tables that belong to that domain.  Clicking one
// opens the generic editor for it.  Because the generic editor is driven by
// the content pack's own metadata, a structure becomes editable the moment
// the exporter describes it — no per-domain UI code.

import { el, clear, formatOffset } from '../ui.js';
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
 * Render the index of one domain.
 * @param {HTMLElement} container
 * @param {object} ctx
 * @param {object} options { title, intro, structures: [], texts: [], extra: HTMLElement }
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
  if (options.extra) container.appendChild(options.extra);

  const sections = [];
  for (const id of options.structures || []) {
    const structure = ctx.pack.structure(id);
    if (!structure) continue;
    sections.push({
      kind: 'structure',
      id,
      title: structure.label,
      badge: `${structure.entry_count} 条`,
      meta: `ROM ${formatOffset(structure.rom_offset)} · ${structure.entry_size} 字节/条`,
      desc: structure.note || '',
      verification: structure.verification || '',
    });
  }
  for (const id of options.texts || []) {
    const table = ctx.pack.textTable(id);
    if (!table) {
      // A table that lives in its own file (the exhaustive ROM text index)
      // is loaded on demand — show it as an entry that loads when clicked.
      if (id === 'rom_text_index') {
        sections.push({
          kind: 'text',
          id,
          title: '全 ROM 文本索引',
          badge: '按需载入',
          meta: '绝对地址引用',
          desc: '用 ROM 自带字库扫出的全卡带字符串清单，进入时下载。',
          verification: '等长改写',
        });
      }
      continue;
    }
    sections.push({
      kind: 'text',
      id,
      title: table.label,
      badge: `${table.count} 条`,
      meta: table.pointer_table_offset
        ? `指针表 ${formatOffset(table.pointer_table_offset)}`
        : '绝对地址引用',
      desc: table.note || '',
      verification: table.relocatable ? '可变长（重定位）' : '等长改写',
    });
  }

  const grid = el('div', { class: 'card-grid' });
  for (const section of sections) {
    grid.appendChild(el('div', {
      class: 'stat',
      style: { cursor: 'pointer' },
      onclick: () => ctx.openPanel(section.kind, section.id),
    }, [
      el('div', { class: 'stat-label', text: section.title }),
      el('div', { class: 'stat-value', style: { fontSize: '15px' }, text: section.badge }),
      el('div', { class: 'stat-hint', text: section.meta }),
      section.desc ? el('div', { class: 'stat-hint', text: section.desc }) : null,
      section.verification
        ? el('div', { class: 'stat-hint', style: { color: '#6f9ad8' }, text: section.verification })
        : null,
    ]));
  }
  container.appendChild(el('div', { class: 'section' }, [
    el('h3', { text: '可编辑内容' }),
    grid,
  ]));
}

/** Render the editor for one structure or text table. */
export function renderPanel(container, ctx, kind, id) {
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
    });
    editor.render(container);
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
  }
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
      tr.appendChild(el('td', {
        class: i === 0 ? 'col-id' : '',
        text: cell === null || cell === undefined ? '' : String(cell),
      }));
    });
    body.appendChild(tr);
  }
  table.appendChild(body);
  return el('div', { class: 'table-wrap' }, [table]);
}
