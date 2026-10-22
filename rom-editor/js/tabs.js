// 通用页签面板：各域的「主界面 + 右侧配置」都用它。
//
// 为什么要有这个：
// 一个域的相关配置往往有好几类（战斗里就有战场布置 / 物件 / 出生点 /
// 胜负条件 / 剧情触发），全堆在右侧面板里会变成一条看不到头的长滚动。
// 页签把它们按类分开，一次只看一类，改完一类切到下一类。
//
// 三条约定：
// 1. **懒渲染** —— 只有当前页签的内容会被构建。右侧面板里有几个几十行的表，
//    一次性全建出来既慢又没必要。
// 2. **记住当前页签** —— 按 `key` 记在 localStorage 里，下次进来还在这一页。
// 3. **角标** —— 页签上可以显示「这一类改了几处」，让作者不用逐个点开找。

import { el, clear } from './ui.js';

/**
 * @typedef {object} TabSpec
 * @property {string} id      页签 id（同一组里唯一）
 * @property {string} label   页签上的字
 * @property {string} [hint]  悬停提示
 * @property {() => (string|null)} [badge] 角标文字（返回 null / undefined 就不显示）
 * @property {() => Node} render  内容构建函数
 */

/** 记住当前页签的 localStorage 前缀。 */
const STORE_PREFIX = 'editor.tabs.';

/**
 * 当前的内容包。
 *
 * 页签要订阅内容包的变更（角标「这一类改了几处」得在每次写入后跟上），
 * 但页签自己并不知道内容包是谁 —— 所以由 app.js 在建包时登记一次。
 */
let defaultPack = null;

/**
 * 登记当前的内容包（app.js 建包之后调一次）。
 *
 * @param {object} pack
 */
export function setDefaultPack(pack) {
  defaultPack = pack || null;
}

/**
 * 活着的页签面板。
 *
 * 每个面板都订阅了内容包的变更（角标要跟上）——
 * 视图被关掉以后那个订阅就没用了，所以要能退订，
 * 否则来回切视图会越攒越多。
 */
const livePanels = new Set();

/**
 * 退订所有活着的页签面板。
 *
 * app.js 重画整个界面前调一次：旧的面板马上要被丢掉，
 * 留着它的订阅只是白跑（每次写回都去更新一个已经不在页面上的角标）。
 */
export function disposeAllTabs() {
  for (const panel of [...livePanels]) {
    panel.dispose();
  }
  livePanels.clear();
}

/**
 * A tabbed panel.
 *
 * ```js
 * const tabs = new TabPanel([
 *   { id: 'setup',  label: '战场布置', render: () => setupNode() },
 *   { id: 'rules',  label: '胜负条件', render: () => rulesNode() },
 * ], { key: 'battle' });
 * host.appendChild(tabs.element);
 * tabs.setBadge('rules', '2');
 * ```
 */
export class TabPanel {
  /**
   * @param {TabSpec[]} tabs
   * @param {object} [options]
   * @param {string} [options.key]     记住当前页签用的 localStorage 键
   * @param {string} [options.active]  初始页签（不给就取记住的那个，再不给就第一个）
   * @param {(id: string) => void} [options.onChange] 切页签时的回调
   * @param {object} [options.pack]    内容包 —— 给了就会订阅它的变更，
   *                                   角标（「这一类改了几处」）在每次写入后自动跟上
   */
  constructor(tabs, options = {}) {
    this.options = options;
    this.tabs = [];
    this.activeId = null;
    this.badgeOverrides = new Map();
    this.badgeNodes = [];

    this.bar = el('div', { class: 'tab-bar', role: 'tablist' });
    this.body = el('div', { class: 'tab-body', role: 'tabpanel' });
    this.element = el('div', { class: 'tab-panel' }, [this.bar, this.body]);

    this.setTabs(tabs, options.active);

    // 内容包变了 → 角标要跟上。
    //
    // app.js 的 `onChange()` 只标脏**不重绘**，所以靠它刷新角标是不行的；
    // 这里直接订阅内容包自己的变更通知。
    const pack = options.pack || defaultPack;
    if (pack && typeof pack.onChange === 'function') {
      this.unlisten = pack.onChange(() => this.updateBadges());
    }
    livePanels.add(this);
  }

  /**
   * 退订：视图被关掉时叫。
   *
   * 不退订的话，每次打开这个视图都会多一个内容包变更的订阅者，
   * 写得越多跑得越多 —— 而且是在更新一个已经不在页面上的角标。
   */
  dispose() {
    if (this.unlisten) {
      this.unlisten();
      this.unlisten = null;
    }
    livePanels.delete(this);
  }

  /**
   * 换掉整组页签（数据变了、条目数变了时用）。
   *
   * @param {TabSpec[]} tabs
   * @param {string} [active] 指定要选中的页签；不给就尽量留在原来那一页
   */
  setTabs(tabs, active) {
    const previous = this.activeId;
    this.tabs = (tabs || []).filter((t) => t && t.id);
    this.renderBar();
    const wanted = active
      || (previous && this.has(previous) ? previous : null)
      || this.remembered()
      || (this.tabs[0] ? this.tabs[0].id : null);
    this.activeId = this.has(wanted) ? wanted : (this.tabs[0] ? this.tabs[0].id : null);
    this.renderBody();
    this.syncBar();
  }

  /** 有这个页签吗。 */
  has(id) {
    return this.tabs.some((t) => t.id === id);
  }

  /** 当前选中的页签 id。 */
  get active() {
    return this.activeId;
  }

  /** 当前选中的页签定义。 */
  get activeTab() {
    return this.tabs.find((t) => t.id === this.activeId) || null;
  }

  /**
   * 切到某个页签。
   *
   * @param {string} id
   * @param {boolean} [force] 已经在这页时也重新构建内容
   */
  setActive(id, force = false) {
    if (!this.has(id)) return false;
    const changed = this.activeId !== id;
    this.activeId = id;
    if (changed || force) this.renderBody();
    // 角标可能已经变了（内容包被改过）—— 切页签时顺手跟上。
    this.updateBadges();
    this.syncBar();
    if (changed) {
      this.remember(id);
      if (this.options.onChange) this.options.onChange(id);
    }
    return true;
  }

  /**
   * 重新构建当前页签的内容。
   *
   * 改完一个字段之后要调它 —— 内容里的「已改 N 处」这类统计才会跟上。
   */
  refresh() {
    this.renderBody();
    this.updateBadges();
  }

  /**
   * 给某个页签加角标。
   *
   * @param {string} id
   * @param {string|null} text  传 null 去掉角标
   */
  setBadge(id, text) {
    if (text === null || text === undefined || text === '') {
      this.badgeOverrides.delete(id);
    } else {
      this.badgeOverrides.set(id, String(text));
    }
    this.renderBar();
  }

  // --- 内部 ---------------------------------------------------------------

  renderBar() {
    clear(this.bar);
    this.badgeNodes = [];
    for (const tab of this.tabs) {
      const badge = this.badgeFor(tab);
      const badgeNode = badge
        ? el('span', { class: 'tab-badge', text: badge })
        : null;
      this.badgeNodes.push(badgeNode);
      const btn = el('button', {
        class: 'tab-btn',
        type: 'button',
        role: 'tab',
        title: tab.hint || tab.label,
        onclick: () => this.setActive(tab.id),
        onkeydown: (e) => this.onTabKey(e, tab.id),
      }, [
        el('span', { class: 'tab-btn-label', text: tab.label }),
        badgeNode,
      ]);
      this.bar.appendChild(btn);
    }
    // 重建完要把「当前是哪一页」的高亮补回去 ——
    // 不然 refresh 之后页签条会变成「一个都没选中」。
    this.syncBar();
  }

  /**
   * 只更新角标 —— 内容包变了以后不必重建整条页签条
   * （重建会把焦点从页签按钮上弄丢）。
   */
  updateBadges() {
    let changed = false;
    for (let i = 0; i < this.tabs.length; i += 1) {
      const tab = this.tabs[i];
      const badge = this.badgeFor(tab);
      const node = this.badgeNodes[i];
      if (!node) {
        if (badge) { changed = true; break; }
        continue;
      }
      if (!badge) { changed = true; break; }
      if (node.textContent !== badge) node.textContent = badge;
    }
    if (changed) this.renderBar();
  }

  badgeFor(tab) {
    if (this.badgeOverrides.has(tab.id)) return this.badgeOverrides.get(tab.id);
    if (!tab.badge) return null;
    try {
      const value = tab.badge();
      return value === null || value === undefined || value === '' ? null : String(value);
    } catch (err) {
      return null;
    }
  }

  syncBar() {
    const buttons = Array.from(this.bar.children);
    for (let i = 0; i < buttons.length; i += 1) {
      const on = i < this.tabs.length && this.tabs[i].id === this.activeId;
      buttons[i].className = on ? 'tab-btn active' : 'tab-btn';
      buttons[i].setAttribute('aria-selected', on ? 'true' : 'false');
      buttons[i].tabIndex = on ? 0 : -1;
    }
  }

  renderBody() {
    clear(this.body);
    const tab = this.activeTab;
    if (!tab) {
      this.body.appendChild(el('div', { class: 'empty', text: '没有可显示的内容。' }));
      return;
    }
    let node = null;
    try {
      node = tab.render();
    } catch (err) {
      node = el('div', { class: 'empty', text: `这一页渲染出错：${err && err.message ? err.message : err}` });
    }
    if (node) this.body.appendChild(node);
  }

  /** 左右方向键在页签之间移动。 */
  onTabKey(event, id) {
    if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return;
    event.preventDefault();
    const index = this.tabs.findIndex((t) => t.id === id);
    if (index < 0) return;
    const step = event.key === 'ArrowRight' ? 1 : -1;
    const next = this.tabs[(index + step + this.tabs.length) % this.tabs.length];
    if (!next) return;
    this.setActive(next.id);
    const buttons = Array.from(this.bar.children);
    const at = this.tabs.findIndex((t) => t.id === next.id);
    if (buttons[at] && buttons[at].focus) buttons[at].focus();
  }

  remembered() {
    const key = this.options.key;
    if (!key) return null;
    try {
      return window.localStorage.getItem(STORE_PREFIX + key);
    } catch (err) {
      return null;
    }
  }

  remember(id) {
    const key = this.options.key;
    if (!key) return;
    try {
      window.localStorage.setItem(STORE_PREFIX + key, id);
    } catch (err) {
      /* 隐私模式下 localStorage 会抛 —— 记住页签不是必需功能，忽略即可 */
    }
  }
}

/**
 * 造一个页签面板的便捷函数。
 *
 * @param {TabSpec[]} tabs
 * @param {object} [options] 同 TabPanel 的 options
 * @returns {TabPanel}
 */
export function tabPanel(tabs, options = {}) {
  return new TabPanel(tabs, options);
}
