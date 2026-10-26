const endpoint = 'https://mcp.okocrm.com/crm';
const token = 'OKOCRM_TOKEN_PLACEHOLDER';

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
  console.log('Fetching all leads across pipelines 30944 and 30895...');
  let allLeads = [];

  for (const pipeline_id of [30944, 30895]) {
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

  console.log(`Total leads fetched: ${allLeads.length}`);

  let updatedLeadsCount = 0;
  let updatedContactsResponsibleCount = 0;

  for (let i = 0; i < allLeads.length; i++) {
    const lead = allLeads[i];
    if (lead.name && lead.name.includes('test')) continue;

    const leadId = lead.id;
    const leadRespId = lead.responsible ? lead.responsible.id : null;

    let leadTg = null;
    let leadEmail = null;
    let leadPhone = null;

    // Check contact(s)
    if (lead.contacts && lead.contacts.length > 0) {
      for (const c of lead.contacts) {
        const fullC = await callTool('get_contact', { contact_id: c.id });
        const cData = fullC.result && fullC.result.structuredContent ? fullC.result.structuredContent.contact : fullC;

        if (cData.phones && cData.phones.length > 0 && !leadPhone) {
          leadPhone = cData.phones[0];
        }
        if (cData.emails && cData.emails.length > 0 && !leadEmail) {
          leadEmail = cData.emails[0];
        }

        const tgField = (cData.fields || []).find(f => f.name && f.name.includes('Telegram'));
        if (tgField && tgField.value && !leadTg) {
          leadTg = tgField.value;
        }

        // Align contact responsible with lead responsible if different
        if (leadRespId && cData.responsible && cData.responsible.id !== leadRespId) {
          try {
            await callTool('update_contact', {
              contact_id: c.id,
              responsible_id: leadRespId
            });
            updatedContactsResponsibleCount++;
          } catch(e) {
            console.error('Failed to update contact responsible:', e.message);
          }
        }
      }
    }

    // Fallback: extract from lead name if still missing
    const name = lead.name || '';
    if (!leadTg) {
      const matchTg = name.match(/@([a-zA-Z0-9_]{4,})/);
      if (matchTg) leadTg = '@' + matchTg[1];
    }
    if (!leadEmail) {
      const matchEmail = name.match(/([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})/);
      if (matchEmail) leadEmail = matchEmail[1];
    }
    if (!leadPhone) {
      const matchPhone = name.match(/(\+?7[\d\s\-()]{10,})/);
      if (matchPhone) leadPhone = matchPhone[1].replace(/[^\d+]/g, '');
    }

    // Now populate custom fields in lead: cf_42063 (TG), cf_42064 (Email), cf_42065 (Phone)
    const fieldsToUpdate = {};
    if (leadTg) fieldsToUpdate['cf_42063'] = leadTg;
    if (leadEmail) fieldsToUpdate['cf_42064'] = leadEmail;
    if (leadPhone) fieldsToUpdate['cf_42065'] = leadPhone;

    if (Object.keys(fieldsToUpdate).length > 0) {
      try {
        await callTool('update_lead', {
          lead_id: leadId,
          fields: fieldsToUpdate
        });
        updatedLeadsCount++;
      } catch(e) {
        console.error(`Error updating lead ${leadId}:`, e.message);
      }
    }

    if ((i + 1) % 15 === 0 || i === allLeads.length - 1) {
      console.log(`Processed ${i + 1}/${allLeads.length} leads... (Updated leads: ${updatedLeadsCount}, Contact rights synced: ${updatedContactsResponsibleCount})`);
    }

    await sleep(80);
  }

  console.log(`\nALL DONE!`);
  console.log(`Updated ${updatedLeadsCount} deals with direct phone/email/tg fields.`);
  console.log(`Synced ${updatedContactsResponsibleCount} contacts permissions so managers can view them.`);
}

main().catch(console.error);
