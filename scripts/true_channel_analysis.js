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

async function getAllLeadsWithFilter(fieldsFilter) {
  let leads = [];
  let cursor = null;
  while (true) {
    const p = { limit: 100, fields: fieldsFilter };
    if (cursor) p.cursor = cursor;
    const res = await callTool('search_leads', p);
    const items = res.items || [];
    leads = leads.concat(items);
    cursor = res.next_cursor;
    if (!cursor || items.length === 0) break;
  }
  return leads;
}

async function getAllLeadsBasic(params) {
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
  console.log('=== ЧЕСТНЫЙ АНАЛИЗ КАНАЛОВ ПО ПОЛЮ source_id (САЙТ vs EMAIL) ===\n');

  // Fetch all leads by source
  const siteLeads = await getAllLeadsWithFilter({ source_id: 'Сайт' });
  const emailLeads = await getAllLeadsWithFilter({ source_id: 'Email' });
  const partnerLeads = await getAllLeadsWithFilter({ source_id: 'Партнерка' });
  const networkLeads = await getAllLeadsWithFilter({ source_id: 'Network основателя' });

  // Also fetch all leads in CRM to check if any have source_id unassigned
  const allLeadsInCRM = await getAllLeadsBasic({ status: 'all' }); // wait, remember status: 'all' is invalid
  const activeAll = await getAllLeadsBasic({ status: 'active' });
  const wonAll = await getAllLeadsBasic({ status: 'won' });
  const lostAll = await getAllLeadsBasic({ status: 'lost' });
  const totalCRM = [...activeAll, ...wonAll, ...lostAll];

  console.log(`Всего сделок в CRM: ${totalCRM.length}`);
  console.log(`  - С источником «Сайт»: ${siteLeads.length}`);
  console.log(`  - С источником «Email» (включая Trigga): ${emailLeads.length}`);
  console.log(`  - С источником «Партнерка»: ${partnerLeads.length}`);
  console.log(`  - С источником «Network основателя»: ${networkLeads.length}`);

  const accountedIds = new Set([...siteLeads, ...emailLeads, ...partnerLeads, ...networkLeads].map(l => l.id));
  const unassigned = totalCRM.filter(l => !accountedIds.has(l.id));
  console.log(`  - Без явного источника в поле: ${unassigned.length}`);

  // Let's analyze DATE RANGE for each channel
  function getDateRange(arr) {
    const dates = arr.map(l => l.created_at).filter(Boolean).sort();
    return { from: dates[0]?.slice(0, 10), to: dates[dates.length - 1]?.slice(0, 10) };
  }

  console.log(`\nПериоды:`);
  console.log(`  Сайт: с ${getDateRange(siteLeads).from} по ${getDateRange(siteLeads).to}`);
  console.log(`  Email: с ${getDateRange(emailLeads).from} по ${getDateRange(emailLeads).to}`);

  // Funnel analysis function
  function analyzeFunnel(leads, name) {
    console.log(`\n======================================================`);
    console.log(`📡 КАНАЛ: ${name.toUpperCase()} (Всего: ${leads.length})`);
    console.log(`======================================================`);

    const stageCounts = {};
    let mql = 0;
    let meeting = 0;
    let kp = 0;
    let contract = 0;
    let won = 0;
    let lost = 0;

    for (const l of leads) {
      const s = (l.stage?.name || '').toLowerCase();
      stageCounts[l.stage?.name] = (stageCounts[l.stage?.name] || 0) + 1;

      if (l.status === 'won' || s.includes('успешно') || s.includes('оплач')) {
        won++; contract++; kp++; meeting++; mql++;
      } else if (s.includes('договор') || s.includes('счёт')) {
        contract++; kp++; meeting++; mql++;
      } else if (s.includes('кп отправлено') || s.includes('кп')) {
        kp++; meeting++; mql++;
      } else if (s.includes('встреч')) {
        meeting++; mql++;
      } else if (s.includes('квалификац') || s.includes('mql')) {
        mql++;
      }

      if (l.status === 'lost' || s.includes('отказ') || s.includes('архив')) {
        lost++;
      }
    }

    console.log(`Текущие этапы:`, stageCounts);
    console.log(`Воронка:`);
    console.log(`  1. Всего лидов: ${leads.length}`);
    console.log(`  2. Дошли до MQL/Квал: ${mql} (${leads.length ? ((mql/leads.length)*100).toFixed(1) : 0}%)`);
    console.log(`  3. Дошли до Встречи: ${meeting} (${leads.length ? ((meeting/leads.length)*100).toFixed(1) : 0}%)`);
    console.log(`  4. Дошли до КП: ${kp} (${meeting ? ((kp/meeting)*100).toFixed(1) : 0}% от встреч | ${leads.length ? ((kp/leads.length)*100).toFixed(1) : 0}% от всех лидов)`);
    console.log(`  5. Договор на подписи: ${contract} (${kp ? ((contract/kp)*100).toFixed(1) : 0}% от КП | ${leads.length ? ((contract/leads.length)*100).toFixed(1) : 0}% от лидов)`);
    console.log(`  6. Выиграно / Оплачено: ${won} (${kp ? ((won/kp)*100).toFixed(1) : 0}% от КП | ${leads.length ? ((won/leads.length)*100).toFixed(1) : 0}% от лидов)`);
    console.log(`  7. Закрыто в отказ/архив: ${lost} (${leads.length ? ((lost/leads.length)*100).toFixed(1) : 0}%)`);

    // List key leads in KP/Contract/Won
    const keyLeads = leads.filter(l => {
      const s = (l.stage?.name || '').toLowerCase();
      return s.includes('кп') || s.includes('договор') || s.includes('счёт') || l.status === 'won';
    });
    if (keyLeads.length) {
      console.log(`\n  Ключевые сделки (КП / Договор / Оплата):`);
      keyLeads.forEach(kl => console.log(`    * [ID ${kl.id}] "${kl.name}" | Этап: "${kl.stage?.name}" | Ответственный: ${kl.responsible?.name}`));
    }
  }

  analyzeFunnel(siteLeads, 'Сайт');
  analyzeFunnel(emailLeads, 'Email-аутрич (вкл. Trigga)');
  if (partnerLeads.length) analyzeFunnel(partnerLeads, 'Партнерка');
  if (networkLeads.length) analyzeFunnel(networkLeads, 'Network основателя');
}

main();
