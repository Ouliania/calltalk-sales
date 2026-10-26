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
  console.log('=== ЗАГРУЗКА ВСЕХ СДЕЛОК ДЛЯ АНАЛИТИКИ КАНАЛОВ И ВОРОНКИ ===');
  const activeB2B = await getAllLeads({ pipeline_id: 30895, status: 'active' });
  const wonB2B = await getAllLeads({ pipeline_id: 30895, status: 'won' });
  const lostB2B = await getAllLeads({ pipeline_id: 30895, status: 'lost' });
  const allB2B = [...activeB2B, ...wonB2B, ...lostB2B];

  console.log(`Всего сделок в B2B: ${allB2B.length} (активных: ${activeB2B.length}, выиграно: ${wonB2B.length}, проиграно: ${lostB2B.length})`);

  // Let's identify sources
  // Look for site leads: url, form, domain in name, or specific names
  // Also check custom fields or tags if any
  const siteLeads = [];
  const triggaLeads = [];
  const partnerLeads = [];
  const emailLeads = [];

  for (const l of allB2B) {
    const name = l.name || '';
    const nameLower = name.toLowerCase();
    
    if (nameLower.includes('intarial') || nameLower.includes('заявка с сайта') || nameLower.includes('входящая заявка') || /^https?:\/\//i.test(name) || /^[a-z0-9-]+\.(ru|pro|com|net|io|tech|su)$/i.test(name.trim())) {
      siteLeads.push(l);
    } else if (nameLower.includes('trigga') || l.stage?.name?.toLowerCase().includes('trigga')) {
      triggaLeads.push(l);
    } else if (nameLower.includes('перестройка') || nameLower.includes('партнер')) {
      partnerLeads.push(l);
    } else {
      emailLeads.push(l);
    }
  }

  console.log(`\nРаспределение по каналам:`);
  console.log(`  - Сайт / Входящие с сайта: ${siteLeads.length}`);
  console.log(`  - Trigga: ${triggaLeads.length}`);
  console.log(`  - Партнерка: ${partnerLeads.length}`);
  console.log(`  - Email-аутрич: ${emailLeads.length}`);

  console.log('\n--- ДЕТАЛИЗАЦИЯ ЛИДОВ С САЙТА ---');
  for (const sl of siteLeads) {
    console.log(`\n[ID ${sl.id}] "${sl.name}" | Этап: "${sl.stage?.name}" | Статус: ${sl.status} | Ответственный: ${sl.responsible?.name}`);
    try {
      const tl = await callTool('get_timeline', { entity_type: 'lead', entity_id: sl.id });
      const events = Array.isArray(tl) ? tl : (tl.items || tl.events || []);
      events.slice(0, 5).forEach(ev => {
        console.log(`   * [${ev.kind}] ${ev.created_at?.slice(0, 16)}: ${ev.text || ev.task?.text || ev.title || ''}`);
      });
    } catch(e) {}
  }

  // Also search contacts and companies to see if any site leads were registered differently
  console.log('\n--- ПОИСК ДРУГИХ ВОЗМОЖНЫХ ЗАЯВОК С САЙТА ПО ТЕГАМ / ПОЛЯМ / ПОИСКУ ---');
  const searchSite = await callTool('search_leads', { q: 'сайт' });
  (searchSite.items || []).forEach(l => console.log(`  Найдено по "сайт": [ID ${l.id}] ${l.name} (${l.stage?.name})`));

  // Let's analyze LOST reasons in B2B
  console.log('\n--- АНАЛИЗ ПРИЧИН ОТКАЗОВ (LOST LEADS) ---');
  for (const ll of lostB2B) {
    console.log(`\n[ID ${ll.id}] "${ll.name}" | Причина отказа: ${ll.loss_reason?.name || 'не указана'}`);
    try {
      const tl = await callTool('get_timeline', { entity_type: 'lead', entity_id: ll.id });
      const events = Array.isArray(tl) ? tl : (tl.items || tl.events || []);
      events.filter(e => e.kind === 'note' || e.kind === 'system' || e.kind === 'task').slice(0, 5).forEach(ev => {
        console.log(`   * [${ev.kind}] ${ev.text || ev.task?.text || ''}`);
      });
    } catch(e) {}
  }
}

main();
