// Small DOM toolkit.  No build step, no framework: the editor has to run from
// a plain file:// URL on a machine that has nothing but a browser.

export function el(tag, props = {}, children = []) {
  const node = document.createElement(tag);
  // 说明性文字里用了 markdown 的粗体标记，而编辑器不渲染 markdown，
  // 星号会原样露出来。只在说明类容器里去掉，不动用户数据。
  const prose = PROSE_CLASSES.some((name) =>
    String((props && props.class) || '').includes(name));
  for (const [key, value] of Object.entries(props || {})) {
    if (value === null || value === undefined) continue;
    if (key === 'class') node.className = value;
    else if (key === 'text') node.textContent = prose ? stripStars(value) : value;
    else if (key === 'html') node.innerHTML = value;
    else if (key.startsWith('on') && typeof value === 'function') {
      node.addEventListener(key.slice(2).toLowerCase(), value);
    } else if (key === 'dataset') {
      Object.assign(node.dataset, value);
    } else if (key === 'style' && typeof value === 'object') {
      Object.assign(node.style, value);
    } else if (value === true) {
      node.setAttribute(key, '');
    } else if (value !== false) {
      node.setAttribute(key, value);
    }
  }
  for (const child of [].concat(children)) {
    if (child === null || child === undefined || child === false) continue;
    if (typeof child === 'string' || typeof child === 'number') {
      // 以前只处理 `text` 属性，**当子节点传进来时就漏出去了**
      // （素材域那句「但**资源内容本身**要另走导入流程」就是这么露的）。
      node.appendChild(document.createTextNode(prose ? stripStars(child) : String(child)));
    } else {
      node.appendChild(child);
    }
  }
  if (prose) stripStarsDeep(node);
  return node;
}

/** Remove markdown's bold markers from prose text. */
function stripStars(text) {
  return String(text === null || text === undefined ? '' : text).replace(/\*\*/g, '');
}

/**
 * The same, but for text that lives inside a child element.
 *
 * `el('p', {class:'section-note'}, [el('b', {text:'**加粗**'})])` — the
 * stars are in the child's own text, and the child does not know that its
 * parent is prose.  So the prose container cleans its subtree.
 */
function stripStarsDeep(node) {
  const kids = node.childNodes || node.children || [];
  for (const kid of kids) {
    if (!kid) continue;
    if (kid.nodeType === 3) {
      const text = kid.nodeValue !== undefined && kid.nodeValue !== null
        ? kid.nodeValue : kid.textContent;
      if (typeof text === 'string' && text.includes('**')) {
        const clean = stripStars(text);
        if (kid.nodeValue !== undefined) kid.nodeValue = clean;
        else kid.textContent = clean;
      }
      continue;
    }
    stripStarsDeep(kid);
    // 无头自检用的桩 DOM 把元素自己的文字直接放在属性里，没有子节点；
    // 真的浏览器里这里由上面的文本节点分支处理。
    const own = kid.childNodes || kid.children || [];
    if (!own.length) {
      const text = kid.textContent;
      if (typeof text === 'string' && text.includes('**')) {
        kid.textContent = stripStars(text);
      }
    }
  }
}

/** Containers whose text is prose (not user data). */
const PROSE_CLASSES = ['section-note', 'stat-hint', 'rule-note', 'field-hint', 'entry-card'];

export function clear(node) {
  while (node.firstChild) node.removeChild(node.firstChild);
  return node;
}

export function formatNumber(value) {
  if (value === null || value === undefined) return '';
  return String(value);
}

export function formatHex32(value) {
  return '0x' + (value >>> 0).toString(16).toUpperCase().padStart(8, '0');
}

export function formatOffset(value) {
  return '0x' + (value >>> 0).toString(16).toUpperCase();
}

/**
 * 让**整块**（一整行 / 一整张卡）都能触发同一个动作。
 *
 * 但**自带别的功能的地方不抢点击**：按钮、链接、输入框、下拉框、标签，
 * 以及标了 `data-no-area-click` 的元素 —— 点它们走它们自己的动作。
 *
 * 为什么要有它：入口做成一个小按钮，作者得**瞄准**才能点到；
 * 列表里一长串「打开」「编辑」尤其费眼。整块可点就没有瞄准的负担。
 * 键盘用户不受影响 —— 块里那个真正的按钮仍然可以 Tab 到。
 */
export function clickableArea(node, action) {
  // 有些无头自检的 DOM 桩没有 classList —— 加不上类名也不能崩。
  if (node.classList && typeof node.classList.add === 'function') {
    node.classList.add('area-clickable');
  }
  node.addEventListener('click', (event) => {
    if (hasOwnAction(event && event.target)) return;
    action(event);
  });
  return node;
}

/** 自带功能的标签（点它们不该触发外层的动作）。 */
const OWN_ACTION_TAGS = new Set([
  'BUTTON', 'A', 'INPUT', 'TEXTAREA', 'SELECT', 'OPTION', 'LABEL',
]);

/** 「自己就是入口」的标记类 —— 点它走它自己的动作。 */
const OWN_ACTION_CLASSES = ['xref-link'];

/** 从点的地方往上找：有没有自带功能的元素？ */
function hasOwnAction(target) {
  let node = target;
  while (node) {
    const tag = String(node.tagName || '').toUpperCase();
    if (OWN_ACTION_TAGS.has(tag)) return true;
    if (node.classList && typeof node.classList.contains === 'function'
        && OWN_ACTION_CLASSES.some((name) => node.classList.contains(name))) return true;
    if (node.dataset && node.dataset.noAreaClick !== undefined) return true;
    node = node.parentNode;
  }
  return false;
}

/** A labelled read-only statistic. */
export function stat(label, value, hint) {  return el('div', { class: 'stat' }, [
    el('div', { class: 'stat-label', text: label }),
    el('div', { class: 'stat-value', text: String(value) }),
    hint ? el('div', { class: 'stat-hint', text: hint }) : null,
  ]);
}

/** A simple modal dialog. */
export function modal(title, bodyNode, actions = []) {
  const overlay = el('div', { class: 'modal-overlay' });
  const box = el('div', { class: 'modal' }, [
    el('div', { class: 'modal-title', text: title }),
    el('div', { class: 'modal-body' }, [bodyNode]),
    el('div', { class: 'modal-actions' },
      actions.map((a) => el('button', {
        class: 'btn ' + (a.primary ? 'btn-primary' : ''),
        text: a.label,
        onclick: () => {
          const keep = a.onClick && a.onClick();
          if (!keep) overlay.remove();
        },
      }))),
  ]);
  overlay.appendChild(box);
  overlay.addEventListener('mousedown', (e) => {
    if (e.target === overlay) overlay.remove();
  });
  document.body.appendChild(overlay);
  return overlay;
}

export function toast(message, kind = 'info') {
  const node = el('div', { class: `toast toast-${kind}`, text: message });
  document.body.appendChild(node);
  setTimeout(() => node.classList.add('toast-out'), 3200);
  setTimeout(() => node.remove(), 3800);
  return node;
}

/** Download a Blob under `filename`. */
export function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const link = el('a', { href: url, download: filename });
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 4000);
}

/** Read a File as an ArrayBuffer. */
export function readFile(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(new Uint8Array(reader.result));
    reader.onerror = () => reject(reader.error);
    reader.readAsArrayBuffer(file);
  });
}
