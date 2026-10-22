// 剧情脚本查看器：把剧情 VM 的字节码反汇编成可读的指令表。
//
// 内容包里的 `pack.scripts` 只有剧本的**指针**与路线边；剧本正文（指令、文本、
// 分支）此前在界面上完全看不到 —— 尽管 `js/storyvm.js` 已经能把它们反汇编出来。
//
// **对白可以就地改，而且**长度不限**：文本是内联在脚本字节流里的，而脚本里的
// 分支目标是绝对 ROM 地址 —— 改长改短都会让后面的指令移位、分支全部失效。
// 所以：
//   * **等长**改写 → 原地改（一条补丁）；
//   * **变长 / 变短**改写 → 构建时把**整个剧本**搬到空闲区，把它内部的绝对
//     地址全部重基，再改根表里指向它的指针（`js/rom.js::applyScriptRelocations`）。
// 每个输入框旁边写着「现在多少字节 / 原来多少字节」，以及这一改会不会搬动剧本。
// 仓库证明可原地改写的定宽操作数同样给成输入框。

import { el, clear, toast } from '../ui.js';
import { summaryTable } from './common.js';
import {
  OPCODE_NAMES, KNOWN_OPERANDS, OPERAND_LABELS, ROM_BASE,
  branchTargets, editableOperands, instructionLength, scanScript,
} from '../storyvm.js';
import { textSegments, segmentBudget, commitSegment } from '../scripttext.js';

const ROOTS = [
  { id: 'before', label: '战前剧情', structure: 'story_before_root' },
  { id: 'after', label: '战后剧情', structure: 'story_after_root' },
  { id: 'logic', label: '战场事件逻辑', structure: 'story_logic_root' },
  { id: 'events', label: '战场事件表', structure: 'story_events_root' },
];

export function renderScriptView(container, ctx) {
  clear(container);
  const pack = ctx.pack;
  const rom = ctx.rom || ctx.baseRom;
  const params = (ctx.state.view.panel && ctx.state.view.panel.params) || {};
  const rootId = params.root || 'before';
  const scene = Number(params.scene) || 1;
  const root = ROOTS.find((r) => r.id === rootId) || ROOTS[0];

  if (!rom) {
    container.appendChild(el('div', { class: 'empty' }, [
      el('div', { text: '未载入原版 ROM —— 反汇编剧情脚本需要 ROM 字节。' }),
    ]));
    return;
  }

  const structure = pack.structure(root.structure);
  const record = structure ? structure.records[scene] : null;
  const pointer = record ? record.values.ptr : 0;
  const offset = pointer ? pointer - ROM_BASE : 0;

  // --- 选剧本 / 选场景 --------------------------------------------------
  const rootSelect = el('select', {
    class: 'search',
    onchange: (e) => ctx.openPanel('script', 'script', {
      root: e.target.value, scene,
    }),
  });
  for (const item of ROOTS) {
    rootSelect.appendChild(el('option', {
      value: item.id, text: item.label, selected: item.id === root.id,
    }));
  }
  const sceneSelect = el('select', {
    class: 'search',
    onchange: (e) => ctx.openPanel('script', 'script', {
      root: root.id, scene: Number(e.target.value),
    }),
  });
  const count = structure ? structure.records.length : 0;
  for (let s = 0; s < count; s++) {
    sceneSelect.appendChild(el('option', {
      value: String(s), text: `第 ${s} 场`, selected: s === scene,
    }));
  }

  container.appendChild(el('div', { class: 'panel-head' }, [
    el('div', {}, [
      el('h2', { text: `${root.label} · 第 ${scene} 场` }),
      el('div', { class: 'panel-sub' }, [
        el('span', { text: `ROM ${pointer ? '0x' + pointer.toString(16).toUpperCase() : '—'}` }),
        el('span', { text: `文件偏移 0x${offset.toString(16).toUpperCase()}` }),
      ]),
    ]),
    el('div', { class: 'panel-tools' }, [rootSelect, sceneSelect]),
  ]));

  container.appendChild(el('div', { class: 'rule-note' }, [
    el('span', { class: 'rule-title', text: '说明' }),
    el('span', {
      text: '这是剧情 VM 的字节码。对白正文**可以就地改，长度不限** —— ' +
        '文本是内联在这段字节流里的，而脚本里的分支目标是绝对地址，' +
        '所以等长改写直接原地落地；' +
        '**变长 / 变短**的话，构建时会把整个剧本搬到 ROM 的空闲区，' +
        '把它内部的绝对地址全部重基，再改根表里指向它的指针。' +
        '每个输入框旁边写着「现在多少字节 / 原来多少字节」，' +
        '以及这一改会不会搬动剧本。' +
        '控制码 0x01 / 0x02 带着换行 / 分页的排版含义，写回时按原位保留。' +
        '定宽操作数（0x16 / 0x1A 下一场景、0x1E 地图、0x1F 子配置、0x23 队员，' +
        '以及战场触发的 0x34–0x39 条件字段）' +
        '同样可以改。',
    }),
  ]));

  if (!pointer) {
    container.appendChild(el('div', { class: 'empty', text: '这一场没有剧本指针。' }));
    return;
  }

  const instructions = scanScript(rom, offset);
  const rows = { head: ['ROM 地址', '指令', '操作数', '文本', '分支'], body: [] };
  for (const instruction of instructions) {
    const op = instruction.op;
    const name = OPCODE_NAMES[op] || `未知指令 0x${op.toString(16).toUpperCase()}`;
    const operands = editableOperands(rom, instruction);
    const targets = branchTargets(rom, instruction.offset, instruction.length);
    rows.body.push([
      '0x' + (instruction.offset + ROM_BASE).toString(16).toUpperCase(),
      `0x${op.toString(16).toUpperCase()} ${name}`,
      operands.length
        ? el('div', {}, operands.map((operand) => el('div', { class: 'operand-row' }, [
          el('span', { class: 'operand-label', text: operand.label }),
          operandInput(ctx, operand),
        ])))
        : el('span', { class: 'stat-hint', text: '—' }),
      textCell(ctx, rom, instruction),
      targets.length
        ? targets.map((t) => '0x' + (t + ROM_BASE).toString(16).toUpperCase()).join('、')
        : '—',
    ]);
  }
  container.appendChild(el('div', { class: 'section' }, [
    el('h3', { text: '指令表' }),
    summaryTable(rows),
    el('div', { class: 'table-foot', text: `显示 ${rows.body.length} 条指令` }),
  ]));
}

/**
 * The text runs of a text-carrying instruction, as editable cells.
 *
 * 文本是内联在脚本字节流里的，所以「可编辑」= **长度不限**：
 * 等长的直接原地改写；变长 / 变短的靠「构建时搬迁整个剧本」落地。
 * 输入框旁边写着现在多少字节、原来多少字节，以及会不会搬动剧本。
 *
 * 导出给战斗域的「剧情触发」列表复用（别复制粘贴一份）。
 */
export function textCell(ctx, rom, instruction) {
  const segments = textSegments(rom, ctx.pack, instruction);
  if (!segments.length) {
    return el('span', { class: 'stat-hint', text: '—' });
  }
  return el('div', { class: 'script-text-cell' },
    segments.map((segment) => textSegmentCell(ctx, segment)));
}

/**
 * One text run: an input, a byte budget and a link to the raw bytes.
 *
 * @param {object} ctx
 * @param {object} segment   `textSegments` 给出的一段
 * @param {(result:object)=>void} [onEdited]  改完之后回调（对白页要刷新舞台）
 */
export function textSegmentCell(ctx, segment, onEdited) {
  const pack = ctx.pack;
  const input = el('input', {
    class: 'text-input-inline script-text-input',
    type: 'text',
    spellcheck: 'false',
    value: segment.text,
    title: '失焦即保存。长度不限：等长直接原地改写；' +
      '变长 / 变短的话，构建时会把整个剧本搬到空闲区并重基它内部的地址。',
    oninput: () => refresh(),
    onchange: () => commit(),
  });
  const counter = el('div', { class: 'text-counter script-text-counter' });
  const meta = el('div', { class: 'script-text-meta' });

  if (segment.speaker !== null && segment.speaker !== undefined) {
    const name = speakerName(pack, segment.speaker);
    meta.appendChild(el('span', {
      class: 'script-text-speaker',
      title: '0x20 的第 2 字节是这条指令自带的说话人/头像 id' +
        '（说话人名表 0x5A57C4，步长 12 字节）。本 ROM 里它恒为 1；' +
        '游戏显示的名牌取自对话框状态（由 0x08 指令设置），' +
        '所以这类对白的说话人通常写在正文里。',
      text: `说话人 #${segment.speaker}${name ? `（${name}）` : ''}`,
    }));
  }
  for (const token of segment.controls) {
    const hex = token.b.map((b) => b.toString(16).toUpperCase().padStart(2, '0')).join(' ');
    meta.appendChild(el('span', {
      class: 'seg-ctrl',
      title: `控制码 0x${hex}：换行 / 分页的排版含义。` +
        '文本框里看不到它，但写回时按原位保留。',
      text: `⟦控制码 ${hex}⟧`,
    }));
  }
  meta.appendChild(el('button', {
    class: 'btn btn-tiny script-text-link',
    text: '跳到原始字节',
    title: `打开原始字节 0x${segment.offset.toString(16).toUpperCase()}`
      + '（这是原版里的位置；构建时若剧本被搬到空闲区，ROM 里的新位置会不一样）',
    onclick: () => ctx.onJump({
      module: 'raw',
      kind: 'raw-offset',
      id: 'raw',
      params: { offset: segment.offset },
      label: `原始字节 0x${segment.offset.toString(16).toUpperCase()}`,
    }),
  }));

  const cell = el('div', { class: 'script-text-run' }, [input, counter, meta]);

  if (segment.problem) {
    input.disabled = true;
  }

  /** The byte budget next to the input: how many bytes are left. */
  function refresh() {
    clear(counter);
    if (segment.problem) {
      counter.appendChild(el('span', { class: 'bad', text: segment.problem }));
      return;
    }
    const budget = segmentBudget(segment, input.value, pack.font);
    counter.appendChild(el('span', {
      text: `${budget.used} / ${budget.capacity} 字节`,
    }));
    if (budget.missing.length) {
      counter.appendChild(el('span', {
        class: 'bad',
        text: `· 字库缺字: ${budget.missing.join(' ')}`,
      }));
    } else if (budget.delta > 0) {
      counter.appendChild(el('span', {
        class: 'warn',
        title: '正文变长了 —— 脚本里的分支目标是绝对地址，构建时会把整个剧本' +
          '搬到 ROM 的空闲区，并把剧本内部的绝对地址全部重基。旧位置原样留着。',
        text: `· 变长 ${budget.delta} 字节：构建时整个剧本会搬到空闲区`,
      }));
    } else if (budget.delta < 0) {
      counter.appendChild(el('span', {
        class: 'warn',
        title: '正文变短了 —— 脚本里的分支目标是绝对地址，构建时会把整个剧本' +
          '搬到 ROM 的空闲区，并把剧本内部的绝对地址全部重基。旧位置原样留着。',
        text: `· 变短 ${-budget.delta} 字节：构建时整个剧本会搬到空闲区`,
      }));
    } else {
      counter.appendChild(el('span', { class: 'ok', text: '· 等长，失焦即保存' }));
    }
  }

  /** Save on blur; refuse (and roll back) when the text cannot be written. */
  function commit() {
    const result = commitSegment(pack, segment, input.value);
    if (!result.ok) {
      toast(result.message, 'error');
      input.value = segment.text;   // 回滚：不能默默截断，也不能静默不保存
      refresh();
      return;
    }
    if (result.unchanged) {
      refresh();
      return;
    }
    ctx.onChange();
    refresh();
    if (result.relocated) {
      toast(`已改写对白 0x${segment.offset.toString(16).toUpperCase()}`
        + `（${result.bytes.length} 字节）—— 构建时整个剧本会搬到空闲区`);
    } else {
      toast(`已改写对白 0x${segment.offset.toString(16).toUpperCase()}`);
    }
    if (onEdited) onEdited(result);
  }

  refresh();
  return cell;
}

/** The name of a speaker id (the inline 12-byte table at 0x5A57C4). */
function speakerName(pack, id) {
  const table = pack.textTable('speaker_names');
  if (!table) return null;
  const record = (table.records || []).find((r) => r.id === id);
  return record ? record.text : null;
}

/** An editable operand: a proved fixed-width field inside the instruction. */
function operandInput(ctx, operand) {
  const input = el('input', {
    class: 'num-input',
    type: 'text',
    style: { width: '72px' },
    value: String(operand.value),
    onchange: (e) => {
      const next = Number(e.target.value);
      if (!Number.isFinite(next) || next < 0 || next > 0xffff) {
        toast('请输入 0–65535 的整数', 'error');
        e.target.value = String(operand.value);
        return;
      }
      ctx.pack.setScriptOperand({
        ...operand,
        before_hex: bytesOf(ctx, operand),
      }, next);
      ctx.onChange();
      toast(`已改写 0x${operand.rom_offset.toString(16).toUpperCase()}（${operand.label}）`);
    },
  });
  return input;
}

/** The instruction's original bytes for the operand (the write-back guard). */
function bytesOf(ctx, operand) {
  const rom = ctx.rom || ctx.baseRom;
  if (!rom) return '';
  const out = new Uint8Array(operand.size);
  out.set(rom.subarray(operand.rom_offset, operand.rom_offset + operand.size));
  return [...out].map((b) => b.toString(16).padStart(2, '0')).join('');
}

export { ROOTS };
