import urllib.request
import ssl
import json
import time

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

NEW_TOKEN = os.getenv("HUBSPOT_ACCESS_TOKEN", "YOUR_HUBSPOT_TOKEN")
headers = {'Authorization': f'Bearer {NEW_TOKEN}', 'Content-Type': 'application/json'}
OWNER_ID = '99659620' # Ulyana Kirpichnikova

STAGE_MAP = {
    '4324629204': 'appointmentscheduled', # Prospecting
    '4324629205': 'qualifiedtobuy',        # Initial Contact
    '4324629206': 'presentationscheduled', # Meeting
    '4324629207': 'decisionmakerboughtin', # Qualified Lead
    '4324629208': 'contractsent',          # Proposal Sent
    '4324629209': '4342570695',            # Negotiation
    'closedwon': 'closedwon',              # Closed Won
    'closedlost': 'closedlost'             # Closed Lost
}

def hubspot_post(url, data):
    req = urllib.request.Request(url, headers=headers, data=json.dumps(data).encode(), method='POST')
    try:
        with urllib.request.urlopen(req, context=ctx) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        print(f"Error POST {url}: {e.code} - {e.read().decode()[:200]}")
        return None

def main():
    with open('/Users/ulyana/CALL TALK/HUBSPOT_BACKUP_2026-09-23.json', 'r', encoding='utf-8') as f:
        backup = json.load(f)

    print("--- 1. Migrating Companies ---")
    company_id_map = {}
    for comp in backup.get('companies', []):
        old_id = comp['id']
        props = comp.get('properties', {}).copy()
        # Clean read-only props
        for ro in ['hs_object_id', 'createdate', 'hs_lastmodifieddate']:
            props.pop(ro, None)
        props['hubspot_owner_id'] = OWNER_ID
        res = hubspot_post('https://api.hubapi.com/crm/v3/objects/companies', {'properties': props})
        if res:
            company_id_map[old_id] = res['id']
            print(f"Company {props.get('name')} migrated -> {res['id']}")
        time.sleep(0.1)

    print(f"Companies migrated: {len(company_id_map)}/{len(backup.get('companies', []))}")

    print("--- 2. Migrating Contacts ---")
    contact_id_map = {}
    for cont in backup.get('contacts', []):
        old_id = cont['id']
        props = cont.get('properties', {}).copy()
        for ro in ['hs_object_id', 'createdate', 'hs_lastmodifieddate']:
            props.pop(ro, None)
        props['hubspot_owner_id'] = OWNER_ID
        res = hubspot_post('https://api.hubapi.com/crm/v3/objects/contacts', {'properties': props})
        if res:
            contact_id_map[old_id] = res['id']
            print(f"Contact {props.get('firstname', '')} {props.get('lastname', '')} ({props.get('email', '')}) migrated -> {res['id']}")
            
            # Associate with company if old contact had it
            for assoc in cont.get('associations', {}).get('companies', {}).get('results', []):
                old_c_id = assoc['id']
                if old_c_id in company_id_map:
                    new_c_id = company_id_map[old_c_id]
                    # Assoc contact -> company
                    hubspot_post(f"https://api.hubapi.com/crm/v4/objects/contacts/{res['id']}/associations/companies/{new_c_id}",
                                 [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 1}])
        time.sleep(0.1)

    print(f"Contacts migrated: {len(contact_id_map)}/{len(backup.get('contacts', []))}")

    print("--- 3. Migrating Deals ---")
    deal_id_map = {}
    for deal in backup.get('deals', []):
        old_id = deal['id']
        props = deal.get('properties', {}).copy()
        for ro in ['hs_object_id', 'createdate', 'hs_lastmodifieddate']:
            props.pop(ro, None)
        props['hubspot_owner_id'] = OWNER_ID
        
        # Map stage
        old_stage = props.get('dealstage')
        if old_stage in STAGE_MAP:
            props['dealstage'] = STAGE_MAP[old_stage]

        # Handle closed lost reason
        clr = props.get('closed_lost_reason')
        if clr:
            props['prichina_proigrysha'] = clr

        res = hubspot_post('https://api.hubapi.com/crm/v3/objects/deals', {'properties': props})
        if res:
            deal_id_map[old_id] = res['id']
            new_deal_id = res['id']
            print(f"Deal {props.get('dealname')} ({props.get('dealstage')}) migrated -> {new_deal_id}")

            # Associate Deal -> Company
            for assoc in deal.get('associations', {}).get('companies', {}).get('results', []):
                old_c_id = assoc['id']
                if old_c_id in company_id_map:
                    new_c_id = company_id_map[old_c_id]
                    hubspot_post(f"https://api.hubapi.com/crm/v4/objects/deals/{new_deal_id}/associations/companies/{new_c_id}",
                                 [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 5}])

            # Associate Deal -> Contact
            for assoc in deal.get('associations', {}).get('contacts', {}).get('results', []):
                old_cnt_id = assoc['id']
                if old_cnt_id in contact_id_map:
                    new_cnt_id = contact_id_map[old_cnt_id]
                    hubspot_post(f"https://api.hubapi.com/crm/v4/objects/deals/{new_deal_id}/associations/contacts/{new_cnt_id}",
                                 [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 3}])
        time.sleep(0.1)

    print(f"Deals migrated: {len(deal_id_map)}/{len(backup.get('deals', []))}")

    print("--- 4. Migrating Tasks ---")
    tasks_count = 0
    for task in backup.get('tasks', []):
        props = task.get('properties', {}).copy()
        for ro in ['hs_object_id', 'createdate', 'hs_lastmodifieddate']:
            props.pop(ro, None)
        props['hubspot_owner_id'] = OWNER_ID
        res = hubspot_post('https://api.hubapi.com/crm/v3/objects/tasks', {'properties': props})
        if res:
            new_t_id = res['id']
            tasks_count += 1
            # Associations
            for assoc in task.get('associations', {}).get('deals', {}).get('results', []):
                if assoc['id'] in deal_id_map:
                    hubspot_post(f"https://api.hubapi.com/crm/v4/objects/tasks/{new_t_id}/associations/deals/{deal_id_map[assoc['id']]}",
                                 [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 216}])
            for assoc in task.get('associations', {}).get('contacts', {}).get('results', []):
                if assoc['id'] in contact_id_map:
                    hubspot_post(f"https://api.hubapi.com/crm/v4/objects/tasks/{new_t_id}/associations/contacts/{contact_id_map[assoc['id']]}",
                                 [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 204}])
        time.sleep(0.08)

    print(f"Tasks migrated: {tasks_count}/{len(backup.get('tasks', []))}")

    print("--- 5. Migrating Notes ---")
    notes_count = 0
    for note in backup.get('notes', []):
        props = note.get('properties', {}).copy()
        for ro in ['hs_object_id', 'createdate', 'hs_lastmodifieddate']:
            props.pop(ro, None)
        props['hubspot_owner_id'] = OWNER_ID
        res = hubspot_post('https://api.hubapi.com/crm/v3/objects/notes', {'properties': props})
        if res:
            new_n_id = res['id']
            notes_count += 1
            # Associations
            for assoc in note.get('associations', {}).get('deals', {}).get('results', []):
                if assoc['id'] in deal_id_map:
                    hubspot_post(f"https://api.hubapi.com/crm/v4/objects/notes/{new_n_id}/associations/deals/{deal_id_map[assoc['id']]}",
                                 [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 214}])
            for assoc in note.get('associations', {}).get('contacts', {}).get('results', []):
                if assoc['id'] in contact_id_map:
                    hubspot_post(f"https://api.hubapi.com/crm/v4/objects/notes/{new_n_id}/associations/contacts/{contact_id_map[assoc['id']]}",
                                 [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 202}])
        time.sleep(0.08)

    print(f"Notes migrated: {notes_count}/{len(backup.get('notes', []))}")
    print("=== MIGRATION COMPLETE! ===")

if __name__ == '__main__':
    main()
