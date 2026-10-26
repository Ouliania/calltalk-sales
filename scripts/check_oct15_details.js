const endpoint = 'https://mcp.okocrm.com/crm';
const token = 'OKOCRM_TOKEN_PLACEHOLDER';

async function callTool(name, args) {
  const res = await fetch(endpoint, {
    method: 'POST',
    headers: { 'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json' },
    body: JSON.stringify({ jsonrpc: '2.0', id: Date.now(), method: 'tools/call', params: { name, arguments: args } })
  });
  const data = await res.json();
  const text = data.result.content[0].text;
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

async function getAllTasks(params) {
  let tasks = [];
  let cursor = null;
  while (true) {
    const p = { ...params, limit: 50 };
    if (cursor) p.cursor = cursor;
    const res = await callTool('list_tasks', p);
    const items = res.items || [];
    tasks = tasks.concat(items);
    cursor = res.next_cursor;
    if (!cursor || items.length === 0) break;
  }
  return tasks;
}

async function main() {
  const pipesRes = await callTool('list_pipelines', {});
  const b2bPipe = pipesRes.pipelines.find(p => p.id === 30895);
  console.log('=== B2B STAGES ===');
  b2bPipe.stages.forEach(s => console.log(s.id, s.name, '(sort: ' + s.sort + ')'));

  const b2bLeads = await getAllLeads({ pipeline_id: 30895, status: 'active' });
  console.log('\nTotal active B2B leads:', b2bLeads.length);

  const managers = [
    { id: 28418, name: 'Андрей' },
    { id: 28419, name: 'Лёня' },
    { id: 28415, name: 'Ульяна' }
  ];

  // Stage categories:
  // Before KP: 148040 (Новый лид), 148041 (Первичный контакт), 148042 (Первичная квалификация), 149436 (Встреча назначена), 148043 (Встреча проведена)
  // At KP: 148044 (КП отправлено)
  // After KP: 148045 (Договор на подписи), 148046 (Счёт направлен)
  const beforeKpStageIds = [148040, 148041, 148042, 149436, 148043];
  const kpStageId = 148044;
  const afterKpStageIds = [148045, 148046];

  for (const m of managers) {
    const mLeads = b2bLeads.filter(l => l.responsible && l.responsible.id === m.id);
    console.log('\n========================================');
    console.log(`МЕНЕДЖЕР: ${m.name} (Всего активных сделок в B2B: ${mLeads.length})`);
    
    const beforeKp = mLeads.filter(l => beforeKpStageIds.includes(l.stage?.id));
    const atKp = mLeads.filter(l => l.stage?.id === kpStageId);
    const afterKp = mLeads.filter(l => afterKpStageIds.includes(l.stage?.id));
    const other = mLeads.filter(l => !beforeKpStageIds.includes(l.stage?.id) && l.stage?.id !== kpStageId && !afterKpStageIds.includes(l.stage?.id));

    console.log(`📌 ДО стадии «КП отправлено»: ${beforeKp.length}`);
    beforeKp.forEach(l => console.log(`   - [${l.stage?.name}] ${l.name} (ID: ${l.id})`));

    console.log(`📌 НА стадии «КП отправлено»: ${atKp.length}`);
    atKp.forEach(l => console.log(`   - [${l.stage?.name}] ${l.name} (ID: ${l.id})`));

    console.log(`📌 ПОСЛЕ стадии «КП отправлено» (Договор/Счёт): ${afterKp.length}`);
    afterKp.forEach(l => console.log(`   - [${l.stage?.name}] ${l.name} (ID: ${l.id})`));

    if (other.length) {
      console.log(`📌 Другие стадии: ${other.length}`);
      other.forEach(l => console.log(`   - [${l.stage?.name}] ${l.name} (ID: ${l.id})`));
    }
  }

  // Check timeline / changes on 2026-10-15
  console.log('\n========================================');
  console.log('=== АКТИВНОСТИ И ПЕРЕДВИЖЕНИЯ ЗА 15 ОКТЯБРЯ ===');
  
  // Inspect timelines of recently updated leads
  // Filter leads with updated_at starting with 2026-10-15 or 2026-10-16
  const updatedLeads = b2bLeads.filter(l => l.updated_at && l.updated_at.startsWith('2026-10-15'));
  console.log(`Leads with updated_at on 2026-10-15: ${updatedLeads.length}`);
  
  // Also check all tasks for Oct 15
  const allTasks = await getAllTasks({ status: 'all' });
  const tasks15Closed = allTasks.filter(t => t.closed_at && t.closed_at.startsWith('2026-10-15'));
  const tasks15Created = allTasks.filter(t => t.created_at && t.created_at.startsWith('2026-10-15'));
  console.log(`Tasks closed on 2026-10-15: ${tasks15Closed.length}`);
  console.log(`Tasks created on 2026-10-15: ${tasks15Created.length}`);

  // Let's print closed tasks to see what happened (meetings, KPs, calls)
  console.log('\n--- Closed Tasks on 2026-10-15 ---');
  tasks15Closed.forEach(t => {
    console.log(`[${t.executor?.name}] Task: "${t.title || t.name}" | Lead ID: ${t.lead_id} | Type: ${t.type?.name || 'task'}`);
  });

  // Let's check timelines for leads updated on 15th
  for (const l of updatedLeads.slice(0, 15)) {
    try {
      const tl = await callTool('get_timeline', { lead_id: l.id });
      // filter timeline items for 2026-10-15
      const items15 = (tl.items || tl || []).filter(item => {
        const d = item.created_at || item.date || '';
        return d.startsWith('2026-10-15');
      });
      if (items15.length) {
        console.log(`\nTimeline for Lead ${l.id} (${l.name}):`);
        items15.forEach(it => {
          console.log(`  - [${it.type || it.action}] ${it.text || it.title || it.comment || JSON.stringify(it)}`);
        });
      }
    } catch(e) {
      // ignore
    }
  }
}

main();
