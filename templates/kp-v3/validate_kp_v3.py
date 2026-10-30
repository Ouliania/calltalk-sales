#!/usr/bin/env python3
"""Проверка неизменяемой структуры девятислайдового КП Call-Talk v3."""
import argparse
import re
import sys
from pathlib import Path
from bs4 import BeautifulSoup, Tag

p = argparse.ArgumentParser()
g = p.add_mutually_exclusive_group(required=True)
g.add_argument("--template", type=Path)
g.add_argument("--ready", type=Path)
p.add_argument("--client", default="")
p.add_argument("--reference", type=Path, help="Путь к эталонному HTML для сравнения")
args = p.parse_args()
file = args.template or args.ready
html = file.read_text(encoding="utf-8")
soup = BeautifulSoup(html, "html.parser")
slides = soup.select(".slide")
errors = []

def check(ok, msg):
    if not ok:
        errors.append(msg)

def text(i):
    return slides[i - 1].get_text(" ", strip=True) if len(slides) >= i else ""

check(len(slides) == 9, "Должно быть ровно 9 слайдов")
if len(slides) == 9:
    market = slides[1].select_one("table.data-table")
    check(market is not None, "Слайд 2: отсутствует таблица рынка")
    if market:
        headers = [" ".join(x.stripped_strings).lower() for x in market.select("thead th")]
        check(len(headers) == 4, "Слайд 2: нужны четыре столбца")
        check(any("оквэд" in x for x in headers), "Слайд 2: потерян ОКВЭД")
        check(bool(headers) and ("организац" in headers[-1] or "компан" in headers[-1] or headers[-1].startswith("в ")),
              "Слайд 2: последнее поле должно обозначать число организаций и географию")
        check(not any("приоритет" in x for x in headers),
              "Слайд 2: нельзя заменять количество организаций приоритетом")
        check(len(market.select("tbody tr")) == 6,
              "Слайд 2: должно быть пять сегментов и итог")
    check("4 этапа" in text(3), "Слайд 3: нет четырех этапов")
    # Неизменяемые заголовки и подписи методологии: не перефразировать.
    stage3 = slides[2]
    headings3 = [h.get_text(" ", strip=True) for h in stage3.select("h3")]
    fixed_headings3 = [
        "Подбор компаний и контактов",
        "Предложения под задачи заказчиков",
        "Проверка цепочек писем",
        "Расширение кампании и передача лидов",
    ]
    fixed_captions3 = [
        "База целевых контактов",
        "Письма под разные задачи",
        "Выбор лучших цепочек",
        "Заинтересованные обращения",
    ]
    check(headings3 == fixed_headings3,
          "Слайд 3: изменены постоянные названия четырех этапов")
    caption_nodes3 = stage3.select('.slide-body > div[style*="grid-template-columns"] > .card > div:last-child')
    captions3 = [node.get_text(" ", strip=True) for node in caption_nodes3]
    check(captions3 == fixed_captions3,
          "Слайд 3: изменены нижние подписи четырех этапов")

    case_cols = slides[3].select_one('.slide-body > div[style*="grid-template-columns"]')
    cards = case_cols.find_all("div", class_="card", recursive=False) if case_cols else []
    check(len(cards) == 2, "Слайд 4: две колонки — кейс и преимущества")
    if len(cards) == 2:
        check(len(cards[0].select('div[style*="border-left:3px"]')) == 2,
              "Слайд 4: два текстовых блока кейса")
        check(len(cards[1].select('div[style*="border-left:3px"]')) == 3,
              "Слайд 4: три тезиса преимуществ")
        if args.template:
            for field in ("КЕЙС_ОТРАСЛЬ", "КЕЙС_НАЗВАНИЕ",
                          "КЕЙС_ЗАДАЧА_И_АУДИТОРИЯ", "КЕЙС_КОНТАКТЫ",
                          "КЕЙС_ПИСЬМА", "КЕЙС_ПРЕДЛОЖЕНИЕ",
                          "КЕЙС_ЛИДЫ", "КЕЙС_СДЕЛКИ", "КЕЙС_СРОК"):
                check("{{" + field + "}}" in cards[0].get_text(" ", strip=True),
                      "Слайд 4: осталось чужое содержимое или пропущено поле " + field)
    tariffs = slides[4].select(".sm-grid2 .sm-panel")
    check(len(tariffs) == 2, "Слайд 5: обязательны две тарифные карточки")
    check("Тариф на 2 месяца" in text(5) and "Тариф на 4 месяца" in text(5),
          "Слайд 5: названия тарифов")
    for card in tariffs:
        rows = card.select("table.sm-table tbody tr")
        check(len(rows) == 3, "Слайд 5: нужны варианты 10/20/30 ящиков")
    for page in (6, 7):
        slide = slides[page - 1]
        table = slide.select_one("table.benefit-table")
        check(table is not None, f"Слайд {page}: нет справочной таблицы воронки")
        if table:
            check(len(table.select("thead th")) == 4,
                  f"Слайд {page}: нужна таблица для 10/20/30 ящиков")
            check(len(table.select("tbody tr")) == 4,
                  f"Слайд {page}: нужны контакты, прогноз, лиды для расчета и расходы")
        cards = slide.select(".benefit-cards > .benefit-card")
        check(len(cards) == 3, f"Слайд {page}: нужны три карточки финансового результата")
        if len(cards) == 3:
            check("benefit-main" in cards[1].get("class", []),
                  f"Слайд {page}: рекомендуемый вариант — средняя карточка")
            for card in cards:
                check(card.select_one(".revenue") is not None,
                      f"Слайд {page}: нужна потенциальная выручка")
                check(card.select_one(".profit") is not None,
                      f"Слайд {page}: нужна прибыль после расходов")
                check(card.select_one(".payback") is not None,
                      f"Слайд {page}: нужен порог окупаемости")
        cards_container = slide.select_one(".benefit-cards")
        table_container = slide.select_one("table.benefit-table")
        if cards_container and table_container:
            check(list(slide.descendants).index(cards_container) < list(slide.descendants).index(table_container),
                  f"Слайд {page}: финансовые карточки должны быть над таблицей")
        check(len(slide.select(".benefit-cards")) == 1,
              f"Слайд {page}: нельзя добавлять другие наборы карточек")
        check("маржинальная прибыль после расходов" in text(page).lower(),
              f"Слайд {page}: нет ключевого результата для клиента")
        check("потенциальная годовая выручка" in text(page).lower(),
              f"Слайд {page}: нет ключевого показателя выручки")
        check("общие расходы в расчете на лид" not in text(page).lower(),
              f"Слайд {page}: старый акцент на стоимости лида")
    # Защищаем четыре этапа запуска от изменения названий и подписей.
    stage8 = slides[7]
    headings8 = [h.get_text(" ", strip=True) for h in stage8.select(".slide-body h3")]
    fixed_headings8 = [
        "Подготовка почты и сегментов",
        "База контактов и цепочки писем",
        "Первый запуск и ответы",
        "Расширение кампании",
    ]
    check(headings8 == fixed_headings8,
          "Слайд 8: изменены постоянные названия этапов")
    for fixed in ["Защищаем доставляемость писем", "Тексты и база под ключ",
                  "Первые ответы от компаний", "Регулярная передача лидов"]:
        check(text(8).count(fixed) == 1,
              f"Слайд 8: изменена или продублирована подпись: {fixed}")
    check("Тексты и база под ключ" in text(8), "Слайд 8: обязательная подпись")
    check("Защищаем доставляемость писем" in text(8),
          "Слайд 8: обязательная подпись")
    check("Остались вопросы?" in text(9), "Слайд 9: блок вопросов")
    check("Основатель: Игорь Ермолаев" in text(9), "Слайд 9: блок основателя")
    images = slides[8].select("img")
    check(bool(images) and all(str(img.get("src", "")).startswith("data:") for img in images),
          "Слайд 9: фото должно быть встроено")
    for i, slide in enumerate(slides, 1):
        check(bool(slide.select_one(".slide-header")) and bool(slide.select_one(".slide-footer")),
              f"Слайд {i}: нет хедера или футера")

raw = soup.get_text(" ", strip=True)
check("с его слов" not in raw.casefold()
      and "со слов клиента" not in raw.casefold()
      and "по словам клиента" not in raw.casefold(),
      "В клиентском тексте осталась служебная пометка о происхождении кейса")
placeholders = re.findall(r"\{\{[^}]+\}\}", html)
if args.template:
    check(bool(placeholders), "Шаблон должен содержать поля заполнения")
    check(not any(x in raw.lower() for x in ("упаковки для цветов", "цветочных магазинов",
                                           "4 730 контактов", "14 190 писем")),
          "Шаблон содержит данные предыдущего кейса")
else:
    check(not placeholders, "В готовом КП остались поля шаблона")
    if args.client:
        check(args.client.casefold() in raw.casefold(), "Название клиента не найдено")


# Сравнение структуры с эталоном: запрет новых бейджей, карточек,
# подзаголовков, стилей и иных самовольных элементов.
reference = args.reference or Path(__file__).with_name("CALL-TALK_Эталон_КП_9_слайдов_v3.html")
if not reference.exists():
    check(False, f"Не найден эталон HTML: {reference}. Укажите --reference")
else:
    ref_html = reference.read_text(encoding="utf-8")
    ref_soup = BeautifulSoup(ref_html, "html.parser")
    ref_slides = ref_soup.select(".slide")
    if len(slides) == 9 and len(ref_slides) == 9:
        def signature(slide, strict_style):
            result = []
            for n in slide.descendants:
                if isinstance(n, Tag) and n.name not in ("b", "strong", "em", "i"):
                    result.append((n.name, tuple(n.get("class", [])),
                                   n.get("style", "") if strict_style else ""))
            return result

        for index, (actual, expected) in enumerate(zip(slides, ref_slides), 1):
            # У четвертого слайда допустима ранее согласованная адаптация отступов
            # внутри кейса, но не изменение структуры.
            check(signature(actual, index != 4) == signature(expected, index != 4),
                  f"Слайд {index}: изменены структура, классы или inline-стили эталона")
            actual_badge = actual.select_one(".header-badge")
            ref_badge = expected.select_one(".header-badge")
            if actual_badge and ref_badge:
                check(actual_badge.get_text(" ", strip=True) == ref_badge.get_text(" ", strip=True),
                      f"Слайд {index}: изменена постоянная подпись в шапке")
            footer = actual.select_one(".slide-footer")
            if footer:
                check(footer.get_text(" ", strip=True).endswith(f"Слайд {index:02d} / 09"),
                      f"Слайд {index}: изменена постоянная подпись или номер страницы")

        styles = [x.get_text() for x in soup.select("head style")]
        ref_styles = [x.get_text() for x in ref_soup.select("head style")]
        check(styles == ref_styles, "Изменены глобальные CSS-стили эталона")

        if args.template:
            required_fields = set(re.findall(r"\{\{[^}]+\}\}", ref_html))
            current_fields = set(re.findall(r"\{\{[^}]+\}\}", html))
            check(required_fields == current_fields,
                  "Изменены или удалены обязательные поля шаблона")


# Экономическая арифметика: пересчет всех шести финансовых карточек.
# Проверяется логическая согласованность, но не достоверность допущений.
def number_in(text):
    m = re.search(r"([0-9][0-9\s\xa0]*(?:[.,][0-9]+)?)", text)
    return float(m.group(1).replace(" ", "").replace("\xa0", "").replace(",", ".")) if m else None


def money(text):
    m = re.search(r"([0-9][0-9\s\xa0]*(?:[.,][0-9]+)?)\s*(млн|тыс)?\.?\s*руб", text.lower())
    if not m:
        return None
    raw_value = m.group(1).replace(" ", "").replace("\xa0", "")
    factor = {"млн": 1000000, "тыс": 1000, None: 1}[m.group(2)]
    chunks = re.split("[,.]", raw_value)
    value = float(raw_value.replace(",", ".")) * factor
    if len(chunks) == 2:
        tol = factor * .5 * 10**(-len(chunks[1]))
    else:
        zeros = len(chunks[0]) - len(chunks[0].rstrip("0"))
        tol = factor * .5 * 10**zeros
    return value, tol


if args.ready and len(slides) == 9:
    import math
    for page_num in (6, 7):
        slide = slides[page_num - 1]
        subnode = slide.select_one(".benefit-head .sm-sub")
        note = slide.select_one(".formula-note")
        table = slide.select_one("table.benefit-table")
        cards = slide.select(".benefit-cards > .benefit-card")
        if not (subnode and note and table and len(cards) == 3):
            continue
        subtext = subnode.get_text(" ", strip=True)
        note_text = note.get_text(" ", strip=True)
        price_match = re.search(r"([0-9][0-9\s\xa0]*)\s*руб", subtext)
        percentages = re.findall(r"([0-9]+(?:[.,][0-9]+)?)\s*%", subtext)
        notesums = re.findall(r"([0-9][0-9\s\xa0]*)\s*руб", note_text)
        check(bool(price_match and len(percentages) >= 2 and len(notesums) >= 2),
              f"Слайд {page_num}: для расчета экономики не хватает чека, конверсии, маржи или ставок")
        if not (price_match and len(percentages) >= 2 and len(notesums) >= 2):
            continue
        check_value = number_in(price_match.group())
        conversion = float(percentages[0].replace(",", ".")) / 100
        margin = float(percentages[1].replace(",", ".")) / 100
        fixed_cost, unit_cost = (number_in(n + " руб") for n in notesums[:2])
        rows = table.select("tbody tr")
        if len(rows) != 4:
            continue
        for j, card in enumerate(cards, 1):
            lead_cells = rows[2].select("td")
            cost_cells = rows[3].select("td")
            if len(lead_cells) < 4 or len(cost_cells) < 4:
                check(False, f"Слайд {page_num}: таблица расчетных лидов повреждена")
                break
            leads = number_in(lead_cells[j].get_text(" ", strip=True))
            budget = money(cost_cells[j].get_text(" ", strip=True))
            revenue_node = card.select_one(".revenue > span")
            profit_node = card.select_one(".profit > span")
            payback_node = card.select_one(".payback b")
            deals_node = card.select_one(".deal-count")
            if any(x is None for x in (leads, budget, revenue_node, profit_node, payback_node, deals_node)):
                check(False, f"Слайд {page_num}, {j*10} ящиков: отсутствуют числовые параметры")
                continue
            amount = fixed_cost + leads * unit_cost
            check(abs(budget[0] - amount) <= 1,
                  f"Слайд {page_num}, {j*10} ящиков: бюджет должен быть {amount:,.0f} руб.")
            deals = leads * conversion
            revenue_expected = deals * check_value
            profit_expected = revenue_expected * margin - budget[0]
            shown_revenue = money(revenue_node.get_text(" ", strip=True))
            shown_profit = money(profit_node.get_text(" ", strip=True))
            check(shown_revenue is not None and abs(shown_revenue[0] - revenue_expected) <= shown_revenue[1] + 1,
                  f"Слайд {page_num}, {j*10} ящиков: неверно показана потенциальная выручка")
            check(shown_profit is not None and abs(shown_profit[0] - profit_expected)
                  <= max(shown_profit[1] if shown_profit else 0, abs(profit_expected)*.01, 1000),
                  f"Слайд {page_num}, {j*10} ящиков: неверно показана маржинальная прибыль")
            shown_deals = number_in(deals_node.get_text(" ", strip=True))
            check(shown_deals is not None and abs(shown_deals - deals) <= .51,
                  f"Слайд {page_num}, {j*10} ящиков: неверно показано число договоров")
            if check_value * margin > 0:
                expected_payback = math.ceil(budget[0] / (check_value * margin))
                actual_payback = number_in(payback_node.get_text(" ", strip=True))
                check(actual_payback == expected_payback,
                      f"Слайд {page_num}, {j*10} ящиков: окупаемость с {expected_payback}-го договора, а не с {actual_payback}-го")


for issue in errors:
    print("ОШИБКА:", issue)
if errors:
    sys.exit(1)
print(f"Проверка структуры пройдена: {len(slides)} слайдов.")
print("Дополнительно обязательны проверка расчета расходов и визуальный просмотр всех слайдов.")
