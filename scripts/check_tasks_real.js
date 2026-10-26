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

async function run() {
  const tasks = await getAllTasks({ executor_ids: [28418, 28419, 28415], status: 'all' });
  console.log('Total tasks fetched:', tasks.length);

  const closed20 = tasks.filter(t => t.done && t.closed_at && t.closed_at.includes('2026-10-20'));
  const closed21 = tasks.filter(t => t.done && t.closed_at && t.closed_at.includes('2026-10-21'));
  
  console.log('\n--- 1. ЗАКРЫТО 20 ОКТЯБРЯ (ВЧЕРА) ---');
  console.log('Всего закрыто вчера:', closed20.length);
  const byUser20 = {};
  closed20.forEach(t => {
    const name = t.executor?.name || 'Unknown';
    byUser20[name] = (byUser20[name] || 0) + 1;
  });
  console.log('По сотрудникам:', byUser20);
  
  console.log('\n--- 2. ЗАКРЫТО 21 ОКТЯБРЯ (СЕГОДНЯ УТРОМ) ---');
  console.log('Всего закрыто сегодня:', closed21.length);
  const byUser21 = {};
  closed21.forEach(t => {
    const name = t.executor?.name || 'Unknown';
    byUser21[name] = (byUser21[name] || 0) + 1;
  });
  console.log('По сотрудникам:', byUser21);

  console.log('\n--- 3. СПЕЦИАЛЬНАЯ ЗАДАЧА АНДРЕЯ ПО НАВЕДЕНИЮ ПОРЯДКА ---');
  const foundTask = tasks.filter(t => {
    const txt = ((t.text || '') + ' ' + (t.title || '')).toLowerCase();
    return txt.includes('unicraft') || txt.includes('правильные') || txt.includes('пронто') || txt.includes('порядок');
  });
  console.log('Найдено задач:', foundTask.length);
  foundTask.forEach(t => {
    console.log(`[Task ID: ${t.id}] "${t.text || t.title}" | Исполнитель: ${t.executor?.name} | Выполнено: ${t.done} | Закрыто: ${t.closed_at}`);
  });

  // Check timeline of lead 2888092 (Пронто Кью), 2893582 (Правильные ИТ), 2911079 (Unicraft)
  console.log('\n--- 4. ТАЙМЛАЙНЫ СДЕЛОК UNICRAFT, ПРАВИЛЬНЫЕ ИТ, ПРОНТО КЬЮ ---');
  for (const leadId of [2911079, 2893582, 2888092]) {
    const tl = await callTool('get_timeline', { entity_type: 'lead', entity_id: leadId });
    const events = Array.isArray(tl) ? tl : (tl.items || tl.events || []);
    console.log(`\nСделка ID ${leadId}:`);
    events.slice(0, 4).forEach(ev => {
      console.log(`  - [${ev.kind}] ${ev.created_at || ev.date}: ${ev.text || ev.task?.text || ev.title || JSON.stringify(ev).slice(0, 100)}`);
    });
  }
}
run();
