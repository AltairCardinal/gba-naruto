// The list / detail split, with a draggable divider.
//
// 左边是列表、右边是编辑面板 —— 但两边该多宽，作者说了算：
// 改一串忍术名时详情面板可以窄一点，逐字读剧情时又需要宽一点。
//
// 实现：详情面板的宽度写进容器的 CSS 变量 `--split-right`，
// 拖动分隔条改这个变量；宽度记在 localStorage 里，下次进来还是这个宽度。
// 双击分隔条复位。

import { el } from './ui.js';

const MIN_WIDTH = 260;
const MAX_RATIO = 0.78;

/**
 * A list/detail split with a draggable divider.
 *
 * @param {object} left    the list element
 * @param {object} right   the detail element
 * @param {{key?: string, defaultWidth?: number, wide?: boolean}} options
 */
export function splitPane(left, right, options = {}) {
  const container = el('div', { class: 'split' });
  const handle = el('div', {
    class: 'split-handle',
    title: '拖动调整宽度 · 双击复位',
  });
  container.appendChild(left);
  container.appendChild(handle);
  container.appendChild(right);

  const defaultWidth = options.defaultWidth || (options.wide ? 560 : 380);
  const saved = readWidth(options.key);
  if (saved) container.style.setProperty('--split-right', `${saved}px`);
  else if (options.wide) container.style.setProperty('--split-right', `${defaultWidth}px`);

  attachResizer(container, handle, options.key, defaultWidth);
  return container;
}

function attachResizer(container, handle, key, defaultWidth) {
  let dragging = false;

  const currentWidth = () => {
    const raw = container.style.getPropertyValue('--split-right');
    const value = parseInt(raw, 10);
    return Number.isFinite(value) && value > 0 ? value : defaultWidth;
  };

  const onMove = (event) => {
    if (!dragging) return;
    const rect = container.getBoundingClientRect();
    if (!rect || !rect.width) return;
    const clientX = event && event.clientX !== undefined ? event.clientX : 0;
    // 分隔条本身占 6px，所以右边的宽度 = 右边界 − 鼠标位置 − 分隔条宽度。
    const width = Math.round(rect.right - clientX - 6);
    const max = Math.round(rect.width * MAX_RATIO);
    const clamped = Math.max(MIN_WIDTH, Math.min(max, width));
    container.style.setProperty('--split-right', `${clamped}px`);
    if (event && event.preventDefault) event.preventDefault();
  };

  const onUp = () => {
    if (!dragging) return;
    dragging = false;
    handle.classList.remove('dragging');
    if (typeof window !== 'undefined' && window.removeEventListener) {
      window.removeEventListener('pointermove', onMove);
      window.removeEventListener('pointerup', onUp);
    }
    writeWidth(key, currentWidth());
  };

  handle.addEventListener('pointerdown', (event) => {
    dragging = true;
    handle.classList.add('dragging');
    if (typeof window !== 'undefined' && window.addEventListener) {
      window.addEventListener('pointermove', onMove);
      window.addEventListener('pointerup', onUp);
    }
    if (event && event.preventDefault) event.preventDefault();
  });

  handle.addEventListener('dblclick', () => {
    container.style.setProperty('--split-right', `${defaultWidth}px`);
    writeWidth(key, defaultWidth);
  });
}

function readWidth(key) {
  if (!key) return null;
  try {
    const raw = globalThis.localStorage && globalThis.localStorage.getItem(key);
    const value = parseInt(raw, 10);
    return Number.isFinite(value) && value >= MIN_WIDTH ? value : null;
  } catch (err) {
    return null;
  }
}

function writeWidth(key, width) {
  if (!key || !Number.isFinite(width)) return;
  try {
    if (globalThis.localStorage) {
      globalThis.localStorage.setItem(key, String(width));
    }
  } catch (err) {
    // 隐私模式下 localStorage 可能不可用 —— 宽度不记住而已，不影响功能。
  }
}
