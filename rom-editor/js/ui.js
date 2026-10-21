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

/** A labelled read-only statistic. */
export function stat(label, value, hint) {
  return el('div', { class: 'stat' }, [
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
