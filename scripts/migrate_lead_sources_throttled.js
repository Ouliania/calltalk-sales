const endpoint = 'https://mcp.okocrm.com/crm';
const token = 'OKOCRM_TOKEN_PLACEHOLDER';

const SOURCE_MAP = {
  EMAIL: 78389,              // 'Email'
  SITE: 78388,               // 'Сайт'
  NETWORK: 78390,            // 'Network основателя'
  PARTNER: 78391             // 'Партнерка'
};

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function callToolWithRetry(name, args, maxRetries = 5) {
  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json' },
        body: JSON.stringify({ jsonrpc: '2.0', id: Date.now(), method: 'tools/call', params: { name, arguments: args } })
      });
      const data = await res.json();
      if (data.error === 'rate_limited') {
        const backoff = attempt * 2000;
        console.log(`[Rate limited] Backing off for ${backoff}ms (attempt ${attempt}/${maxRetries})...`);
        await sleep(backoff);
        continue;
      }
      return data;
    } catch (e) {
      console.log(`[Network error] ${e.message}, retrying in 2000ms...`);
      await sleep(2000);
    }
  }
  return null;
}

async function main() {
  console.log('Fetching all leads from both pipelines (30895, 30944)...');
  let allLeads = [];

  for (const pipeline_id of [30895, 30944]) {
    let cursor = null;
    while (true) {
      const args = { pipeline_id };
      if (cursor) args.cursor = cursor;
      const resRaw = await callToolWithRetry('search_leads', args);
      const content = resRaw && resRaw.result && resRaw.result.content && resRaw.result.content[0] ? JSON.parse(resRaw.result.content[0].text) : {};
      const items = content.items || [];
      allLeads = allLeads.concat(items);
      cursor = content.next_cursor;
      if (!cursor || items.length === 0) break;
      await sleep(500);
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

    // Fetch full lead details with retry
    const fullLeadRes = await callToolWithRetry('get_lead', { lead_id: leadId });
    const fullLead = fullLeadRes && fullLeadRes.result && fullLeadRes.result.structuredContent ? fullLeadRes.result.structuredContent.lead : null;

    if (!fullLead) {
      console.error(`Could not fetch details for lead ${leadId} after retries`);
      await sleep(1000);
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
        targetSourceId = SOURCE_MAP.SITE;
      }
    }

    // Update if different
    if (currentSysValId === targetSourceId) {
      alreadySetCount++;
    } else {
      const updateRes = await callToolWithRetry('update_lead', {
        lead_id: leadId,
        fields: {
          source_id: targetSourceId
        }
      });
      if (updateRes && !updateRes.error) {
        updatedCount++;
      } else {
        console.error(`Failed to update lead ${leadId}:`, updateRes ? updateRes.error : 'null');
      }
      await sleep(350); // safe pause after writes
    }

    if ((i + 1) % 15 === 0 || i === allLeads.length - 1) {
      console.log(`Progress: ${i + 1}/${allLeads.length} leads evaluated (Updated: ${updatedCount}, Already matched: ${alreadySetCount})`);
    }

    await sleep(250); // gentle pause between leads
  }

  console.log('\n--- MIGRATION FINISHED SUCCESSFULLY ---');
  console.log(`Total leads: ${allLeads.length}`);
  console.log(`Updated with source_id: ${updatedCount}`);
  console.log(`Already had correct source_id: ${alreadySetCount}`);
  console.log(`Skipped test leads: ${skippedTestCount}`);
}

main().catch(console.error);
