// 音频工作台：音效分派表 + 乐曲描述符 + 函数指针表。
//
// 通用结构编辑器只认「字段 → 表」的 id 关系；音频这一层是**指针**关系
// （一条音效指向一个 m4a 描述符地址），而且 81 个描述符分散在 81 张结构里，
// 一个字段级 relation 挂不下。所以描述符下拉、轨道表与「谁指向这个描述符」
// 都在这里自己渲染 —— 事实全部来自内容包：
//
//   * structure.ptr_relation.options  描述符地址 → 标签 / 轨道数 / 共用数
//   * derived.sound_stats             通道分布、函数指针表每个槽「是什么」
//
// 右侧详情面板按类分页签（描述符 / 谁指向它 / 播放入口）—— 见
// notes/specs/tabbed-side-panels.md。头部留在页签外面，内容进页签。
//
// 写回只有一条路：pack.setValue。

import { el, clear, formatOffset, toast } from '../ui.js';
import { fieldControl, fieldHint, originalValue } from '../fields.js';
import { backReferencesByPointer } from '../xref.js';
import { arraysIn, renderArrayTable, columnLabel } from '../slots.js';
import { bytesToHex, base64ToBytes, ROM_BASE } from '../bytes.js';
import { splitPane } from '../split.js';
import { TabPanel } from '../tabs.js';

const KIND_TEXT = {
  song: '乐曲',
  sfx: '短音效',
  empty: '空',
  unknown: '未解码',
};

const FILTERS = [
  { value: 'all', label: '全部' },
  { value: 'content', label: '有内容的' },
  { value: 'song', label: '乐曲' },
  { value: 'sfx', label: '短音效' },
  { value: 'empty', label: '空的' },
  { value: 'changed', label: '已改动的' },
];

/** 这张结构是不是音频域自己的。 */
export function isAudioStructure(id) {
  if (!id) return false;
  return id === 'sound_id_table' || id === 'function_pointer_table' ||
    id.startsWith('audio_song_');
}

/** 内容包里 sound_id_table.ptr_relation.options —— 描述符的完整选项集。 */
export function descriptorOptions(pack) {
  const structure = pack.structure('sound_id_table');
  const relation = structure && structure.ptr_relation;
  return (relation && relation.options) || [];
}

/** 地址 → 描述符事实。 */
export function descriptorMap(pack) {
  const map = new Map();
  for (const option of descriptorOptions(pack)) {
    map.set(option.value >>> 0, option);
  }
  return map;
}

/** 描述符的显示名：名字 + ROM 文件偏移（0x466068 这种写法）。 */
export function descriptorLabel(option) {
  const offset = (option.value >>> 0) - ROM_BASE;
  const hex = '0x' + offset.toString(16).toUpperCase();
  if (option.kind === 'empty') return `空哨兵（没有声音）· ROM ${hex}`;
  return `${option.label} · ROM ${hex}`;
}

/**
 * 谁指向这个地址？
 *
 * `xref.backReferencesByPointer` 扫全包的 ptr 字段；这里把结果整理成
 * 音频能读懂的样子（「音效 #7 · 播放通道 0」）。
 */
export function pointerBackRefs(pack, address) {
  const out = [];
  for (const ref of backReferencesByPointer(pack, address >>> 0)) {
    const values = ref.record.values || {};
    let label;
    if (ref.structure.id === 'sound_id_table') {
      label = `音效 #${ref.record.id} · 播放通道 ${values.player_index}`;
    } else {
      label = `${ref.structure.label} · ${ref.field.label || ref.field.key}`;
    }
    out.push({
      structureId: ref.structure.id,
      recordId: ref.record.id,
      module: ref.structure.module,
      structure: ref.structure,
      record: ref.record,
      label,
    });
  }
  return out;
}

/** 跳到原版 ROM 的某个字节偏移（原始字节编辑器）。 */
function openRawAt(ctx, offset) {
  if (ctx.goModule) ctx.goModule('raw');
  ctx.openPanel('raw-offset', 'raw', { offset });
}

/** 复制到剪贴板（无剪贴板的环境里也不报错）。 */
function copyToClipboard(text) {
  if (typeof navigator === 'undefined' || !navigator.clipboard) return;
  navigator.clipboard.writeText(text);
}

/**
 * 这张结构表里哪些记录改过了（rom_offset 集合）。
 *
 * 判定走 `pack.changedStructureRecords` —— 与通用表格编辑器同一套口径
 * （按字节比，改过又改回去不算改）。
 */
function changedOffsets(pack, structure) {
  const out = new Set();
  if (!structure) return out;
  for (const record of pack.changedStructureRecords(structure)) {
    out.add(record.rom_offset);
  }
  return out;
}

/** 这几个字段里有几处改了（和记录里的原始字节比）。 */
function fieldsChanged(structure, record, fields) {
  const values = record.values || {};
  let n = 0;
  for (const field of fields || []) {
    if (!field) continue;
    const original = originalValue(structure, record, field);
    if (JSON.stringify(original) !== JSON.stringify(values[field.key])) n += 1;
  }
  return n;
}

/**
 * 函数指针表里与这些音效号对应的播放入口槽。
 *
 * 1..11 槽是「movs r0,#k」的播放 thunk；k 与音效号的对应是**静态推定**
 * （notes/audio-ux-redesign-20261021.md §4.4）。
 */
function playEntrySlots(pack, soundIds) {
  const stats = (pack.derived && pack.derived.sound_stats) || {};
  const slots = stats.function_pointer_slots || {};
  const wanted = (soundIds || []).map((id) => Number(id));
  const out = [];
  for (const key of Object.keys(slots)) {
    const slot = slots[key];
    if (!slot || slot.kind !== 'play_entry') continue;
    if (!wanted.includes(Number(slot.sound_id))) continue;
    out.push({ ...slot, id: Number(key) });
  }
  return out;
}

/** 播放入口在函数指针表里的那条记录（原始字节位置用）。 */
function playEntryRecord(pack, slotId) {
  const table = pack.structure('function_pointer_table');
  if (!table) return null;
  return (table.records || []).find((r) => r.id === slotId) || null;
}

/** 函数指针表覆盖的音效号范围（写成人话）。 */
function playEntryRange(pack) {
  const stats = (pack.derived && pack.derived.sound_stats) || {};
  const slots = stats.function_pointer_slots || {};
  const ids = [];
  for (const key of Object.keys(slots)) {
    const slot = slots[key];
    if (!slot || slot.kind !== 'play_entry') continue;
    ids.push(Number(slot.sound_id));
  }
  if (!ids.length) return '（没有）';
  const min = Math.min(...ids);
  const max = Math.max(...ids);
  return min === max ? `#${min}` : `#${min} 到 #${max}`;
}

/**
 * 「播放入口（推定）」块。
 *
 * @param {object} ctx
 * @param {Array} slots       playEntrySlots() 的结果
 * @param {string} emptyText  没有对应槽时写什么
 */
function renderPlayEntryBlock(ctx, slots, emptyText) {
  const block = el('div', { class: 'xref-block audio-play-entry' }, [
    el('div', { class: 'xref-title', text: '播放入口（推定）' }),
  ]);
  if (!slots.length) {
    block.appendChild(el('div', { class: 'xref-hint', text: emptyText }));
    return block;
  }
  block.appendChild(el('div', {
    class: 'xref-hint',
    text: '槽里的 thunk 与音效号的对应是静态推定，尚未由运行时证据闭环。',
  }));
  for (const slot of slots) {
    block.appendChild(el('div', { class: 'xref-row' }, [
      el('span', { text: `槽 ${slot.id} · 音效 #${slot.sound_id}` }),
      el('span', { class: 'audio-estimate', text: '静态推定' }),
    ]));
    block.appendChild(el('div', { class: 'xref-row' }, [
      el('span', { text: `代码 ${slot.code} → 目标 ${slot.target}` }),
    ]));
    const record = playEntryRecord(ctx.pack, slot.id);
    if (record) {
      block.appendChild(el('div', { class: 'xref-row' }, [
        el('button', {
          class: 'btn btn-tiny',
          text: '在原始字节里看这一段',
          onclick: () => openRawAt(ctx, record.rom_offset),
        }),
      ]));
    }
  }
  return block;
}

/**
 * 一个字段：标签 + 控件 + 提示 + 已改标记 + 恢复原值。
 *
 * 控件由调用方给（描述符下拉、通道下拉、通用字段控件……），
 * 提示可以是随值变化的函数（播放配置的警告就是这样）。
 */
function renderField(ctx, structure, record, field, control) {
  const wrapper = el('div', { class: 'field' });
  const label = el('label', { class: 'field-label' }, [
    el('span', { text: field.label || field.key }),
  ]);
  const marker = el('span', { class: 'tag tag-warn', text: '已改' });
  const restore = el('button', {
    class: 'btn btn-tiny',
    text: '↺',
    title: '把这个字段恢复成原值',
    onclick: () => {
      const original = originalValue(structure, record, field);
      ctx.pack.setValue(structure, record, field.key, original);
      ctx.onChange();
      refresh();
      toast(`已恢复「${field.label || field.key}」的原值 ${original}`);
    },
  });
  label.appendChild(marker);
  label.appendChild(restore);
  label.appendChild(el('span', { class: 'field-offset', text: `+${formatOffset(field.offset)}` }));

  const hintLine = el('div', { class: 'field-hint' });
  const refresh = () => {
    const original = originalValue(structure, record, field);
    const current = record.values ? record.values[field.key] : undefined;
    const changed = JSON.stringify(original) !== JSON.stringify(current);
    wrapper.classList.toggle('field-changed', changed);
    marker.classList.toggle('hidden', !changed);
    restore.classList.toggle('hidden', !changed);
    const lines = typeof control.hint === 'function'
      ? control.hint()
      : (control.hint || fieldHint(ctx.pack, structure, record, field));
    if (changed) lines.push(`原值 ${original}`);
    hintLine.textContent = lines.join(' · ');
  };
  wrapper.appendChild(label);
  wrapper.appendChild(control.node);
  wrapper.appendChild(hintLine);
  refresh();
  return wrapper;
}

/** 状态徽章：乐曲 / 短音效 / 空 / 未解码。 */
function statusPill(kind) {
  const cls = kind === 'song' ? 'pill-song'
    : kind === 'sfx' ? 'pill-sfx'
      : kind === 'empty' ? 'pill-empty' : 'pill-raw';
  return el('span', { class: 'pill ' + cls, text: KIND_TEXT[kind] || kind });
}

// --------------------------------------------------------------------------
// 音效分派表
// --------------------------------------------------------------------------
class AudioSoundTable {
  constructor(pack, ctx, structure) {
    this.pack = pack;
    this.ctx = ctx;
    this.structure = structure;
    this.descriptors = descriptorMap(pack);
    this.query = '';
    this.filter = 'all';
    this.jumpTo = '';
    this.selected = null;
  }

  /** 一条音效当前指向的描述符。 */
  descriptorOf(record) {
    const address = (record.values.descriptor_ptr >>> 0);
    if (!address) {
      return {
        address,
        option: null,
        kind: 'unknown',
        tracks: null,
        label: '（空指针）',
      };
    }
    const option = this.descriptors.get(address);
    if (!option) {
      return {
        address,
        option: null,
        kind: 'unknown',
        tracks: null,
        label: `未解码描述符 · ROM 0x${(address - ROM_BASE).toString(16).toUpperCase()}`,
      };
    }
    return {
      address,
      option,
      kind: option.kind,
      tracks: option.tracks,
      label: descriptorLabel(option),
    };
  }

  matchesQuery(record, query) {
    if (String(record.id).includes(query)) return true;
    if (query.startsWith('#') && String(record.id).includes(query.slice(1))) return true;
    const address = record.values.descriptor_ptr >>> 0;
    const hex = address.toString(16).toLowerCase();
    const offset = (address - ROM_BASE).toString(16).toLowerCase();
    if (hex.includes(query) || offset.includes(query)) return true;
    if (String(record.values.player_index) === query) return true;
    return false;
  }

  matchesFilter(record) {
    const info = this.descriptorOf(record);
    switch (this.filter) {
      case 'content': return info.kind !== 'empty' && info.kind !== 'unknown';
      case 'song': return info.kind === 'song';
      case 'sfx': return info.kind === 'sfx';
      case 'empty': return info.kind === 'empty';
      case 'changed': return this.isDirty(record);
      default: return true;
    }
  }

  isDirty(record) {
    const bytes = this.pack.recordBytes(this.structure, record);
    const raw = record.raw ? base64ToBytes(record.raw) : new Uint8Array(0);
    return bytesToHex(bytes) !== bytesToHex(raw);
  }

  get records() {
    const all = this.structure.records || [];
    const query = this.query.trim().toLowerCase();
    let list = all;
    if (query) list = list.filter((r) => this.matchesQuery(r, query));
    if (this.filter !== 'all') list = list.filter((r) => this.matchesFilter(r));
    return list;
  }

  render(container) {
    clear(container);
    const structure = this.structure;
    const stats = (this.pack.derived && this.pack.derived.sound_stats) || {};

    const filterSelect = el('select', {
      class: 'num-input audio-filter',
      onchange: (e) => {
        this.filter = e.target.value;
        this.renderTable();
      },
    });
    for (const filter of FILTERS) {
      filterSelect.appendChild(el('option', {
        value: filter.value, text: filter.label, selected: filter.value === this.filter,
      }));
    }

    const head = el('div', { class: 'panel-head' }, [
      el('div', {}, [
        el('h2', { text: '音效分派表（sound-ID）' }),
        el('div', { class: 'panel-sub' }, [
          el('span', { text: `ROM ${formatOffset(structure.rom_offset)}` }),
          el('span', { text: `${structure.entry_size || 0} 字节/行` }),
          el('span', { text: `${(structure.records || []).length} 条` }),
          el('span', { text: `描述符 ${stats.descriptor_count ?? this.descriptors.size} 个` }),
          structure.verification ? el('span', { text: structure.verification }) : null,
        ]),
      ]),
      el('div', { class: 'panel-tools' }, [
        el('input', {
          class: 'search',
          type: 'search',
          placeholder: '搜音效 id、描述符地址…',
          value: this.query,
          oninput: (e) => {
            this.query = e.target.value;
            this.renderTable();
          },
        }),
        filterSelect,
        el('input', {
          class: 'num-input',
          type: 'text',
          style: { width: '96px' },
          placeholder: '跳到音效 #',
          value: this.jumpTo,
          onchange: (e) => {
            this.jumpTo = e.target.value;
            const id = Number(e.target.value.replace(/^#/, ''));
            const record = (structure.records || []).find((r) => r.id === id);
            if (!record) {
              toast(`没有音效 #${e.target.value}`, 'error');
              return;
            }
            this.openDetail(record);
          },
        }),
      ]),
    ]);

    const tableWrap = el('div', { class: 'table-wrap' });
    const detail = el('div', { class: 'detail-panel hidden' });

    // 右侧详情：头部留在页签外面，内容进页签。
    //
    // 页签面板挂在**自己的容器**里（tabHost），openDetail() 只重画
    // 头部 / 摘要 / 动作与页签内容 —— 页签条本身不重建，
    // 这样「停在哪一页」与记住的页签都还在。
    this.detailHead = el('div', { class: 'detail-head' });
    this.detailSub = el('div', { class: 'detail-sub' });
    this.tabHost = el('div', { class: 'detail-tabs' });
    this.detailActions = el('div', { class: 'detail-actions' });
    detail.appendChild(this.detailHead);
    detail.appendChild(this.detailSub);
    detail.appendChild(this.tabHost);
    detail.appendChild(this.detailActions);

    // 页签面板只建一次：换音效只 refresh，页签条与记住的页签都还在。
    this.tabs = new TabPanel(this.tabSpecs(), { key: 'editor.audio', pack: this.pack });
    this.tabHost.appendChild(this.tabs.element);

    container.appendChild(head);
    container.appendChild(el('div', { class: 'rule-note' }, [
      el('span', { class: 'rule-title', text: '这一层能改什么' }),
      el('span', {
        text: '这里改的是「哪个音效播哪首曲子」：改描述符指针就行。'
          + '音频采样本体是压缩载荷，不在这些表里；改采样要走 m4a 导入流程。',
      }),
    ]));
    container.appendChild(splitPane(tableWrap, detail, { key: 'editor.audio' }));
    this.tableWrap = tableWrap;
    this.detail = detail;
    this.renderTable();
  }

  renderTable() {
    clear(this.tableWrap);
    const records = this.records;
    const table = el('table', { class: 'grid' });
    table.appendChild(el('thead', {}, [el('tr', {}, [
      el('th', { class: 'col-id', text: '音效 id' }),
      el('th', { text: '描述符' }),
      el('th', { class: 'col-num', text: '轨道数' }),
      el('th', { class: 'col-num', text: '通道' }),
      el('th', { text: '状态' }),
      el('th', { class: 'col-actions', text: '' }),
    ])]));
    const body = el('tbody');
    for (const record of records) {
      const dirty = this.isDirty(record);
      const info = this.descriptorOf(record);
      body.appendChild(el('tr', {
        onclick: () => this.openDetail(record),
        class: (this.selected === record ? 'selected' : '') + (dirty ? ' changed' : ''),
      }, [
        el('td', { class: 'col-id', text: `#${record.id}` }),
        el('td', { class: 'text-cell', text: info.label }),
        el('td', { class: 'col-num', text: info.tracks === null ? '—' : String(info.tracks) }),
        el('td', { class: 'col-num', text: String(record.values.player_index) }),
        el('td', {}, [statusPill(info.kind)]),
        el('td', { class: 'col-actions' }, [
          el('button', {
            class: 'btn btn-tiny',
            text: dirty ? '已改' : '编辑',
            onclick: (e) => {
              e.stopPropagation();
              this.openDetail(record);
            },
          }),
        ]),
      ]));
    }
    table.appendChild(body);
    this.tableWrap.appendChild(table);
    if (!records.length) {
      this.tableWrap.appendChild(el('div', { class: 'empty', text: '没有匹配的音效' }));
    }
    const total = (this.structure.records || []).length;
    const dirtyCount = (this.structure.records || [])
      .filter((r) => this.isDirty(r)).length;
    this.tableWrap.appendChild(el('div', { class: 'table-foot' }, [
      el('span', { text: `显示 ${records.length} / ${total} 条` }),
      dirtyCount ? el('span', { class: 'tag tag-warn', text: `已改 ${dirtyCount} 条` }) : null,
    ]));
  }

  openDetail(record) {
    this.selected = record;
    this.detail.classList.remove('hidden');
    const structure = this.structure;
    const ctx = this.ctx;
    const info = this.descriptorOf(record);
    const values = record.values || {};

    // --- 头部（留在页签外面） ---------------------------------------------
    clear(this.detailHead);
    this.detailHead.appendChild(el('h3', { text: `音效 #${record.id} · ${info.label}` }));
    this.detailHead.appendChild(el('div', { class: 'detail-nav' }, [
      el('button', {
        class: 'btn btn-tiny', text: '← 上一条',
        onclick: () => this.step(-1),
      }),
      el('button', {
        class: 'btn btn-tiny', text: '下一条 →',
        onclick: () => this.step(1),
      }),
      el('button', {
        class: 'btn btn-ghost', text: '✕',
        onclick: () => {
          this.detail.classList.add('hidden');
          this.selected = null;
          this.renderTable();
        },
      }),
    ]));

    clear(this.detailSub);
    for (const node of [
      el('span', { text: `ROM ${formatOffset(record.rom_offset)}` }),
      el('span', { text: `音效 id ${record.id}` }),
      el('span', { text: `${structure.entry_size} 字节/行` }),
      el('span', { text: `通道 ${values.player_index}` }),
      el('span', { text: info.tracks === null ? '轨道 —' : `轨道 ${info.tracks}` }),
      el('span', { text: KIND_TEXT[info.kind] || info.kind }),
      this.isDirty(record) ? el('span', { class: 'tag tag-warn', text: '已改动' }) : null,
    ]) {
      if (node) this.detailSub.appendChild(node);
    }

    // --- 内容（进页签） ---------------------------------------------------
    // 页签面板在 render() 里就建好了，这里只重画当前页的内容。
    this.tabs.refresh();

    // --- 动作（留在页签外面） ---------------------------------------------
    clear(this.detailActions);
    this.detailActions.appendChild(el('button', {
      class: 'btn btn-ghost',
      text: '恢复原值',
      onclick: () => {
        for (const field of structure.fields || []) {
          this.pack.setValue(structure, record, field.key,
            originalValue(structure, record, field));
        }
        this.openDetail(record);
        this.renderTable();
        ctx.onChange();
      },
    }));
    this.detailActions.appendChild(el('button', {
      class: 'btn btn-ghost',
      text: '复制十六进制',
      onclick: () => {
        const bytes = this.pack.recordBytes(structure, record);
        copyToClipboard(bytesToHex(bytes));
        toast('已复制该记录的十六进制字节');
      },
    }));
    this.detailActions.appendChild(el('button', {
      class: 'btn btn-ghost',
      text: '在原始字节里看这一行',
      onclick: () => openRawAt(ctx, record.rom_offset),
    }));
  }

  // --- 右侧面板的页签 -------------------------------------------------------

  /**
   * 右侧面板的页签。
   *
   * 内容按类分 —— 描述符 / 谁指向它 / 播放入口。
   * 页签 id 用英文，label 用中文；key 记住上次停在哪一页。
   *
   * render() 里的内容函数不缓存节点：切走的那一页不在 DOM 里
   * （TabPanel 的约定，见 rom-editor/js/tabs.js）。
   */
  tabSpecs() {
    return [
      {
        id: 'descriptor',
        label: '描述符',
        hint: '这个音效指向哪个 m4a 描述符：指针、轨道数与共用情况',
        badge: () => this.badgeDescriptor(),
        render: () => this.renderDescriptorTab(),
      },
      {
        id: 'refs',
        label: '谁指向它',
        hint: '反向引用：哪些音效共用这个描述符',
        badge: () => this.badgeRefs(),
        render: () => this.renderRefsTab(),
      },
      {
        id: 'playback',
        label: '播放入口',
        hint: '播放通道与播放配置，以及推定出来的播放入口',
        badge: () => this.badgePlayback(),
        render: () => this.renderPlaybackTab(),
      },
    ];
  }

  /** 一个分组框（折叠组的头 + 体）。 */
  groupBox(name, count, body) {
    return el('div', { class: 'group' }, [
      el('div', { class: 'group-head' }, [
        el('span', { class: 'group-caret', text: '▾' }),
        el('span', { class: 'group-name', text: name }),
        el('span', { class: 'group-count', text: count }),
      ]),
      body,
    ]);
  }

  /** 「描述符」这一页：这个音效指向哪个描述符。 */
  renderDescriptorTab() {
    const record = this.selected;
    if (!record) return el('div', { class: 'empty', text: '没有选中的音效。' });
    const structure = this.structure;
    const field = structure.fields.find((f) => f.key === 'descriptor_ptr');
    const body = el('div', { class: 'group-body' });
    if (field) {
      body.appendChild(renderField(this.ctx, structure, record, field, {
        node: this.descriptorControl(record),
        hint: () => this.descriptorHint(record),
      }));
      body.appendChild(this.customAddressRow(record));
    }
    return el('div', { class: 'field-list' }, [
      this.groupBox('描述符', '1 项', body),
    ]);
  }

  /** 「谁指向它」这一页：反向引用（共用这个描述符的音效）。 */
  renderRefsTab() {
    const record = this.selected;
    if (!record) return el('div', { class: 'empty', text: '没有选中的音效。' });
    return this.pointerBlock(record);
  }

  /** 「播放入口」这一页：播放通道 / 播放配置 + 推定出来的播放入口。 */
  renderPlaybackTab() {
    const record = this.selected;
    if (!record) return el('div', { class: 'empty', text: '没有选中的音效。' });
    const structure = this.structure;
    const channelField = structure.fields.find((f) => f.key === 'player_index');
    const configField = structure.fields.find((f) => f.key === 'player_config');
    const body = el('div', { class: 'group-body' });
    let count = 0;
    if (channelField) {
      count += 1;
      body.appendChild(renderField(this.ctx, structure, record, channelField, {
        node: this.enumControl(record, channelField),
        hint: () => fieldHint(this.pack, structure, record, channelField),
      }));
    }
    if (configField) {
      count += 1;
      body.appendChild(renderField(this.ctx, structure, record, configField, {
        node: this.configControl(record, configField),
        hint: () => this.configHint(record, configField),
      }));
    }
    const wrap = el('div', { class: 'field-list' }, [
      this.groupBox('播放', `${count} 项`, body),
    ]);
    wrap.appendChild(this.playEntryBlock(record));
    return wrap;
  }

  /**
   * 推定出来的播放入口。
   *
   * 函数指针表的 1..11 槽是「movs r0,#k」的播放 thunk；k 与音效号的对应
   * 是**静态推定**（notes/audio-ux-redesign-20261021.md §4.4）。
   * 这里把同号的那一槽摆出来，并明确标成推定。
   */
  playEntryBlock(record) {
    const slots = playEntrySlots(this.pack, [record.id]);
    return renderPlayEntryBlock(this.ctx, slots,
      `函数指针表只覆盖音效 ${playEntryRange(this.pack)}，这个音效没有对应的入口槽。`);
  }

  /** 函数指针表里与这个音效同号的播放入口槽（推定）。 */
  playEntrySlot(record) {
    return playEntrySlots(this.pack, [record.id])[0] || null;
  }

  // --- 页签角标：这一类改了几处 -------------------------------------------

  /**
   * 这张结构表里哪些记录改过了（rom_offset 集合）。
   *
   * 判定走 pack.changedStructureRecords —— 与通用表格编辑器同一套口径
   * （按字节比，改过又改回去不算改）。
   */
  changedOffsets(structure) {
    return changedOffsets(this.pack, structure);
  }

  /** 这几个字段里有几处改了（和记录里的原始字节比）。 */
  fieldsChanged(record, fields) {
    return fieldsChanged(this.structure, record, fields);
  }

  /** 角标：描述符那一类改了几处（描述符指针）。 */
  badgeDescriptor() {
    const record = this.selected;
    if (!record) return null;
    if (!this.changedOffsets(this.structure).has(record.rom_offset)) return null;
    const field = this.structure.fields.find((f) => f.key === 'descriptor_ptr');
    return this.fieldsChanged(record, [field]) || null;
  }

  /** 角标：谁指向它 —— 共用这个描述符的音效里，除了本条以外改过几条。 */
  badgeRefs() {
    const record = this.selected;
    if (!record) return null;
    const address = record.values.descriptor_ptr >>> 0;
    const changed = this.changedOffsets(this.structure);
    let n = 0;
    for (const other of this.structure.records || []) {
      if (other === record) continue;
      if ((other.values.descriptor_ptr >>> 0) !== address) continue;
      if (changed.has(other.rom_offset)) n += 1;
    }
    return n || null;
  }

  /** 角标：播放入口 —— 播放通道 / 播放配置改了几处，外加入口槽本身。 */
  badgePlayback() {
    const record = this.selected;
    if (!record) return null;
    let n = 0;
    if (this.changedOffsets(this.structure).has(record.rom_offset)) {
      const fields = this.structure.fields
        .filter((f) => f.key === 'player_index' || f.key === 'player_config');
      n += this.fieldsChanged(record, fields);
    }
    const entry = this.playEntrySlot(record);
    const slot = entry ? playEntryRecord(this.pack, entry.id) : null;
    const table = this.pack.structure('function_pointer_table');
    if (slot && table && this.changedOffsets(table).has(slot.rom_offset)) n += 1;
    return n || null;
  }

  /** 描述符下拉：81 个已导出的描述符，一个选项一个地址。 */
  descriptorControl(record) {
    const address = record.values.descriptor_ptr >>> 0;
    const select = el('select', {
      class: 'num-input audio-descriptor',
      onchange: (e) => {
        const next = Number(e.target.value);
        if (!Number.isFinite(next)) return;
        this.pack.setValue(this.structure, record, 'descriptor_ptr', next);
        this.ctx.onChange();
        this.openDetail(record);
        this.renderTable();
        const info = this.descriptorOf(record);
        toast(`音效 #${record.id} 现在指向 ${info.label}`);
      },
    });
    const known = this.descriptors.has(address);
    if (!known) {
      select.appendChild(el('option', {
        value: String(address),
        text: `未解码描述符 · ROM 0x${(address - ROM_BASE).toString(16).toUpperCase()}`,
        selected: true,
      }));
    }
    for (const option of descriptorOptions(this.pack)) {
      const shared = option.shared > 1 ? `（${option.shared} 个音效共用）` : '';
      select.appendChild(el('option', {
        value: String(option.value),
        text: descriptorLabel(option) + shared,
        selected: known && option.value === address,
      }));
    }
    return select;
  }

  descriptorHint(record) {
    const info = this.descriptorOf(record);
    const lines = [];
    if (info.kind === 'empty') {
      lines.push(`空哨兵：0 个轨道 —— 这个描述符没有声音（${info.option.shared} 个音效共用）`);
    } else if (info.kind === 'unknown') {
      lines.push('这个地址不在已导出的描述符里：编辑器改不了它的轨道');
    } else {
      lines.push(`轨道 ${info.tracks} 条`);
      if (info.option.shared > 1) {
        lines.push(`${info.option.shared} 个音效共用这个描述符`);
      }
      lines.push(`音效 #${info.option.sound_ids.join('、#')} 在用`);
    }
    return lines;
  }

  /** 播放通道 / 播放配置：取值域已知 → 下拉。 */
  enumControl(record, field) {
    const value = record.values[field.key];
    const select = el('select', {
      class: 'num-input',
      onchange: (e) => {
        const next = Number(e.target.value);
        this.pack.setValue(this.structure, record, field.key, next);
        this.ctx.onChange();
        this.openDetail(record);
        this.renderTable();
      },
    });
    for (const [raw, label] of Object.entries(field.enum || {})) {
      select.appendChild(el('option', {
        value: raw, text: `${label}`, selected: String(value) === raw,
      }));
    }
    if (value !== undefined && (field.enum || {})[String(value)] === undefined) {
      select.appendChild(el('option', {
        value: String(value), text: `${value}（取值域外）`, selected: true,
      }));
    }
    return select;
  }

  /** 播放配置：默认与播放通道相同，改成不等时给警告。 */
  configControl(record, field) {
    const channel = Number(record.values.player_index);
    const value = Number(record.values.player_config);
    const select = el('select', {
      class: 'num-input',
      onchange: (e) => {
        const next = Number(e.target.value);
        this.pack.setValue(this.structure, record, field.key, next);
        this.ctx.onChange();
        this.openDetail(record);
        this.renderTable();
      },
    });
    select.appendChild(el('option', {
      value: String(channel),
      text: `与播放通道相同（当前 ${channel}）`,
      selected: value === channel,
    }));
    for (const [raw, label] of Object.entries(field.enum || {})) {
      if (Number(raw) === channel) continue;
      select.appendChild(el('option', {
        value: raw, text: `${raw} · ${label}`, selected: value === Number(raw),
      }));
    }
    return select;
  }

  configHint(record, field) {
    const lines = fieldHint(this.pack, this.structure, record, field);
    const channel = Number(record.values.player_index);
    const value = Number(record.values.player_config);
    if (value !== channel) {
      lines.push('这一列在原生 ROM 的 159 行里始终等于播放通道，改了可能没有效果');
    }
    return lines;
  }

  /**
   * 自定义地址：填一个不在已导出描述符里的地址。
   *
   * 下拉里只有 81 个已解码的描述符；作者偶尔要指向别处（比如手工搭的描述符），
   * 所以留一个十六进制输入框。它是描述符字段**之外**的一行，不占用下拉。
   */
  customAddressRow(record) {
    const address = record.values.descriptor_ptr >>> 0;
    const input = el('input', {
      class: 'num-input ptr-box',
      type: 'text',
      spellcheck: 'false',
      value: address ? '0x' + address.toString(16).toUpperCase().padStart(8, '0') : '',
      onchange: (e) => {
        const text = String(e.target.value).trim();
        const parsed = text.startsWith('0x')
          ? parseInt(text.slice(2), 16)
          : (/[a-fA-F]/.test(text) ? parseInt(text, 16) : Number(text));
        if (!Number.isFinite(parsed) || parsed < 0) {
          toast('请输入十六进制地址', 'error');
          e.target.value = address ? '0x' + address.toString(16).toUpperCase() : '';
          return;
        }
        this.pack.setValue(this.structure, record, 'descriptor_ptr', parsed);
        this.ctx.onChange();
        this.openDetail(record);
        this.renderTable();
      },
    });
    return el('div', { class: 'field' }, [
      el('label', { class: 'field-label' }, [
        el('span', { text: '自定义地址' }),
        el('span', { class: 'field-offset', text: '下拉之外的地址' }),
      ]),
      input,
      el('div', {
        class: 'field-hint',
        text: '填一个不在 81 个已导出描述符里的地址。'
          + '编辑器读不懂它的轨道，只会原样写回这 4 个字节。',
      }),
    ]);
  }

  /** 「谁指向这个描述符」：指针级反查。 */
  pointerBlock(record) {
    const address = record.values.descriptor_ptr >>> 0;
    const refs = pointerBackRefs(this.pack, address);
    const block = el('div', { class: 'xref-block' }, [
      el('div', { class: 'xref-title', text: `被谁引用（${refs.length} 处）` }),
    ]);
    if (!refs.length) {
      block.appendChild(el('div', {
        class: 'xref-hint',
        text: '没有别的字段指向这个地址。',
      }));
      return block;
    }
    block.appendChild(el('div', {
      class: 'xref-hint',
      text: '改这个描述符会同时影响下面这些音效。',
    }));
    for (const ref of refs.slice(0, 12)) {
      block.appendChild(el('div', { class: 'xref-row' }, [
        el('span', { text: ref.label }),
        el('button', {
          class: 'btn btn-tiny',
          text: '跳过去',
          onclick: () => {
            if (!this.ctx.onJump) return;
            this.ctx.onJump({
              module: ref.module,
              kind: 'structure',
              id: ref.structureId,
              recordId: ref.recordId,
              label: ref.structure.label,
            });
          },
        }),
      ]));
    }
    if (refs.length > 12) {
      block.appendChild(el('div', {
        class: 'xref-hint',
        text: `…还有 ${refs.length - 12} 处`,
      }));
    }
    return block;
  }

  step(delta) {
    const records = this.structure.records || [];
    if (!this.selected) {
      if (records.length) this.openDetail(records[0]);
      return;
    }
    const at = records.indexOf(this.selected);
    const next = records[at + delta];
    if (!next) {
      toast(delta > 0 ? '已经是最后一条了' : '已经是第一条了', 'error');
      return;
    }
    this.openDetail(next);
  }
}

// --------------------------------------------------------------------------
// 乐曲描述符
// --------------------------------------------------------------------------
function renderSongDescriptor(container, ctx, structure, params) {
  clear(container);
  const pack = ctx.pack;
  const record = (structure.records || [])[0];
  if (!record) {
    container.appendChild(el('div', { class: 'empty', text: '这张表里没有记录' }));
    return;
  }
  const values = record.values || {};
  const address = structure.rom_offset + ROM_BASE;
  const tracks = values.track_count || 0;
  const descriptor = descriptorMap(pack).get(address);
  const users = pointerBackRefs(pack, address);

  container.appendChild(el('div', { class: 'panel-head' }, [
    el('div', {}, [
      el('h2', { text: structure.label || structure.id }),
      el('div', { class: 'panel-sub' }, [
        el('span', { text: `ROM ${formatOffset(structure.rom_offset)}` }),
        el('span', { text: `${structure.entry_size} 字节` }),
        el('span', { text: `轨道 ${tracks}` }),
        el('span', { text: `音色组 0x${(values.voicegroup_ptr >>> 0).toString(16).toUpperCase()}` }),
        structure.verification ? el('span', { text: structure.verification }) : null,
      ]),
    ]),
  ]));

  container.appendChild(el('div', { class: 'rule-note' }, [
    el('span', { class: 'rule-title', text: '这一层能改什么' }),
    el('span', {
      text: '音频采样是压缩载荷，编辑器改不了采样本身；'
        + '这里能改的是「指向哪段轨道数据」。',
    }),
  ]));

  // 谁指向这个描述符
  const refsSection = () => {
    const block = el('div', { class: 'xref-block' }, [
      el('div', { class: 'xref-title', text: `被谁引用（${users.length} 处）` }),
    ]);
    if (!users.length) {
      block.appendChild(el('div', { class: 'xref-hint', text: '没有音效指向这个描述符。' }));
    } else {
      block.appendChild(el('div', { class: 'xref-hint', text: '这些音效用的是这首曲子。' }));
      for (const ref of users.slice(0, 12)) {
        block.appendChild(el('div', { class: 'xref-row' }, [
          el('span', { text: ref.label }),
          el('button', {
            class: 'btn btn-tiny',
            text: '跳过去',
            onclick: () => {
              if (!ctx.onJump) return;
              ctx.onJump({
                module: ref.module,
                kind: 'structure',
                id: ref.structureId,
                recordId: ref.recordId,
                label: ref.structure.label,
              });
            },
          }),
        ]));
      }
    }
    const wrap = el('div', {}, [block]);
    if (descriptor && descriptor.sound_ids.length) {
      wrap.appendChild(el('div', { class: 'section-note' }, [
        `音效 #${descriptor.sound_ids.join('、#')} 指向这个描述符。`,
      ]));
    }
    return wrap;
  };

  // 描述符本身：歌曲头 + 轨道
  const descriptorSection = () => {
    const form = el('div', { class: 'field-list' });
    const headerFields = (structure.fields || [])
      .filter((f) => !f.array);
    const headerGroup = el('div', { class: 'group' }, [
      el('div', { class: 'group-head' }, [
        el('span', { class: 'group-caret', text: '▾' }),
        el('span', { class: 'group-name', text: '歌曲头' }),
        el('span', { class: 'group-count', text: `${headerFields.length} 项` }),
      ]),
    ]);
    const headerBody = el('div', { class: 'group-body' });
    for (const field of headerFields) {
      const control = fieldControl(
        { pack, onChange: ctx.onChange, onJump: ctx.onJump },
        structure, record, field);
      headerBody.appendChild(renderField(ctx, structure, record, field, control));
    }
    headerGroup.appendChild(headerBody);
    form.appendChild(headerGroup);

    // 轨道：一张 N 行的表（导出器给了 array/index/item）
    const trackFields = (structure.fields || []).filter((f) => f.array === 'tracks');
    const arrays = arraysIn(trackFields);
    const trackGroup = el('div', { class: 'group' }, [
      el('div', { class: 'group-head' }, [
        el('span', { class: 'group-caret', text: '▾' }),
        el('span', { class: 'group-name', text: '轨道' }),
        el('span', { class: 'group-count', text: `${tracks} 条` }),
      ]),
    ]);
    const trackBody = el('div', { class: 'group-body' });
    if (arrays.length) {
      for (const array of arrays) {
        trackBody.appendChild(el('div', { class: 'slot-block' }, [
          el('div', {
            class: 'slot-caption',
            text: `${columnLabel(array.name, 'id')}列表（${array.rows.size} 项）`,
          }),
          renderArrayTable(
            { pack, onChange: ctx.onChange, onJump: ctx.onJump },
            structure, record, array),
        ]));
      }
    } else {
      trackBody.appendChild(el('div', {
        class: 'field-hint',
        text: '这个描述符没有轨道（track_count = 0）：它是「没有声音」的空哨兵。',
      }));
    }
    trackGroup.appendChild(trackBody);
    form.appendChild(trackGroup);
    return form;
  };

  // --- 内容进页签 ---------------------------------------------------------
  // 描述符（歌曲头 + 轨道）/ 谁指向它（反查）/ 播放入口（推定的 thunk）。
  const soundIds = descriptor ? descriptor.sound_ids.map((id) => Number(id)) : [];
  const entrySlots = playEntrySlots(pack, soundIds);

  const tabs = new TabPanel([
    {
      id: 'descriptor',
      label: '描述符',
      hint: '这个 m4a 描述符的字段：歌曲头与轨道指针',
      badge: () => fieldsChanged(structure, record, structure.fields || []) || null,
      render: () => descriptorSection(),
    },
    {
      id: 'refs',
      label: '谁指向它',
      hint: '反向引用：哪些音效用的是这首曲子',
      badge: () => songRefsChanged(pack, users),
      render: () => refsSection(),
    },
    {
      id: 'playback',
      label: '播放入口',
      hint: '函数指针表里与这些音效对应的播放 thunk（静态推定）',
      badge: () => playEntriesChanged(pack, entrySlots),
      render: () => renderPlayEntryBlock(ctx, entrySlots,
        `函数指针表只覆盖音效 ${playEntryRange(pack)}，`
        + (soundIds.length ? '这些音效没有对应的入口槽。' : '这个描述符还没有音效在用。')),
    },
  ], { key: 'editor.audio', pack });
  container.appendChild(tabs.element);

  container.appendChild(el('div', { class: 'detail-actions' }, [
    el('button', {
      class: 'btn btn-ghost',
      text: '在原始字节里看这一段',
      onclick: () => openRawAt(ctx, structure.rom_offset),
    }),
    el('button', {
      class: 'btn btn-ghost',
      text: '复制十六进制',
      onclick: () => {
        const bytes = pack.recordBytes(structure, record);
        copyToClipboard(bytesToHex(bytes));
        toast('已复制该描述符的十六进制字节');
      },
    }),
  ]));
}

/** 角标：引用这个描述符的音效里改过几条（按字节判定）。 */
function songRefsChanged(pack, users) {
  const sets = new Map();
  let n = 0;
  for (const ref of users || []) {
    let set = sets.get(ref.structure.id);
    if (!set) {
      set = changedOffsets(pack, ref.structure);
      sets.set(ref.structure.id, set);
    }
    if (set.has(ref.record.rom_offset)) n += 1;
  }
  return n || null;
}

/** 角标：这些播放入口槽本身改过几条（按字节判定）。 */
function playEntriesChanged(pack, slots) {
  if (!slots || !slots.length) return null;
  const table = pack.structure('function_pointer_table');
  if (!table) return null;
  const changed = changedOffsets(pack, table);
  let n = 0;
  for (const slot of slots) {
    const record = playEntryRecord(pack, slot.id);
    if (record && changed.has(record.rom_offset)) n += 1;
  }
  return n || null;
}

// --------------------------------------------------------------------------
// 函数指针表
// --------------------------------------------------------------------------
function renderFunctionPointers(container, ctx, structure, params) {
  clear(container);
  const pack = ctx.pack;
  const stats = (pack.derived && pack.derived.sound_stats) || {};
  const slots = stats.function_pointer_slots || {};

  container.appendChild(el('div', { class: 'panel-head' }, [
    el('div', {}, [
      el('h2', { text: structure.label || structure.id }),
      el('div', { class: 'panel-sub' }, [
        el('span', { text: `ROM ${formatOffset(structure.rom_offset)}` }),
        el('span', { text: `${(structure.records || []).length} 槽` }),
        structure.verification ? el('span', { text: structure.verification }) : null,
      ]),
    ]),
  ]));

  container.appendChild(el('div', { class: 'rule-note' }, [
    el('span', { class: 'rule-title', text: '证据等级' }),
    el('span', {
      text: stats.function_pointer_note
        || '1..11 槽是播放 thunk（推定）。',
    }),
  ]));

  const table = el('table', { class: 'grid' });
  table.appendChild(el('thead', {}, [el('tr', {}, [
    el('th', { class: 'col-id', text: '槽' }),
    el('th', { text: '代码指针' }),
    el('th', { text: '是什么' }),
    el('th', { class: 'col-actions', text: '' }),
  ])]));
  const body = el('tbody');
  for (const record of structure.records || []) {
    const slot = slots[String(record.id)] || {};
    const value = record.values.ptr >>> 0;
    body.appendChild(el('tr', {}, [
      el('td', { class: 'col-id', text: `槽 ${record.id}` }),
      el('td', { text: '0x' + value.toString(16).toUpperCase() }),
      el('td', { class: 'text-cell' }, [
        el('span', {
          class: 'pill ' + (slot.kind === 'play_entry' ? 'pill-song' : 'pill-raw'),
          text: slot.label || '（未判定）',
        }),
        slot.evidence === 'static'
          ? el('span', { class: 'audio-estimate', text: '静态推定' })
          : null,
      ]),
      el('td', { class: 'col-actions' }, [
        el('button', {
          class: 'btn btn-tiny',
          text: '原始字节',
          onclick: () => openRawAt(ctx, record.rom_offset),
        }),
      ]),
    ]));
  }
  table.appendChild(body);
  container.appendChild(el('div', { class: 'table-wrap' }, [table]));
}

// --------------------------------------------------------------------------
// 路由
// --------------------------------------------------------------------------
export function renderAudioStructure(container, ctx, id, params) {
  const pack = ctx.pack;
  const structure = pack.structure(id);
  if (!structure) {
    clear(container);
    container.appendChild(el('div', { class: 'empty', text: '找不到结构 ' + id }));
    return;
  }
  if (id === 'sound_id_table') {
    const table = new AudioSoundTable(pack, ctx, structure);
    table.render(container);
    const recordId = params && params.recordId;
    if (recordId !== undefined && recordId !== null) {
      const record = (structure.records || []).find((r) => r.id === recordId);
      if (record) table.openDetail(record);
      else toast(`这张表里没有音效 #${recordId}`, 'error');
    }
    return;
  }
  if (id === 'function_pointer_table') {
    renderFunctionPointers(container, ctx, structure, params);
    return;
  }
  renderSongDescriptor(container, ctx, structure, params);
}
