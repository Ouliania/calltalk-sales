#!/usr/bin/env python3
"""
HubSpot CRM Automation Tool for Call-Talk.
Handles Contact, Deal, Note and Task creation with automatic stage-based task assignment.
"""

import sys
import os
import argparse
import json
import urllib.request
import urllib.error
import ssl
from datetime import datetime, timedelta, timezone

# Create SSL context to handle certificate verification on macOS
try:
    import certifi
    SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
except Exception:
    SSL_CONTEXT = ssl.create_default_context()
    SSL_CONTEXT.check_hostname = False
    SSL_CONTEXT.verify_mode = ssl.CERT_NONE

PORTAL_ID = "247498625"
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
DEFAULT_OWNER_ID = "99659620"  # Ульяна Кирпичникова
OWNER_ID = DEFAULT_OWNER_ID

OWNERS = {
    "ulyana": "99659620",
    "ульяна": "99659620",
    "ulyana.k@calltalk.ru": "99659620",
    "andrey": "169030152",
    "андрей": "169030152",
    "andrey.s@calltalk.ru": "169030152",
}

def resolve_owner(val=None):
    if not val:
        return DEFAULT_OWNER_ID
    val_str = str(val).strip().lower()
    return OWNERS.get(val_str, str(val).strip())

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}

STAGE_NAMES = {
    "appointmentscheduled": "Prospecting",
    "qualifiedtobuy": "Initial Contact",
    "presentationscheduled": "Meeting",
    "decisionmakerboughtin": "Qualified Lead",
    "contractsent": "Offer Sent",
    "4342570695": "Negotiation",
    "4364735215": "Contract for signature",
    "closedwon": "Closed Won",
    "closedlost": "Closed Lost"
}

def api_request(endpoint, method="GET", data=None):
    url = f"https://api.hubapi.com{endpoint}"
    req = urllib.request.Request(
        url,
        headers=HEADERS,
        data=json.dumps(data).encode("utf-8") if data is not None else None,
        method=method
    )
    try:
        with urllib.request.urlopen(req, context=SSL_CONTEXT) as resp:
            if resp.status == 204:
                return {}
            content = resp.read().decode("utf-8")
            return json.loads(content) if content else {}
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        print(f"API Error {e.code} on {endpoint}: {error_body}", file=sys.stderr)
        return None

def get_deal(deal_id_or_query):
    deal_str = str(deal_id_or_query).strip()
    if deal_str.isdigit():
        return api_request(f"/crm/v3/objects/deals/{deal_str}?properties=dealname,dealstage,where_lead_from,communication_channel,amount,hubspot_owner_id")
    # Search by text query
    res = api_request("/crm/v3/objects/deals/search", method="POST", data={
        "query": deal_str,
        "properties": ["dealname", "dealstage", "where_lead_from", "communication_channel", "amount", "hubspot_owner_id"]
    })
    if res and res.get("results"):
        return res["results"][0]
    return None

def get_deal_tasks(deal_id):
    res = api_request(f"/crm/v4/objects/deals/{deal_id}/associations/tasks")
    if not res or "results" not in res:
        return []
    task_ids = [item["toObjectId"] for item in res["results"]]
    tasks = []
    for tid in task_ids:
        t_data = api_request(f"/crm/v3/objects/tasks/{tid}?properties=hs_task_subject,hs_task_body,hs_timestamp,hs_task_status,hs_task_priority,hs_task_type")
        if t_data:
            tasks.append(t_data)
    return tasks

def get_deal_company(deal_id):
    res = api_request(f"/crm/v4/objects/deals/{deal_id}/associations/companies")
    if res and res.get("results"):
        return res["results"][0]["toObjectId"]
    return None

def build_task_associations(deal_id, contact_id=None, company_id=None):
    """
    Builds full associations for a task:
    Always includes Deal (216), plus Contact (204) and Company (192) if present,
    so the task appears on the Deal record and is linked across all entities in HubSpot.
    """
    assocs = []
    if deal_id:
        assocs.append({"to": {"id": str(deal_id)}, "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 216}]})
    if contact_id:
        assocs.append({"to": {"id": str(contact_id)}, "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 204}]})
    if company_id:
        assocs.append({"to": {"id": str(company_id)}, "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 192}]})
    return assocs

def create_or_update_task_for_stage(deal_id, deal_name, deal_stage, contact_id=None, contact_name="", tg_or_phone="", owner_id=None, company_id=None):
    """
    Checks if an active task exists for the deal.
    If none exists, or if the existing task is empty/generic, creates or updates an actionable task.
    """
    final_owner = resolve_owner(owner_id)
    if not company_id and deal_id:
        company_id = get_deal_company(deal_id)
    existing_tasks = get_deal_tasks(deal_id)
    active_tasks = [t for t in existing_tasks if t.get("properties", {}).get("hs_task_status") != "COMPLETED"]

    # Calculate deadline (next business morning 10:00 MSK = 07:00 UTC)
    now = datetime.now(timezone.utc)
    due_dt = now + timedelta(days=1)
    due_iso = due_dt.strftime("%Y-%m-%dT07:00:00Z")

    contact_ref = f"{contact_name} ({tg_or_phone})" if tg_or_phone else (contact_name or deal_name)

    if deal_stage in ["closedlost", "closedwon"]:
        for t in active_tasks:
            api_request(f"/crm/v3/objects/tasks/{t['id']}", method="PATCH", data={"properties": {"hs_task_status": "COMPLETED"}})
        if contact_id and deal_stage == "closedlost":
            api_request(f"/crm/v3/objects/contacts/{contact_id}", method="PATCH", data={"properties": {"hs_lead_status": "UNQUALIFIED"}})
        return {"action": "closed_tasks_completed", "count": len(active_tasks)}

    if deal_stage == "qualifiedtobuy":
        subject = f"Пинг 1: получить ответ от {contact_ref}"
        body = (f"Контекст:\n"
                f"Проверить ответ на квалифицирующие вопросы в Telegram/мессенджере ({tg_or_phone}).\n\n"
                f"Что сделать:\n"
                f"1. Если ответил — квалифицировать чек и наличие РОПа/сейлзов, предложить слот на созвон.\n"
                f"2. Если нет ответа — отправить Пинг 1 по регламенту:\n\n"
                f"Скрипт сообщения:\n"
                f"«{contact_name}, приветствую! Удалось посмотреть сообщение? Если сомневаетесь по формату — у нас модель с оплатой за результат. "
                f"При вашем чеке достаточно закрыть 1 контракт, чтобы окупить аутрич... Давайте созвонимся на 15–20 минут...»")
    elif deal_stage == "presentationscheduled":
        subject = f"Подготовка и созвон-квалификация с {contact_ref}"
        body = (f"Контекст:\n"
                f"Назначена встреча / звонок-квалификация с {contact_ref}.\n\n"
                f"Что сделать:\n"
                f"1. Изучить сайт компании, определить профиль продукта и целевых ЛПР.\n"
                f"2. Подготовить предварительный расчет окупаемости и оценку емкости базы.\n"
                f"3. Провести 20-минутный созвон в Телемосте/Zoom.")
    elif deal_stage == "decisionmakerboughtin":
        subject = f"Подготовить и согласовать КП для {contact_ref}"
        body = (f"Контекст:\n"
                f"Интерес подтвержден, этап подготовки коммерческого предложения.\n\n"
                f"Что сделать:\n"
                f"1. Собрать HTML коммерческого предложения по эталону Call-Talk (9 слайдов).\n"
                f"2. Выверить расчет окупаемости (строго 15% конверсия от маржи, без ₽).\n"
                f"3. Согласовать HTML с клиентом и направить финальную версию.")
    elif deal_stage == "contractsent":
        subject = f"Контроль ОС по коммерческому предложению: {contact_ref}"
        body = (f"Контекст:\n"
                f"Коммерческое предложение направлено клиенту ({contact_ref}).\n\n"
                f"Что сделать:\n"
                f"1. Уточнить обратную связь по КП и ответить на вопросы по экономике.\n"
                f"2. Обсудить выбор тарифа (4 месяца vs 2 месяца) и перейти к договору.")
    elif deal_stage == "4342570695":
        subject = f"Согласование договора и счета: {contact_ref}"
        body = (f"Контекст:\n"
                f"Условия согласованы, сделка на этапе подписания договора ({contact_ref}).\n\n"
                f"Что сделать:\n"
                f"1. Запросить карточку предприятия / реквизиты.\n"
                f"2. Подготовить договор Call-Talk и выставить счет на оплату фикса.\n"
                f"3. Направить на подписание и проконтролировать оплату.")
    else:
        subject = f"Следующий шаг по сделке: {contact_ref}"
        body = (f"Контекст:\n"
                f"Текущая сделка: {deal_name}.\n\n"
                f"Что сделать:\n"
                f"1. Проверить статус сделки и связаться с клиентом ({tg_or_phone}).")

    # If there's an active task that is generic or empty, update it
    for t in active_tasks:
        props = t.get("properties", {})
        sub = props.get("hs_task_subject", "")
        b = props.get("hs_task_body")
        if not b or "follow-up" in sub.lower() or sub.strip() == "пинг 1" or sub.strip() == "пинг":
            tid = t["id"]
            patch_data = {
                "properties": {
                    "hs_task_subject": subject,
                    "hs_task_body": body,
                    "hs_task_priority": "HIGH",
                    "hs_timestamp": due_iso,
                    "hubspot_owner_id": final_owner
                }
            }
            updated = api_request(f"/crm/v3/objects/tasks/{tid}", method="PATCH", data=patch_data)
            return {"action": "updated", "id": tid, "subject": subject, "due": due_iso}

    if active_tasks:
        # An active, customized task already exists!
        t = active_tasks[0]
        return {"action": "already_exists", "id": t["id"], "subject": t.get("properties", {}).get("hs_task_subject"), "due": t.get("properties", {}).get("hs_timestamp")}

    # The task belongs to the Deal, but is also associated with Contact and Company
    associations = build_task_associations(deal_id, contact_id, company_id)

    task_payload = {
        "properties": {
            "hs_task_subject": subject,
            "hs_task_body": body,
            "hs_timestamp": due_iso,
            "hs_task_status": "NOT_STARTED",
            "hs_task_priority": "HIGH",
            "hs_task_type": "TODO",
            "hubspot_owner_id": final_owner
        },
        "associations": associations
    }
    new_task = api_request("/crm/v3/objects/tasks", method="POST", data=task_payload)
    if new_task:
        return {"action": "created", "id": new_task.get("id"), "subject": subject, "due": due_iso}
    return {"action": "error"}

def add_inbound_lead(name, phone, tg, niche, first_message="", company_name="", website="", owner=None):
    owner_id = resolve_owner(owner)

    # 1. Check or create Contact
    clean_tg = tg.strip() if tg else ""
    if clean_tg and not clean_tg.startswith("@") and not clean_tg.startswith("http"):
        clean_tg = "@" + clean_tg

    # Search existing contact
    contact_id = None
    search_query = clean_tg.replace("@", "") if clean_tg else phone.replace(" ", "").replace("+", "").replace("-", "")
    if search_query:
        s_res = api_request("/crm/v3/objects/contacts/search", method="POST", data={"query": search_query})
        if s_res and s_res.get("results"):
            contact_id = s_res["results"][0]["id"]
            api_request(f"/crm/v3/objects/contacts/{contact_id}", method="PATCH", data={"properties": {"hubspot_owner_id": owner_id}})

    if not contact_id:
        contact_payload = {
            "properties": {
                "firstname": name,
                "phone": phone or "",
                "telegram": clean_tg or "",
                "hs_lead_status": "IN_PROGRESS",
                "hubspot_owner_id": owner_id
            }
        }
        c_res = api_request("/crm/v3/objects/contacts", method="POST", data=contact_payload)
        if c_res:
            contact_id = c_res.get("id")

    # 2. Create Company if provided
    company_id = None
    if company_name or website:
        comp_payload = {
            "properties": {
                "name": company_name or (website.replace("https://", "").replace("http://", "").split("/")[0] if website else name),
                "website": website or "",
                "hubspot_owner_id": owner_id
            }
        }
        comp_res = api_request("/crm/v3/objects/companies", method="POST", data=comp_payload)
        if comp_res:
            company_id = comp_res.get("id")
            if contact_id:
                api_request(f"/crm/v4/objects/contacts/{contact_id}/associations/companies/{company_id}", method="PUT",
                            data=[{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 1}])

    # 3. Create Deal
    deal_title = f"{niche} ({name} {clean_tg})".strip()
    deal_associations = []
    if contact_id:
        deal_associations.append({"to": {"id": str(contact_id)}, "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 3}]})
    if company_id:
        deal_associations.append({"to": {"id": str(company_id)}, "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 5}]})

    deal_payload = {
        "properties": {
            "dealname": deal_title,
            "dealstage": "qualifiedtobuy", # Initial Contact
            "pipeline": "default",
            "where_lead_from": "website",
            "communication_channel": "TG" if clean_tg else "Почта",
            "hubspot_owner_id": owner_id
        },
        "associations": deal_associations
    }
    deal_res = api_request("/crm/v3/objects/deals", method="POST", data=deal_payload)
    deal_id = deal_res.get("id") if deal_res else None

    # 4. Create Note
    note_body = (
        f"<b>Новая заявка с сайта Call-Talk:</b><br>"
        f"• Имя: {name}<br>"
        f"• Телефон: {phone or '—'}<br>"
        f"• Telegram: {clean_tg or '—'}<br>"
        f"• Ниша / интерес: {niche}<br>"
    )
    if website:
        note_body += f"• Сайт: {website}<br>"
    if first_message:
        note_body += f"<br><b>Отправлено первое сообщение в мессенджер:</b><br>{first_message.replace(chr(10), '<br>')}"

    note_assoc = []
    if deal_id:
        note_assoc.append({"to": {"id": str(deal_id)}, "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 214}]})
    if contact_id:
        note_assoc.append({"to": {"id": str(contact_id)}, "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 202}]})

    now_iso = datetime.now(timezone.utc).isoformat()
    note_payload = {
        "properties": {
            "hs_note_body": note_body,
            "hubspot_owner_id": owner_id,
            "hs_timestamp": now_iso
        },
        "associations": note_assoc
    }
    api_request("/crm/v3/objects/notes", method="POST", data=note_payload)

    # 5. Check and set Task
    task_res = create_or_update_task_for_stage(deal_id, deal_title, "qualifiedtobuy", contact_id, name, clean_tg or phone, owner_id=owner_id, company_id=company_id)

    # Output result
    result = {
        "status": "success",
        "deal_id": deal_id,
        "contact_id": contact_id,
        "company_id": company_id,
        "deal_url": f"https://app-na2.hubspot.com/contacts/{PORTAL_ID}/record/0-3/{deal_id}" if deal_id else None,
        "contact_url": f"https://app-na2.hubspot.com/contacts/{PORTAL_ID}/record/0-1/{contact_id}" if contact_id else None,
        "task": task_res
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result

def check_or_set_task(deal_id):
    deal = get_deal(deal_id)
    if not deal:
        print(json.dumps({"error": f"Deal {deal_id} not found"}))
        return
    real_deal_id = deal["id"]
    props = deal.get("properties", {})
    deal_name = props.get("dealname", "")
    deal_stage = props.get("dealstage", "qualifiedtobuy")
    deal_id = real_deal_id

    # Get associated contact
    c_res = api_request(f"/crm/v4/objects/deals/{deal_id}/associations/contacts")
    contact_id = None
    contact_name = ""
    tg_or_phone = ""
    if c_res and c_res.get("results"):
        contact_id = c_res["results"][0]["toObjectId"]
        c_obj = api_request(f"/crm/v3/objects/contacts/{contact_id}?properties=firstname,telegram,phone")
        if c_obj:
            c_props = c_obj.get("properties", {})
            contact_name = c_props.get("firstname", "")
            tg_or_phone = c_props.get("telegram") or c_props.get("phone") or ""

    task_res = create_or_update_task_for_stage(deal_id, deal_name, deal_stage, contact_id, contact_name, tg_or_phone)
    result = {
        "status": "success",
        "deal_id": deal_id,
        "deal_name": deal_name,
        "stage": STAGE_NAMES.get(deal_stage, deal_stage),
        "task": task_res,
        "deal_url": f"https://app-na2.hubspot.com/contacts/{PORTAL_ID}/record/0-3/{deal_id}"
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result

def update_deal_stage(deal_id, new_stage, note_text="", amount=None, task_subject="", task_body="", task_due=""):
    deal = get_deal(deal_id)
    if not deal:
        print(json.dumps({"error": f"Deal {deal_id} not found"}))
        return
    real_deal_id = deal["id"]
    props = deal.get("properties", {})
    deal_name = props.get("dealname", "")
    deal_id = real_deal_id

    # Patch deal
    patch_payload = {"dealstage": new_stage}
    if amount is not None:
        patch_payload["amount"] = str(amount)
    api_request(f"/crm/v3/objects/deals/{deal_id}", method="PATCH", data={"properties": patch_payload})

    # Get contact
    c_res = api_request(f"/crm/v4/objects/deals/{deal_id}/associations/contacts")
    contact_id = None
    contact_name = ""
    tg_or_phone = ""
    if c_res and c_res.get("results"):
        contact_id = c_res["results"][0]["toObjectId"]
        c_obj = api_request(f"/crm/v3/objects/contacts/{contact_id}?properties=firstname,telegram,phone")
        if c_obj:
            c_props = c_obj.get("properties", {})
            contact_name = c_props.get("firstname", "")
            tg_or_phone = c_props.get("telegram") or c_props.get("phone") or ""

    # Add note if provided
    if note_text:
        note_assoc = [
            {"to": {"id": str(deal_id)}, "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 214}]}
        ]
        if contact_id:
            note_assoc.append({"to": {"id": str(contact_id)}, "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 202}]})
        now_iso = datetime.now(timezone.utc).isoformat()
        api_request("/crm/v3/objects/notes", method="POST", data={
            "properties": {
                "hs_note_body": note_text.replace(chr(10), "<br>"),
                "hubspot_owner_id": OWNER_ID,
                "hs_timestamp": now_iso
            },
            "associations": note_assoc
        })

    # Create/update task for new stage
    if task_subject or task_body or task_due:
        existing_tasks = get_deal_tasks(deal_id)
        active_tasks = [t for t in existing_tasks if t.get("properties", {}).get("hs_task_status") != "COMPLETED"]
        sub = task_subject or f"Следующий шаг: {deal_name}"
        b = task_body or ""
        due = task_due or (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%dT07:00:00Z")

        if active_tasks:
            tid = active_tasks[0]["id"]
            patch_data = {
                "properties": {
                    "hs_task_subject": sub,
                    "hs_task_body": b,
                    "hs_task_priority": "HIGH",
                    "hs_timestamp": due,
                    "hubspot_owner_id": OWNER_ID
                }
            }
            api_request(f"/crm/v3/objects/tasks/{tid}", method="PATCH", data=patch_data)
            task_res = {"action": "updated", "id": tid, "subject": sub, "due": due}
        else:
            company_id = get_deal_company(deal_id)
            associations = build_task_associations(deal_id, contact_id, company_id)
            new_task = api_request("/crm/v3/objects/tasks", method="POST", data={
                "properties": {
                    "hs_task_subject": sub,
                    "hs_task_body": b,
                    "hs_timestamp": due,
                    "hs_task_status": "NOT_STARTED",
                    "hs_task_priority": "HIGH",
                    "hs_task_type": "TODO",
                    "hubspot_owner_id": OWNER_ID
                },
                "associations": associations
            })
            task_res = {"action": "created", "id": new_task.get("id"), "subject": sub, "due": due}
    else:
        task_res = create_or_update_task_for_stage(deal_id, deal_name, new_stage, contact_id, contact_name, tg_or_phone)

    result = {
        "status": "success",
        "deal_id": deal_id,
        "deal_name": deal_name,
        "new_stage": STAGE_NAMES.get(new_stage, new_stage),
        "task": task_res,
        "deal_url": f"https://app-na2.hubspot.com/contacts/{PORTAL_ID}/record/0-3/{deal_id}"
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result

def log_chat(deal_id, chat_text, task_subject="", task_body="", due_hours=24):
    deal = get_deal(deal_id)
    if not deal:
        print(json.dumps({"error": f"Deal {deal_id} not found"}))
        return
    real_deal_id = deal["id"]
    props = deal.get("properties", {})
    deal_name = props.get("dealname", "")
    deal_id = real_deal_id

    # Get contact
    c_res = api_request(f"/crm/v4/objects/deals/{deal_id}/associations/contacts")
    contact_id = None
    contact_name = ""
    tg_or_phone = ""
    if c_res and c_res.get("results"):
        contact_id = c_res["results"][0]["toObjectId"]
        c_obj = api_request(f"/crm/v3/objects/contacts/{contact_id}?properties=firstname,telegram,phone")
        if c_obj:
            c_props = c_obj.get("properties", {})
            contact_name = c_props.get("firstname", "")
            tg_or_phone = c_props.get("telegram") or c_props.get("phone") or ""

    contact_ref = f"{contact_name} ({tg_or_phone})" if tg_or_phone else (contact_name or deal_name)

    # 1. Add Note
    note_assoc = [
        {"to": {"id": str(deal_id)}, "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 214}]}
    ]
    if contact_id:
        note_assoc.append({"to": {"id": str(contact_id)}, "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 202}]})
    now_iso = datetime.now(timezone.utc).isoformat()
    note_res = api_request("/crm/v3/objects/notes", method="POST", data={
        "properties": {
            "hs_note_body": f"<b>Переписка в мессенджере ({datetime.now().strftime('%d.%m.%Y %H:%M')}):</b><br><br>{chat_text.replace(chr(10), '<br>')}",
            "hubspot_owner_id": OWNER_ID,
            "hs_timestamp": now_iso
        },
        "associations": note_assoc
    })

    # 2. Update or create Task
    existing_tasks = get_deal_tasks(deal_id)
    active_tasks = [t for t in existing_tasks if t.get("properties", {}).get("hs_task_status") != "COMPLETED"]

    # Calculate deadline
    now = datetime.now(timezone.utc)
    due_dt = now + timedelta(hours=due_hours)
    # Align to 07:00 UTC (10:00 MSK) if due tomorrow
    due_iso = due_dt.strftime("%Y-%m-%dT07:00:00Z")

    subject = task_subject or f"Контроль ответов на вопросы / Пинг 1: {contact_ref}"
    body = task_body or (
        f"Контекст:\n"
        f"Проверить ответы {contact_name} на квалифицирующие вопросы в Telegram ({tg_or_phone}).\n\n"
        f"Что сделать:\n"
        f"1. Если ответил — квалифицировать чек/РОПа и предложить созвон.\n"
        f"2. Если не ответил — отправить Пинг 1 по регламенту:\n\n"
        f"Скрипт сообщения:\n"
        f"«{contact_name}, приветствую! Удалось посмотреть сообщение? Если сомневаетесь по формату — у нас модель с оплатой за результат. "
        f"При вашем чеке достаточно закрыть 1 контракт, чтобы полностью окупить весь проект... Давайте созвонимся на 15–20 минут...»"
    )

    task_res = None
    if active_tasks:
        tid = active_tasks[0]["id"]
        patch_data = {
            "properties": {
                "hs_task_subject": subject,
                "hs_task_body": body,
                "hs_task_priority": "HIGH",
                "hs_timestamp": due_iso,
                "hubspot_owner_id": OWNER_ID
            }
        }
        task_res = api_request(f"/crm/v3/objects/tasks/{tid}", method="PATCH", data=patch_data)
        task_info = {"action": "updated", "id": tid, "subject": subject, "due": due_iso}
    else:
        company_id = get_deal_company(deal_id)
        associations = build_task_associations(deal_id, contact_id, company_id)
        task_payload = {
            "properties": {
                "hs_task_subject": subject,
                "hs_task_body": body,
                "hs_timestamp": due_iso,
                "hs_task_status": "NOT_STARTED",
                "hs_task_priority": "HIGH",
                "hs_task_type": "TODO",
                "hubspot_owner_id": OWNER_ID
            },
            "associations": associations
        }
        new_task = api_request("/crm/v3/objects/tasks", method="POST", data=task_payload)
        task_info = {"action": "created", "id": new_task.get("id"), "subject": subject, "due": due_iso}

def handle_client_reply(query, reply_text, task_subject="", task_body="", phone="", email="", tg="", company="",
                        owner=None, task_due="", task_type="", jobtitle="", deal_name="", first_name="", last_name="", note_html="",
                        ref_name="", ref_email="", ref_jobtitle="", stage=""):
    owner_id = resolve_owner(owner)

    # 1. Search existing deal
    deal = get_deal(query)
    deal_id = deal["id"] if deal else None
    contact_id = None
    company_id = None

    if not deal_id:
        for search_term in [company, email, phone]:
            if search_term and search_term.strip():
                d_res = get_deal(search_term.strip())
                if d_res:
                    deal = d_res
                    deal_id = deal["id"]
                    break

    if deal_id:
        c_res = api_request(f"/crm/v4/objects/deals/{deal_id}/associations/contacts")
        if c_res and c_res.get("results"):
            contact_id = c_res["results"][0]["toObjectId"]

        # Add note
        note_assoc = [
            {"to": {"id": str(deal_id)}, "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 214}]}
        ]
        if contact_id:
            note_assoc.append({"to": {"id": str(contact_id)}, "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 202}]})
        now_iso = datetime.now(timezone.utc).isoformat()
        final_note = note_html if note_html else f"<b>Ответ клиента на аутрич / обращение:</b><br><br>{reply_text.replace(chr(10), '<br>')}"
        api_request("/crm/v3/objects/notes", method="POST", data={
            "properties": {
                "hs_note_body": final_note,
                "hubspot_owner_id": owner_id,
                "hs_timestamp": now_iso
            },
            "associations": note_assoc
        })

        # Update or create task
        due_iso = task_due or (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%dT07:00:00Z")
        sub = task_subject or f"Следующий шаг по клиенту: {query}"
        b = task_body or f"Клиент ответил: «{reply_text}»"
        ttype = task_type or ("EMAIL" if email and not phone else ("CALL" if phone else "TODO"))

        existing_tasks = get_deal_tasks(deal_id)
        active_tasks = [t for t in existing_tasks if t.get("properties", {}).get("hs_task_status") != "COMPLETED"]
        if active_tasks:
            tid = active_tasks[0]["id"]
            api_request(f"/crm/v3/objects/tasks/{tid}", method="PATCH", data={
                "properties": {
                    "hs_task_subject": sub,
                    "hs_task_body": b,
                    "hs_timestamp": due_iso,
                    "hs_task_type": ttype,
                    "hs_task_priority": "HIGH",
                    "hubspot_owner_id": owner_id
                }
            })
            task_info = {"action": "updated", "id": tid, "subject": sub, "due": due_iso}
        else:
            t_assoc = [{"to": {"id": str(deal_id)}, "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 216}]}]
            if contact_id:
                t_assoc.append({"to": {"id": str(contact_id)}, "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 204}]})
            new_task = api_request("/crm/v3/objects/tasks", method="POST", data={
                "properties": {
                    "hs_task_subject": sub,
                    "hs_task_body": b,
                    "hs_timestamp": due_iso,
                    "hs_task_status": "NOT_STARTED",
                    "hs_task_priority": "HIGH",
                    "hs_task_type": ttype,
                    "hubspot_owner_id": owner_id
                },
                "associations": t_assoc
            })
            task_info = {"action": "created", "id": new_task.get("id") if new_task else None, "subject": sub, "due": due_iso}

        result = {
            "status": "success",
            "deal_id": deal_id,
            "contact_id": contact_id,
            "task": task_info,
            "deal_url": f"https://app-na2.hubspot.com/contacts/{PORTAL_ID}/record/0-3/{deal_id}"
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return result

    # Deal not found: create full lead
    clean_tg = tg.strip() if tg else ""
    if clean_tg and not clean_tg.startswith("@") and not clean_tg.startswith("http"):
        clean_tg = "@" + clean_tg

    # Search or create Contact
    c_res = api_request("/crm/v3/objects/contacts/search", method="POST", data={"query": email or phone or query})
    if c_res and c_res.get("results"):
        contact_id = c_res["results"][0]["id"]
        api_request(f"/crm/v3/objects/contacts/{contact_id}", method="PATCH", data={
            "properties": {"hubspot_owner_id": owner_id}
        })
    else:
        fn = first_name
        ln = last_name
        if not fn and not ln:
            name_parts = query.split()
            fn = name_parts[0] if name_parts else query
            ln = name_parts[1] if len(name_parts) > 1 else ""
        c_payload = {
            "properties": {
                "firstname": fn,
                "lastname": ln,
                "email": email or "",
                "phone": phone or "",
                "telegram": clean_tg or "",
                "jobtitle": jobtitle or "",
                "role": "decision_maker",
                "lead_source": "email_outreach",
                "hs_lead_status": "IN_PROGRESS",
                "hubspot_owner_id": owner_id
            }
        }
        new_c = api_request("/crm/v3/objects/contacts", method="POST", data=c_payload)
        if new_c:
            contact_id = new_c.get("id")

    # Company
    if company:
        comp_res = api_request("/crm/v3/objects/companies/search", method="POST", data={"query": company})
        if comp_res and comp_res.get("results"):
            company_id = comp_res["results"][0]["id"]
            api_request(f"/crm/v3/objects/companies/{company_id}", method="PATCH", data={
                "properties": {"hubspot_owner_id": owner_id}
            })
        else:
            domain = email.split("@")[-1] if email and "@" in email and not any(d in email for d in ["mail.ru", "yandex.ru", "gmail.com", "bk.ru"]) else ""
            new_comp = api_request("/crm/v3/objects/companies", method="POST", data={
                "properties": {
                    "name": company,
                    "domain": domain,
                    "website": f"https://{domain}" if domain else "",
                    "phone": phone or "",
                    "hubspot_owner_id": owner_id
                }
            })
            if new_comp:
                company_id = new_comp.get("id")

        if company_id and contact_id:
            api_request(f"/crm/v4/objects/contacts/{contact_id}/associations/companies/{company_id}", method="PUT",
                        data=[{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 1}])

    # Deal
    deal_title = deal_name or (f"{company} ({query} {clean_tg})".strip() if company else f"{query} ({clean_tg or phone})".strip())
    domain = email.split("@")[-1] if email and "@" in email and not any(d in email for d in ["mail.ru", "yandex.ru", "gmail.com", "bk.ru"]) else ""
    deal_assoc = []
    if contact_id:
        deal_assoc.append({"to": {"id": str(contact_id)}, "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 3}]})
    if company_id:
        deal_assoc.append({"to": {"id": str(company_id)}, "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 5}]})

    new_deal = api_request("/crm/v3/objects/deals", method="POST", data={
        "properties": {
            "dealname": deal_title,
            "pipeline": "default",
            "dealstage": stage or "qualifiedtobuy",
            "where_lead_from": "email_outreach",
            "communication_channel": "Почта" if email else "TG",
            "phone_number": phone or "",
            "tekegram": clean_tg or "",
            "website": f"https://{domain}" if domain else "",
            "hubspot_owner_id": owner_id
        },
        "associations": deal_assoc
    })
    deal_id = new_deal.get("id") if new_deal else None

    # Referral / Assistant Contact (e.g. Victoria Titko)
    ref_id = None
    if ref_email:
        ref_res = api_request("/crm/v3/objects/contacts/search", method="POST", data={"query": ref_email})
        if ref_res and ref_res.get("results"):
            ref_id = ref_res["results"][0]["id"]
            api_request(f"/crm/v3/objects/contacts/{ref_id}", method="PATCH", data={"properties": {"hubspot_owner_id": owner_id}})
        else:
            r_parts = ref_name.split() if ref_name else []
            r_fn = r_parts[0] if r_parts else ""
            r_ln = r_parts[1] if len(r_parts) > 1 else ""
            new_ref = api_request("/crm/v3/objects/contacts", method="POST", data={
                "properties": {
                    "firstname": r_fn,
                    "lastname": r_ln,
                    "email": ref_email,
                    "jobtitle": ref_jobtitle or "Секретарь / Офис-менеджер",
                    "role": "influencer",
                    "lead_source": "email_outreach",
                    "hs_lead_status": "IN_PROGRESS",
                    "hubspot_owner_id": owner_id
                }
            })
            if new_ref:
                ref_id = new_ref.get("id")
        if ref_id and company_id:
            api_request(f"/crm/v4/objects/contacts/{ref_id}/associations/companies/{company_id}", method="PUT",
                        data=[{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 1}])
        if ref_id and deal_id:
            api_request(f"/crm/v4/objects/deals/{deal_id}/associations/contacts/{ref_id}", method="PUT",
                        data=[{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 3}])

    # Note
    now_iso = datetime.now(timezone.utc).isoformat()
    note_assoc = []
    if deal_id:
        note_assoc.append({"to": {"id": str(deal_id)}, "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 214}]})
    if contact_id:
        note_assoc.append({"to": {"id": str(contact_id)}, "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 202}]})
    if ref_id:
        note_assoc.append({"to": {"id": str(ref_id)}, "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 202}]})

    final_note = note_html if note_html else f"<b>Ответ клиента на аутрич / обращение:</b><br><br>{reply_text.replace(chr(10), '<br>')}"
    api_request("/crm/v3/objects/notes", method="POST", data={
        "properties": {
            "hs_note_body": final_note,
            "hubspot_owner_id": owner_id,
            "hs_timestamp": now_iso
        },
        "associations": note_assoc
    })

    # Task
    due_iso = task_due or (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%dT07:00:00Z")
    sub = task_subject or f"Позвонить клиенту: {query} ({phone or company})"
    b = task_body or f"Клиент ответил: «{reply_text}»\nСвязаться по телефону {phone} или Telegram {clean_tg}."
    ttype = task_type or ("EMAIL" if email and not phone else ("CALL" if phone else "TODO"))
    # Task associations: Deal (216), Contact (204), Company (192)
    t_assoc = build_task_associations(deal_id, contact_id, company_id)
    if not t_assoc and contact_id:
        t_assoc.append({"to": {"id": str(contact_id)}, "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 204}]})

    new_task = api_request("/crm/v3/objects/tasks", method="POST", data={
        "properties": {
            "hs_task_subject": sub,
            "hs_task_body": b,
            "hs_timestamp": due_iso,
            "hs_task_status": "NOT_STARTED",
            "hs_task_priority": "HIGH",
            "hs_task_type": ttype,
            "hubspot_owner_id": owner_id
        },
        "associations": t_assoc
    })

    result = {
        "status": "success",
        "deal_id": deal_id,
        "contact_id": contact_id,
        "company_id": company_id,
        "task": {"action": "created", "id": new_task.get("id") if new_task else None, "subject": sub, "due": due_iso},
        "deal_url": f"https://app-na2.hubspot.com/contacts/{PORTAL_ID}/record/0-3/{deal_id}" if deal_id else None
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result

def main():
    parser = argparse.ArgumentParser(description="Call-Talk HubSpot Automation Tool")
    subparsers = parser.add_subparsers(dest="command")

    # reply command
    p_reply = subparsers.add_parser("reply")
    p_reply.add_argument("--query", required=True, help="Contact/Deal/Company query name")
    p_reply.add_argument("--text", required=True, help="Client reply text")
    p_reply.add_argument("--phone", default="", help="Client phone")
    p_reply.add_argument("--email", default="", help="Client email")
    p_reply.add_argument("--tg", default="", help="Client telegram")
    p_reply.add_argument("--company", default="", help="Client company")
    p_reply.add_argument("--task-subject", default="", help="Task subject")
    p_reply.add_argument("--task-body", default="", help="Task body")
    p_reply.add_argument("--owner", default=None, help="Owner name, email or ID")
    p_reply.add_argument("--task-due", default="", help="Task due date ISO 8601 (e.g. 2026-10-09T07:00:00Z)")
    p_reply.add_argument("--task-type", default="", help="Task type (EMAIL, CALL, TODO)")
    p_reply.add_argument("--jobtitle", default="", help="Contact job title")
    p_reply.add_argument("--deal-name", default="", help="Custom deal name")
    p_reply.add_argument("--first-name", default="", help="Contact first name")
    p_reply.add_argument("--last-name", default="", help="Contact last name")
    p_reply.add_argument("--note-html", default="", help="Custom HTML for Note")
    p_reply.add_argument("--ref-name", default="", help="Referral / Assistant contact name")
    p_reply.add_argument("--ref-email", default="", help="Referral / Assistant contact email")
    p_reply.add_argument("--ref-jobtitle", default="", help="Referral / Assistant contact job title")
    p_reply.add_argument("--stage", default="", help="Custom dealstage ID (e.g. presentationscheduled)")

    # add-lead command
    p_lead = subparsers.add_parser("add-lead")
    p_lead.add_argument("--name", required=True, help="Contact name")
    p_lead.add_argument("--phone", default="", help="Contact phone")
    p_lead.add_argument("--tg", default="", help="Telegram handle")
    p_lead.add_argument("--niche", required=True, help="Lead niche/interest")
    p_lead.add_argument("--first-message", default="", help="First message text")
    p_lead.add_argument("--company", default="", help="Company name")
    p_lead.add_argument("--website", default="", help="Company website")
    p_lead.add_argument("--owner", default=None, help="Owner name, email or ID")

    # check-task command
    p_task = subparsers.add_parser("check-task")
    p_task.add_argument("--deal-id", required=True, help="HubSpot Deal ID")

    # update-stage command
    p_stage = subparsers.add_parser("update-stage")
    p_stage.add_argument("--deal-id", required=True, help="HubSpot Deal ID")
    p_stage.add_argument("--stage", required=True, help="New dealstage ID (e.g. qualifiedtobuy, presentationscheduled, decisionmakerboughtin, contractsent, 4342570695, closedwon, closedlost)")
    p_stage.add_argument("--note", default="", help="Optional note text")
    p_stage.add_argument("--amount", default=None, help="Optional amount")
    p_stage.add_argument("--task-subject", default="", help="Optional custom task subject")
    p_stage.add_argument("--task-body", default="", help="Optional custom task body")
    p_stage.add_argument("--task-due", default="", help="Optional custom task due date ISO 8601 (e.g. 2026-10-01T10:00:00Z)")

    # log-chat command
    p_chat = subparsers.add_parser("log-chat")
    p_chat.add_argument("--deal-id", required=True, help="HubSpot Deal ID")
    p_chat.add_argument("--text", required=True, help="Chat text / dialogue to log")
    p_chat.add_argument("--task-subject", default="", help="Optional custom task subject")
    p_chat.add_argument("--task-body", default="", help="Optional custom task body")
    p_chat.add_argument("--due-hours", type=int, default=24, help="Hours until task due date")

    # batch command
    p_batch = subparsers.add_parser("batch")
    p_batch.add_argument("--json", required=True, help="JSON list of action objects to execute sequentially")

    args = parser.parse_args()

    if args.command == "reply":
        handle_client_reply(
            query=args.query,
            reply_text=args.text,
            task_subject=args.task_subject,
            task_body=args.task_body,
            phone=args.phone,
            email=args.email,
            tg=args.tg,
            company=args.company,
            owner=args.owner,
            task_due=args.task_due,
            task_type=args.task_type,
            jobtitle=args.jobtitle,
            deal_name=args.deal_name,
            first_name=args.first_name,
            last_name=args.last_name,
            note_html=args.note_html,
            ref_name=args.ref_name,
            ref_email=args.ref_email,
            ref_jobtitle=args.ref_jobtitle,
            stage=args.stage
        )
    elif args.command == "add-lead":
        add_inbound_lead(
            name=args.name,
            phone=args.phone,
            tg=args.tg,
            niche=args.niche,
            first_message=args.first_message,
            company_name=args.company,
            website=args.website,
            owner=args.owner
        )
    elif args.command == "check-task":
        check_or_set_task(args.deal_id)
    elif args.command == "update-stage":
        update_deal_stage(args.deal_id, args.stage, args.note, args.amount, args.task_subject, args.task_body, args.task_due)
    elif args.command == "log-chat":
        log_chat(args.deal_id, args.text, args.task_subject, args.task_body, args.due_hours)
    elif args.command == "batch":
        try:
            tasks = json.loads(args.json)
            results = []
            for item in tasks:
                act = item.get("action")
                if act == "add-lead":
                    results.append(add_inbound_lead(
                        name=item.get("name", ""),
                        phone=item.get("phone", ""),
                        tg=item.get("tg", ""),
                        niche=item.get("niche", ""),
                        first_message=item.get("first_message", ""),
                        company_name=item.get("company_name", ""),
                        website=item.get("website", "")
                    ))
                elif act == "update-stage":
                    results.append(update_deal_stage(
                        deal_id=item.get("deal_id"),
                        new_stage=item.get("stage"),
                        note_text=item.get("note", ""),
                        amount=item.get("amount"),
                        task_subject=item.get("task_subject", ""),
                        task_body=item.get("task_body", ""),
                        task_due=item.get("task_due", "")
                    ))
                elif act == "log-chat":
                    results.append(log_chat(
                        deal_id=item.get("deal_id"),
                        chat_text=item.get("text", ""),
                        task_subject=item.get("task_subject", ""),
                        task_body=item.get("task_body", ""),
                        due_hours=item.get("due_hours", 24)
                    ))
                elif act == "check-task":
                    results.append(check_or_set_task(deal_id=item.get("deal_id")))
                elif act == "reply":
                    results.append(handle_client_reply(
                        query=item.get("query", ""),
                        reply_text=item.get("text", ""),
                        task_subject=item.get("task_subject", ""),
                        task_body=item.get("task_body", ""),
                        phone=item.get("phone", ""),
                        email=item.get("email", ""),
                        tg=item.get("tg", ""),
                        company=item.get("company", ""),
                        owner=item.get("owner"),
                        task_due=item.get("task_due", ""),
                        task_type=item.get("task_type", ""),
                        jobtitle=item.get("jobtitle", ""),
                        deal_name=item.get("deal_name", ""),
                        first_name=item.get("first_name", ""),
                        last_name=item.get("last_name", ""),
                        note_html=item.get("note_html", "")
                    ))
            print(json.dumps({"status": "batch_complete", "count": len(results)}, ensure_ascii=False))
        except Exception as e:
            print(json.dumps({"error": f"Batch execution failed: {e}"}))
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
