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
  const leadsToCheck = [2905345, 2924494, 2888095, 2897921, 2906373];
  for (const lid of leadsToCheck) {
    const tl = await callTool('get_timeline', { entity_type: 'lead', entity_id: lid });
    const items = tl.items || [];
    console.log('\n====================================');
    console.log('Lead ID:', lid);
    items.forEach(it => {
      const txt = (it.text || it.task?.text || it.title || '').replace(/\n/g, ' ').slice(0, 120);
      console.log(`[${it.kind}] Author: ${it.author?.id} (${it.author?.name}) | ${it.created_at} | ${txt}`);
    });
  }
}
run();
