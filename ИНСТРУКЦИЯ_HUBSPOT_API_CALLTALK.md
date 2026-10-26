# 🔌 Инструкция по работе с HubSpot CRM API в Call-Talk

Данный документ содержит полную техническую спецификацию для интеграции с HubSpot CRM: ключи авторизации, ID сущностей, воронки продаж, связи (ассоциации), кастомные свойства, а также готовые примеры кода для чтения и записи данных.

---

## 🔑 1. Авторизационные данные и параметры аккаунта

* **Тип доступа:** Private App Token (Personal Access Token)
* **Токен доступа:** Указывается в файле `.env` (`HUBSPOT_ACCESS_TOKEN`)
* **Portal ID (Hub ID):** `247498625`
* **Регион размещения:** NA2 (`app-na2.hubspot.com`)
* **Базовый URL API:** `https://api.hubapi.com`
* **Заголовок авторизации:** `Authorization: Bearer <HUBSPOT_ACCESS_TOKEN>`
* **Ответственные менеджеры (HubSpot Owners):**
  * **Ульяна Кирпичникова (Lead Manager):**
    * **Email:** `ulyana.k@calltalk.ru`
    * **Owner ID:** `99659620`
  * **Андрей (Leading Specialist / Sales Manager):**
    * **Email:** `andrey.s@calltalk.ru`
    * **Owner ID:** `169030152`

---

## 🧭 2. Воронка продаж и этапы сделок (Pipeline & Stages)

* **ID воронки (Pipeline ID):** `default`
* **Название воронки:** `Воронка Call-Talk`

| Название этапа | ID этапа (`dealstage`) | Вероятность | Описание |
|---|---|---|---|
| **Prospecting** | `appointmentscheduled` | 10% | Холодный контакт в проработке / сбор базы |
| **Initial Contact** | `qualifiedtobuy` | 25% | Первичный контакт, переписка, согласование времени |
| **Meeting** | `presentationscheduled` | 60% | Назначена встреча / звонок-квалификация |
| **Qualified Lead** | `decisionmakerboughtin` | 50% | Квалифицированный лид (подтвержден интерес и бюджет) |
| **Proposal Sent** | `contractsent` | 75% | Отправлено коммерческое предложение |
| **Negotiation** | `4342570695` | 90% | Согласование договора и условий оплаты |
| **Closed Won** | `closedwon` | 100% | Сделка выиграна, оплата получена |
| **Closed Lost** | `closedlost` | 0% | Отказ / сделка закрыта |

---

## 🧱 3. Структура сущностей и ключевые свойства

### 3.1. Сделки (Deals — `0-3`)
* **URL:** `https://api.hubapi.com/crm/v3/objects/deals`
* **Основные свойства:**
  * `dealname` *(строка)* — Название сделки (рекомендуется: `НазваниеКомпании (ИмяЛПР @Telegram)`)
  * `pipeline` *(строка)* — строго `default`
  * `dealstage` *(строка)* — ID этапа из таблицы выше
  * `amount` *(число)* — Сумма сделки (только цифры, без знаков валюты)
  * `hubspot_owner_id` *(строка)* — `99659620`
* **Кастомные свойства Call-Talk:**
  * `tekegram` *(строка)* — Telegram ЛПР (например, `@username`)
  * `phone_number` *(строка)* — Телефон контакта (например, `+7 913 970 0530`)
  * `website` *(строка)* — Сайт компании клиента (`https://site.ru`)
  * `where_lead_from` *(строка, строго enum)* — Источник лида: `email_outreach`, `social_media`, `referral`, `website`, `other`
  * `pricing_model` *(строка, строго enum)* — Модель оплаты: `Fixed & leads`, `Pay per Lead`, `Custom`
  * `pricing__bonus_terms` *(строка, свободный текст)* — Условия по бонусам / стоимости лида / % со сделки (например, *«1% от сделки (чек от 10 млн руб.)»*)
  * `number_of_leads_promised` *(строка/число)* — Прогноз / объем лидов
  * `campaign_start_date` *(строка/дата)* — Дата старта аутрича
  * `campaign_end_date` *(строка/дата)* — Дата окончания спринта

### 3.2. Контакты (Contacts — `0-1`)
* **URL:** `https://api.hubapi.com/crm/v3/objects/contacts`
* **Свойства:**
  * `firstname` *(строка)* — Имя
  * `lastname` *(строка)* — Фамилия
  * `email` *(строка)* — Рабочий email
  * `phone` *(строка)* — Телефон
  * `telegram` *(строка)* — Telegram ЛПР
  * `jobtitle` *(строка)* — Должность ЛПР (свободный текст: *«Коммерческий директор»*, *«Генеральный директор»*, *«Руководитель / ЛПР»*)
  * `role` *(строка, строго enum)* — Допустимые значения: `decision_maker`, `influencer`, `procurement`, `end_user`
  * `lead_source` *(строка, строго enum)* — Источник контакта: `email_outreach`, `social_media`, `referral`, `event`
  * `hubspot_owner_id` *(строка)* — `99659620`

### 3.3. Компании (Companies — `0-2`)
* **URL:** `https://api.hubapi.com/crm/v3/objects/companies`
* **Свойства:**
  * `name` *(строка)* — Официальное название компании
  * `domain` *(строка)* — Домен компании (например, `company.ru`)
  * `website` *(строка)* — Полный URL сайта
  * `phone` *(строка)* — Телефон компании
  * `hubspot_owner_id` *(строка)* — `99659620`

### 3.4. Задачи и Напоминалки (Tasks — `0-27`)
* **URL:** `https://api.hubapi.com/crm/v3/objects/tasks`
* **Свойства:**
  * `hs_task_subject` *(строка)* — Тема напоминалки (например, *«Связаться с Татьяной — согласовать созвон»*)
  * `hs_task_body` *(строка)* — Текст задачи и детали
  * `hs_timestamp` *(строка/дата)* — Дедлайн задачи в формате ISO 8601 UTC (например, `2026-09-28T07:00:00.000Z`)
  * `hs_task_status` *(строка)* — `NOT_STARTED` / `COMPLETED`
  * `hs_task_priority` *(строка)* — `HIGH` / `MEDIUM` / `LOW` / `NONE`
  * `hs_task_type` *(строка)* — `TODO`, `CALL`, `EMAIL`
  * `hubspot_owner_id` *(строка)* — `99659620`

### 3.5. Заметки (Notes — `0-4`)
* **URL:** `https://api.hubapi.com/crm/v3/objects/notes`
* **Свойства:**
  * `hs_note_body` *(строка)* — Текст заметки (поддерживает HTML: `<b>`, `<br>`, `<a>`, `<ul>`, `<li>`)
  * `hs_timestamp` *(строка/дата)* — Дата и время события
  * `hubspot_owner_id` *(строка)* — `99659620`

> 🛑 **СТАНДАРТ ОФОРМЛЕНИЯ ЗАМЕТОК И ЗАДАЧ (ЗАПРЕТ НА СПЛОШНОЙ ТЕКСТ):**
> * **Категорически запрещено писать сплошным текстом!** Вся информация должна считываться сейлзом за 3 секунды.
> * **Абзацы и отступы:** Каждый смысловой блок отделяется двойным переносом (`<br><br>` в заметках, `\n\n` в задачах).
> * **Заголовки и маркеры:** Выделять жирным `<b>Заголовок</b>` и оформлять списки через маркеры `• ` (`<br>• Пункт 1<br>• Пункт 2`).
> * **Структура заметки:**
>   1. `<b>Заголовок / Результат касания</b>`
>   2. Маркированный список ключевых договоренностей / параметров
>   3. Финансовые условия и тариф (отдельный абзац)
>   4. Следующий шаг и дедлайн (отдельный абзац)
> * **Структура задачи (`hs_task_body`):**
>   1. Контекст в 1 строку (кто, откуда, какой статус)
>   2. Четкий пошаговый план (`Что сделать: 1. ... 2. ...`)
>   3. Контакты и скрипт сообщения для отправки


### 3.6. Письма (Emails — `0-49` / Log an email)
* **URL:** `https://api.hubapi.com/crm/v3/objects/emails`
* **Отображение:** Отображается в ленте контакта и сделки как полноценное электронное письмо (Log an email)
* **Свойства:**
  * `hs_email_subject` *(строка)* — Тема письма
  * `hs_email_html` *(строка/html)* — Тело письма в HTML
  * `hs_email_direction` *(строка)* — `EMAIL` (отправленное) или `INCOMING_EMAIL` (входящее)
  * `hs_email_status` *(строка)* — `SENT`
  * `hs_timestamp` *(строка/дата)* — Время отправки/получения в UTC
  * `hubspot_owner_id` *(строка)* — `99659620`

---

## 🔗 4. Ассоциации (Связи между объектами в API v4)

Для связи объектов используется эндпоинт v4:  
`PUT https://api.hubapi.com/crm/v4/objects/{fromType}/{fromId}/associations/{toType}/{toId}`  
Тело запроса:  
`[{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": <ID>}]`

| Связываемые объекты | From $\rightarrow$ To | `associationTypeId` | Категория |
|---|---|---|---|
| **Сделка $\rightarrow$ Компания** (Основная) | `deals` $\rightarrow$ `companies` | **5** | `HUBSPOT_DEFINED` |
| **Контакт $\rightarrow$ Компания** (Основная) | `contacts` $\rightarrow$ `companies` | **1** | `HUBSPOT_DEFINED` |
| **Сделка $\rightarrow$ Контакт** | `deals` $\rightarrow$ `contacts` | **3** | `HUBSPOT_DEFINED` |
| **Задача $\rightarrow$ Сделка** | `tasks` $\rightarrow$ `deals` | **216** | `HUBSPOT_DEFINED` |
| **Задача $\rightarrow$ Контакт** | `tasks` $\rightarrow$ `contacts` | **204** | `HUBSPOT_DEFINED` |
| **Задача $\rightarrow$ Компания** | `tasks` $\rightarrow$ `companies` | **192** | `HUBSPOT_DEFINED` |
| **Заметка $\rightarrow$ Сделка** | `notes` $\rightarrow$ `deals` | **214** | `HUBSPOT_DEFINED` |
| **Заметка $\rightarrow$ Контакт** | `notes` $\rightarrow$ `contacts` | **202** | `HUBSPOT_DEFINED` |
| **Письмо (Email) $\rightarrow$ Контакт** | `emails` $\rightarrow$ `contacts` | **198** | `HUBSPOT_DEFINED` |
| **Письмо (Email) $\rightarrow$ Сделка** | `emails` $\rightarrow$ `deals` | **210** | `HUBSPOT_DEFINED` |

> [!WARNING]
> **Удаление ошибочной связи:**  
> `DELETE https://api.hubapi.com/crm/v4/objects/{fromType}/{fromId}/associations/{toType}/{toId}`

---

## 💻 5. Готовые шаблоны кода (Python)

### 5.1. Базовый клиент API
```python
import urllib.request
import json
import os

TOKEN = os.getenv('HUBSPOT_ACCESS_TOKEN', 'YOUR_TOKEN_HERE')
OWNER_ID = '99659620'
HEADERS = {
    'Authorization': f'Bearer {TOKEN}',
    'Content-Type': 'application/json'
}

def hubspot_request(endpoint, method='GET', data=None):
    url = f"https://api.hubapi.com{endpoint}"
    req = urllib.request.Request(
        url,
        headers=HEADERS,
        data=json.dumps(data).encode('utf-8') if data is not None else None,
        method=method
    )
    try:
        with urllib.request.urlopen(req) as resp:
            if resp.status == 204:
                return {}
            content = resp.read().decode('utf-8')
            return json.loads(content) if content else {}
    except urllib.error.HTTPError as e:
        print(f"API Error {e.code}: {e.read().decode('utf-8')}")
        return None
```

### 5.2. Создание полного лида (Компания + Контакт + Сделка + Связи)
```python
def create_full_lead(company_name, domain, contact_name, phone, telegram, email, deal_name):
    # 1. Компания
    company = hubspot_request('/crm/v3/objects/companies', method='POST', data={
        'properties': {
            'name': company_name,
            'domain': domain,
            'hubspot_owner_id': OWNER_ID
        }
    })
    comp_id = company['id']

    # 2. Контакт
    contact = hubspot_request('/crm/v3/objects/contacts', method='POST', data={
        'properties': {
            'firstname': contact_name,
            'phone': phone,
            'telegram': telegram,
            'email': email,
            'role': 'decision_maker',
            'hubspot_owner_id': OWNER_ID
        }
    })
    cont_id = contact['id']

    # Привязка Контакта к Компании (typeId: 1)
    hubspot_request(f'/crm/v4/objects/contacts/{cont_id}/associations/companies/{comp_id}', method='PUT', data=[
        {'associationCategory': 'HUBSPOT_DEFINED', 'associationTypeId': 1}
    ])

    # 3. Сделка
    deal = hubspot_request('/crm/v3/objects/deals', method='POST', data={
        'properties': {
            'dealname': deal_name,
            'pipeline': 'default',
            'dealstage': 'qualifiedtobuy', # Initial Contact
            'phone_number': phone,
            'tekegram': telegram,
            'website': f"https://{domain}" if domain else '',
            'hubspot_owner_id': OWNER_ID
        }
    })
    deal_id = deal['id']

    # Привязка Сделки к Компании (typeId: 5) и Сделки к Контакту (typeId: 3)
    hubspot_request(f'/crm/v4/objects/deals/{deal_id}/associations/companies/{comp_id}', method='PUT', data=[
        {'associationCategory': 'HUBSPOT_DEFINED', 'associationTypeId': 5}
    ])
    hubspot_request(f'/crm/v4/objects/deals/{deal_id}/associations/contacts/{cont_id}', method='PUT', data=[
        {'associationCategory': 'HUBSPOT_DEFINED', 'associationTypeId': 3}
    ])

    return {'deal_id': deal_id, 'contact_id': cont_id, 'company_id': comp_id}
```

### 5.3. Постановка задачи / напоминалки (Task)
```python
def create_task(subject, body, due_iso, deal_id=None, contact_id=None):
    associations = []
    if deal_id:
        associations.append({'to': {'id': deal_id}, 'types': [{'associationCategory': 'HUBSPOT_DEFINED', 'associationTypeId': 216}]})
    if contact_id:
        associations.append({'to': {'id': contact_id}, 'types': [{'associationCategory': 'HUBSPOT_DEFINED', 'associationTypeId': 204}]})

    return hubspot_request('/crm/v3/objects/tasks', method='POST', data={
        'properties': {
            'hs_task_subject': subject,
            'hs_task_body': body,
            'hs_timestamp': due_iso, # e.g. "2026-09-28T07:00:00.000Z"
            'hs_task_status': 'NOT_STARTED',
            'hs_task_priority': 'HIGH',
            'hs_task_type': 'TODO',
            'hubspot_owner_id': OWNER_ID
        },
        'associations': associations
    })
```

### 5.4. Добавление заметки с историей (Note)
```python
def add_note(html_content, deal_id=None, contact_id=None):
    associations = []
    if deal_id:
        associations.append({'to': {'id': deal_id}, 'types': [{'associationCategory': 'HUBSPOT_DEFINED', 'associationTypeId': 214}]})
    if contact_id:
        associations.append({'to': {'id': contact_id}, 'types': [{'associationCategory': 'HUBSPOT_DEFINED', 'associationTypeId': 202}]})

    return hubspot_request('/crm/v3/objects/notes', method='POST', data={
        'properties': {
            'hs_note_body': html_content,
            'hubspot_owner_id': OWNER_ID
        },
        'associations': associations
    })
```

### 5.5. Поиск и фильтрация объектов (Search API)
```python
# Поиск сделки по имени или контакту
def search_deals(query_text):
    return hubspot_request('/crm/v3/objects/deals/search', method='POST', data={
        'query': query_text
    })

# Получение открытых сделок на этапе 'Meeting' (presentationscheduled)
def get_meetings():
    return hubspot_request('/crm/v3/objects/deals/search', method='POST', data={
        'filterGroups': [{
            'filters': [{
                'propertyName': 'dealstage',
                'operator': 'EQ',
                'value': 'presentationscheduled'
            }]
        }],
        'properties': ['dealname', 'amount', 'tekegram', 'phone_number', 'website']
    })
```
