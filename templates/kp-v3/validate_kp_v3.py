#!/usr/bin/env python3
"""Проверка неизменяемой структуры девятислайдового КП Call-Talk v3."""
import argparse
import re
import sys
from pathlib import Path
from bs4 import BeautifulSoup

p = argparse.ArgumentParser()
g = p.add_mutually_exclusive_group(required=True)
g.add_argument("--template", type=Path)
g.add_argument("--ready", type=Path)
p.add_argument("--client", default="")
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
        check(any("организац" in x and "рф" in x for x in headers),
              "Слайд 2: столбец оценки организаций заменен")
        check(not any("приоритет" in x for x in headers),
              "Слайд 2: нельзя заменять количество организаций приоритетом")
        check(len(market.select("tbody tr")) == 6,
              "Слайд 2: должно быть пять сегментов и итог")
    check("4 этапа" in text(3), "Слайд 3: нет четырех этапов")
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
        check("маржинальная прибыль после расходов" in text(page).lower(),
              f"Слайд {page}: нет ключевого результата для клиента")
        check("потенциальная годовая выручка" in text(page).lower(),
              f"Слайд {page}: нет ключевого показателя выручки")
        check("общие расходы в расчете на лид" not in text(page).lower(),
              f"Слайд {page}: старый акцент на стоимости лида")
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
placeholders = re.findall(r"\{\{[^}]+\}\}", raw)
if args.template:
    check(bool(placeholders), "Шаблон должен содержать поля заполнения")
    check(not any(x in raw.lower() for x in ("упаковки для цветов", "цветочных магазинов",
                                           "4 730 контактов", "14 190 писем")),
          "Шаблон содержит данные предыдущего кейса")
else:
    check(not placeholders, "В готовом КП остались поля шаблона")
    if args.client:
        check(args.client.casefold() in raw.casefold(), "Название клиента не найдено")

for issue in errors:
    print("ОШИБКА:", issue)
if errors:
    sys.exit(1)
print(f"Проверка структуры пройдена: {len(slides)} слайдов.")
print("Дополнительно обязательны проверка расчета расходов и визуальный просмотр всех слайдов.")
