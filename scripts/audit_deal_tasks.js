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
  const now = new Date('2026-10-21T11:05:00+07:00');
  console.log(`Текущее время среза: ${now.toLocaleString('ru-RU')}`);

  // Fetch all active B2B leads
  const activeLeads = await getAllLeads({ pipeline_id: 30895, status: 'active' });
  console.log(`Всего активных сделок в B2B: ${activeLeads.length}`);

  // Fetch all open tasks for managers
  const openTasks = await getAllTasks({ executor_ids: [28418, 28419], status: 'open' });
  console.log(`Всего открытых задач у менеджеров: ${openTasks.length}`);

  const managers = [
    { id: 28418, name: 'Андрей' },
    { id: 28419, name: 'Лёня' }
  ];

  for (const m of managers) {
    console.log(`\n======================================================`);
    console.log(`👤 МЕНЕДЖЕР: ${m.name}`);
    console.log(`======================================================`);

    const mLeads = activeLeads.filter(l => l.responsible?.id === m.id);
    const mTasks = openTasks.filter(t => t.executor?.id === m.id);

    console.log(`Активных сделок в B2B: ${mLeads.length}`);
    console.log(`Открытых задач в CRM: ${mTasks.length}`);

    // 1. Check leads WITHOUT tasks
    // A lead is considered without task if closest_task_at is null OR there is no open task for this lead
    const leadsNoTask = [];
    for (const l of mLeads) {
      const hasTask = mTasks.some(t => (t.entity?.id === l.id && t.entity?.type === 'lead') || t.lead_id === l.id);
      if (!hasTask && !l.closest_task_at) {
        leadsNoTask.push(l);
      }
    }

    console.log(`\n🚨 Сделок БЕЗ запланированных задач: ${leadsNoTask.length}`);
    if (leadsNoTask.length === 0) {
      console.log(`  🟢 Все сделки закрыты задачами на 100%!`);
    } else {
      leadsNoTask.forEach(l => {
        console.log(`  - [ID ${l.id}] "${l.name}" | Этап: "${l.stage?.name}" | closest_task_at: ${l.closest_task_at}`);
      });
    }

    // 2. Check OVERDUE tasks
    // Compare date_finish with now
    const overdueTasks = [];
    const dueToday = [];
    const futureTasks = [];

    for (const t of mTasks) {
      if (!t.date_finish) continue;
      const dFinish = new Date(t.date_finish);
      if (dFinish < now) {
        overdueTasks.push(t);
      } else if (t.date_finish.startsWith('2026-10-21')) {
        dueToday.push(t);
      } else {
        futureTasks.push(t);
      }
    }

    console.log(`\n⏰ Просроченных задач: ${overdueTasks.length}`);
    if (overdueTasks.length === 0) {
      console.log(`  🟢 Просроченных задач нет! Все дедлайны соблюдены.`);
    } else {
      overdueTasks.forEach(t => {
        console.log(`  ⚠️ [Дедлайн был: ${t.date_finish}] "${t.text || t.title}" | Сделка ID: ${t.entity?.id || t.lead_id} ("${t.entity?.name}")`);
      });
    }

    console.log(`\n📅 Задач со сроком СЕГОДНЯ (21 октября): ${dueToday.length}`);
    dueToday.forEach(t => {
      console.log(`  - [Время: ${t.date_finish?.split('T')[1]?.slice(0, 5)}] "${t.text || t.title}" | Сделка: "${t.entity?.name}"`);
    });

    console.log(`\n🔮 Задач на будущие даты: ${futureTasks.length}`);
  }
}

main();
