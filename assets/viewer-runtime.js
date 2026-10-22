/* ============================================================
   Viewer runtime: motion players, pagination, global search.
   Shared by every page; nothing here knows about a specific
   artifact family.
   ============================================================ */

/* ---------- 1. Motion: one player for GIF and for frame strips ----------

   The character action exports are inconsistent at the source: 14 characters
   ship an animated GIF, 21 ship only a horizontal PNG frame strip.  Both are
   presented through this one component so the viewer never shows an
   animation beside a still frame of the same kind of thing.
*/
function initMotion(root) {
  root.querySelectorAll('[data-motion]').forEach(function (el) {
    if (el.dataset.motionReady) return;
    el.dataset.motionReady = '1';

    var gif = el.dataset.gif;
    var strip = el.dataset.strip;
    var frames = parseInt(el.dataset.frames || '1', 10);
    var frameW = parseInt(el.dataset.frameWidth || '0', 10);
    var frameH = parseInt(el.dataset.frameHeight || '0', 10);

    // GIF: the browser animates it natively, nothing to do but pause on click.
    if (gif) {
      var img = el.querySelector('img');
      if (img) {
        img.src = gif;
        el.classList.add('is-motion');
        el.addEventListener('click', function () { img.classList.toggle('paused'); });
        el.title = '点击暂停 / 继续';
        return;
      }
    }

    // Frame strip: drive it with background-position on a fixed-size window.
    if (!strip || !frameW || !frameH) {
      el.classList.add('is-motion-static');
      return;
    }

    el.classList.add('is-motion');
    el.style.setProperty('--fw', frameW + 'px');
    el.style.setProperty('--fh', frameH + 'px');
    el.style.backgroundImage = 'url("' + strip + '")';
    el.style.backgroundSize = (frameW * frames) + 'px ' + frameH + 'px';
    el.title = '点击暂停 / 继续';

    // If the strip cannot be fetched, say so instead of leaving an empty
    // (apparently black) cell behind.
    var probe = new Image();
    probe.onload = function () {
      el.classList.add('is-motion-ready');
    };
    probe.onerror = function () {
      el.classList.add('is-motion-missing');
      el.innerHTML = '<span class="motion-err">帧条缺失</span>';
    };
    probe.src = strip;

    var index = 0;
    var timer = null;
    var fps = parseInt(el.dataset.fps || '10', 10);
    function paint() {
      el.style.backgroundPosition = (-index * frameW) + 'px 0';
    }
    function play() {
      if (timer) return;
      timer = setInterval(function () {
        index = (index + 1) % frames;
        paint();
      }, 1000 / fps);
    }
    function pause() { clearInterval(timer); timer = null; }
    el.addEventListener('click', function () { timer ? pause() : play(); });
    el.addEventListener('mouseenter', function () { if (!timer) paint(); });

    // Only animate what is actually on screen: 200 simultaneous intervals
    // would peg the CPU and is the reason large pages used to hang.
    if ('IntersectionObserver' in window) {
      var io = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) play(); else pause();
        });
      }, { rootMargin: '120px' });
      io.observe(el);
    } else {
      play();
    }
    paint();
  });
}

/* ---------- 2. Pagination ----------------------------------------------

   Every gallery is capped per page.  A page that renders a thousand <img>
   at once is unusable; the viewer keeps each page light and reveals more on
   demand.
*/
function initPagination(root) {
  root.querySelectorAll('[data-paginate]').forEach(function (box) {
    if (box.dataset.paginateReady) return;
    box.dataset.paginateReady = '1';

    var perPage = parseInt(box.dataset.paginate, 10) || 24;
    var items = Array.prototype.slice.call(box.children);
    var label = box.dataset.paginateLabel || '项';

    function show(count) {
      items.forEach(function (item, i) {
        item.style.display = i < count ? '' : 'none';
      });
      var totalPages = Math.ceil(items.length / perPage);
      var current = Math.min(Math.ceil(count / perPage), totalPages) || 1;
      info.textContent = '第 ' + current + ' / ' + totalPages + ' 页 · 共 ' +
        items.length + ' ' + label;
      more.style.display = count < items.length ? '' : 'none';
    }

    var controls = document.createElement('div');
    controls.className = 'pager';
    var info = document.createElement('span');
    info.className = 'pager-info';
    var more = document.createElement('button');
    more.className = 'pager-more';
    more.textContent = '加载更多';
    more.addEventListener('click', function () {
      var visible = items.filter(function (i) { return i.style.display !== 'none'; }).length;
      show(visible + perPage);
    });
    controls.appendChild(info);
    controls.appendChild(more);
    box.parentNode.insertBefore(controls, box.nextSibling);
    show(perPage);
  });
}

/* ---------- 3. Global search --------------------------------------------

   Searches a generated index of every section and every note, then jumps to
   the page that owns the hit.  Per-page filtering is not enough once the
   viewer spans nine documents.
*/
var SEARCH_INDEX = [];

function loadSearchIndex() {
  if (SEARCH_INDEX.length) return Promise.resolve(SEARCH_INDEX);
  return fetch('assets/search-index.json')
    .then(function (r) { return r.json(); })
    .then(function (d) { SEARCH_INDEX = d.entries || []; return SEARCH_INDEX; })
    .catch(function () { SEARCH_INDEX = []; return SEARCH_INDEX; });
}

function runGlobalSearch(query) {
  var panel = document.getElementById('searchPanel');
  if (!panel) return;
  var q = query.trim().toLowerCase();
  if (!q) { panel.style.display = 'none'; panel.innerHTML = ''; return; }

  loadSearchIndex().then(function (entries) {
    var hits = [];
    entries.forEach(function (e) {
      var hay = (e.title + ' ' + e.text + ' ' + e.key).toLowerCase();
      var at = hay.indexOf(q);
      if (at >= 0) {
        hits.push({
          entry: e,
          score: (e.title.toLowerCase().indexOf(q) >= 0 ? 0 : 1),
          snippet: hay.slice(Math.max(0, at - 40), at + 90)
        });
      }
    });
    hits.sort(function (a, b) { return a.score - b.score; });
    var top = hits.slice(0, 40);
    if (!top.length) {
      panel.innerHTML = '<div class="sp-empty">无匹配：' + query + '</div>';
    } else {
      panel.innerHTML =
        '<div class="sp-head">命中 ' + hits.length + ' 条，显示前 ' + top.length + ' 条</div>' +
        top.map(function (h) {
          return '<a class="sp-row" href="' + h.entry.page + (h.entry.anchor ? '#' + h.entry.anchor : '') + '">' +
            '<span class="sp-title">' + h.entry.title + '</span>' +
            '<span class="sp-where">' + h.entry.page + '</span>' +
            '<span class="sp-snip">…' + h.snippet + '…</span></a>';
        }).join('');
    }
    panel.style.display = 'block';
  });
}

/* ---------- 4. Boot ----------------------------------------------------*/
document.addEventListener('DOMContentLoaded', function () {
  var root = document.body;
  initMotion(root);
  initPagination(root);
  initLightbox();
  initFramePlayers(document.body);
  initSidebarSpy();
  initAnchorLanding();

  // Character switching and other views replace their container wholesale, so
  // freshly inserted motion elements would otherwise stay uninitialised and
  // render as empty (black) cells.  Watch for insertions and initialise them.
  if ('MutationObserver' in window) {
    var mo = new MutationObserver(function (records) {
      var touched = false;
      records.forEach(function (record) {
        if (record.addedNodes && record.addedNodes.length) touched = true;
      });
      if (touched) {
        initMotion(document.body);
        initPagination(document.body);
      }
    });
    mo.observe(root, { childList: true, subtree: true });
  }

  var input = document.getElementById('searchInput');
  var clear = document.getElementById('searchClearBtn');
  var panel = document.getElementById('searchPanel');
  if (input) {
    input.setAttribute('placeholder', '全站检索：角色 / 地址 / 公式 / 结论 / 产物族 (Ctrl+K)');
    input.addEventListener('input', function () {
      runGlobalSearch(input.value);
      if (clear) clear.style.display = input.value ? 'block' : 'none';
    });
  }
  if (clear && input) {
    clear.addEventListener('click', function () {
      input.value = '';
      clear.style.display = 'none';
      if (panel) { panel.style.display = 'none'; panel.innerHTML = ''; }
      input.focus();
    });
  }
  document.addEventListener('keydown', function (e) {
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
      e.preventDefault();
      if (input) { input.focus(); input.select(); }
    } else if (e.key === 'Escape' && panel && panel.style.display === 'block') {
      panel.style.display = 'none';
    }
  });
});

/* ---------- 4b. Frame-sequence player --------------------------------

   Some families ship one image per animation frame instead of a single
   sprite sheet.  ``data-frames`` is a pipe-separated list of frame URLs and
   the player cycles them, so an animation is not shown as a still.
*/
function initFramePlayers(root) {
  root.querySelectorAll('[data-frames]').forEach(function (el) {
    if (el.dataset.framesReady) return;
    el.dataset.framesReady = '1';
    var frames = (el.dataset.frames || '').split('|').filter(Boolean);
    if (!frames.length) return;
    var fps = parseInt(el.dataset.fps || '10', 10);
    // Optional per-frame hold counts (the family's own keyframe timing).
    var holds = (el.dataset.holds || '').split(',').map(function (h) {
      return Math.max(1, parseInt(h, 10) || 1);
    });
    var index = 0;
    var remaining = holds[0] || 1;
    el.style.backgroundImage = 'url("' + frames[0] + '")';
    el.style.backgroundSize = 'auto 100%';
    el.style.backgroundRepeat = 'no-repeat';
    el.title = '动画帧：' + frames.length + ' 帧（点击暂停/继续）';
    var timer = null;
    function paint() {
      el.style.backgroundImage = 'url("' + frames[index % frames.length] + '")';
    }
    function tick() {
      remaining -= 1;
      if (remaining > 0) return;
      index = (index + 1) % frames.length;
      remaining = holds[index] || 1;
      paint();
    }
    el.addEventListener('click', function () {
      if (timer) { clearInterval(timer); timer = null; }
      else { timer = setInterval(tick, 1000 / fps); }
    });
    if ('IntersectionObserver' in window) {
      var io = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting && !timer) {
            timer = setInterval(tick, 1000 / fps);
          } else if (!entry.isIntersecting && timer) {
            clearInterval(timer); timer = null;
          }
        });
      }, { rootMargin: '120px' });
      io.observe(el);
    } else {
      timer = setInterval(function () { index++; paint(); }, 1000 / fps);
    }
  });
}


/* ---------- 5. Lightbox: click any image to enlarge ------------------- */

var LIGHTBOX = null;

function ensureLightbox() {
  if (LIGHTBOX) return LIGHTBOX;
  var box = document.createElement('div');
  box.id = 'lightbox';
  box.className = 'lb';
  box.innerHTML =
    '<div class="lb-backdrop"></div>' +
    '<figure class="lb-figure">' +
    '  <img class="lb-image" alt="">' +
    '  <figcaption class="lb-caption"></figcaption>' +
    '</figure>' +
    '<button class="lb-close" title="关闭 (Esc)">✕</button>' +
    '<button class="lb-nav lb-prev" title="上一张 (←)">‹</button>' +
    '<button class="lb-nav lb-next" title="下一张 (→)">›</button>' +
    '<a class="lb-download" download>下载原图</a>';
  document.body.appendChild(box);
  LIGHTBOX = box;

  // Wire the controls.  They are created with innerHTML, so the handlers have
  // to be attached here -- without this the close and arrow buttons do nothing.
  var currentList = [];
  function currentIndex() {
    return parseInt(box.dataset.index, 10) || 0;
  }
  function step(delta) {
    if (!currentList.length) return;
    var next = (currentIndex() + delta + currentList.length) % currentList.length;
    showLightbox(currentList, next);
  }
  box.querySelector('.lb-close').addEventListener('click', function (e) {
    e.stopPropagation();
    closeLightbox();
  });
  box.querySelector('.lb-prev').addEventListener('click', function (e) {
    e.stopPropagation();
    step(-1);
  });
  box.querySelector('.lb-next').addEventListener('click', function (e) {
    e.stopPropagation();
    step(1);
  });
  // Clicking outside the image closes: the backdrop, and the figure's own
  // padding area (the figure covers most of the screen, so the backdrop is
  // only reachable in the narrow margins).
  box.querySelector('.lb-backdrop').addEventListener('click', function (e) {
    e.stopPropagation();
    closeLightbox();
  });
  box.querySelector('.lb-figure').addEventListener('click', function (e) {
    // Only the image itself counts as "inside"; the caption is outside it.
    if (e.target.closest('.lb-image')) return;
    e.stopPropagation();
    closeLightbox();
  });
  // The lightbox remembers the list it was opened with, for the arrow buttons.
  box._setList = function (list) { currentList = list; box._list = list; };
  return box;
}

function galleryImages(scope) {
  return Array.prototype.slice.call(
    (scope || document).querySelectorAll(
      '.tileset-item img, .vcard img, .fml-list img, .fam-sec img'
    )
  ).filter(function (img) {
    return !img.closest('#lightbox') && !img.closest('a');
  });
}

function openLightbox(img, group) {
  var box = ensureLightbox();
  var list = group || galleryImages(document);
  var index = Math.max(0, list.indexOf(img));
  showLightbox(list, index);
}

function showLightbox(list, index) {
  var box = ensureLightbox();
  if (!list.length) return;
  if (box._setList) box._setList(list);
  if (index < 0) index = 0;
  if (index >= list.length) index = 0;
  var img = list[index];
  box.querySelector('.lb-image').src = img.currentSrc || img.src;
  box.querySelector('.lb-caption').textContent =
    (index + 1) + ' / ' + list.length + '　' + (img.alt || '');
  var link = box.querySelector('.lb-download');
  link.href = img.currentSrc || img.src;
  link.setAttribute('download', '');
  box.classList.add('is-open');
  box.dataset.index = String(index);
}

function closeLightbox() {
  if (!LIGHTBOX) return;
  LIGHTBOX.classList.remove('is-open');
}

function initLightbox() {
  document.addEventListener('click', function (e) {
    var img = e.target;
    if (!(img instanceof HTMLImageElement)) return;
    if (img.closest('#lightbox')) return;
    if (img.closest('a')) return;
    if (!img.closest('.tileset-item, .vcard, .fam-sec, .fml-list')) return;
    e.preventDefault();
    var scope = img.closest('[data-paginate]') || document;
    openLightbox(img, galleryImages(scope));
  });

  document.addEventListener('keydown', function (e) {
    if (!LIGHTBOX || !LIGHTBOX.classList.contains('is-open')) return;
    var list = LIGHTBOX._list || galleryImages(document);
    if (e.key === 'Escape') { closeLightbox(); }
    else if (e.key === 'ArrowLeft') {
      showLightbox(list, (parseInt(LIGHTBOX.dataset.index, 10) - 1 + list.length) % list.length);
    } else if (e.key === 'ArrowRight') {
      showLightbox(list, (parseInt(LIGHTBOX.dataset.index, 10) + 1) % list.length);
    }
  });
}


/* ---------- 6. Sidebar scroll spy: the nav follows what you are reading ---

   The sidebar is generated from the real cards, so it already knows every
   anchor of every page.  What was missing is the link back the other way:
   nothing told the nav which card the reader was actually looking at, so the
   highlight stayed wherever the page happened to load.

   This picks the card under the reading line (just below the sticky header),
   marks that entry active, marks the group it belongs to as the current
   group, and scrolls the sidebar just far enough to keep the active entry in
   view.  The sidebar is scrolled by hand instead of with scrollIntoView(),
   because scrollIntoView() also scrolls the page and would fight the reader.
*/
function initSidebarSpy() {
  var sidebar = document.getElementById('leftSidebar');
  if (!sidebar) return;

  var all = Array.prototype.slice.call(sidebar.querySelectorAll('.sidebar-link'));
  if (!all.length) return;

  var here = document.body.getAttribute('data-page') || '';
  var entries = [];
  var hubLinks = [];

  all.forEach(function (link) {
    var href = link.getAttribute('href') || '';
    var file = href.split('#')[0];
    var anchor = link.getAttribute('data-anchor') ||
      (href.indexOf('#') >= 0 ? href.split('#').slice(1).join('#') : '');
    if (!anchor) { hubLinks.push(link); return; }
    // An entry for another page can never be the one being read.
    if (file !== here) return;
    var el = document.getElementById(anchor);
    if (!el) return;
    entries.push({ link: link, el: el });
  });
  if (!entries.length) return;

  // The group header of the page being viewed.
  var pageHub = null;
  hubLinks.forEach(function (link) {
    if ((link.getAttribute('href') || '').split('#')[0] === here) pageHub = link;
  });

  var active;          // undefined until the first pass
  var queued = false;

  function readingLine() {
    var header = document.querySelector('.top-bar');
    var offset = header ? header.getBoundingClientRect().height : 56;
    return window.scrollY + offset + 24;
  }

  function current() {
    var line = readingLine();
    var found = null;
    for (var i = 0; i < entries.length; i++) {
      var top = entries[i].el.getBoundingClientRect().top + window.scrollY;
      if (top <= line) found = entries[i];
    }
    return found;
  }

  // Keep the marked entry visible without touching the page scroll.
  function keepVisible(link) {
    var box = sidebar.getBoundingClientRect();
    var item = link.getBoundingClientRect();
    var pad = 16;
    if (item.top < box.top + pad) {
      sidebar.scrollTop -= (box.top + pad - item.top);
    } else if (item.bottom > box.bottom - pad) {
      sidebar.scrollTop += (item.bottom - (box.bottom - pad));
    }
  }

  function apply(entry) {
    if (entry === active) return;
    active = entry;
    all.forEach(function (link) { link.classList.remove('active'); });
    if (entry) {
      entry.link.classList.add('active');
      var group = entry.link.closest('.sidebar-group');
      var hub = group ? group.querySelector('.sidebar-hub') : null;
      hubLinks.forEach(function (link) {
        link.classList.toggle('current-group', link === hub);
      });
      keepVisible(entry.link);
    } else {
      // Above the first card: the page itself is the current entry.
      if (pageHub) pageHub.classList.add('active');
      hubLinks.forEach(function (link) { link.classList.remove('current-group'); });
    }
  }

  function update() {
    queued = false;
    apply(current());
  }

  function schedule() {
    if (queued) return;
    queued = true;
    window.requestAnimationFrame(update);
  }

  window.addEventListener('scroll', schedule, { passive: true });
  window.addEventListener('resize', schedule);
  window.addEventListener('hashchange', schedule);
  window.addEventListener('load', schedule);
  // The shared script clears the highlight on its own; let the spy re-sync.
  window.refreshSidebarSpy = update;
  update();
}


/* ---------- 7. Anchor landing correction --------------------------------

   A first visit to a page with a hash lands on the wrong card.  Measured on
   the data page: when the load event fired the browser had not jumped at all
   (scrollY was still 0, the document was only 3991px tall because the lazy
   images had no size yet), and by the time the images had settled the
   document was 10514px tall and the requested card had moved ~1000px down --
   so it ended up just below the fold instead of in front of the reader.

   So the landing is re-aligned until the layout stops moving.  The reader
   always wins: any real scroll input ends the correction.
*/
function initAnchorLanding() {
  var hash = window.location.hash.replace('#', '');
  if (!hash) return;
  var target = document.getElementById(hash);
  if (!target) return;

  var readerMoved = false;
  window.addEventListener('wheel', function () { readerMoved = true; },
                          { passive: true });
  window.addEventListener('touchmove', function () { readerMoved = true; },
                          { passive: true });
  window.addEventListener('keydown', function (e) {
    var k = e.key;
    if (k === 'ArrowUp' || k === 'ArrowDown' || k === 'PageUp' ||
        k === 'PageDown' || k === 'Home' || k === 'End' || k === ' ') {
      readerMoved = true;
    }
  });

  // Where the card is meant to sit: the CSS scroll-margin-top, so the title
  // clears the sticky header.  Read it from the CSS instead of repeating it.
  function wantedTop() {
    var margin = parseFloat(
      window.getComputedStyle(target).scrollMarginTop || '0') || 0;
    return margin;
  }

  var lastOffset = null;
  var stable = 0;
  var rounds = 0;

  function settle() {
    if (readerMoved) return;
    var box = target.getBoundingClientRect();
    var offset = Math.round(box.top + window.scrollY);
    if (offset === lastOffset) stable++; else { stable = 0; lastOffset = offset; }
    if (Math.abs(box.top - wantedTop()) > 4) {
      target.scrollIntoView({ block: 'start' });
    }
    rounds++;
    // Keep going while the layout is still moving, then stop.
    if (stable < 2 && rounds < 40) setTimeout(settle, 250);
  }

  if (document.readyState === 'complete') settle();
  else window.addEventListener('load', settle);
}
