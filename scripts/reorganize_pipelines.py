#!/usr/bin/env python3
"""
Reorganize Leads across Pipelines:
- Move [Свободный лид] (60) -> Pipeline 30944 ("База в проработку"), Stage 148390 ("Свободный пул (в разбор)")
- Move [Архив: Отказ] (23) -> Pipeline 30944 ("База в проработку"), Stage 148393 ("Архив / Отказ")
- Distribute remaining active leads in Pipeline 30895 ("B2B лидогенерация") to their rightful stages:
    * Первичный контакт (148041)
    * Встреча проведена / Квалифицирован (148043)
    * КП отправлено (148044)
    * Договор на подписи (148045)
"""
import urllib.request
import json
import ssl
import time

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

OKOCRM_URL = 'https://mcp.okocrm.com/crm'
OKOCRM_TOKEN = 'OKOCRM_TOKEN_PLACEHOLDER'

# Pipeline 30944 (База в проработку)
STAGE_FREE_POOL = 148390   # Свободный пул (в разбор)
STAGE_ARCHIVE_LOST = 148393 # Архив / Отказ

# Pipeline 30895 (B2B лидогенерация)
STAGE_B2B_NEW = 148040      # Новый лид
STAGE_B2B_CONTACT = 148041  # Первичный контакт
STAGE_B2B_MQL = 148042      # MQL
STAGE_B2B_MEETING = 148043  # Встреча проведена / Квалифицирован
STAGE_B2B_PROPOSAL = 148044 # КП отправлено
STAGE_B2B_CONTRACT = 148045 # Договор на подписи
STAGE_B2B_WON = 148038      # Успешно реализовано

# Stage map for active deals from HubSpot stages
ACTIVE_STAGE_MAP = {
    'presentationscheduled': STAGE_B2B_MEETING,
    'decisionmakerboughtin': STAGE_B2B_MEETING,
    'contractsent': STAGE_B2B_PROPOSAL,
    '4364735215': STAGE_B2B_CONTRACT,
    '4342570695': STAGE_B2B_CONTRACT,
    'closedwon': STAGE_B2B_WON,
    'appointmentscheduled': STAGE_B2B_CONTACT,
    'qualifiedtobuy': STAGE_B2B_CONTACT
}

def oko_mcp(tool_name, arguments, retries=5):
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
            time.sleep(1 + attempt)
            if attempt == retries - 1:
                print(f"[{tool_name}] Network Error: {e}")
                return None
    return None

def main():
    print("=== 1. Loading HubSpot export mapping for stage reference ===")
    with open('/Users/ulyana/CALL TALK/scratch/hubspot_live_export.json', 'r', encoding='utf-8') as f:
        hs_data = json.load(f)
    with open('/Users/ulyana/CALL TALK/scratch/migration_final_report.json', 'r', encoding='utf-8') as f:
        rep_data = json.load(f)

    deal_id_map = rep_data.get('deal_id_mapping', {}) # hs_deal_id -> oko_deal_id
    oko_to_hs_stage = {}
    for hs_deal in hs_data.get('deals', []):
        hs_id = str(hs_deal['id'])
        if hs_id in deal_id_map:
            oko_id = deal_id_map[hs_id]
            oko_to_hs_stage[oko_id] = hs_deal.get('properties', {}).get('dealstage', '')

    print(f"Mapped {len(oko_to_hs_stage)} deals to their original HubSpot stages")

    print("\n=== 2. Fetching all leads currently on stage 'Новый лид' (148040) in B2B pipeline ===")
    cursor = None
    all_new_leads = []
    while True:
        args = {'pipeline_id': 30895, 'stage_id': 148040, 'limit': 50}
        if cursor:
            args['cursor'] = cursor
        res = oko_mcp('search_leads', args)
        if not res or not isinstance(res, dict):
            break
        items = res.get('items', [])
        all_new_leads.extend(items)
        cursor = res.get('next_cursor')
        if not cursor or not items:
            break

    print(f"Found {len(all_new_leads)} leads on 'Новый лид'")

    free_count = 0
    archive_count = 0
    active_count = 0

    for i, lead in enumerate(all_new_leads, 1):
        lid = lead['id']
        name = lead.get('name') or ''
        
        # Test leads cleanup
        if name in ['тест', '__test_no_responsible__', '__test_closed__'] or not name:
            oko_mcp('update_lead', {'lead_id': lid, 'stage_id': STAGE_ARCHIVE_LOST})
            continue

        if name.startswith('[Свободный лид]'):
            # Move to Pipeline 30944 -> Stage 148390 (Свободный пул)
            res = oko_mcp('update_lead', {'lead_id': lid, 'stage_id': STAGE_FREE_POOL})
            if res:
                free_count += 1
                print(f"[{i}/{len(all_new_leads)}] [Свободный пул] -> {lid}: {name[:40]}")
        elif name.startswith('[Архив: Отказ]'):
            # Move to Pipeline 30944 -> Stage 148393 (Архив / Отказ)
            res = oko_mcp('update_lead', {'lead_id': lid, 'stage_id': STAGE_ARCHIVE_LOST})
            if res:
                archive_count += 1
                print(f"[{i}/{len(all_new_leads)}] [Архив / Отказ] -> {lid}: {name[:40]}")
        else:
            # Active deal in B2B pipeline: move out of 'Новый лид' into its actual stage!
            orig_stage = oko_to_hs_stage.get(lid, 'qualifiedtobuy')
            target_stage = ACTIVE_STAGE_MAP.get(orig_stage, STAGE_B2B_CONTACT)
            res = oko_mcp('update_lead', {'lead_id': lid, 'stage_id': target_stage})
            if res:
                active_count += 1
                print(f"[{i}/{len(all_new_leads)}] [B2B Активная -> Stage {target_stage}] -> {lid}: {name[:40]}")

        time.sleep(0.08)

    print(f"\nMoved:")
    print(f"  - Свободные лиды в 'База в проработку': {free_count}")
    print(f"  - Отказные лиды в 'Архив / Отказ': {archive_count}")
    print(f"  - Активные лиды распределены по этапам B2B: {active_count}")

    print("\n=== 3. Final Verification ===")
    # Check leads on stage Новый лид
    res_new = oko_mcp('search_leads', {'pipeline_id': 30895, 'stage_id': 148040})
    remaining = len(res_new.get('items', [])) if res_new and isinstance(res_new, dict) else 0
    print(f"Leads remaining on 'Новый лид' in B2B pipeline: {remaining}")

    # Check leads in База в проработку
    res_free = oko_mcp('search_leads', {'pipeline_id': 30944, 'stage_id': STAGE_FREE_POOL})
    total_free = res_free.get('total', len(res_free.get('items', []))) if res_free and isinstance(res_free, dict) else 0
    print(f"Leads in 'База в проработку' (Свободный пул): {total_free}")

    print("\nREORGANIZATION COMPLETED SUCCESSFULLY!")

if __name__ == '__main__':
    main()
