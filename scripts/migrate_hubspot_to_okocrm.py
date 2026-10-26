#!/usr/bin/env python3
"""
Full Autonomous Migration Script: HubSpot -> OkoCRM
Call Talk CRM Data Migration
"""
import urllib.request
import json
import ssl
import time
import os
import re

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

OKOCRM_URL = 'https://mcp.okocrm.com/crm'
OKOCRM_TOKEN = 'OKOCRM_TOKEN_PLACEHOLDER'

# Users Mapping: HubSpot Owner -> OkoCRM User ID
USER_MAP = {
    '99659620': 28415,   # Ulyana Kirpichnikova -> Uliana K (28415)
    '169030152': 28418   # Andrey -> andrey.s@calltalk.ru (28418)
}
DEFAULT_RESPONSIBLE = 28415

# OkoCRM Pipeline & Stages
PIPELINE_ID = 30895 # B2B лидогенерация
STAGE_NEW = 148040          # Новый лид
STAGE_CONTACT = 148041      # Первичный контакт
STAGE_MQL = 148042          # Первичная квалификация проведена / MQL
STAGE_MEETING = 148043      # Встреча проведена / Квалифицирован
STAGE_PROPOSAL = 148044     # КП отправлено
STAGE_CONTRACT = 148045     # Договор на подписи
STAGE_INVOICE = 148046      # Счёт направлен
STAGE_WON = 148038          # Успешно реализовано (won)
STAGE_LOST = 148039         # Закрыто и не реализовано (lost)

STAGE_MAP = {
    'appointmentscheduled': STAGE_NEW,
    'qualifiedtobuy': STAGE_CONTACT,
    'presentationscheduled': STAGE_MEETING,
    'decisionmakerboughtin': STAGE_MEETING,
    'contractsent': STAGE_PROPOSAL,
    '4364735215': STAGE_CONTRACT,
    '4342570695': STAGE_CONTRACT,
    'closedwon': STAGE_WON,
    'closedlost': STAGE_LOST
}

# OkoCRM Custom Field IDs
CF_COMPANY_WEBSITE = 'cf_41805'  # URL
CF_CONTACT_JOB = 'cf_41803'      # Должность ЛПР
CF_CONTACT_TG = 'cf_41804'       # Telegram (@username)
CF_LEAD_FREE = 'cf_41850'        # Свободный лид (флаг "Да")
CF_LEAD_SOURCE = 'cf_41795'      # Источник лида (select)
CF_LEAD_STATUS = 'cf_41802'      # Статус сделки (select)

def clean_html(raw_html):
    if not raw_html:
        return ""
    # Replace <br> and </p> with newlines
    text = re.sub(r'<br\s*/?>', '\n', raw_html, flags=re.IGNORECASE)
    text = re.sub(r'</p>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</li>', '\n', text, flags=re.IGNORECASE)
    # Remove remaining HTML tags
    clean = re.sub(r'<.*?>', '', text)
    return clean.strip()

def oko_mcp(tool_name, arguments, retries=3):
    payload = {
        "jsonrpc": "2.0",
        "id": int(time.time() * 1000) % 1000000,
        "method": "tools/call",
        "params": {
            "name": tool_name,
            "arguments": arguments
        }
    }
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(OKOCRM_URL, data=data, headers={
        'Authorization': f'Bearer {OKOCRM_TOKEN}',
        'Content-Type': 'application/json'
    })

    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
                res = json.loads(resp.read().decode('utf-8'))
                if res.get('error'):
                    print(f"[{tool_name}] RPC Error: {res['error']}")
                    return None
                result = res.get('result', {})
                if result.get('isError'):
                    content = result.get('content', [{}])[0].get('text', '')
                    print(f"[{tool_name}] Business Error: {content}")
                    return None
                text = result.get('content', [{}])[0].get('text', '')
                try:
                    return json.loads(text)
                except Exception:
                    return text
        except Exception as e:
            time.sleep(0.5 * (attempt + 1))
            if attempt == retries - 1:
                print(f"[{tool_name}] Network Error: {e}")
                return None
    return None

def main():
    export_path = '/Users/ulyana/CALL TALK/scratch/hubspot_live_export.json'
    if not os.path.exists(export_path):
        print(f"Error: {export_path} not found!")
        return

    with open(export_path, 'r', encoding='utf-8') as f:
        export_data = json.load(f)

    companies = export_data.get('companies', [])
    contacts = export_data.get('contacts', [])
    deals = export_data.get('deals', [])
    notes = export_data.get('notes', [])
    tasks = export_data.get('tasks', [])
    associations = export_data.get('associations', {})

    deal_to_company = associations.get('deal_to_company', {})
    deal_to_contact = associations.get('deal_to_contact', {})
    contact_to_company = associations.get('contact_to_company', {})
    note_to_deal = associations.get('note_to_deal', {})
    note_to_contact = associations.get('note_to_contact', {})
    task_to_deal = associations.get('task_to_deal', {})
    task_to_contact = associations.get('task_to_contact', {})

    print(f"Loaded: {len(companies)} companies, {len(contacts)} contacts, {len(deals)} deals, {len(notes)} notes, {len(tasks)} tasks")

    # Check loss reasons in OkoCRM
    loss_reasons_res = oko_mcp('list_loss_reasons', {})
    loss_reasons = loss_reasons_res.get('loss_reasons', []) if isinstance(loss_reasons_res, dict) else []
    default_loss_reason_id = loss_reasons[0]['id'] if loss_reasons else None
    print(f"OkoCRM Loss Reasons count: {len(loss_reasons)} (default ID: {default_loss_reason_id})")

    # -------------------------------------------------------------
    # STEP 1: MIGRATE COMPANIES
    # -------------------------------------------------------------
    print("\n=== STEP 1: Migrating Companies ===")
    company_map = {} # hubspot_company_id -> oko_company_id

    for i, comp in enumerate(companies, 1):
        hs_id = comp['id']
        props = comp.get('properties', {})
        name = props.get('name') or props.get('domain') or f"Компания #{hs_id}"
        domain = props.get('domain') or props.get('website') or ""
        phone = props.get('phone') or ""
        owner_id = props.get('hubspot_owner_id')
        resp_id = USER_MAP.get(owner_id, DEFAULT_RESPONSIBLE)

        args = {
            "name": name,
            "responsible_id": resp_id,
            "fields": {}
        }
        if domain:
            args["fields"][CF_COMPANY_WEBSITE] = domain if domain.startswith('http') else f"https://{domain}"
        if phone:
            args["phones"] = [phone]

        res = oko_mcp('create_company', args)
        if res and isinstance(res, dict) and 'company' in res:
            oko_id = res['company']['id']
            company_map[str(hs_id)] = oko_id
            print(f"[{i}/{len(companies)}] Company: {name} -> OkoCRM ID {oko_id}")
        else:
            print(f"[{i}/{len(companies)}] Company FAILED: {name}")
        time.sleep(0.1)

    print(f"Companies migrated: {len(company_map)}/{len(companies)}")

    # -------------------------------------------------------------
    # STEP 2: MIGRATE CONTACTS
    # -------------------------------------------------------------
    print("\n=== STEP 2: Migrating Contacts ===")
    contact_map = {} # hubspot_contact_id -> oko_contact_id

    for i, cont in enumerate(contacts, 1):
        hs_id = cont['id']
        props = cont.get('properties', {})
        first = props.get('firstname') or ""
        last = props.get('lastname') or ""
        name = f"{first} {last}".strip() or props.get('email') or f"Контакт #{hs_id}"
        email = props.get('email') or ""
        phone = props.get('phone') or ""
        telegram = props.get('telegram') or ""
        jobtitle = props.get('jobtitle') or ""
        owner_id = props.get('hubspot_owner_id')
        resp_id = USER_MAP.get(owner_id, DEFAULT_RESPONSIBLE)

        # Find linked company
        linked_comp_ids = []
        hs_comp_ids = contact_to_company.get(str(hs_id), [])
        for cid in hs_comp_ids:
            if str(cid) in company_map:
                linked_comp_ids.append(company_map[str(cid)])

        args = {
            "name": name,
            "responsible_id": resp_id,
            "fields": {}
        }
        if email:
            args["emails"] = [email]
        if phone:
            args["phones"] = [phone]
        if telegram:
            args["fields"][CF_CONTACT_TG] = telegram if telegram.startswith('@') else f"@{telegram}"
        if jobtitle:
            args["fields"][CF_CONTACT_JOB] = jobtitle
        if linked_comp_ids:
            args["company_ids"] = linked_comp_ids

        res = oko_mcp('create_contact', args)
        if res and isinstance(res, dict) and 'contact' in res:
            oko_id = res['contact']['id']
            contact_map[str(hs_id)] = oko_id
            print(f"[{i}/{len(contacts)}] Contact: {name} -> OkoCRM ID {oko_id}")
        else:
            print(f"[{i}/{len(contacts)}] Contact FAILED: {name}")
        time.sleep(0.1)

    print(f"Contacts migrated: {len(contact_map)}/{len(contacts)}")

    # -------------------------------------------------------------
    # STEP 3: MIGRATE DEALS
    # -------------------------------------------------------------
    print("\n=== STEP 3: Migrating Deals ===")
    deal_map = {} # hubspot_deal_id -> oko_deal_id
    free_deals_count = 0

    for i, deal in enumerate(deals, 1):
        hs_id = deal['id']
        props = deal.get('properties', {})
        name = props.get('dealname') or f"Сделка #{hs_id}"
        amount_str = props.get('amount')
        budget = float(amount_str) if amount_str and amount_str.replace('.', '', 1).isdigit() else None
        owner_id = props.get('hubspot_owner_id')
        stage_raw = props.get('dealstage', '')

        # Associations
        linked_contacts = []
        for cid in deal_to_contact.get(str(hs_id), []):
            if str(cid) in contact_map:
                linked_contacts.append(contact_map[str(cid)])

        linked_companies = []
        for cid in deal_to_company.get(str(hs_id), []):
            if str(cid) in company_map:
                linked_companies.append(company_map[str(cid)])

        # Business Rule: Deals on Ulyana before Meeting stage -> FREE LEADS
        is_free_lead = (owner_id == '99659620' and stage_raw in ['appointmentscheduled', 'qualifiedtobuy'])
        
        target_stage = STAGE_MAP.get(stage_raw, STAGE_NEW)
        deal_name = name
        deal_fields = {}
        deal_resp_id = USER_MAP.get(owner_id, DEFAULT_RESPONSIBLE)

        if is_free_lead:
            target_stage = STAGE_NEW
            deal_name = f"[Свободный лид] {name}"
            deal_fields[CF_LEAD_FREE] = "Да"
            deal_resp_id = DEFAULT_RESPONSIBLE
            free_deals_count += 1
        elif stage_raw == 'closedlost':
            if default_loss_reason_id:
                target_stage = STAGE_LOST
            else:
                # If no loss reason configured yet, mark as archive in title and put on NEW or last regular stage
                deal_name = f"[Архив: Отказ] {name}"
                target_stage = STAGE_NEW
                deal_fields[CF_LEAD_STATUS] = 77845 # Отложенная

        args = {
            "name": deal_name,
            "pipeline_id": PIPELINE_ID,
            "stage_id": target_stage,
            "responsible_id": deal_resp_id,
            "fields": deal_fields
        }
        if budget:
            args["budget"] = budget
        if linked_contacts:
            args["contact_ids"] = linked_contacts
        if linked_companies:
            args["company_ids"] = linked_companies
        if target_stage == STAGE_LOST and default_loss_reason_id:
            args["loss_reason_id"] = default_loss_reason_id

        res = oko_mcp('create_lead', args)
        if res and isinstance(res, dict) and 'lead' in res:
            oko_id = res['lead']['id']
            deal_map[str(hs_id)] = oko_id
            print(f"[{i}/{len(deals)}] Deal: {deal_name} (Stage: {target_stage}) -> OkoCRM ID {oko_id}")
        else:
            print(f"[{i}/{len(deals)}] Deal FAILED: {deal_name}")
        time.sleep(0.12)

    print(f"Deals migrated: {len(deal_map)}/{len(deals)} (Свободных лидов: {free_deals_count})")

    # -------------------------------------------------------------
    # STEP 4: MIGRATE NOTES
    # -------------------------------------------------------------
    print("\n=== STEP 4: Migrating Notes ===")
    notes_added = 0
    for i, note in enumerate(notes, 1):
        hs_id = note['id']
        props = note.get('properties', {})
        body = clean_html(props.get('hs_note_body', ''))
        if not body:
            continue

        # Check association to deal first, then contact
        target_entity = None
        target_id = None

        hs_deals = note_to_deal.get(str(hs_id), [])
        for d in hs_deals:
            if str(d) in deal_map:
                target_entity = 'lead'
                target_id = deal_map[str(d)]
                break

        if not target_id:
            hs_conts = note_to_contact.get(str(hs_id), [])
            for c in hs_conts:
                if str(c) in contact_map:
                    target_entity = 'contact'
                    target_id = contact_map[str(c)]
                    break

        if target_entity and target_id:
            res = oko_mcp('add_note', {
                "entity_type": target_entity,
                "entity_id": target_id,
                "text": body[:4500]
            })
            if res:
                notes_added += 1
            time.sleep(0.08)

    print(f"Notes migrated: {notes_added}/{len(notes)}")

    # -------------------------------------------------------------
    # STEP 5: MIGRATE OPEN TASKS
    # -------------------------------------------------------------
    print("\n=== STEP 5: Migrating Tasks ===")
    tasks_added = 0
    for i, task in enumerate(tasks, 1):
        hs_id = task['id']
        props = task.get('properties', {})
        status = props.get('hs_task_status', '')
        if status == 'COMPLETED':
            continue # Skip already completed tasks

        subject = props.get('hs_task_subject', '')
        body = clean_html(props.get('hs_task_body', ''))
        full_text = f"{subject}\n\n{body}".strip() if body else subject
        if not full_text:
            continue

        due_date = props.get('hs_timestamp')
        if due_date:
            # Format ISO date: e.g. 2026-10-15T12:00:00Z -> 2026-10-15 15:00
            due_clean = due_date[:16].replace('T', ' ')
        else:
            due_clean = time.strftime('%Y-%m-%d %H:%M')

        owner_id = props.get('hubspot_owner_id')
        executor_id = USER_MAP.get(owner_id, DEFAULT_RESPONSIBLE)

        target_entity = None
        target_id = None

        for d in task_to_deal.get(str(hs_id), []):
            if str(d) in deal_map:
                target_entity = 'lead'
                target_id = deal_map[str(d)]
                break

        if not target_id:
            for c in task_to_contact.get(str(hs_id), []):
                if str(c) in contact_map:
                    target_entity = 'contact'
                    target_id = contact_map[str(c)]
                    break

        args = {
            "text": full_text[:2000],
            "executor_id": executor_id,
            "date_start": due_clean
        }
        if target_entity and target_id:
            args["entity_type"] = target_entity
            args["entity_id"] = target_id

        res = oko_mcp('create_task', args)
        if res:
            tasks_added += 1
        time.sleep(0.08)

    print(f"Open tasks migrated: {tasks_added}")

    # -------------------------------------------------------------
    # SUMMARY REPORT
    # -------------------------------------------------------------
    report = {
        "migrated_at": time.strftime('%Y-%m-%d %H:%M:%S'),
        "companies_total": len(companies),
        "companies_migrated": len(company_map),
        "contacts_total": len(contacts),
        "contacts_migrated": len(contact_map),
        "deals_total": len(deals),
        "deals_migrated": len(deal_map),
        "free_deals_count": free_deals_count,
        "notes_migrated": notes_added,
        "tasks_migrated": tasks_added,
        "deal_id_mapping": deal_map
    }

    report_file = '/Users/ulyana/CALL TALK/scratch/migration_final_report.json'
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print("\n==========================================")
    print("MIGRATION FINISHED SUCCESSFULLY!")
    print(f"Report saved to: {report_file}")
    print("==========================================")

if __name__ == '__main__':
    main()
