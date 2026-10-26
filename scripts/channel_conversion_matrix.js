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

function classifyChannel(lead, timelineEvents) {
  const name = (lead.name || '').toLowerCase();
  const stageName = (lead.stage?.name || '').toLowerCase();
  
  // 1. Trigga
  if (name.includes('trigga') || stageName.includes('trigga')) return 'Trigga';
  for (const ev of timelineEvents) {
    const txt = (ev.text || ev.title || '').toLowerCase();
    if (txt.includes('входящий ответ из trigga') || txt.includes('кампания: для call-talk') || txt.includes('trigga')) {
      return 'Trigga';
    }
  }

  // 2. Partner / Referral
  if (name.includes('партнер') || name.includes('перестройка') || name.includes('алексе') || name.includes('рекомендаци')) {
    return 'Партнерка / Рекомендация';
  }
  for (const ev of timelineEvents) {
    const txt = (ev.text || '').toLowerCase();
    if (txt.includes('партнерский лид') || txt.includes('передал партнер')) return 'Партнерка / Рекомендация';
  }

  // 3. Website / Inbound
  if (name.includes('заявка с сайта') || name.includes('входящая заявка') || name.includes('intarial') || name.includes('take and wake') ||
      /^https?:\/\//i.test(lead.name || '') || /^[a-z0-9-]+\.(ru|pro|com|net|io|tech|su)$/i.test((lead.name || '').trim())) {
    // Check if it's not a cold outreach lead where the deal was named after the domain
    // If timeline mentions "заявка с сайта" -> website
    for (const ev of timelineEvents) {
      const txt = (ev.text || '').toLowerCase();
      if (txt.includes('заявка с сайта') || txt.includes('входящая заявка')) return 'Сайт / Входящий';
    }
    if (name.includes('intarial') || name.includes('take and wake')) return 'Сайт / Входящий';
  }

  // 4. Default: Cold Email Outreach
  return 'Холодный Email-аутрич';
}

async function main() {
  console.log('=== СБОР ВСЕХ ДАННЫХ ПО ВОРОНКЕ B2B ДЛЯ АНАЛИЗА КАНАЛОВ ===');
  
  const activeLeads = await getAllLeads({ pipeline_id: 30895, status: 'active' });
  const wonLeads = await getAllLeads({ pipeline_id: 30895, status: 'won' });
  const lostLeads = await getAllLeads({ pipeline_id: 30895, status: 'lost' });

  const allLeads = [...activeLeads, ...wonLeads, ...lostLeads];
  console.log(`Всего сделок в B2B: ${allLeads.length} (активных: ${activeLeads.length}, выиграно: ${wonLeads.length}, проиграно: ${lostLeads.length})\n`);

  // Channel tracking structures
  const channels = {
    'Холодный Email-аутрич': { total: 0, mql: 0, meeting: 0, kp: 0, contract: 0, paid: 0, leads: [] },
    'Trigga': { total: 0, mql: 0, meeting: 0, kp: 0, contract: 0, paid: 0, leads: [] },
    'Сайт / Входящий': { total: 0, mql: 0, meeting: 0, kp: 0, contract: 0, paid: 0, leads: [] },
    'Партнерка / Рекомендация': { total: 0, mql: 0, meeting: 0, kp: 0, contract: 0, paid: 0, leads: [] }
  };

  for (const l of allLeads) {
    let events = [];
    try {
      const tl = await callTool('get_timeline', { entity_type: 'lead', entity_id: l.id });
      events = Array.isArray(tl) ? tl : (tl.items || tl.events || []);
    } catch(e) {}

    const ch = classifyChannel(l, events);
    const cData = channels[ch] || channels['Холодный Email-аутрич'];
    cData.total++;
    cData.leads.push(l);

    // Track stages reached by this lead
    const curStage = (l.stage?.name || '').toLowerCase();
    const isWon = l.status === 'won' || curStage.includes('успешно') || curStage.includes('оплач');
    
    // Check if reached MQL / Квалификация
    let hasMQL = curStage.includes('квалификац') || curStage.includes('mql') || curStage.includes('встреч') || curStage.includes('кп') || curStage.includes('договор') || curStage.includes('счёт') || isWon;
    
    // Check if reached Meeting
    let hasMeeting = curStage.includes('встреч') || curStage.includes('кп') || curStage.includes('договор') || curStage.includes('счёт') || isWon;
    
    // Check if reached KP
    let hasKP = curStage.includes('кп') || curStage.includes('договор') || curStage.includes('счёт') || isWon;
    
    // Check if reached Contract
    let hasContract = curStage.includes('договор') || curStage.includes('счёт') || isWon;
    
    // Check if Paid
    let hasPaid = isWon;

    // Also check historical timeline events for leads that were disqualified or moved
    for (const ev of events) {
      const txt = ((ev.text || '') + ' ' + (ev.title || '') + ' ' + (ev.task?.title || '') + ' ' + (ev.task?.text || '')).toLowerCase();
      if (txt.includes('встреча назначена') || txt.includes('встреча проведена') || txt.includes('назначена встреча') || txt.includes('проведена встреча')) {
        hasMeeting = true;
        hasMQL = true;
      }
      if (txt.includes('кп отправлено') || txt.includes('отправлено кп') || txt.includes('коммерческое предложение')) {
        hasKP = true;
        hasMeeting = true;
        hasMQL = true;
      }
      if (txt.includes('договор на подписи') || txt.includes('договор отправлен')) {
        hasContract = true;
        hasKP = true;
        hasMeeting = true;
        hasMQL = true;
      }
      if (txt.includes('успешно реализовано') || txt.includes('оплата получена') || txt.includes('счет оплачен')) {
        hasPaid = true;
      }
    }

    if (hasMQL) cData.mql++;
    if (hasMeeting) cData.meeting++;
    if (hasKP) cData.kp++;
    if (hasContract) cData.contract++;
    if (hasPaid) cData.paid++;
  }

  console.log('======================================================');
  console.log('📊 ИТОГОВАЯ МАТРИЦА КОНВЕРСИЙ ПО КАНАЛАМ В B2B:');
  console.log('======================================================\n');

  for (const [chName, d] of Object.entries(channels)) {
    console.log(`------------------------------------------------------`);
    console.log(`📡 КАНАЛ: ${chName.toUpperCase()} (Всего лидов: ${d.total})`);
    console.log(`------------------------------------------------------`);
    
    if (d.total === 0) {
      console.log('  Нет данных по лидам в этом канале.\n');
      continue;
    }

    const convMQL = ((d.mql / d.total) * 100).toFixed(1);
    const convMeeting = ((d.meeting / d.total) * 100).toFixed(1);
    const convKPFromMeeting = d.meeting > 0 ? ((d.kp / d.meeting) * 100).toFixed(1) : 0;
    const convKPFromTotal = ((d.kp / d.total) * 100).toFixed(1);
    const convContractFromKP = d.kp > 0 ? ((d.contract / d.kp) * 100).toFixed(1) : 0;
    const convContractFromTotal = ((d.contract / d.total) * 100).toFixed(1);
    const convPaidFromTotal = ((d.paid / d.total) * 100).toFixed(1);
    const convPaidFromKP = d.kp > 0 ? ((d.paid / d.kp) * 100).toFixed(1) : 0;

    console.log(`1. Лиды (Входящий поток): ${d.total}`);
    console.log(`2. Квалифицированы / MQL: ${d.mql} (${convMQL}% от лидов)`);
    console.log(`3. Дошли до Встречи: ${d.meeting} (${convMeeting}% от лидов)`);
    console.log(`4. Дошли до КП: ${d.kp} (${convKPFromMeeting}% от встреч | ${convKPFromTotal}% сквозная от лидов)`);
    console.log(`5. Договор на подписи: ${d.contract} (${convContractFromKP}% от КП | ${convContractFromTotal}% от лидов)`);
    console.log(`6. Оплачено / Выиграно: ${d.paid} (${convPaidFromKP}% от КП | ${convPaidFromTotal}% общая сквозная)`);
    
    // Print key leads
    console.log(`\n  Сделки на этапе КП / Договор / Оплата:`);
    d.leads.filter(l => {
      const s = (l.stage?.name || '').toLowerCase();
      return s.includes('кп') || s.includes('договор') || s.includes('счёт') || l.status === 'won';
    }).forEach(l => {
      console.log(`    * [ID ${l.id}] "${l.name}" | Этап: "${l.stage?.name}" | Ответственный: ${l.responsible?.name}`);
    });
    console.log('\n');
  }

  // Overall totals across ALL channels
  const totalLeads = allLeads.length;
  const totalMQL = Object.values(channels).reduce((acc, c) => acc + c.mql, 0);
  const totalMeeting = Object.values(channels).reduce((acc, c) => acc + c.meeting, 0);
  const totalKP = Object.values(channels).reduce((acc, c) => acc + c.kp, 0);
  const totalContract = Object.values(channels).reduce((acc, c) => acc + c.contract, 0);
  const totalPaid = Object.values(channels).reduce((acc, c) => acc + c.paid, 0);

  console.log('======================================================');
  console.log('🏆 ОБЩАЯ СВОДНАЯ КОНВЕРСИЯ ВСЕЙ B2B-ВОРОНКИ CALL-TALK:');
  console.log('======================================================');
  console.log(`1. Всего лидов: ${totalLeads}`);
  console.log(`2. Квалифицированы / MQL: ${totalMQL} (${((totalMQL/totalLeads)*100).toFixed(1)}%)`);
  console.log(`3. Назначено / проведено встреч: ${totalMeeting} (${((totalMeeting/totalLeads)*100).toFixed(1)}% от лидов)`);
  console.log(`4. Отправлено КП: ${totalKP} (${totalMeeting > 0 ? ((totalKP/totalMeeting)*100).toFixed(1) : 0}% от встреч | ${((totalKP/totalLeads)*100).toFixed(1)}% от лидов)`);
  console.log(`5. Договоров на подписи: ${totalContract} (${totalKP > 0 ? ((totalContract/totalKP)*100).toFixed(1) : 0}% от КП | ${((totalContract/totalLeads)*100).toFixed(1)}% от лидов)`);
  console.log(`6. Оплачено: ${totalPaid} (${totalKP > 0 ? ((totalPaid/totalKP)*100).toFixed(1) : 0}% от КП | ${((totalPaid/totalLeads)*100).toFixed(1)}% сквозная)`);
}

main();
