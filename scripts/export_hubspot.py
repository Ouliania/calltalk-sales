#!/usr/bin/env python3
"""
Full live exporter for HubSpot CRM (Portal 247498625)
"""
import urllib.request
import json
import ssl
import time
import os

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

def _get_hubspot_token():
    t = os.getenv("HUBSPOT_ACCESS_TOKEN")
    if t:
        return t
    p = Path(__file__).resolve().parent.parent / ".env"
    if p.exists():
        for line in p.read_text().splitlines():
            if line.startswith("HUBSPOT_ACCESS_TOKEN="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""

TOKEN = _get_hubspot_token()
HEADERS = {
    'Authorization': f'Bearer {TOKEN}',
    'Content-Type': 'application/json'
}

def hubspot_get(endpoint):
    url = f"https://api.hubapi.com{endpoint}"
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, context=ctx) as resp:
        return json.loads(resp.read().decode())

def get_all_objects(obj_type, properties=None):
    results = []
    after = None
    props_str = f"&properties={','.join(properties)}" if properties else ""
    while True:
        endpoint = f"/crm/v3/objects/{obj_type}?limit=100{props_str}"
        if after:
            endpoint += f"&after={after}"
        try:
            data = hubspot_get(endpoint)
            results.extend(data.get('results', []))
            after = data.get('paging', {}).get('next', {}).get('after')
            if not after:
                break
            time.sleep(0.05)
        except Exception as e:
            print(f"Error fetching {obj_type}: {e}")
            break
    print(f"Fetched {len(results)} {obj_type}")
    return results

def get_associations(from_type, to_type, object_ids):
    # Fetch batch associations
    associations = {}
    chunk_size = 100
    for i in range(0, len(object_ids), chunk_size):
        chunk = object_ids[i:i + chunk_size]
        payload = {"inputs": [{"id": str(oid)} for oid in chunk]}
        url = f"https://api.hubapi.com/crm/v4/associations/{from_type}/{to_type}/batch/read"
        req = urllib.request.Request(url, headers=HEADERS, data=json.dumps(payload).encode(), method='POST')
        try:
            with urllib.request.urlopen(req, context=ctx) as resp:
                data = json.loads(resp.read().decode())
                for item in data.get('results', []):
                    from_id = item['from']['id']
                    to_ids = [to['toObjectId'] for to in item.get('to', [])]
                    associations[from_id] = to_ids
            time.sleep(0.05)
        except Exception as e:
            print(f"Error fetching associations {from_type}->{to_type}: {e}")
    return associations

def main():
    print("=== Starting live export from HubSpot ===")
    
    # 1. Deals
    deal_props = ['dealname', 'dealstage', 'pipeline', 'amount', 'hubspot_owner_id', 
                  'tekegram', 'phone_number', 'website', 'where_lead_from', 
                  'pricing_model', 'pricing__bonus_terms', 'number_of_leads_promised', 
                  'campaign_start_date', 'campaign_end_date', 'createdate', 'hs_lastmodifieddate']
    deals = get_all_objects('deals', deal_props)
    deal_ids = [d['id'] for d in deals]

    # 2. Contacts
    contact_props = ['firstname', 'lastname', 'email', 'phone', 'telegram', 
                     'jobtitle', 'role', 'lead_source', 'hubspot_owner_id', 'createdate']
    contacts = get_all_objects('contacts', contact_props)
    contact_ids = [c['id'] for c in contacts]

    # 3. Companies
    company_props = ['name', 'domain', 'website', 'phone', 'hubspot_owner_id', 'createdate']
    companies = get_all_objects('companies', company_props)
    company_ids = [c['id'] for c in companies]

    # 4. Notes
    note_props = ['hs_note_body', 'hs_timestamp', 'hubspot_owner_id']
    notes = get_all_objects('notes', note_props)
    note_ids = [n['id'] for n in notes]

    # 5. Tasks
    task_props = ['hs_task_subject', 'hs_task_body', 'hs_timestamp', 'hs_task_status', 
                  'hs_task_priority', 'hs_task_type', 'hubspot_owner_id']
    tasks = get_all_objects('tasks', task_props)
    task_ids = [t['id'] for t in tasks]

    # 6. Associations
    print("Fetching associations...")
    deal_to_company = get_associations('deals', 'companies', deal_ids)
    deal_to_contact = get_associations('deals', 'contacts', deal_ids)
    contact_to_company = get_associations('contacts', 'companies', contact_ids)
    note_to_deal = get_associations('notes', 'deals', note_ids)
    note_to_contact = get_associations('notes', 'contacts', note_ids)
    task_to_deal = get_associations('tasks', 'deals', task_ids)
    task_to_contact = get_associations('tasks', 'contacts', task_ids)

    export_data = {
        'exported_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        'companies': companies,
        'contacts': contacts,
        'deals': deals,
        'notes': notes,
        'tasks': tasks,
        'associations': {
            'deal_to_company': deal_to_company,
            'deal_to_contact': deal_to_contact,
            'contact_to_company': contact_to_company,
            'note_to_deal': note_to_deal,
            'note_to_contact': note_to_contact,
            'task_to_deal': task_to_deal,
            'task_to_contact': task_to_contact
        }
    }

    out_file = '/Users/ulyana/CALL TALK/scratch/hubspot_live_export.json'
    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump(export_data, f, ensure_ascii=False, indent=2)

    print(f"Export completed! Saved to {out_file}")
    print(f"Summary: {len(companies)} companies, {len(contacts)} contacts, {len(deals)} deals, {len(notes)} notes, {len(tasks)} tasks")

if __name__ == '__main__':
    main()
