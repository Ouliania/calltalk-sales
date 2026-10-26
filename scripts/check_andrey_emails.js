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
  const allActive = await getAllLeads({ pipeline_id: 30895, status: 'active' });
  const andreyLeads = allActive.filter(l => l.responsible?.id === 28418);
  console.log(`Проверяем переписки у ${andreyLeads.length} сделок Андрея...`);

  for (const l of andreyLeads) {
    const tl = await callTool('get_timeline', { entity_type: 'lead', entity_id: l.id });
    const items = tl.items || [];
    const emails = items.filter(it => it.kind === 'email');
    const tasks = items.filter(it => it.kind === 'task');
    
    if (emails.length >= 2 || tasks.some(t => t.task?.text?.toLowerCase().includes('письм') || t.text?.toLowerCase().includes('письм'))) {
      console.log(`\n======================================================`);
      console.log(`Сделка ID ${l.id}: "${l.name}" | Этап: "${l.stage?.name}"`);
      console.log(`Количество писем в таймлайне: ${emails.length}`);
      
      emails.forEach(em => {
        console.log(`  - [EMAIL ${em.email?.direction}] ${em.created_at?.slice(0, 16)} | Тема: "${em.email?.subject}" | From: ${em.email?.from} -> To: ${em.email?.to}`);
        console.log(`    Превью: "${(em.email?.preview || '').replace(/\n/g, ' ').slice(0, 150)}"`);
      });

      // Show recent tasks / notes related to email
      tasks.slice(0, 3).forEach(ts => {
        const txt = (ts.text || ts.task?.text || '').replace(/\n/g, ' ');
        if (txt) console.log(`  - [TASK] ${ts.created_at?.slice(0, 16)} | ${txt.slice(0, 140)}`);
      });
    }
  }
}
run();
