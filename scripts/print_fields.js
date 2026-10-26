const endpoint = 'https://mcp.okocrm.com/crm';
const token = 'OKOCRM_TOKEN_PLACEHOLDER';

async function test() {
  const res = await fetch(endpoint, {
    method: 'POST',
    headers: { 'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json' },
    body: JSON.stringify({ jsonrpc: '2.0', id: Date.now(), method: 'tools/call', params: { name: 'list_fields', arguments: { entity_type: 'leads' } } })
  });
  const data = await res.json();
  const parsed = JSON.parse(data.result.content[0].text);
  parsed.tabs.forEach(t => {
    console.log(`\n=== TAB: ${t.name} ===`);
    t.groups.forEach(g => {
      console.log(`  -- Group: ${g.name} --`);
      g.fields.forEach(f => {
        const optStr = f.options ? f.options.map(o => o.name).join(', ') : '';
        console.log(`    [Field ${f.id}] "${f.name}" (var: ${f.var_name}, type: ${f.type}) ${optStr ? '-> [' + optStr + ']' : ''}`);
      });
    });
  });
}
test();
