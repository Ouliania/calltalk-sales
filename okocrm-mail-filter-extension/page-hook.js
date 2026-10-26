// page-hook.js - MAIN world network sniffer, Vue inspector & auto-learner (Call-Talk)
(function () {
  const INITIAL_CODES = [
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

  const SAFE_7CHAR_WORDS = new Set([
    'youtube', 'macbook', 'onenote', 'airpods', 'outlook', 'android', 'windows',
    'company', 'regards', 'manager', 'support', 'service', 'partner', 'calltalk',
    'okocrm1', 'bitrix2', 'amocrm1', 'iphones', 'samsung', 'desktop', 'browser',
    'account', 'profile', 'message', 'subject', 'contact', 'default', 'primary'
  ]);

  let activeCodes = [...INITIAL_CODES];
  const warmupIds = new Set();
  const warmupSubjects = new Set();
  const emailDataById = new Map();

  // Permanent verdicts cache: { [letterId]: 'warmup' | 'safe' }
  let cachedLetterVerdicts = {};

  let confirmedDetailUrlTemplate = null;
  let confirmedDetailMethod = 'GET';
  let lastCapturedHeaders = {
    'Accept': 'application/json, text/plain, */*',
    'X-Requested-With': 'XMLHttpRequest'
  };

  let debugApiUrls = [];
  let debugSampleKeys = [];
  let debugSampleLen = 0;
  let debugBodiesChecked = 0;
  let lastClickedRowId = null;
  let lastClickedTime = 0;

  // 1. Restore cache from localStorage immediately
  try {
    const savedCodes = localStorage.getItem('ct_warmup_codes');
    if (savedCodes) {
      const parsed = JSON.parse(savedCodes);
      if (Array.isArray(parsed) && parsed.length > 0) {
        activeCodes = Array.from(new Set([...activeCodes, ...parsed]));
      }
    }

    const savedVerdicts = localStorage.getItem('ct_cached_letter_verdicts');
    if (savedVerdicts) {
      cachedLetterVerdicts = JSON.parse(savedVerdicts) || {};
      for (const [id, verdict] of Object.entries(cachedLetterVerdicts)) {
        if (verdict === 'warmup') warmupIds.add(String(id));
      }
    }

    const savedIds = localStorage.getItem('ct_cached_warmup_ids');
    if (savedIds) JSON.parse(savedIds).forEach(id => warmupIds.add(String(id)));

    const savedSubs = localStorage.getItem('ct_cached_warmup_subs');
    if (savedSubs) JSON.parse(savedSubs).forEach(s => warmupSubjects.add(String(s).toLowerCase()));

    const savedTpl = localStorage.getItem('ct_detail_url_template');
    if (savedTpl && savedTpl.includes('{id}')) {
      confirmedDetailUrlTemplate = savedTpl;
    }

    const savedMethod = localStorage.getItem('ct_detail_api_method');
    if (savedMethod) confirmedDetailMethod = savedMethod;

    const savedHeaders = localStorage.getItem('ct_captured_headers');
    if (savedHeaders) {
      try { Object.assign(lastCapturedHeaders, JSON.parse(savedHeaders)); } catch (e) {}
    }
  } catch (e) {}

  function saveCache() {
    try {
      localStorage.setItem('ct_warmup_codes', JSON.stringify(activeCodes));
      localStorage.setItem('ct_cached_warmup_ids', JSON.stringify(Array.from(warmupIds)));
      localStorage.setItem('ct_cached_warmup_subs', JSON.stringify(Array.from(warmupSubjects)));
      localStorage.setItem('ct_cached_letter_verdicts', JSON.stringify(cachedLetterVerdicts));
      if (confirmedDetailUrlTemplate) {
        localStorage.setItem('ct_detail_url_template', confirmedDetailUrlTemplate);
      }
      if (confirmedDetailMethod) {
        localStorage.setItem('ct_detail_api_method', confirmedDetailMethod);
      }
      if (lastCapturedHeaders) {
        localStorage.setItem('ct_captured_headers', JSON.stringify(lastCapturedHeaders));
      }
    } catch (e) {}
  }

  function writeSharedDomState() {
    try {
      if (document.documentElement) {
        document.documentElement.setAttribute('data-ct-state', JSON.stringify({
          ids: Array.from(warmupIds),
          subjects: Array.from(warmupSubjects),
          discoveredCodes: activeCodes,
          hasDetailTpl: Boolean(confirmedDetailUrlTemplate),
          detailTpl: confirmedDetailUrlTemplate || '',
          cachedCount: emailDataById.size,
          checkedCount: Object.keys(cachedLetterVerdicts).length,
          cachedBotCount: warmupIds.size,
          bodiesChecked: debugBodiesChecked,
          sampleKeys: debugSampleKeys,
          sampleLen: debugSampleLen,
          debugUrls: debugApiUrls.slice(-6)
        }));
      }
    } catch (e) {}
  }

  function notifyContentScript() {
    writeSharedDomState();
    window.dispatchEvent(new Event('CT_HOOK_UPDATED'));
    document.dispatchEvent(new Event('CT_HOOK_UPDATED'));
  }

  function handleSyncSignal() {
    try {
      const rawCodes = document.documentElement.getAttribute('data-ct-codes');
      if (rawCodes) {
        const parsed = JSON.parse(rawCodes);
        if (Array.isArray(parsed)) {
          const merged = Array.from(new Set([...activeCodes, ...parsed.map(c => String(c).trim()).filter(Boolean)]));
          if (merged.length !== activeCodes.length) {
            activeCodes = merged;
          }
        }
      }
    } catch (e) {}

    reScanMemory();
    scanPerformanceUrls();
    scanGlobalVueAndStores();
    inspectDomVueRows();
    writeSharedDomState();
    if (confirmedDetailUrlTemplate) {
      triggerVisibleRowsScan();
    }
  }

  window.addEventListener('CT_SYNC', handleSyncSignal);
  document.addEventListener('CT_SYNC', handleSyncSignal);

  // Periodic scan in MAIN world for Vue rows & DOM changes
  setInterval(() => {
    if (window.location.href.includes('/mail/inbox')) {
      scanPerformanceUrls();
      scanGlobalVueAndStores();
      inspectDomVueRows();
      writeSharedDomState();
      if (confirmedDetailUrlTemplate) {
        triggerVisibleRowsScan();
      }
    }
  }, 700);

  // Track user clicks on email rows to correlate with detail API requests
  document.addEventListener('click', (e) => {
    const row = e.target && e.target.closest && e.target.closest('[data-ct-row="1"]');
    if (row) {
      const id = row.getAttribute('data-ct-id');
      if (id) {
        lastClickedRowId = id;
        lastClickedTime = Date.now();
      }
    }
  }, true);

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

  function detectTrailing7CharCode(rawText) {
    if (!rawText || typeof rawText !== 'string' || rawText.length < 10) return null;

    let text = rawText
      .replace(/<style[\s\S]*?<\/style>/gi, '\n')
      .replace(/<script[\s\S]*?<\/script>/gi, '\n')
      .replace(/<blockquote[\s\S]*?<\/blockquote>/gi, '\n__QUOTE_SPLIT__\n')
      .replace(/<\/?(?:p|div|br|tr|li|h[1-6])[^>]*>/gi, '\n')
      .replace(/<[^>]+>/g, ' ')
      .replace(/&nbsp;/gi, ' ')
      .replace(/https?:\/\/\S+/gi, ' ')
      .replace(/[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/g, ' ')
      .replace(/\b(?:Ответить|Закрыть|Переслать|Удалить|Создать сделку)\b/gi, '\n');

    if (!/[а-яёА-ЯЁ]{3,}/.test(text)) return null;

    const lines = text.split(/__QUOTE_SPLIT__|[\r\n]+/).map(l => l.trim()).filter(Boolean);

    for (let i = lines.length - 1; i >= 0; i--) {
      const cleaned = lines[i].replace(/[\s.!?,;:"'»«)\]]+$/g, '').trim();
      if (!cleaned) continue;

      const words = cleaned.split(/\s+/);
      const lastWord = (words[words.length - 1] || '').replace(/^[^A-Za-z0-9]+|[^A-Za-z0-9]+$/g, '');

      if (isTrigga7CharToken(lastWord)) {
        if (!activeCodes.some(c => c.toLowerCase() === lastWord.toLowerCase())) {
          activeCodes.push(lastWord);
          saveCache();
        }
        return lastWord;
      }
    }

    return null;
  }

  function hasWarmupCode(str) {
    if (!str || typeof str !== 'string') return null;
    const lower = str.toLowerCase();
    for (const code of activeCodes) {
      if (code && lower.includes(code.toLowerCase())) {
        return code;
      }
    }
    const autoDetected = detectTrailing7CharCode(str);
    if (autoDetected) return autoDetected;
    return null;
  }

  function unwrapVueValue(val) {
    if (!val || typeof val !== 'object') return val;
    if (val.__v_isRef && val._value !== undefined) return val._value;
    if (val.__v_raw && typeof val.__v_raw === 'object') return val.__v_raw;
    return val;
  }

  function findFieldDeep(rawObj, fieldNames, depth = 0, seen = new Set()) {
    const obj = unwrapVueValue(rawObj);
    if (!obj || typeof obj !== 'object' || depth > 5 || seen.has(obj)) return '';
    if (obj instanceof Node || obj === window || obj === document) return '';
    seen.add(obj);

    for (const f of fieldNames) {
      if (obj[f] !== undefined && obj[f] !== null && typeof obj[f] !== 'object') {
        const s = String(obj[f]).trim();
        if (s) return s;
      }
    }

    let keys;
    try { keys = Object.keys(obj); } catch (e) { return ''; }
    for (const k of keys) {
      if (k === 'parent' || k === 'vnode' || k === 'subTree' || k === 'appContext' || k === '$el' || k === '$parent' || k === '$root' || k === 'deps' || k === 'effects') continue;
      let val;
      try { val = unwrapVueValue(obj[k]); } catch (e) { continue; }
      if (Array.isArray(val)) {
        for (let i = 0; i < Math.min(val.length, 5); i++) {
          const res = findFieldDeep(val[i], fieldNames, depth + 1, seen);
          if (res) return res;
        }
      } else if (val && typeof val === 'object') {
        const res = findFieldDeep(val, fieldNames, depth + 1, seen);
        if (res) return res;
      }
    }
    return '';
  }

  const EMAIL_EXTRACT_RE = /([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})/;

  function extractSenderEmail(rawObj) {
    const obj = unwrapVueValue(rawObj);
    if (!obj || typeof obj !== 'object') return '';
    const src = obj.attributes && typeof obj.attributes === 'object' ? { ...obj, ...obj.attributes } : obj;
    const rawCandidates = [
      src.from_email,
      src.sender_email,
      src.from_address,
      src.from,
      src.sender,
      src.reply_to,
      src.author,
      src.contact_email,
      src.email,
      findFieldDeep(src, ['from_email', 'sender_email', 'from_address', 'from', 'sender'])
    ];
    for (const item of rawCandidates) {
      if (!item) continue;
      if (typeof item === 'string') {
        const m = item.match(EMAIL_EXTRACT_RE);
        if (m) return m[1].toLowerCase();
      } else if (typeof item === 'object') {
        const sub = item.email || item.address || item.from_email || item.value ||
          (Array.isArray(item) && item[0] && (item[0].email || item[0].address || item[0]));
        if (typeof sub === 'string') {
          const m = sub.match(EMAIL_EXTRACT_RE);
          if (m) return m[1].toLowerCase();
        }
      }
    }
    return '';
  }

  function estimateChainDepth(rawObj, fullText) {
    const obj = unwrapVueValue(rawObj);
    let explicitCount = 0;
    if (obj && typeof obj === 'object') {
      const src = obj.attributes && typeof obj.attributes === 'object' ? { ...obj, ...obj.attributes } : obj;
      explicitCount = Number(
        src.messages_count || src.thread_count || src.count || src.letters_count ||
        (Array.isArray(src.messages) ? src.messages.length : 0) ||
        (Array.isArray(src.letters) ? src.letters.length : 0)
      ) || 0;
    }
    if (explicitCount > 1) return explicitCount;
    if (!fullText || typeof fullText !== 'string') return 0;

    const blockquotes = (fullText.match(/<blockquote/gi) || []).length;
    const replyHeaders = (fullText.match(/(написал\(а\)|wrote:|-----Original Message-----|От кого:|От:\s)/gi) || []).length;
    const signatures = (fullText.match(/Буду признателен за ответ/gi) || []).length;

    const depthFromQuotes = Math.max(blockquotes, replyHeaders, signatures);
    return depthFromQuotes >= 1 ? depthFromQuotes + 1 : 0;
  }

  function collectStringsFromObject(rawObj, depth = 0, seen = new Set()) {
    const obj = unwrapVueValue(rawObj);
    if (!obj || typeof obj !== 'object' || depth > 6 || seen.has(obj)) return '';
    if (obj instanceof Node || obj === window || obj === document) return '';
    seen.add(obj);

    let parts = [];
    let keys;
    try { keys = Object.keys(obj); } catch (e) { return ''; }

    for (const k of keys) {
      if (k === 'vnode' || k === 'parent' || k === 'subTree' || k === 'appContext' || k === 'deps' || k === 'effects' || k === '$el' || k === '$parent' || k === '$root' || k === '$children' || k === '_vnode' || k === '__v_skip') {
        continue;
      }
      let val;
      try { val = unwrapVueValue(obj[k]); } catch (e) { continue; }

      if (typeof val === 'string' && val.length > 0 && val.length < 300000) {
        parts.push(val);
      } else if (typeof val === 'object' && val !== null) {
        parts.push(collectStringsFromObject(val, depth + 1, seen));
      }
    }
    return parts.join('\n');
  }

  function normalizeSubj(s) {
    if (!s || typeof s !== 'string') return '';
    return s.replace(/^(?:(?:re|fwd|отв):\s*)+/i, '').replace(/\s+/g, ' ').trim().toLowerCase();
  }

  function registerEmailObject(rawObj, isFromDetailFetch = false) {
    const rawNode = unwrapVueValue(rawObj);
    if (!rawNode || typeof rawNode !== 'object' || Array.isArray(rawNode) || rawNode instanceof Node) return false;

    if (Array.isArray(rawNode.data) || Array.isArray(rawNode.items) || Array.isArray(rawNode.letters) || Array.isArray(rawNode.threads)) {
      return false;
    }

    const id = rawNode.id || rawNode.uid || rawNode.email_id || rawNode.message_id || rawNode.letter_id ||
      findFieldDeep(rawNode, ['id', 'uid', 'email_id', 'message_id', 'letter_id', 'uuid', '_id']);
    const subject = findFieldDeep(rawNode, ['subject', 'theme', 'title', 'caption']);
    const bodyStr = findFieldDeep(rawNode, ['body', 'body_html', 'body_text', 'html', 'text', 'content', 'message_body', 'full_text']);
    const snippetStr = findFieldDeep(rawNode, ['preview', 'snippet', 'short_text', 'excerpt']);
    const senderEmail = extractSenderEmail(rawNode);

    const hasMailFields = Boolean(subject || bodyStr || snippetStr || senderEmail);
    if (!id && !subject) return false;
    if (!hasMailFields) return false;

    if (debugSampleKeys.length === 0) {
      try {
        const ks = Object.keys(rawNode).filter(k => !k.startsWith('$'));
        if (ks.length >= 2) debugSampleKeys = ks.slice(0, 12);
      } catch (e) {}
    }

    const strId = id ? String(id) : `subj_${normalizeSubj(subject)}`;
    const fullText = collectStringsFromObject(rawNode);
    const chainDepth = estimateChainDepth(rawNode, fullText);

    detectTrailing7CharCode(bodyStr);
    detectTrailing7CharCode(snippetStr);
    detectTrailing7CharCode(fullText);

    const prev = emailDataById.get(strId);
    const mergedText = prev
      ? (prev.fullText.includes(fullText) ? prev.fullText : (prev.fullText + '\n' + fullText))
      : fullText;
    const mergedBodyLen = Math.max(bodyStr.length, prev ? (prev.bodyLen || 0) : 0);
    const mergedDepth = Math.max(chainDepth, prev ? (prev.chainDepth || 0) : 0);

    const record = {
      id: id ? String(id) : (prev ? prev.id : null),
      subject: subject || (prev ? prev.subject : ''),
      normSubject: normalizeSubj(subject || (prev ? prev.subject : '')),
      senderEmail: senderEmail || (prev ? prev.senderEmail : ''),
      fullText: mergedText,
      bodyLen: mergedBodyLen,
      chainDepth: mergedDepth
    };

    emailDataById.set(strId, record);

    if (isFromDetailFetch || mergedBodyLen > 140) {
      debugBodiesChecked++;
    }

    const matchedCode = hasWarmupCode(mergedText);
    if (matchedCode) {
      if (record.id) {
        warmupIds.add(record.id);
        cachedLetterVerdicts[record.id] = 'warmup';
      }
      if (record.subject) warmupSubjects.add(record.subject.toLowerCase());
      if (record.normSubject) warmupSubjects.add(record.normSubject);
      saveCache();
    } else if (isFromDetailFetch && record.id) {
      cachedLetterVerdicts[record.id] = 'safe';
      saveCache();
    }

    return true;
  }

  function extractAndScanEmails(rawNode, depth = 0, seen = new Set(), isFromDetailFetch = false) {
    const node = unwrapVueValue(rawNode);
    if (!node || typeof node !== 'object' || depth > 9 || seen.has(node)) return false;
    if (node instanceof Node || node === window || node === document) return false;
    seen.add(node);

    let foundAny = false;

    if (Array.isArray(node)) {
      for (let i = 0; i < node.length; i++) {
        if (extractAndScanEmails(node[i], depth + 1, seen, isFromDetailFetch)) foundAny = true;
      }
      return foundAny;
    }

    if (registerEmailObject(node, isFromDetailFetch)) {
      foundAny = true;
    }

    let keys;
    try { keys = Object.keys(node); } catch (e) { return foundAny; }

    for (const k of keys) {
      if (k === 'vnode' || k === 'parent' || k === 'appContext' || k === 'deps' || k === 'effects' || k === '$el' || k === '$parent' || k === '$root' || k === '__v_skip') {
        continue;
      }
      let val;
      try { val = unwrapVueValue(node[k]); } catch (e) { continue; }
      if (typeof val === 'object' && val !== null) {
        if (extractAndScanEmails(val, depth + 1, seen, isFromDetailFetch)) foundAny = true;
      }
    }

    return foundAny;
  }

  function scanPerformanceUrls() {
    try {
      const entries = performance.getEntriesByType('resource') || [];
      for (const entry of entries) {
        if (entry.initiatorType !== 'xmlhttprequest' && entry.initiatorType !== 'fetch') continue;
        const url = entry.name || '';
        if (!url || url.includes('.js') || url.includes('.css') || url.includes('.png') || url.includes('.svg')) continue;

        const clean = url.split('?')[0].replace(/\/+$/, '');
        if (/mail|letter|message|inbox|thread|box|email/i.test(clean)) {
          if (!debugApiUrls.includes(clean)) debugApiUrls.push(clean);
        }
      }
    } catch (e) {}
  }

  function mapVNodesToDomRows(vnode, depth = 0, seen = new Set()) {
    if (!vnode || typeof vnode !== 'object' || depth > 18 || seen.has(vnode)) return;
    seen.add(vnode);

    const domEl = vnode.el || vnode.elm;
    if (domEl && domEl.nodeType === 1 && domEl.getAttribute && domEl.getAttribute('data-ct-row') === '1') {
      if (vnode.key !== undefined && vnode.key !== null && !domEl.getAttribute('data-ct-id')) {
        domEl.setAttribute('data-ct-id', String(vnode.key));
      }
      if (vnode.props && typeof vnode.props === 'object') {
        registerEmailObject(vnode.props.item || vnode.props.letter || vnode.props.message || vnode.props.row || vnode.props);
      }
      if (vnode.component) {
        const c = vnode.component;
        registerEmailObject(c.props?.item || c.props?.letter || c.props?.message || c.props);
        registerEmailObject(c.setupState?.item || c.setupState?.letter || c.setupState?.message);
      }
    }

    if (Array.isArray(vnode.children)) {
      for (const child of vnode.children) {
        mapVNodesToDomRows(child, depth + 1, seen);
      }
    } else if (vnode.children && typeof vnode.children === 'object') {
      mapVNodesToDomRows(vnode.children, depth + 1, seen);
    }

    if (vnode.component && vnode.component.subTree) {
      mapVNodesToDomRows(vnode.component.subTree, depth + 1, seen);
    }
    if (vnode.child && vnode.child._vnode) {
      mapVNodesToDomRows(vnode.child._vnode, depth + 1, seen);
    }
  }

  function scanGlobalVueAndStores() {
    const rootsToScan = new Set();
    const rows = document.querySelectorAll('[data-ct-row="1"]');
    rows.forEach(r => {
      let curr = r;
      while (curr && curr !== document.documentElement) {
        rootsToScan.add(curr);
        curr = curr.parentElement;
      }
    });

    document.querySelectorAll('#app, [id*="app"], main, table, [class*="mail"], [class*="inbox"], [class*="list"], [class*="modal"], [class*="dialog"]').forEach(el => {
      rootsToScan.add(el);
    });

    const seenVueObjs = new Set();
    const seenVNodes = new Set();

    rootsToScan.forEach(el => {
      if (el.__vue__) {
        const v = el.__vue__;
        if (v._vnode) mapVNodesToDomRows(v._vnode, 0, seenVNodes);
        extractAndScanEmails(v.$data || v._data, 0, seenVueObjs);
        extractAndScanEmails(v.$props || v._props, 0, seenVueObjs);
        if (v._computedWatchers) {
          Object.keys(v._computedWatchers).forEach(k => {
            try { extractAndScanEmails(v._computedWatchers[k].value, 0, seenVueObjs); } catch (e) {}
          });
        }
        const store = v.$store || (v.$root && v.$root.$store);
        if (store && store.state) {
          extractAndScanEmails(store.state, 0, seenVueObjs);
        }
      }

      if (el.__vueParentComponent) {
        let comp = el.__vueParentComponent;
        for (let step = 0; step < 8 && comp; step++) {
          if (comp.subTree) mapVNodesToDomRows(comp.subTree, 0, seenVNodes);
          extractAndScanEmails(comp.props, 0, seenVueObjs);
          extractAndScanEmails(comp.setupState, 0, seenVueObjs);
          extractAndScanEmails(comp.data, 0, seenVueObjs);
          extractAndScanEmails(comp.ctx, 0, seenVueObjs);
          comp = comp.parent;
        }
      }

      if (el.__vue_app__) {
        const app = el.__vue_app__;
        const gp = app.config && app.config.globalProperties;
        if (gp) {
          if (gp.$store && gp.$store.state) {
            extractAndScanEmails(gp.$store.state, 0, seenVueObjs);
          }
          if (gp.$pinia && gp.$pinia._s && gp.$pinia._s instanceof Map) {
            gp.$pinia._s.forEach(store => {
              extractAndScanEmails(store.$state || store, 0, seenVueObjs);
            });
          }
        }
        if (app._instance) {
          if (app._instance.subTree) mapVNodesToDomRows(app._instance.subTree, 0, seenVNodes);
          extractAndScanEmails(app._instance.setupState, 0, seenVueObjs);
          extractAndScanEmails(app._instance.data, 0, seenVueObjs);
        }
      }
    });
  }

  function matchRowToEmailRecords(row) {
    const matches = [];
    const existingId = row.getAttribute('data-ct-id') || row.getAttribute('data-id') || row.getAttribute('data-email-id');
    if (existingId && emailDataById.has(String(existingId))) {
      matches.push(emailDataById.get(String(existingId)));
    }

    const rowTextLower = (row.textContent || '').replace(/\s+/g, ' ').trim().toLowerCase();
    if (!rowTextLower) return matches;

    for (const [, record] of emailDataById.entries()) {
      if (record.normSubject && record.normSubject.length >= 4 && rowTextLower.includes(record.normSubject)) {
        if (!matches.includes(record)) {
          matches.push(record);
        }
      }
    }

    return matches;
  }

  function inspectDomVueRows() {
    const rows = document.querySelectorAll('[data-ct-row="1"]');

    rows.forEach(row => {
      detectTrailing7CharCode(row.textContent || '');

      const records = matchRowToEmailRecords(row);

      let extractedId = row.getAttribute('data-ct-id') || null;
      let extractedText = '';
      let extractedSubject = '';
      let extractedSender = row.getAttribute('data-ct-sender-email') || '';
      let chainDepth = 0;

      for (const record of records) {
        if (record.id && !extractedId) extractedId = record.id;
        if (record.subject && !extractedSubject) extractedSubject = record.subject;
        if (record.senderEmail && !extractedSender) extractedSender = record.senderEmail;
        if (record.fullText) extractedText += '\n' + record.fullText;
        if ((record.chainDepth || 0) > chainDepth) chainDepth = record.chainDepth;
      }

      if (extractedId) {
        row.setAttribute('data-ct-id', String(extractedId));
      }

      if (extractedSender) {
        row.setAttribute('data-ct-sender-email', extractedSender);
      }

      if (chainDepth > 1) {
        row.setAttribute('data-ct-chain', String(chainDepth));
      }

      const fullRowContext = (row.textContent || '') + '\n' + extractedText;
      if (fullRowContext.length > debugSampleLen) {
        debugSampleLen = fullRowContext.length;
      }

      if (extractedText.trim()) {
        row.setAttribute('data-ct-meta', extractedText.slice(0, 5000).toLowerCase());
      }

      const isKnownWarmupId = extractedId && (warmupIds.has(String(extractedId)) || cachedLetterVerdicts[String(extractedId)] === 'warmup') ||
        records.some(r => r.id && (warmupIds.has(String(r.id)) || cachedLetterVerdicts[String(r.id)] === 'warmup'));
      
      const normSub = normalizeSubj(extractedSubject);
      const isKnownWarmupSubj = (normSub && warmupSubjects.has(normSub)) ||
        (extractedSubject && warmupSubjects.has(extractedSubject.toLowerCase()));

      const matched = hasWarmupCode(fullRowContext);

      if (matched || isKnownWarmupId || isKnownWarmupSubj) {
        row.setAttribute('data-ct-warmup', matched || 'id');
        if (extractedId) {
          warmupIds.add(String(extractedId));
          cachedLetterVerdicts[String(extractedId)] = 'warmup';
        }
        if (extractedSubject) warmupSubjects.add(extractedSubject.trim().toLowerCase());
        if (normSub) warmupSubjects.add(normSub);
        saveCache();
      } else if (extractedId && cachedLetterVerdicts[String(extractedId)] === 'safe') {
        row.removeAttribute('data-ct-warmup');
      }
    });
  }

  function reScanMemory() {
    for (const [, record] of emailDataById.entries()) {
      if (hasWarmupCode(record.fullText)) {
        if (record.id) {
          warmupIds.add(String(record.id));
          cachedLetterVerdicts[String(record.id)] = 'warmup';
        }
        if (record.subject) warmupSubjects.add(record.subject.trim().toLowerCase());
        if (record.normSubject) warmupSubjects.add(record.normSubject);
      }
    }
  }

  // --- Background Scanner for visible inbox rows ---
  const activeFetchSet = new Set();
  const fetchQueue = [];
  let isProcessingQueue = false;

  function triggerVisibleRowsScan() {
    if (!confirmedDetailUrlTemplate) return;

    const rows = document.querySelectorAll('[data-ct-row="1"]');
    rows.forEach(row => {
      const id = row.getAttribute('data-ct-id');
      if (!id || id.startsWith('subj_')) return;

      const verdict = cachedLetterVerdicts[id];
      if (verdict === 'warmup') {
        row.setAttribute('data-ct-warmup', 'cached');
        return;
      }
      if (verdict === 'safe') return;

      if (!activeFetchSet.has(id)) {
        activeFetchSet.add(id);
        fetchQueue.push(id);
      }
    });

    processScanQueue();
  }

  async function processScanQueue() {
    if (isProcessingQueue || fetchQueue.length === 0 || !confirmedDetailUrlTemplate) return;
    isProcessingQueue = true;

    while (fetchQueue.length > 0) {
      const id = fetchQueue.shift();
      if (cachedLetterVerdicts[id]) continue;

      const targetUrl = confirmedDetailUrlTemplate.replace('{id}', id);
      try {
        const headers = { ...lastCapturedHeaders };
        const res = await origFetch(targetUrl, {
          method: confirmedDetailMethod || 'GET',
          headers,
          credentials: 'include'
        });

        if (res.ok) {
          const text = await res.text();
          debugBodiesChecked++;
          const code = hasWarmupCode(text);

          if (code) {
            cachedLetterVerdicts[id] = 'warmup';
            warmupIds.add(String(id));
            const row = document.querySelector(`[data-ct-row="1"][data-ct-id="${id}"]`);
            if (row) row.setAttribute('data-ct-warmup', code);
            
            try {
              const parsed = JSON.parse(text);
              extractAndScanEmails(parsed, 0, new Set(), true);
            } catch (e) {}

            saveCache();
            notifyContentScript();
          } else {
            cachedLetterVerdicts[id] = 'safe';
            saveCache();
          }
        }
      } catch (e) {}

      // Gentle pause to avoid rate limiting
      await new Promise(r => setTimeout(r, 45));
    }

    isProcessingQueue = false;
  }

  // --- Network Interceptor (Fetch & XHR) ---
  function processApiPayload(url, text, isDetailFetch = false, method = 'GET') {
    if (!text || typeof text !== 'string') return;
    const urlStr = typeof url === 'string' ? url : String(url || '');

    if (urlStr && !urlStr.includes('.js') && !urlStr.includes('.css') && !urlStr.includes('.png')) {
      const cleanUrl = urlStr.split('?')[0].replace(/\/+$/, '');
      if (/mail|letter|message|inbox|dialog|communication|email/i.test(cleanUrl)) {
        if (!debugApiUrls.includes(cleanUrl)) debugApiUrls.push(cleanUrl);
      }
    }

    const rawMatched = hasWarmupCode(text);

    try {
      const parsed = JSON.parse(text);
      const hadEmails = extractAndScanEmails(parsed, 0, new Set(), isDetailFetch);

      // Inspect if this response contains a single email / detail body
      const candidateId = parsed.id || parsed.letter_id || parsed.data?.id || parsed.letter?.id || parsed.email?.id;
      const candidateBody = parsed.body || parsed.body_html || parsed.html || parsed.text ||
        parsed.data?.body || parsed.data?.text || parsed.letter?.body || parsed.letter?.text;

      const isSingleEmailDetail = Boolean(candidateId && (candidateBody || (typeof text === 'string' && text.length > 250)));

      // Auto-capture the confirmed detail URL template
      if (isSingleEmailDetail) {
        const idStr = String(candidateId);
        if (urlStr.includes(idStr)) {
          confirmedDetailUrlTemplate = urlStr.replace(idStr, '{id}');
          confirmedDetailMethod = method || 'GET';
          saveCache();
        } else if (lastClickedRowId && (Date.now() - lastClickedTime < 2500)) {
          if (urlStr.includes(lastClickedRowId)) {
            confirmedDetailUrlTemplate = urlStr.replace(lastClickedRowId, '{id}');
            confirmedDetailMethod = method || 'GET';
            saveCache();
          }
        }

        if (rawMatched) {
          warmupIds.add(idStr);
          cachedLetterVerdicts[idStr] = 'warmup';
          saveCache();
        } else if (candidateBody && candidateBody.length > 80) {
          cachedLetterVerdicts[idStr] = 'safe';
          saveCache();
        }

        triggerVisibleRowsScan();
      }

      if (rawMatched || hadEmails || isDetailFetch) {
        saveCache();
        inspectDomVueRows();
        notifyContentScript();
      }
    } catch (e) {}
  }

  const origFetch = window.fetch;
  window.fetch = async function (...args) {
    let method = 'GET';
    try {
      const req = args[0];
      const opts = args[1] || {};
      method = (opts.method || (req && req.method) || 'GET').toUpperCase();

      if (opts.headers) {
        if (opts.headers instanceof Headers) {
          opts.headers.forEach((v, k) => { lastCapturedHeaders[k] = v; });
        } else if (typeof opts.headers === 'object') {
          Object.assign(lastCapturedHeaders, opts.headers);
        }
      }
    } catch (e) {}

    const res = await origFetch.apply(this, args);
    try {
      const url = typeof args[0] === 'string' ? args[0] : (args[0]?.url || '');
      const clone = res.clone();
      clone.text().then(text => processApiPayload(url, text, false, method)).catch(() => {});
    } catch (e) {}
    return res;
  };

  const origOpen = XMLHttpRequest.prototype.open;
  const origSetHeader = XMLHttpRequest.prototype.setRequestHeader;
  const origSend = XMLHttpRequest.prototype.send;

  XMLHttpRequest.prototype.open = function (method, url, ...rest) {
    this._ct_req_url = typeof url === 'string' ? url : String(url || '');
    this._ct_req_method = (method || 'GET').toUpperCase();
    return origOpen.apply(this, [method, url, ...rest]);
  };

  XMLHttpRequest.prototype.setRequestHeader = function (header, value) {
    if (header && value) {
      lastCapturedHeaders[header] = value;
    }
    return origSetHeader.apply(this, [header, value]);
  };

  XMLHttpRequest.prototype.send = function (...args) {
    const reqUrl = this._ct_req_url || '';
    const reqMethod = this._ct_req_method || 'GET';

    this.addEventListener('load', function () {
      try {
        if (this.responseType === '' || this.responseType === 'text') {
          processApiPayload(reqUrl, this.responseText, false, reqMethod);
        } else if (this.responseType === 'json' && this.response) {
          processApiPayload(reqUrl, JSON.stringify(this.response), false, reqMethod);
        }
      } catch (e) {}
    });
    return origSend.apply(this, args);
  };
})();
