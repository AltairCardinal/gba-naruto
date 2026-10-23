// 载入 ROM 门禁 —— 载入 ROM 是编辑器的前置操作。
//
// 以前「载入 ROM」是顶栏一个可有可无的按钮：作者可以一路编辑到点「构建 ROM」
// 才被一句 toast 挡住，「原始字节」域则渲染一句「请先载入原版 ROM」就结束了。
// 现在载入 ROM 变成**门禁**：一个升起来的窗口，编辑器在它后面待着，
// 窗口不关，下面的内容就点不到。
//
// 门禁的判据（见 notes/specs/rom-gate-20261023.md）：
//
//   1. 窗口里**只有两个选择**：载入内置 ROM / 上传本地 ROM。
//   2. **不可直接关闭**：没有 × 按钮、Esc 无效、点遮罩无效、没有「稍后再说」。
//      唯一的出路是成功载入一个 ROM。
//   3. **不能透过窗口操作下方的内容**：遮罩覆盖整个视口；下方的应用外壳
//      置 inert（不可聚焦、不可点击、Tab 也进不去）；焦点锁在窗口里。
//   4. 载入失败**不关窗**：错误显示在窗口里，两个按钮恢复可用，可以换一条路重试。
//
// 两种模式：
//   * **必需**（编辑器还没拿到 ROM）：完全不可关。
//   * **可选**（ROM 已经载入了，作者只是想换一份）：这时才给 Esc / 遮罩 / 取消。
//     判据一句话：需要载入 ROM 时不可关，不需要载入 ROM 时随你关。
//
// 本模块只管「窗口长什么样、能不能关、焦点锁不锁」；
// ROM 从哪来由调用方用回调给进来（loadBundled / loadFile），
// 这样它不必 import app.js，也就不会和 app.js 互相 import。

import { el } from './ui.js';

/** 当前打开的门禁（同一时刻只有一个）。 */
let current = null;

/** 门禁是不是开着。 */
export function isGateOpen() {
  return current !== null;
}

/**
 * 打开载入 ROM 的门禁。
 *
 * @param {object} [options]
 * @param {string} [options.reason]     为什么要载入 ROM（显示在窗口里）
 * @param {boolean} [options.closable]  是否允许关闭（只有「ROM 已经载入了」才为真）
 * @param {(onProgress: (msg: string) => void) => Promise<Uint8Array>} [options.loadBundled]
 *        取内置 ROM 的方法
 * @param {(file: File) => Promise<Uint8Array>} [options.loadFile]
 *        读本地 ROM 文件的方法
 * @returns {Promise<Uint8Array|null>} 载到 ROM 就 resolve 它；被关掉就 resolve(null)
 *        （必需模式下不会 resolve，直到真的载入成功）
 */
export function openRomGate(options = {}) {
  // 已经开着一个了 —— 直接复用那一个，不要叠两个窗口。
  if (current) return current.promise;

  const {
    reason = '原版 ROM 是编辑器的前置操作：构建 ROM、原始字节视图都要用它当基底。',
    closable = false,
    loadBundled = null,
    loadFile = null,
  } = options;

  let resolveGate;
  const promise = new Promise((resolve) => { resolveGate = resolve; });

  const shell = document.getElementById('app-shell');
  const status = el('div', { class: 'rom-gate-status', text: '' });
  const error = el('div', { class: 'rom-gate-error hidden' });
  const actions = el('div', { class: 'rom-gate-actions' });

  // 文件输入框**长在窗口里**（不是外壳里）：外壳被置了 inert，
  // inert 子树里的 input.click() 会被浏览器吞掉，文件选择框就点不开了。
  const fileInput = el('input', { type: 'file', accept: '.gba', class: 'rom-gate-file' });
  fileInput.addEventListener('change', () => {
    const file = fileInput.files && fileInput.files[0];
    fileInput.value = '';
    if (!file) return;
    run(() => loadFile(file), `正在读取 ${file.name}…`);
  });

  const bundledButton = el('button', {
    class: 'btn btn-primary',
    text: '载入内置 ROM',
    title: '从编辑器自带的压缩副本里取回原版 ROM（部分浏览器有单页下载量限制，可能取不到）',
    onclick: () => {
      run(() => loadBundled((msg) => setStatus(msg)), '正在载入内置原版 ROM…');
    },
  });
  const uploadButton = el('button', {
    class: 'btn',
    text: '上传本地 ROM',
    title: '选一个原版 ROM 文件（不走网络，最稳）',
    onclick: () => fileInput.click(),
  });
  // 窗口里能聚焦的就这几个按钮（文件输入框是隐藏的，本来也不该被 Tab 到）。
  // 自己记一份，比 querySelectorAll 稳 —— 桩 DOM 里没有选择器引擎。
  const buttons = [bundledButton, uploadButton];
  actions.appendChild(bundledButton);
  actions.appendChild(uploadButton);
  if (closable) {
    const cancelButton = el('button', {
      class: 'btn btn-ghost',
      text: '取消',
      onclick: () => close(null),
    });
    buttons.push(cancelButton);
    actions.appendChild(cancelButton);
  }

  const box = el('div', { class: 'rom-gate', tabindex: '-1' }, [
    el('div', { class: 'rom-gate-title', text: '载入 ROM' }),
    el('div', { class: 'rom-gate-note', text: reason }),
    el('div', { class: 'rom-gate-hint', text: closable
      ? '换一份 ROM 会替换当前的构建基底。'
      : '这一步不能跳过：编辑器要拿原版 ROM 当基底，才能构建 ROM、才能逐字节看原始数据。' }),
    actions,
    status,
    error,
    fileInput,
  ]);

  const overlay = el('div', {
    class: 'rom-gate-overlay',
    role: 'dialog',
    'aria-modal': 'true',
    'aria-label': '载入 ROM',
  }, [box]);

  // --- 底下那一层彻底封死 --------------------------------------------------
  // 遮罩盖住整个视口：点它只会落到遮罩上，不会落到下面的内容上。
  // 再叠 inert：连 Tab 都进不去下面的内容（老浏览器没有 inert 时，
  // 下面的 focusin 兜底也会把焦点拉回来）。
  if (shell) {
    shell.setAttribute('inert', '');
    shell.setAttribute('aria-hidden', 'true');
  }

  overlay.addEventListener('mousedown', (event) => {
    // 只处理点在**遮罩本身**上的那一下 —— 窗口里的点击要照常落到按钮上。
    if (event.target !== overlay) return;
    // 点遮罩：必需模式下**什么都不做**（也不能让焦点掉到下面的内容上）。
    event.preventDefault();
    if (closable) close(null);
  });

  function onKeyDown(event) {
    if (!current) return;
    if (event.key === 'Escape' || event.key === 'Esc') {
      // 必需模式：Esc 不关窗。而且要 stopPropagation —— 否则页面里别的
      // Esc 处理器（关面板之类）会被一起触发。
      event.preventDefault();
      event.stopPropagation();
      if (closable) close(null);
      return;
    }
    if (event.key !== 'Tab') return;
    // 焦点锁在窗口里：Tab 在几个按钮之间来回走，不许跑到外面去。
    const list = focusables();
    if (!list.length) return;
    const first = list[0];
    const last = list[list.length - 1];
    const active = document.activeElement || null;
    const inside = contains(box, active);
    if (event.shiftKey && (!inside || active === first)) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && (!inside || active === last)) {
      event.preventDefault();
      first.focus();
    }
  }

  function onFocusIn(event) {
    if (!current) return;
    if (contains(box, event.target)) return;
    const list = focusables();
    const target = list[0] || box;
    if (target.focus) target.focus();
  }

  window.addEventListener('keydown', onKeyDown, true);
  window.addEventListener('focusin', onFocusIn, true);

  // --- 载入 ---------------------------------------------------------------
  let busy = false;

  function setStatus(text) {
    status.textContent = text || '';
  }

  function showError(message) {
    error.textContent = message;
    error.classList.remove('hidden');
    setStatus('载入失败 —— 请换一条路重试。');
  }

  async function run(task, label) {
    if (busy) return;
    busy = true;
    bundledButton.disabled = true;
    uploadButton.disabled = true;
    error.textContent = '';
    error.classList.add('hidden');
    setStatus(label);
    try {
      const rom = await task();
      if (!rom || !rom.length) throw new Error('没有读到任何字节');
      close(rom);
    } catch (err) {
      // 失败**不关窗**：错误留在窗口里，按钮恢复可用。
      busy = false;
      bundledButton.disabled = false;
      uploadButton.disabled = false;
      showError(err && err.message ? err.message : String(err));
    }
  }

  function focusables() {
    return buttons.filter((node) => !node.disabled);
  }

  function close(rom) {
    if (!current) return;
    const done = current;
    current = null;
    done.overlay.remove();
    window.removeEventListener('keydown', done.onKeyDown, true);
    window.removeEventListener('focusin', done.onFocusIn, true);
    if (shell) {
      shell.removeAttribute('inert');
      shell.removeAttribute('aria-hidden');
    }
    done.resolve(rom || null);
  }

  document.body.appendChild(overlay);
  current = {
    overlay,
    promise,
    resolve: resolveGate,
    onKeyDown,
    onFocusIn,
  };

  // 焦点先放进窗口里（否则 inert 生效的一瞬间，焦点还在下面的内容上）。
  const first = focusables()[0] || box;
  if (first.focus) first.focus();

  return promise;
}

/**
 * `node` 在 `root` 的子树里吗？
 *
 * 自己写而不用 `Node.contains`：桩 DOM（无头自检）里没有这个方法，
 * 而且从 node 往上走 parentNode 在两边的行为一致。
 */
function contains(root, node) {
  let cursor = node;
  while (cursor) {
    if (cursor === root) return true;
    cursor = cursor.parentNode;
  }
  return false;
}
