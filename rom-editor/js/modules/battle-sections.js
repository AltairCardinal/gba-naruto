// 战斗域「一关之内的全部配置」——按类拆成几块，交给战场地图视图的右侧页签。
//
// 这些内容原来在「关卡视图」里（battle.js 的一长条纵向页面）。
// 地图升为主界面之后，它们改挂在地图右侧的页签上：
// 战场布置 / 战场物件 / 角色出生点 在 battle-map.js 里（它们与地图标记联动），
// 胜负条件 与 剧情触发 在这里（与地图没有空间关系，但说的仍是**这一关**）。

import { el, toast } from '../ui.js';
import { fieldControl } from '../fields.js';
import { summaryTable, operandInput, BATTLE_LAYOUT } from './common.js';

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
  ]);
}

/**
 * 这一关在战斗里会触发的剧情。
 *
 * 四张根表定位到本关的四个剧本（战前 / 战后 / 战场事件逻辑 / 战场事件表），
 * 剧本里的 0x22 指令「把角色加入战斗配置」会回到编成矩阵去取角色与等级 ——
 * 所以**出生点那一页改的就是「战斗中谁出场」**。
 *
 * @param {object} ctx
 * @param {number} stage
 * @returns {HTMLElement}
 */
export function renderScriptsTab(ctx, stage) {
  const pack = ctx.pack;
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
      '因此**在「角色出生点」那一页改角色 id / 等级 / 出生点，就等于改了战斗中谁出场、在哪出现**。',
    ]),
    summaryTable(scriptRows),
  ]);
  if (operandRows.body.length) {
    node.appendChild(el('h3', { text: '本关剧情脚本里可改的操作数' }));
    node.appendChild(el('p', { class: 'section-note' }, [
      '0x1E 决定本关载入哪张地图，0x1F 决定用哪个子配置，0x23 决定队员，' +
      '0x22 是「把角色加入战斗配置」。这些操作数都是定宽的，改它们是原地写，' +
      '不会让脚本里的分支目标失效。',
      '（带操作数的是战前/战后剧本；战场事件逻辑与事件表的指令表由原生代码消费，' +
      '仓库没有证明其字段语义，所以不列为可改。）',
    ]));
    node.appendChild(summaryTable(operandRows));
  }
  return node;
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
