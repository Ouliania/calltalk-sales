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
  console.log('=== 1. ПРОВЕРКА ПОЛЕЙ В CRM (FIELDS) ===');
  const fields = await callTool('list_fields', {});
  console.log('Fields count:', fields.length || Object.keys(fields).length);
  const items = Array.isArray(fields) ? fields : (fields.items || fields.fields || []);
  items.forEach(f => console.log(`  - [ID ${f.id}] "${f.name}" (type: ${f.type}, entity: ${f.entity_type})`));

  console.log('\n=== 2. ПРОВЕРКА ТЕГОВ (TAGS) ===');
  const tags = await callTool('list_tags', {});
  console.log('Tags:', JSON.stringify(tags));

  console.log('\n=== 3. ПРОВЕРКА ВОРОНОК (PIPELINES) ===');
  const pipes = await callTool('list_pipelines', {});
  (pipes.pipelines || pipes || []).forEach(p => console.log(`  - Pipeline [ID ${p.id}] "${p.name}" (stages: ${p.stages?.length})`));

  console.log('\n=== 4. ПРОВЕРКА КАНАЛОВ СВЯЗИ / ИНТЕГРАЦИЙ (CHANNELS) ===');
  try {
    const channels = await callTool('get_channels', {});
    console.log('Channels:', JSON.stringify(channels));
  } catch(e) {
    console.log('get_channels err:', e.message);
  }
}
run();
