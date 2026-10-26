const endpoint = 'https://mcp.okocrm.com/crm';
const token = 'OKOCRM_TOKEN_PLACEHOLDER';

const ANDREY_ID = 28418;
const LEONID_ID = 28419;
const ULIANA_ID = 28415;

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
  return data;
}

function isEmail(l) {
  const name = l.name || '';
  return /@.*\.|\.ru>|\.com>|mail|email|^re:/i.test(name) || /@\w+\.\w+/.test(name);
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function main() {
  console.log('Fetching leads from pipeline 30944...');
  let leads = [];
  let cursor = null;
  while (true) {
    const args = { pipeline_id: 30944 };
    if (cursor) args.cursor = cursor;
    const resRaw = await callTool('search_leads', args);
    const content = resRaw.result && resRaw.result.content && resRaw.result.content[0] ? JSON.parse(resRaw.result.content[0].text) : {};
    const items = content.items || [];
    leads = leads.concat(items);
    cursor = content.next_cursor;
    if (!cursor || items.length === 0) break;
  }

  // Filter only Uliana's leads, exclude test leads
  const ulianaLeads = leads.filter(l => l.responsible && l.responsible.id === ULIANA_ID && !l.name.includes('__test_') && l.name !== 'тест');
  console.log('Total Uliana leads to reassign:', ulianaLeads.length);

  const activeLeads = ulianaLeads.filter(l => l.stage && l.stage.id === 148390);
  const archiveLeads = ulianaLeads.filter(l => l.stage && l.stage.id === 148393);

  const activeEmail = activeLeads.filter(isEmail);
  const activeSite = activeLeads.filter(l => !isEmail(l));

  const archiveEmail = archiveLeads.filter(isEmail);
  const archiveSite = archiveLeads.filter(l => !isEmail(l));

  const assignments = [];

  // 1. Distribute active Email alternating
  activeEmail.forEach((l, idx) => {
    const respId = idx % 2 === 0 ? ANDREY_ID : LEONID_ID;
    assignments.push({ leadId: l.id, name: l.name, respId, type: 'Active-Email' });
  });

  // 2. Distribute active Site alternating
  // Notice activeEmail has 15 items: 8 to Andrey, 7 to Leonid.
  // To keep 50/50 overall active, start activeSite with Leonid first!
  activeSite.forEach((l, idx) => {
    const respId = idx % 2 === 0 ? LEONID_ID : ANDREY_ID;
    assignments.push({ leadId: l.id, name: l.name, respId, type: 'Active-Site' });
  });

  // 3. Distribute archive Email alternating
  archiveEmail.forEach((l, idx) => {
    const respId = idx % 2 === 0 ? ANDREY_ID : LEONID_ID;
    assignments.push({ leadId: l.id, name: l.name, respId, type: 'Archive-Email' });
  });

  // 4. Distribute archive Site alternating
  archiveSite.forEach((l, idx) => {
    const respId = idx % 2 === 0 ? ANDREY_ID : LEONID_ID;
    assignments.push({ leadId: l.id, name: l.name, respId, type: 'Archive-Site' });
  });

  const andreyTotal = assignments.filter(a => a.respId === ANDREY_ID).length;
  const leonidTotal = assignments.filter(a => a.respId === LEONID_ID).length;
  console.log(`Plan verified: Andrey = ${andreyTotal}, Leonid = ${leonidTotal}`);

  console.log('Starting reassignment in OkoCRM with responsible_id...');
  let successCount = 0;
  for (let i = 0; i < assignments.length; i++) {
    const item = assignments[i];
    const userLabel = item.respId === ANDREY_ID ? 'Андрей' : 'Леонид';
    try {
      const res = await callTool('update_lead', {
        lead_id: item.leadId,
        responsible_id: item.respId
      });
      if (res.error) {
        console.error(`Error updating lead ${item.leadId}:`, res.error);
      } else {
        successCount++;
      }
      if ((i + 1) % 10 === 0 || i === assignments.length - 1) {
        console.log(`Progress: ${i + 1}/${assignments.length} updated (latest: ${item.leadId} -> ${userLabel})`);
      }
      await sleep(100);
    } catch (e) {
      console.error(`Exception updating lead ${item.leadId}:`, e.message);
    }
  }

  console.log(`DONE! Successfully reassigned ${successCount} leads 50/50.`);
}

main().catch(console.error);
