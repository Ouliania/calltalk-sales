const endpoint = 'https://mcp.okocrm.com/crm';
const token = 'OKOCRM_TOKEN_PLACEHOLDER';

async function callTool(name, args) {
  const res = await fetch(endpoint, {
    method: 'POST',
    headers: {
      'Authorization': 'Bearer ' + token,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      jsonrpc: '2.0',
      id: Date.now(),
      method: 'tools/call',
      params: { name, arguments: args }
    })
  });
  const data = await res.json();
  if (data.result && data.result.content && data.result.content[0]) {
    try {
      return JSON.parse(data.result.content[0].text);
    } catch(e) {
      return data.result.content[0].text;
    }
  }
  return data;
}

const renames = [
  { id: 2899846, newName: 'Марина Романова — БВС-Логистика' },
  { id: 2899812, newName: 'Артем Якушев — Pikabu' },
  { id: 2898147, newName: 'Александр Баранов — Аполло ЗМК' },
  { id: 2898142, newName: 'Артем Даниловец — NeedToBuild' },
  { id: 2898115, newName: 'Александр — Стальные Технологии (DZ Steel)' },
  { id: 2898106, newName: 'GuteGrad — Металлоконструкции' },
  { id: 2898095, newName: 'Елена Точиленко — Софико' },
  { id: 2898086, newName: 'Алексей Смирнов — ЯЗМК' },
  { id: 2898083, newName: 'Павел Ригосик — Изолинк' },
  { id: 2898075, newName: 'Татьяна Орлова — Гридем' },
  { id: 2898063, newName: 'Михаил Витальевич — HealthSoul' },
  { id: 2897915, newName: 'Игорь Стеценко — BestCarCenter' },
  { id: 2897906, newName: 'Владислав — Моя Удаленка' },
  { id: 2897663, newName: 'Коммерческий директор — 4B (Лирус)' }
];

async function run() {
  console.log(`Starting renaming ${renames.length} leads for Leonid...`);
  for (const item of renames) {
    try {
      const res = await callTool('update_lead', {
        lead_id: item.id,
        name: item.newName
      });
      console.log(`✅ [${item.id}] -> "${item.newName}"`);
    } catch (err) {
      console.error(`❌ Error on [${item.id}]:`, err.message);
    }
  }
  console.log('All renames completed successfully!');
}

run();
