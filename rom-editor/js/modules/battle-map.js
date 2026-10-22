// 战场地图视图：看得见的战场 + 在地图上就地布置。
//
// 依据 notes/specs/battle-map-editor.md（设计与事实都已钉死在规格里）：
//   §2.3  1 格 = 32 × 16 像素
//   §2.7  能改的只有 battle_actors / battle_map_objects / map_table.background_id
//   §2.8  剧情底图不是战场贴图，单列一块小面板
//   §2.11 阵营真正生效的是 unit_flags 的 bit0
//   §3    版面：面包屑 → 工具条 → 提示条 → 左画布 / 右面板 → 状态行
//   §4    编辑流：拖动标记、右侧表格、越界拦截
//   §6.4  素材缺失时降级成格线底图，编辑功能一条不少
//
// 写回只走 pack.setValue —— 不新开任何通路（§2.7）。

import { el, clear, toast, modal } from '../ui.js';
import { splitPane } from '../split.js';
import {
  sideCell, stageChangeCount, mapAssetNotice, operandChanged, openInTable, BATTLE_LAYOUT,
} from './common.js';
import { renderRulesTab, renderScriptsTab } from './battle-sections.js';
import { CardStack } from '../cards.js';
import { fetchMaybeGzip } from '../romsource.js';
import { editorUrl } from '../loader.js';
import {
  CELL_PX_W, CELL_PX_H,
  decodeMapAsset, renderMapImage, terrainAt,
  cellFromClientPoint, setMapAssetIndex, backgroundIds,
  renderBackgroundImage,
} from '../maprender.js';

/**
 * 通行值的显示名。
 *
 * 仓库没有官方的地形名表；这三个名字来自第三方编辑器
 * （third_party/konoha-workshop/editor/feature_ui.js:3-4），写回的仍是原始编号，
 * 而且通行值**不可编辑**（战斗加载器 0x08068FF0 根本不读那一块，见规格 §2.7）。
 */
const TERRAIN_NAMES = {
  0: '可通行地面',
  7: '障碍（不可通过）',
  15: '边界（不可通过）',
};
const TERRAIN_OTHER = '原有特殊地形';

/** 朝向枚举（0 上 / 1 右 / 2 下 / 3 左）。 */
const FACING_NAMES = ['上', '右', '下', '左'];

/**
 * 机关脚本的名字（第三方编辑器 features.js:26 里的硬编码表）。
 *
 * 本仓库**没有收录这张表**；这里只是把第三方名字显示出来，写回的仍是编号。
 */
const MECHANISM_NAMES = {
  1: '开门机关',
  2: '空箱 / 开门分支',
  3: '停止傀儡的机关',
  4: '开门机关（另一组）',
  5: '空箱 / 开门分支（另一组）',
  6: '停止傀儡的机关（另一组）',
  7: '密书',
  8: '空箱 / 密书分支',
  9: '甘薯（收集计数）',
  10: '发现奖励（强化剂剧情）',
  11: '空事件',
  12: '宝箱教学',
  13: '认识卡教学',
};

/** 缩放档（整数档，不缩放就不换挡，避免糊）。 */
const ZOOM_STEPS = [1, 2, 3, 4];

// ---------------------------------------------------------------------------
// 素材
// ---------------------------------------------------------------------------

/** map_assets 段只拉一次。 */
let assetMetaPromise = null;

/**
 * 内容包里的 map_assets 段。
 *
 * 主代理在 pack.js 的构造函数里补一行 `this.map_assets = data.map_assets || null`
 * 之后，这里就直接命中；补之前就自己拉一次内容包（只在这个视图打开时）。
 */
async function resolveMapAssets(ctx) {
  const pack = ctx && ctx.pack;
  if (pack && pack.map_assets) {
    setMapAssetIndex(pack.map_assets);
    return pack.map_assets;
  }
  if (!assetMetaPromise) {
    assetMetaPromise = (async () => {
      const buffer = await fetchMaybeGzip(editorUrl('content/pack.min.json.gz'));
      if (!buffer) return null;
      try {
        const data = JSON.parse(new TextDecoder().decode(buffer));
        if (data.map_assets) {
          setMapAssetIndex(data.map_assets);
          return data.map_assets;
        }
      } catch (err) {
        /* 内容包读不出来就当没有素材 */
      }
      return null;
    })();
  }
  return assetMetaPromise;
}

/**
 * 拉素材文件。
 *
 * sha256 是对**打包后**的那个 .gz 文件算的，而 fetchMaybeGzip 会先把 gzip 解开 ——
 * 所以这里自己取原始字节：先校验摘要，再解开。
 *
 * @returns {Promise<{bytes: Uint8Array}|{error: string}>}
 */
async function fetchAssetBytes(meta) {
  const url = editorUrl(meta.file);
  try {
    const response = await fetch(url, { cache: 'no-cache' });
    if (!response.ok) return { error: `素材文件拉取失败（HTTP ${response.status}）` };
    const packed = new Uint8Array(await response.arrayBuffer());
    if (meta.sha256) {
      const digest = await sha256Hex(packed);
      if (digest && digest !== meta.sha256) {
        return { error: '素材文件与内容包不是同一版（sha256 不符）' };
      }
    }
    const raw = await gunzip(packed);
    if (!raw) return { error: '素材文件解不开（不是 gzip）' };
    if (meta.raw_size && raw.byteLength !== meta.raw_size) {
      return { error: `素材长度不符（${raw.byteLength} ≠ ${meta.raw_size} 字节）` };
    }
    return { bytes: raw };
  } catch (err) {
    // 退一步：用现成的 fetchMaybeGzip（这条路不校验摘要）。
    const buffer = await fetchMaybeGzip(url);
    if (!buffer) return { error: '素材文件拉取失败' };
    return { bytes: new Uint8Array(buffer) };
  }
}

async function gunzip(bytes) {
  if (typeof DecompressionStream !== 'function') return null;
  try {
    const copy = new Uint8Array(bytes);
    const stream = new Response(copy).body.pipeThrough(new DecompressionStream('gzip'));
    return new Uint8Array(await new Response(stream).arrayBuffer());
  } catch (err) {
    return null;
  }
}

async function sha256Hex(bytes) {
  const subtle = globalThis.crypto && globalThis.crypto.subtle;
  if (!subtle) return null;
  try {
    const digest = await subtle.digest('SHA-256', bytes);
    return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, '0')).join('');
  } catch (err) {
    return null;
  }
}

// ---------------------------------------------------------------------------
// 视图
// ---------------------------------------------------------------------------

/**
 * 战场地图视图。
 *
 * @param {HTMLElement} container
 * @param {object} ctx
 * @param {number} stage   关卡 id
 * @param {number} variant 变体 id
 */
export function renderBattleMap(container, ctx, stage, variant) {
  clear(container);
  const pack = ctx.pack;
  const layout = BATTLE_LAYOUT;

  // 视图的局部状态（改动本身一律在 pack 里，视图不维护第二份）。
  const view = {
    stage,
    variant,
    mapId: stage,        // 显示地图表的哪一条（默认 = 关卡 id，见规格 §2.9）
    zoom: 1,
    selected: null,      // 选中的格
    asset: null,         // 解码后的素材
    assetError: null,    // 素材缺失的原因
    showGrid: true,
  };

  const mapStructure = pack.structure('map_table');
  const mapRecord = mapStructure ? mapStructure.records[stage] : null;

  /** 这一关这一变体的 12 个角色槽 / 16 个物件槽。 */
  const actors = collectSlots(pack, 'battle_actors', stage, variant, 12,
    layout.ACTORS_BASE + stage * layout.GROUP_STRIDE + variant * layout.VARIANT_STRIDE + 4,
    layout.SLOT_STRIDE);
  const objects = collectSlots(pack, 'battle_map_objects', stage, variant, layout.OBJECT_COUNT,
    layout.ACTORS_BASE + stage * layout.GROUP_STRIDE + variant * layout.VARIANT_STRIDE + layout.OBJECT_OFFSET,
    4);

  /** 地图尺寸：素材没到之前用地图表的原始宽高算（格宽 = 原始宽 >> 2，格高 = 原始高 >> 1）。 */
  function cellSize() {
    const meta = assetMeta();
    const entry = meta && meta.maps ? meta.maps[String(view.mapId)] : null;
    if (entry) return { cellW: entry.cell_w, cellH: entry.cell_h };
    const record = currentMapRecord();
    if (record) {
      return {
        cellW: record.values.raw_width >> 2,
        cellH: record.values.raw_height >> 1,
      };
    }
    return { cellW: 0, cellH: 0 };
  }

  let assetMetaRef = null;
  function assetMeta() {
    return assetMetaRef;
  }

  // --- 头部 ---------------------------------------------------------------
  const stageSelect = el('select', {
    class: 'search',
    onchange: (e) => ctx.openPanel('map', 'map', { stage: Number(e.target.value), variant }),
  });
  const variantSelect = el('select', {
    class: 'search',
    onchange: (e) => ctx.openPanel('map', 'map', { stage, variant: Number(e.target.value) }),
  });
  for (const v of Array.from({ length: layout.VARIANT_COUNT }, (_, i) => i)) {
    variantSelect.appendChild(el('option', {
      value: String(v), text: `变体 ${v}`, selected: v === variant,
    }));
  }
  const mapSelect = el('select', {
    class: 'search',
    title: '地图 id 与关卡 id 的对应关系是推测（见下方说明）',
    onchange: (e) => {
      view.mapId = Number(e.target.value);
      reloadAsset();
    },
  });

  container.appendChild(el('div', { class: 'panel-head' }, [
    el('div', {}, [
      el('h2', { text: `第 ${stage} 关 · 战场地图` }),
      el('div', { class: 'panel-sub' }, [
        el('span', { text: `地图表 0x${(layout.MAP_BASE + stage * 32).toString(16).toUpperCase()}` }),
        el('span', {
          text: `编成组 0x${(layout.ACTORS_BASE + stage * layout.GROUP_STRIDE)
            .toString(16).toUpperCase()}` }),
        el('span', {
          class: 'stat-hint',
          text: changeCount() ? `本关已改 ${changeCount()} 处` : '本关还没有改动',
        }),
      ]),
    ]),
    el('div', { class: 'panel-tools' }, [
      el('button', {
        class: 'btn btn-ghost',
        text: '← 返回战斗',
        title: '回到战斗域首页',
        onclick: () => { ctx.state.view.panel = null; ctx.render(); },
      }),
      stageSelect, variantSelect, mapSelect,
    ]),
  ]));

  // --- 一行说明（地图多大） ------------------------------------------------
  const infoLine = el('div', { class: 'map-info' });
  container.appendChild(infoLine);

  // --- 素材提示条（只在降级时出现） ----------------------------------------
  const noticeHost = el('div', { class: 'map-notice-host' });
  container.appendChild(noticeHost);

  // --- 左：画布 -----------------------------------------------------------
  const canvas = el('canvas', { class: 'map-canvas' });
  // 格线底图：素材没到时占位（纯 CSS 网格，每 32×16 像素一格）。
  // 它在 .map-stage 里，跟着缩放一起变。
  const fallback = el('div', { class: 'map-grid-fallback' });
  const hoverBox = el('div', { class: 'map-cell-hover' });
  const selectBox = el('div', { class: 'map-cell-selected' });
  const stageEl = el('div', { class: 'map-stage' }, [canvas, fallback, hoverBox, selectBox]);
  const frame = el('div', { class: 'map-frame' }, [stageEl]);
  const scroll = el('div', { class: 'map-scroll' }, [frame]);
  const statusLine = el('div', { class: 'map-status' });

  const zoomLabel = el('span', { class: 'map-zoom-label', text: '100%' });
  const toolbar = el('div', { class: 'map-toolbar' }, [
    el('button', {
      class: 'btn btn-tiny', text: '适应窗口',
      onclick: () => setZoom(fitZoom()),
    }),
    el('button', {
      class: 'btn btn-tiny', text: '100%',
      onclick: () => setZoom(1),
    }),
    el('button', {
      class: 'btn btn-tiny', text: '−',
      title: '缩小一档',
      onclick: () => setZoom(zoomIndex() - 1),
    }),
    el('button', {
      class: 'btn btn-tiny', text: '＋',
      title: '放大一档',
      onclick: () => setZoom(zoomIndex() + 1),
    }),
    zoomLabel,
    el('label', { class: 'map-toggle' }, [
      el('input', {
        type: 'checkbox',
        checked: true,
        onchange: (e) => {
          view.showGrid = !!e.target.checked;
          drawCanvas();
        },
      }),
      el('span', { text: '格线与坐标' }),
    ]),
  ]);

  const left = el('div', { class: 'map-left' }, [
    toolbar, scroll, statusLine,
    el('div', { class: 'map-legend' }, [
      legendItem('#275a3b', '角色 · 我方'),
      legendItem('#a74636', '角色 · 敌方'),
      legendItem('#ffdb79', '战场物件', '#513509'),
      legendItem('transparent', '选中', '#ffda64'),
    ]),
  ]);

  // --- 右：面板 -----------------------------------------------------------
  const side = el('div', { class: 'map-side' });
  const right = el('div', { class: 'map-right' }, [side]);

  container.appendChild(splitPane(left, right, { key: 'battle-map', defaultWidth: 420 }));

  // =========================================================================
  // 绘制
  // =========================================================================

  function zoomIndex() {
    const at = ZOOM_STEPS.indexOf(view.zoom);
    return at < 0 ? 0 : at;
  }

  function fitZoom() {
    const { cellW } = cellSize();
    const mapWidth = cellW * CELL_PX_W;
    if (!mapWidth || !scroll.clientWidth) return 1;
    const fit = Math.floor(scroll.clientWidth / mapWidth);
    const step = ZOOM_STEPS.findIndex((z) => z >= fit);
    if (step < 0) return ZOOM_STEPS[ZOOM_STEPS.length - 1];
    return ZOOM_STEPS[Math.max(0, step)];
  }

  function setZoom(zoom) {
    const clamped = Math.min(ZOOM_STEPS.length - 1, Math.max(0, zoom));
    view.zoom = ZOOM_STEPS[clamped];
    zoomLabel.textContent = `${view.zoom * 100}%`;
    const { cellW, cellH } = cellSize();
    const pxW = cellW * CELL_PX_W;
    const pxH = cellH * CELL_PX_H;
    frame.style.width = `${pxW * view.zoom}px`;
    frame.style.height = `${pxH * view.zoom}px`;
    // 画布是 1:1 画的，缩放交给 CSS —— 所以换档不用重画像素。
    stageEl.style.transform = `scale(${view.zoom})`;
  }

  function drawCanvas() {
    const { cellW, cellH } = cellSize();
    const pxW = cellW * CELL_PX_W;
    const pxH = cellH * CELL_PX_H;
    canvas.width = pxW;
    canvas.height = pxH;
    const c = canvas2d(canvas);
    if (!c) return;
    if (view.asset) {
      const img = renderMapImage(view.asset);
      if (c.createImageData && c.putImageData) {
        const data = c.createImageData(img.width, img.height);
        data.data.set(img.pixels);
        c.putImageData(data, 0, 0);
      }
    }
    if (!view.showGrid) return;
    // 素材没到时格线由 CSS 底图画（.map-grid-fallback），这里只画行列号，
    // 免得两套格线叠在一起。
    if (view.asset) {
      c.strokeStyle = 'rgba(255,255,255,0.15)';
      c.lineWidth = 1;
      c.beginPath();
      for (let x = 0; x <= cellW; x++) {
        c.moveTo(x * CELL_PX_W + 0.5, 0);
        c.lineTo(x * CELL_PX_W + 0.5, pxH);
      }
      for (let y = 0; y <= cellH; y++) {
        c.moveTo(0, y * CELL_PX_H + 0.5);
        c.lineTo(pxW, y * CELL_PX_H + 0.5);
      }
      c.stroke();
    }
    // 行列号是**格**坐标，不是像素
    c.fillStyle = 'rgba(255,255,255,0.55)';
    c.font = '8px sans-serif';
    for (let x = 0; x < cellW; x++) c.fillText(String(x), x * CELL_PX_W + 2, 8);
    for (let y = 0; y < cellH; y++) c.fillText(String(y), 2, y * CELL_PX_H + 9);
  }

  // =========================================================================
  // 标记
  // =========================================================================

  function refreshMarkers() {
    for (const node of Array.from(stageEl.children)) {
      if (node !== canvas && node.className && String(node.className).includes('map-marker')) {
        node.remove();
      }
    }
    // 「改过的」以 pack 为准（规格 §4.8：视图不维护第二份改动状态）。
    const changedObjects = changedOffsets(objects.structure);
    const changedActors = changedOffsets(actors.structure);
    const picked = view.selected;
    const onPicked = (v) => !!picked && v.x === picked.x && v.y === picked.y;
    for (let slot = 0; slot < objects.records.length; slot++) {
      const record = objects.records[slot];
      if (!record) continue;
      const v = record.values;
      if (!v.type) continue;                       // 空槽不画
      stageEl.appendChild(el('div', {
        class: `map-marker map-marker-object${onPicked(v) ? ' selected' : ''}` +
          `${changedObjects.has(record.rom_offset) ? ' changed' : ''}`,
        style: {
          left: `${v.x * CELL_PX_W + 1}px`,
          top: `${v.y * CELL_PX_H + 1}px`,
          width: `${CELL_PX_W - 2}px`,
          height: `${CELL_PX_H - 2}px`,
        },
        text: `物${slot + 1}`,
        title: `物件 #${slot + 1} · (${v.x}, ${v.y})`,
        dataset: { kind: 'object', slot: String(slot) },
        onmousedown: (e) => startDrag(e, 'object', slot),
      }));
    }
    for (let slot = 0; slot < actors.records.length; slot++) {
      const record = actors.records[slot];
      if (!record) continue;
      const v = record.values;
      if (!v.character_id) continue;               // 空槽不画
      const enemy = (v.unit_flags & 1) === 1;
      stageEl.appendChild(el('div', {
        class: `map-marker map-marker-actor ${enemy ? 'enemy' : 'ally'}` +
          `${onPicked(v) ? ' selected' : ''}` +
          `${changedActors.has(record.rom_offset) ? ' changed' : ''}`,
        style: {
          left: `${v.x * CELL_PX_W + 6}px`,
          top: `${v.y * CELL_PX_H + 1}px`,
          width: '20px',
          height: `${CELL_PX_H - 2}px`,
        },
        text: String(slot + 1),
        title: `角色 #${slot + 1} · (${v.x}, ${v.y})`,
        dataset: { kind: 'actor', slot: String(slot) },
        onmousedown: (e) => startDrag(e, 'actor', slot),
      }));
    }
  }

  /** 这张表里哪些记录被改过（按字节比较，与通用表格编辑器同一套判断）。 */
  function changedOffsets(structure) {
    const out = new Set();
    if (!structure) return out;
    for (const record of pack.changedStructureRecords(structure)) {
      out.add(record.rom_offset);
    }
    return out;
  }

  /** 悬停 / 选中的格：两个覆盖在画布上的小框（重画整幅图太贵）。 */
  function placeBox(box, cell) {
    if (!cell) {
      box.style.display = 'none';
      return;
    }
    box.style.display = 'block';
    box.style.left = `${cell.x * CELL_PX_W}px`;
    box.style.top = `${cell.y * CELL_PX_H}px`;
    box.style.width = `${CELL_PX_W}px`;
    box.style.height = `${CELL_PX_H}px`;
  }

  // =========================================================================
  // 拖动
  // =========================================================================

  let drag = null;
  let panning = null;
  let spaceDown = false;

  function pointerPixels(event) {
    const rect = canvasRect(canvas);
    if (!rect) return null;
    const { cellW } = cellSize();
    const mapWidth = cellW * CELL_PX_W;
    const scale = mapWidth ? rect.width / mapWidth : 1;
    if (!scale) return null;
    return {
      px: (event.clientX - rect.left) / scale,
      py: (event.clientY - rect.top) / scale,
    };
  }

  function startDrag(event, kind, slot) {
    const record = kind === 'object' ? objects.records[slot] : actors.records[slot];
    if (!record) return;
    const values = record.values;
    drag = {
      kind,
      slot,
      x: values.x,
      y: values.y,
      node: event.currentTarget,
      moved: false,
    };
    if (event.currentTarget && event.currentTarget.classList) {
      event.currentTarget.classList.add('dragging');
    }
    if (event.preventDefault) event.preventDefault();
  }

  function onMove(event) {
    if (panning) {
      // 平移：按住空格拖拽 / 中键拖拽
      scroll.scrollLeft = panning.left - (event.clientX - panning.x);
      scroll.scrollTop = panning.top - (event.clientY - panning.y);
      return;
    }
    if (!drag) return;
    const point = pointerPixels(event);
    if (!point) return;
    const cellX = Math.floor(point.px / CELL_PX_W);
    const cellY = Math.floor(point.py / CELL_PX_H);
    drag.moved = true;
    const offsetX = drag.kind === 'object' ? 1 : 6;
    drag.node.style.left = `${cellX * CELL_PX_W + offsetX}px`;
    drag.node.style.top = `${cellY * CELL_PX_H + 1}px`;
    updateStatus({ x: cellX, y: cellY });
  }

  function onUp(event) {
    if (panning) {
      panning = null;
      if (scroll.classList) scroll.classList.remove('panning');
      return;
    }
    if (!drag) return;
    const current = drag;
    drag = null;
    if (current.node && current.node.classList) current.node.classList.remove('dragging');
    const point = pointerPixels(event);
    const { cellW, cellH } = cellSize();
    if (!point) {
      refreshMarkers();
      return;
    }
    const x = Math.floor(point.px / CELL_PX_W);
    const y = Math.floor(point.py / CELL_PX_H);
    if (x < 0 || x >= cellW || y < 0 || y >= cellH) {
      // 越界：不写回，标记弹回原位（规格 §4.3）
      if (x < 0 || x >= cellW) {
        toast(`X 坐标越界：这张地图只有 ${cellW} 列（0–${cellW - 1}）。`, 'error');
      } else {
        toast(`Y 坐标越界：这张地图只有 ${cellH} 行（0–${cellH - 1}）。`, 'error');
      }
      refreshMarkers();
      return;
    }
    if (x === current.x && y === current.y) {
      refreshMarkers();
      return;
    }
    moveTo(current.kind, current.slot, x, y);
  }

  function moveTo(kind, slot, x, y) {
    const { cellW, cellH } = cellSize();
    if (x < 0 || x >= cellW) {
      toast(`X 坐标越界：这张地图只有 ${cellW} 列（0–${cellW - 1}）。`, 'error');
      return false;
    }
    if (y < 0 || y >= cellH) {
      toast(`Y 坐标越界：这张地图只有 ${cellH} 行（0–${cellH - 1}）。`, 'error');
      return false;
    }
    const structure = kind === 'object' ? objects.structure : actors.structure;
    const record = kind === 'object' ? objects.records[slot] : actors.records[slot];
    if (!structure || !record) return false;
    pack.setValue(structure, record, 'x', x);
    pack.setValue(structure, record, 'y', y);
    ctx.onChange();
    toast(`已把 ${kind === 'object' ? '物件' : '角色'} #${slot + 1} 移到 (${x}, ${y})` +
      '（Ctrl+Z 撤销）');
    refreshMarkers();
    updateStatus({ x, y });
    return true;
  }

  // =========================================================================
  // 状态行 / 提示条
  // =========================================================================

  function updateStatus(cell) {
    const target = cell || view.selected;
    const { cellW, cellH } = cellSize();
    if (!target) {
      statusLine.textContent = view.assetError
        ? '（底图缺失）'
        : '点一个格子看它的坐标、通行值与上面放着什么。';
      return;
    }
    const on = [];
    for (let slot = 0; slot < objects.records.length; slot++) {
      const record = objects.records[slot];
      if (!record) continue;
      const v = record.values;
      if (v.type && v.x === target.x && v.y === target.y) on.push(`物件 #${slot + 1}`);
    }
    for (let slot = 0; slot < actors.records.length; slot++) {
      const record = actors.records[slot];
      if (!record) continue;
      const v = record.values;
      if (v.character_id && v.x === target.x && v.y === target.y) on.push(`角色 #${slot + 1}`);
    }
    const terrain = view.asset ? terrainAt(view.asset, target.x, target.y) : null;
    const terrainText = terrain === null
      ? '通行值未知（素材没到）'
      : `通行 ${terrain}（${TERRAIN_NAMES[terrain] || TERRAIN_OTHER}）`;
    const parts = [`所选格 (${target.x}, ${target.y})`, terrainText];
    if (on.length) parts.push(`该格上：${on.join('、')}`);
    if (view.assetError) parts.push('（底图缺失）');
    statusLine.textContent = parts.join(' · ');
  }

  function updateNotice() {
    clear(noticeHost);
    if (!view.assetError) return;
    const meta = assetMeta();
    noticeHost.appendChild(mapAssetNotice(
      `未载入地图素材 —— 只显示格线与标记。${view.assetError}`,
      meta ? meta.file : null,
      () => reloadAsset()
    ));
  }

  function changeCount() {
    let n = stageChangeCount(ctx, stage, variant);
    const record = currentMapRecord();
    if (mapStructure && record) {
      const changed = pack.changedStructureRecords(mapStructure)
        .some((r) => r.rom_offset === record.rom_offset);
      if (changed) n += 1;
    }
    return n;
  }

  /** 当前显示的那一条地图表记录（默认是这一关自己的那一条）。 */
  function currentMapRecord() {
    if (!mapStructure) return null;
    return mapStructure.records[view.mapId] || mapRecord;
  }

  function updateInfo() {
    clear(infoLine);
    const { cellW, cellH } = cellSize();
    const meta = assetMeta();
    const parts = [];
    if (view.mapId === stage) {
      parts.push(`战场地图：第 ${stage} 关的战场`);
    } else {
      parts.push(`战场地图：地图表第 ${view.mapId} 条（第 ${stage} 关用的是第 ${stage} 条）`);
    }
    parts.push(`地图表第 ${view.mapId} 条`);
    parts.push(`${cellW} × ${cellH} 格`);
    parts.push(`${cellW * CELL_PX_W} × ${cellH * CELL_PX_H} 像素`);
    if (view.assetError) parts.push('（只显示格线与标记）');
    infoLine.appendChild(el('span', { text: parts.join(' · ') }));
    if (view.mapId !== stage) {
      infoLine.appendChild(el('span', {
        class: 'stat-hint',
        text: '地图 id 与关卡 id 的对应关系是推测：原生剧本的 0x1E 指令本仓库只提取到 3 处，' +
          '都不是战斗关卡，所以这里默认按「地图 id = 关卡 id」处理，可以手动换成地图表的另一条。',
      }));
    }
    if (meta && meta.maps && !meta.maps[String(view.mapId)]) {
      infoLine.appendChild(el('span', {
        class: 'stat-hint',
        text: `素材包里没有第 ${view.mapId} 条地图。`,
      }));
    }
  }

  // =========================================================================
  // 右侧面板：这一关的全部配置，按类分成卡片
  // =========================================================================
  //
  // 地图是主界面；**这一关的其它配置**摆在右侧的卡片里：
  // 战场布置 / 战场物件 / 角色出生点 / 胜负条件 / 剧情触发。
  // 以前这些散在「关卡视图」那一长条页面里，作者要在两个页面之间来回跳。
  //
  // 卡片**全都同时可见**（不是页签）—— 往下滚就是这一关全部能改的东西。

  const cards = new CardStack([
    {
      id: 'setup',
      label: '战场布置',
      hint: '这张地图的尺寸、剧情底图与六个 LZ77 资源指针',
      badge: () => changedCount(['map_table'], [layout.MAP_BASE + stage * 32]),
      render: () => battleSetupSection(),
    },
    {
      id: 'objects',
      label: '战场物件',
      hint: '16 个物件槽：类别 / 触发目标 / 格坐标',
      badge: () => changedCount(['battle_map_objects'], objectOffsets()),
      render: () => objectSection(),
    },
    {
      id: 'actors',
      label: '角色出生点',
      hint: '12 个角色槽：角色 / 阵营 / 格坐标 / 朝向 / 等级',
      badge: () => changedCount(['battle_actors'], actorOffsets()),
      render: () => actorSection(),
    },
    {
      id: 'rules',
      label: '胜负条件',
      hint: '回合上限 + 4 个胜利条件 + 4 个失败条件（与给玩家看的说明文字）',
      badge: () => rulesChanged(),
      render: () => renderRulesTab(ctx, stage, variant),
    },
    {
      id: 'scripts',
      label: '剧情触发',
      hint: '这一关在战斗里会触发的四个剧本与可改的操作数',
      badge: () => scriptsChanged(),
      render: () => renderScriptsTab(ctx, stage),
    },
  ], { pack });

  // 卡片堆只挂一次；刷新内容都在 CardStack 内部做。
  side.appendChild(cards.element);

  function refreshPanel() {
    cards.refresh();
  }

  /** 这些偏移上的记录有几条被改过（按字节判定，与通用表格同一套）。 */
  function changedCount(structureIds, offsets) {
    let n = 0;
    for (const id of structureIds) {
      const structure = pack.structure(id);
      if (!structure) continue;
      const changed = new Set(pack.changedStructureRecords(structure).map((r) => r.rom_offset));
      for (const offset of offsets) {
        if (changed.has(offset)) n += 1;
      }
    }
    return n || null;
  }

  function actorOffsets() {
    const base = layout.ACTORS_BASE + stage * layout.GROUP_STRIDE + variant * layout.VARIANT_STRIDE + 4;
    return Array.from({ length: 12 }, (_, s) => base + s * layout.SLOT_STRIDE);
  }

  function objectOffsets() {
    const base = layout.ACTORS_BASE + stage * layout.GROUP_STRIDE + variant * layout.VARIANT_STRIDE +
      layout.OBJECT_OFFSET;
    return Array.from({ length: layout.OBJECT_COUNT }, (_, o) => base + o * 4);
  }

  /** 胜负条件这一页改了几处（记录本身 + 给玩家看的说明文字）。 */
  function rulesChanged() {
    const structure = pack.structure('battle_rules');
    let n = 0;
    if (structure) {
      const offset = layout.RULES_BASE + stage * layout.RULE_STAGE_STRIDE + variant * layout.RULE_SUB_STRIDE;
      const changed = new Set(pack.changedStructureRecords(structure).map((r) => r.rom_offset));
      if (changed.has(offset)) n += 1;
    }
    const objectives = pack.textTable('battle_objectives');
    if (objectives) {
      const changed = new Set(pack.changedTextRecords(objectives).map((r) => r.id));
      for (const binding of objectives.bindings || []) {
        if (binding.rule !== stage * layout.VARIANT_COUNT + variant) continue;
        if (changed.has(binding.text_id)) n += 1;
      }
    }
    return n || null;
  }

  /** 剧情触发这一页改了几处（脚本操作数是补丁，按操作数算）。 */
  function scriptsChanged() {
    let n = 0;
    for (const script of pack.scripts || []) {
      if (script.scene !== stage) continue;
      for (const operand of script.operands || []) {
        if (operandChanged(operand)) n += 1;
      }
    }
    return n || null;
  }

  function battleSetupSection() {
    const { cellW, cellH } = cellSize();
    const record = currentMapRecord();
    const v = record ? record.values : null;
    const rows = [
      ['地图', record
        ? `地图表第 ${view.mapId} 条 · ${cellW} × ${cellH} 格 · ${cellW * CELL_PX_W} × ${cellH * CELL_PX_H} 像素`
        : '找不到地图表记录'],
    ];
    const node = el('div', { class: 'map-section' }, [
      el('h3', { text: '战场布置' }),
      el('div', { class: 'kv' }, rows.flatMap(([k, value]) => [
        el('dt', { text: k }),
        el('dd', { text: value }),
      ])),
    ]);
    if (v) {
      node.appendChild(backgroundBlock());
      node.appendChild(el('div', { class: 'kv' }, [
        el('dt', { text: '图块图形' }),
        el('dd', { text: `${ptrText(v.tile_gfx_ptr)} · LZ77 4bpp 图形` }),
        el('dt', { text: '调色板' }),
        el('dd', { text: `${ptrText(v.palette_ptr)} · LZ77 384 字节` }),
        el('dt', { text: '图层 0' }),
        el('dd', { text: `${ptrText(v.layer0_ptr)} · LZ77 tilemap` }),
        el('dt', { text: '图层 1' }),
        el('dd', { text: v.layer1_ptr ? `${ptrText(v.layer1_ptr)} · LZ77 tilemap` : 'NULL —— 本关无第二层' }),
        el('dt', { text: '组合图块表' }),
        el('dd', { text: `${ptrText(v.metatile_ptr)} · LZ77，8 字节/项` }),
        el('dt', { text: '通行值表' }),
        el('dd', { text: `${ptrText(v.terrain_ptr)} · LZ77，每格 u16（战斗加载器不读，只读）` }),
      ]));
      node.appendChild(el('p', { class: 'section-note' }, [
        '图块、调色板、图层、组合图块、通行值都是 LZ77 载荷，编辑器改不了；' +
        '能改的是指针（等于手工接线）。',
        '剧情底图是剧情画面上半屏（240×80）的那张贴图，不是战场贴图，所以它单列一块，' +
        '不叠在战场地图上。',
      ]));
    }
    return node;
  }

  function backgroundBlock() {
    const record = currentMapRecord();
    const v = record ? record.values : null;
    const current = v ? v.background_id : 0;
    const valid = backgroundIds(pack);
    const options = valid.map((id) => ({ value: id, text: `底图 ${id}` }));
    if (!valid.includes(current)) {
      options.push({ value: current, text: `底图 ${current}（该 id 没有可用底图）` });
    }
    const select = el('select', {
      class: 'search',
      style: { width: '160px' },
      onchange: (e) => {
        const next = Number(e.target.value);
        const record = currentMapRecord();
        if (!mapStructure || !record) return;
        pack.setValue(mapStructure, record, 'background_id', next);
        ctx.onChange();
        toast(view.mapId === stage
          ? `已把第 ${stage} 关的剧情底图换成 底图 ${next}`
          : `已把地图表第 ${view.mapId} 条的剧情底图换成 底图 ${next}`);
        refreshPanel();
        updateInfo();
      },
    }, options.map((o) => el('option', {
      value: String(o.value), text: o.text, selected: Number(o.value) === current,
    })));

    const preview = el('canvas', { class: 'map-bg-preview', width: 240, height: 80 });
    const rom = ctx.rom;
    let note = '';
    if (!rom) {
      note = '底图预览要载入原版 ROM：素材包里只有战场图块，没有底图。';
    } else {
      const img = renderBackgroundImage(rom, current);
      if (img) {
        const c = canvas2d(preview);
        if (c && c.createImageData && c.putImageData) {
          const data = c.createImageData(img.width, img.height);
          data.data.set(img.pixels);
          c.putImageData(data, 0, 0);
        }
      } else {
        note = '这一张底图暂时预览不了（8bpp 底图没有完整调色板）。';
      }
    }
    return el('div', { class: 'map-background' }, [
      el('div', { class: 'map-bg-head' }, [
        el('span', { text: '剧情底图' }),
        select,
      ]),
      preview,
      note ? el('div', { class: 'stat-hint', text: note }) : null,
    ]);
  }

  function objectSection() {
    const typeEnum = objectTypeEnum();
    const rows = [];
    for (let slot = 0; slot < objects.records.length; slot++) {
      const record = objects.records[slot];
      if (!record) {
        rows.push([`#${slot + 1}`, '（缺记录）', '—', '—', '—', '—']);
        continue;
      }
      const v = record.values;
      const empty = !v.type && !v.target && !v.x && !v.y;
      rows.push([
        `#${slot + 1}`,
        objectTypeSelect(record, v, typeEnum),
        objectTargetSelect(record, v),
        empty ? '—' : coordInput(objects.structure, record, 'x', v.x),
        empty ? '—' : coordInput(objects.structure, record, 'y', v.y),
        openInTable(ctx, 'battle_map_objects', record.id, '↗'),
      ]);
    }
    return el('div', { class: 'map-section' }, [
      el('h3', { text: '战场物件（16 个槽）' }),
      el('p', { class: 'section-note' }, [
        '类别决定外观与音效，触发目标决定触发的剧本；X / Y 是格坐标，' +
        '越界会被拒绝。',
        '地图上标的是记录槽位，不是战斗中的实际生成顺序：卷轴（类别 3）与认识卡' +
        '（类别 4）可能不会生成，所以后面的编号会往前挪。',
        '机关名来自第三方编辑器（其作者在游戏里逐个验证过），本仓库未收录这张表 —— ' +
        '名字仅供参考，写回的仍是编号。',
        '每行末尾的 ↗ 可以在通用表格里打开同一条记录。',
      ]),
      mapTable(['槽', '类别', '内容', 'X', 'Y', '↗'], rows),
    ]);
  }

  function actorSection() {
    const rows = [];
    for (let slot = 0; slot < actors.records.length; slot++) {
      const record = actors.records[slot];
      if (!record) {
        rows.push([`#${slot + 1}`, '（缺记录）', '—', '—', '—', '—', '—', '—']);
        continue;
      }
      const v = record.values;
      rows.push([
        `#${slot + 1}`,
        characterSelect(record, v),
        sideCell(ctx, actors.structure, record, v),
        coordInput(actors.structure, record, 'x', v.x),
        coordInput(actors.structure, record, 'y', v.y),
        facingSelect(record, v),
        levelInput(record, v),
        openInTable(ctx, 'battle_actors', record.id, '↗'),
      ]);
    }
    return el('div', { class: 'map-section' }, [
      el('h3', { text: '角色出生点（12 个槽）' }),
      el('p', { class: 'section-note' }, [
        '阵营取自 unit_flags 的 bit0（+0x01 那个字节原生不读）。',
        '朝向枚举来自第三方编辑器的实机校验（0 上 / 1 右 / 2 下 / 3 左），' +
        '本仓库未独立复核。',
        '换角色不会把角色模板（属性与技能）拷进槽位 —— 槽内那 168 字节在内容包里是未解字节，' +
        '所以换角色时会有一次确认。',
        '每行末尾的 ↗ 可以在通用表格里打开同一条记录。',
      ]),
      mapTable(['槽', '角色', '阵营', 'X', 'Y', '朝向', '等级', '↗'], rows),
    ]);
  }

  // --- 表格里的控件 -------------------------------------------------------

  function objectTypeEnum() {
    const field = (objects.structure.fields || []).find((f) => f.key === 'type');
    return (field && field.enum) || { 0: '空' };
  }

  function objectTypeSelect(record, values, typeEnum) {
    const select = el('select', {
      class: 'search map-cell-select',
      onchange: (e) => {
        const type = Number(e.target.value);
        pack.setValue(objects.structure, record, 'type', type);
        if (type === 0) {
          // 选「空」= 清掉目标与坐标（一起写回）
          pack.setValue(objects.structure, record, 'target', 0);
          pack.setValue(objects.structure, record, 'x', 0);
          pack.setValue(objects.structure, record, 'y', 0);
        } else {
          const range = targetRange(type);
          const target = values.target;
          if (range && (target < range.min || target > range.max)) {
            pack.setValue(objects.structure, record, 'target', range.min);
          }
        }
        ctx.onChange();
        toast(`已改写 战场物件 · 类别`);
        refreshPanel();
        refreshMarkers();
      },
    }, Object.keys(typeEnum).map((key) => el('option', {
      value: key,
      text: typeEnum[key],
      selected: Number(key) === values.type,
    })));
    return select;
  }

  function targetRange(type) {
    if (type === 1) return { min: 1, max: 93, table: 'ninjutsu_names' };
    if (type === 2) return { min: 1, max: 16, table: 'material_names' };
    if (type === 3) return { min: 1, max: 21, table: 'character_names' };
    if (type === 4) return { min: 1, max: 62, table: 'character_names' };
    if (type === 5 || type === 6 || type === 7) return { min: 1, max: 13, table: null };
    return null;
  }

  function objectTargetSelect(record, values) {
    const type = values.type;
    const range = targetRange(type);
    if (!range) return el('span', { class: 'stat-hint', text: '—' });
    const options = [];
    for (let id = range.min; id <= range.max; id++) {
      options.push({ value: id, text: targetLabel(type, id) });
    }
    const select = el('select', {
      class: 'search map-cell-select',
      onchange: (e) => {
        pack.setValue(objects.structure, record, 'target', Number(e.target.value));
        ctx.onChange();
        toast('已改写 战场物件 · 触发目标');
        refreshMarkers();
      },
    }, options.map((o) => el('option', {
      value: String(o.value), text: o.text, selected: o.value === values.target,
    })));
    return select;
  }

  function targetLabel(type, id) {
    if (type === 1) return nameOf('ninjutsu_names', id) || `忍具 ${id}`;
    if (type === 2) return nameOf('material_names', id) || `强化素材 ${id}`;
    if (type === 3) return `${nameOf('character_names', id) || `人物 ${id}`} 的专属修行卷轴`;
    if (type === 4) return `${nameOf('character_names', id) || `人物 ${id}`} 的认识卡`;
    const third = MECHANISM_NAMES[id];
    return third ? `机关 ${id}（${third}）` : `机关 ${id}`;
  }

  function nameOf(tableId, id) {
    const table = pack.textTable(tableId);
    if (!table) return '';
    const record = (table.records || [])[id];
    return record ? (record.text || '') : '';
  }

  function characterSelect(record, values) {
    const table = pack.textTable('character_names');
    const records = (table && table.records) || [];
    const select = el('select', {
      class: 'search map-cell-select',
      onchange: (e) => {
        const next = Number(e.target.value);
        if (next === values.character_id) return;
        confirmCharacter(record, values, next);
      },
    }, records.map((r) => el('option', {
      value: String(r.id),
      text: r.text || `人物 ${r.id}`,
      selected: r.id === values.character_id,
    })));
    return select;
  }

  /**
   * 换角色要弹一次确认（规格 §4.5）。
   *
   * 第三方编辑器换角色时会把角色模板（属性 / 技能）整块拷进槽位；本仓库不做这件事
   * —— 槽内那 168 字节在内容包里是未解字节。所以这里只问一句，不拷贝。
   */
  function confirmCharacter(record, values, next) {
    const name = nameOf('character_names', next) || `人物 ${next}`;
    const body = el('p', {
      class: 'section-note',
      text: `换成「${name}」会沿用槽位里原有的属性与技能` +
        '（仓库没有把这张表接进编成矩阵）。继续吗？',
    });
    const actions = [
      {
        label: '取消',
        onClick: () => {
          refreshPanel();
          return false;
        },
      },
      {
        label: '继续',
        primary: true,
        onClick: () => {
          pack.setValue(actors.structure, record, 'character_id', next);
          ctx.onChange();
          toast(`已改写 角色出生点 · 角色（${name}）`);
          refreshPanel();
          refreshMarkers();
          return false;
        },
      },
    ];
    modal('换角色', body, actions);
  }

  function facingSelect(record, values) {
    const select = el('select', {
      class: 'search map-cell-select',
      onchange: (e) => {
        pack.setValue(actors.structure, record, 'facing', Number(e.target.value));
        ctx.onChange();
        toast('已改写 角色出生点 · 朝向');
        refreshMarkers();
      },
    }, FACING_NAMES.map((name, index) => el('option', {
      value: String(index), text: name, selected: index === values.facing,
    })));
    return select;
  }

  function levelInput(record, values) {
    return el('input', {
      class: 'num-input',
      type: 'text',
      style: { width: '56px' },
      value: String(values.level),
      onchange: (e) => {
        const next = Number(e.target.value);
        if (!Number.isFinite(next) || next < 0 || next > 99) {
          toast('请输入 0–99', 'error');
          e.target.value = String(values.level);
          return;
        }
        pack.setValue(actors.structure, record, 'level', next);
        ctx.onChange();
        toast('已改写 角色出生点 · 等级');
      },
    });
  }

  function coordInput(structure, record, key, value) {
    const { cellW, cellH } = cellSize();
    const max = key === 'x' ? cellW - 1 : cellH - 1;
    return el('input', {
      class: 'num-input',
      type: 'text',
      style: { width: '56px' },
      value: String(value),
      onchange: (e) => {
        const next = Number(e.target.value);
        if (!Number.isFinite(next) || next < 0 || next > max) {
          toast(key === 'x'
            ? `X 坐标越界：这张地图只有 ${cellW} 列（0–${cellW - 1}）。`
            : `Y 坐标越界：这张地图只有 ${cellH} 行（0–${cellH - 1}）。`, 'error');
          e.target.value = String(value);
          return;
        }
        pack.setValue(structure, record, key, next);
        ctx.onChange();
        toast(`已改写 ${structure.label} · ${key}`);
        refreshMarkers();
      },
    });
  }

  // =========================================================================
  // 素材载入
  // =========================================================================

  async function reloadAsset() {
    view.asset = null;
    view.assetError = null;
    assetMetaRef = null;
    updateNotice();
    updateInfo();
    const meta = await resolveMapAssets(ctx);
    assetMetaRef = meta;
    if (!meta) {
      view.assetError = '内容包里没有地图素材段';
      finishAsset();
      return;
    }
    const mapMeta = (meta.maps || {})[String(view.mapId)];
    if (!mapMeta) {
      view.assetError = `素材包里没有第 ${view.mapId} 条地图`;
      finishAsset();
      return;
    }
    const result = await fetchAssetBytes(meta);
    if (result.error) {
      view.assetError = result.error;
      finishAsset();
      return;
    }
    const asset = decodeMapAsset(result.bytes, mapMeta);
    if (!asset) {
      view.assetError = '素材解不开';
      finishAsset();
      return;
    }
    view.asset = asset;
    finishAsset();
  }

  function finishAsset() {
    fillSelectors();
    updateNotice();
    updateInfo();
    refreshPanel();
    refreshMarkers();
    drawCanvas();
    setZoom(zoomIndex());
    updateStatus();
    if (fallback.classList) fallback.classList.toggle('on', !view.asset);
    if (container.dataset) container.dataset.mapReady = '1';
  }

  // =========================================================================
  // 交互
  // =========================================================================

  canvas.addEventListener('click', (event) => {
    const rect = canvasRect(canvas);
    if (!rect) return;
    const { cellW, cellH } = cellSize();
    const cell = cellFromClientPoint(event.clientX, event.clientY, rect, cellW, cellH);
    if (!cell) return;
    view.selected = cell;
    placeBox(selectBox, cell);
    updateStatus(cell);
    refreshMarkers();
    refreshPanel();
  });

  canvas.addEventListener('mousemove', (event) => {
    const rect = canvasRect(canvas);
    if (!rect || drag) return;
    const { cellW, cellH } = cellSize();
    const cell = cellFromClientPoint(event.clientX, event.clientY, rect, cellW, cellH);
    if (!cell) {
      placeBox(hoverBox, null);
      return;
    }
    placeBox(hoverBox, cell);
    canvas.title = `(${cell.x}, ${cell.y})`;
  });

  canvas.addEventListener('mouseleave', () => placeBox(hoverBox, null));

  canvas.addEventListener('dblclick', () => {
    const fit = fitZoom();
    setZoom(view.zoom === fit ? 1 : fit);
  });

  // 滚轮缩放：必须 passive:false，否则 preventDefault 不生效（页面会跟着滚）。
  // el() 不支持事件选项，所以这里直接挂。
  canvas.addEventListener('wheel', (event) => {
    if (event.preventDefault) event.preventDefault();
    setZoom(zoomIndex() + (event.deltaY < 0 ? 1 : -1));
  }, { passive: false });

  if (typeof window !== 'undefined' && window.addEventListener) {
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
    window.addEventListener('keydown', (event) => {
      if (event.code === 'Space' || event.key === ' ') spaceDown = true;
    });
    window.addEventListener('keyup', (event) => {
      if (event.code === 'Space' || event.key === ' ') spaceDown = false;
    });
  }

  // 平移：按住空格拖拽 / 中键拖拽
  scroll.addEventListener('mousedown', (event) => {
    const middle = event.button === 1;
    if (!middle && !spaceDown) return;
    panning = {
      x: event.clientX,
      y: event.clientY,
      left: scroll.scrollLeft || 0,
      top: scroll.scrollTop || 0,
    };
    if (scroll.classList) scroll.classList.add('panning');
    if (event.preventDefault) event.preventDefault();
  });

  // --- 起步 ----------------------------------------------------------------
  refreshPanel();
  updateStatus();
  updateInfo();
  fillSelectors();
  setZoom(1);
  reloadAsset();

  /**
   * 关卡 / 地图两个下拉。
   *
   * 编号**从内容包取**：素材段里有哪几张图就列哪几张；没有素材段时退回地图表
   * （第 0 条没有对应的战斗关卡，见规格 §6.1）。
   */
  function fillSelectors() {
    const ids = mapIds();
    clear(stageSelect);
    clear(mapSelect);
    for (const id of ids) {
      stageSelect.appendChild(el('option', {
        value: String(id), text: `第 ${id} 关`, selected: id === stage,
      }));
      mapSelect.appendChild(el('option', {
        value: String(id), text: `地图 ${id}`, selected: id === view.mapId,
      }));
    }
  }

  function mapIds() {
    const meta = assetMeta();
    if (meta && meta.maps) {
      return Object.keys(meta.maps).map(Number).sort((a, b) => a - b);
    }
    const table = pack.structure('map_table');
    if (!table) return [];
    return (table.records || []).map((r) => r.id).filter((id) => id > 0);
  }
}

/**
 * 某一关某一变体的定长槽位。
 */
function collectSlots(pack, structureId, stage, variant, count, base, stride) {
  const structure = pack.structure(structureId);
  if (!structure) return { structure: null, records: [] };
  const records = [];
  for (let i = 0; i < count; i++) {
    const offset = base + i * stride;
    records.push((structure.records || []).find((r) => r.rom_offset === offset) || null);
  }
  return { structure, records };
}

/** 画布的 2D 上下文（无头环境里没有，返回 null）。 */
function canvas2d(canvas) {
  if (!canvas || typeof canvas.getContext !== 'function') return null;
  try {
    return canvas.getContext('2d');
  } catch (err) {
    return null;
  }
}

/** 画布在屏幕上的位置（无头环境里没有，返回 null）。 */
function canvasRect(canvas) {
  if (!canvas || typeof canvas.getBoundingClientRect !== 'function') return null;
  try {
    return canvas.getBoundingClientRect();
  } catch (err) {
    return null;
  }
}

/** 图例里的一格。 */
function legendItem(background, label, color) {
  return el('span', { class: 'map-legend-item' }, [
    el('i', { class: 'map-legend-swatch', style: { background, borderColor: color || 'transparent' } }),
    el('span', { text: label }),
  ]);
}

/** 一张小表（地图视图自己渲染，不用通用表格编辑器）。 */
function mapTable(head, rows) {
  const table = el('table', { class: 'grid map-table' });
  table.appendChild(el('thead', {}, [el('tr', {}, head.map((h) => el('th', { text: h })))]));
  const body = el('tbody');
  for (const row of rows) {
    const tr = el('tr');
    for (const cell of row) {
      const isNode = cell && typeof cell === 'object' && cell.nodeType === 1;
      tr.appendChild(el('td', {
        class: isNode ? '' : 'map-cell',
        text: isNode ? '' : (cell === null || cell === undefined ? '' : String(cell)),
      }, isNode ? [cell] : []));
    }
    body.appendChild(tr);
  }
  table.appendChild(body);
  return el('div', { class: 'table-wrap' }, [table]);
}

function ptrText(value) {
  if (!value) return 'NULL';
  return '0x' + (value >>> 0).toString(16).toUpperCase();
}
