// 战斗地图视图的无头验收脚本。
//
// 对应 notes/specs/battle-map-editor.md §8 的 V1–V12。
//
// 用法：node rom-editor/tools/verify_battle_map.mjs
//
// 断言分两半：
//   * 像素 / 坐标 / 尺寸 —— 走 js/maprender.js 的纯函数（画布在无头环境里没有
//     2D 上下文，所以像素断言不许碰 canvas）；
//   * 编辑 / 降级 / 深链 —— 走 js/modules/battle-map.js 的真实 DOM（自带最小
//     DOM 桩），素材文件用真实的 content/maps/maps.bin.gz（fetch 被桩住，
//     真的走了一遍 sha256 + 解压 + 解码）。
import { readFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

// --- 一个很小的 DOM --------------------------------------------------------
class StubNode {
  constructor(tag) {
    this.tagName = String(tag || '').toUpperCase();
    this.nodeType = 1;
    this.children = [];
    this.parentNode = null;
    this.attributes = {};
    this.dataset = {};
    this.style = {
      setProperty(name, value) { this[name] = value; },
    };
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

// --- fetch 桩：把真实的素材文件端上去 ---------------------------------------
const here = dirname(fileURLToPath(import.meta.url));
const repoRoot = join(here, '..', '..');
const editorRoot = join(repoRoot, 'rom-editor');
const packPath = join(editorRoot, 'content', 'pack.json');
const romPath = join(repoRoot, 'rom', 'base.gba');
const mapAssetPath = join(editorRoot, 'content', 'maps', 'maps.bin.gz');

/** 素材包与内容包要不要端上去（降级那一关要端不到）。 */
let servePack = true;

function fileResponse(path) {
  if (!existsSync(path)) return { ok: false, status: 404, arrayBuffer: async () => new ArrayBuffer(0) };
  const bytes = readFileSync(path);
  return {
    ok: true,
    status: 200,
    arrayBuffer: async () => bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength),
  };
}

globalThis.fetch = async (url) => {
  const href = String(url);
  if (href.includes('maps.bin.gz')) return fileResponse(mapAssetPath);
  if (href.includes('pack.min.json.gz')) {
    return servePack
      ? fileResponse(join(editorRoot, 'content', 'pack.min.json.gz'))
      : { ok: false, status: 404, arrayBuffer: async () => new ArrayBuffer(0) };
  }
  return { ok: false, status: 404, arrayBuffer: async () => new ArrayBuffer(0) };
};

const { ContentPack } = await import('../js/pack.js');
const { buildRom } = await import('../js/rom.js');
const maprender = await import('../js/maprender.js');
const { renderBattleMap } = await import('../js/modules/battle-map.js');
const { parseHash, hashFor } = await import('../js/routing.js');

let failures = 0;
function check(name, ok, detail = '') {
  if (!ok) failures += 1;
  console.log(`  [${ok ? 'PASS' : 'FAIL'}] ${name}${detail ? ' — ' + detail : ''}`);
}
function note(text) {
  console.log(`  [NOTE] ${text}`);
}

const packData = JSON.parse(readFileSync(packPath, 'utf8'));
const originalRom = new Uint8Array(readFileSync(romPath));

/** 一个干净的内容包（改动过的测试各自用新的，免得互相污染）。 */
function freshPack() {
  // 深拷贝：ContentPack.fromJSON 不复制记录，直接用 packData 会让上一段测试的
  // 改动漏到下一段去。
  const pack = ContentPack.fromJSON(JSON.parse(JSON.stringify(packData)));
  // 主代理在 pack.js 里补上 `this.map_assets = data.map_assets` 之后，
  // 这里就不用手动挂了 —— 现在先挂上，视图就不用再拉一遍内容包。
  pack.map_assets = packData.map_assets;
  return pack;
}

const ctxFor = (pack) => ({
  pack,
  rom: originalRom,
  baseRom: originalRom,
  state: { view: { panel: null } },
  onChange() {},
  openPanel() {},
  goModule() {},
  render() {},
  setStatus() {},
  onJump() {},
});

/** 渲染地图视图，等素材载入落定。 */
async function renderMapView(pack, stage, variant, render = renderBattleMap) {
  const host = new StubNode('div');
  const ctx = ctxFor(pack);
  render(host, ctx, stage, variant);
  const started = Date.now();
  while (Date.now() - started < 8000) {
    if (host.dataset && host.dataset.mapReady === '1') break;
    await new Promise((r) => setTimeout(r, 5));
  }
  return { host, ctx };
}

const byClass = (host, name) =>
  host.descendants().filter((n) => String(n.className || '').split(/\s+/).includes(name));
const tables = (host) => host.descendants().filter((n) => n.tagName === 'TABLE');

/**
 * 右侧面板的某张卡片（按卡片头的标题找）。
 *
 * 右侧是**一摞纵排的卡片**，全都同时在 DOM 里 ——
 * 所以不用「切页签」，直接按标题找那张卡片。
 */
function cardOf(host, title) {
  return byClass(host, 'editor-card').find((card) => {
    const head = card.children.find((c) => String(c.className || '').includes('editor-card-head'));
    const name = head ? head.children.find((c) => String(c.className || '').includes('editor-card-title')) : null;
    return name && String(name.textContent || '').includes(title);
  });
}

/** 某张卡片里的表格。 */
function cardTables(host, title) {
  const card = cardOf(host, title);
  return card ? card.descendants().filter((n) => n.tagName === 'TABLE') : [];
}

/** 某张卡片的文字。 */
function cardText(host, title) {
  const card = cardOf(host, title);
  return card ? card.textContent : '';
}

function rowsOf(table) {
  const body = (table.children || []).find((n) => n.tagName === 'TBODY');
  return body ? body.children.filter((n) => n.tagName === 'TR') : [];
}
function cellsOf(row) {
  return row.children.filter((n) => n.tagName === 'TD');
}
const clearToasts = () => { documentStub.body.children.splice(0); };
const toastText = () => documentStub.body.textContent;

// 独立实现的一份像素取样（不共用 maprender.js 的代码）—— 用来当对照。
const U16 = (b, p) => b[p] | (b[p + 1] << 8);
function independentTilePixel(gfx, entry, x, y) {
  if (entry & 1024) x = 7 - x;
  if (entry & 2048) y = 7 - y;
  const at = (entry & 1023) * 32 + y * 4 + (x >> 1);
  const c = (gfx[at] >> ((x & 1) * 4)) & 15;
  return c ? c + (entry >>> 12) * 16 : 0;
}
function independentColor(palette, index) {
  const v = U16(palette, index * 2);
  const conv = (c5) => (c5 << 3) | (c5 >> 2);
  return [conv(v & 31), conv((v >>> 5) & 31), conv((v >>> 10) & 31)];
}

console.log('1) V1 像素渲染正确');
{
  // 第 0 条地图不在素材包里（它没有对应的战斗关卡），所以从 ROM 现解。
  const asset = maprender.decodeMapAssetFromRom(originalRom, 0);
  const image = maprender.renderMapImage(asset);
  check('第 0 条地图是 736 × 512',
    asset.cellW === 23 && asset.cellH === 32 && image.width === 736 && image.height === 512,
    `${asset.cellW} × ${asset.cellH} 格 → ${image.width} × ${image.height} 像素`);
  check('像素缓冲长度 = 宽 × 高 × 4',
    image.pixels.length === 736 * 512 * 4,
    `${image.pixels.length} 字节`);

  // 独立算一遍第 0 个像素的颜色，与 assetPixelColor 对照
  let mismatches = 0;
  let compared = 0;
  for (const [px, py] of [[0, 0], [1, 0], [7, 7], [8, 8], [31, 15], [32, 16], [100, 40]]) {
    const tx = px >> 3;
    const ty = py >> 3;
    const meta = U16(asset.layer0, ((ty >> 1) * asset.cellW * 2 + (tx >> 1)) * 2);
    const entry = U16(asset.metatiles, meta * 8 + ((ty & 1) * 2 + (tx & 1)) * 2);
    const index = independentTilePixel(asset.gfx, entry, px & 7, py & 7);
    const expected = index ? independentColor(asset.palette, index) : [0, 0, 0, 0];
    const got = maprender.assetPixelColor(asset, px, py);
    compared += 1;
    const same = expected[3] === 0
      ? got[3] === 0
      : expected.every((c, i) => Math.abs(c - got[i]) <= 1);
    if (!same) {
      mismatches += 1;
      console.log(`        (${px}, ${py}) 期望 ${expected}，实际 ${got}`);
    }
  }
  check('取样点颜色与独立实现一致', mismatches === 0, `${compared} 个取样点，${mismatches} 处不同`);

  // 素材包里的图与从 ROM 现解的图必须一模一样
  const packed = readFileSync(mapAssetPath);
  const { gunzipSync } = await import('node:zlib');
  const raw = new Uint8Array(gunzipSync(packed));
  maprender.setMapAssetIndex(packData.map_assets);
  const shipped = maprender.decodeMapAsset(raw, 40);
  const fromRom = maprender.decodeMapAssetFromRom(originalRom, 40);
  const shippedImage = maprender.renderMapImage(shipped);
  const romImage = maprender.renderMapImage(fromRom);
  let same = shippedImage.width === romImage.width && shippedImage.height === romImage.height;
  for (let i = 0; same && i < shippedImage.pixels.length; i++) {
    if (shippedImage.pixels[i] !== romImage.pixels[i]) same = false;
  }
  check('素材包里的第 40 关与从 ROM 现解的逐像素相同', same,
    `${shippedImage.width} × ${shippedImage.height}`);
}

console.log('\n2) V2 坐标换算是 32 × 16');
{
  const { cellFromPixel, pixelFromCell, cellRect } = maprender;
  const cases = [
    [[0, 0], { x: 0, y: 0 }],
    [[31, 15], { x: 0, y: 0 }],
    [[32, 0], { x: 1, y: 0 }],
    [[31, 16], { x: 0, y: 1 }],
    [[32, 16], { x: 1, y: 1 }],
  ];
  for (const [[px, py], want] of cases) {
    const got = cellFromPixel(px, py, 9, 22);
    check(`cellFromPixel(${px}, ${py}) = (${want.x}, ${want.y})`,
      !!got && got.x === want.x && got.y === want.y, got ? JSON.stringify(got) : 'null');
  }
  check('越界返回 null', cellFromPixel(32 * 9, 0, 9, 22) === null);
  check('pixelFromCell(3, 5) = (96, 80)',
    JSON.stringify(pixelFromCell(3, 5)) === JSON.stringify({ px: 96, py: 80 }));
  check('cellRect(3, 5) = {x:96, y:80, w:32, h:16}',
    JSON.stringify(cellRect(3, 5)) === JSON.stringify({ x: 96, y: 80, w: 32, h: 16 }));
}

console.log('\n3) V3 命中测试带缩放');
{
  const cellW = 9;
  const mapWidth = cellW * 32;
  const rect = { left: 0, top: 0, width: mapWidth * 2, height: 22 * 16 * 2 };
  const cell = maprender.cellFromClientPoint(64, 32, rect, cellW, 22);
  check('显示宽 = 图宽 × 2 时，画布 (64, 32) 落在格 (1, 1)',
    !!cell && cell.x === 1 && cell.y === 1, cell ? JSON.stringify(cell) : 'null');
  const plain = maprender.cellFromClientPoint(64, 32,
    { left: 0, top: 0, width: mapWidth, height: 22 * 16 }, cellW, 22);
  check('不缩放时同一处落在格 (2, 2)',
    !!plain && plain.x === 2 && plain.y === 2, plain ? JSON.stringify(plain) : 'null');
  check('画布之外返回 null',
    maprender.cellFromClientPoint(mapWidth * 2 + 10, 0, rect, cellW, 22) === null);
}

console.log('\n4) V4 格数与地图表一致');
{
  const table = packData.structures.find((s) => s.id === 'map_table');
  const maps = packData.map_assets.maps;
  const ids = Object.keys(maps);
  let bad = [];
  for (const id of ids) {
    const meta = maps[id];
    const record = table.records.find((r) => r.id === Number(id));
    if (!record) { bad.push(`${id}: 地图表里没有`); continue; }
    const cellW = record.values.raw_width >> 2;
    const cellH = record.values.raw_height >> 1;
    if (meta.cell_w !== cellW || meta.cell_h !== cellH) {
      bad.push(`${id}: ${meta.cell_w}×${meta.cell_h} ≠ ${cellW}×${cellH}`);
    }
    if (meta.px_w !== meta.cell_w * 32 || meta.px_h !== meta.cell_h * 16) {
      bad.push(`${id}: 像素尺寸对不上`);
    }
  }
  check(`${ids.length} 张图的格数都等于地图表的 raw_width>>2 / raw_height>>1`,
    bad.length === 0, bad.slice(0, 3).join('；') || `例如第 ${ids[0]} 关 ${maps[ids[0]].cell_w} × ${maps[ids[0]].cell_h} 格`);
  check('素材段里的图数与内容包一致', ids.length === Object.keys(maps).length, `${ids.length} 张`);
}

console.log('\n5) V5 写回只动该动的字节');
{
  const pack = freshPack();
  const { host } = await renderMapView(pack, 40, 0);
  const objects = pack.structure('battle_map_objects');
  const objectBase = 0x5461c4 + 40 * 0x1aac + 0 * 0x8e4 + 0x8a4;
  const record = objects.records.find((r) => r.rom_offset === objectBase);
  const before = { ...record.values };

  // 从视图里改 X（走的是真正的那条路：数字框 → 越界检查 → pack.setValue）
  const objectTable = cardTables(host, '战场物件')[0];
  const row = rowsOf(objectTable)[0];
  const xInput = cellsOf(row)[3].descendants().find((n) => n.tagName === 'INPUT');
  check('物件第 1 槽的 X 是可编辑输入框', !!xInput, xInput ? `X=${xInput.value}` : '没有输入框');
  xInput.listeners.change[0]({ target: { value: '7' } });
  check('写回了 x = 7', record.values.x === 7, `x = ${record.values.x}`);

  const out = buildRom(pack, originalRom);
  check('构建无错误', out.report.errors.length === 0, out.report.errors.join('；'));
  const diffs = [];
  const limit = Math.min(out.bytes.length, originalRom.length);
  for (let i = 0; i < limit; i++) {
    if (out.bytes[i] !== originalRom[i]) diffs.push(i);
  }
  check('整份 ROM 只有 1 个字节与原版不同', diffs.length === 1,
    diffs.length ? `0x${diffs[0].toString(16).toUpperCase()}` : '没有差异');
  check('变的正是物件第 1 槽的 x 字节',
    diffs.length === 1 && diffs[0] === objectBase + 2 && out.bytes[objectBase + 2] === 7,
    diffs.length ? `偏移 0x${diffs[0].toString(16).toUpperCase()} = ${out.bytes[diffs[0]]}` : '没有差异');
  check('同槽的 type / target / y 三个字节与原版逐字节相同',
    out.bytes[objectBase] === originalRom[objectBase] &&
    out.bytes[objectBase + 1] === originalRom[objectBase + 1] &&
    out.bytes[objectBase + 3] === originalRom[objectBase + 3],
    `type ${out.bytes[objectBase]} / target ${out.bytes[objectBase + 1]} / y ${out.bytes[objectBase + 3]}`);
  check('原值记录还在（可以撤销）', before.x === 4, `原 x = ${before.x}`);

  // 改过的标记要标出来（以 pack 为准）
  const changedMarkers = byClass(host, 'changed');
  check('改过的物件在地图上被标出来', changedMarkers.length >= 1,
    `${changedMarkers.length} 个标记带 changed`);
  const objectMarkers = byClass(host, 'map-marker-object');
  check('空槽不画标记', objectMarkers.length === 1,
    `${objectMarkers.length} 个物件标记（16 个槽里只有 1 个非空）`);
}

console.log('\n6) V6 撤销与改动计数');
{
  const pack = freshPack();
  const objects = pack.structure('battle_map_objects');
  const objectBase = 0x5461c4 + 40 * 0x1aac + 0 * 0x8e4 + 0x8a4;
  const record = objects.records.find((r) => r.rom_offset === objectBase);
  const originalX = record.values.x;
  const originalY = record.values.y;
  const base = pack.changedCount();

  pack.setValue(objects, record, 'x', 7);
  check('改完 x 后改动数 +1', pack.changedCount() === base + 1, `${base} → ${pack.changedCount()}`);
  pack.undo();
  check('撤销后 x 恢复原值', record.values.x === originalX, `x = ${record.values.x}`);
  check('撤销后改动数回落', pack.changedCount() === base, `${pack.changedCount()}`);

  pack.setValue(objects, record, 'x', 6);
  pack.setValue(objects, record, 'y', 9);
  check('改了 x 与 y 两处', pack.changedCount() === base + 1, `${pack.changedCount()}`);
  pack.undo();
  pack.undo();
  check('撤两次后 x / y 都回到原值',
    record.values.x === originalX && record.values.y === originalY,
    `x = ${record.values.x}, y = ${record.values.y}`);
  check('撤两次后改动数回到原处', pack.changedCount() === base, `${pack.changedCount()}`);
}

console.log('\n7) V7 深链与面包屑');
{
  const parsed = parseHash('#battle/map/40/0');
  check('parseHash 认出战场地图',
    parsed.module === 'battle' && parsed.panel && parsed.panel.kind === 'map' &&
    parsed.panel.params.stage === 40 && parsed.panel.params.variant === 0,
    JSON.stringify(parsed.panel && parsed.panel.params));
  const hash = hashFor({ module: 'battle', panel: parsed.panel });
  check('hashFor 反向得到同一个字符串', hash === '#battle/map/40/0', hash);
  // 战斗域的「关卡视图」已经并进地图：两者是同一个界面，地址也就统一了。
  check('战斗域的关卡面板序列化后也是地图地址', hashFor({
    module: 'battle', panel: { kind: 'stage', params: { stage: 40, variant: 0 } },
  }) === hash, hashFor({
    module: 'battle', panel: { kind: 'stage', params: { stage: 40, variant: 0 } },
  }));
  check('剧情路线域的关卡面板还是它自己的地址', hashFor({
    module: 'route', panel: { kind: 'stage', params: { stage: 40, variant: 0 } },
  }) === '#route/stage/40/0', hashFor({
    module: 'route', panel: { kind: 'stage', params: { stage: 40, variant: 0 } },
  }));

  // 面包屑在 app.js 里（app.js 一导入就会启动整个应用，所以这里读源码取标签）
  const appSource = readFileSync(join(editorRoot, 'js', 'app.js'), 'utf8');
  const at = appSource.indexOf("kind === 'map'");
  const slice = at >= 0 ? appSource.slice(at, at + 600) : '';
  const match = slice.match(/label:\s*`([^`]*)`/);
  const label = match
    ? match[1].replace(/\$\{([^}]+)\}/g, (_, expr) => {
      const parts = expr.split('.');
      const field = (parts[1] || '').split('||')[0].trim();
      const fallback = (parts[1] || '').split('||')[1];
      const value = { stage: 40, variant: 0 }[field];
      if ((value === undefined || value === null) && fallback) return fallback.trim();
      return value === undefined ? '' : String(value);
    })
    : '';
  check('面包屑标签含「第 40 关」与「战场地图」',
    label.includes('第 40 关') && label.includes('战场地图'), `「${label}」`);
  check('面包屑标签就是规格 §3.1 的「第 40 关 · 战场地图」',
    label === '第 40 关 · 战场地图', `「${label}」`);
  if (label !== '第 40 关 · 战场地图') {
    note('app.js 的 map 分支要输出「第 N 关 · 战场地图」（规格 §3.1 / §7.2）。');
  }
}

console.log('\n8) V8 越界被拦');
{
  const pack = freshPack();
  const { host } = await renderMapView(pack, 40, 0);
  const objects = pack.structure('battle_map_objects');
  const objectBase = 0x5461c4 + 40 * 0x1aac + 0 * 0x8e4 + 0x8a4;
  const record = objects.records.find((r) => r.rom_offset === objectBase);
  const before = record.values.x;
  clearToasts();

  const objectTable = cardTables(host, '战场物件')[0];
  const xInput = cellsOf(rowsOf(objectTable)[0])[3].descendants().find((n) => n.tagName === 'INPUT');
  // 第 40 关的地图是 9 列 → 9 已经越界
  xInput.listeners.change[0]({ target: { value: '9' } });
  check('越界的 X 没有写回', record.values.x === before, `x = ${record.values.x}（原 ${before}）`);
  check('出现了「X 坐标越界」的提示',
    toastText().includes('X 坐标越界'), (toastText().match(/X 坐标越界[^。]*/) || ['没有'])[0]);
  check('输入框弹回原值', String(xInput.value) === String(before), `输入框 = ${xInput.value}`);
}

console.log('\n9) V9 阵营写的是 unit_flags bit0');
{
  const pack = freshPack();
  const { host } = await renderMapView(pack, 40, 0);
  const actors = pack.structure('battle_actors');
  const actorBase = 0x5461c4 + 40 * 0x1aac + 0 * 0x8e4 + 4;
  const record = actors.records.find((r) => r.rom_offset === actorBase);
  const sideBefore = record.values.side;
  const flagsBefore = record.values.unit_flags;

  const actorTable = cardTables(host, '角色出生点')[0];
  const row = rowsOf(actorTable)[0];
  const sideSelect = cellsOf(row)[2].descendants().find((n) => n.tagName === 'SELECT');
  check('阵营是一个下拉', !!sideSelect);
  sideSelect.listeners.change[0]({ target: { value: '敌方' } });
  check('unit_flags 的 bit0 变成 1', (record.values.unit_flags & 1) === 1,
    `unit_flags = 0x${(record.values.unit_flags >>> 0).toString(16)}（原 0x${(flagsBefore >>> 0).toString(16)}）`);
  check('+0x01 那个字节（side）没有被动', record.values.side === sideBefore,
    `side = ${record.values.side}（原 ${sideBefore}）`);
}

console.log('\n10) V10 素材缺失时降级但不瘫');
{
  servePack = false;
  // 换一个模块实例，免得用上前一次测试缓存下来的素材段
  const degraded = await import('../js/modules/battle-map.js?degraded=1');
  const pack = freshPack();
  pack.map_assets = null;
  const { host } = await renderMapView(pack, 40, 0, degraded.renderBattleMap);
  servePack = true;

  const text = host.textContent;
  check('出现了「未载入地图素材」提示条', text.includes('未载入地图素材'),
    (text.match(/未载入地图素材[^。]{0,30}/) || ['没有'])[0]);
  const fallback = byClass(host, 'map-grid-fallback')[0];
  check('有 .map-grid-fallback 元素', !!fallback);
  check('格线底图是显示着的', !!fallback && fallback.classList.contains('on'));
  const objectRows = rowsOf(cardTables(host, '战场物件')[0]);
  const actorRows = rowsOf(cardTables(host, '角色出生点')[0]);
  check('「战场物件」表仍有 16 行', objectRows.length === 16, `${objectRows.length} 行`);
  check('「角色出生点」表仍有 12 行', actorRows.length === 12, `${actorRows.length} 行`);

  // 素材齐的时候，格线底图是收起来的
  const ok = freshPack();
  const { host: host2 } = await renderMapView(ok, 40, 0);
  const fallback2 = byClass(host2, 'map-grid-fallback')[0];
  check('素材齐时不显示格线底图', !!fallback2 && !fallback2.classList.contains('on'));
  check('素材齐时状态行没有「底图缺失」', !host2.textContent.includes('底图缺失'),
    (host2.textContent.match(/底图缺失/) || ['没有'])[0]);
}

console.log('\n11) V11 胜负条件与剧情触发在页签里（不再有「去关卡视图改」）');
{
  const pack = freshPack();
  const { host } = await renderMapView(pack, 40, 0);
  // 右侧是**一摞纵排的卡片** —— 胜负条件就在同一页里，不用切。
  const text = host.textContent;
  for (const word of ['胜利', '失败', '回合上限']) {
    check(`同一页里能看到「${word}」`, text.includes(word),
      text.includes(word) ? '出现了' : '没有');
  }
  // 旧设计里这里有一个「战斗目标在关卡视图里 →」的链接；
  // 现在条件就在右侧的卡片里，那个链接不该再存在。
  const links = host.descendants().filter((n) => n.tagName === 'BUTTON')
    .filter((n) => n.textContent.includes('关卡视图'));
  check('没有「去关卡视图改战斗目标」的链接了', links.length === 0, `${links.length} 个`);

  // 条件在「胜负条件」那张卡片里，且能改。
  const rulesText = cardText(host, '胜负条件');
  check('「胜负条件」那张卡片里有胜利与失败',
    rulesText.includes('胜利') && rulesText.includes('失败'),
    (rulesText.match(/胜利|失败/g) || []).join(' '));
  check('「胜负条件」那张卡片里有回合上限', rulesText.includes('回合上限'));
}

console.log('\n12) V12 底图 id 可改');
{
  const pack = freshPack();
  const { host } = await renderMapView(pack, 40, 0);
  const table = pack.structure('map_table');
  const record = table.records.find((r) => r.id === 40);
  check('第 40 条的底图 id 原本是 1', record.values.background_id === 1,
    `background_id = ${record.values.background_id}`);

  const block = byClass(host, 'map-background')[0];
  const select = block ? block.descendants().find((n) => n.tagName === 'SELECT') : null;
  check('剧情底图有一个下拉', !!select);
  select.listeners.change[0]({ target: { value: '3' } });
  check('写回了 background_id = 3', record.values.background_id === 3,
    `background_id = ${record.values.background_id}`);

  const out = buildRom(pack, originalRom);
  check('构建无错误', out.report.errors.length === 0, out.report.errors.join('；'));
  const base = 0x53d910 + 40 * 32;
  check('底图 id 字节写对了', out.bytes[base + 28] === 3, `0x${(base + 28).toString(16).toUpperCase()} = ${out.bytes[base + 28]}`);
  let same = true;
  for (let i = 0; i < 32; i++) {
    if (i === 28) continue;
    if (out.bytes[base + i] !== originalRom[base + i]) same = false;
  }
  check('该记录其余 31 字节不变', same);
  const diffs = [];
  const limit = Math.min(out.bytes.length, originalRom.length);
  for (let i = 0; i < limit; i++) {
    if (out.bytes[i] !== originalRom[i]) diffs.push(i);
  }
  check('整份 ROM 只有 1 个字节与原版不同', diffs.length === 1,
    diffs.length ? `0x${diffs[0].toString(16).toUpperCase()}` : '没有差异');
}

console.log('\n13) 右侧页签收纳了这一关的全部配置');
{
  const pack = freshPack();
  const { host } = await renderMapView(pack, 40, 0);

  const cards = byClass(host, 'editor-card');
  const labels = cards.map((card) => {
    const head = card.children.find((c) => String(c.className || '').includes('editor-card-head'));
    const name = head ? head.children.find((c) => String(c.className || '').includes('editor-card-title')) : null;
    return name ? name.textContent : '';
  });
  check('右侧面板是一摞卡片', cards.length >= 5, `${cards.length} 张卡片：${labels.join(' / ')}`);
  for (const want of ['战场布置', '战场物件', '角色出生点', '胜负条件', '剧情触发']) {
    check(`卡片里有「${want}」`, labels.some((t) => t.includes(want)), labels.join(' / '));
  }

  // 胜负条件那张卡片：回合上限 + 4 胜 + 4 负 + 说明文字
  const rulesTable = cardTables(host, '胜负条件')[0];
  const rulesRows = rowsOf(rulesTable);
  check('「胜负条件」卡片里有条件表', !!rulesTable, rulesTable ? `${rulesRows.length} 行` : '没有表');
  check('条件表里带「说明文字」列',
    !!rulesTable && String(rulesTable.children[0].textContent).includes('说明文字'));
  check('胜利条件与失败条件都在',
    rulesRows.length > 0 && rulesRows.some((r) => r.textContent.includes('胜利'))
    && rulesRows.some((r) => r.textContent.includes('失败')),
    rulesRows.map((r) => r.textContent).join(' | ').slice(0, 160));
  check('「胜负条件」卡片能改类型（原生取值域下拉）',
    rulesRows.length > 0
    && cellsOf(rulesRows[0]).some((c) => c.descendants().some((n) => n.tagName === 'SELECT')));

  // 剧情触发那张卡片：四个剧本根指针
  const scriptTable = cardTables(host, '剧情触发')[0];
  const scriptRows = rowsOf(scriptTable);
  check('「剧情触发」卡片里有剧本表', !!scriptTable, scriptTable ? `${scriptRows.length} 行` : '没有表');
  check('四个剧本入口都在',
    scriptRows.length >= 4
    && ['战前剧情', '战后剧情', '战场事件逻辑', '战场事件表']
      .every((name) => scriptRows.some((r) => r.textContent.includes(name))),
    scriptRows.map((r) => r.textContent).join(' | ').slice(0, 200));

  // 战场布置那张卡片：地图尺寸 + 剧情底图 + 六个指针
  const setupText = cardText(host, '战场布置');
  check('「战场布置」卡片写着地图尺寸', setupText.includes('格') && setupText.includes('像素'));
  check('「战场布置」卡片列了剧情底图', setupText.includes('剧情底图'));
  check('「战场布置」卡片说了地形改不了', setupText.includes('通行值'));

  // 卡片**全都同时在 DOM 里** —— 不藏内容，往下滚就是全部。
  check('所有卡片的内容同时在 DOM 里（不藏内容）',
    cards.length >= 5 && byClass(host, 'card-stack').length === 1,
    `${cards.length} 张卡片 / ${byClass(host, 'card-stack').length} 个卡片堆`);
  check('每一张卡片的标题旁边都能挂改动数角标',
    cards.every((card) => {
      const head = card.children.find((c) => String(c.className || '').includes('editor-card-head'));
      return !!head;
    }));
}

console.log('\n14) 入口与页面文字');
{
  const { renderBattle } = await import('../js/modules/battle.js');
  const pack = freshPack();
  const ctx = ctxFor(pack);
  const home = new StubNode('div');
  ctx.state.view = { panel: null };
  renderBattle(home, ctx);
  const homeButtons = home.descendants().filter((n) => n.tagName === 'BUTTON');
  check('域首页有「打开战场地图」按钮',
    homeButtons.some((n) => n.textContent.includes('打开战场地图')),
    homeButtons.map((n) => n.textContent).join(' / '));
  check('域首页不再有「按关卡改」的长页面入口',
    !homeButtons.some((n) => n.textContent.includes('战场地图 →')));

  // 旧深链 `#battle/stage/40/0` 不能失效：它现在开的是地图。
  const oldHash = parseHash('#battle/stage/40/0');
  check('旧深链 #battle/stage/40/0 解析成地图面板',
    oldHash.module === 'battle' && oldHash.panel && oldHash.panel.kind === 'map'
    && oldHash.panel.params.stage === 40 && oldHash.panel.params.variant === 0,
    JSON.stringify(oldHash.panel));
  const newHash = hashFor({ module: 'battle', panel: { kind: 'map', id: 'map', params: { stage: 40, variant: 0 } } });
  check('地图面板的地址是 #battle/map/40/0', newHash === '#battle/map/40/0', newHash);
  check('旧地址重新序列化后指向地图',
    hashFor(oldHash) === '#battle/map/40/0', hashFor(oldHash));

  // 战斗域要把 stage 面板也分发到地图视图
  const dispatchPack = freshPack();
  const dispatchCtx = ctxFor(dispatchPack);
  dispatchCtx.state.view = { panel: { kind: 'stage', id: 'stage', params: { stage: 40, variant: 0 } } };
  const dispatchHost = new StubNode('div');
  renderBattle(dispatchHost, dispatchCtx);
  check('战斗域把 stage 面板也分发到地图视图',
    byClass(dispatchHost, 'map-scroll').length === 1,
    `${byClass(dispatchHost, 'map-scroll').length} 个画布区`);

  const map = freshPack();
  const { host } = await renderMapView(map, 40, 0);
  check('地图视图的页面文本里没有字面星号', !host.textContent.includes('**'),
    host.textContent.includes('**') ? '还有星号' : '没有');
  check('域首页的页面文本里没有字面星号', !home.textContent.includes('**'),
    home.textContent.includes('**') ? '还有星号' : '没有');

  // 战斗域要能把 map 面板分发到地图视图
  const dispatchPack2 = freshPack();
  const dispatchCtx2 = ctxFor(dispatchPack2);
  dispatchCtx2.state.view = { panel: { kind: 'map', id: 'map', params: { stage: 40, variant: 0 } } };
  const dispatchHost2 = new StubNode('div');
  renderBattle(dispatchHost2, dispatchCtx2);
  check('战斗域把 map 面板分发到地图视图',
    dispatchHost2.textContent.includes('战场地图') &&
    byClass(dispatchHost2, 'map-scroll').length === 1,
    `${byClass(dispatchHost2, 'map-scroll').length} 个画布区`);

  // 剧情底图：单列一块小面板，240×80，不叠在战场地图上
  const preview = byClass(host, 'map-bg-preview')[0];
  check('有一块 240×80 的剧情底图预览', !!preview && preview.attributes.width === '240' &&
    preview.attributes.height === '80');
  const background = maprender.renderBackgroundImage(originalRom, 1);
  let opaque = 0;
  if (background) {
    for (let i = 3; i < background.pixels.length; i += 4) {
      if (background.pixels[i]) opaque += 1;
    }
  }
  check('剧情底图能从 ROM 渲染出来（4bpp）',
    !!background && background.width === 240 && background.height === 80 && opaque > 0,
    background ? `${opaque} 个不透明像素` : '渲染不出来');
  check('剧情底图没有叠在战场地图上（它是独立的一块）',
    !!preview && preview.parentNode !== byClass(host, 'map-stage')[0]);
}

console.log(failures ? `\n${failures} 项未通过` : '\n全部通过');
process.exit(failures ? 1 : 0);
