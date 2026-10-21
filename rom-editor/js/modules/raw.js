// 原始字节：整张卡带的十六进制编辑器
//
// 这是「任何内容都可以改」的兜底通道。结构化编辑器覆盖不了的字节，
// 这里都能直接改；改动以显式补丁（patch）的形式记在内容包里，
// 构建时按「原字节必须匹配」写回——原字节对不上就跳过并报告，
// 不会把别处的数据改坏。

import { el, clear, formatOffset, toast } from '../ui.js';
import { bytesToHex, hexToBytes, readUint } from '../bytes.js';

const PAGE = 0x100;
const ROWS = 16;

export function renderRaw(container, ctx) {
  const pack = ctx.pack;
  const rom = ctx.rom || ctx.baseRom;

  if (!rom) {
    container.appendChild(el('div', { class: 'empty', text: '请先载入原版 ROM' }));
    return;
  }

  // 「按地址打开原始字节」用的是面板参数。以前这里读的是
  // `ctx.state.view.params.offset`，而参数其实在 `ctx.state.view.panel.params` 里，
  // 于是深链 #raw/offset/0x… 永远从 0x000000 开始。
  const viewParams = (ctx.state.view.panel && ctx.state.view.panel.params) || {};
  let cursor = viewParams.offset ? Number(viewParams.offset) : 0;

  const head = el('div', { class: 'panel-head' }, [
    el('div', {}, [
      el('h2', { text: '原始字节编辑' }),
      el('div', { class: 'panel-sub' }, [
        el('span', { text: `ROM ${rom.length.toLocaleString()} 字节` }),
        el('span', { text: `显式补丁 ${pack.patches.length} 条` }),
      ]),
    ]),
  ]);
  container.appendChild(head);

  container.appendChild(el('p', { class: 'section-note' }, [
    '直接点字节就能改；改动记为显式补丁，构建时按「原字节必须匹配」写回。' +
    '也可以用下面的跳转 / 搜索定位到结构化编辑器没覆盖的地址。',
    '补丁在**结构与文本写回之后**才写：所以落在某张表记录里的补丁能生效，' +
    '但如果那一格已经被结构化编辑器改过，补丁会被跳过并在构建报告里点名。',
  ]));

  // --- 控件 ------------------------------------------------------------
  const gotoInput = el('input', {
    class: 'search', type: 'text', placeholder: '地址（十六进制，如 545BE4）',
    style: { width: '210px' },
  });
  const hexInput = el('input', {
    class: 'search', type: 'text', placeholder: '搜索字节（十六进制）',
    style: { width: '190px' },
  });
  const textInput = el('input', {
    class: 'search', type: 'text', placeholder: '搜索文本（按 ROM 字库编码）',
    style: { width: '210px' },
  });
  const results = el('div', { class: 'stat-hint' });

  const grid = el('div', { class: 'hex-grid' });
  const tools = el('div', { class: 'hex-controls' }, [
    gotoInput,
    el('button', {
      class: 'btn btn-ghost', text: '跳转',
      onclick: () => {
        const value = parseInt(gotoInput.value.replace(/^0x/i, ''), 16);
        if (!Number.isFinite(value) || value < 0 || value >= rom.length) {
          toast('地址超出 ROM 范围', 'error');
          return;
        }
        cursor = value;
        draw();
      },
    }),
    el('span', { class: 'stat-hint', text: '｜' }),
    hexInput,
    el('button', {
      class: 'btn btn-ghost', text: '查找字节',
      onclick: () => {
        const needle = hexToBytes(hexInput.value);
        if (!needle.length) return;
        const found = findBytes(rom, needle, pack);
        if (found < 0) {
          results.textContent = '未找到';
          return;
        }
        cursor = found;
        results.textContent = '命中 0x' + found.toString(16).toUpperCase();
        draw();
      },
    }),
    el('span', { class: 'stat-hint', text: '｜' }),
    textInput,
    el('button', {
      class: 'btn btn-ghost', text: '查找文本',
      onclick: () => {
        const needle = pack.font.encode(textInput.value);
        if (!needle.length) return;
        const found = findBytes(rom, needle, pack);
        if (found < 0) {
          results.textContent = '未找到';
          return;
        }
        cursor = found;
        results.textContent = '命中 0x' + found.toString(16).toUpperCase();
        draw();
      },
    }),
    results,
  ]);
  container.appendChild(tools);

  // --- 常用地址 --------------------------------------------------------
  const quick = el('div', { class: 'tag-list', style: { margin: '10px 0' } });
  for (const structure of pack.structures.slice(0, 40)) {
    quick.appendChild(el('span', {
      class: 'scene-chip',
      style: { cursor: 'pointer' },
      text: structure.label + ' ' + formatOffset(structure.rom_offset),
      onclick: () => { cursor = structure.rom_offset; draw(); },
    }));
  }
  container.appendChild(quick);

  container.appendChild(grid);

  // --- 绘制 ------------------------------------------------------------
  function currentBytes(offset, length) {
    const out = new Uint8Array(length);
    out.set(rom.subarray(offset, offset + length));
    for (const patch of pack.patches) {
      const after = hexToBytes(patch.after_hex || '');
      for (let i = 0; i < after.length; i++) {
        const at = patch.offset + i;
        if (at >= offset && at < offset + length) out[at - offset] = after[i];
      }
    }
    return out;
  }

  /** The addresses that carry a local patch (so they can be highlighted). */
  function patchedAddresses() {
    const set = new Set();
    for (const patch of pack.patches) {
      const after = hexToBytes(patch.after_hex || '');
      for (let i = 0; i < after.length; i++) set.add(patch.offset + i);
    }
    return set;
  }
  const patched = patchedAddresses();

  function draw() {
    clear(grid);
    const pageStart = Math.max(0, Math.floor(cursor / PAGE) * PAGE);
    const bytes = currentBytes(pageStart, PAGE);
    for (let row = 0; row < ROWS; row++) {
      const rowStart = row * ROWS;
      const addr = pageStart + rowStart;
      if (addr >= rom.length) break;
      const hexCells = [];
      const ascii = [];
      for (let i = 0; i < ROWS; i++) {
        const at = addr + i;
        const b = at < rom.length ? bytes[rowStart + i] : 0;
        const cell = el('span', {
          class: 'editable' + (at === cursor ? ' hex-cursor' : '') +
            (patched.has(at) ? ' hex-changed' : ''),
          text: b.toString(16).padStart(2, '0'),
          title: '点击修改',
          onclick: () => {
            cursor = at;
            const input = window.prompt(
              `修改 0x${at.toString(16).toUpperCase()} 的字节（0x00–0xFF）`,
              b.toString(16).padStart(2, '0')
            );
            if (input === null) return;
            const value = parseInt(String(input).replace(/^0x/i, ''), 16);
            if (!Number.isFinite(value) || value < 0 || value > 0xff) {
              toast('请输入 0x00–0xFF 之间的值', 'error');
              return;
            }
            applyPatch(ctx, at, value);
            draw();
            ctx.onChange();
          },
        });
        hexCells.push(cell);
        ascii.push(b >= 0x20 && b < 0x7f ? String.fromCharCode(b) : '.');
      }
      grid.appendChild(el('div', { class: 'hex-row' }, [
        el('span', { class: 'hex-addr', text: addr.toString(16).padStart(6, '0').toUpperCase() }),
        el('span', { class: 'hex-bytes' }, hexCells.map((c, i) =>
          el('span', {}, [c, i % 8 === 7 ? '  ' : ' ']))),
        el('span', { class: 'hex-ascii', text: ascii.join('') }),
      ]));
    }
    grid.appendChild(el('div', { class: 'hex-row', style: { marginTop: '8px' } }, [
      el('span', { class: 'hex-addr', text: `页 0x${pageStart.toString(16).toUpperCase()}` }),
      el('span', { class: 'hex-ascii', text: '←/→ 键翻页' }),
    ]));
  }

  const onKey = (e) => {
    if (!container.isConnected) {
      window.removeEventListener('keydown', onKey);
      return;
    }
    if (e.key === 'ArrowLeft') { cursor = Math.max(0, cursor - 16); draw(); e.preventDefault(); }
    if (e.key === 'ArrowRight') { cursor = Math.min(rom.length - 1, cursor + 16); draw(); e.preventDefault(); }
  };
  window.addEventListener('keydown', onKey);

  draw();
  renderSide();

  /**
   * The right-hand column: where the cursor is, which table owns that address,
   * and the list of patches (with undo).
   *
   * Before this, the module had no patch list at all: the author could not see
   * what they had changed, could not undo it, and the build report did not even
   * render the warnings.
   */
  function renderSide() {
  const pack = ctx.pack;
  const rom = ctx.rom || ctx.baseRom;
  const where = locateAddress(pack, rom, cursor);
  const side = el('div', { class: 'detail-panel' }, [
    el('div', { class: 'detail-head' }, [
      el('h3', { text: `当前字节 0x${cursor.toString(16).toUpperCase()}` }),
    ]),
    el('div', { class: 'detail-sub' }, [
      el('span', { text: where ? where.text : '不被任何表写回' }),
    ]),
    where
      ? el('div', { class: 'rule-note rule-warn' }, [
        el('span', { class: 'rule-title', text: '落点' }),
        el('span', {
          text: `这个地址在${where.text}里。构建时那一条记录会整段写回，` +
            '所以在这里改它要靠补丁生效（补丁在结构写回之后才写）。',
        }),
      ])
      : null,
  ]);

  // --- 补丁清单 --------------------------------------------------------
  const patches = pack.patches || [];
  const list = el('div', { class: 'xref-block' }, [
    el('div', { class: 'xref-title', text: `补丁 ${patches.length} 条` }),
  ]);
  if (!patches.length) {
    list.appendChild(el('div', { class: 'xref-hint', text: '还没有补丁。在左边的十六进制视图里点一个字节就能改。' }));
  }
  for (const patch of patches) {
    const before = patch.before_hex || '';
    const after = patch.after_hex || '';
    list.appendChild(el('div', { class: 'xref-row' }, [
      el('span', { text: `0x${patch.offset.toString(16).toUpperCase()}` }),
      el('span', { text: `${before} → ${after}` }),
      el('button', {
        class: 'btn btn-tiny',
        text: '撤销',
        onclick: () => {
          pack.removePatch(patch);
          ctx.onChange();
          draw();
          renderSide();
          toast(`已撤销 0x${patch.offset.toString(16).toUpperCase()}`);
        },
      }),
    ]));
  }
  side.appendChild(list);
  side.appendChild(el('div', { class: 'detail-actions' }, [
    el('button', {
      class: 'btn btn-ghost',
      text: '全部撤销',
      onclick: () => {
        const n = pack.patches.length;
        pack.patches.length = 0;
        ctx.onChange();
        draw();
        renderSide();
        toast(`已撤销 ${n} 条补丁`);
      },
    }),
  ]));
  container.appendChild(side);
  }
}

/** Record a one-byte change as an explicit patch in the pack. */
export function applyPatch(ctx, offset, value) {
  const pack = ctx.pack;
  const rom = ctx.rom || ctx.baseRom;
  const original = rom ? rom[offset] : 0;
  const patch = pack.ensurePatch(offset, new Uint8Array([original]));
  const after = hexToBytes(patch.after_hex || '');
  const merged = new Uint8Array(Math.max(after.length, 1));
  merged.set(after, 0);
  // 要改的是**用户点的那一个字节**，不是这条补丁的第 0 字节。
  // 早先写的是 merged[0] = value：点一条多字节补丁（剧情操作数）里的
  // 第 2 个字节时，被改的其实是补丁的第 0 字节，而且没有任何提示。
  const index = Math.max(0, Math.min(merged.length - 1, offset - patch.offset));
  merged[index] = value & 0xff;
  patch.after_hex = bytesToHex(merged);
  if (!patch.before_hex) patch.before_hex = bytesToHex(new Uint8Array([original]));
  return patch;
}

/**
 * Which table record covers this address?
 *
 * The author needs to know where a byte lives before changing it: a byte
 * inside a structure record will be rewritten by that record's write-back.
 */
export function locateAddress(pack, rom, offset) {
  for (const structure of pack.structures || []) {
    const size = structure.entry_size || 0;
    for (const record of structure.records || []) {
      if (offset >= record.rom_offset && offset < record.rom_offset + size) {
        return {
          kind: 'structure',
          id: structure.id,
          label: structure.label,
          recordId: record.id,
          text: `${structure.label} 第 ${record.id + 1} 条记录内`,
        };
      }
    }
  }
  for (const table of pack.texts || []) {
    for (const record of table.records || []) {
      if (record.text_offset === null || record.text_offset === undefined) continue;
      const end = record.text_offset + (record.capacity || 0);
      if (offset >= record.text_offset && offset < end) {
        return {
          kind: 'text',
          id: table.id,
          label: table.label,
          recordId: record.id,
          text: `${table.label} 第 ${record.id + 1} 条文本内`,
        };
      }
    }
  }
  return null;
}

function findBytes(rom, needle, pack) {
  if (!needle.length) return -1;
  const haystack = new Uint8Array(rom);
  for (const patch of pack.patches) {
    const after = hexToBytes(patch.after_hex || '');
    for (let i = 0; i < after.length; i++) {
      const at = patch.offset + i;
      if (at >= 0 && at < haystack.length) haystack[at] = after[i];
    }
  }
  outer: for (let i = 0; i + needle.length <= haystack.length; i++) {
    for (let j = 0; j < needle.length; j++) {
      if (haystack[i + j] !== needle[j]) continue outer;
    }
    return i;
  }
  return -1;
}
