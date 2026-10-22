// 剧情脚本查看器：把剧情 VM 的字节码反汇编成可读的指令表。
//
// 内容包里的 `pack.scripts` 只有剧本的**指针**与路线边；剧本正文（指令、文本、
// 分支）此前在界面上完全看不到 —— 尽管 `js/storyvm.js` 已经能把它们反汇编出来。
//
// 指令与文本**不可改**（改文本会移动后续指令、让全部分支失效）；
// 仓库证明可原地改写的定宽操作数在这里给成输入框。

import { el, clear } from '../ui.js';
import { summaryTable } from './common.js';
import {
  OPCODE_NAMES, KNOWN_OPERANDS, OPERAND_LABELS, ROM_BASE,
  branchTargets, editableOperands, instructionLength, scanScript, textEnd,
} from '../storyvm.js';

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
      text: '这是剧情 VM 的字节码。指令与文本**不可改**：改文本会移动后续指令、' +
        '让脚本里的分支目标全部失效。仓库证明可原地改写的只有定宽操作数' +
        '（0x16 / 0x1A 下一场景、0x1E 地图、0x1F 子配置、0x23 队员），' +
        '它们在这里给成输入框。',
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
      textCell(pack, rom, instruction),
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

/** The text run of a text-carrying instruction, decoded with the ROM's font. */
function textCell(pack, rom, instruction) {
  const op = instruction.op;
  if (op !== 0x01 && op !== 0x05 && op !== 0x13 && op !== 0x20) {
    return el('span', { class: 'stat-hint', text: '—' });
  }
  const start = instruction.offset + (op === 0x01 ? 1 : op === 0x13 ? 4 : 2);
  const end = textEnd(rom, start);
  const raw = rom.subarray(start, Math.max(start, end - 1));
  let text;
  try {
    text = pack.font.decode(raw);
  } catch (err) {
    text = `（解码失败：${err.message}）`;
  }
  return el('span', {
    class: 'script-text',
    text: (text || '').replace(/\n/g, '↵') || '（空）',
  });
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
