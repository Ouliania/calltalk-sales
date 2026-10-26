// content.js - OkoCRM Mail Filter & Search + Sidebar Organizer + Thread & Later Pills (Call-Talk)
(function () {
  const DEFAULT_CODES = [
    '1Vf6ZV1',
    '9mBA4U0',
    'JdFpDtJ',
    'Jx8gasS',
    'mp5WvVX',
    'icKKRxR',
    'nYVUhOn',
    'eonvzb4',
    'cc8OzlS',
    'uELDGph',
    'ZLH0hVB',
    'kx9rx6E',
    'O6VBbdu',
    '2FAGSWY',
    'wVQHpag'
  ];

  let warmupCodes = [...DEFAULT_CODES];
  let hideWarmupEnabled = true;
  let hideBouncesEnabled = true;
  let outreachFolderExpanded = false;
  let onlyMarkedFilter = false;
  let rowMarks = {}; // rowKey -> 'later'
  let searchQuery = '';
  let identifiedWarmupIds = new Set();
  let identifiedWarmupSubjects = new Set();
  let hookCachedCount = 0;
  let hookSampleKeys = [];
  let hookSampleLen = 0;
  let hookHasDetailTpl = false;
  let hookDetailTpl = '';
  let hookCheckedCount = 0;
  let hookCachedBotCount = 0;
  let hookDebugUrls = [];

  // Strictly check if we are on https://client-onkfic.okocrm.com/mail/inbox
  function isMailInboxPage() {
    return window.location.pathname.startsWith('/mail/inbox') || window.location.href.includes('/mail/inbox');
  }

  function readSharedHookState() {
    try {
      const raw = document.documentElement.getAttribute('data-ct-state');
      if (!raw) return;
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed.ids)) {
        parsed.ids.forEach(id => identifiedWarmupIds.add(String(id)));
      }
      if (Array.isArray(parsed.subjects)) {
        parsed.subjects.forEach(s => identifiedWarmupSubjects.add(String(s).toLowerCase()));
      }
      if (Array.isArray(parsed.discoveredCodes)) {
        let addedNew = false;
        for (const dc of parsed.discoveredCodes) {
          const clean = String(dc || '').trim();
          if (clean && !warmupCodes.some(c => c.toLowerCase() === clean.toLowerCase())) {
            warmupCodes.push(clean);
            addedNew = true;
          }
        }
        if (addedNew) {
          chrome.storage.local.set({ warmupCodes });
          updateSettingsBtn();
        }
      }
      if (typeof parsed.hasDetailTpl === 'boolean') {
        hookHasDetailTpl = parsed.hasDetailTpl;
      }
      if (typeof parsed.detailTpl === 'string') {
        hookDetailTpl = parsed.detailTpl;
      }
      if (typeof parsed.checkedCount === 'number') {
        hookCheckedCount = parsed.checkedCount;
      }
      if (typeof parsed.cachedBotCount === 'number') {
        hookCachedBotCount = parsed.cachedBotCount;
      }
      if (Array.isArray(parsed.debugUrls)) {
        hookDebugUrls = parsed.debugUrls;
      }
      if (typeof parsed.cachedCount === 'number') {
        hookCachedCount = parsed.cachedCount;
      }
      if (Array.isArray(parsed.sampleKeys)) {
        hookSampleKeys = parsed.sampleKeys;
      }
      if (typeof parsed.sampleLen === 'number') {
        hookSampleLen = parsed.sampleLen;
      }
      updateScannerBadge();
    } catch (e) {}
  }

  function syncWithHook() {
    try {
      document.documentElement.setAttribute('data-ct-codes', JSON.stringify(warmupCodes));
      window.dispatchEvent(new Event('CT_SYNC'));
      document.dispatchEvent(new Event('CT_SYNC'));
      readSharedHookState();
    } catch (e) {}
  }

  chrome.storage.local.get(['warmupCodes', 'hideWarmupEnabled', 'hideBouncesEnabled', 'outreachFolderExpanded', 'rowMarks'], (data) => {
    if (data.warmupCodes && Array.isArray(data.warmupCodes) && data.warmupCodes.length > 0) {
      const existing = data.warmupCodes.map(c => String(c).trim()).filter(Boolean);
      warmupCodes = Array.from(new Set([...DEFAULT_CODES, ...existing]));
    } else {
      warmupCodes = [...DEFAULT_CODES];
    }
    chrome.storage.local.set({ warmupCodes });

    if (data.hideWarmupEnabled !== undefined) {
      hideWarmupEnabled = data.hideWarmupEnabled;
    }

    if (data.hideBouncesEnabled !== undefined) {
      hideBouncesEnabled = data.hideBouncesEnabled;
    }

    if (data.outreachFolderExpanded !== undefined) {
      outreachFolderExpanded = data.outreachFolderExpanded;
    }

    if (data.rowMarks && typeof data.rowMarks === 'object') {
      rowMarks = data.rowMarks;
    }

    try {
      const savedIds = localStorage.getItem('ct_cached_warmup_ids');
      if (savedIds) JSON.parse(savedIds).forEach(id => identifiedWarmupIds.add(String(id)));

      const savedSubs = localStorage.getItem('ct_cached_warmup_subs');
      if (savedSubs) JSON.parse(savedSubs).forEach(s => identifiedWarmupSubjects.add(String(s).toLowerCase()));
    } catch (e) {}

    syncWithHook();
    updateToolbarVisibility();
    updateSettingsBtn();
    doScanAndFilter();
  });

  function onHookUpdated() {
    readSharedHookState();
    if (isMailInboxPage()) scanAndFilter();
  }
  window.addEventListener('CT_HOOK_UPDATED', onHookUpdated);
  document.addEventListener('CT_HOOK_UPDATED', onHookUpdated);

  chrome.storage.onChanged.addListener((changes, area) => {
    if (area === 'local') {
      if (changes.warmupCodes) {
        warmupCodes = (changes.warmupCodes.newValue || []).map(c => String(c).trim()).filter(Boolean);
        updateSettingsBtn();
      }
      if (changes.hideWarmupEnabled !== undefined) {
        hideWarmupEnabled = changes.hideWarmupEnabled.newValue;
        const toggle = document.getElementById('ct-filter-toggle');
        if (toggle) toggle.checked = hideWarmupEnabled;
      }
      if (changes.hideBouncesEnabled !== undefined) {
        hideBouncesEnabled = changes.hideBouncesEnabled.newValue;
        const bouncesBtn = document.getElementById('ct-bounces-filter-btn');
        if (bouncesBtn) bouncesBtn.classList.toggle('ct-active', hideBouncesEnabled);
      }
      if (changes.rowMarks && changes.rowMarks.newValue) {
        rowMarks = changes.rowMarks.newValue;
      }
      syncWithHook();
      if (isMailInboxPage()) doScanAndFilter();
    }
  });

  function updateToolbarVisibility() {
    const onInbox = isMailInboxPage();
    let toolbar = document.getElementById('ct-mail-filter-toolbar');

    if (!onInbox) {
      if (toolbar) toolbar.style.display = 'none';
      const modal = document.getElementById('ct-settings-modal');
      if (modal) modal.remove();
      return;
    }

    if (!toolbar) {
      initUI();
      toolbar = document.getElementById('ct-mail-filter-toolbar');
    }
    if (toolbar) {
      toolbar.style.display = 'flex';
    }
  }

  function updateScannerBadge() {
    const badge = document.getElementById('ct-scanner-badge');
    if (!badge) return;
    if (hookHasDetailTpl) {
      badge.className = 'ct-scanner-badge ct-scan-active';
      badge.textContent = '✓ Сканер активен';
      badge.title = `Автосканер активен: проверяет невидимые концовки писем.\nШаблон: ${hookDetailTpl}`;
    } else {
      badge.className = 'ct-scanner-badge ct-scan-pending';
      badge.textContent = '👆 Нажмите на 1 письмо';
      badge.title = 'Нажмите на любое 1 письмо (например, Corium), чтобы сканер обучился и скрыл остальных ботов';
    }
  }

  function initUI() {
    if (document.getElementById('ct-mail-filter-toolbar')) return;

    const toolbar = document.createElement('div');
    toolbar.id = 'ct-mail-filter-toolbar';
    toolbar.innerHTML = `
      <div class="ct-filter-toggle-wrap" title="Скрывать прогревочные письма Trigga">
        <label class="ct-switch">
          <input type="checkbox" id="ct-filter-toggle" ${hideWarmupEnabled ? 'checked' : ''}>
          <span class="ct-slider"></span>
        </label>
        <span class="ct-toggle-label">Скрыть прогрев</span>
        <span class="ct-counter-badge" id="ct-hidden-count" style="display: none;">0</span>
      </div>

      <span id="ct-scanner-badge" class="ct-scanner-badge ${hookHasDetailTpl ? 'ct-scan-active' : 'ct-scan-pending'}" title="${hookHasDetailTpl ? 'Автосканер активен: проверяет невидимые концовки писем' : 'Нажмите на любое 1 письмо (например, Corium), чтобы сканер обучился и скрыл остальных ботов'}">
        ${hookHasDetailTpl ? '✓ Сканер активен' : '👆 Нажмите на 1 письмо'}
      </span>

      <button id="ct-bounces-filter-btn" class="ct-btn-bounces-filter ${hideBouncesEnabled ? 'ct-active' : ''}" title="В 1 клик скрыть или показать технические ошибки доставки (Mailer-Daemon, Недоставленное сообщение)">
        <span class="ct-dot ct-dot-rose"></span>
        <span>Скрыть отбивки</span>
        <span id="ct-bounces-count" style="display: none;">0</span>
      </button>

      <div class="ct-divider"></div>

      <button id="ct-marked-filter-btn" class="ct-btn-marked-filter" title="Показать письма с пометкой «Ответить позже»">
        <span class="ct-dot ct-dot-amber"></span>
        <span>Ответить позже</span>
        <span id="ct-marked-count">0</span>
      </button>

      <div class="ct-search-box">
        <svg class="ct-search-icon" viewBox="0 0 24 24" width="13" height="13" stroke="currentColor" stroke-width="2" fill="none"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
        <input type="text" id="ct-search-input" placeholder="Поиск по письмам..." value="${searchQuery}">
        <button id="ct-search-clear" title="Очистить поиск" style="display: none;">&times;</button>
      </div>

      <button id="ct-settings-btn" class="ct-btn-settings" title="Настройки кодов прогрева Trigga">
        <span class="ct-dot ct-dot-indigo"></span>
        <span id="ct-settings-btn-text">Коды · ${warmupCodes.length}</span>
      </button>
    `;

    document.body.appendChild(toolbar);

    const toggle = document.getElementById('ct-filter-toggle');
    toggle.addEventListener('change', (e) => {
      hideWarmupEnabled = e.target.checked;
      chrome.storage.local.set({ hideWarmupEnabled });
      doScanAndFilter();
    });

    const bouncesBtn = document.getElementById('ct-bounces-filter-btn');
    bouncesBtn.addEventListener('click', () => {
      hideBouncesEnabled = !hideBouncesEnabled;
      bouncesBtn.classList.toggle('ct-active', hideBouncesEnabled);
      chrome.storage.local.set({ hideBouncesEnabled });
      doScanAndFilter();
    });

    const markedBtn = document.getElementById('ct-marked-filter-btn');
    markedBtn.addEventListener('click', () => {
      onlyMarkedFilter = !onlyMarkedFilter;
      markedBtn.classList.toggle('ct-active', onlyMarkedFilter);
      doScanAndFilter();
    });

    const searchInput = document.getElementById('ct-search-input');
    const searchClear = document.getElementById('ct-search-clear');

    searchInput.addEventListener('input', (e) => {
      searchQuery = e.target.value.trim().toLowerCase();
      searchClear.style.display = searchQuery ? 'block' : 'none';
      doScanAndFilter();
    });

    searchClear.addEventListener('click', () => {
      searchInput.value = '';
      searchQuery = '';
      searchClear.style.display = 'none';
      doScanAndFilter();
    });

    document.getElementById('ct-settings-btn').addEventListener('click', openSettingsModal);
  }

  function updateSettingsBtn() {
    const btnText = document.getElementById('ct-settings-btn-text');
    if (btnText) btnText.innerText = `Коды · ${warmupCodes.length}`;
  }

  function openSettingsModal() {
    let modal = document.getElementById('ct-settings-modal');
    if (modal) modal.remove();

    doScanAndFilter();
    const rows = findEmailRows();
    const hiddenCount = rows.filter(r => r.getAttribute('data-ct-hidden') === 'warmup').length;

    modal = document.createElement('div');
    modal.id = 'ct-settings-modal';
    modal.innerHTML = `
      <div class="ct-modal-backdrop"></div>
      <div class="ct-modal-content">
        <div class="ct-modal-header">
          <div class="ct-modal-title-wrap">
            <span class="ct-dot ct-dot-indigo"></span>
            <h3>Коды прогрева Trigga</h3>
          </div>
          <button class="ct-modal-close">&times;</button>
        </div>
        <div class="ct-modal-body">
          <label class="ct-input-label">Коды прогревочных ящиков (каждый с новой строки):</label>
          <textarea id="ct-codes-textarea" rows="7" placeholder="1Vf6ZV1&#10;icKKRxR&#10;9mBA4U0...">${warmupCodes.join('\n')}</textarea>
          
          <div class="ct-modal-stats">
            <div><span class="ct-dot ct-dot-slate"></span> Строк на странице: <b>${rows.length}</b> &nbsp;·&nbsp; Скрыто ботов: <b>${hiddenCount}</b></div>
            <div><span class="ct-dot ${hookHasDetailTpl ? 'ct-dot-indigo' : 'ct-dot-amber'}"></span> Сканер: <b>${hookHasDetailTpl ? 'Активен (шаблон найден)' : 'Ожидает 1 клик по любому письму'}</b> &nbsp;·&nbsp; В кэше: <b>${hookCheckedCount}</b></div>
            <div class="ct-modal-keys" style="margin-top: 5px;">Шаблон API: <code>${hookDetailTpl || 'захватится при клике на письмо'}</code></div>
            ${hookDebugUrls.length > 0 ? `<div class="ct-modal-keys" style="margin-top: 4px;">Запросы CRM: <code>${hookDebugUrls.slice(-3).join(', ')}</code></div>` : ''}
          </div>
        </div>
        <div class="ct-modal-footer">
          <button id="ct-modal-cancel" class="ct-btn-secondary">Отмена</button>
          <button id="ct-modal-save" class="ct-btn-primary">Сохранить</button>
        </div>
      </div>
    `;

    document.body.appendChild(modal);

    const close = () => modal.remove();
    modal.querySelector('.ct-modal-close').addEventListener('click', close);
    modal.querySelector('.ct-modal-backdrop').addEventListener('click', close);
    modal.querySelector('#ct-modal-cancel').addEventListener('click', close);

    modal.querySelector('#ct-modal-save').addEventListener('click', () => {
      const raw = document.getElementById('ct-codes-textarea').value;
      warmupCodes = raw.split('\n').map(s => s.trim()).filter(Boolean);

      chrome.storage.local.set({ warmupCodes }, () => {
        updateSettingsBtn();
        syncWithHook();
        doScanAndFilter();
        close();
      });
    });
  }

  // Clean row text (excluding our own injected pills)
  function getCleanRowText(row) {
    const clone = row.cloneNode(true);
    clone.querySelectorAll('.ct-row-actions').forEach(el => el.remove());
    return (clone.textContent || '').replace(/\s+/g, ' ').trim();
  }

  function getRowKey(row) {
    const id = row.getAttribute('data-ct-id') || row.getAttribute('data-id') || row.getAttribute('data-email-id');
    if (id) return `id_${id}`;
    return `txt_${getCleanRowText(row).slice(0, 80)}`;
  }

  // Compute thread/chain number for each row (e.g. 2-е в цепочке, 3-е в цепочке)
  function computeChainNumbers(rows) {
    // Map normalized conversation key -> array of rows (from bottom/oldest to top/newest)
    const threadGroups = new Map();

    // Rows in inbox are ordered newest (top) to oldest (bottom). Reverse to process oldest first.
    const chronological = [...rows].reverse();

    for (const row of chronological) {
      const text = getCleanRowText(row);
      const lower = text.toLowerCase();

      // Skip mailer-daemon / bounce notifications
      if (lower.includes('недоставленное сообщение') || lower.includes('mailer-daemon')) {
        row.setAttribute('data-ct-computed-chain', '0');
        continue;
      }

      // Extract subject/conversation signature by looking for Re: / Fwd: or sender + subject
      const reMatch = text.match(/(?:re|fwd|отв):\s*(?:(?:re|fwd|отв):\s*)*([^\n\r]{5,45})/i);
      const hasRe = /\b(re|fwd|отв):/i.test(text);
      const hasDoubleRe = /\b(re|fwd|отв):\s*(re|fwd|отв):/i.test(text);

      let groupKey = null;
      if (reMatch && reMatch[1]) {
        groupKey = reMatch[1].trim().toLowerCase().slice(0, 30);
      }

      let indexInList = 1;
      if (groupKey) {
        const list = threadGroups.get(groupKey) || [];
        list.push(row);
        threadGroups.set(groupKey, list);
        indexInList = list.length;
      }

      // Combine signals:
      // 1) Depth from Vue/API quotes (data-ct-chain)
      const hookChain = Number(row.getAttribute('data-ct-chain') || '0');
      // 2) If it has "Re:", there was at least 1 prior email + this reply = 2
      let baseChain = hasDoubleRe ? 3 : (hasRe ? 2 : 1);
      // 3) If multiple replies of the same thread are in the inbox, increment position
      if (indexInList > 1) {
        baseChain = Math.max(baseChain, indexInList + (hasRe ? 1 : 0));
      }

      const finalChain = Math.max(hookChain, baseChain);
      row.setAttribute('data-ct-computed-chain', String(finalChain >= 2 ? finalChain : 0));
    }
  }

  const FREE_AND_SYSTEM_DOMAINS = new Set([
    'yandex.ru', 'yandex.com', 'yandex.by', 'yandex.kz', 'yandex.ua', 'ya.ru',
    'mail.ru', 'bk.ru', 'inbox.ru', 'list.ru', 'internet.ru', 'xmail.ru',
    'gmail.com', 'googlemail.com',
    'rambler.ru', 'lenta.ru', 'autorambler.ru', 'myrambler.ru', 'ro.ru',
    'icloud.com', 'me.com', 'mac.com',
    'outlook.com', 'hotmail.com', 'live.com', 'msn.com',
    'yahoo.com', 'ymail.com', 'aol.com', 'zoho.com', 'protonmail.com', 'proton.me', 'gmx.com',
    'calltalk.ru', 'call-talk.ru', 'okocrm.com'
  ]);

  function extractCorporateDomainInfo(row) {
    const candidates = [];
    const attrEmail = row.getAttribute('data-ct-sender-email');
    if (attrEmail) candidates.push(attrEmail.trim().toLowerCase());

    const cleanText = getCleanRowText(row);
    const matches = cleanText.match(/[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/g) || [];
    for (const m of matches) {
      candidates.push(m.toLowerCase());
    }

    for (const email of candidates) {
      const parts = email.split('@');
      if (parts.length !== 2) continue;
      const local = parts[0];
      const domain = parts[1].replace(/^www\./, '');

      // Skip system bounce senders and our own outreach mailboxes
      if (local.includes('mailer-daemon') || local.includes('postmaster') || local.includes('noreply') || local.includes('no-reply')) {
        continue;
      }
      if (local.startsWith('igor.') || local.startsWith('erm.') || local.startsWith('ermolaev')) {
        continue;
      }
      if (FREE_AND_SYSTEM_DOMAINS.has(domain)) {
        continue;
      }

      return { email, domain };
    }
    return null;
  }

  // Inject sleek modern pills: Corporate Domain + Thread indicator + "Ответить позже" pill
  function ensureRowPills(row) {
    const key = getRowKey(row);
    const isLater = Boolean(rowMarks[key]);
    const chainNum = Number(row.getAttribute('data-ct-computed-chain') || '0');
    const corpInfo = extractCorporateDomainInfo(row);

    row.classList.toggle('ct-row-marked-later', isLater);

    if (getComputedStyle(row).position === 'static') {
      row.style.position = 'relative';
    }

    let actionsBox = row.querySelector('.ct-row-actions');
    if (!actionsBox) {
      actionsBox = document.createElement('div');
      actionsBox.className = 'ct-row-actions';
      actionsBox.addEventListener('click', (e) => {
        e.stopPropagation();
        e.preventDefault();
      });
      row.appendChild(actionsBox);
    }

    const domainKey = corpInfo ? corpInfo.email : 'no_domain';
    const nextState = `${key}:${isLater ? 'later' : 'none'}:chain_${chainNum}:${domainKey}`;
    if (actionsBox.getAttribute('data-pill-state') === nextState) return;
    actionsBox.setAttribute('data-pill-state', nextState);

    const domainPillHtml = corpInfo
      ? `<button type="button" class="ct-domain-pill" title="1-й клик — открыть сайт ${corpInfo.domain}&#10;2-й клик — скопировать ${corpInfo.email}">
           <span class="ct-domain-arrow">↗</span>
           <span class="ct-domain-text">${corpInfo.domain}</span>
         </button>`
      : '';

    const chainPillHtml = chainNum >= 2
      ? `<span class="ct-chain-pill" title="${chainNum}-е письмо в цепочке">${chainNum}</span>`
      : '';

    actionsBox.innerHTML = `
      <button type="button" class="ct-later-pill ${isLater ? 'ct-active' : ''}" title="${isLater ? 'Снять пометку «Ответить позже»' : 'Поставить пометку «Ответить позже»'}">
        <span class="ct-dot ct-dot-amber"></span>
        <span>Ответить позже</span>
      </button>
      ${domainPillHtml}
      ${chainPillHtml}
    `;

    if (corpInfo) {
      const btnDomain = actionsBox.querySelector('.ct-domain-pill');
      if (btnDomain) {
        btnDomain.addEventListener('click', (e) => {
          e.stopPropagation();
          e.preventDefault();

          const arrowEl = btnDomain.querySelector('.ct-domain-arrow');
          const textEl = btnDomain.querySelector('.ct-domain-text');

          if (!btnDomain.hasAttribute('data-opened-once')) {
            // 1st click: open corporate website in a new tab
            btnDomain.setAttribute('data-opened-once', '1');
            window.open(`https://${corpInfo.domain}`, '_blank', 'noopener,noreferrer');
            btnDomain.title = `Нажмите ещё раз, чтобы скопировать ${corpInfo.email}`;
          } else {
            // 2nd click: copy sender email to clipboard
            navigator.clipboard.writeText(corpInfo.email).catch(() => {});
            btnDomain.classList.add('ct-copied');
            if (arrowEl) arrowEl.textContent = '✓';
            if (textEl) textEl.textContent = corpInfo.email;

            setTimeout(() => {
              btnDomain.classList.remove('ct-copied');
              btnDomain.removeAttribute('data-opened-once');
              if (arrowEl) arrowEl.textContent = '↗';
              if (textEl) textEl.textContent = corpInfo.domain;
              btnDomain.title = `1-й клик — открыть сайт ${corpInfo.domain}\n2-й клик — скопировать ${corpInfo.email}`;
            }, 1800);
          }
        });
      }
    }

    const btnLater = actionsBox.querySelector('.ct-later-pill');
    btnLater.addEventListener('click', (e) => {
      e.stopPropagation();
      e.preventDefault();
      const k = getRowKey(row);
      if (rowMarks[k]) {
        delete rowMarks[k];
      } else {
        rowMarks[k] = 'later';
      }
      chrome.storage.local.set({ rowMarks });
      doScanAndFilter();
    });
  }

  // Organize left sidebar ("ПОЧТОВЫЕ ЯЩИКИ")
  function isPersonalMailbox(emailStr) {
    const s = emailStr.toLowerCase();
    return s.includes('andrey') || s.includes('leonid') || s.includes('ulyana') || s.includes('uliana');
  }

  function organizeMailboxesSidebar() {
    const allEls = document.querySelectorAll('div, span, p, h3, h4');
    let headingEl = null;
    for (const el of allEls) {
      if (el.children.length === 0 && (el.textContent || '').trim().toUpperCase() === 'ПОЧТОВЫЕ ЯЩИКИ') {
        headingEl = el;
        break;
      }
    }
    if (!headingEl) return;

    let sidebarBox = headingEl.parentElement;
    while (sidebarBox && sidebarBox !== document.body) {
      const text = sidebarBox.textContent || '';
      const matches = text.match(/@[a-z0-9.-]+\.[a-z]{2,}/gi);
      if (matches && matches.length >= 2) break;
      sidebarBox = sidebarBox.parentElement;
    }
    if (!sidebarBox || sidebarBox === document.body) return;

    const emailLeaves = [];
    const subEls = sidebarBox.querySelectorAll('div, span, a, li');
    for (const el of subEls) {
      if (el.children.length === 0) {
        const t = (el.textContent || '').trim();
        if (/@[a-z0-9.-]+/i.test(t) && t.length < 50) {
          emailLeaves.push(el);
        }
      }
    }
    if (emailLeaves.length < 2) return;

    const mailboxItems = [];
    let listContainer = null;

    for (const leaf of emailLeaves) {
      let curr = leaf;
      while (curr.parentElement && curr.parentElement !== sidebarBox) {
        const parent = curr.parentElement;
        let countInParent = 0;
        for (const el of emailLeaves) {
          if (parent.contains(el)) countInParent++;
        }
        if (countInParent > 1) {
          listContainer = parent;
          break;
        }
        curr = parent;
      }
      if (curr && !mailboxItems.includes(curr)) {
        mailboxItems.push(curr);
      }
    }

    if (!listContainer || mailboxItems.length < 2) return;

    if (listContainer.style.display !== 'flex') {
      listContainer.style.display = 'flex';
      listContainer.style.flexDirection = 'column';
    }

    let outreachCount = 0;
    const outreachItems = [];

    for (const item of mailboxItems) {
      if (item.id === 'ct-outreach-folder-toggle') continue;
      const text = (item.textContent || '').trim();

      if (isPersonalMailbox(text)) {
        item.style.order = '1';
        item.style.display = '';
        item.classList.add('ct-personal-mailbox');
      } else {
        item.style.order = '3';
        item.classList.add('ct-outreach-mailbox');
        outreachItems.push(item);
        outreachCount++;
      }
    }

    let folderBtn = document.getElementById('ct-outreach-folder-toggle');
    if (!folderBtn && outreachCount > 0) {
      folderBtn = document.createElement('div');
      folderBtn.id = 'ct-outreach-folder-toggle';
      folderBtn.style.order = '2';
      folderBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        outreachFolderExpanded = !outreachFolderExpanded;
        chrome.storage.local.set({ outreachFolderExpanded });
        organizeMailboxesSidebar();
      });
      listContainer.appendChild(folderBtn);
    }

    if (folderBtn) {
      folderBtn.classList.toggle('ct-expanded', outreachFolderExpanded);
      folderBtn.innerHTML = `
        <div class="ct-folder-left">
          <span class="ct-dot ct-dot-indigo"></span>
          <span>Почты рассылки</span>
          <span class="ct-folder-count">${outreachCount}</span>
        </div>
        <svg class="ct-folder-chevron" viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" stroke-width="2" fill="none"><polyline points="6 9 12 15 18 9"></polyline></svg>
      `;
    }

    for (const item of outreachItems) {
      item.style.display = outreachFolderExpanded ? '' : 'none';
    }

    for (const child of Array.from(listContainer.children)) {
      if (!mailboxItems.includes(child) && child.id !== 'ct-outreach-folder-toggle') {
        child.style.order = '10';
      }
    }
  }

  // Row Finder
  const DATE_CELL_REGEX = /^(сегодня(\s+в)?|вчера(\s+в)?|\d{2}\.\d{2}\.\d{2,4})\s+\d{1,2}:\d{2}$/i;

  function findEmailRows() {
    const allEls = document.querySelectorAll('div, span, th, td, p');
    let headerLeaf = null;
    for (const el of allEls) {
      if (el.children.length === 0 && (el.textContent || '').trim() === 'Тема и сообщение') {
        headerLeaf = el;
        break;
      }
    }

    if (headerLeaf) {
      let headerRow = headerLeaf.parentElement;
      while (headerRow && headerRow !== document.body) {
        const t = (headerRow.textContent || '').trim();
        if (t.includes('Отправитель') && t.includes('Тема и сообщение')) {
          const p = headerRow.parentElement;
          if (p && (p.textContent || '').replace(/\s+/g, ' ').trim().length < 70) {
            headerRow = p;
          }
          break;
        }
        headerRow = headerRow.parentElement;
      }

      if (headerRow && headerRow !== document.body) {
        const table = headerRow.closest('table');
        if (table) {
          const trs = Array.from(table.querySelectorAll('tbody tr'));
          if (trs.length > 0) {
            trs.forEach(r => r.setAttribute('data-ct-row', '1'));
            return trs;
          }
        }

        const parentChildren = Array.from(headerRow.parentElement.children).filter(
          c => c !== headerRow && !c.id?.startsWith('ct-')
        );

        if (parentChildren.length > 1) {
          parentChildren.forEach(r => r.setAttribute('data-ct-row', '1'));
          return parentChildren;
        } else if (headerRow.nextElementSibling) {
          let bodyBox = headerRow.nextElementSibling;
          while (bodyBox.children.length === 1 && bodyBox.children[0].children.length > 1) {
            const grandChildren = Array.from(bodyBox.children[0].children);
            const isSingleRowCols = grandChildren.some(gc => {
              const gt = (gc.textContent || '').replace(/\s+/g, ' ').trim();
              return gt.length >= 10 && gt.length <= 25 && DATE_CELL_REGEX.test(gt);
            });
            if (isSingleRowCols) break;
            bodyBox = bodyBox.children[0];
          }
          const rows = Array.from(bodyBox.children).filter(c => !c.id?.startsWith('ct-'));
          if (rows.length > 0) {
            rows.forEach(r => r.setAttribute('data-ct-row', '1'));
            return rows;
          }
        }
      }
    }

    const dateNodes = [];
    for (const el of allEls) {
      if (el.closest('#ct-mail-filter-toolbar, #ct-settings-modal, .ct-row-actions')) continue;
      const txt = (el.textContent || '').replace(/\s+/g, ' ').trim();
      if (txt.length >= 10 && txt.length <= 25 && DATE_CELL_REGEX.test(txt)) {
        dateNodes.push(el);
      }
    }

    const dateLeaves = dateNodes.filter(dn => !dateNodes.some(other => other !== dn && dn.contains(other)));
    if (dateLeaves.length === 0) return [];

    const rowSet = new Set();
    for (const leaf of dateLeaves) {
      let curr = leaf;
      while (curr.parentElement && curr.parentElement !== document.body) {
        const parent = curr.parentElement;
        if (curr.tagName === 'TR') break;

        let countInParent = 0;
        for (const dl of dateLeaves) {
          if (parent.contains(dl)) {
            countInParent++;
            if (countInParent > 1) break;
          }
        }
        if (countInParent > 1) break;

        const pt = parent.textContent || '';
        if (pt.includes('Отправитель') && pt.includes('Тема и сообщение')) break;

        curr = parent;
      }

      if (curr && curr !== document.body) {
        curr.setAttribute('data-ct-row', '1');
        rowSet.add(curr);
      }
    }

    return Array.from(rowSet);
  }

  const SAFE_7CHAR_WORDS = new Set([
    'youtube', 'macbook', 'onenote', 'airpods', 'outlook', 'android', 'windows',
    'company', 'regards', 'manager', 'support', 'service', 'partner', 'calltalk',
    'okocrm1', 'bitrix2', 'amocrm1', 'iphones', 'samsung', 'desktop', 'browser',
    'account', 'profile', 'message', 'subject', 'contact', 'default', 'primary'
  ]);

  function isTrigga7CharToken(tok) {
    if (!tok || tok.length !== 7 || !/^[A-Za-z0-9]{7}$/.test(tok)) return false;
    if (SAFE_7CHAR_WORDS.has(tok.toLowerCase())) return false;
    const hasDigit = /[0-9]/.test(tok);
    const hasLetter = /[A-Za-z]/.test(tok);
    const hasLower = /[a-z]/.test(tok);
    const hasInternalUpper = /[A-Z]/.test(tok.slice(1));
    if (hasDigit && hasLetter) return true;
    if (hasLower && hasInternalUpper) return true;
    return false;
  }

  function detectTrailing7CharCodeInDom(rawText) {
    if (!rawText || typeof rawText !== 'string' || rawText.length < 12) return null;
    if (!/[а-яёА-ЯЁ]{3,}/.test(rawText)) return null;

    const text = rawText
      .replace(/https?:\/\/\S+/gi, ' ')
      .replace(/[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/g, ' ')
      .replace(/(?:сегодня|вчера|\d{2}\.\d{2}\.\d{2,4})(?:\s+в)?\s+\d{1,2}:\d{2}/gi, '\n')
      .replace(/\b(?:Ответить|Закрыть|Переслать|Удалить|Создать сделку)\b/gi, '\n');

    const lines = text.split(/[\r\n]+/).map(l => l.trim()).filter(Boolean);
    for (let i = lines.length - 1; i >= 0; i--) {
      const cleaned = lines[i].replace(/[\s.!?,;:"'»«)\]]+$/g, '').trim();
      if (!cleaned) continue;
      const words = cleaned.split(/\s+/);
      const lastWord = (words[words.length - 1] || '').replace(/^[^A-Za-z0-9]+|[^A-Za-z0-9]+$/g, '');
      if (isTrigga7CharToken(lastWord)) {
        if (!warmupCodes.some(c => c.toLowerCase() === lastWord.toLowerCase())) {
          warmupCodes.push(lastWord);
          chrome.storage.local.set({ warmupCodes });
          updateSettingsBtn();
        }
        return lastWord;
      }
    }
    return null;
  }

  function containsAnyCode(text) {
    if (!text || typeof text !== 'string') return false;
    const lower = text.toLowerCase();
    for (const code of warmupCodes) {
      if (code && lower.includes(code.toLowerCase())) return true;
    }
    if (detectTrailing7CharCodeInDom(text)) return true;
    return false;
  }

  function checkOpenEmailOnScreen(rows) {
    const candidates = document.querySelectorAll(
      '[class*="modal"], [class*="dialog"], [class*="popup"], [role="dialog"], [class*="view"], [class*="detail"], [class*="letter"], [class*="message"]'
    );
    for (const el of candidates) {
      if (el.closest('#ct-mail-filter-toolbar, #ct-settings-modal')) continue;
      if (el.querySelector('[data-ct-row="1"]')) continue;

      const txt = el.innerText || el.textContent || '';
      if (!txt || txt.length < 20) continue;

      if (containsAnyCode(txt)) {
        // 1. Extract subject before "От кого:" in OkoCRM's email modal
        const beforeFrom = txt.split(/От кого:/i)[0];
        if (beforeFrom) {
          const cleanSubj = beforeFrom.replace(/\s+/g, ' ').trim().toLowerCase();
          const normSubj = cleanSubj.replace(/^(?:(?:re|fwd|отв):\s*)+/i, '').trim();
          if (cleanSubj.length > 3) identifiedWarmupSubjects.add(cleanSubj);
          if (normSubj.length > 3) identifiedWarmupSubjects.add(normSubj);
        }

        // 2. Also check which row in `rows` has its subject or sender inside this open modal
        const lowerModal = txt.replace(/\s+/g, ' ').toLowerCase();
        if (Array.isArray(rows)) {
          for (const r of rows) {
            const rText = getCleanRowText(r);
            const reMatch = rText.match(/((?:re|fwd|отв):\s*[^\n\r]{5,60})/i);
            if (reMatch && lowerModal.includes(reMatch[1].trim().toLowerCase().slice(0, 35))) {
              const s = reMatch[1].trim().toLowerCase().slice(0, 45);
              identifiedWarmupSubjects.add(s);
              r.setAttribute('data-ct-warmup', 'modal');
            }
          }
        }

        try {
          localStorage.setItem('ct_cached_warmup_subs', JSON.stringify(Array.from(identifiedWarmupSubjects)));
        } catch (e) {}
      }
    }
  }

  function isWarmupRow(row) {
    const rawText = getCleanRowText(row);
    const metaText = row.getAttribute('data-ct-meta') || '';

    if (containsAnyCode(rawText) || containsAnyCode(metaText)) {
      return true;
    }

    if (row.getAttribute('data-ct-warmup')) {
      return true;
    }

    const rowId = row.getAttribute('data-ct-id') || row.getAttribute('data-id') || row.getAttribute('data-email-id');
    if (rowId && identifiedWarmupIds.has(String(rowId))) {
      return true;
    }

    const lowerText = rawText.toLowerCase();
    for (const sub of identifiedWarmupSubjects) {
      if (sub && sub.length > 4 && lowerText.includes(sub)) {
        return true;
      }
    }

    return false;
  }

  function isBounceRow(row) {
    const rawText = getCleanRowText(row).toLowerCase();
    const senderEmail = (row.getAttribute('data-ct-sender-email') || '').toLowerCase();
    const combined = rawText + ' ' + senderEmail;
    return (
      combined.includes('недоставленное сообщение') ||
      combined.includes('mailer-daemon') ||
      combined.includes('postmaster@') ||
      combined.includes('undelivered mail') ||
      combined.includes('delivery status notification') ||
      combined.includes('mail delivery subsystem') ||
      combined.includes('failure notice') ||
      combined.includes('returned mail') ||
      combined.includes('не удалось доставить') ||
      combined.includes('ошибка доставки')
    );
  }

  let filterTimer = null;
  let isScanning = false;

  function scanAndFilter() {
    clearTimeout(filterTimer);
    filterTimer = setTimeout(doScanAndFilter, 30);
  }

  function doScanAndFilter() {
    updateToolbarVisibility();
    if (!isMailInboxPage()) return;

    if (isScanning) return;
    isScanning = true;

    try {
      document.querySelectorAll('.ct-item-badge').forEach(b => b.remove());

      organizeMailboxesSidebar();

      const rows = findEmailRows();
      if (rows.length > 0) {
        syncWithHook();
        computeChainNumbers(rows);
      }
      checkOpenEmailOnScreen(rows);

      let hiddenWarmupCount = 0;
      let bounceTotalCount = 0;
      let markedTotalCount = 0;

      for (const row of rows) {
        ensureRowPills(row);

        const rowKey = getRowKey(row);
        const isLater = Boolean(rowMarks[rowKey]);
        if (isLater) markedTotalCount++;

        const rawText = getCleanRowText(row).toLowerCase();
        const metaText = (row.getAttribute('data-ct-meta') || '').toLowerCase();
        const combinedSearchable = rawText + ' ' + metaText;

        const isWarmup = isWarmupRow(row);
        const isBounce = isBounceRow(row);
        if (isBounce) bounceTotalCount++;

        const matchesSearch = !searchQuery || combinedSearchable.includes(searchQuery);
        const matchesMarkedFilter = !onlyMarkedFilter || isLater;

        if (isWarmup && hideWarmupEnabled) {
          if (row.style.display !== 'none') row.style.display = 'none';
          row.setAttribute('data-ct-hidden', 'warmup');
          hiddenWarmupCount++;
        } else if (isBounce && hideBouncesEnabled) {
          if (row.style.display !== 'none') row.style.display = 'none';
          row.setAttribute('data-ct-hidden', 'bounce');
        } else if (!matchesSearch || !matchesMarkedFilter) {
          if (row.style.display !== 'none') row.style.display = 'none';
          row.setAttribute('data-ct-hidden', 'search');
        } else {
          if (row.style.display === 'none') row.style.display = '';
          row.removeAttribute('data-ct-hidden');
        }
      }

      const counterBadge = document.getElementById('ct-hidden-count');
      if (counterBadge) {
        counterBadge.innerText = `${hiddenWarmupCount} скрыто`;
        counterBadge.style.display = (hiddenWarmupCount > 0 && hideWarmupEnabled) ? 'inline-block' : 'none';
      }

      const bouncesCountSpan = document.getElementById('ct-bounces-count');
      if (bouncesCountSpan) {
        bouncesCountSpan.innerText = String(bounceTotalCount);
        bouncesCountSpan.style.display = bounceTotalCount > 0 ? 'inline-block' : 'none';
      }

      const markedCountSpan = document.getElementById('ct-marked-count');
      if (markedCountSpan) {
        markedCountSpan.innerText = String(markedTotalCount);
        markedCountSpan.style.display = markedTotalCount > 0 ? 'inline-block' : 'none';
      }
    } finally {
      isScanning = false;
    }
  }

  const observer = new MutationObserver((mutations) => {
    let relevant = false;
    for (const m of mutations) {
      if (m.target && m.target.closest && m.target.closest('#ct-mail-filter-toolbar, #ct-settings-modal, #ct-outreach-folder-toggle, .ct-row-actions')) {
        continue;
      }
      relevant = true;
      break;
    }
    if (!relevant) return;

    updateToolbarVisibility();
    if (isMailInboxPage()) {
      scanAndFilter();
    }
  });

  observer.observe(document.body, {
    childList: true,
    subtree: true
  });

  window.addEventListener('popstate', updateToolbarVisibility);
  window.addEventListener('hashchange', updateToolbarVisibility);
})();
