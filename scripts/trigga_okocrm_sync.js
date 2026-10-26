/**
 * Trigga <-> OkoCRM Bidirectional Sync Engine
 * 
 * Features:
 * 1. Pulls incoming campaign replies from Trigga API (https://api.trigga.ru/api/public/v1).
 *    (Zero warmup bots exist in Trigga inbox - warmup emails are excluded at source).
 * 2. Filters out auto-replies (out of office, vacation, delivery notifications, etc.).
 * 3. Filters out flat rejections ("не актуально", "отпишитесь" without deferral).
 *    Keeps deferred rejections ("сейчас не актуально, напомните через полгода").
 * 4. Deduplication: verifies contact and deal existence in OkoCRM before creation.
 *    Never creates duplicate leads for contacts that already have deals.
 * 5. 50/50 round-robin lead distribution between Andrey (28418) and Leonid (28419).
 * 6. Sets Source = "Email" (78389), creates Contact, Company and attaches correspondence Note.
 * 7. Two-way sync:
 *    - Deal moved to "Первичный контакт" (or further) -> sets Trigga status "interested"
 *    - Deal closed with "Trigga черный список" -> adds lead to Trigga Blacklist & sets "not_interested"
 */

const https = require('https');
const fs = require('fs');
const path = require('path');

// Configuration
const CONFIG = {
  trigga: {
    baseUrl: 'https://api.trigga.ru/api/public/v1',
    token: 'TRIGGA_API_KEY_PLACEHOLDER',
  },
  okocrm: {
    url: 'https://mcp.okocrm.com/crm',
    token: 'OKOCRM_TOKEN_PLACEHOLDER',
    pipelineId: 30895, // B2B лидогенерация
    stageName: 'Лид с Trigga',
    sourceOptionName: 'Email',
    lossReasonName: 'Trigga черный список',
  },
  managers: [
    { id: 28418, name: 'Andrey', email: 'andrey.s@calltalk.ru' },
    { id: 28419, name: 'Leonid', email: 'leonid.g@calltalk.ru' }
  ],
  stateFilePath: path.join(__dirname, 'trigga_sync_state.json'),
  logFilePath: path.join(__dirname, 'sync.log'),
  errorLogFilePath: path.join(__dirname, 'error.log'),
  syncIntervalMinutes: 5,
};

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

// Logging helper
function log(msg, isError = false) {
  const ts = new Date().toISOString();
  const line = `[${ts}] ${msg}`;
  console.log(line);
  try {
    fs.appendFileSync(CONFIG.logFilePath, line + '\n');
    if (isError) {
      fs.appendFileSync(CONFIG.errorLogFilePath, line + '\n');
    }
  } catch (e) {
    // ignore
  }
}

// State Management
function loadState() {
  if (fs.existsSync(CONFIG.stateFilePath)) {
    try {
      return JSON.parse(fs.readFileSync(CONFIG.stateFilePath, 'utf8'));
    } catch (e) {
      log('Failed to parse state file, initializing new state: ' + e.message, true);
    }
  }
  return {
    nextManagerIndex: 0,
    processedLeads: {}, // lead_id -> { okoLeadId, email, contactId, companyId, responsibleId, createdAt, triggaStatus }
    lastSyncAt: null,
  };
}

function saveState(state) {
  state.lastSyncAt = new Date().toISOString();
  fs.writeFileSync(CONFIG.stateFilePath, JSON.stringify(state, null, 2), 'utf8');
}

// HTTP request helper for Trigga
function callTrigga(apiPath, method = 'GET', body = null) {
  return new Promise((resolve, reject) => {
    const url = new URL(CONFIG.trigga.baseUrl + apiPath);
    const headers = {
      'Authorization': `Bearer ${CONFIG.trigga.token}`,
      'Accept': 'application/json'
    };
    let payload = null;
    if (body) {
      payload = JSON.stringify(body);
      headers['Content-Type'] = 'application/json';
      headers['Content-Length'] = Buffer.byteLength(payload);
    }

    const req = https.request({
      hostname: url.hostname,
      path: url.pathname + url.search,
      method: method,
      headers: headers
    }, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          try {
            resolve(data ? JSON.parse(data) : null);
          } catch (e) {
            resolve(data);
          }
        } else {
          reject(new Error(`Trigga API error ${res.statusCode}: ${data}`));
        }
      });
    });

    req.on('error', reject);
    if (payload) req.write(payload);
    req.end();
  });
}

// HTTP request helper for OkoCRM MCP with retry on 429
let rpcId = 1;
async function callOko(toolName, args = {}, retryCount = 0) {
  await sleep(400); // polite rate limit throttle
  return new Promise((resolve, reject) => {
    const payload = JSON.stringify({
      jsonrpc: '2.0',
      id: rpcId++,
      method: 'tools/call',
      params: {
        name: toolName,
        arguments: args
      }
    });

    const req = https.request({
      hostname: 'mcp.okocrm.com',
      path: '/crm',
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${CONFIG.okocrm.token}`,
        'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(payload)
      }
    }, async (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', async () => {
        if (res.statusCode === 429 && retryCount < 3) {
          log(`⚠️ Rate limit (429) hit on ${toolName}, waiting 4s and retrying (attempt ${retryCount + 1})...`);
          await sleep(4000);
          try {
            const retryRes = await callOko(toolName, args, retryCount + 1);
            return resolve(retryRes);
          } catch (e) {
            return reject(e);
          }
        }

        if (res.statusCode >= 200 && res.statusCode < 300) {
          try {
            const json = JSON.parse(data);
            if (json.error) {
              return reject(new Error(`OkoCRM MCP error: ${json.error.message || JSON.stringify(json.error)}`));
            }
            const text = json.result?.content?.[0]?.text;
            if (text) {
              try {
                return resolve(JSON.parse(text));
              } catch {
                return resolve(text);
              }
            }
            resolve(json.result);
          } catch (e) {
            reject(new Error(`Failed to parse OkoCRM response: ${e.message} (raw: ${data})`));
          }
        } else {
          reject(new Error(`OkoCRM HTTP error ${res.statusCode}: ${data}`));
        }
      });
    });

    req.on('error', reject);
    req.write(payload);
    req.end();
  });
}

// Strip quoted email history to isolate the fresh reply body
function stripQuotedEmail(text) {
  if (!text) return '';
  const quoteSplitters = [
    /(?:пн|вт|ср|чт|пт|сб|вс|понедельник|вторник|среда|четверг|пятница|суббота|воскресенье)[,\s]+\d{1,2}\s+[а-яё]+.*от\s+/i,
    /\n\s*on\s+.*wrote:/i,
    /\n\s*from:\s+/i,
    /\n\s*от:\s+/i,
    /\n\s*---\s*исходное сообщение\s*---/i,
    /\n\s*---\s*original message\s*---/i,
    /\n\s*_{3,}/
  ];

  let clean = text;
  for (const splitter of quoteSplitters) {
    const parts = clean.split(splitter);
    if (parts.length > 1 && parts[0].trim().length > 0) {
      clean = parts[0];
    }
  }
  return clean.trim();
}

// Smart rejection & auto-reply filters
function isAutoReply(thread, messages) {
  if (thread.user_status === 'auto_reply') return true;

  const markers = [
    'auto-reply', 'автоответ', 'out of office', 'в отпуске', 'нахожусь в отпуске',
    'не доставлено', 'delivery status notification', 'undeliverable',
    'mail delivery subsystem', 'mailbox is full', 'уволен', 'больше не работает',
    'сообщение доставлено', 'не могу ответить', 'автоматическое уведомление',
    'автоматический ответ', 'vacation response'
  ];

  const subj = (thread.subject || '').toLowerCase();
  for (const m of markers) {
    if (subj.includes(m)) return true;
  }

  // Check last reply message
  const replies = (messages || []).filter(m => m.event_type === 'reply');
  const lastReply = replies[replies.length - 1];
  if (lastReply && lastReply.email_text) {
    const text = lastReply.email_text.toLowerCase();
    for (const m of markers) {
      if (text.includes(m)) return true;
    }
  }

  return false;
}

function isFlatRejection(rawReplyText) {
  const cleanBody = stripQuotedEmail(rawReplyText);
  const text = cleanBody.toLowerCase().trim();
  
  // Rejection markers
  const rejectionMarkers = [
    'не актуально', 'неактуально', 'нам не актуально', 'не интересно',
    'неинтересно', 'не нужно', 'удалите из рассылки', 'отпишитесь',
    'отпишите меня', 'хватит спамить', 'не пишите сюда', 'не пишите нам',
    'не пишите больше', 'спам'
  ];

  let hasRejection = false;
  for (const rm of rejectionMarkers) {
    if (text.includes(rm)) {
      hasRejection = true;
      break;
    }
  }

  if (!hasRejection) return false;

  // Deferral markers - if present, DO NOT reject, keep in CRM!
  const deferralMarkers = [
    'сейчас', 'пока', 'позже', 'через', 'вернемся', 'напомните',
    'напишите через', 'полгода', 'квартал', 'весной', 'осенью', 'зимой',
    'летом', 'следующ', 'в следующем', 'позвоните', 'наберите',
    'на следующей', 'в ноябре', 'в декабре', 'в январе', 'в феврале'
  ];

  for (const dm of deferralMarkers) {
    if (text.includes(dm)) {
      return false; // Has deferred interest -> keep it!
    }
  }

  // If text without quotes is short (< 250 chars) and contains rejection with no deferral -> flat reject!
  return text.length < 250;
}

// Clean HTML to text
function htmlToText(html) {
  if (!html) return '';
  return html
    .replace(/<style[^>]*>[\s\S]*?<\/style>/gi, '')
    .replace(/<script[^>]*>[\s\S]*?<\/script>/gi, '')
    .replace(/<br\s*[\/]?>/gi, '\n')
    .replace(/<\/p>/gi, '\n\n')
    .replace(/<\/div>/gi, '\n')
    .replace(/<[^>]+>/g, '')
    .replace(/&nbsp;/g, ' ')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&amp;/g, '&')
    .replace(/&#160;/g, ' ')
    .replace(/&#1072;/gi, 'а')
    .replace(/&#1079;/gi, 'з')
    .replace(/&#1082;/gi, 'к')
    .replace(/&#1088;/gi, 'р')
    .replace(/&#1086;/gi, 'о')
    .replace(/&#1073;/gi, 'б')
    .replace(/&#1090;/gi, 'т')
    .replace(/&#1082;/gi, 'к')
    .replace(/&#1091;/gi, 'у')
    .replace(/&#1058;/gi, 'Т')
    .replace(/&#1077;/gi, 'е')
    .replace(/&#1093;/gi, 'х')
    .replace(/&#1085;/gi, 'н')
    .replace(/&#1075;/gi, 'г')
    .replace(/&#1088;/gi, 'р')
    .replace(/&#1076;/gi, 'д')
    .replace(/&#\d+;/g, '')
    .replace(/\r/g, '')
    .replace(/\n\s*\n\s*\n/g, '\n\n')
    .trim();
}

// Extract Name, Phone, Company from thread & messages
function extractLeadInfo(thread, threadDetail) {
  const leadEmail = thread.lead_email;
  const messages = threadDetail.messages || [];
  const sendMessages = messages.filter(m => m.event_type === 'send');
  const replyMessages = messages.filter(m => m.event_type === 'reply');
  const lastReply = replyMessages[replyMessages.length - 1];
  const replyText = lastReply ? htmlToText(lastReply.email_text) : '';
  const firstSendText = sendMessages.length > 0 ? htmlToText(sendMessages[0].email_text) : '';

  let name = '';
  let phone = '';
  let company = '';

  // 1. Try signature in reply: "С уважением, [Имя Фамилия]"
  const sigMatch = replyText.match(/с\s+уважением,?\s*([А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ][а-яё]+)?)/i);
  if (sigMatch && sigMatch[1]) {
    const words = sigMatch[1].trim().split(/\s+/);
    const stopProfessions = ['программист', 'инженер', 'менеджер', 'руководитель', 'директор', 'специалист', 'ведущий', 'заместитель', 'главный', 'отдел'];
    if (words.length > 1 && stopProfessions.includes(words[1].toLowerCase())) {
      name = words[0];
    } else if (!stopProfessions.includes(words[0].toLowerCase())) {
      name = sigMatch[1].trim();
    }
  }

  // 2. Try greeting in initial outreach: "Здравствуйте, [Имя]!"
  if (!name && firstSendText) {
    const greetMatch = firstSendText.match(/Здравствуйте,\s*([А-ЯЁA-Z][а-яёa-z]+)/i);
    if (greetMatch && greetMatch[1]) {
      name = greetMatch[1].trim();
    }
  }

  // 3. Try extracting phone from reply text
  const phoneRegex = /(?:\+7|8)[\s\(\)-]*\d{3}[\s\(\)-]*\d{3}[\s\(\)-]*\d{2}[\s\(\)-]*\d{2}/;
  const phoneMatch = replyText.match(phoneRegex);
  if (phoneMatch) {
    phone = phoneMatch[0].replace(/[^\d+]/g, '');
    if (phone.startsWith('8')) phone = '+7' + phone.slice(1);
  }

  // 4. Try extracting company from subject e.g. "для [Компания]"
  const subj = thread.subject || '';
  const compMatch = subj.match(/для\s+([«"][^»"]+[»"]|[А-ЯЁA-Z0-9][\w\s«»"-]{2,30})/i);
  if (compMatch && compMatch[1]) {
    company = compMatch[1].replace(/[«»"]/g, '').trim();
  }

  // Fallback company from domain if still empty
  if (!company && leadEmail) {
    const domain = leadEmail.split('@')[1];
    if (domain && !['gmail.com', 'mail.ru', 'yandex.ru', 'bk.ru', 'inbox.ru', 'list.ru'].includes(domain)) {
      company = domain.split('.')[0].toUpperCase();
    }
  }

  // Fallback name if empty
  if (!name) {
    const parts = (leadEmail || '').split('@')[0].split(/[._-]/);
    name = parts.map(p => p.charAt(0).toUpperCase() + p.slice(1)).join(' ');
  }

  return { name, phone, company, replyText };
}

// Discover CRM IDs dynamically
async function discoverCrmMetadata() {
  log('Discovering OkoCRM metadata (stages, loss reasons, fields)...');
  
  // Pipeline & Stages
  const pipeRes = await callOko('list_pipelines', { pipeline_id: CONFIG.okocrm.pipelineId });
  const pipeline = pipeRes?.pipelines?.[0];
  if (!pipeline) throw new Error(`Pipeline ${CONFIG.okocrm.pipelineId} not found in OkoCRM!`);

  let targetStage = pipeline.stages.find(s => s.name.toLowerCase().includes(CONFIG.okocrm.stageName.toLowerCase()));
  if (!targetStage) {
    log(`Stage "${CONFIG.okocrm.stageName}" not found by name, using first stage ${pipeline.stages[0].name} (${pipeline.stages[0].id})`, true);
    targetStage = pipeline.stages[0];
  } else {
    log(`Found target stage: "${targetStage.name}" (ID: ${targetStage.id})`);
  }

  // Find stage "Первичный контакт"
  const primaryContactStage = pipeline.stages.find(s => s.name.toLowerCase().includes('первичный контакт') || s.sort === 3);
  const primaryContactSort = primaryContactStage ? primaryContactStage.sort : 3;

  // Loss Reason
  const lossRes = await callOko('list_loss_reasons');
  const reasons = lossRes?.loss_reasons || [];
  let triggaLossReason = reasons.find(r => r.pipeline_id === CONFIG.okocrm.pipelineId && r.name.toLowerCase().includes('trigga'));
  if (!triggaLossReason) {
    log(`Loss reason "${CONFIG.okocrm.lossReasonName}" not found, blacklist sync will fallback to reason ID 58924`, true);
    triggaLossReason = { id: 58924, name: 'Trigga черный список' };
  } else {
    log(`Found loss reason: "${triggaLossReason.name}" (ID: ${triggaLossReason.id})`);
  }

  // Source field "Email"
  const fieldsRes = await callOko('list_fields', { entity_type: 'leads' });
  let emailSourceOptionId = 78389; // Default ID
  try {
    for (const tab of (fieldsRes?.tabs || [])) {
      for (const group of (tab.groups || [])) {
        for (const field of (group.fields || [])) {
          if (field.var_name === 'source_id' && field.options) {
            const opt = field.options.find(o => o.name.toLowerCase() === 'email');
            if (opt) emailSourceOptionId = opt.id;
          }
        }
      }
    }
  } catch (e) {
    log('Could not dynamically find source_id option, using 78389', true);
  }

  return {
    stageId: targetStage.id,
    primaryContactSort: primaryContactSort,
    lossReasonId: triggaLossReason.id,
    emailSourceOptionId: emailSourceOptionId
  };
}

// Strict Deduplication Check in OkoCRM
async function findExistingContactAndDeal(email) {
  try {
    // 1. Search leads directly by email query
    const leadsRes = await callOko('search_leads', { query: email });
    const leads = leadsRes?.items || [];
    
    // 2. Search contacts directly by email query
    const contactsRes = await callOko('search_contacts', { query: email });
    const contacts = contactsRes?.items || [];
    const match = contacts.find(c => (c.emails || []).some(e => e.toLowerCase() === email.toLowerCase()));

    if (leads.length > 0) {
      return { contact: match || null, existingLead: leads[0] };
    }

    if (!match) return { contact: null, existingLead: null };

    // If contact exists, check its leads
    const contactDetail = await callOko('get_contact', { contact_id: match.id });
    const cLeads = contactDetail?.leads || [];
    const pipelineLead = cLeads.find(l => l.pipeline_id === CONFIG.okocrm.pipelineId);

    return { contact: match, existingLead: pipelineLead || null };
  } catch (e) {
    log(`Error checking existing contact/lead for ${email}: ${e.message}`, true);
    return { contact: null, existingLead: null };
  }
}

// Extract additional colleagues / copy participants
function extractAdditionalParticipants(threadDetail) {
  const ourDomains = ['calltalk.ru', 'call-talk.ru', 'calltalks.ru', 'email-talk.ru'];
  const leadEmail = (threadDetail.lead_email || '').toLowerCase().trim();
  const additional = [];

  const participants = threadDetail.participants || [];
  for (const p of participants) {
    const email = (p.value || '').toLowerCase().trim();
    if (!email || !email.includes('@')) continue;
    const domain = email.split('@')[1] || '';
    if (ourDomains.includes(domain)) continue; // our mailbox
    if (email === leadEmail) continue; // primary lead

    additional.push({
      email: p.value,
      name: p.name || (p.label ? p.label.replace(/<[^>]+>/, '').trim() : email.split('@')[0]),
      label: p.label || p.value
    });
  }

  // Also check messages replied_to_emails and replied_carbon_copy
  const messages = threadDetail.messages || [];
  for (const m of messages) {
    const list = [...(m.replied_to_emails || []), ...(m.replied_carbon_copy || [])];
    for (const item of list) {
      const emailMatch = item.match(/<([^>]+)>/) || [null, item];
      const email = (emailMatch[1] || item).trim().toLowerCase();
      const domain = email.split('@')[1] || '';
      if (!email.includes('@') || ourDomains.includes(domain) || email === leadEmail) continue;

      if (!additional.some(a => a.email.toLowerCase() === email)) {
        const namePart = item.split('<')[0].trim();
        additional.push({
          email: email,
          name: namePart && namePart !== item ? namePart : email.split('@')[0],
          label: item
        });
      }
    }
  }

  return additional;
}

// Format note content
function formatNote(threadDetail, info) {
  const messages = threadDetail.messages || [];
  let note = `📨 ВХОДЯЩИЙ ОТВЕТ ИЗ TRIGGA\n`;
  note += `Кампания: ${threadDetail.campaign_name || 'Call-Talk аутрич'}\n`;
  note += `Лид: ${threadDetail.lead_email}\n`;
  if (info.phone) note += `Телефон: ${info.phone}\n`;
  if (info.company) note += `Компания: ${info.company}\n`;

  const additional = extractAdditionalParticipants(threadDetail);
  if (additional.length > 0) {
    note += `👥 Добавлены в копию/диалог: ${additional.map(a => `${a.name} <${a.email}>`).join(', ')}\n`;
  }
  note += `\n──────────────────────────────────────\n`;

  // Add outgoing messages
  const sent = messages.filter(m => m.event_type === 'send');
  if (sent.length > 0) {
    note += `📤 ИСХОДЯЩИЕ КАСАНИЯ (Call-Talk):\n`;
    sent.forEach((m, idx) => {
      note += `\n[Письмо №${idx + 1}] Тема: ${m.email_subject || ''}\n`;
      note += `${htmlToText(m.email_text).slice(0, 400)}...\n`;
    });
    note += `\n──────────────────────────────────────\n`;
  }

  // Add replies
  const replies = messages.filter(m => m.event_type === 'reply');
  note += `📥 ОТВЕТ КЛИЕНТА:\n`;
  replies.forEach((m) => {
    note += `От: ${m.replied_from_email || threadDetail.lead_email}\n`;
    if (m.replied_to_emails && m.replied_to_emails.length > 0) {
      note += `Кому: ${m.replied_to_emails.join(', ')}\n`;
    }
    if (m.replied_carbon_copy && m.replied_carbon_copy.length > 0) {
      note += `Копия (Cc): ${m.replied_carbon_copy.join(', ')}\n`;
    }
    note += `\n${htmlToText(m.email_text)}\n\n`;
  });

  return note.slice(0, 4800); // OkoCRM note limit is 4900
}

// Main Sync Routine
async function runSync(options = { dryRun: false }) {
  log(`=== Starting Trigga <-> OkoCRM Sync (dryRun: ${options.dryRun}) ===`);
  const state = loadState();
  const meta = await discoverCrmMetadata();

  // 1. Fetch Page 1 of threads from Trigga
  log('Fetching threads from Trigga...');
  const threadsData = await callTrigga('/inbox/threads/?page=1');
  const threads = threadsData?.data || [];
  log(`Fetched ${threads.length} threads from Trigga inbox.`);

  // Find index of starting cutoff (alexandr@atomlog.pro)
  const CUTOFF_EMAIL = 'alexandr@atomlog.pro';
  const cutoffIndex = threads.findIndex(t => t.lead_email === CUTOFF_EMAIL);
  
  if (cutoffIndex === -1) {
    log(`Cutoff email ${CUTOFF_EMAIL} not found on page 1, processing unread threads.`, true);
  }

  // Threads from cutoff up to newest, in chronological order (oldest first)
  const threadsToConsider = cutoffIndex !== -1 
    ? threads.slice(0, cutoffIndex + 1).reverse()
    : threads.slice().reverse();

  log(`Evaluating ${threadsToConsider.length} threads in chronological order...`);

  // Track historical threads older than cutoff so they are never touched
  if (cutoffIndex !== -1) {
    const historicalThreads = threads.slice(cutoffIndex + 1);
    for (const ht of historicalThreads) {
      if (!state.processedLeads[ht.lead_id]) {
        state.processedLeads[ht.lead_id] = {
          skippedHistorical: true,
          email: ht.lead_email,
          recordedAt: new Date().toISOString()
        };
      }
    }
  }

  let createdCount = 0;
  let skippedCount = 0;

  for (const thread of threadsToConsider) {
    const leadId = thread.lead_id;
    const leadEmail = thread.lead_email;

    // Check local state
    if (state.processedLeads[leadId] && state.processedLeads[leadId].okoLeadId) {
      continue;
    }

    log(`\nEvaluating lead_id ${leadId} (${leadEmail}): "${thread.subject}"`);

    // Fetch full thread details
    const threadDetail = await callTrigga(`/inbox/threads/${leadId}/`);
    const messages = threadDetail?.messages || [];

    // Filter 1: Auto-reply
    if (isAutoReply(thread, messages)) {
      log(`⏩ SKIP: Auto-reply detected for ${leadEmail}`);
      state.processedLeads[leadId] = { skippedAutoReply: true, email: leadEmail };
      skippedCount++;
      continue;
    }

    // Filter 2: Flat rejection (without deferral)
    const replies = messages.filter(m => m.event_type === 'reply');
    const lastReply = replies[replies.length - 1];
    const replyText = lastReply ? htmlToText(lastReply.email_text) : '';

    if (isFlatRejection(replyText)) {
      log(`⏩ SKIP: Flat rejection without deferral for ${leadEmail}: "${stripQuotedEmail(replyText).slice(0, 60)}..."`);
      state.processedLeads[leadId] = { skippedFlatRejection: true, email: leadEmail, text: stripQuotedEmail(replyText).slice(0, 100) };
      skippedCount++;
      continue;
    }

    // Filter 3: Check if deal/contact already exists in OkoCRM (Strict Deduplication!)
    const { contact: existingContact, existingLead } = await findExistingContactAndDeal(leadEmail);
    if (existingLead) {
      log(`⏩ SKIP (DEDUP): Deal already exists in OkoCRM (Lead ID: ${existingLead.id}, "${existingLead.name}") for ${leadEmail}`);
      state.processedLeads[leadId] = {
        okoLeadId: existingLead.id,
        email: leadEmail,
        contactId: existingContact?.id,
        isExisting: true
      };
      skippedCount++;
      continue;
    }

    // Extract Info
    const info = extractLeadInfo(thread, threadDetail);
    const assignedManager = CONFIG.managers[state.nextManagerIndex % CONFIG.managers.length];

    log(`✅ QUALIFIED FOR CRM:
    - Email: ${leadEmail}
    - Name: ${info.name}
    - Company: ${info.company || '(none)'}
    - Phone: ${info.phone || '(none)'}
    - Assigned to: ${assignedManager.name} (${assignedManager.email})
    - Reply snippet: "${stripQuotedEmail(info.replyText).slice(0, 100).replace(/\n/g, ' ')}..."`);

    if (options.dryRun) {
      log(`[DRY-RUN] Would create Deal for ${leadEmail} assigned to ${assignedManager.name}`);
      state.nextManagerIndex = (state.nextManagerIndex + 1) % CONFIG.managers.length;
      createdCount++;
      continue;
    }

    // --- CREATE IN OKOCRM ---
    try {
      // 1. Create or use Contact
      let contactId = existingContact ? existingContact.id : null;
      if (!contactId) {
        log(`Creating contact in OkoCRM for ${info.name} (${leadEmail})...`);
        const newContact = await callOko('create_contact', {
          name: info.name,
          emails: [leadEmail],
          phones: info.phone ? [info.phone] : [],
          responsible_id: assignedManager.id
        });
        contactId = newContact?.contact?.id || newContact?.id;
        log(`Created contact ID: ${contactId}`);
      }

      // 2. Create Company (if name available)
      let companyId = null;
      if (info.company && info.company.length > 1) {
        try {
          const compSearch = await callOko('search_companies', { query: info.company });
          const existingComp = (compSearch?.items || []).find(c => c.name.toLowerCase() === info.company.toLowerCase());
          if (existingComp) {
            companyId = existingComp.id;
          } else {
            const newCompany = await callOko('create_company', {
              name: info.company,
              responsible_id: assignedManager.id
            });
            companyId = newCompany?.company?.id || newCompany?.id;
          }
          log(`Company ID: ${companyId} (${info.company})`);

          // Link Contact to Company
          if (contactId && companyId) {
            await callOko('update_contact', {
              contact_id: contactId,
              add_company_ids: [companyId]
            });
            log(`Linked contact ${contactId} to company ${companyId}`);
          }
        } catch (compErr) {
          log(`Notice: company handling: ${compErr.message}`);
        }
      }

      // 2b. Check for colleagues in copy / recipients
      const additional = extractAdditionalParticipants(threadDetail);
      const allContactIds = contactId ? [contactId] : [];

      for (const col of additional) {
        try {
          log(`Found colleague in copy/thread: ${col.name} (${col.email})`);
          const existingCol = await callOko('search_contacts', { query: col.email });
          let colContactId = (existingCol?.items || []).find(c => (c.emails || []).some(e => e.toLowerCase() === col.email.toLowerCase()))?.id;

          if (!colContactId) {
            const newCol = await callOko('create_contact', {
              name: col.name,
              emails: [col.email],
              responsible_id: assignedManager.id
            });
            colContactId = newCol?.contact?.id || newCol?.id;
            log(`Created colleague contact ID: ${colContactId}`);
          }

          if (colContactId) {
            allContactIds.push(colContactId);
            if (companyId) {
              await callOko('update_contact', {
                contact_id: colContactId,
                add_company_ids: [companyId]
              });
            }
          }
        } catch (colErr) {
          log(`Notice: colleague handling error: ${colErr.message}`);
        }
      }

      // 3. Create Deal
      const dealTitle = info.company 
        ? `${info.company} (${info.name}${info.phone ? ' ' + info.phone : ''})`
        : `${thread.subject || 'Ответ с рассылки'} / ${info.name}`;

      log(`Creating lead in OkoCRM: "${dealTitle}"...`);
      const newLead = await callOko('create_lead', {
        name: dealTitle,
        pipeline_id: CONFIG.okocrm.pipelineId,
        stage_id: meta.stageId,
        responsible_id: assignedManager.id,
        contact_ids: allContactIds,
        company_ids: companyId ? [companyId] : [],
        fields: {
          source_id: meta.emailSourceOptionId
        }
      });

      const leadRecordId = newLead?.lead?.id || newLead?.id;
      log(`🎉 Deal created successfully! OkoCRM Lead ID: ${leadRecordId}`);

      // Ensure All Contacts and Company are explicitly linked to Deal
      if (leadRecordId) {
        if (allContactIds.length > 0 || companyId) {
          await callOko('link_lead', {
            lead_id: leadRecordId,
            action: 'attach',
            contact_ids: allContactIds,
            company_ids: companyId ? [companyId] : []
          });
        }
      }

      // 4. Attach Note
      if (leadRecordId) {
        const noteText = formatNote(threadDetail, info);
        await callOko('add_note', {
          entity_type: 'lead',
          entity_id: leadRecordId,
          text: noteText
        });
        log(`Attached correspondence note to lead ${leadRecordId}`);
      }

      // Record in State
      state.processedLeads[leadId] = {
        okoLeadId: leadRecordId,
        email: leadEmail,
        contactId: contactId,
        companyId: companyId,
        responsibleId: assignedManager.id,
        triggaStatus: thread.user_status,
        createdAt: new Date().toISOString()
      };

      // Advance manager round-robin pointer
      state.nextManagerIndex = (state.nextManagerIndex + 1) % CONFIG.managers.length;
      createdCount++;

    } catch (createErr) {
      log(`❌ FAILED to create deal in OkoCRM for ${leadEmail}: ${createErr.message}`, true);
    }
  }

  // --- TWO-WAY SYNC: Check OkoCRM deals and update Trigga ---
  log('\n=== Checking Two-Way Sync (OkoCRM -> Trigga) ===');
  for (const [leadIdStr, item] of Object.entries(state.processedLeads)) {
    if (!item.okoLeadId || item.isExisting || item.status === 'closed_blacklisted') continue;

    try {
      const okoLead = await callOko('get_lead', { lead_id: item.okoLeadId });
      const leadObj = okoLead?.lead || okoLead;
      if (!leadObj) continue;

      // Check if deal is closed
      if (leadObj.stage?.kind === 'lost') {
        const reasonId = leadObj.loss_reason_id || leadObj.stage?.loss_reason_id;
        if (reasonId === meta.lossReasonId) {
          log(`🛑 Deal ${item.okoLeadId} was CLOSED with "Trigga черный список"! Adding lead ${leadIdStr} to Trigga Blacklist...`);
          
          if (!options.dryRun) {
            // Add to Trigga blacklist
            await callTrigga('/blacklist/leads/', 'POST', { lead_ids: [parseInt(leadIdStr, 10)] });
            // Set Trigga status to not_interested
            await callTrigga(`/inbox/threads/${leadIdStr}/`, 'PATCH', { user_status: 'not_interested' });
            item.status = 'closed_blacklisted';
            item.triggaStatus = 'not_interested';
            log(`Added lead ${leadIdStr} to Trigga blacklist.`);
          }
        }
      } 
      // Check if moved to "Первичный контакт" or further
      else if (leadObj.stage && leadObj.stage.sort >= meta.primaryContactSort && item.triggaStatus !== 'interested') {
        log(`🎯 Deal ${item.okoLeadId} advanced to "${leadObj.stage.name}" (sort: ${leadObj.stage.sort})! Updating Trigga status to "interested"...`);
        
        if (!options.dryRun) {
          await callTrigga(`/inbox/threads/${leadIdStr}/`, 'PATCH', { user_status: 'interested' });
          item.triggaStatus = 'interested';
          log(`Updated lead ${leadIdStr} status in Trigga to "interested".`);
        }
      }
    } catch (syncErr) {
      log(`Error during 2-way sync for Oko lead ${item.okoLeadId}: ${syncErr.message}`, true);
    }
  }

  if (!options.dryRun) {
    saveState(state);
  }
  log(`=== Sync completed: ${createdCount} deals processed, ${skippedCount} skipped ===\n`);
  return { createdCount, skippedCount };
}

// CLI execution
if (require.main === module) {
  const isDryRun = process.argv.includes('--dry-run');
  const isDaemon = process.argv.includes('--daemon') || process.argv.includes('--watch');

  if (isDaemon) {
    log(`Starting Trigga <-> OkoCRM sync daemon (interval: ${CONFIG.syncIntervalMinutes} minutes)...`);
    runSync({ dryRun: false }).catch(e => log(`Sync error: ${e.message}`, true));
    setInterval(() => {
      runSync({ dryRun: false }).catch(e => log(`Sync error: ${e.message}`, true));
    }, CONFIG.syncIntervalMinutes * 60 * 1000);
  } else {
    runSync({ dryRun: isDryRun }).catch(err => {
      log(`Fatal sync error: ${err.stack || err.message}`, true);
      process.exit(1);
    });
  }
}

module.exports = { runSync, loadState, saveState, callTrigga, callOko, extractLeadInfo, formatNote };
