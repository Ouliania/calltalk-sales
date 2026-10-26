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
  const stages = Object.fromEntries(b2bPipe.stages.map(s => [s.id, s.name]));

  console.log('=== ЭТАПЫ ВОРОНКИ B2B ===');
  b2bPipe.stages.forEach(s => console.log(`  ${s.id}: ${s.name}`));

  // 1. Specifically check Unicraft, Правильные ИТ, Пронто Кью
  console.log('\n======================================================');
  console.log('🔍 ПРОВЕРКА 3 КОНКРЕТНЫХ СДЕЛОК АНДРЕЯ:');
  console.log('======================================================');
  
  const targetNames = ['unicraft', 'правильные ит', 'пронто'];
  const allActiveLeads = await getAllLeads({ pipeline_id: 30895, status: 'active' });
  
  for (const t of targetNames) {
    const found = allActiveLeads.filter(l => l.name?.toLowerCase().includes(t));
    if (found.length) {
      for (const f of found) {
        console.log(`\nСделка: "${f.name}" (ID ${f.id})`);
        console.log(`  - Ответственный: ${f.responsible?.name} (${f.responsible?.email})`);
        console.log(`  - ТЕКУЩИЙ ЭТАП: "${f.stage?.name || stages[f.stage_id]}" (ID: ${f.stage_id || f.stage?.id})`);
        console.log(`  - Обновлено: ${f.updated_at}`);
        
        // Fetch timeline to see when it moved or what happened yesterday/today
        try {
          const tl = await callTool('get_timeline', { entity_type: 'lead', entity_id: f.id });
          const events = Array.isArray(tl) ? tl : (tl.items || tl.events || []);
          console.log(`  - Последние события таймлайна:`);
          events.slice(0, 5).forEach(ev => {
            console.log(`      * [${ev.kind || ev.type}] ${ev.created_at || ev.date}: ${ev.text || ev.task?.text || ev.email?.subject || JSON.stringify(ev)}`);
          });
        } catch(e) {}
      }
    } else {
      console.log(`\nСделка "${t}" не найдена в активных! Проверяем won/lost...`);
      const lost = await callTool('search_leads', { pipeline_id: 30895, status: 'lost', q: t });
      console.log(`  Lost results:`, lost.items?.map(l => ({ id: l.id, name: l.name, stage: l.stage?.name })));
    }
  }

  // 2. Check Andrey's task "Навести порядок в CRM..."
  console.log('\n======================================================');
  console.log('🔍 ПРОВЕРКА ЗАДАЧИ АНДРЕЯ ПО НАВЕДЕНИЮ ПОРЯДКА:');
  console.log('======================================================');
  const allTasks = await getAllTasks({ status: 'all' });
  const andreyTasks = allTasks.filter(t => t.executor?.id === 28418 || t.owner?.id === 28418);
  const crmCleanTasks = andreyTasks.filter(t => {
    const txt = ((t.text || '') + ' ' + (t.title || '') + ' ' + (t.name || '')).toLowerCase();
    return txt.includes('порядок') || txt.includes('unicraft') || txt.includes('правильные ит') || txt.includes('пронто') || txt.includes('кп отправлено');
  });
  console.log(`Найдено подходящих задач: ${crmCleanTasks.length}`);
  crmCleanTasks.forEach(t => {
    console.log(`  - [ID ${t.id}] "${t.text || t.title || t.name}"`);
    console.log(`    Done: ${t.done} | Closed at: ${t.closed_at} | Finish date: ${t.date_finish} | Created: ${t.created_at}`);
  });

  // 3. Yesterday (2026-10-20) and Today (2026-10-21) tasks per manager
  console.log('\n======================================================');
  console.log('📊 ЗАКРЫТЫЕ И СОЗДАННЫЕ ЗАДАЧИ (20 и 21 ОКТЯБРЯ):');
  console.log('======================================================');
  const managers = [
    { id: 28418, name: 'Андрей' },
    { id: 28419, name: 'Лёня' }
  ];

  for (const m of managers) {
    const mTasks = allTasks.filter(t => t.executor?.id === m.id);
    const closedYesterday = mTasks.filter(t => t.done && t.closed_at && t.closed_at.startsWith('2026-10-20'));
    const closedToday = mTasks.filter(t => t.done && t.closed_at && t.closed_at.startsWith('2026-10-21'));
    const openTasks = mTasks.filter(t => !t.done);
    const now = new Date('2026-10-21T11:00:00+07:00');
    const overdue = openTasks.filter(t => t.date_finish && new Date(t.date_finish) < now);

    console.log(`\n👤 ${m.name}:`);
    console.log(`  - Закрыто вчера (20 окт): ${closedYesterday.length}`);
    closedYesterday.slice(0, 10).forEach(t => console.log(`      * [${t.closed_at?.split('T')[1]?.slice(0, 5)}] ${t.text || t.title} (сделка ${t.lead_id})`));
    console.log(`  - Закрыто сегодня утром (21 окт): ${closedToday.length}`);
    closedToday.forEach(t => console.log(`      * [${t.closed_at?.split('T')[1]?.slice(0, 5)}] ${t.text || t.title} (сделка ${t.lead_id})`));
    console.log(`  - Открытых задач: ${openTasks.length} (из них просрочено: ${overdue.length})`);
    if (overdue.length) {
      console.log(`    ⚠️ Просроченные задачи:`);
      overdue.forEach(t => console.log(`      * [Дедлайн ${t.date_finish}] ${t.text || t.title} (сделка ${t.lead_id})`));
    }
  }

  // 4. Current distribution of active leads across stages for both managers
  console.log('\n======================================================');
  console.log('📌 РАСПРЕДЕЛЕНИЕ СДЕЛОК ПО ЭТАПАМ НА ТЕКУЩИЙ МОМЕНТ:');
  console.log('======================================================');
  for (const m of managers) {
    const mLeads = allActiveLeads.filter(l => l.responsible?.id === m.id);
    console.log(`\n👤 ${m.name} (Всего активных сделок: ${mLeads.length})`);
    
    // Group by stage
    const stageMap = {};
    b2bPipe.stages.forEach(s => stageMap[s.name] = []);
    mLeads.forEach(l => {
      const sName = l.stage?.name || stages[l.stage_id] || 'Неизвестно';
      if (!stageMap[sName]) stageMap[sName] = [];
      stageMap[sName].push(l);
    });

    for (const [st, arr] of Object.entries(stageMap)) {
      if (arr.length > 0) {
        console.log(`  [${st}]: ${arr.length}`);
        arr.forEach(l => console.log(`     - [ID ${l.id}] ${l.name}`));
      }
    }
  }
}

main();
