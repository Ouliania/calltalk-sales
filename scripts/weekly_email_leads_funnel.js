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

function detectSource(l) {
  const name = l.name || '';
  if (/^https?:\/\//i.test(name) || /^[a-z0-9-]+\.(ru|pro|com|net|io|tech|su)$/i.test(name.trim())) {
    return 'Сайт / Входящий';
  }
  if (name.includes('Intarial') || name.includes('Входящая заявка') || name.includes('заявка с сайта')) {
    return 'Сайт / Входящий';
  }
  if (name.includes('Отделы маркетинга для клиник') || name.includes('Перестройка')) {
    return 'Партнерка';
  }
  return 'Email-аутрич';
}

async function main() {
  const pipesRes = await callTool('list_pipelines', {});
  const b2bPipe = pipesRes.pipelines.find(p => p.id === 30895);
  const stages = Object.fromEntries(b2bPipe.stages.map(s => [s.id, s.name]));

  // Fetch all active, won, lost leads in B2B
  console.log('Загружаем все лиды (active, won, lost) из воронки B2B...');
  const activeLeads = await getAllLeads({ pipeline_id: 30895, status: 'active' });
  const wonLeads = await getAllLeads({ pipeline_id: 30895, status: 'won' });
  const lostLeads = await getAllLeads({ pipeline_id: 30895, status: 'lost' });

  const allB2BLeads = [...activeLeads, ...wonLeads, ...lostLeads];
  console.log(`Всего лидов в B2B (активных: ${activeLeads.length}, выиграно: ${wonLeads.length}, проиграно: ${lostLeads.length}) = ${allB2BLeads.length}`);

  // Filter leads created between 2026-10-12 and 2026-10-16
  const weekLeads = allB2BLeads.filter(l => {
    const created = l.created_at || '';
    return created >= '2026-10-12' && created <= '2026-10-16T23:59:59';
  });

  console.log(`Создано лидов за неделю (12-16 октября): ${weekLeads.length}`);

  const emailLeads = weekLeads.filter(l => detectSource(l) === 'Email-аутрич');
  const otherLeads = weekLeads.filter(l => detectSource(l) !== 'Email-аутрич');
  console.log(`  - Из них Email-аутрич: ${emailLeads.length}`);
  console.log(`  - Прочие (Сайт / Партнерка): ${otherLeads.length}`);
  otherLeads.forEach(l => console.log(`      * [${detectSource(l)}] ${l.name} (Ответственный: ${l.responsible?.name})`));

  const days = ['2026-10-12', '2026-10-13', '2026-10-14', '2026-10-15', '2026-10-16'];
  const managers = [
    { id: 28418, name: 'Андрей' },
    { id: 28419, name: 'Лёня' }
  ];

  console.log('\n======================================================');
  console.log('📊 ОБЩАЯ ДИНАМИКА EMAIL-ЛИДОВ ПО ДНЯМ НЕДЕЛИ:');
  console.log('======================================================');
  for (const d of days) {
    const dLeads = emailLeads.filter(l => l.created_at && l.created_at.startsWith(d));
    const andreyCount = dLeads.filter(l => l.responsible && l.responsible.id === 28418).length;
    const leonidCount = dLeads.filter(l => l.responsible && l.responsible.id === 28419).length;
    const otherCount = dLeads.filter(l => !l.responsible || (l.responsible.id !== 28418 && l.responsible.id !== 28419)).length;
    console.log(`📅 ${d}: ВСЕГО ${dLeads.length} email-лидов (Андрей: ${andreyCount}, Лёня: ${leonidCount}${otherCount > 0 ? ', др: ' + otherCount : ''})`);
  }

  for (const m of managers) {
    console.log(`\n======================================================`);
    console.log(`👤 МЕНЕДЖЕР: ${m.name}`);
    console.log(`======================================================`);

    const mLeads = emailLeads.filter(l => l.responsible && l.responsible.id === m.id);
    console.log(`Всего новых email-лидов за неделю: ${mLeads.length}`);

    console.log(`\n📅 Регистрация по дням:`);
    for (const d of days) {
      const dLeads = mLeads.filter(l => l.created_at && l.created_at.startsWith(d));
      console.log(`  - ${d}: ${dLeads.length} лидов`);
      dLeads.forEach(l => console.log(`      * [ID ${l.id}] ${l.name} | Этап: ${l.stage?.name || stages[l.stage_id]} | Статус: ${l.status}`));
    }

    // Progression to Meeting, KP, Contract
    let reachedMeeting = [];
    let reachedKP = [];
    let reachedContract = [];

    for (const l of mLeads) {
      const curStage = l.stage?.name || stages[l.stage_id] || '';
      let hasMeeting = false;
      let hasKP = false;
      let hasContract = false;

      if (curStage.includes('Встреча') || curStage.includes('КП') || curStage.includes('Договор') || curStage.includes('Счёт')) {
        hasMeeting = true;
      }
      if (curStage.includes('КП') || curStage.includes('Договор') || curStage.includes('Счёт')) {
        hasKP = true;
      }
      if (curStage.includes('Договор') || curStage.includes('Счёт')) {
        hasContract = true;
      }

      try {
        const tl = await callTool('get_timeline', { entity_type: 'lead', entity_id: l.id });
        const events = Array.isArray(tl) ? tl : (tl.items || tl.events || []);
        for (const ev of events) {
          const txt = ((ev.text || '') + ' ' + (ev.title || '') + ' ' + (ev.task?.title || '') + ' ' + (ev.task?.text || '')).toLowerCase();
          if (txt.includes('встреча назначена') || txt.includes('встреча проведена') || txt.includes('назначена встреча') || txt.includes('проведена встреча')) {
            hasMeeting = true;
          }
          if (txt.includes('кп отправлено') || txt.includes('отправлено кп') || txt.includes('коммерческое предложение')) {
            hasKP = true;
          }
          if (txt.includes('договор на подписи') || txt.includes('договор отправлен')) {
            hasContract = true;
          }
        }
      } catch(e) {}

      if (hasMeeting) reachedMeeting.push({ lead: l, stage: curStage });
      if (hasKP) reachedKP.push({ lead: l, stage: curStage });
      if (hasContract) reachedContract.push({ lead: l, stage: curStage });
    }

    console.log(`\n📈 КОНВЕРСИЯ И ПЕРЕХОДЫ (${m.name}):`);
    console.log(`  1. Новые Email-лиды: ${mLeads.length}`);
    
    const convMeeting = mLeads.length ? ((reachedMeeting.length / mLeads.length) * 100).toFixed(1) : 0;
    console.log(`  2. Дошли до Встречи: ${reachedMeeting.length} (${convMeeting}% от входящих email-лидов)`);
    reachedMeeting.forEach(r => console.log(`      * [ID ${r.lead.id}] ${r.lead.name} -> Этап: ${r.stage}`));

    const convKPFromMeeting = reachedMeeting.length ? ((reachedKP.length / reachedMeeting.length) * 100).toFixed(1) : 0;
    const convKPFromLeads = mLeads.length ? ((reachedKP.length / mLeads.length) * 100).toFixed(1) : 0;
    console.log(`  3. Дошли до КП: ${reachedKP.length} (${convKPFromMeeting}% от встреч, ${convKPFromLeads}% от всех лидов)`);
    reachedKP.forEach(r => console.log(`      * [ID ${r.lead.id}] ${r.lead.name} -> Этап: ${r.stage}`));

    const convContractFromKP = reachedKP.length ? ((reachedContract.length / reachedKP.length) * 100).toFixed(1) : 0;
    const convContractFromLeads = mLeads.length ? ((reachedContract.length / mLeads.length) * 100).toFixed(1) : 0;
    console.log(`  4. Дошли до Договора: ${reachedContract.length} (${convContractFromKP}% от КП, ${convContractFromLeads}% от всех лидов)`);
    reachedContract.forEach(r => console.log(`      * [ID ${r.lead.id}] ${r.lead.name} -> Этап: ${r.stage}`));
  }

  // Also check all meetings / KPs / contracts across the whole pipeline this week (including older leads)
  console.log('\n======================================================');
  console.log('📌 ОБЩИЙ РЕЗУЛЬТАТ ПО ВСЕМ СДЕЛКАМ (включая заведенные ранее):');
  console.log('======================================================');
  
  // Let's inspect who held meetings this week
  const allTasks = [];
  let tCursor = null;
  while (true) {
    const res = await callTool('list_tasks', { limit: 50, cursor: tCursor, status: 'all' });
    const items = res.items || [];
    allTasks.push(...items);
    tCursor = res.next_cursor;
    if (!tCursor || items.length === 0) break;
  }
  
  const weekTasks = allTasks.filter(t => 
    (t.closed_at && t.closed_at >= '2026-10-12' && t.closed_at <= '2026-10-16T23:59:59') ||
    (t.date_finish && t.date_finish >= '2026-10-12' && t.date_finish <= '2026-10-16T23:59:59')
  );
  
  console.log(`Всего задач на неделе: ${weekTasks.length}`);
}

main();
