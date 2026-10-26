const endpoint = 'https://mcp.okocrm.com/crm';
const token = 'OKOCRM_TOKEN_PLACEHOLDER';

// System source IDs in OkoCRM
const SOURCE_MAP = {
  EMAIL: 78389,              // 'Email'
  SITE: 78388,               // 'Сайт'
  NETWORK: 78390,            // 'Network основателя'
  PARTNER: 78391             // 'Партнерка'
};

async function callTool(name, args) {
  const res = await fetch(endpoint, {
    method: 'POST',
    headers: { 'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json' },
    body: JSON.stringify({ jsonrpc: '2.0', id: Date.now(), method: 'tools/call', params: { name, arguments: args } })
  });
  const data = await res.json();
  return data;
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function main() {
  console.log('Fetching all leads from both pipelines (30895, 30944)...');
  let allLeads = [];

  for (const pipeline_id of [30895, 30944]) {
    let cursor = null;
    while (true) {
      const args = { pipeline_id };
      if (cursor) args.cursor = cursor;
      const resRaw = await callTool('search_leads', args);
      const content = resRaw.result && resRaw.result.content && resRaw.result.content[0] ? JSON.parse(resRaw.result.content[0].text) : {};
      const items = content.items || [];
      allLeads = allLeads.concat(items);
      cursor = content.next_cursor;
      if (!cursor || items.length === 0) break;
    }
  }

  console.log(`Total leads to process: ${allLeads.length}`);

  let updatedCount = 0;
  let alreadySetCount = 0;
  let skippedTestCount = 0;

  for (let i = 0; i < allLeads.length; i++) {
    const leadSummary = allLeads[i];
    if (leadSummary.name && (leadSummary.name.includes('__test_') || leadSummary.name === 'тест')) {
      skippedTestCount++;
      continue;
    }

    const leadId = leadSummary.id;

    // Fetch full lead details
    const fullLeadRes = await callTool('get_lead', { lead_id: leadId });
    const fullLead = fullLeadRes.result && fullLeadRes.result.structuredContent ? fullLeadRes.result.structuredContent.lead : null;

    if (!fullLead) {
      console.error(`Could not fetch details for lead ${leadId}`);
      continue;
    }

    const fields = fullLead.fields || [];
    const cfField = fields.find(f => f.var_name === 'cf_41795');
    const sysField = fields.find(f => f.var_name === 'source_id');

    const cfVal = cfField && cfField.value ? (cfField.value.name || cfField.value) : null;
    const currentSysValId = sysField && sysField.value ? sysField.value.id : null;

    let targetSourceId = null;

    // Rule 1: From custom field cf_41795 if populated
    if (cfVal) {
      if (cfVal === 'Email-аутрич') {
        targetSourceId = SOURCE_MAP.EMAIL;
      } else if (cfVal === 'Сайт') {
        targetSourceId = SOURCE_MAP.SITE;
      } else if (cfVal === 'Рекомендация') {
        targetSourceId = SOURCE_MAP.NETWORK;
      } else if (cfVal === 'Партнёры') {
        targetSourceId = SOURCE_MAP.PARTNER;
      }
    }

    // Rule 2: If still not determined or was "Другое", check contacts for email
    if (!targetSourceId) {
      const contacts = fullLead.contacts || [];
      let hasContactEmail = false;

      for (const c of contacts) {
        if (c.emails && c.emails.length > 0) {
          hasContactEmail = true;
          break;
        }
      }

      // Also check lead custom email field cf_42064
      const leadEmailField = fields.find(f => f.var_name === 'cf_42064');
      if (leadEmailField && leadEmailField.value && leadEmailField.value.includes('@')) {
        hasContactEmail = true;
      }

      if (hasContactEmail) {
        targetSourceId = SOURCE_MAP.EMAIL;
      }
    }

    // Rule 3: Check name patterns
    if (!targetSourceId) {
      const name = (fullLead.name || '').toLowerCase();
      if (name.startsWith('re:') || /@.*\.|\.ru>|\.com>|mail|email/.test(name)) {
        targetSourceId = SOURCE_MAP.EMAIL;
      } else {
        // Default to Сайт
        targetSourceId = SOURCE_MAP.SITE;
      }
    }

    // Now check if update is needed
    if (currentSysValId === targetSourceId) {
      alreadySetCount++;
    } else {
      try {
        await callTool('update_lead', {
          lead_id: leadId,
          fields: {
            source_id: targetSourceId
          }
        });
        updatedCount++;
      } catch (e) {
        console.error(`Error updating lead ${leadId}:`, e.message);
      }
    }

    if ((i + 1) % 20 === 0 || i === allLeads.length - 1) {
      console.log(`Progress: ${i + 1}/${allLeads.length} leads evaluated (Updated: ${updatedCount}, Already matched: ${alreadySetCount})`);
    }

    await sleep(80);
  }

  console.log('\n--- MIGRATION FINISHED ---');
  console.log(`Total leads: ${allLeads.length}`);
  console.log(`Updated with source_id: ${updatedCount}`);
  console.log(`Already had correct source_id: ${alreadySetCount}`);
  console.log(`Skipped test leads: ${skippedTestCount}`);
}

main().catch(console.error);
