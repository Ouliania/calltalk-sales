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

async function run() {
  const pipesRes = await callTool('list_pipelines', {});
  const b2bPipe = pipesRes.pipelines.find(p => p.id === 30895);
  const stages = Object.fromEntries(b2bPipe.stages.map(s => [s.id, s.name]));

  let leads = [];
  let cursor = null;
  while (true) {
    const res = await callTool('search_leads', { pipeline_id: 30895, limit: 100, cursor });
    leads = leads.concat(res.items || []);
    cursor = res.next_cursor;
    if (!cursor || !res.items.length) break;
  }

  // Also check won or lost leads
  const closedLeads = await callTool('search_leads', { pipeline_id: 30895, status: 'all', limit: 100 });
  const allLeads = (closedLeads.items || []).concat(leads.filter(l => !closedLeads.items?.some(c => c.id === l.id)));

  console.log(`Found ${allLeads.length} total leads in B2B.`);

  const movements15 = [];

  for (const l of allLeads) {
    try {
      const tl = await callTool('get_timeline', { entity_type: 'lead', entity_id: l.id });
      const events = Array.isArray(tl) ? tl : (tl.items || tl.events || []);
      for (const ev of events) {
        const d = ev.created_at || ev.date || '';
        if (d.includes('2026-10-15')) {
          movements15.push({
            leadId: l.id,
            leadName: l.name,
            responsible: l.responsible?.name,
            currentStage: l.stage?.name,
            date: d,
            kind: ev.kind,
            action: ev.action,
            text: ev.text,
            task: ev.task,
            email: ev.email
          });
        }
      }
    } catch(e) {}
  }

  console.log(`\nTotal timeline events on 2026-10-15: ${movements15.length}`);

  // Let's filter by interesting kinds: system stage changes, tasks (especially meetings), emails
  const stageChanges = movements15.filter(m => m.kind === 'system' && (m.text?.toLowerCase().includes('этап') || m.text?.toLowerCase().includes('статус')));
  const meetingEvents = movements15.filter(m => {
    const txt = ((m.task?.title || m.task?.name || m.task?.text || '') + ' ' + (m.text || '')).toLowerCase();
    return txt.includes('встреч') || txt.includes('созвон') || txt.includes('зум') || txt.includes('телемост');
  });
  const emailEvents = movements15.filter(m => m.kind === 'email');

  console.log('\n--- 1. ПЕРЕХОДЫ ПО ЭТАПАМ (Stage Changes) ---');
  if (stageChanges.length === 0) console.log('Нет зафиксированных смен этапов через timeline.');
  stageChanges.forEach(sc => console.log(`[${sc.responsible}] Сделка "${sc.leadName}" (ID ${sc.leadId}): ${sc.text} (в ${sc.date})`));

  console.log('\n--- 2. ВСТРЕЧИ / СОЗВОНЫ (Meetings) ---');
  if (meetingEvents.length === 0) console.log('Нет задач на встречи/созвоны за 15 октября.');
  meetingEvents.forEach(me => console.log(`[${me.responsible}] Сделка "${me.leadName}" (ID ${me.leadId}): ${me.task?.text || me.text} | Done: ${me.task?.done}`));

  console.log('\n--- 3. ВСЕ СОБЫТИЯ ЗА 15 ОКТЯБРЯ ---');
  movements15.forEach(m => {
    console.log(`[${m.responsible}] [${m.kind}] [${m.leadName}]: ${m.text || m.task?.text || m.email?.subject || ''}`);
  });
}
run();
