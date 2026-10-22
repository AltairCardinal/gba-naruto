// 通用卡片堆：右侧面板按类别纵向排开，一个滚动页面看完所有可改的东西。
//
// 为什么不叫「页签」：
// 页签把别的类别**藏起来** —— 作者看到「成长」这一页时，
// 不知道还有几类东西没看，来回比对还要重新滚。卡片全都摆在页面上，
// 往下滚就是全部。
//
// 一个域的右侧通常是这么排的：
//
//   ┌ 战场布置            已改 0 处 ┐
//   │ 这张战场多大、底图是哪一张      │
//   └───────────────────────────────┘
//   ┌ 战场物件            已改 2 处 ┐
//   │ 槽 类别 内容 X Y ↗             │
//   └───────────────────────────────┘
//
// 类别名 + 改动数在卡片头上；内容在卡片体里。

import { el, clear } from './ui.js';

/**
 * @typedef {object} CardSpec
 * @property {string} id      卡片 id（同一组里唯一）
 * @property {string} label   卡片头的标题（中文）
 * @property {string} [hint]  卡片头下的一行说明：这组东西是干嘛的
 * @property {() => (string|null)} [badge] 角标（「这一类改了几处」）
 * @property {() => Node} render  内容构建函数
 */

/**
 * 当前的内容包。
 *
 * 卡片要订阅内容包的变更（角标得在每次写入后跟上），
 * 但卡片自己并不知道内容包是谁 —— 所以由 app.js 在建包时登记一次。
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
 * 活着的卡片堆。
 *
 * 每个都订阅了内容包的变更（角标要跟上）—— 视图被关掉以后那个订阅就没用了，
 * 所以要能退订，否则来回切视图会越攒越多。
 */
const liveStacks = new Set();

/**
 * 退订所有活着的卡片堆。
 *
 * app.js 重画整个界面前调一次：旧的面板马上要被丢掉，
 * 留着它的订阅只是白跑。
 */
export function disposeAllCards() {
  for (const stack of [...liveStacks]) {
    stack.dispose();
  }
  liveStacks.clear();
}

/**
 * 一摞卡片。
 *
 * ```js
 * const cards = new CardStack([
 *   { id: 'setup', label: '战场布置', hint: '…', badge: () => '2', render: () => node },
 *   { id: 'rules', label: '胜负条件', render: () => node },
 * ], { pack });
 * host.appendChild(cards.element);
 * ```
 */
export class CardStack {
  /**
   * @param {CardSpec[]} cards
   * @param {object} [options]
   * @param {object} [options.pack] 内容包 —— 给了就会订阅它的变更，角标自动跟上
   */
  constructor(cards, options = {}) {
    this.options = options;
    this.cards = [];
    this.badgeNodes = new Map();
    this.badgeOverrides = new Map();
    this.host = el('div', { class: 'card-stack' });
    this.setCards(cards);

    const pack = options.pack || defaultPack;
    if (pack && typeof pack.onChange === 'function') {
      this.unlisten = pack.onChange(() => this.updateBadges());
    }
    liveStacks.add(this);
  }

  /**
   * 换掉整组卡片（数据变了、条目数变了时用）。
   *
   * @param {CardSpec[]} cards
   */
  setCards(cards) {
    this.cards = (cards || []).filter((c) => c && c.id);
    this.render();
  }

  /** 卡片堆的根节点（挂到面板上）。 */
  get element() {
    return this.host;
  }

  /**
   * 重新构建全部卡片。
   *
   * 改完数据后要调它 —— 内容里的「已改 N 处」这类统计才会跟上。
   */
  refresh() {
    this.render();
  }

  /**
   * 给某个卡片加角标。
   *
   * @param {string} id
   * @param {string|null} text 传 null 去掉角标
   */
  setBadge(id, text) {
    if (text === null || text === undefined || text === '') {
      this.badgeOverrides.delete(id);
    } else {
      this.badgeOverrides.set(id, String(text));
    }
    this.updateBadges();
  }

  /** 退订：视图被关掉时叫（app.js 在重画前统一调）。 */
  dispose() {
    if (this.unlisten) {
      this.unlisten();
      this.unlisten = null;
    }
    liveStacks.delete(this);
  }

  // --- 内部 ---------------------------------------------------------------

  render() {
    clear(this.host);
    this.badgeNodes = new Map();
    for (const card of this.cards) {
      const badge = this.badgeFor(card);
      const badgeNode = badge
        ? el('span', { class: 'card-badge', text: badge })
        : null;
      this.badgeNodes.set(card.id, badgeNode);
      let body = null;
      try {
        body = card.render();
      } catch (err) {
        body = el('div', {
          class: 'empty',
          text: `这一块渲染出错：${err && err.message ? err.message : err}`,
        });
      }
      this.host.appendChild(el('section', { class: 'editor-card' }, [
        el('div', { class: 'editor-card-head' }, [
          el('h3', { class: 'editor-card-title', text: card.label }),
          badgeNode,
        ]),
        card.hint ? el('p', { class: 'editor-card-hint', text: card.hint }) : null,
        el('div', { class: 'editor-card-body' }, body ? [body] : []),
      ]));
    }
  }

  badgeFor(card) {
    if (this.badgeOverrides.has(card.id)) return this.badgeOverrides.get(card.id);
    if (!card.badge) return null;
    try {
      const value = card.badge();
      return value === null || value === undefined || value === '' ? null : String(value);
    } catch (err) {
      return null;
    }
  }

  /**
   * 只更新角标 —— 内容包变了以后不必重建整摞卡片。
   */
  updateBadges() {
    let changed = false;
    for (const card of this.cards) {
      const badge = this.badgeFor(card);
      const node = this.badgeNodes.get(card.id);
      if (!node) {
        if (badge) { changed = true; break; }
        continue;
      }
      if (!badge) { changed = true; break; }
      if (node.textContent !== badge) node.textContent = badge;
    }
    if (changed) this.render();
  }
}

/**
 * 造一个卡片堆的便捷函数。
 *
 * @param {CardSpec[]} cards
 * @param {object} [options]
 * @returns {CardStack}
 */
export function cardStack(cards, options = {}) {
  return new CardStack(cards, options);
}
