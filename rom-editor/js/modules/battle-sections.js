// 战斗域「一关之内的全部配置」——按类拆成几块，交给战场地图视图的右侧页签。
//
// 这些内容原来在「关卡视图」里（battle.js 的一长条纵向页面）。
// 地图升为主界面之后，它们改挂在地图右侧的页签上：
// 战场布置 / 战场物件 / 角色出生点 在 battle-map.js 里（它们与地图标记联动），
// 胜负条件 与 剧情触发 在这里（与地图没有空间关系，但说的仍是**这一关**）。

import { el, toast, clear } from '../ui.js';
import { fieldControl } from '../fields.js';
import { summaryTable, operandInput, BATTLE_LAYOUT } from './common.js';
import { textCell } from './scriptview.js';
import { OPCODE_NAMES } from '../storyvm.js';
import {
  ONE_BASED_NOTE, buildTriggerModel, targetText,
} from '../battletriggers.js';

const { RULES_BASE, RULE_STAGE_STRIDE, RULE_SUB_STRIDE } = BATTLE_LAYOUT;

/**
 * 条件类型的原版语义。
 *
 * 语义来源见 notes/battle-tables.md §1.1（原版说明文字）与 §1.1.1
 * （类型 2 / 3 的原生断点定案）。
 */
export const CONDITION_TYPES = {
  1: '全灭敌方（a=1）/ 我方全灭（a=0）',
  2: '回合用尽 —— 原生根本不读 a/b',
  3: '指定角色已离场',
  6: '获得指定道具',
  7: '剩余体力比较',
  8: '击杀数比较',
  9: '收集物数量比较',
};

/** 每个类型里 a / b 两个字节的原生含义。 */
export const CONDITION_PARAMS = {
  1: { a: '阵营（1=胜 / 0=负）', b: '未用' },
  2: { a: '冗余：原生不读', b: '冗余：原生不读' },
  3: { a: '阵营（0=我方 / 1=敌方）', b: '角色 id' },
  6: { a: '道具序号', b: '未用' },
  7: { a: '阵营（0=我方 / 1=对方）', b: '未用' },
  8: { a: '阵营（0=我方 / 1=对方）', b: '未用' },
  9: { a: '阵营（0=我方 / 1=对方）', b: '未用' },
};

/**
 * 胜负条件（战斗目标）。
 *
 * 每条记录 0x44 字节：回合上限 + 4 个胜利条件 + 4 个失败条件，
 * 每个条件是「类型 + 参数A + 参数B」三个字节，外加一句给玩家看的说明文字。
 *
 * @param {object} ctx
 * @param {number} stage
 * @param {number} variant
 * @returns {HTMLElement}
 */
export function renderRulesTab(ctx, stage, variant) {
  const pack = ctx.pack;
  const rules = pack.structure('battle_rules');
  const record = rules
    ? rules.records.find((r) => r.rom_offset === RULES_BASE + stage * RULE_STAGE_STRIDE + variant * RULE_SUB_STRIDE)
    : null;
  if (!record) {
    return el('div', { class: 'map-section' }, [
      el('h3', { text: '胜负条件' }),
      el('div', { class: 'empty', text: '战斗目标表里没有这一关的记录。' }),
    ]);
  }
  const v = record.values;
  const objectiveTable = pack.textTable('battle_objectives');
  const objectiveTexts = objectiveBindings(objectiveTable);
  const rows = { head: ['条件', '类型', '参数A', '参数B', '说明文字（可直接改）'], body: [] };
  for (let g = 0; g < 2; g += 1) {
    for (let k = 0; k < 4; k += 1) {
      const label = g === 0 ? `胜利 ${k + 1}` : `失败 ${k + 1}`;
      const type = v[`g${g}_${k}_type`];
      if (type === 0 && v[`g${g}_${k}_a`] === 0 && v[`g${g}_${k}_b`] === 0) continue;
      const params = CONDITION_PARAMS[type] || { a: '未用', b: '未用' };
      const typeField = (rules.fields || []).find((f) => f.key === `g${g}_${k}_type`);
      const aField = (rules.fields || []).find((f) => f.key === `g${g}_${k}_a`);
      const bField = (rules.fields || []).find((f) => f.key === `g${g}_${k}_b`);
      rows.body.push([
        label,
        // 类型用**内容包自带的取值域**渲染成下拉（语义只有一处真相），
        // 而不是这里手写的一张表。
        typeField
          ? fieldControl({ pack, onChange: ctx.onChange }, rules, record, typeField).node
          : `${type} · ${CONDITION_TYPES[type] || '未知'}`,
        aField
          ? el('div', {}, [
            numCell(ctx, rules, record, aField.key, v[aField.key]),
            el('div', { class: 'stat-hint', text: params.a }),
          ])
          : paramCell(v[`g${g}_${k}_a`], params.a),
        bField
          ? el('div', {}, [
            numCell(ctx, rules, record, bField.key, v[bField.key]),
            el('div', { class: 'stat-hint', text: params.b }),
          ])
          : paramCell(v[`g${g}_${k}_b`], params.b),
        descriptionCell(ctx, objectiveTable, objectiveTexts.get(`${record.id}:${g}:${k}`)),
      ]);
    }
  }
  return el('div', { class: 'map-section' }, [
    el('h3', { text: '胜负条件' }),
    el('p', { class: 'section-note' }, [
      `回合上限：${v.turn_limit === 0 ? '无限制' : v.turn_limit}。`,
      '每条记录 4 个胜利条件 + 4 个失败条件；类型与参数都能直接改。',
      '类型 2 的数据写着「指定角色仍在场」，但原生代码根本不读这两个字节，',
      '它比较的是回合计数与回合上限 —— 这一版 ROM 的 type-2 实际表达的是「回合用尽」',
      '（notes/battle-tables.md §1.1.1；2026-10-21 用真实战斗读数证实 0x0202680C 就是回合计数）。',
      '类型 3 是「指定角色已离场」，a=阵营、b=角色 id。',
    ]),
    summaryTable(rows),
    el('p', { class: 'section-note' }, [
      '说明文字被代码用绝对地址引用，只能等长改写：超过原槽位长度时编辑器会拒绝并提示。',
    ]),
    rulesCrossReference(ctx, stage, v),
  ]);
}

/**
 * 「胜负条件」与「剧情触发」共用同一个战斗计数 —— 两张卡片之间的一行交叉引用。
 *
 * 措辞按审核 P2-9：那个字节（战斗控制块 0x0202680C）仓库里有两个互相矛盾的名字
 * （多数笔记叫「回合计数」，一处叫「战斗阶段 / 子阶段」），
 * 所以这里写它的**地址**，不把「回合数」当成没有争议的词。
 */
function rulesCrossReference(ctx, stage, values) {
  const rom = ctx.rom || ctx.baseRom;
  if (!rom) return null;
  const model = buildTriggerModel(rom, ctx.pack, stage);
  if (!model.counts.blocks) return null;
  const roundConditions = model.blocks.reduce(
    (n, block) => n + block.conditions.filter((c) => c.op === 52).length, 0);
  return el('p', { class: 'section-note' }, [
    `这一关的剧情触发也读同一个战斗计数：战斗控制块 0x0202680C` +
    `（仓库多数笔记叫「回合计数」，另一处笔记叫「战斗阶段 / 子阶段」，两种说法没对上过）。` +
    `本关有 ${roundConditions} 处触发条件按它判定` +
    (values && values.turn_limit ? `，而本关的回合上限是 ${values.turn_limit}。` : '。') +
    '条件写在哪、怎么改，见下面「剧情触发」那张卡片。',
  ]);
}

/**
 * 这一关在战斗里会触发的剧情。
 *
 * 四张根表定位到本关的四个剧本（战前 / 战后 / 战场事件逻辑 / 战场事件表），
 * 剧本里的 0x22 指令「把角色加入战斗配置」会回到编成矩阵去取角色与等级 ——
 * 所以**出生点那一页改的就是「战斗中谁出场」**。
 *
 * 「战斗中触发」那一段是**触发块列表**：一行 = 一组守门条件 + 它触发的那一段对白，
 * 条件与对白都能就地改（见 `js/battletriggers.js` 的模型说明）。
 *
 * @param {object} ctx
 * @param {number} stage
 * @returns {HTMLElement}
 */
export function renderScriptsTab(ctx, stage) {
  const pack = ctx.pack;
  const rom = ctx.rom || ctx.baseRom;

  // --- 四张根表 ---------------------------------------------------------
  const scriptRows = { head: ['剧本', '根表', '本关脚本首地址'], body: [] };
  for (const [label, id] of [
    ['战前剧情', 'story_before_root'],
    ['战后剧情', 'story_after_root'],
    ['战场事件逻辑', 'story_logic_root'],
    ['战场事件表', 'story_events_root'],
  ]) {
    const structure = pack.structure(id);
    if (!structure) continue;
    const record = structure.records[stage];
    if (!record) continue;
    scriptRows.body.push([label, structure.label, ptrText(record.values.ptr)]);
  }

  // 本关战斗剧本里可改的定宽操作数
  //
  // 这里曾经**永远是空的**：筛选只留 logic / events 两类剧本，而带操作数的
  // 恰恰是 before / after 两类（logic / events 的 operands 是空数组）。
  // 于是文案写着「0x1E / 0x1F / 0x23 / 0x22 可改」，实际一处也找不到。
  const operandRows = { head: ['剧本', '指令', '含义', '当前值'], body: [] };
  for (const script of pack.scripts || []) {
    if (script.scene !== stage) continue;
    for (const operand of script.operands || []) {
      operandRows.body.push([
        script.root === 'before' ? '战前剧情'
          : script.root === 'after' ? '战后剧情'
          : script.root === 'logic' ? '战场事件逻辑' : '战场事件表',
        '0x' + operand.opcode.toString(16).toUpperCase(),
        operand.label,
        operandInput(ctx, operand),
      ]);
    }
  }

  const node = el('div', { class: 'map-section' }, [
    el('h3', { text: '剧情触发' }),
    el('p', { class: 'section-note' }, [
      '战斗中的剧情由「战场事件逻辑」与「战场事件表」两根根指针定位到本关的剧本。' +
      '剧本里的 0x22 指令「把角色加入战斗配置」会按关卡 id 与变体 id 定位到编成矩阵，' +
      '扫描 12 个槽位找到角色 id 匹配的条目，取出等级并把模板拷进战斗单位。' +
      '因此在「角色出生点」那一页改角色 id / 等级 / 出生点，就等于改了战斗中谁出场、在哪出现。',
    ]),
    summaryTable(scriptRows),
    el('p', { class: 'section-note' }, [
      '剧情按关卡（场景）编号，本关的三个战斗变体共用同一份剧情 —— ' +
      '在变体 2 里改了对白，变体 1 的那段对白也跟着变，这是原版的结构，不是编辑器出错。',
    ]),
  ]);

  node.appendChild(triggerSection(ctx, stage, rom));

  // --- 战前 / 战后过场 ---------------------------------------------------
  node.appendChild(el('h3', { text: '战前 / 战后过场' }));
  node.appendChild(el('p', { class: 'section-note' }, [
    '战前与战后是**过场对白**，不是触发器：它们没有条件、没有事件 id，' +
    '结构上跟上面的触发块不是一回事。正文太长（最长 2123 条指令），' +
    '这一页只给指针与可改的操作数，要改正文请到剧情页。',
  ]));
  node.appendChild(el('div', { class: 'story-links' }, [
    storyLink(ctx, 'before', stage, '在剧情页打开战前剧情'),
    storyLink(ctx, 'after', stage, '在剧情页打开战后剧情'),
  ]));
  if (operandRows.body.length) {
    node.appendChild(el('h3', { text: '本关剧情脚本里可改的操作数' }));
    node.appendChild(el('p', { class: 'section-note' }, [
      '0x1E 决定本关载入哪张地图，0x1F 决定用哪个子配置，0x23 决定队员，' +
      '0x22 是「把角色加入战斗配置」。这些操作数都是定宽的，改它们是原地写，' +
      '不会让脚本里的分支目标失效。',
      '（带操作数的是战前/战后剧本；战场事件逻辑与事件表的定宽字段，' +
      '在上面的触发块列表里就地改。）',
    ]));
    node.appendChild(summaryTable(operandRows));
  }
  return node;
}

/**
 * 「战斗中触发」那一段：触发块列表。
 *
 * 没有载入 ROM 时降级成一句说明 —— 但**根指针表与操作数表照常显示**
 * （它们来自内容包，不需要 ROM）。
 */
function triggerSection(ctx, stage, rom) {
  const model = buildTriggerModel(rom, ctx.pack, stage);
  const wrap = el('div', { class: 'trigger-section' });
  wrap.appendChild(el('h3', { text: '战斗中触发' }));

  const list = el('div', { class: 'trigger-list', dataset: { triggers: '1' } });

  if (model.empty) {
    wrap.appendChild(el('p', { class: 'section-note' }, [
      model.empty,
      '触发块列表要反汇编剧情脚本才画得出来；下面的剧本指针与可改操作数来自内容包，照常显示。',
    ]));
    list.appendChild(el('div', { class: 'empty', text: '触发块列表需要原版 ROM。' }));
    wrap.appendChild(list);
    return wrap;
  }

  wrap.appendChild(el('p', { class: 'section-note' }, [
    '每一行是一处触发：左边是这一段的守门条件，右边是它触发的那一段对白。' +
    '守门条件的读法：判定**成立**就跳到「命中时跳到」那一列（多数情况下是跳过本组、' +
    '不触发这一段），**全部落空**才会压入事件 id、触发这一段对白。' +
    '0x35 是反过来的：它在复合条件**不**成立时才跳，所以复合条件**成立**才会触发本组。',
    '条件来自「战场事件逻辑」，对白来自「战场事件表」。',
  ]));
  wrap.appendChild(el('p', { class: 'section-note' }, [
    ONE_BASED_NOTE,
    `本关共 ${model.counts.blocks} 处触发 · 事件链 ${model.counts.chainLength} 段 · ` +
    `其中 ${model.counts.unconditional} 处无条件（一直成立）。`,
  ]));
  wrap.appendChild(el('p', { class: 'stat-hint' }, [
    '条件里没定名的东西照实写：0x34 里那个字节（战斗控制块 0x0202680E）仓库还没给它起名字，' +
    '而且仓库对它有两种互相矛盾的说法（0/1 与 0x0E/0x0F），需要一次运行期读数才能定；' +
    '0x35 的三个参数、0x36 的参数 b、0x37/0x38 的模式取值，仓库都还没解。',
    '「回合计数」是战斗控制块 0x0202680C 的首字节：仓库多数笔记这么叫，' +
    '也有一处笔记叫它「战斗阶段 / 子阶段」，两种说法没对上过。',
  ]));
  if (model.overlapping) {
    wrap.appendChild(el('p', { class: 'section-note' }, [
      '这一关的「战场事件逻辑」与「战场事件表」是**同一段字节**（事件表从逻辑的中间接上），' +
      '所以这里只列一张表，段数与触发数不重复计。',
    ]));
  }
  for (const block of model.blocks) {
    list.appendChild(triggerBlockNode(ctx, stage, model, block));
  }
  wrap.appendChild(list);
  return wrap;
}

/**
 * 展开状态：视图的临时状态，**不进内容包**（换关卡就换一份）。
 */
const expandedTriggers = new Map();

function expansionOf(stage) {
  let set = expandedTriggers.get(stage);
  if (!set) {
    set = new Set();
    expandedTriggers.set(stage, set);
  }
  return set;
}

/** 一个触发块：行头 + 展开后的条件表与对白表。 */
function triggerBlockNode(ctx, stage, model, block) {
  const node = el('div', { class: 'trigger-block', dataset: { trigger: String(block.index + 1) } });
  const expanded = expansionOf(stage);
  const paint = () => {
    clear(node);
    const isOpen = expanded.has(block.index);
    node.appendChild(el('button', {
      class: 'trigger-head' + (isOpen ? ' open' : ''),
      type: 'button',
      title: isOpen ? '收起这一处的条件与对白' : '展开这一处的条件与对白',
      onclick: () => {
        if (expanded.has(block.index)) expanded.delete(block.index);
        else expanded.add(block.index);
        paint();
      },
    }, [
      el('span', { class: 'trigger-no', text: `触发 #${block.index + 1}` }),
      el('span', {
        class: 'trigger-seg',
        text: block.segment
          ? `第 ${block.segment.index} 段对白 · ${block.lineCount} 句`
          : `没有对应的剧情段（压入的值是 ${block.value}）`,
      }),
      el('span', { class: 'trigger-cond', text: block.summary }),
      el('span', { class: 'trigger-toggle', text: isOpen ? '收起' : '展开' }),
    ]));
    if (isOpen) node.appendChild(triggerBody(ctx, stage, model, block, paint));
  };
  paint();
  return node;
}

/** 展开后的内容：事件 id + 条件表 + 对白表。 */
function triggerBody(ctx, stage, model, block, repaint) {
  const rom = ctx.rom || ctx.baseRom;
  const wrap = el('div', { class: 'trigger-body' });

  // --- 事件 id（选链上第几段）------------------------------------------
  const pushRows = { head: ['事件 id（1 基：选中链上第几段）', '当前值'], body: [] };
  for (const operand of block.pushOperands || []) {
    pushRows.body.push([operand.label, operandInput(ctx, operand)]);
  }
  if (pushRows.body.length) {
    wrap.appendChild(summaryTable(pushRows));
  }
  if (!block.linked) {
    wrap.appendChild(el('p', { class: 'stat-hint' }, [
      `这一处压入的值是 ${block.value}，链上只有 ${model.counts.chainLength} 段 —— ` +
      '按 1 基规则它选不中任何一段（静态字节推定，未做运行期确认）。',
    ]));
  }

  // --- 条件表 -----------------------------------------------------------
  // 最后一列是**人话说明**，得能换行 ——
  // `table.grid td` 全局是 `white-space: nowrap`，说明文字会被顶出容器。
  // `.cond-table` 是给这张表单独用的类（common.js::summaryTable 的可选 class）。
  const rows = {
    head: ['条件', '参数（可改）', '命中时跳到', '这条条件在测什么'],
    body: [],
    class: 'cond-table',
  };
  for (const condition of block.conditions) {
    rows.body.push([
      `0x${condition.op.toString(16).toUpperCase()} ${OPCODE_NAMES[condition.op] || ''}`,
      operandCells(ctx, condition.operands, repaint),
      targetText(condition.target, block),
      condition.detail,
    ]);
  }
  if (block.flag) {
    rows.body.push([
      `0x${block.flag.op.toString(16).toUpperCase()} ${OPCODE_NAMES[block.flag.op] || ''}`,
      operandCells(ctx, block.flag.operands, repaint),
      '不跳转（改完标志接着往下走）',
      `置上或清掉战斗标志 #${block.flag.values.battle_flag}` +
      `（模式 = ${block.flag.values.flag_mode}，这个模式代表什么仓库还没命名）。`,
    ]);
  }
  if (!rows.body.length) {
    rows.body.push(['—', '—', '—', '这一处没有任何条件：压入事件 id 就会触发这一段对白。']);
  }
  wrap.appendChild(summaryTable(rows));

  // --- 对白表 -----------------------------------------------------------
  if (block.segment) {
    const lines = block.segment.lines;
    wrap.appendChild(el('h4', { class: 'trigger-sub', text: `第 ${block.segment.index} 段对白` }));
    if (!lines.length) {
      wrap.appendChild(el('div', { class: 'empty', text: '这一段没有文本指令。' }));
    } else {
      const dialogue = { head: ['对白（可改，长度不限）'], body: [] };
      for (const line of lines) {
        dialogue.body.push([textCell(ctx, rom, line)]);
      }
      wrap.appendChild(summaryTable(dialogue));
    }
  }
  return wrap;
}

/** 一行操作数：标签 + 输入框。 */
function operandCells(ctx, operands, repaint) {
  return el('div', {}, operands.map((operand) => {
    const input = operandInput(ctx, operand);
    // 改完要把这一块重画 —— 摘要里的数字跟着变。
    input.addEventListener('change', () => repaint());
    return el('div', { class: 'operand-row' }, [
      el('span', { class: 'operand-label', text: operand.label }),
      input,
    ]);
  }));
}

/** 跳到剧情页看战前 / 战后剧本。 */
function storyLink(ctx, root, scene, label) {
  return el('button', {
    class: 'btn btn-tiny',
    text: label,
    onclick: () => ctx.onJump({
      module: 'story',
      kind: 'script',
      id: 'script',
      params: { root, scene },
      label: `${label}（第 ${scene} 场）`,
    }),
  });
}

/**
 * One condition parameter: the raw byte plus what that byte means here.
 */
function paramCell(value, meaning) {
  return el('div', {}, [
    el('code', { text: String(value) }),
    el('div', { class: 'stat-hint', text: meaning }),
  ]);
}

/**
 * One numeric field of a structure record, editable in place.
 *
 * The write-back follows the pack's model: only this field changes, every
 * other byte of the record stays as it was.
 */
function numCell(ctx, structure, record, key, value) {
  if (!structure || !record) return String(value);
  return el('input', {
    class: 'num-input',
    type: 'text',
    style: { width: '64px' },
    value: String(value),
    onchange: (e) => {
      const next = Number(e.target.value);
      if (!Number.isFinite(next) || next < 0 || next > 0xffff) {
        toast('请输入 0–65535', 'error');
        e.target.value = String(value);
        return;
      }
      ctx.pack.setValue(structure, record, key, next);
      ctx.onChange();
      toast(`已改写 ${structure.label} · ${key}`);
    },
  });
}

/**
 * Map "rule record : group : index" to the sentence that describes it.
 *
 * The battle-objective text table carries the sentences; the `bindings` array
 * says which condition each sentence belongs to (several conditions share one
 * sentence, so the map is not one-to-one).
 */
function objectiveBindings(table) {
  const map = new Map();
  if (!table) return map;
  const records = table.records || [];
  for (const binding of table.bindings || []) {
    const record = records[binding.text_id];
    if (!record) continue;
    map.set(`${binding.rule}:${binding.group}:${binding.index}`, record);
  }
  return map;
}

/**
 * The battle objective's description sentence.
 *
 * The rule record holds an **absolute** pointer to the sentence the player
 * sees on the Conditions page.  The sentence itself lives in the battle
 * objective text table, so it can be shown and edited in place — but only to
 * the same byte length, because the address is baked into the ROM.
 */
function descriptionCell(ctx, textTable, record) {
  if (!record) return el('span', { class: 'stat-hint', text: '—' });
  const text = record.text ?? '';
  const used = ctx.pack.font.encodedLength(text);
  const input = el('input', {
    class: 'text-input-inline',
    type: 'text',
    value: text,
    onchange: (e) => {
      const value = e.target.value;
      const missing = ctx.pack.font.missingCharacters(value);
      if (missing.length) {
        toast(`字库里没有这些字：${missing.join(' ')}`, 'error');
        e.target.value = text;
        return;
      }
      const bytes = ctx.pack.font.encodedLength(value);
      if (record.capacity && bytes + 1 > record.capacity) {
        toast(
          `超长：需要 ${bytes + 1} 字节，槽位只有 ${record.capacity} 字节` +
          '（该说明文字被绝对地址引用，只能等长改写）',
          'error'
        );
        e.target.value = text;
        return;
      }
      ctx.pack.setText(textTable, record, value);
      ctx.onChange();
      toast('已改写战斗目标说明文字');
    },
  });
  return el('div', {}, [
    input,
    el('div', {
      class: 'stat-hint',
      text: `${used} / ${record.capacity} 字节 · ${ptrText(record.pointer)}`,
    }),
  ]);
}

export function ptrText(value) {
  if (!value) return 'NULL';
  return '0x' + (value >>> 0).toString(16).toUpperCase();
}
