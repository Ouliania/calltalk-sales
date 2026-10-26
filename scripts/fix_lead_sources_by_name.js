const endpoint = 'https://mcp.okocrm.com/crm';
const token = 'OKOCRM_TOKEN_PLACEHOLDER';

// Map to human-readable option NAMES (because OkoCRM API expects option name for select fields!)
const SOURCE_NAMES = {
  EMAIL: 'Email',
  SITE: 'Сайт',
  NETWORK: 'Network основателя',
  PARTNER: 'Партнерка'
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
        const backoff = attempt * 2500;
        console.log(`[Rate limited] Waiting ${backoff}ms (attempt ${attempt}/${maxRetries})...`);
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

    // Fetch full lead details
    const fullLeadRes = await callToolWithRetry('get_lead', { lead_id: leadId });
    const fullLead = fullLeadRes && fullLeadRes.result && fullLeadRes.result.structuredContent ? fullLeadRes.result.structuredContent.lead : null;

    if (!fullLead) {
      console.error(`Could not fetch details for lead ${leadId}`);
      await sleep(1000);
      continue;
    }

    const fields = fullLead.fields || [];
    const cfField = fields.find(f => f.var_name === 'cf_41795');
    const sysField = fields.find(f => f.var_name === 'source_id');

    const cfVal = cfField && cfField.value ? (cfField.value.name || cfField.value) : null;
    const currentSysVal = sysField && sysField.value ? (sysField.value.name || sysField.value) : null;

    let targetSourceName = null;

    // 1. From custom field cf_41795
    if (cfVal) {
      if (cfVal === 'Email-аутрич') {
        targetSourceName = SOURCE_NAMES.EMAIL;
      } else if (cfVal === 'Сайт') {
        targetSourceName = SOURCE_NAMES.SITE;
      } else if (cfVal === 'Рекомендация') {
        targetSourceName = SOURCE_NAMES.NETWORK;
      } else if (cfVal === 'Партнёры') {
        targetSourceName = SOURCE_NAMES.PARTNER;
      }
    }

    // 2. Check contacts for email
    if (!targetSourceName) {
      const contacts = fullLead.contacts || [];
      let hasContactEmail = false;

      for (const c of contacts) {
        if (c.emails && c.emails.length > 0) {
          hasContactEmail = true;
          break;
        }
      }

      // Check lead email field cf_42064
      const leadEmailField = fields.find(f => f.var_name === 'cf_42064');
      if (leadEmailField && leadEmailField.value && leadEmailField.value.includes('@')) {
        hasContactEmail = true;
      }

      if (hasContactEmail) {
        targetSourceName = SOURCE_NAMES.EMAIL;
      }
    }

    // 3. Check name patterns
    if (!targetSourceName) {
      const name = (fullLead.name || '').toLowerCase();
      if (name.startsWith('re:') || /@.*\.|\.ru>|\.com>|mail|email/.test(name)) {
        targetSourceName = SOURCE_NAMES.EMAIL;
      } else {
        targetSourceName = SOURCE_NAMES.SITE;
      }
    }

    // Check if update is needed
    if (currentSysVal === targetSourceName) {
      alreadySetCount++;
    } else {
      const updateRes = await callToolWithRetry('update_lead', {
        lead_id: leadId,
        fields: {
          source_id: targetSourceName // PASSING NAME STRING!
        }
      });
      if (updateRes && !updateRes.error) {
        updatedCount++;
      } else {
        console.error(`Failed to update lead ${leadId}:`, updateRes ? updateRes.error : 'null');
      }
      await sleep(350);
    }

    if ((i + 1) % 15 === 0 || i === allLeads.length - 1) {
      console.log(`Progress: ${i + 1}/${allLeads.length} evaluated (Updated: ${updatedCount}, Already matched: ${alreadySetCount})`);
    }

    await sleep(200);
  }

  console.log('\n=== FIX COMPLETED ===');
  console.log(`Total leads: ${allLeads.length}`);
  console.log(`Updated successfully: ${updatedCount}`);
  console.log(`Already set: ${alreadySetCount}`);
  console.log(`Skipped test leads: ${skippedTestCount}`);
}

main().catch(console.error);
