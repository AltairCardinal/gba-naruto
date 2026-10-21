// Headless view test: render the editor's views without a browser.
//
// The in-browser self-test (tools/selftest.html) covers the same ground, but
// this environment's embedded browser keeps reloading the tab, so the page
// never finishes a run.  This file renders the same views against a minimal
// DOM stub, which makes the view assertions reproducible in CI.
//
// Run:  node tools/verify_views.mjs
import { readFileSync } from 'node:fs';
import { gunzipSync } from 'node:zlib';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

// --- a very small DOM ------------------------------------------------------
class StubNode {
  constructor(tag) {
    this.tagName = String(tag || '').toUpperCase();
    this.nodeType = 1;
    this.children = [];
    this.parentNode = null;
    this.attributes = {};
    this.dataset = {};
    this.style = {};
    this.listeners = {};
    this._text = '';
    this._className = '';
    const self = this;
    this.classList = {
      add: (...names) => {
        const set = new Set(self._className.split(/\s+/).filter(Boolean));
        names.forEach((n) => set.add(n));
        self._className = [...set].join(' ');
      },
      remove: (...names) => {
        const set = new Set(self._className.split(/\s+/).filter(Boolean));
        names.forEach((n) => set.delete(n));
        self._className = [...set].join(' ');
      },
      toggle: (name, force) => {
        const has = self.classList.contains(name);
        const want = force === undefined ? !has : !!force;
        if (want) self.classList.add(name); else self.classList.remove(name);
        return want;
      },
      contains: (name) => self._className.split(/\s+/).includes(name),
    };
  }
  get className() { return this._className; }
  set className(v) { this._className = String(v || ''); }
  get value() { return this.attributes.value ?? ''; }
  set value(v) { this.attributes.value = String(v); }
  get firstChild() { return this.children[0] || null; }
  get textContent() {
    if (this.children.length) return this.children.map((c) => c.textContent).join('');
    return this._text;
  }
  set textContent(v) { this.children = []; this._text = String(v === null || v === undefined ? '' : v); }
  set innerHTML(v) { this.children = []; this._text = String(v || ''); }
  get innerHTML() { return this.textContent; }
  appendChild(node) {
    if (node && node.__text) {
      this.children.push({ textContent: node.__text, nodeType: 3, children: [] });
    } else {
      this.children.push(node);
      if (node) node.parentNode = this;
    }
    return node;
  }
  removeChild(node) {
    const at = this.children.indexOf(node);
    if (at >= 0) this.children.splice(at, 1);
    return node;
  }
  remove() { if (this.parentNode) this.parentNode.removeChild(this); }
  addEventListener(name, fn) { (this.listeners[name] ||= []).push(fn); }
  setAttribute(name, value) { this.attributes[name] = String(value); }
  getAttribute(name) { return this.attributes[name] ?? null; }
  querySelector() { return null; }
  querySelectorAll() { return []; }
  /** Every descendant element (the stub has no CSS engine). */
  descendants() {
    const out = [];
    const walk = (node) => {
      for (const child of node.children) {
        if (!child || !child.children) continue;
        out.push(child);
        walk(child);
      }
    };
    walk(this);
    return out;
  }
}

const documentStub = {
  createElement: (tag) => new StubNode(tag),
  createTextNode: (text) => ({ __text: String(text), textContent: String(text), nodeType: 3 }),
  body: new StubNode('body'),
  getElementById: () => null,
  querySelector: () => null,
};
globalThis.document = documentStub;
globalThis.setTimeout = globalThis.setTimeout || (() => 0);
globalThis.window = {
  location: { hash: '' },
  addEventListener() {},
  removeEventListener() {},
};

const { ContentPack } = await import('../js/pack.js');
const { renderStory } = await import('../js/modules/story.js');
const { renderItems } = await import('../js/modules/items.js');
const { renderCharacters } = await import('../js/modules/characters.js');
const { renderNinjutsu } = await import('../js/modules/ninjutsu.js');
const { renderBattle, renderStage } = await import('../js/modules/battle.js');
const routeModule = await import('../js/modules/route.js');
const renderRoute = routeModule.renderRoute;
const renderRouteStage = routeModule.renderStage;
const { renderAudio } = await import('../js/modules/audio.js');
const { renderAssets } = await import('../js/modules/assets.js');
const { renderRaw } = await import('../js/modules/raw.js');

const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, '..');

let failures = 0;
function check(name, ok, detail = '') {
  if (!ok) failures += 1;
  console.log(`  [${ok ? 'PASS' : 'FAIL'}] ${name}${detail ? ' — ' + detail : ''}`);
}

const packData = JSON.parse(readFileSync(join(root, 'content', 'pack.json'), 'utf8'));
const pack = ContentPack.fromJSON(packData);
try {
  const index = JSON.parse(gunzipSync(readFileSync(join(root, 'content', 'text-index.json.gz'))).toString('utf8'));
  pack.texts.push(index);
} catch (err) {
  console.log('  （未找到 text-index.json.gz）');
}

const statuses = [];
// A synthetic canvas that mirrors the real ROM's shape: zeroed, with the
// 0xFF free region at 0x5DFBEC that the text rewriter allocates from.
const base = new Uint8Array(0x600000);
base.fill(0xff, 0x5dfbec);
const ctx = {
  pack,
  rom: base,
  baseRom: base,
  state: { view: { panel: null } },
  onChange() {},
  openPanel() {},
  render() {},
  setStatus(message) { statuses.push(message); },
};

console.log('1) 每个模块的首页都能渲染');
const MODULES = [
  ['剧情与对白', renderStory],
  ['道具', renderItems],
  ['角色属性与技能', renderCharacters],
  ['忍术', renderNinjutsu],
  ['战斗', renderBattle],
  ['剧情路线', renderRoute],
  ['音频', renderAudio],
  ['素材与资源', renderAssets],
  ['原始字节', renderRaw],
];
for (const [label, render] of MODULES) {
  const host = new StubNode('div');
  ctx.state.view = { panel: null };
  let error = null;
  try {
    render(host, ctx);
  } catch (err) {
    error = err;
  }
  const text = host.textContent;
  check(`${label}：首页渲染`, !error && text.length > 80,
    error ? String(error.message) : `${text.length} 字符`);
}

console.log('\n2) 战斗：第 40 关的视图');
{
  const host = new StubNode('div');
  let error = null;
  let text = '';
  try {
    renderStage(host, ctx, 40, 0);
    text = host.textContent;
  } catch (err) {
    error = err;
  }
  check('战斗视图渲染成功', !error && text.length > 200,
    error ? String(error.message) : `${text.length} 字符`);
  for (const needle of ['战场布置', '角色出生点', '战斗目标', '战场物件', '战场事件']) {
    check(`战斗视图含「${needle}」`, text.includes(needle));
  }

  // 说明文字必须显示成原文，而不是只有指针
  const rules = pack.structure('battle_rules');
  const rule = rules.records.find((r) => r.rom_offset === 0x594758 + 40 * 0xcc);
  const objectives = pack.textTable('battle_objectives');
  const byPointer = new Map();
  for (const r of objectives.records) byPointer.set(r.pointer, r);
  let sample = '';
  for (let g = 0; g < 2 && !sample; g++) {
    for (let k = 0; k < 4 && !sample; k++) {
      const ptr = rule.values[`g${g}_${k}_text_ptr`];
      if (!ptr) continue;
      const rec = byPointer.get(ptr);
      if (rec && rec.text) sample = rec.text;
    }
  }
  // 说明文字放在输入框里，所以要读输入框的 value（不是 textContent）
  const inputs = host.descendants().filter((n) => n.tagName === 'INPUT');
  const values = inputs.map((n) => n.value);
  check('说明文字是可编辑的输入框', !!sample && values.includes(sample),
    `输入框 ${inputs.length} 个，样例「${sample}」${values.includes(sample) ? '在其中' : '不在其中'}`);
  // 输入框下面还要标出字节用量与地址
  check('说明文字标出字节用量与地址', /\d+ \/ \d+ 字节 · 0x[0-9A-F]+/.test(text),
    (text.match(/\d+ \/ \d+ 字节 · 0x[0-9A-F]+/) || ['没有'])[0]);

  // 类型 2 的语义必须与原生行为一致
  check('类型 2 标注为「回合用尽」', text.includes('回合用尽'),
    text.includes('回合用尽') ? '已标注' : '没有标注');
  check('不再声称类型 2 是「指定角色仍在场」', !text.includes('指定角色仍在场上'));

  // 参数含义要写出来
  check('参数含义被标注', text.includes('角色 id') || text.includes('道具序号'));

  // --- 就地编辑：改一个出生点的 X，落点必须正确 -------------------------
  const actors = pack.structure('battle_actors');
  const slot0 = actors.records.find(
    (r) => r.rom_offset === 0x5461c4 + 40 * 0x1aac + 4);
  const allInputs = host.descendants().filter((n) => n.tagName === 'INPUT');
  // 每行 5 个输入框：角色 id / X / Y / 朝向 / 等级
  const xInput = allInputs[1];
  check('出生点表格里 X 是可编辑输入框', !!xInput && xInput.value === String(slot0.values.x),
    `X=${xInput ? xInput.value : '没有输入框'}（原生 ${slot0.values.x}）`);
  if (xInput) {
    xInput.listeners.change[0]({ target: { value: '9' } });
    const changed = slot0.values.x === 9;
    check('改出生点的 X 立刻写回内容包', changed,
      `x = ${slot0.values.x}`);
    // 构建后必须只动那一个字节
    const { buildRom } = await import('../js/rom.js');
    const rom = new Uint8Array(0x600000);
    rom.fill(0xff, 0x5dfbec);
    const out = buildRom(pack, rom);
    const offset = slot0.rom_offset + 0x02;   // x 在记录里的偏移
    check('改出生点的 X 只动那一个字节',
      out.report.errors.length === 0 && out.bytes[offset] === 9,
      out.report.errors.join('; ') ||
      `@0x${offset.toString(16)} = ${out.bytes[offset]}`);
    // 复原，避免影响后面的断言
    slot0.values.x = slot0.original_x ?? slot0.values.x;
  }
}

console.log('\n3) 剧情路线：第 40 关的视图');
{
  const host = new StubNode('div');
  let error = null;
  let text = '';
  try {
    renderRouteStage(host, ctx, 40);
    text = host.textContent;
  } catch (err) {
    error = err;
  }
  check('剧情路线视图渲染成功', !error && text.length > 200,
    error ? String(error.message) : `${text.length} 字符`);
  for (const needle of ['剧情脚本', '剧情路线', '任务文本', '奖励']) {
    check(`剧情路线视图含「${needle}」`, text.includes(needle));
  }
  // 路线边必须真的列出来（脚本里的「下一场景」）
  const edges = (pack.scripts || []).reduce((n, s) => n + ((s.route || []).length), 0);
  check('剧情路线列出脚本里的路线边', edges > 0 && text.includes('0x16') || text.includes('0x1A'),
    `内容包里有 ${edges} 条边`);
  // 本关的任务文本必须显示出来（标题/说明/提示）
  const titles = pack.textTable('mission_titles');
  const descs = pack.textTable('mission_descriptions');
  const hints = pack.textTable('mission_hints');
  const index = pack.structure('mission_index');
  const base = index.records[40] ? index.records[40].values.value : null;
  const slot = base === null ? null : base;
  const titleText = slot !== null && titles.records[slot] ? titles.records[slot].text : '';
  const descText = slot !== null && descs.records[slot] ? descs.records[slot].text : '';
  const hintText = slot !== null && hints.records[slot] ? hints.records[slot].text : '';
  check('本关任务标题/说明/提示都显示出来',
    !!titleText && !!descText && !!hintText &&
    text.includes(titleText) && text.includes(descText) && text.includes(hintText),
    `标题「${titleText}」说明「${(descText || '').slice(0, 12)}…」提示「${(hintText || '').slice(0, 12)}…」`);
}

console.log('\n4) 字段元数据：枚举 / 跨表引用 / 分组 / 原始字节表');
{
  const fields = await import('../js/fields.js');
  const rules = pack.structure('battle_rules');
  const rule = rules.records.find((r) => r.rom_offset === 0x594758 + 40 * 0xcc);

  // 4a. 枚举 → 下拉（标签是人话，不是裸数字）
  const typeField = rules.fields.find((f) => f.key === 'g0_0_type');
  const control = fields.fieldControl(ctx, rules, rule, typeField);
  const options = control.node.children ? control.node.children.map((o) => o.textContent) : [];
  check('枚举字段渲染成下拉并带中文标签',
    control.node.tagName === 'SELECT' && options.some((t) => t.includes('回合用尽')),
    `选项：${options.slice(0, 3).join(' / ')}`);

  // 4b. 跨表引用 → 显示出名字
  const actors = pack.structure('battle_actors');
  const slot = actors.records.find((r) => r.rom_offset === 0x5461c4 + 40 * 0x1aac + 4);
  const actorHint = fields.fieldControl(
    ctx, actors, slot, actors.fields.find((f) => f.key === 'character_id')).hint.join(' | ');
  check('角色 id 显示成角色名', actorHint.includes('漩涡鸣人'), actorHint);

  // 4c. 奖励的物品 id 依赖同槽的类别
  const rewards = pack.structure('reward_table');
  const reward = rewards.records.find((r) => {
    const v = r.values;
    return v.slot0_category && v.slot0_item;
  });
  const itemHint = rewards
    ? fields.fieldControl(ctx, rewards, reward,
        rewards.fields.find((f) => f.key === 'slot0_item')).hint.join(' | ')
    : '';
  check('奖励物品 id 按类别显示对应名字', /物品名：/.test(itemHint), itemHint || '没有带掉落的记录');

  // 4d. 分组信息没丢
  const groups = fields.groupFields(rules.fields);
  check('字段分组被保留',
    groups.length >= 3 && groups.some((g) => g.name === '胜利条件'),
    groups.map((g) => `${g.name}×${g.fields.length}`).join('、'));

  // 4e. 整张表都是未解码字节 → 认出来
  check('整表未解码的结构被标记为 raw_only',
    fields.isRawOnly(pack.structure('item_record')),
    '道具/忍具记录表 94 条全是原始字节');
}

console.log('\n5) 结构编辑器：分组折叠 + 重复槽位成表 + 记录导航');
{
  const { StructureEditor } = await import('../js/editors.js');
  const host = new StubNode('div');
  const template = pack.structure('character_template');
  const editor = new StructureEditor(pack, template, { onChange: ctx.onChange });
  editor.render(host);
  const text = host.textContent;

  // 5a. 分组：角色定义表的 5 个分组都在，标题可读
  const groups = template.fields.reduce((set, f) => {
    if (f.group) set.add(f.group);
    return set;
  }, new Set());
  check('字段分组被渲染成可折叠分区', groups.size >= 5,
    [...groups].join('、'));

  // 5b. 默认只展开「有主列的分组」，其余折叠（标题里带规模）
  const record = template.records.find((r) => r.id === 1);
  editor.openDetail(record);
  const defaultInputs = host.descendants().filter(
    (n) => n.tagName === 'INPUT' || n.tagName === 'TEXTAREA' || n.tagName === 'SELECT');
  check('默认只展开少量分组', defaultInputs.length < 30,
    `默认 ${defaultInputs.length} 个控件（字段共 ${template.fields.length} 个）`);

  // 5c. 展开全部分组后，重复槽位渲染成表格
  editor.collapsed.clear();
  editor.openDetail(record);
  const all = host.descendants();
  const slotTables = all.filter((n) => n.className === 'grid grid-slots');
  const inTable = new Set();
  for (const table of slotTables) {
    for (const row of table.descendants()) inTable.add(row);
  }
  const loose = all.filter(
    (n) => ['INPUT', 'TEXTAREA', 'SELECT'].includes(n.tagName) && !inTable.has(n));
  check('重复槽位渲染成表格', slotTables.length >= 2,
    `${slotTables.length} 张槽位表`);
  check('槽位之外的控件很少', loose.length < 40,
    `表内 ${all.filter((n) => ['INPUT', 'TEXTAREA', 'SELECT'].includes(n.tagName)).length - loose.length} 个 + 表外 ${loose.length} 个`);

  // 5c. 槽位表里的行数 = 槽位数
  const jutsuTable = slotTables[0];
  const rows = jutsuTable ? jutsuTable.children[1].children : [];
  check('忍术槽是 15 行的表', rows.length === 15, `${rows.length} 行`);

  // 5d. 枚举 → 下拉；引用 → 名字
  const selects = all.filter((n) => n.tagName === 'SELECT');
  const optionTexts = selects.flatMap((s) => s.children.map((o) => o.textContent));
  check('档位用下拉并带中文标签',
    optionTexts.some((t) => t.includes('未习得')),
    optionTexts.slice(0, 4).join(' / '));
  check('忍术 id 显示成忍术名',
    (host.textContent || '').includes('分身术') ||
    (host.textContent || '').includes('变身术'),
    ((host.textContent || '').match(/分身术|变身术|螺旋丸/) || ['没有'])[0]);

  // 5e. 记录导航：下一条 / 上一条
  const navTexts = all.filter((n) => n.tagName === 'BUTTON').map((b) => b.textContent);
  check('详情面板有上一条/下一条', navTexts.includes('← 上一条') && navTexts.includes('下一条 →'),
    navTexts.filter((t) => t.includes('条')).join(' / '));

  // 5f. 改动标记
  const hpField = template.fields.find((f) => f.key === 'hp_base');
  const hpOriginal = record.values.hp_base;
  pack.setValue(template, record, 'hp_base', 123);
  editor.renderTable();
  const rowsAfter = host.descendants().filter((n) => n.tagName === 'TR');
  const changedRow = rowsAfter.find((tr) => (tr.className || '').includes('changed'));
  check('改过的记录在表格里被标出来', !!changedRow,
    changedRow ? '有 changed 标记' : '没有标记');
  pack.setValue(template, record, 'hp_base', hpOriginal);
}

console.log('\n6) 写回安全性：越界拒绝 / 有符号原值 / 指针解析 / 改后即刷新');
{
  const { StructureEditor } = await import('../js/editors.js');
  const fields = await import('../js/fields.js');

  // 6a. 越界必须被拒绝，不能落到写回时的掩码里（999 → 231 那种静默截断）
  const template = pack.structure('character_template');
  const templateRecord = template.records.find((r) => r.id === 1);
  const statA = template.fields.find((f) => f.key === 'stat_a');
  const statABefore = templateRecord.values.stat_a;
  const control = fields.fieldControl(ctx, template, templateRecord, statA);
  control.node.listeners.change[0]({ target: { value: '999' } });
  check('越界的数值被拒绝写回',
    templateRecord.values.stat_a === statABefore,
    `u8 字段输入 999，原值 ${statABefore}，现在 ${templateRecord.values.stat_a}`);

  // 6b. s16 必须按有符号读：原值 -4，不是 65532
  const delta = pack.structure('unit_delta_table');
  const deltaRecord = delta.records[0];
  const deltaField = delta.fields.find((f) => f.key === 'delta');
  const original = fields.originalValue(delta, deltaRecord, deltaField);
  check('有符号字段按有符号读', original === -4, `原值 ${original}`);

  // 6c. 指针型 relation 要按地址查表（说明文字指针 → 那句话）
  const rules = pack.structure('battle_rules');
  const rule = rules.records.find((r) => r.rom_offset === 0x594758 + 40 * 0xcc);
  const ptrField = rules.fields.find((f) => f.key === 'g0_0_text_ptr');
  const ptrValue = rule.values[ptrField.key];
  const hit = fields.resolveRelation(pack, ptrField.relation, ptrValue);
  check('说明文字指针解析出那句话',
    !!hit && hit.name === '得到宝箱了',
    `0x${(ptrValue >>> 0).toString(16).toUpperCase()} → ${hit ? hit.name : '没解析出来'}`);

  // 6d. 改完必须立刻刷新：表格有 changed 标记、字段带「已改」
  const host = new StubNode('div');
  const editor = new StructureEditor(pack, template, { onChange: ctx.onChange });
  editor.render(host);
  const record = template.records.find((r) => r.id === 1);
  const hpBefore = record.values.hp_base;
  editor.openDetail(record);
  const hpField = template.fields.find((f) => f.key === 'hp_base');
  const hpInput = editor.detail.descendants().find(
    (n) => n.tagName === 'INPUT' && n.value === String(hpBefore));
  check('找到 HP 基础输入框', !!hpInput, hpInput ? `值 ${hpInput.value}` : '没有');
  if (hpInput) {
    hpInput.listeners.change[0]({ target: { value: '123' } });
    const changedRows = host.descendants().filter(
      (n) => n.tagName === 'TR' && (n.className || '').includes('changed'));
    const changedFields = editor.detail.descendants().filter(
      (n) => (n.className || '').includes('field-changed'));
    check('改完立刻刷新：行有 changed 标记',
      changedRows.length > 0,
      `${changedRows.length} 行被标记`);
    check('改完立刻刷新：字段带「已改」',
      changedFields.length > 0,
      `${changedFields.length} 个字段被标记`);
    // 复原
    pack.setValue(template, record, 'hp_base', hpBefore);
  }
}

console.log('\n7) 文本表编辑器：写回规则 / 控制码分段 / 标记 / 行数上限 / 无位置槽');
{
  const { TextTableEditor } = await import('../js/editors.js');
  const host = new StubNode('div');

  // 7a. 写回规则要说清楚：可重定位 vs 等长
  const names = pack.textTable('character_names');
  const reloc = new TextTableEditor(pack, names, { onChange: ctx.onChange });
  reloc.render(host);
  check('可重定位表说明写回规则',
    (host.textContent || '').includes('长度可变'),
    (host.textContent || '').slice(0, 40));
  const objectives = pack.textTable('battle_objectives');
  const fixed = new TextTableEditor(pack, objectives, { onChange: ctx.onChange });
  const host2 = new StubNode('div');
  fixed.render(host2);
  check('等长表说明写回规则',
    (host2.textContent || '').includes('长度不能变'),
    (host2.textContent || '').includes('长度不能变') ? '已说明' : '没有说明');

  // 7b. 控制码分段条
  const desc = pack.textTable('mission_descriptions');
  const withCtrl = desc.records.find((r) => r.text && r.raw && r.raw.includes('AQ'));
  if (!withCtrl) {
    check('控制码分段条', false, '没有找到带控制码的记录');
  } else {
    const host3 = new StubNode('div');
    const editor = new TextTableEditor(pack, desc, { onChange: ctx.onChange });
    editor.render(host3);
    editor.openDetail(withCtrl);
    const segs = host3.descendants().filter((n) => (n.className || '').includes('seg-ctrl'));
    check('控制码分段条把控制码画出来', segs.length > 0,
      `${segs.length} 个控制码段`);
  }

  // 7c. 共享 / 归属标记
  const titles = pack.textTable('mission_titles');
  const shared = titles.records.find((r) => (r.shared_with || []).length > 0);
  const host4 = new StubNode('div');
  const editor4 = new TextTableEditor(pack, titles, { onChange: ctx.onChange });
  editor4.render(host4);
  const chips = host4.descendants().filter((n) => (n.className || '').includes('mark-shared'));
  check('共用同一段字节的条目被标出来', chips.length > 0,
    shared ? `${shared.shared_with.length + 1} 处共用` : '没有共用条目');

  // 7d. 大表默认只渲染前 200 行
  const index = pack.textTable('rom_text_index');
  if (!index) {
    check('大表默认只渲染前 200 行', false, '文本索引未载入');
  } else {
    const host5 = new StubNode('div');
    const editor5 = new TextTableEditor(pack, index, { onChange: ctx.onChange });
    editor5.render(host5);
    const rows = host5.descendants().filter((n) => n.tagName === 'TR').length;
    check('大表默认只渲染前 200 行', rows <= 201, `渲染了 ${rows} 行（含表头）`);
    check('被具名表拥有的条目默认不显示',
      (host5.textContent || '').includes('显示已被其它表拥有的条目'),
      '有开关');
  }

  // 7e. 没有 ROM 位置的槽位不可编辑
  const slots = pack.textTable('dialogue_slots');
  const nullSlot = slots.records.find((r) => r.text_offset === null);
  if (!nullSlot) {
    check('无位置的槽位不可编辑', false, '没有找到空指针槽');
  } else {
    const host6 = new StubNode('div');
    const editor6 = new TextTableEditor(pack, slots, { onChange: ctx.onChange });
    editor6.render(host6);
    editor6.openDetail(nullSlot);
    const areas = editor6.detail.descendants().filter((n) => n.tagName === 'TEXTAREA');
    check('无位置的槽位不可编辑', areas.length > 0 && areas[0].attributes.disabled === '',
      areas.length ? '文本框已禁用' : '没有文本框');
  }
}

console.log('\n8) 域首页：每张表都够得着 + 带可编辑性信息');
{
  const DOMAINS = [
    ['剧情与对白', renderStory, 'story'],
    ['道具', renderItems, 'items'],
    ['角色属性与技能', renderCharacters, 'characters'],
    ['忍术', renderNinjutsu, 'ninjutsu'],
    ['战斗', renderBattle, 'battle'],
    ['剧情路线', renderRoute, 'route'],
    ['音频', renderAudio, 'audio'],
    ['素材与资源', renderAssets, 'assets'],
  ];
  for (const [label, render, module] of DOMAINS) {
    const host = new StubNode('div');
    ctx.state.view = { panel: null };
    let error = null;
    try {
      render(host, ctx);
    } catch (err) {
      error = err;
    }
    const text = host.textContent || '';
    const tables = host.descendants().filter((n) => n.tagName === 'TR');
    const cards = host.descendants().filter((n) => (n.className || '') === 'stat');
    const expected = pack.structures.filter((s) => s.module === module).length +
      pack.texts.filter((t) => t.module === module).length;
    check(`${label}：域首页渲染且列出本域全部表`,
      !error && tables.length >= expected &&
      (host.textContent || '').includes('本域可编辑内容'),
      error ? String(error.message) : `${tables.length} 行（应 ≥ ${expected}）`);
    check(`${label}：不再是纯卡片墙`, cards.length <= 5,
      `${cards.length} 张卡片`);
  }

  // 战斗域的 7 张表以前在首页根本够不着
  const battleHost = new StubNode('div');
  ctx.state.view = { panel: null };
  renderBattle(battleHost, ctx);
  const battleText = battleHost.textContent || '';
  const hidden = ['单位槽位重映射表', '八方向位移表', '战场事件逻辑根表', '战场事件根表',
    '战斗/地图事件处理程序分派表', '精灵帧描述符表', '原生拾取分派表'];
  const stillHidden = hidden.filter((name) => !battleText.includes(name));
  check('战斗域 7 张原先够不着的表现在都在首页',
    stillHidden.length === 0,
    stillHidden.length ? `还缺：${stillHidden.join('、')}` : '全部可达');

  // 剧情与对白域的字宽表以前任何域都够不着
  const storyHost = new StubNode('div');
  ctx.state.view = { panel: null };
  renderStory(storyHost, ctx);
  check('字宽表现在在剧情与对白域首页',
    (storyHost.textContent || '').includes('字宽表'),
    '可达');
}

console.log('\n9) 导航：URL 可寻址 + 跨域引用可点');
{
  const routing = await import('../js/routing.js');
  const cases = [
    ['#overview', 'overview', null],
    ['#battle', 'battle', null],
    ['#battle/stage/40/0', 'battle', 'stage'],
    ['#characters/structure/character_template/1', 'characters', 'structure'],
    ['#characters/text/dialogue_slots/12', 'characters', 'text'],
  ];
  for (const [hash, module, kind] of cases) {
    const parsed = routing.parseHash(hash);
    check(`URL 可寻址 ${hash}`,
      parsed.module === module && (kind === null || (parsed.panel && parsed.panel.kind === kind)),
      `${parsed.module}/${parsed.panel ? parsed.panel.kind : '无面板'}`);
  }
  check('hash 能写回去',
    routing.hashFor({ module: 'characters', panel: { kind: 'structure', id: 'character_template', params: { recordId: 1 } } })
      === '#characters/structure/character_template/1',
    '往返一致');

  // 跨域跳转：忍术 id 字段旁边应当有可点的链接
  const { StructureEditor } = await import('../js/editors.js');
  const template = pack.structure('character_template');
  const jumps = [];
  const host = new StubNode('div');
  const editor = new StructureEditor(pack, template, {
    onChange: ctx.onChange,
    onJump: (target) => jumps.push(target),
  });
  editor.render(host);
  const record = template.records.find((r) => r.id === 1);
  editor.collapsed.clear();     // 忍术槽在折叠的分组里，展开才看得见链接
  editor.openDetail(record);
  const links = editor.detail.descendants().filter((n) => (n.className || '') === 'xref-link');
  check('跨表引用是可点的链接', links.length > 0, `${links.length} 个链接`);
  if (links.length) {
    links[0].listeners.click[0]({ target: {} });
    const target = jumps[0];
    check('点击链接跳到目标表与记录',
      !!target && target.module === 'ninjutsu' && target.kind === 'text' &&
      target.id === 'jutsu_names' && target.recordId !== null,
      target ? `${target.module}/${target.kind}/${target.id}#${target.recordId}` : '没有跳转');
  }
}

console.log(`\n${failures === 0 ? '全部通过' : failures + ' 项失败'}`);
process.exit(failures === 0 ? 0 : 1);
