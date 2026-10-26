import urllib.request
import ssl
import json
import time

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

OLD_TOKEN = 'DISABLED_OLD_TOKEN'
NEW_TOKEN = os.getenv("HUBSPOT_ACCESS_TOKEN", "YOUR_HUBSPOT_TOKEN")

old_headers = {'Authorization': f'Bearer {OLD_TOKEN}', 'Content-Type': 'application/json'}
new_headers = {'Authorization': f'Bearer {NEW_TOKEN}', 'Content-Type': 'application/json'}

def get_all(url, token):
    results = []
    after = None
    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
    while True:
        p_url = url + ('&' if '?' in url else '?') + 'limit=100'
        if after:
            p_url += f'&after={after}'
        req = urllib.request.Request(p_url, headers=headers)
        with urllib.request.urlopen(req, context=ctx) as resp:
            data = json.loads(resp.read().decode())
            results.extend(data.get('results', []))
            if 'paging' in data and 'next' in data['paging']:
                after = data['paging']['next']['after']
            else:
                break
    return results

def put_assoc(from_obj, from_id, to_obj, to_id, type_id):
    url = f"https://api.hubapi.com/crm/v4/objects/{from_obj}/{from_id}/associations/{to_obj}/{to_id}"
    body = json.dumps([{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": type_id}]).encode()
    req = urllib.request.Request(url, headers=new_headers, data=body, method='PUT')
    try:
        with urllib.request.urlopen(req, context=ctx) as resp:
            return True
    except urllib.error.HTTPError as e:
        print(f"Error PUT assoc {from_obj}/{from_id} -> {to_obj}/{to_id}: {e.code} {e.read().decode()[:150]}")
        return False

def main():
    print("--- 1. Fetching all objects from OLD portal with associations ---")
    old_companies = get_all('https://api.hubapi.com/crm/v3/objects/companies', OLD_TOKEN)
    old_contacts = get_all('https://api.hubapi.com/crm/v3/objects/contacts?associations=companies', OLD_TOKEN)
    old_deals = get_all('https://api.hubapi.com/crm/v3/objects/deals?associations=contacts,companies', OLD_TOKEN)
    old_tasks = get_all('https://api.hubapi.com/crm/v3/objects/tasks?associations=deals,contacts', OLD_TOKEN)
    old_notes = get_all('https://api.hubapi.com/crm/v3/objects/notes?associations=deals,contacts', OLD_TOKEN)

    print(f"Old objects: {len(old_companies)} comps, {len(old_contacts)} conts, {len(old_deals)} deals, {len(old_tasks)} tasks, {len(old_notes)} notes")

    print("--- 2. Fetching all objects from NEW portal to map IDs ---")
    new_companies = get_all('https://api.hubapi.com/crm/v3/objects/companies', NEW_TOKEN)
    new_contacts = get_all('https://api.hubapi.com/crm/v3/objects/contacts', NEW_TOKEN)
    new_deals = get_all('https://api.hubapi.com/crm/v3/objects/deals', NEW_TOKEN)
    new_tasks = get_all('https://api.hubapi.com/crm/v3/objects/tasks', NEW_TOKEN)
    new_notes = get_all('https://api.hubapi.com/crm/v3/objects/notes', NEW_TOKEN)

    print(f"New objects: {len(new_companies)} comps, {len(new_contacts)} conts, {len(new_deals)} deals, {len(new_tasks)} tasks, {len(new_notes)} notes")

    # Mapping dictionaries
    # Companies mapped by name
    comp_map = {}
    new_comp_by_name = {c['properties'].get('name'): c['id'] for c in new_companies if c['properties'].get('name')}
    for c in old_companies:
        name = c['properties'].get('name')
        if name and name in new_comp_by_name:
            comp_map[c['id']] = new_comp_by_name[name]

    # Contacts mapped by email or firstname+lastname
    cont_map = {}
    new_cont_by_email = {c['properties'].get('email', '').lower(): c['id'] for c in new_contacts if c['properties'].get('email')}
    new_cont_by_name = {f"{c['properties'].get('firstname', '')} {c['properties'].get('lastname', '')}".strip(): c['id'] for c in new_contacts}
    for c in old_contacts:
        email = (c['properties'].get('email') or '').lower()
        full_name = f"{c['properties'].get('firstname', '')} {c['properties'].get('lastname', '')}".strip()
        if email and email in new_cont_by_email:
            cont_map[c['id']] = new_cont_by_email[email]
        elif full_name and full_name in new_cont_by_name:
            cont_map[c['id']] = new_cont_by_name[full_name]

    # Deals mapped by dealname
    deal_map = {}
    new_deal_by_name = {d['properties'].get('dealname'): d['id'] for d in new_deals if d['properties'].get('dealname')}
    for d in old_deals:
        dname = d['properties'].get('dealname')
        if dname and dname in new_deal_by_name:
            deal_map[d['id']] = new_deal_by_name[dname]

    # Tasks mapped by hs_task_body + hs_timestamp + hs_task_subject
    task_map = {}
    new_tasks_list = list(new_tasks)
    # Match tasks sequentially by body/subject
    for ot in old_tasks:
        ot_body = ot['properties'].get('hs_task_body') or ''
        ot_subj = ot['properties'].get('hs_task_subject') or ''
        for nt in new_tasks_list:
            nt_body = nt['properties'].get('hs_task_body') or ''
            nt_subj = nt['properties'].get('hs_task_subject') or ''
            if (ot_body and ot_body == nt_body) or (ot_subj and ot_subj == nt_subj):
                task_map[ot['id']] = nt['id']
                break

    print(f"Mapped: {len(comp_map)} comps, {len(cont_map)} conts, {len(deal_map)} deals, {len(task_map)} tasks")

    # --- 3. Link Contacts to Companies (typeId: 1) ---
    print("--- 3. Linking Contacts to Companies ---")
    c_to_co_count = 0
    for c in old_contacts:
        old_c_id = c['id']
        if old_c_id not in cont_map:
            continue
        new_c_id = cont_map[old_c_id]
        for assoc in c.get('associations', {}).get('companies', {}).get('results', []):
            old_co_id = assoc['id']
            if old_co_id in comp_map:
                new_co_id = comp_map[old_co_id]
                if put_assoc('contacts', new_c_id, 'companies', new_co_id, 1):
                    c_to_co_count += 1
        time.sleep(0.05)
    print(f"Contacts -> Companies linked: {c_to_co_count}")

    # --- 4. Link Deals to Companies (typeId: 5) & Deals to Contacts (typeId: 3) ---
    print("--- 4. Linking Deals to Companies & Contacts ---")
    d_to_co_count = 0
    d_to_c_count = 0
    for d in old_deals:
        old_d_id = d['id']
        if old_d_id not in deal_map:
            continue
        new_d_id = deal_map[old_d_id]
        # To companies
        for assoc in d.get('associations', {}).get('companies', {}).get('results', []):
            old_co_id = assoc['id']
            if old_co_id in comp_map:
                new_co_id = comp_map[old_co_id]
                if put_assoc('deals', new_d_id, 'companies', new_co_id, 5):
                    d_to_co_count += 1
        # To contacts
        for assoc in d.get('associations', {}).get('contacts', {}).get('results', []):
            old_cnt_id = assoc['id']
            if old_cnt_id in cont_map:
                new_cnt_id = cont_map[old_cnt_id]
                if put_assoc('deals', new_d_id, 'contacts', new_cnt_id, 3):
                    d_to_c_count += 1
        time.sleep(0.05)
    print(f"Deals -> Companies linked: {d_to_co_count}, Deals -> Contacts linked: {d_to_c_count}")

    # --- 5. Link Tasks to Deals (typeId: 216) & Tasks to Contacts (typeId: 204) ---
    print("--- 5. Linking Tasks to Deals & Contacts ---")
    t_to_d_count = 0
    t_to_c_count = 0
    for t in old_tasks:
        old_t_id = t['id']
        if old_t_id not in task_map:
            continue
        new_t_id = task_map[old_t_id]
        # To deals
        for assoc in t.get('associations', {}).get('deals', {}).get('results', []):
            old_d_id = assoc['id']
            if old_d_id in deal_map:
                new_d_id = deal_map[old_d_id]
                if put_assoc('tasks', new_t_id, 'deals', new_d_id, 216):
                    t_to_d_count += 1
        # To contacts
        for assoc in t.get('associations', {}).get('contacts', {}).get('results', []):
            old_cnt_id = assoc['id']
            if old_cnt_id in cont_map:
                new_cnt_id = cont_map[old_cnt_id]
                if put_assoc('tasks', new_t_id, 'contacts', new_cnt_id, 204):
                    t_to_c_count += 1
        time.sleep(0.05)
    print(f"Tasks -> Deals linked: {t_to_d_count}, Tasks -> Contacts linked: {t_to_c_count}")

    print("=== ALL ASSOCIATIONS LINKED SUCCESSFULLY! ===")

if __name__ == '__main__':
    main()
