// Hub -> page map.  switchHub() navigates across pages and only scrolls in
    // place when the target already lives on this document.
    const VIEWER_PAGES = {
      "progress": "reverse-engineering-results.html",
      "visuals": "reverse-engineering-visuals.html",
      "battle": "reverse-engineering-battle.html",
      "story": "reverse-engineering-story.html",
      "data": "reverse-engineering-data.html",
      "engineering": "reverse-engineering-engineering.html",
      "formulas": "reverse-engineering-formulas.html",
      "conclusions": "reverse-engineering-conclusions.html",
      "dataindex": "reverse-engineering-data-index.html",
    };

    const VIEWER_PAGE = document.body.getAttribute('data-page');
    const HUB_FOR_PAGE = Object.keys(VIEWER_PAGES).find(
      hub => VIEWER_PAGES[hub] === VIEWER_PAGE
    ) || 'progress';
    let currentActiveHub = HUB_FOR_PAGE;

    // Where the shared assets live, relative to the page.  The pages sit in
    // docs/ in the repository and at the site root once published, so this
    // is one constant instead of a hard-coded "../" in every place that
    // builds a path at runtime; the publish build rewrites it to ''.
    const ASSET_BASE = '';

    function switchHub(hubId, targetAnchor) {
      const file = VIEWER_PAGES[hubId];
      if (!file) return;
      const here = file.split('#')[0];
      if (here !== VIEWER_PAGE) {
        window.location.href = targetAnchor ? file + '#' + targetAnchor : file;
        return;
      }
      currentActiveHub = hubId;
      markActive(targetAnchor || null, here);
      if (targetAnchor) {
        const el = document.getElementById(targetAnchor);
        if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
      } else {
        window.scrollTo({ top: 0, behavior: 'smooth' });
      }
    }

    function markActive(targetAnchor, here) {
      document.querySelectorAll('.sidebar-link').forEach(link => {
        const href = link.getAttribute('href') || '';
        link.classList.toggle('active',
          targetAnchor ? href.endsWith('#' + targetAnchor)
                       : href === here);
      });
      // The scroll spy owns the highlight while the reader scrolls; let it
      // re-derive instead of leaving the two out of step.
      if (window.refreshSidebarSpy) window.refreshSidebarSpy();
    }

    // Restores the sidebar highlight after a reload or a cross-page anchor jump.
    function restoreActiveFromLocation() {
      const hash = window.location.hash.replace('#', '');
      const here = VIEWER_PAGE;
      document.querySelectorAll('.sidebar-link').forEach(link => {
        const href = link.getAttribute('href') || '';
        if (href.endsWith('#' + hash) || (href === here && !hash)) {
          link.classList.add('active');
        }
      });
    }

    // Restores every card on this page after a search is cleared.  This must
    // never call switchHub(), which would navigate to another page.
    function resetCards() {
      document.querySelectorAll('.category-section').forEach(sec => {
        sec.style.display = '';
      });
      document.querySelectorAll('.card').forEach(card => {
        card.style.display = '';
      });
      markActive(null, VIEWER_PAGE);
    }


    function copyAddr(addr) {
      navigator.clipboard.writeText(addr);
      const toast = document.getElementById('toast');
      toast.textContent = '已复制: ' + addr;
      toast.classList.add('show');
      setTimeout(() => toast.classList.remove('show'), 1800);
    }

    function copyCurrentUrl() {
      navigator.clipboard.writeText(window.location.href);
      const toast = document.getElementById('toast');
      toast.textContent = '已复制控制台页面链接';
      toast.classList.add('show');
      setTimeout(() => toast.classList.remove('show'), 1800);
    }

    function toggleSidebar() {
      document.body.classList.toggle('sidebar-collapsed');
    }


    function clearSearch() {
      document.getElementById('searchInput').value = '';
      document.getElementById('searchClearBtn').style.display = 'none';
      resetCards();
    }

    function handleSearch() {
      const query = document.getElementById('searchInput').value.trim().toLowerCase();
      const clearBtn = document.getElementById('searchClearBtn');
      const sections = document.querySelectorAll('.category-section');

      if (!query) {
        clearBtn.style.display = 'none';
        resetCards();
        return;
      }

      clearBtn.style.display = 'block';

      // Each hub is its own page, so search filters this page's cards.
      sections.forEach(sec => {
        let secHasMatch = false;
        const cards = sec.querySelectorAll('.card');

        cards.forEach(card => {
          const text = card.textContent.toLowerCase();
          if (text.includes(query)) {
            card.style.display = '';
            secHasMatch = true;
          } else {
            card.style.display = 'none';
          }
        });

        sec.style.display = secHasMatch ? 'block' : 'none';
      });
    }

    // Keyboard shortcuts
    document.addEventListener('keydown', (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        document.getElementById('searchInput').focus();
      } else if (e.key === 'Escape' && document.activeElement === document.getElementById('searchInput')) {
        clearSearch();
        document.getElementById('searchInput').blur();
      }
    });

    function selectStudioChar(charId) {
      const data = STUDIO_DATA[charId];
      if (!data) return;

      document.querySelectorAll('.char-chip').forEach(btn => btn.classList.remove('active'));
      const activeBtn = document.querySelector(`.char-chip[onclick*="selectStudioChar(${charId})"]`);
      if (activeBtn) activeBtn.classList.add('active');

      const vp = document.getElementById('studioViewport');
      const actionNames = {
        "locomotion": "四向位移步态",
        "attack1": "普攻连击 (Combo)",
        "attack2": "重击击退 (Strike)",
        "charge": "结印蓄力 (Chakra)",
        "cast": "奥义释放 (Jutsu)",
        "victory": "胜利姿态 (Victory)",
        "hurt": "受创击退 (Hurt)",
        "guard": "防御格挡 (Guard)",
        "defeat": "倒地击溃 (Defeat)"
      };

      let actionCardsHtml = '';
      for (const [k, name] of Object.entries(actionNames)) {
        const act = data.actions[k];
        if (act) {
          const gif = act.gif_path;
          const media = gif
            ? `<img src="${ASSET_BASE}${gif}" alt="${name}">`
            : `<span class="is-motion" data-motion data-strip="${ASSET_BASE}${act.strip_path}" data-frames="${act.frames_count}" data-frame-width="64" data-frame-height="64" data-fps="10"></span>`;
          actionCardsHtml += `
            <div class="studio-act-card" onclick="viewActionStrip('${act.strip_path}', '${name}')">
              <div class="studio-act-title">${name} (${act.frames_count}帧)${gif ? '' : ' · 帧条'}</div>
              <div class="studio-act-img-wrap">${media}</div>
            </div>`;
        }
      }

      // Per-character portrait binding is intentionally absent: the only
      // evidence-backed binding is battle scripts -> (record, variant) in the
      // 0x5A4DEC matrix.  Character names were a guess on the disproved
      // 0x5A4E14 reading, so this pane points at the verified matrix instead.
      const portraitsHtml = `
            <div style="color:var(--text-secondary); font-size:0.82rem; line-height:1.6; padding:6px 4px;">
              <div style="margin-bottom:8px;">该角色的立绘<strong>不按姓名绑定</strong>：唯一有证据的绑定是战斗脚本 → <code>(记录, 变体)</code> 指向 <code>0x5A4DEC</code> 矩阵。</div>
              <div style="margin-bottom:8px;">早前版本按中文姓名把立绘挂到角色身上，该映射源自已被证伪的 <code>0x5A4E14</code> 155×16 读法，故已移除。</div>
              <a class="tag tag-cyan" style="text-decoration:none;" href="javascript:void(0)" onclick="switchHub('visuals','sec-portraits-poster')">前往已验证的 311 变体立绘矩阵总集 →</a>
            </div>`;

      vp.innerHTML = `
        <div class="studio-header">
          <div class="studio-char-info">
            <div class="studio-char-name">${data.zh_name} <span class="studio-char-en">${data.en_name}</span></div>
            <div class="studio-char-meta">
              <span>角色编号: <strong>#${data.id < 10 ? '0' + data.id : data.id}</strong></span>
              <span>描述表起始行: <strong>${data.start_row}</strong></span>
              <span>调色板地址: <code class="addr-badge" onclick="copyAddr('${data.pal_offset}')">${data.pal_offset}</code></span>
            </div>
          </div>
          <div>
            <a href="${ASSET_BASE}${data.matrix_sheet}" target="_blank" class="tag tag-cyan" style="text-decoration:none; font-size:0.8rem;">查看全套动作图谱 ↗</a>
          </div>
        </div>

        <div class="studio-body">
          <div class="studio-actions-pane">
            <div class="studio-pane-title">🎮 9 大行动状态循环动图 (点击查看完整切片)</div>
            <div class="studio-act-grid">
              ${actionCardsHtml}
            </div>
          </div>
          <div class="studio-portraits-pane">
            <div class="studio-pane-title">🎭 角色立绘绑定说明</div>
            <div class="studio-portrait-list">
              ${portraitsHtml}
            </div>
          </div>
        </div>

        <div class="studio-strip-preview" id="studioStripPreview" style="display:none;">
          <div class="studio-pane-title" id="stripPreviewTitle">动作切片预览</div>
          <div class="studio-strip-img-wrap">
            <img id="stripPreviewImg" src="" style="image-rendering:pixelated; max-width:100%; height:auto;">
          </div>
        </div>
      `;
      if (window.initMotion) window.initMotion(document.body);
    }

    function viewActionStrip(stripPath, actionName) {
      const box = document.getElementById('studioStripPreview');
      const img = document.getElementById('stripPreviewImg');
      const title = document.getElementById('stripPreviewTitle');
      if (box && img && title) {
        box.style.display = 'block';
        img.src = ASSET_BASE + stripPath;
        title.textContent = '动作完整帧切片: ' + actionName;
        box.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      }
    }

    // Initialize with Progress View & Naruto
    window.addEventListener('DOMContentLoaded', () => {
      restoreActiveFromLocation();
      if (document.getElementById('charSelectorBar')) selectStudioChar(0);
    });
