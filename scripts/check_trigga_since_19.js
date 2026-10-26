const endpoint = 'https://mcp.okocrm.com/crm';
const token = 'OKOCRM_TOKEN_PLACEHOLDER';

async function callTool(name, args) {
  const res = await fetch(endpoint, {
    method: 'POST',
    headers: { 'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json' },
    body: JSON.stringify({ jsonrpc: '2.0', id: Date.now(), method: 'tools/call', params: { name, arguments: args } })
  });
  const data = await res.json();
  const text = data.result?.content?.[0]?.text;
  try { return JSON.parse(text); } catch(e) { return text; }
}

async function getAllLeads(params) {
  let leads = [];
  let cursor = null;
  while (true) {
    const p = { ...params, limit: 100 };
    if (cursor) p.cursor = cursor;
    const res = await callTool('search_leads', p);
    const items = res.items || [];
    leads = leads.concat(items);
    cursor = res.next_cursor;
    if (!cursor || items.length === 0) break;
  }
  return leads;
}

async function main() {
  console.log('=== АНАЛИЗ СДЕЛОК ИЗ TRIGGA С 19 ОКТЯБРЯ 2026 ===\n');

  // Fetch all leads created from 2026-10-19
  const b2bActive = await getAllLeads({ pipeline_id: 30895, status: 'active' });
  const b2bWon = await getAllLeads({ pipeline_id: 30895, status: 'won' });
  const b2bLost = await getAllLeads({ pipeline_id: 30895, status: 'lost' });
  const poolActive = await getAllLeads({ pipeline_id: 30944, status: 'active' });
  const poolLost = await getAllLeads({ pipeline_id: 30944, status: 'lost' });

  const allLeads = [...b2bActive, ...b2bWon, ...b2bLost, ...poolActive, ...poolLost];

  // Filter leads created since 2026-10-19
  const since19 = allLeads.filter(l => l.created_at && l.created_at >= '2026-10-19T00:00:00');
  console.log(`Всего сделок создано с 19 октября: ${since19.length}`);

  const triggaLeads = [];

  for (const l of since19) {
    let isTrigga = false;
    let triggaNote = null;
    let events = [];

    // Check stage or name first
    const stageName = (l.stage?.name || '').toLowerCase();
    const nameLower = (l.name || '').toLowerCase();
    if (stageName.includes('trigga') || nameLower.includes('trigga')) {
      isTrigga = true;
    }

    // Check timeline
    try {
      const tl = await callTool('get_timeline', { entity_type: 'lead', entity_id: l.id });
      events = Array.isArray(tl) ? tl : (tl.items || tl.events || []);
      for (const ev of events) {
        const txt = ((ev.text || '') + ' ' + (ev.title || '')).toLowerCase();
        if (txt.includes('trigga') || txt.includes('входящий ответ из trigga') || txt.includes('кампания: для call-talk')) {
          isTrigga = true;
          triggaNote = ev.text || ev.title;
        }
      }
    } catch(e) {}

    if (isTrigga) {
      triggaLeads.push({ lead: l, events, triggaNote });
    }
  }

  console.log(`Из них лидов из Trigga: ${triggaLeads.length}\n`);

  // Group by manager
  const managers = [
    { id: 28418, name: 'Андрей' },
    { id: 28419, name: 'Лёня' },
    { id: 28415, name: 'Ульяна' }
  ];

  for (const m of managers) {
    console.log(`======================================================`);
    console.log(`👤 МЕНЕДЖЕР: ${m.name}`);
    console.log(`======================================================`);

    const mTrigga = triggaLeads.filter(t => t.lead.responsible?.id === m.id);
    console.log(`Всего лидов из Trigga с 19 октября: ${mTrigga.length}`);

    let inDialogue = [];
    let closed = [];
    let waiting = []; // untouched or on "Лид с Trigga"

    for (const item of mTrigga) {
      const l = item.lead;
      const s = (l.stage?.name || '').toLowerCase();
      const status = l.status;

      // Check if closed
      const isClosed = status === 'lost' || s.includes('закрыто') || s.includes('отказ') || s.includes('архив');
      
      // Check if in dialogue:
      // Moved to "Первичный контакт", "MQL", "Встреча", "КП" OR has outgoing email/task/note indicating communication
      let hasCommunication = false;
      if (s.includes('первичный контакт') || s.includes('квалификац') || s.includes('встреч') || s.includes('кп') || s.includes('договор')) {
        hasCommunication = true;
      }
      for (const ev of item.events) {
        if (ev.kind === 'email' && ev.email?.direction === 'out') hasCommunication = true;
        if (ev.kind === 'note' && (ev.text?.toLowerCase().includes('написал') || ev.text?.toLowerCase().includes('позвонил') || ev.text?.toLowerCase().includes('диалог'))) {
          hasCommunication = true;
        }
      }

      if (isClosed) {
        closed.push({ lead: l, hadDialogue: hasCommunication, reason: l.loss_reason?.name });
      } else if (hasCommunication) {
        inDialogue.push({ lead: l, stage: l.stage?.name });
      } else {
        waiting.push({ lead: l, stage: l.stage?.name });
      }
    }

    console.log(`\n📊 ИТОГО:`);
    console.log(`  1. Всего новых сделок Trigga: ${mTrigga.length}`);
    console.log(`  2. В диалоге (активные в работе): ${inDialogue.length}`);
    inDialogue.forEach(it => {
      console.log(`      * [ID ${it.lead.id}] "${it.lead.name}" | Этап: "${it.stage}"`);
    });

    console.log(`  3. Закрыты (в отказ/архив): ${closed.length}`);
    closed.forEach(it => {
      console.log(`      * [ID ${it.lead.id}] "${it.lead.name}" | Причина: ${it.reason || 'не указана'} | Был ли диалог: ${it.hadDialogue ? 'Да' : 'Нет'}`);
    });

    if (waiting.length > 0) {
      console.log(`  4. Ожидают первого касания / не разобраны: ${waiting.length}`);
      waiting.forEach(it => {
        console.log(`      * [ID ${it.lead.id}] "${it.lead.name}" | Этап: "${it.stage}"`);
      });
    }
    console.log('\n');
  }

  // Also print all trigga leads with details to be 100% sure we didn't miss anything
  console.log('--- ВСЕ СДЕЛКИ TRIGGA С 19 ОКТЯБРЯ ДЛЯ СВЕРКИ ---');
  triggaLeads.forEach(t => {
    console.log(`[ID ${t.lead.id}] "${t.lead.name}" | Ответственный: ${t.lead.responsible?.name} | Создан: ${t.lead.created_at?.slice(0, 16)} | Этап: ${t.lead.stage?.name} | Статус: ${t.lead.status}`);
  });
}

main();
