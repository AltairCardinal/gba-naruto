// 载入状态条：ROM 槽 与 内容包 槽。
//
// **纯函数** —— 只画 DOM，不碰全局状态、不做 IO ⇒ 无头门禁能直接测它。
// 动作由调用方（app.js）通过 `actions` 传进来。
//
// 规则（用户定的）：
//   * **ROM 槽** —— 未载入时给**二选一**（内置原版 / 在本地浏览上传）；
//     载入后显示**绿底白 √**，并且**不再提供载入别的 ROM 的入口**：
//     要换 ROM 得先「导出修改后卸载 ROM」。
//   * **内容包槽** —— 未载入时给**二选一**（从 ROM 中解析 / 在本地浏览上传）；
//     载入后显示 **√** 并注明来源；有**未导出过的修改**时，
//     【导出】按钮**高亮**；点【载入】会先确认「改动会被覆盖」。

import { el, clear, modal } from './ui.js';

/** 绿底白 √ —— 载入成功的标记。 */
const OK_MARK = '√';

/**
 * 画载入状态条。
 *
 * @param {HTMLElement} romSlot
 * @param {HTMLElement} packSlot
 * @param {object} view {
 *   rom:  { loaded, name, size, sha },
 *   pack: { loaded, source, structures, texts, changed },
 * }
 * @param {object} actions {
 *   loadBundledRom, loadRomFile, unloadRom, parsePack, loadPack, exportPack,
 * }
 */
export function renderLoadBar(romSlot, packSlot, view, actions = {}) {
  if (!romSlot || !packSlot) return;
  clear(romSlot);
  clear(packSlot);

  // --- ROM ---------------------------------------------------------------
  romSlot.appendChild(el('span', { class: 'slot-label', text: 'ROM' }));
  if (view.rom && view.rom.loaded) {
    romSlot.appendChild(el('span', {
      class: 'slot-ok', text: OK_MARK, title: '原版 ROM 已载入（要换 ROM 请先卸载）',
    }));
    romSlot.appendChild(el('span', {
      class: 'slot-state',
      text: `${view.rom.name || 'base.gba'} · ${(view.rom.size || 0).toLocaleString()} 字节` +
        (view.rom.sha ? ` · sha256 ${view.rom.sha.slice(0, 12)}…` : ''),
    }));
    romSlot.appendChild(el('button', {
      class: 'btn btn-tiny',
      text: '导出修改后卸载 ROM',
      title: '先把改动构建成 ROM 下载下来，再卸载这个 ROM（卸载后才能载入别的 ROM）',
      onclick: actions.unloadRom,
    }));
  } else {
    romSlot.appendChild(el('button', {
      class: 'btn btn-tiny',
      text: '木叶战记熊组汉化版原版',
      title: '载入编辑器自带的原版 ROM（content/base-rom/base-rom.bin.gz）',
      onclick: actions.loadBundledRom,
    }));
    romSlot.appendChild(el('label', {
      class: 'btn btn-tiny', for: 'rom-file',
      title: '从本地选择一个 .gba 文件',
      text: '在本地浏览上传',
      onclick: actions.loadRomFile,
    }));
  }

  // --- 内容包 -------------------------------------------------------------
  packSlot.appendChild(el('span', { class: 'slot-label', text: '内容包' }));
  if (view.pack && view.pack.loaded) {
    packSlot.appendChild(el('span', {
      class: 'slot-ok', text: OK_MARK, title: '内容包已载入',
    }));
    packSlot.appendChild(el('span', {
      class: 'slot-state',
      text: `${view.pack.structures || 0} 结构 / ${view.pack.texts || 0} 文本表 · ` +
        sourceText(view.pack.source),
    }));
    packSlot.appendChild(el('button', {
      class: 'btn btn-tiny',
      text: '载入',
      title: '重新载入内容包（会覆盖当前改动）',
      onclick: actions.loadPack,
    }));
    if (view.pack.changed) {
      packSlot.appendChild(el('button', {
        class: 'btn btn-tiny btn-primary',
        text: '导出',
        title: '当前有未导出过的修改 —— 把内容包导出成文件',
        onclick: actions.exportPack,
      }));
    }
  } else {
    packSlot.appendChild(el('button', {
      class: 'btn btn-tiny',
      text: '从 ROM 中解析',
      title: '用当前载入的 ROM 解析出内容包',
      disabled: !(view.rom && view.rom.loaded),
      onclick: actions.parsePack,
    }));
    packSlot.appendChild(el('label', {
      class: 'btn btn-tiny', for: 'pack-file',
      title: '从本地选择一个内容包 .json 文件',
      text: '在本地浏览上传',
      onclick: actions.loadPackFile,
    }));
  }
}

/** 内容包来源的人话。 */
function sourceText(source) {
  if (source === 'rom') return '从 ROM 中解析';
  if (source === 'file') return '从本地文件上传';
  return '编辑器自带';
}

/**
 * 「载入会覆盖当前改动」的确认框。
 *
 * **「否」是高亮按钮** —— 丢数据是这个操作的主要风险，
 * 所以默认落点应该是「不覆盖」。
 *
 * @param {() => void} onYes 点了「是」之后做什么
 */
export function confirmOverwrite(onYes) {
  modal('载入会覆盖当前改动', el('div', { class: 'section-note' }, [
    el('div', { text: '当前有未导出过的修改，载入新内容包会导致当前变动被覆盖，是否确认？' }),
  ]), [
    { label: '否', primary: true, onClick: () => {} },
    { label: '是', onClick: onYes },
  ]);
}
