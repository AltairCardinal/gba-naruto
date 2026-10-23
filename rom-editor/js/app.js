// Editor shell: boot, routing, global state, build & export.
//
// The editor is a pure client-side app.  It needs two things to work:
//   * the content pack  (content/pack.json — the editor's initial data)
//   * the base ROM      (../rom/base.gba — the bytes everything is written into)
// Both are fetched relative to this page, so serving the repository root is
// enough:  python -m http.server 8000   →   http://localhost:8000/rom-editor/
//
// 载入 ROM 是**编辑器的前置操作**（notes/specs/rom-gate-20261023.md）：
// 内容包装好之后门禁就升起来，作者必须先给一份原版 ROM
// （内置的或本地的）才能继续 —— 门禁不可关，下面的内容也点不到。
// 载入状态条（loadbar）是**状态**显示（载入后显示 √ 与卸载按钮）；
// 门禁是**入口**（没载入时拦住不让往下走）。两者分工，不重复。

import { ContentPack } from './pack.js';
import { parsePackFromRom } from './parsepack.js';
import { buildRom } from './rom.js';
import { loadBundledRom } from './romsource.js';
import { openRomGate } from './romgate.js';
import { loadPackWithProgress, loadPackInFrame } from './loader.js';
import { ensureTextIndex } from './textindex.js';
import { parseHash as parseHashRaw, hashFor } from './routing.js';
import { setDefaultPack, disposeAllCards } from './cards.js';
import { renderLoadBar as renderLoadBarView, confirmOverwrite } from './loadbar.js';
import { el, clear, toast, modal, downloadBlob, readFile } from './ui.js';

export const MODULES = [
  { id: 'overview', label: '概览', emoji: '◎', render: renderOverview },
  { id: 'story', label: '剧情与对白', emoji: '❖', render: renderStory },
  { id: 'items', label: '道具', emoji: '◆', render: renderItems },
  { id: 'characters', label: '角色属性与技能', emoji: '✦', render: renderCharacters },
  { id: 'ninjutsu', label: '忍术', emoji: '✧', render: renderNinjutsu },
  { id: 'battle', label: '战斗', emoji: '⚔', render: renderBattle },
  { id: 'route', label: '剧情路线', emoji: '⇉', render: renderRoute },
  { id: 'audio', label: '音频', emoji: '♪', render: renderAudio },
  { id: 'assets', label: '素材与资源', emoji: '❒', render: renderAssets },
  { id: 'raw', label: '原始字节', emoji: '▤', render: renderRaw },
];

export const state = {
  pack: null,
  baseRom: null,
  rom: null,
  view: { module: 'overview', panel: null },
  status: '',
  /** ROM 的来源：null（未载入）/ 'bundled'（内置原版）/ 'file'（本地上传）。 */
  romSource: null,
  /** ROM 的显示信息（文件名、摘要）。 */
  romName: null,
  romSha: null,
  /** 内容包的来源：null / 'builtin'（编辑器自带）/ 'rom'（从 ROM 解析）/ 'file'（本地上传）。 */
  packSource: null,
};

const dom = {};

export function setStatus(text) {
  state.status = text;
  dom.statusText.textContent = text;
}

// --- 载入进度 ------------------------------------------------------------
function showProgress(phase) {
  const box = dom.loadProgress;
  const fill = dom.loadProgressFill;
  const text = dom.loadProgressText;
  if (!box) return;
  box.classList.remove('hidden', 'error');
  if (phase.error) {
    box.classList.add('error');
    fill.style.width = '100%';
    fill.classList.remove('indeterminate');
    text.textContent = phase.label;
    dom.romStatus.textContent = '内容包载入失败';
    dom.retryButton.classList.remove('hidden');
    return;
  }
  dom.retryButton.classList.add('hidden');
  if (phase.stage === 'download' && phase.percent === undefined) {
    fill.classList.add('indeterminate');
  } else {
    fill.classList.remove('indeterminate');
    fill.style.width = `${phase.percent ?? 100}%`;
  }
  text.textContent = phase.detail ? `${phase.label} ${phase.detail}` : phase.label;
  dom.romStatus.textContent = phase.label;
}

function hideProgress() {
  if (dom.loadProgress) dom.loadProgress.classList.add('hidden');
  if (dom.retryButton) dom.retryButton.classList.add('hidden');
}

export function markDirty() {
  const count = state.pack ? state.pack.changedCount() : 0;
  dom.dirtyBadge.textContent = String(count);
  dom.dirtyBadge.classList.toggle('hidden', count === 0);
  if (dom.undoButton) {
    const depth = state.pack ? state.pack.undoDepth : 0;
    dom.undoButton.classList.toggle('hidden', depth === 0);
    dom.undoButton.textContent = depth ? `撤销（${depth}）` : '撤销';
    dom.undoButton.title = depth
      ? `撤销上一步改动（Ctrl+Z），栈里还有 ${depth} 步`
      : '还没有可撤销的改动';
  }
  dom.buildButton.disabled = !state.rom;
  // 内容包有未导出的修改时，载入状态条上要出现高亮的【导出】按钮。
  renderLoadBar();
}

/** Undo the most recent change and refresh the view. */
export function undo() {
  if (!state.pack || !state.pack.canUndo) {
    toast('没有可撤销的改动', 'error');
    return;
  }
  if (!state.pack.undo()) {
    toast('撤销失败：这条记录已被重新导入覆盖', 'error');
    return;
  }
  markDirty();
  render();
  toast('已撤销上一步改动');
}

export function currentModule() {
  return MODULES.find((m) => m.id === state.view.module) || MODULES[0];
}

/**
 * Load the exhaustive ROM text index on demand.
 *
 * It lists every font-coded string in the cartridge, so it is far bigger
 * than the core pack; it is fetched only when a view asks for it.  The
 * loader itself lives in js/textindex.js so the battle view can use it too.
 */
export { ensureTextIndex };

/**
 * Route state in the URL hash, so a view can be linked to directly.
 * (The rules live in js/routing.js so they can be tested without a browser.)
 */
function parseHash() {
  return parseHashRaw(location.hash);
}

function syncHash() {
  const next = hashFor(state.view);
  if (location.hash !== next) location.hash = next;
}

/** Drill into one structure or text table. */
export function openPanel(kind, id, params) {
  if (kind === 'text' && id === 'rom_text_index' && !state.pack.textTable('rom_text_index')) {
    ensureTextIndex(state.pack, setStatus).then(() => {
      state.view.panel = { kind, id, params: params || {} };
      syncHash();
      render();
    });
    setStatus('正在载入全 ROM 文本索引…');
    return;
  }
  state.view.panel = { kind, id, params: params || {} };
  syncHash();
  render();
}

export function goModule(id) {
  state.view = { module: id, panel: null };
  syncHash();
  render();
}

export function onChange() {
  markDirty();
}

export function render() {
  const main = dom.main;
  // 旧视图马上要被丢掉 —— 它们的卡片堆要退订内容包的变更，
  // 不然每开一次视图就多一个订阅者，写回时都在更新一个已经不在页面上的角标。
  disposeAllCards();
  clear(main);
  const module = currentModule();
  for (const item of MODULES) {
    const node = dom.nav.querySelector(`[data-module="${item.id}"]`);
    if (node) node.classList.toggle('active', item.id === state.view.module);
  }
  module.render(main, context());
  const crumb = renderBreadcrumb();
  if (crumb) main.insertBefore(crumb, main.firstChild);
}

/**
 * The breadcrumb: where am I, and how do I get back up?
 *
 * Every level but the last one is clickable, so the way back is always
 * visible — before, "返回" was a lone button in the corner and the table
 * level could not be reached from the URL at all.
 */
function renderBreadcrumb() {
  const view = state.view;
  const crumbs = [{ label: '总览', go: () => goModule('overview') }];
  const mod = MODULES.find((m) => m.id === view.module);
  if (mod) crumbs.push({ label: mod.label, go: () => goModule(mod.id) });
  if (view.panel) {
    if (view.panel.kind === 'stage') {
      const p = view.panel.params || {};
      const suffix = view.module === 'battle' ? ` · 变体 ${p.variant || 0}` : '';
      crumbs.push({ label: `第 ${p.stage} 关${suffix}` });
    } else if (view.panel.kind === 'map') {
      // 战场地图：第 N 关 · 战场地图（规格 §3.1 / §7.2；变体在视图自己的工具条上）
      const p = view.panel.params || {};
      crumbs.push({ label: `第 ${p.stage} 关 · 战场地图` });
    } else {
      const table = view.panel.kind === 'structure'
        ? state.pack.structure(view.panel.id)
        : state.pack.textTable(view.panel.id);
      crumbs.push({ label: table ? (table.label || table.id) : view.panel.id });
      const recordId = view.panel.params && view.panel.params.recordId;
      if (recordId !== undefined && recordId !== null) {
        crumbs.push({ label: `记录 ${recordId}` });
      }
    }
  }
  if (crumbs.length < 2) return null;
  const bar = el('div', { class: 'breadcrumb' });
  crumbs.forEach((crumb, i) => {
    if (i) bar.appendChild(el('span', { class: 'crumb-sep', text: '/' }));
    const last = i === crumbs.length - 1;
    bar.appendChild(el('span', {
      class: 'crumb' + (last ? ' current' : ''),
      text: crumb.label,
      onclick: last ? null : crumb.go,
    }));
  });
  return bar;
}

function context() {
  return {
    pack: state.pack,    rom: state.rom,
    baseRom: state.baseRom,
    state,
    render,
    onChange,
    openPanel,
    goModule,
    setStatus,
    onJump,
    requestRom,
  };
}

/**
 * Jump to another table (possibly in another domain) and to a record.
 *
 * The pack knows the relations (「忍术 id 37 → 忍术名表第 37 条」), so the
 * author can follow a reference instead of hunting for the id by hand.
 */
export function onJump(target) {
  if (!target) return;
  if (target.module && target.module !== state.view.module) {
    state.view.module = target.module;
  }
  openPanel(target.kind, target.id, {
    recordId: target.recordId === null ? undefined : target.recordId,
    // 有些跳转带别的参数（例如「跳到原始字节的某个地址」）。
    ...(target.params || {}),
  });
  setStatus(`已跳到 ${target.label}` +
    (target.recordId === null || target.recordId === undefined ? '' : ` · 记录 ${target.recordId}`));
}

// --------------------------------------------------------------------------
// boot
// --------------------------------------------------------------------------
/**
 * Load the content pack.
 *
 * The pack comes with a progress bar, a timeout per source and an actionable
 * error message — a stalled response must never leave the UI frozen on
 * "正在载入内容包…".
 */
async function loadPack() {
  let data = null;
  try {
    data = await loadPackWithProgress(showProgress);
  } catch (err) {
    // 最后再试一次专用载入文档（有些环境里 iframe 的网络栈是独立的）
    const text = await loadPackInFrame();
    if (text) {
      try {
        data = JSON.parse(text);
        hideProgress();
      } catch (parseErr) {
        data = null;
      }
    }
    if (!data) {
      showProgress({ error: true, label: err.message });
      setStatus('内容包载入失败');
      throw err;
    }
  }
  if (data.format !== 'naruto-konoha-content-pack') {
    const err = new Error(`内容包格式不对: ${data.format}`);
    showProgress({ error: true, label: err.message });
    throw err;
  }
  hideProgress();
  const pack = ContentPack.fromJSON(data);
  // 页签要订阅内容包的变更（角标得在每次写入后跟上）。
  setDefaultPack(pack);
  return pack;
}

async function sha256Hex(bytes) {
  const digest = await crypto.subtle.digest('SHA-256', bytes);
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, '0')).join('');
}

function setRomStatus() {
  const parts = [];
  if (state.pack) {
    parts.push(`内容包 ${state.pack.structures.length} 结构 / ${state.pack.texts.length} 文本表`);
  }
  if (state.rom) {
    parts.push(`原版 ROM ${state.rom.length.toLocaleString()} 字节`);
  } else {
    parts.push('未载入原版 ROM');
  }
  dom.romStatus.textContent = parts.join(' · ');
}

// --------------------------------------------------------------------------
// 载入状态条（ROM 槽 / 内容包 槽）
// --------------------------------------------------------------------------
//
// 规则（用户定的）：
//   * **ROM 槽** —— 未载入时给**二选一**（内置原版 / 在本地浏览上传）；
//     载入后显示**绿底白 √**，并且**不再提供载入别的 ROM 的入口**：
//     要换 ROM 得先「导出修改后卸载 ROM」。
//   * **内容包槽** —— 未载入时给**二选一**（从 ROM 中解析 / 在本地浏览上传）；
//     载入后显示 **√** 并注明来源；有**未导出过的修改**时，
//     【导出】按钮**高亮**；点【载入】会先确认「改动会被覆盖」。

/** 内容包里有没有「没导出过的修改」。 */
function packHasUnexportedChanges() {
  return !!state.pack && state.pack.changedCount() > 0;
}

/** 重画载入状态条的两个槽位（画法在 `js/loadbar.js`，那里是纯函数，好测）。 */
function renderLoadBar() {
  renderLoadBarView(dom.slotRom, dom.slotPack, {
    rom: {
      loaded: !!state.rom,
      name: state.romName,
      size: state.rom ? state.rom.length : 0,
      sha: state.romSha,
    },
    pack: {
      loaded: !!state.pack,
      source: state.packSource,
      structures: state.pack ? state.pack.structures.length : 0,
      texts: state.pack ? state.pack.texts.length : 0,
      changed: packHasUnexportedChanges(),
    },
  }, {
    loadBundledRom: loadBundledRomAction,
    loadRomFile: () => { const input = document.getElementById('rom-file'); if (input) input.click(); },
    unloadRom: exportAndUnloadRom,
    parsePack: () => parsePackFromCurrentRom(),
    loadPack: reloadPackAction,
    loadPackFile: () => { const input = document.getElementById('pack-file'); if (input) input.click(); },
    exportPack,
  });
}

/**
 * 内容包有未导出的修改时，载入前先确认。
 *
 * 「否」是高亮按钮 —— 丢数据是这个操作的主要风险，
 * 所以**默认落点应该是「不覆盖」**。
 */
function confirmOverwriteChanges(onYes) {
  if (!packHasUnexportedChanges()) {
    onYes();
    return;
  }
  confirmOverwrite(onYes);
}

/**
 * 从当前载入的 ROM 解析出内容包。
 *
 * 内容包当**模板**（字段布局、记录偏移、文本表指针的位置都在里面），
 * **值**从 ROM 的字节重读。详见 `js/parsepack.js`。
 */
async function parsePackFromCurrentRom() {
  if (!state.rom) {
    toast('请先载入原版 ROM', 'error');
    return;
  }
  if (!state.pack) {
    toast('没有可用的内容包模板', 'error');
    return;
  }
  setStatus('正在从 ROM 解析内容包…');
  await new Promise((resolve) => setTimeout(resolve, 10));
  try {
    const { pack, report } = parsePackFromRom(state.pack, state.rom, {
      name: state.romName || 'base.gba',
      sha256: state.romSha || '',
    });
    const next = ContentPack.fromJSON(pack);
    setDefaultPack(next);
    state.pack = next;
    state.packSource = 'rom';
    setRomStatus();
    renderLoadBar();
    markDirty();
    render();
    setStatus('已从 ROM 解析出内容包');
    toast(`已从 ROM 解析出内容包：${report.records} 条记录 / ${report.texts} 张文本表`, 'ok');
  } catch (err) {
    toast(`从 ROM 解析内容包失败：${err.message}`, 'error');
  }
}

/** 内容包槽的【载入】：重新载入（先确认会覆盖什么）。 */
function reloadPackAction() {
  confirmOverwriteChanges(() => {
    if (state.rom && state.packSource === 'rom') {
      parsePackFromCurrentRom();
      return;
    }
    if (state.rom) {
      parsePackFromCurrentRom();
      return;
    }
    const input = document.getElementById('pack-file');
    if (input) input.click();
  });
}

/**
 * 导出修改后的 ROM，然后卸载这个 ROM。
 *
 * 卸载后才能载入别的 ROM —— 这是有意的：**一个内容包只对应一个基线 ROM**，
 * 拿改过的 ROM 当基线去构建会把内容包覆盖不到的地方回退掉。
 */
async function exportAndUnloadRom() {
  if (!state.rom) return;
  const changes = state.pack ? state.pack.changedCount() : 0;
  if (changes > 0) {
    const { bytes, report } = buildRom(state.pack, state.rom);
    if (report.errors.length) {
      showBuildReport(report, null);
      toast('构建失败 —— ROM 没有卸载', 'error');
      return;
    }
    downloadBlob(new Blob([bytes], { type: 'application/octet-stream' }),
      'naruto-konoha-mod.gba');
  }
  state.rom = null;
  state.baseRom = null;
  state.romSource = null;
  state.romName = null;
  state.romSha = null;
  setRomStatus();
  renderLoadBar();
  markDirty();
  render();
  setStatus('原版 ROM 已卸载');
  toast(changes > 0 ? '已导出修改后的 ROM，并卸载了原版 ROM' : '原版 ROM 已卸载', 'ok');
}

async function doBuild() {
  if (!state.rom) {
    // 没有 ROM 就先把门禁升起来 —— 这一步不能跳过。
    await requestRom('构建 ROM 需要原版 ROM 当基底：改动要写进这份 ROM 里。');
    if (!state.rom) return;
  }
  const button = dom.buildButton;
  button.disabled = true;
  setStatus('正在构建 ROM…');
  await new Promise((resolve) => setTimeout(resolve, 10));
  try {
    const { bytes, report } = buildRom(state.pack, state.rom);
    if (report.errors.length) {
      showBuildReport(report, null);
      toast(`构建失败：${report.errors.length} 处错误`, 'error');
      return;
    }
    showBuildReport(report, bytes);
  } catch (err) {
    toast(`构建异常：${err.message}`, 'error');
  } finally {
    button.disabled = false;
    setStatus('构建完成');
  }
}

function showBuildReport(report, bytes) {
  const body = el('div', {}, [
    el('div', { class: 'kv' }, [
      el('dt', { text: '结构' }), el('dd', { text: `${report.structures} 个 / 记录 ${report.records} 条` }),
      el('dt', { text: '改动记录' }), el('dd', { text: `${report.recordsChanged} 条` }),
      el('dt', { text: '文本表' }), el('dd', { text: `${report.texts} 个 / 改动 ${report.textsChanged} 个` }),
      el('dt', { text: '显式补丁' }), el('dd', { text: `${report.patches} 条` }),
      el('dt', { text: '文本搬迁' }),
      el('dd', { text: report.movedTexts && report.movedTexts.length
        ? report.movedTexts.map((m) => `${m.table}#${m.id} → 0x${m.to.toString(16).toUpperCase()}`).join('，')
        : '无' }),
      // 剧本搬迁要**摊开给人看**：对白变长时整个剧本被搬到了别处，
      // 作者得知道这件事（还有它的根表指针被改了）。
      el('dt', { text: '剧本搬迁' }),
      el('dd', { text: report.movedScripts && report.movedScripts.length
        ? report.movedScripts.map((m) => `${m.id}：0x${(m.from || 0).toString(16).toUpperCase()}`
          + ` → 0x${(m.to || 0).toString(16).toUpperCase()}`
          + `（${m.bytes} 字节 / 重基 ${m.rebased} 处 / 改指针 ${m.slots} 个）`).join('；')
        : '无' }),
      el('dt', { text: '重定位' }),
      el('dd', { text: report.freeRegionsUsed.length
        ? report.freeRegionsUsed.map((r) => `0x${r.offset.toString(16)}+${r.length}`).join(', ')
        : '无' }),
    ]),
    report.errors.length
      ? el('div', { class: 'pill pill-bad', text: `${report.errors.length} 处错误` })
      : el('div', { class: 'pill pill-ok', text: '无错误' }),
    // 警告以前完全不渲染，于是「原字节不匹配（已跳过）」「这段文字属于别处」
    // 这类信息对作者是不可见的 —— 现在摊开给人看。
    report.warnings && report.warnings.length
      ? el('div', { class: 'build-warnings' }, [
        el('div', { class: 'build-warn-title', text: `警告 ${report.warnings.length} 条` }),
        ...report.warnings.map((w) => el('div', { class: 'build-warn', text: w })),
      ])
      : null,
  ]);
  const actions = [];
  if (bytes) {
    actions.push({
      label: '下载 ROM',
      primary: true,
      onClick: () => {
        downloadBlob(new Blob([bytes], { type: 'application/octet-stream' }),
          'naruto-konoha-mod.gba');
      },
    });
  }
  actions.push({ label: '关闭', onClick: () => {} });
  modal('构建报告', body, actions);
}

function exportPack() {
  const data = state.pack.toJSON();
  data.generated = new Date().toISOString();
  const text = JSON.stringify(data, null, 1);
  downloadBlob(new Blob([text], { type: 'application/json' }), 'content-pack.json');
  // 导出过 = 这一版改动已经落到文件里了。
  state.packExported = true;
  renderLoadBar();
  toast('已导出内容包', 'ok');
}

async function importPackFile(file) {
  try {
    const text = await file.text();
    const data = JSON.parse(text);
    if (data.format !== 'naruto-konoha-content-pack') {
      toast('不是本编辑器的内容包', 'error');
      return;
    }
    state.pack = ContentPack.fromJSON(data);
    setDefaultPack(state.pack);
    state.packSource = 'file';
    markDirty();
    setRomStatus();
    renderLoadBar();
    render();
    toast('已导入内容包', 'ok');
  } catch (err) {
    toast(`导入失败：${err.message}`, 'error');
  }
}

async function loadRomFile(file) {
  try {
    const bytes = await readFile(file);
    await applyRom(bytes, 'file', file.name || 'base.gba');
    if (state.pack && state.pack.rom.sha256 && state.romSha
        && state.pack.rom.sha256 !== state.romSha) {
      toast('载入的 ROM 与内容包记录的基线不同 —— '
        + '拿它当构建基底会回退内容包没覆盖到的字节', 'error');
    } else {
      toast(`原版 ROM 已载入（${state.romName}）`, 'ok');
    }
  } catch (err) {
    toast(`读取失败：${err.message}`, 'error');
  }
}

// --------------------------------------------------------------------------
// module views
// --------------------------------------------------------------------------
function renderOverview(container, ctx) {
  const pack = ctx.pack;
  const structures = pack.structures;
  const texts = pack.texts;
  const totalRecords = structures.reduce((a, s) => a + s.entry_count, 0);
  const totalTexts = texts.reduce((a, t) => a + t.count, 0);
  const relocatable = texts.filter((t) => t.relocatable).length;

  container.appendChild(el('div', { class: 'panel-head' }, [
    el('div', {}, [
      el('h2', { text: '编辑器概览' }),
      el('div', { class: 'panel-sub' }, [
        el('span', { text: `内容包 v${pack.version}` }),
        el('span', { text: `ROM ${pack.rom.sha256.slice(0, 16)}…` }),
      ]),
    ]),
  ]));

  container.appendChild(el('div', { class: 'card-grid' }, [
    stat('结构表', structures.length, `${totalRecords.toLocaleString()} 条记录`),
    stat('文本表', texts.length, `${totalTexts.toLocaleString()} 条文本`),
    stat('可重定位文本表', relocatable, '其余只能等长改写'),
    stat('字形码', pack.font.codeToChar.size, 'ROM 自带字库'),
    stat('原版 ROM', ctx.rom ? ctx.rom.length.toLocaleString() : '未载入', '构建基底'),
    stat('已改动', pack.changedCount(), '条记录/文本'),
  ]));

  container.appendChild(el('div', { class: 'section' }, [
    el('h3', { text: '编辑流程' }),
    el('p', { class: 'section-note' }, [
      '编辑器载入的初始数据就是完整的内容包：它含有原版 ROM 中所有可编辑结构的',
      '全量内容。据此构建出的 ROM 与原版 ROM 逐字节相同（',
      el('code', { text: 'node rom-editor/tools/verify_pack.mjs' }),
      ' 会现场证明这一点）。改动任意字段后再次构建，输出即为改过的 ROM。',
    ]),
  ]));

  const byModule = new Map();
  for (const s of structures) {
    if (!byModule.has(s.module)) byModule.set(s.module, []);
    byModule.get(s.module).push(s);
  }
  const table = el('table', { class: 'grid' });
  table.appendChild(el('thead', {}, [el('tr', {}, [
    el('th', { text: '模块' }), el('th', { text: '结构' }),
    el('th', { text: 'ROM 地址' }), el('th', { text: '条数' }), el('th', { text: '说明' }),
  ])]));
  const body = el('tbody');
  for (const s of structures) {
    body.appendChild(el('tr', {
      onclick: () => ctx.openPanel('structure', s.id),
    }, [
      el('td', { text: s.module }),
      el('td', { text: s.label }),
      el('td', { text: '0x' + s.rom_offset.toString(16).toUpperCase() }),
      el('td', { class: 'col-num', text: String(s.entry_count) }),
      el('td', { class: 'text-cell', text: s.note || '' }),
    ]));
  }
  table.appendChild(body);
  container.appendChild(el('div', { class: 'section' }, [
    el('h3', { text: '全部结构（点击进入编辑）' }),
    el('div', { class: 'table-wrap' }, [table]),
  ]));

  const textTable = el('table', { class: 'grid' });
  textTable.appendChild(el('thead', {}, [el('tr', {}, [
    el('th', { text: '模块' }), el('th', { text: '文本表' }),
    el('th', { text: '指针表' }), el('th', { text: '条数' }), el('th', { text: '长度策略' }),
  ])]));
  const tbody = el('tbody');
  for (const t of texts) {
    tbody.appendChild(el('tr', {
      onclick: () => ctx.openPanel('text', t.id),
    }, [
      el('td', { text: t.module }),
      el('td', { text: t.label }),
      el('td', { text: t.pointer_table_offset
        ? '0x' + t.pointer_table_offset.toString(16).toUpperCase() : '—' }),
      el('td', { class: 'col-num', text: String(t.count) }),
      el('td', { text: lengthStrategyLabel(t) }),
    ]));
  }
  textTable.appendChild(tbody);
  container.appendChild(el('div', { class: 'section' }, [
    el('h3', { text: '全部文本表（点击进入编辑）' }),
    el('div', { class: 'table-wrap' }, [textTable]),
  ]));
}

function stat(label, value, hint) {
  return el('div', { class: 'stat' }, [
    el('div', { class: 'stat-label', text: label }),
    el('div', { class: 'stat-value', text: String(value) }),
    hint ? el('div', { class: 'stat-hint', text: hint }) : null,
  ]);
}

// module views are injected by js/modules/*.js
import { renderStory } from './modules/story.js';
import { lengthStrategyLabel } from './modules/common.js';
import { renderItems } from './modules/items.js';
import { renderCharacters } from './modules/characters.js';
import { renderNinjutsu } from './modules/ninjutsu.js';
import { renderBattle } from './modules/battle.js';
import { renderRoute } from './modules/route.js';
import { renderAudio } from './modules/audio.js';
import { renderAssets } from './modules/assets.js';
import { renderRaw } from './modules/raw.js';

// --------------------------------------------------------------------------
// wiring
// --------------------------------------------------------------------------
function build() {
  dom.nav = document.getElementById('sidenav');
  dom.main = document.getElementById('main');
  dom.statusText = document.getElementById('status-text');
  dom.statusHint = document.getElementById('status-hint');
  dom.romStatus = document.getElementById('rom-status');
  dom.loadProgress = document.getElementById('load-progress');
  dom.loadProgressFill = document.getElementById('load-progress-fill');
  dom.loadProgressText = document.getElementById('load-progress-text');
  dom.retryButton = document.getElementById('btn-retry');
  dom.dirtyBadge = document.getElementById('dirty-badge');
  dom.buildButton = document.getElementById('btn-build');
  dom.slotRom = document.getElementById('slot-rom');
  dom.slotPack = document.getElementById('slot-pack');
  dom.buildButton.disabled = true;

  const groups = [
    { title: '总览', ids: ['overview'] },
    { title: '内容编辑', ids: ['story', 'items', 'characters', 'ninjutsu', 'battle', 'route'] },
    { title: '其它已证实内容', ids: ['audio', 'assets'] },
    { title: '底层', ids: ['raw'] },
  ];
  for (const group of groups) {
    const box = el('div', { class: 'nav-group' }, [el('div', { class: 'nav-title', text: group.title })]);
    for (const id of group.ids) {
      const mod = MODULES.find((m) => m.id === id);
      box.appendChild(el('div', {
        class: 'nav-item',
        dataset: { module: id },
        onclick: () => goModule(id),
      }, [
        el('span', { class: 'nav-emoji', text: mod.emoji }),
        el('span', { text: mod.label }),
      ]));
    }
    dom.nav.appendChild(box);
  }

  document.getElementById('btn-build').addEventListener('click', doBuild);
  dom.undoButton = document.getElementById('btn-undo');
  if (dom.undoButton) {
    dom.undoButton.addEventListener('click', undo);
  }
  document.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && (e.key === 'z' || e.key === 'Z')) {
      e.preventDefault();
      undo();
    }
  });
  document.getElementById('btn-retry').addEventListener('click', () => {
    window.location.reload();
  });
  document.getElementById('pack-file').addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (file) importPackFile(file);
    e.target.value = '';
  });
  document.getElementById('rom-file').addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (file) loadRomFile(file);
    e.target.value = '';
  });

  window.addEventListener('hashchange', () => {
    const view = parseHash();
    state.view = view;
    render();
  });
}

async function boot() {
  const trace = (msg) => console.log('[editor] ' + msg);
  build();
  trace('shell ready');
  try {
    state.pack = await loadPack();
    state.packSource = 'builtin';
    trace(`pack loaded: ${state.pack.structures.length} structures`);
  } catch (err) {
    dom.romStatus.textContent = `内容包载入失败：${err.message}`;
    trace(`pack failed: ${err.message}`);
    return;
  }
  setRomStatus();
  renderLoadBar();
  markDirty();
  setStatus('内容包已载入（编辑器自带）—— 请载入原版 ROM');
  state.view = parseHash();
  render();
  trace('first render done');

  // 载入 ROM 是**前置操作**：门禁在这里升起来。
  // 门禁不可关 ⇒ 下面那一层（顶栏 / 载入条 / 侧边栏 / 内容）在载入成功之前点不到。
  await requestRom('原版 ROM 是编辑器的前置操作：构建 ROM、原始字节视图都要用它当基底。');
  trace('rom gate done');
}

/**
 * 取内置原版 ROM 的字节（**不写状态**）。
 *
 * 门禁与载入条都要用它。分开的原因是：门禁升起时顶栏的进度条在外壳里，
 * 被置了 inert ⇒ 看不见 ⇒ **错误必须显示在门禁窗口里**，
 * 所以取字节这一步要能把失败**抛出来**，而不是就地画一条进度条。
 */
async function fetchBundledRom(onProgress) {
  const rom = await loadBundledRom((msg) => {
    console.log('[editor] rom progress: ' + msg);
    if (onProgress) onProgress(msg);
  });
  if (!rom) {
    throw new Error(
      '内置 ROM 取不到 —— 浏览器可能限制了单页下载量。\n'
      + '请改用「上传本地 ROM」选一个 rom/base.gba（文件选择不走网络，一定能成功）。');
  }
  return rom;
}

/**
 * 收下一份 ROM：写状态 + 从 ROM 解析内容包 + 刷新界面。
 *
 * 载入条与门禁走的是同一条路 —— 区别只在**谁来调它**。
 */
async function applyRom(bytes, source, name) {
  state.baseRom = bytes;
  state.rom = bytes;
  state.romSource = source;
  state.romName = name;
  try {
    state.romSha = await sha256Hex(bytes);
  } catch (err) {
    state.romSha = null;
  }
  // 载入 ROM 之后**默认先从 ROM 解析出内容包**。
  await parsePackFromCurrentRom();
  setRomStatus();
  renderLoadBar();
  markDirty();
  setStatus('就绪');
  render();
}

/**
 * 升起载入 ROM 的门禁。
 *
 * 载入 ROM 是**前置操作**：需要 ROM 时窗口**不可关**（没有 ×、Esc 无效、
 * 点遮罩无效），下面的内容也点不到（应用外壳被置 inert）。
 * 载入条负责「已载入」之后的状态显示（√ / 卸载 / 换一份）。
 */
function requestRom(reason) {
  return openRomGate({
    reason,
    closable: false,
    loadBundled: (onProgress) => fetchBundledRom(onProgress),
    loadFile: async (file) => {
      const bytes = await readFile(file);
      await applyRom(bytes, 'file', file.name || 'base.gba');
      return bytes;
    },
  });
}

/** Fetch the bundled base ROM on demand. */
async function loadBundledRomAction() {
  if (state.rom) {
    toast('原版 ROM 已载入 —— 要换 ROM 请先「导出修改后卸载 ROM」', 'ok');
    return;
  }
  console.log('[editor] loading bundled rom…');
  showProgress({ stage: 'download', label: '正在载入内置原版 ROM…', percent: undefined });
  try {
    const rom = await fetchBundledRom((msg) => {
      showProgress({ stage: 'download', label: msg, percent: undefined });
    });
    await applyRom(rom, 'bundled', 'base.gba');
    toast('内置原版 ROM 已载入', 'ok');
  } catch (err) {
    showProgress({ error: true, label: `内置 ROM 载入失败：${err.message}` });
    setStatus('内置 ROM 载入失败');
  }
}

boot();
