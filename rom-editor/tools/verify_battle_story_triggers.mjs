// 「战斗编辑界面里的剧情触发列表」的无头验收（第十一轮）。
//
// 对应 notes/specs/battle-story-triggers-20261022.md §4 的 V1–V12，
// 其中三条按审核 notes/reviews/battle-story-triggers-review-20261022.md §5 的
// M3 改写过：V8（降级）、V12（人话摘要）、V5（前提）。
//
// 用法：node rom-editor/tools/verify_battle_story_triggers.mjs
//
// stdout 在 PowerShell 下会被 GBK 弄乱，所以正文写到
// build/battle-story-trigger-verify.txt（同 tools/probe_battle_story_triggers.mjs）。
import { readFileSync, writeFileSync, existsSync, readdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

// --- 一个很小的 DOM（与 verify_battle_map.mjs 同一套）--------------------
class StubNode {
  constructor(tag) {
    this.tagName = String(tag || '').toUpperCase();
    this.nodeType = 1;
    this.children = [];
    this.parentNode = null;
    this.attributes = {};
    this.dataset = {};
    this.style = { setProperty(name, value) { this[name] = value; } };
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
  get parentElement() { return this.parentNode || null; }
  removeChild(node) {
    const at = this.children.indexOf(node);
    if (at >= 0) this.children.splice(at, 1);
    return node;
  }
  remove() { if (this.parentNode) this.parentNode.removeChild(this); }
  addEventListener(name, fn) { (this.listeners[name] ||= []).push(fn); }
  removeEventListener() {}
  setAttribute(name, value) { this.attributes[name] = String(value); }
  getAttribute(name) { return this.attributes[name] ?? null; }
  querySelector() { return null; }
  querySelectorAll() { return []; }
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
globalThis.window = {
  location: { hash: '' },
  addEventListener() {},
  removeEventListener() {},
};

const here = dirname(fileURLToPath(import.meta.url));
const repoRoot = join(here, '..', '..');
const editorRoot = join(repoRoot, 'rom-editor');
const packPath = join(editorRoot, 'content', 'pack.json');
const romPath = join(repoRoot, 'rom', 'base.gba');
const mapAssetPath = join(editorRoot, 'content', 'maps', 'maps.bin.gz');
const notesRoot = join(repoRoot, 'notes');

/** 素材包：战场地图视图要它（降级那一关也要）。 */
globalThis.fetch = async (url) => {
  const href = String(url);
  if (href.includes('maps.bin.gz')) {
    if (!existsSync(mapAssetPath)) {
      return { ok: false, status: 404, arrayBuffer: async () => new ArrayBuffer(0) };
    }
    const bytes = readFileSync(mapAssetPath);
    return {
      ok: true,
      status: 200,
      arrayBuffer: async () => bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength),
    };
  }
  return { ok: false, status: 404, arrayBuffer: async () => new ArrayBuffer(0) };
};

const { ContentPack } = await import('../js/pack.js');
const { buildRom } = await import('../js/rom.js');
const vm = await import('../js/storyvm.js');
const bt = await import('../js/battletriggers.js');
const scripttext = await import('../js/scripttext.js');
const { renderScriptsTab } = await import('../js/modules/battle-sections.js');
const { renderScriptView } = await import('../js/modules/scriptview.js');
const { renderBattleMap } = await import('../js/modules/battle-map.js');

const packData = JSON.parse(readFileSync(packPath, 'utf8'));
const originalRom = new Uint8Array(readFileSync(romPath));

let failures = 0;
const lines = [];
function check(name, ok, detail = '') {
  if (!ok) failures += 1;
  const line = `  [${ok ? 'PASS' : 'FAIL'}] ${name}${detail ? ' — ' + detail : ''}`;
  lines.push(line);
  console.log(line);
}
function head(text) {
  lines.push(text);
  console.log(text);
}
function note(text) {
  lines.push(`  [NOTE] ${text}`);
  console.log(`  [NOTE] ${text}`);
}

/** 一个干净的内容包（每段测试各自用新的，免得互相污染）。 */
function freshPack() {
  const pack = ContentPack.fromJSON(JSON.parse(JSON.stringify(packData)));
  pack.map_assets = packData.map_assets;
  return pack;
}

/** 内容包当模型用（battletriggers.js 只问根指针）。 */
function packAsModel(pack) {
  return { structure: (id) => pack.structures.find((s) => s.id === id) };
}

const ctxFor = (pack, rom = originalRom) => ({
  pack,
  rom,
  baseRom: rom,
  state: { view: { panel: null } },
  onChange() {},
  openPanel() {},
  goModule() {},
  render() {},
  setStatus() {},
  onJump() {},
});

const byClass = (host, name) =>
  host.descendants().filter((n) => String(n.className || '').split(/\s+/).includes(name));

/** 某个 dataset 标记下的节点。 */
function byDataset(host, key, value) {
  return host.descendants().find((n) => n.dataset && n.dataset[key] === value);
}

const SCENES = [];
for (let scene = 1; scene <= 46; scene += 1) SCENES.push(scene);

const models = new Map();
for (const scene of SCENES) {
  models.set(scene, bt.buildTriggerModel(originalRom, packAsModel(packData), scene));
}

head('1) V1 触发块与剧情段一一对应（数量对账）');
{
  let blocks = 0;
  let linked = 0;
  let unlinked = 0;
  let chain = 0;
  let mismatched = [];
  for (const scene of SCENES) {
    const model = models.get(scene);
    blocks += model.counts.blocks;
    linked += model.counts.linked;
    unlinked += model.counts.unlinked;
    chain += model.counts.chainLength;
    // 每个触发块 = logic 剧本里的一条 0x33
    const pushes = model.logicInstructions.filter((i) => i.op === bt.PUSH_OP).length;
    if (pushes !== model.counts.blocks) {
      mismatched.push(`第 ${scene} 关：0x33 ${pushes} 条 vs 触发块 ${model.counts.blocks} 个`);
    }
  }
  check('每一关的触发块数 == logic 剧本里 0x33 的条数', mismatched.length === 0,
    mismatched.slice(0, 3).join('；') || '46 关全部对上');
  check('全 46 关合计：触发块 407 个', blocks === 407, `${blocks} 个`);
  check('能选到剧情段的 400 个', linked === 400, `${linked} 个`);
  check('选不上的 7 个（场景 32..38 各一个，值 0）', unlinked === 7, `${unlinked} 个`);
  check('事件链合计 400 段', chain === 400, `${chain} 段`);
  const unlinkedScenes = SCENES.filter((s) => models.get(s).counts.unlinked > 0);
  check('选不上的都落在场景 32..38',
    unlinkedScenes.every((s) => s >= 32 && s <= 38) && unlinkedScenes.length === 7,
    unlinkedScenes.join('、'));
}

head('\n2) V2 链是 1 基的（用 ROM 字节钉死）');
{
  // handler：subs r0,#1 @ 0x08097D1A；cmp r0,r4 @ 0x08097D1C
  check('ROM 0x08097D1A 是 subs r0,#1（半字 0x3801 的首字节）',
    originalRom[0x08097D1A - 0x08000000] === 0x01,
    `实际 0x${originalRom[0x08097D1A - 0x08000000].toString(16)}`);
  check('ROM 0x08097D1C 是 cmp r0,r4',
    originalRom[0x08097D1C - 0x08000000] === 0xA0
    && originalRom[0x08097D1D - 0x08000000] === 0x42,
    `实际 0x${originalRom[0x08097D1C - 0x08000000].toString(16)}`
    + ` 0x${originalRom[0x08097D1D - 0x08000000].toString(16)}`);
  // 语义：value - 1 落在 [0, chain.length) 才允许 segment != null；value === 0 ⇒ segment === null
  let bad = [];
  for (const scene of SCENES) {
    for (const block of models.get(scene).blocks) {
      const n = models.get(scene).counts.chainLength;
      const expect = block.value >= 1 && block.value <= n;
      if (expect !== (block.segment !== null)) {
        bad.push(`第 ${scene} 关 #${block.index + 1}（value=${block.value}）`);
      }
      if (block.value === 0 && block.segment !== null) bad.push(`第 ${scene} 关 value=0 却选中了段`);
    }
  }
  check('value - 1 落在 [0, 链长) 才允许选到段；value = 0 选不到', bad.length === 0,
    bad.slice(0, 3).join('；') || '407 个触发块全部符合');
  // 界面上的说法必须带「推定」这个限定词
  check('1 基映射的说法带「按 ROM 字节推定」与「未做运行期确认」',
    bt.ONE_BASED_NOTE.includes('按 ROM 字节推定') && bt.ONE_BASED_NOTE.includes('未做运行期确认'),
    bt.ONE_BASED_NOTE);
}

head('\n3) V3 events 剧本的结构');
{
  let prefixOnly = 0;
  let payloadOK = 0;
  for (const scene of SCENES) {
    const model = models.get(scene);
    const events = model.eventsInstructions;
    const chainLen = model.counts.chainLength;
    const prefix = events.slice(0, chainLen).every((i) => i.op === bt.CHAIN_OP)
      && events.slice(chainLen).every((i) => i.op !== bt.CHAIN_OP);
    if (prefix) prefixOnly += 1;
    const starts = new Set(events.map((i) => i.offset));
    if (model.chain.every((c) => starts.has(c.target))) payloadOK += 1;
  }
  check('46/46 关：events 剧本的前 N 条指令全是 0x32（链是前缀）', prefixOnly === 46, `${prefixOnly}/46`);
  check('46/46 关：每条 0x32 的 u32 载荷落在同一剧本的指令起点上', payloadOK === 46, `${payloadOK}/46`);
}

head('\n4) V4 压值与链长的对账');
{
  let oneToOne = 0;
  let special = 0;
  let dup = 0;
  const bad = [];
  for (const scene of SCENES) {
    const model = models.get(scene);
    const values = model.blocks.map((b) => b.value);
    if (new Set(values).size !== values.length) dup += 1;
    const set = new Set(values);
    const chainLen = model.counts.chainLength;
    if (scene >= 32 && scene <= 38) {
      const ok = set.size === 4 && set.has(0) && set.has(1) && set.has(2) && set.has(3)
        && chainLen === 3 && model.counts.unlinked === 1;
      if (ok) special += 1; else bad.push(`第 ${scene} 关：值集合 ${[...set].join(',')} 链长 ${chainLen}`);
    } else {
      const want = new Set(Array.from({ length: chainLen }, (_, i) => i + 1));
      const ok = set.size === chainLen && [...set].every((v) => want.has(v));
      if (ok) oneToOne += 1; else bad.push(`第 ${scene} 关：值集合 ${[...set].join(',')} 链长 ${chainLen}`);
    }
  }
  check('39 个场景：压入的值集合 == {1..链长}', oneToOne === 39, `${oneToOne}/39`);
  check('7 个场景（32..38）：值集合 == {0,1,2,3}、链长 3、恰有 1 个选不中',
    special === 7, `${special}/7`);
  check('没有任何一关重复压同一个事件 id', dup === 0, `${dup} 关有重复`);
  if (bad.length) note(`对不上的场景：${bad.slice(0, 3).join('；')}`);
}

head('\n5) V5 定宽可改：改操作数不移动任何字节');
{
  // 前提（审核 P2-13）：u32 分支目标这一轮**不可改**。
  const sizeProblems = [];
  for (const op of [52, 53, 54, 55, 56, 57]) {
    for (const [name, [offset, size]] of Object.entries(vm.KNOWN_OPERANDS[op] || {})) {
      if (size !== 1) sizeProblems.push(`0x${op.toString(16)} 的 ${name} 是 ${size} 字节`);
    }
  }
  check('前提成立：0x34–0x39 的可改字段全是 1 字节（u32 目标不可改）',
    sizeProblems.length === 0, sizeProblems.join('；') || '没有 u32 字段');
  check('0x32（事件链选择）没有可改字段（载荷是段首地址）',
    !vm.KNOWN_OPERANDS[50], 'KNOWN_OPERANDS 里没有 0x32');

  let moved = 0;
  let lengthChanged = 0;
  let checked = 0;
  for (const scene of SCENES) {
    const model = models.get(scene);
    for (const block of model.blocks) {
      for (const condition of block.conditions) {
        const operand = condition.operands[0];
        if (!operand) continue;
        const before = vm.instructionLength(originalRom, condition.offset);
        const copy = new Uint8Array(originalRom);
        copy[operand.rom_offset] = (operand.value + 1) & 0xff;
        const after = vm.instructionLength(copy, condition.offset);
        if (after !== before) lengthChanged += 1;
        const beforeOffsets = model.logicInstructions.map((i) => i.offset);
        const afterOffsets = vm.scanScript(copy, model.logicPtr - vm.ROM_BASE).map((i) => i.offset);
        if (beforeOffsets.join(',') !== afterOffsets.join(',')) moved += 1;
        checked += 1;
        if (checked >= 120) break;
      }
      if (checked >= 120) break;
    }
    if (checked >= 120) break;
  }
  check('改一个定宽 u8 操作数后，指令长度不变', lengthChanged === 0, `${lengthChanged} 处变了`);
  check('改一个定宽 u8 操作数后，重新扫描的指令偏移逐项相等', moved === 0,
    `${moved} 处移位（抽查 ${checked} 个操作数）`);
}

head('\n6) V6 对白等长');
{
  const pack = freshPack();
  const model = models.get(40);
  const segment = model.segments[0];
  const line = segment.lines.find((i) => i.op === 1);
  const segments = scripttext.textSegments(originalRom, pack, line);
  const seg = segments[0];
  const font = pack.font;
  // 找一个能替换成同宽字符的字（不改长度）
  const width = new Map();
  for (const [ch, code] of font.charToCode) {
    const w = code >= 0x80 ? 2 : 1;
    if (!width.has(w)) width.set(w, []);
    width.get(w).push(ch);
  }
  let sameLengthText = null;
  let longerText = null;
  for (const ch of seg.text) {
    if (ch === '↵' || ch === '　') continue;
    const code = font.charToCode.get(ch);
    if (code === undefined) continue;
    const w = code >= 0x80 ? 2 : 1;
    const pool = (width.get(w) || []).filter((c) => c !== ch);
    if (!pool.length) continue;
    sameLengthText = seg.text.replace(ch, pool[0]);
    longerText = seg.text + 'A';
    break;
  }
  check('这一段正文里有可替换的同宽字符', sameLengthText !== null,
    sameLengthText === null ? seg.text.slice(0, 30) : `样例：${sameLengthText.slice(0, 30)}`);

  const beforeOffsets = vm.scanScript(originalRom, model.eventsPtr - vm.ROM_BASE).map((i) => i.offset);
  const result = scripttext.commitSegment(pack, seg, sameLengthText);
  check('等长改写被接受', result.ok === true, JSON.stringify(result).slice(0, 120));
  check('等长改写后段字节数不变', seg.bytes.length === seg.capacity,
    `${seg.bytes.length} / ${seg.capacity}`);
  const afterOffsets = vm.scanScript(originalRom, model.eventsPtr - vm.ROM_BASE).map((i) => i.offset);
  check('等长改写后脚本的指令偏移逐项相等', beforeOffsets.join(',') === afterOffsets.join(','),
    `${beforeOffsets.length} 个偏移`);
  check('等长改写只留下一条补丁', pack.patches.length === 1, `${pack.patches.length} 条`);

  const patchesBefore = JSON.stringify(pack.patches);
  const bytesBefore = Array.from(seg.bytes).join(',');
  const bad = scripttext.commitSegment(pack, seg, longerText);
  check('多 1 字节的改写被拒绝', bad.ok === false && bad.reason === 'length',
    JSON.stringify(bad).slice(0, 120));
  check('被拒绝时补丁没有变', JSON.stringify(pack.patches) === patchesBefore,
    `补丁 ${pack.patches.length} 条`);
  check('被拒绝时正文字节没有变', Array.from(seg.bytes).join(',') === bytesBefore);
}

head('\n7) V7 写回通路没有新开');
{
  const pack = freshPack();
  const model = models.get(40);
  const block = model.blocks[0];
  const condition = block.conditions[0];
  const operand = condition.operands[0];
  check('条件操作数带 before_hex（写回校验的依据）', !!operand.before_hex && operand.before_hex.length === 2,
    `before_hex=${operand.before_hex}`);

  pack.setScriptOperand(operand, (operand.value + 1) & 0xff);
  const segment = model.segments[0];
  const line = segment.lines.find((i) => i.op === 1);
  const seg = scripttext.textSegments(originalRom, pack, line)[0];
  const pool = [...pack.font.charToCode.keys()];
  void pool;
  const ch = [...seg.text].find((c) => pack.font.charToCode.has(c));
  const alt = [...pack.font.charToCode.keys()].find(
    (c) => c !== ch && pack.font.charToCode.get(c) >= 0x80
      && pack.font.charToCode.get(ch) >= 0x80);
  const text = ch ? seg.text.replace(ch, alt) : seg.text;
  scripttext.commitSegment(pack, seg, text);

  check('改动之后 pack.patches 变多了', pack.patches.length >= 2, `${pack.patches.length} 条`);
  const unequal = pack.patches.filter(
    (p) => (p.before_hex || '').length !== (p.after_hex || '').length);
  check('每条补丁的 before_hex 与 after_hex 长度相等（等长写回）', unequal.length === 0,
    unequal.map((p) => p.label).join('、') || '全部相等');

  const methods = Object.getOwnPropertyNames(Object.getPrototypeOf(pack))
    .filter((n) => /^set/.test(n));
  const allowed = new Set(['setText', 'setScriptOperand', 'setBytesAt', 'setValue']);
  const extra = methods.filter((n) => !allowed.has(n));
  check('pack 上没有新增写回入口（只有 setText / setScriptOperand / setBytesAt / setValue）',
    extra.length === 0, extra.join('、') || methods.join('、'));

  // 构建时「原字节必须匹配」的校验要过
  const out = buildRom(pack, originalRom);
  check('构建没有报错', out.report.errors.length === 0, out.report.errors.join('；'));
}

head('\n8) V8 / V8b 降级不炸');
{
  const pack = freshPack();
  const ctx = ctxFor(pack, null);
  let node = null;
  let error = null;
  try {
    node = renderScriptsTab(ctx, 40);
  } catch (err) {
    error = err;
  }
  check('V8b：ctx.rom 为空时不抛异常', !error, error ? String(error.message) : '');
  check('V8b：返回的节点非空', !!node && node.children.length > 0,
    node ? `${node.children.length} 个子节点` : 'null');
  const tables = node ? node.descendants().filter((n) => n.tagName === 'TABLE') : [];
  check('V8b：根指针表照常渲染（不需要 ROM）', tables.length >= 1, `${tables.length} 张表`);
  const text = node ? node.textContent : '';
  check('V8b：四个剧本入口照常显示',
    ['战前剧情', '战后剧情', '战场事件逻辑', '战场事件表'].every((n) => text.includes(n)));
  check('V8b：before/after 的可改操作数表照常显示', text.includes('本关剧情脚本里可改的操作数'));
  const triggerArea = node ? byDataset(node, 'triggers', '1') : null;
  check('V8：触发块区存在', !!triggerArea);
  const triggerInputs = triggerArea
    ? triggerArea.descendants().filter((n) => n.tagName === 'INPUT') : [];
  check('V8：触发块区里没有输入框（触发块要 ROM 才画得出来）',
    triggerInputs.length === 0, `${triggerInputs.length} 个输入框`);
  check('V8：降级时给了一句说明', text.includes('未载入原版 ROM'),
    text.includes('未载入原版 ROM') ? '有' : '没有');
}

head('\n9) V9 界面文案不含字面 **');
{
  const pack = freshPack();
  const ctx = ctxFor(pack);
  const node = renderScriptsTab(ctx, 40);
  const text = node.textContent;
  check('「剧情触发」卡片的页面文本里没有字面 **', !text.includes('**'),
    text.includes('**') ? '还有星号' : '没有');

  const viewHost = new StubNode('div');
  const viewCtx = ctxFor(pack);
  viewCtx.state.view = { panel: { kind: 'script', id: 'script', params: { root: 'before', scene: 1 } } };
  renderScriptView(viewHost, viewCtx);
  check('剧情脚本查看器的页面文本里没有字面 **', !viewHost.textContent.includes('**'),
    viewHost.textContent.includes('**') ? '还有星号' : '没有');

  const sectionsSource = readFileSync(join(editorRoot, 'js', 'modules', 'battle-sections.js'), 'utf8');
  const scriptviewSource = readFileSync(join(editorRoot, 'js', 'modules', 'scriptview.js'), 'utf8');
  check('battle-sections.js 里原来那句字面 ** 已经清掉',
    !sectionsSource.includes('因此**在「角色出生点」'));
  check('scriptview.js 里那 4 处字面 ** 已经清掉',
    !scriptviewSource.includes('对白正文**可以就地改**')
    && !scriptviewSource.includes('但必须**等长**'));
}

head('\n10) V10 两处 KNOWN_OPERANDS 一致');
{
  const pythonSource = readFileSync(join(repoRoot, 'tools', 'import_story_script.py'), 'utf8');
  const tableText = pythonSource.slice(
    pythonSource.indexOf('KNOWN_OPERANDS: dict'),
    pythonSource.indexOf('TEXT_OPCODES ='));
  const py = new Map();
  const opRe = /0x([0-9A-Fa-f]{2}):\s*\{([^}]*)\}/g;
  let match;
  while ((match = opRe.exec(tableText))) {
    const fields = new Map();
    const fieldRe = /"(\w+)":\s*\((\d+),\s*(\d+)\)/g;
    let field;
    while ((field = fieldRe.exec(match[2]))) {
      fields.set(field[1], [Number(field[2]), Number(field[3])]);
    }
    // 键是**十六进制**字面量 —— 必须按 16 进制解析（Number('0A') 是 NaN）。
    py.set(parseInt(match[1], 16), fields);
  }
  check('Python 侧抽出 23 个操作码', py.size === 23, `${py.size} 个`);
  const js = new Map(Object.entries(vm.KNOWN_OPERANDS).map(([op, spec]) =>
    [Number(op), new Map(Object.entries(spec).map(([name, v]) => [name, [v[0], v[1]]]))]));
  check('JS 侧抽出 23 个操作码', js.size === 23, `${js.size} 个`);
  const diffs = [];
  for (const [op, fields] of py) {
    const other = js.get(op);
    if (!other) { diffs.push(`0x${op.toString(16)} JS 侧没有`); continue; }
    for (const [name, spec] of fields) {
      const mine = other.get(name);
      if (!mine) { diffs.push(`0x${op.toString(16)} 的 ${name} JS 侧没有`); continue; }
      if (mine[0] !== spec[0] || mine[1] !== spec[1]) {
        diffs.push(`0x${op.toString(16)} 的 ${name} 偏移/宽度不同`);
      }
    }
    for (const name of other.keys()) {
      if (!fields.has(name)) diffs.push(`0x${op.toString(16)} 的 ${name} Python 侧没有`);
    }
  }
  for (const op of js.keys()) if (!py.has(op)) diffs.push(`0x${op.toString(16)} Python 侧没有`);
  check('两边的操作码、字段名、偏移与宽度逐项相等', diffs.length === 0,
    diffs.slice(0, 5).join('；') || '逐项相等');
}

head('\n11) V11 角标不隐形');
{
  const pack = freshPack();
  const host = new StubNode('div');
  const ctx = ctxFor(pack);
  renderBattleMap(host, ctx, 40, 0);

  const card = byClass(host, 'editor-card').find((c) => {
    const head = c.children.find((n) => String(n.className || '').includes('editor-card-head'));
    const title = head ? head.children.find((n) => String(n.className || '').includes('editor-card-title')) : null;
    return title && String(title.textContent || '').includes('剧情触发');
  });
  check('战场地图视图里有「剧情触发」那张卡片', !!card);
  const badgeOf = () => {
    const head = card.children.find((n) => String(n.className || '').includes('editor-card-head'));
    const badge = head ? head.children.find((n) => String(n.className || '').includes('card-badge')) : null;
    return badge ? String(badge.textContent || '') : '';
  };
  const start = badgeOf();
  check('一开始没有角标', start === '', `角标「${start}」`);

  // 改一段对白
  const model = models.get(40);
  const seg = scripttext.textSegments(originalRom, pack, model.segments[0].lines[0])[0];
  const ch = [...seg.text].find((c) => pack.font.charToCode.has(c));
  const alt = [...pack.font.charToCode.keys()].find(
    (c) => c !== ch && pack.font.charToCode.get(c) >= 0x80 && pack.font.charToCode.get(ch) >= 0x80);
  scripttext.commitSegment(pack, seg, seg.text.replace(ch, alt));
  const afterText = badgeOf();
  check('改一段对白后角标 +1', afterText === '1', `角标「${afterText}」`);

  // 改一个条件操作数
  const condition = model.blocks[0].conditions[0];
  const operand = condition.operands[0];
  pack.setScriptOperand(operand, (operand.value + 1) & 0xff);
  const afterOperand = badgeOf();
  check('再改一个条件操作数后角标 +1', afterOperand === '2', `角标「${afterOperand}」`);

  // 撤销要回落
  pack.undo();
  const afterUndo1 = badgeOf();
  check('撤销一次后角标回落', afterUndo1 === '1', `角标「${afterUndo1}」`);
  pack.undo();
  const afterUndo2 = badgeOf();
  check('撤销两次后角标回到原样', afterUndo2 === '', `角标「${afterUndo2}」`);

  // 口径：本关触发块里的改动
  check('角标口径：只算本关 logic / events 剧本范围内的补丁',
    bt.sceneTriggerChangeCount(pack, originalRom, 40) === 0,
    `${bt.sceneTriggerChangeCount(pack, originalRom, 40)} 处`);
}

head('\n12) V12 人话摘要不许编');
{
  const notes = readdirSync(notesRoot)
    .filter((f) => f.endsWith('.md'))
    .map((f) => readFileSync(join(notesRoot, f), 'utf8'))
    .join('\n');
  // 摘要里出现的**有出处的术语**：每一个都要能在 notes/ 里找到同名依据。
  const terms = ['回合计数', '角色', '战斗标志', '子配置', '复合条件', '比较器', '在场'];
  const missing = terms.filter((t) => !notes.includes(t));
  check('摘要里用到的术语都能在 notes/ 里找到同名依据', missing.length === 0,
    missing.join('、') || terms.join('、'));

  // 反向：没证实的名字不许出现
  const blacklist = ['剩余体力', 'HP', '敌我阵营', '生命值', '经验值', '攻击力'];
  const summaries = [];
  for (const scene of SCENES) {
    for (const block of models.get(scene).blocks) {
      for (const condition of block.conditions) {
        summaries.push(condition.summary);
        summaries.push(condition.detail);
      }
    }
  }
  const hits = blacklist.filter((w) => summaries.some((s) => s.includes(w)));
  check('摘要里没有为 0x35 / 0x36 / 0x0202680E 编造的名字', hits.length === 0,
    hits.join('、') || `抽查 ${summaries.length} 条摘要`);

  // 「回合数」不是没有争议的词 —— 用了就必须标出争议。
  // 争议标注写在条件表下面的说明里（界面上看得见的地方）。
  const cardText = renderScriptsTab(ctxFor(freshPack()), 40).textContent;
  const usesRound = summaries.some((s) => s.includes('回合计数'));
  const marksDispute = cardText.includes('战斗阶段 / 子阶段')
    && cardText.includes('两种说法没对上过');
  check('「回合计数」这个有争议的名字旁边标出了另一种说法', usesRound && marksDispute,
    marksDispute ? '争议标注在条件说明里' : '没有标出争议');
  const unnamed = summaries.filter((s) => s.includes('还没给它起名字') || s.includes('未命名'));
  check('没定名的字节照实说「还没给它起名字 / 未命名」', unnamed.length > 0,
    `${unnamed.length} 条`);
}

head('\n13) M3 补的三类界面情形');
{
  // 13a 无条件触发块（33 个）
  let unconditional = 0;
  let withText = 0;
  for (const scene of SCENES) {
    for (const block of models.get(scene).blocks) {
      if (block.conditions.length) continue;
      unconditional += 1;
      if (block.summary.includes('无条件（一直成立）')) withText += 1;
    }
  }
  check('407 个触发块里有 33 个没有任何条件', unconditional === 33, `${unconditional} 个`);
  check('无条件的那一档写的是「无条件（一直成立）」', withText === unconditional,
    `${withText}/${unconditional}`);

  // 13b 组内跳转（19 条）
  let inGroup = 0;
  let inGroupText = 0;
  for (const scene of SCENES) {
    for (const block of models.get(scene).blocks) {
      for (const condition of block.conditions) {
        if (condition.target.kind !== 'in-group') continue;
        inGroup += 1;
        if (bt.targetText(condition.target, block).includes('本组')) inGroupText += 1;
      }
    }
  }
  check('19 条条件跳到本组内部', inGroup === 19, `${inGroup} 条`);
  check('组内跳转写的是「本组」而不是「本组之外」', inGroupText === inGroup,
    `${inGroupText}/${inGroup}`);

  // 13c 目标是某条 0x33（本组的 3 条 + 后面某一组的 5 条）
  let toPush = 0;
  let toPushText = 0;
  for (const scene of SCENES) {
    for (const block of models.get(scene).blocks) {
      for (const condition of block.conditions) {
        if (!['self-push', 'later-push'].includes(condition.target.kind)) continue;
        toPush += 1;
        if (bt.targetText(condition.target, block).includes('压栈')) toPushText += 1;
      }
    }
  }
  check('8 条条件跳到某条 0x33（3 条本组的 + 5 条后面某一组的）', toPush === 8, `${toPush} 条`);
  check('跳到 0x33 的写清楚了是「压栈」', toPushText === toPush, `${toPushText}/${toPush}`);
}

head('\n14) M1 极性：列头与 0x35 的两句摘要');
{
  const pack = freshPack();
  const node = renderScriptsTab(ctxFor(pack), 40);
  const text = node.textContent;
  check('条件表的列头是「命中时跳到」', text.includes('命中时跳到'), '');
  check('界面上没有「不满足时」这个写反的列头', !text.includes('不满足时'), '');

  const model = models.get(40);
  const has35 = SCENES.some((s) => models.get(s).blocks.some(
    (b) => b.conditions.some((c) => c.op === 53)));
  check('数据里确实有 0x35 复合条件', has35);
  const detail53 = bt.conditionDetail(53, { expect: 0, param_b: 0, param_c: 1, param_d: 2 });
  check('0x35 的摘要是两句：成立时才继续；不成立就跳过本组',
    detail53.includes('成立时才继续') && detail53.includes('不成立就跳过本组'),
    detail53);
  check('0x35 的摘要没有编造三个参数的名字',
    !/剩余体力|生命|体力值/.test(detail53), detail53.slice(0, 40));
  const polarities = new Set();
  for (const scene of SCENES) {
    for (const block of models.get(scene).blocks) {
      for (const condition of block.conditions) polarities.add(condition.polarity);
    }
  }
  check('条件指令的极性分两种（0x35 与其它相反）',
    polarities.has('成立才跳') && polarities.has('不成立才跳'),
    [...polarities].join('、'));
}

head('\n15) P1-6 / P2-14 界面口径');
{
  const pack = freshPack();
  const node = renderScriptsTab(ctxFor(pack), 32);
  const text = node.textContent;
  check('场景 32..38：logic 与 events 是同一段字节这件事写出来了',
    text.includes('同一段字节'), '');
  check('摘要数字没有重复计（本关 4 处触发 / 事件链 3 段）',
    text.includes('本关共 4 处触发') && text.includes('事件链 3 段'),
    (text.match(/本关共 \d+ 处触发[^\n]{0,20}/) || [''])[0]);
  const text40 = renderScriptsTab(ctxFor(pack), 40).textContent;
  check('写了「本关的三个战斗变体共用同一份剧情」',
    text40.includes('三个战斗变体共用同一份剧情'), '');
  check('「战斗中触发」与「战前 / 战后过场」在措辞上分开',
    text40.includes('战斗中触发') && text40.includes('战前 / 战后过场'), '');
}

head('\n16) 布局：真浏览器复核查出来的两条（别再犯）');
{
  // 这两条是**在真浏览器里看像素**才发现的 —— 无头门禁断不了布局。
  // 2026-10-22 的真浏览器复核记录见 notes/battle-story-triggers-implementation-20261022.md §7。
  const battleCss = readFileSync(join(editorRoot, 'css', 'battle-map.css'), 'utf8');
  const baseCss = readFileSync(join(editorRoot, 'styles.css'), 'utf8');

  // 16a `.table-wrap` 的 `flex: 1 1 0` 是给**行向** flex 容器控制**宽度**用的。
  // `.trigger-body` 是**列向** flex 容器，flex-basis 落到高度上，
  // 加上 `.table-wrap` 自带 `overflow: auto`（自动最小尺寸归零），
  // 条件表与对白表会被压成 0 高 —— 整张表只剩一条横线。
  check('styles.css 里 .table-wrap 确实是 flex: 1 1 0（所以必须在 .trigger-body 里改回来）',
    /\.table-wrap\s*\{[^}]*flex:\s*1 1 0/.test(baseCss), '');
  check('.trigger-body 里的 .table-wrap 把 flex 改回了 0 0 auto（高度按内容算）',
    /\.trigger-body\s*>\s*\.table-wrap\s*\{[^}]*flex:\s*0 0 auto/.test(battleCss), '');

  // 16b 条件表最后一列是**人话说明**，全局 `table.grid td` 是 nowrap，
  // 长说明会被顶出容器、只能横向滚动才看得到。
  check('全局 table.grid td 确实是 nowrap（所以说明列要单独放开）',
    /table\.grid td\s*\{[^}]*white-space:\s*nowrap/.test(baseCss), '');
  check('条件表最后一列放开了换行',
    /\.trigger-body table\.cond-table td:last-child\s*\{[^}]*white-space:\s*normal/.test(battleCss), '');
  const sectionsSource = readFileSync(join(editorRoot, 'js', 'modules', 'battle-sections.js'), 'utf8');
  check('条件表确实带了 cond-table 这个类（否则上面的 CSS 选不中）',
    sectionsSource.includes("class: 'cond-table'"), '');
  const commonSource = readFileSync(join(editorRoot, 'js', 'modules', 'common.js'), 'utf8');
  check('共享的 summaryTable 支持可选的表类名（向后兼容）',
    commonSource.includes('rows.class'), '');

  // 16c 窄栏（420px）里条件表有四列，输入框会被挤到点不进去。
  check('触发块里的输入框守住了最小宽度',
    /\.trigger-body \.num-input\s*\{[^}]*min-width:\s*\d+px/.test(battleCss)
    && /\.trigger-body \.text-input-inline\s*\{[^}]*min-width:\s*\d+px/.test(battleCss), '');
}

const summary = failures === 0
  ? `全部通过（${lines.filter((l) => l.includes('[PASS]')).length} 条断言）`
  : `${failures} 项失败`;
lines.push('');
lines.push(summary);
writeFileSync(
  join(repoRoot, 'build', 'battle-story-trigger-verify.txt'),
  lines.join('\n') + '\n',
  'utf8');
console.log('');
console.log(summary);
process.exit(failures === 0 ? 0 : 1);
