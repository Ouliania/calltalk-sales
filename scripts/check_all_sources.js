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

async function run() {
  const activeB2B = await getAllLeads({ pipeline_id: 30895, status: 'active' });
  const wonB2B = await getAllLeads({ pipeline_id: 30895, status: 'won' });
  const lostB2B = await getAllLeads({ pipeline_id: 30895, status: 'lost' });
  const poolLeads = await getAllLeads({ pipeline_id: 30944, status: 'active' });
  const poolLost = await getAllLeads({ pipeline_id: 30944, status: 'lost' });

  const all = [...activeB2B, ...wonB2B, ...lostB2B, ...poolLeads, ...poolLost];
  console.log(`Всего сделок во всей CRM: ${all.length}`);

  // Date ranges
  const dates = all.map(l => l.created_at).filter(Boolean).sort();
  console.log(`Самый ранний лид в CRM: ${dates[0]}`);
  console.log(`Самый поздний лид в CRM: ${dates[dates.length - 1]}`);

  // Check source_id or fields on leads
  // Fetch detailed fields for a sample of leads or leads with site
  const bySource = {};
  const siteLeadsList = [];

  for (const l of all) {
    // Check if l has source or source_id or fields
    const src = l.source?.name || l.source_id || 'Не указан';
    bySource[src] = (bySource[src] || 0) + 1;
    
    // Check if name or anything indicates website
    const name = (l.name || '').toLowerCase();
    if (src === 'Сайт' || name.includes('сайт') || name.includes('входящ') || name.includes('tilda') || name.includes('form') || l.utm_source) {
      siteLeadsList.push(l);
    }
  }

  console.log('\nРаспределение по полю source / source_id:');
  console.log(bySource);

  console.log(`\nВсего потенциальных сделок с сайта / форм / UTM: ${siteLeadsList.length}`);
  siteLeadsList.forEach(l => {
    console.log(`  - [ID ${l.id}] "${l.name}" | Источник: ${l.source?.name || l.source_id} | Создан: ${l.created_at} | Этап: ${l.stage?.name}`);
  });

  // Let's also check lead details for some recent leads to see how source is returned by get_lead
  if (siteLeadsList.length > 0) {
    const sample = await callTool('get_lead', { lead_id: siteLeadsList[0].id });
    console.log('\nSample lead fields:');
    console.log('Source:', sample.source);
    console.log('Fields:', sample.fields);
  }
}
run();
