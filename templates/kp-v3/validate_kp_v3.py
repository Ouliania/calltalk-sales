#!/usr/bin/env python3
"""Валидатор утвержденного девятислайдового КП Call-Talk v3 (10 ящиков).

Проверяет структурную идентичность утвержденному HTML, текстовые договоренности
и арифметику. НЕ подтверждает источники рынка, реальные продажи или рендер PDF.
"""
from __future__ import annotations

import argparse
import hashlib
import math
import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup, Comment, NavigableString, Tag

REFERENCE_NAME = "CALL-TALK_Эталон_КП_9_слайдов_v3.html"
# SHA Git blob утвержденного HTML из main на 05.11.2026. Изменять только
# вместе с осознанным обновлением самого шаблона и тестов в отдельном PR.
REFERENCE_BLOB_SHA = "0ef332a04965bab46afb5a40fefb4c206424f88f"
FIELD = re.compile(r"\{\{([^{}]+)\}\}")
NUMBER = r"[+-]?\d[\d \u00a0\u202f]*(?:[.,]\d+)?"
MONEY = re.compile(
    r"(" + NUMBER + r")\s*(млн|тыс)?\.?\s*руб\.?", re.IGNORECASE
)

parser = argparse.ArgumentParser(description=__doc__)
mode = parser.add_mutually_exclusive_group(required=True)
mode.add_argument("--template", type=Path, help="Проверить неизменность эталона")
mode.add_argument("--ready", type=Path, help="Проверить готовое клиентское КП")
parser.add_argument("--reference", type=Path, help="Эталон HTML, если не лежит рядом со скриптом")
parser.add_argument("--client", default="", help="Ожидаемое название клиента")
parser.add_argument(
    "--approve-editorial", action="store_true",
    help="Пропуск неоднозначных оговорок после ручного утверждения; запрещенные пометки не пропускает",
)
args = parser.parse_args()
errors: list[str] = []
warnings: list[str] = []
values: dict[str, str] = {}


def check(condition: bool, description: str) -> None:
    if not condition:
        errors.append(description)


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\u00a0", " ")).strip()


def blob_sha(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


def parse_number(value: str) -> float:
    clean = re.sub(r"[\s\u00a0\u202f]", "", value)
    if "," in clean and "." in clean:
        raise ValueError("неоднозначный разделитель в числе: " + value)
    if "." in clean and re.fullmatch(r"\d{1,3}(?:\.\d{3})+", clean):
        raise ValueError("разделитель тысяч точкой не поддерживается: " + value)
    return float(clean.replace(",", "."))


def parse_money(value: str) -> tuple[float, float]:
    match = MONEY.search(norm(value))
    if not match:
        raise ValueError("не найдено денежное значение в руб.: " + value[:100])
    number = match.group(1)
    factor = {"млн": 1_000_000, "тыс": 1_000, None: 1}[match.group(2)]
    amount = parse_number(number) * factor
    fractional = re.split(r"[.,]", number.replace(" ", "").replace("\u00a0", ""))
    if len(fractional) == 2:
        tolerance = factor * 0.5 * 10 ** (-len(fractional[1]))
    else:
        last = fractional[0].rstrip("0")
        trailing_zeros = len(fractional[0]) - len(last)
        tolerance = max(1, factor * 0.5 * (10 ** trailing_zeros))
    return amount, tolerance


def text(node: Tag | None) -> str:
    return norm(node.get_text(" ", strip=True)) if node else ""


def text_match(expected: str, actual: str, location: str) -> None:
    expected, actual = norm(expected), norm(actual)
    if not FIELD.search(expected):
        check(expected == actual, f"{location}: изменена постоянная подпись или добавлен текст: {actual[:100]!r}")
        return
    pieces = []
    fields = []
    position = 0
    for match in FIELD.finditer(expected):
        pieces.append(re.escape(expected[position:match.start()]))
        pieces.append(r"(.+?)")
        fields.append(match.group(1))
        position = match.end()
    pieces.append(re.escape(expected[position:]))
    extracted = re.fullmatch("".join(pieces), actual, flags=re.S)
    if not extracted:
        check(False, f"{location}: нарушен постоянный текст вокруг заполняемого поля: {actual[:120]!r}")
        return
    for name, value in zip(fields, extracted.groups()):
        value = norm(value)
        check(bool(value), f"{location}: пустое поле {name}")
        if name in values:
            check(values[name] == value, f"{location}: неодинаковое заполнение поля {name}")
        else:
            values[name] = value


def clean_children(tag: Tag) -> list[Tag | NavigableString]:
    return [
        item for item in tag.children
        if isinstance(item, Tag) or (
            isinstance(item, NavigableString)
            and not isinstance(item, Comment) and norm(str(item))
        )
    ]


def attributes(node: Tag, page: int) -> dict:
    attrs = {}
    for key, val in node.attrs.items():
        if key == "src" and node.name == "img" and page == 9:
            check(str(val).startswith("data:image/"), "Слайд 9: фото должно быть встроено в HTML")
            attrs[key] = "<встроенное фото>"
        else:
            attrs[key] = tuple(val) if isinstance(val, list) else val
    return attrs


def compare_nodes(reference: Tag | NavigableString, actual: Tag | NavigableString, page: int, path: str) -> None:
    if isinstance(reference, NavigableString):
        check(isinstance(actual, NavigableString), f"Слайд {page}: изменен тип узла {path}")
        if isinstance(actual, NavigableString):
            text_match(str(reference), str(actual), f"Слайд {page}, {path}")
        return
    if not isinstance(actual, Tag):
        check(False, f"Слайд {page}: пропал элемент {path}")
        return
    check(reference.name == actual.name, f"Слайд {page}: изменен тег {path}")
    check(attributes(reference, page) == attributes(actual, page),
          f"Слайд {page}: изменены CSS-классы, стили или атрибуты элемента {path}")
    expected = clean_children(reference)
    observed = clean_children(actual)
    if len(expected) != len(observed):
        check(False, f"Слайд {page}: изменено число блоков/подписей у {path} (эталон {len(expected)}, КП {len(observed)})")
        return
    for i, (left, right) in enumerate(zip(expected, observed), 1):
        compare_nodes(left, right, page, f"{path}/{i}")


INTERNAL_PHRASES = [
    (r"\b(?:с\s+его\s+слов|с\s+ее\s+слов|с\s+её\s+слов|со\s+слов|по\s+словам)\b", "служебная атрибуция"),
    (r"\b(?:todo|tbd|fixme|заполнить\s+позже|вставить\s+сюда|служебн\w+\s+пометк\w*|внутренн\w+\s+примечани\w*)\b", "внутренняя пометка"),
    (r"\b(?:баз\w*\s+лпр|mql|sql|мкл|скл)\b", "запрещенная маркетинговая терминология"),
    (r"\b(?:гаранти\w+\s+количеств\w+\s+лид\w*|без\s+доплат\s+за\s+фикс)\b", "несогласованное обещание лидов/доработки"),
    (r"\b(?:20|30)\s+(?:почтовых\s+)?ящик\w*\b", "спецоффер 20/30 ящиков в первоначальном КП"),
    (r"\b(?:до\s+)?300\s+писем\s*(?:в\s+день|/\s*день)\b", "устаревшее обещание объема"),
    (r"\b60\+\s+(?:клиент\w*|компани\w*|проект\w*)\b", "устаревшее число клиентов"),
]
REVIEW_PHRASES = [
    (r"\b(?:это\s+лишь\s+предварительн\w+\s+гипотез\w*|предварительн\w+\s+(?:гипотез\w*|оценк\w*))\b", "обесценивающая оговорка"),
    (r"\b(?:возможн\w*\s+пересечени\w*|могут\s+быть\s+неточност\w*)\b", "оговорка о неточности"),
    (r"\b(?:по\s+наш\w+\s+оценк\w*|по\s+информации\s+клиент\w*|важно\s+понимать|следует\s+отметить)\b", "необязательное пояснение"),
    (r"\b(?:не\s+является\s+гаранти\w*|не\s+можем\s+гарантирова\w*)\b", "оговорка о гарантии; проверить существенность"),
]


def editorial_checks(slides: list[Tag]) -> None:
    for slide_idx, slide in enumerate(slides, 1):
        source = norm(slide.get_text(" ", strip=True)).casefold().replace("ё", "е")
        check("₽" not in source, f"Слайд {slide_idx}: используйте 'руб.', а не графический знак рубля")
        for pattern, reason in INTERNAL_PHRASES:
            if re.search(pattern, source, flags=re.I):
                check(False, f"Слайд {slide_idx}: {reason}")
        for pattern, reason in REVIEW_PHRASES:
            match = re.search(pattern, source, flags=re.I)
            if match:
                warnings.append(f"Слайд {slide_idx}: {reason}: {source[max(0,match.start()-15):match.end()+50]!r}")
    if warnings and not args.approve_editorial:
        errors.extend("Требуется редакторское согласование: " + line for line in warnings)


def market_checks(slide: Tag) -> None:
    rows = slide.select("table.data-table tbody tr")
    check(len(rows) == 6, "Слайд 2: должны быть 5 сегментов и 1 итог")
    if len(rows) != 6:
        return
    nums = []
    for i, row in enumerate(rows[:5], 1):
        cells = row.select("td")
        if len(cells) != 4:
            check(False, f"Слайд 2: сегмент {i} должен иметь четыре ячейки")
            continue
        try:
            nums.append(int(parse_number(text(cells[-1]))))
        except ValueError:
            check(False, f"Слайд 2: численность сегмента {i} должна быть числом")
    try:
        total = int(parse_number(text(rows[-1].select("td")[-1])))
        if len(nums) == 5:
            check(sum(nums) == total,
                  f"Слайд 2: итог {total} не совпадает с суммой пяти сегментов {sum(nums)}")
    except (IndexError, ValueError):
        check(False, "Слайд 2: итоговая численность должна быть числом")


def parse_forecast(text_value: str) -> tuple[int, int]:
    match = re.search(r"(\d+)\s*[–—-]\s*(\d+)", text_value)
    if not match:
        raise ValueError("нет диапазона прогноза лидов")
    return int(match.group(1)), int(match.group(2))


def financial_checks(slides: list[Tag]) -> None:
    price_text = values.get("ЦЕНА_ЛИДА", "")
    try:
        lead_price = parse_number(price_text)
        check(lead_price > 0, "Слайд 5: ставка за лид должна быть положительной")
    except ValueError:
        check(False, "Слайд 5: не удалось разобрать стоимость лида")
        return
    assumptions = values.get("ECONOMY_ASSUMPTIONS", "")
    price_match = MONEY.search(assumptions)
    percent_matches = re.findall(r"(\d+(?:[.,]\d+)?)\s*%", assumptions)
    if not price_match or len(percent_matches) < 2:
        check(False, "Слайды 6–7: укажите годовой чек в рублях, конверсию (%) и маржинальность (%)")
        return
    try:
        annual_check = parse_money(price_match.group())[0]
        conv, margin = [parse_number(x) / 100 for x in percent_matches[:2]]
    except ValueError:
        check(False, "Слайды 6–7: некорректные числовые допущения")
        return
    check(annual_check > 0 and 0 < conv <= 1 and 0 < margin <= 1, "Слайды 6–7: некорректная конверсия, чек или маржа")
    check(abs(conv - 0.15) < 0.000001 and abs(margin - 0.15) < 0.000001,
          "Слайды 6–7: статические пояснения шаблона закрепляют 15% конверсии и маржи; для других значений нужно согласованное изменение текста")
    if annual_check <= 0 or conv <= 0 or margin <= 0:
        return
    for months, page, fixed, contacts, emails in ((2, 6, 112000, 2100, 6300), (4, 7, 156000, 5100, 15300)):
        slide = slides[page - 1]
        table = slide.select_one(".benefit-table")
        check(table is not None, f"Слайд {page}: отсутствует таблица воронки")
        if table is None:
            continue
        rows = table.select("tbody tr")
        check(len(rows) == 4, f"Слайд {page}: ожидаются 2 периода, итог и бюджет")
        if len(rows) != 4:
            continue
        summary = rows[2].select("td")
        check(len(summary) == 4, f"Слайд {page}: не распознан итог воронки")
        if len(summary) != 4:
            continue
        try:
            count = parse_number(text(summary[1]))
            sent = parse_number(text(summary[2]))
            leads = parse_number(values[f"LEADS_CALC_{months}M_10"])
            budget = parse_money(values[f"BUDGET_{months}M_10"])[0]
            rev, rev_tol = parse_money(values[f"REV_{months}M_10"])
            profit, profit_tol = parse_money(values[f"PROFIT_{months}M_10"])
            shown_deals = parse_number(re.search(r"\d+", values[f"DEALS_{months}M_10"]).group())
            shown_payback = parse_number(re.search(r"\d+", values[f"PAYBACK_{months}M_10"]).group())
            range_low, range_high = parse_forecast(values[f"M{months}_10"])
            note = values[f"FORMULA_NOTE_{months}M"]
            note_values = [parse_money(m.group())[0] for m in MONEY.finditer(note)]
        except (KeyError, AttributeError, ValueError, IndexError) as exc:
            check(False, f"Слайд {page}: не удалось разобрать финансовые показатели ({exc})")
            continue
        check(count == contacts and sent == emails, f"Слайд {page}: неверный охват или число писем")
        check(range_low <= leads <= range_high, f"Слайд {page}: число расчетных лидов вне прогноза слайда 5")
        check(len(note_values) >= 2, f"Слайд {page}: в формуле должен быть фикс и ставка за лид")
        if len(note_values) >= 2:
            check(abs(note_values[0] - fixed) < 1,
                  f"Слайд {page}: фикс не совпадает с тарифом слайда 5")
            check(abs(note_values[1] - lead_price) < 1,
                  f"Слайд {page}: ставка не совпадает с тарифом слайда 5")
        expected_budget = fixed + leads * lead_price
        expected_deals = leads * conv
        expected_rev = expected_deals * annual_check
        expected_profit = expected_rev * margin - expected_budget
        expected_payback = math.ceil(expected_budget / (annual_check * margin))
        check(abs(budget - expected_budget) <= 1, f"Слайд {page}: бюджет неверен; ожидается {expected_budget:,.0f} руб.")
        check(abs(rev - expected_rev) <= max(rev_tol, 1), f"Слайд {page}: неверна выручка; расчет {expected_rev:,.0f} руб.")
        check(abs(profit - expected_profit) <= max(profit_tol, 1), f"Слайд {page}: неверна прибыль; расчет {expected_profit:,.0f} руб.")
        check(abs(shown_deals - expected_deals) <= .51, f"Слайд {page}: неверно число договоров")
        check(shown_payback == expected_payback, f"Слайд {page}: окупаемость с {expected_payback}-го договора, не с {shown_payback}-го")
        boxes = slide.select(".benefit-cards > .benefit-card")
        check(len(boxes) == 3, f"Слайд {page}: должно быть три финансовые карточки")
        if len(boxes) == 3:
            check(bool(boxes[1].select_one(".benefit-main")) or "benefit-main" in boxes[1].get("class", []),
                  f"Слайд {page}: центральная карточка должна быть ключевой")


def validate() -> None:
    source_path = args.template or args.ready
    reference = args.reference or Path(__file__).with_name(REFERENCE_NAME)
    if not source_path.exists():
        errors.append("Не найден проверяемый HTML: " + str(source_path))
        return
    if not reference.exists():
        errors.append("Не найден эталон HTML: " + str(reference))
        return
    expected_hash = blob_sha(reference)
    check(expected_hash == REFERENCE_BLOB_SHA,
          "Эталон HTML изменился без обновления валидатора. Нужна согласованная версия шаблона.")
    if args.template:
        check(blob_sha(source_path) == REFERENCE_BLOB_SHA,
              "Шаблон не совпадает с утвержденным эталоном v3 от 05.11.2026")
        return
    html = source_path.read_text(encoding="utf-8")
    check(not FIELD.search(html), "В готовом КП остались незаполненные поля {{...}}")
    original = BeautifulSoup(reference.read_text(encoding="utf-8"), "html.parser")
    ready = BeautifulSoup(html, "html.parser")
    original_slides = original.select(".slide")
    ready_slides = ready.select(".slide")
    check(len(original_slides) == len(ready_slides) == 9, "КП должно состоять ровно из девяти слайдов")
    expected_style = [x.get_text() for x in original.select("head style")]
    actual_style = [x.get_text() for x in ready.select("head style")]
    check(expected_style == actual_style, "Изменены CSS-стили эталона")
    if len(ready_slides) != 9:
        return
    for idx, (left, right) in enumerate(zip(original_slides, ready_slides), 1):
        compare_nodes(left, right, idx, f"slide-{idx}")
    check(len(ready.select("script")) == len(original.select("script")),
          "Добавлены несанкционированные скрипты")
    if args.client:
        check(norm(args.client).casefold() == values.get("КОМПАНИЯ", "").casefold(),
              "Название клиента не совпадает с параметром --client")
    editorial_checks(ready_slides)
    market_checks(ready_slides[1])
    financial_checks(ready_slides)


try:
    validate()
except Exception as exc:
    errors.append(f"Необработанная ошибка проверки ({type(exc).__name__}): {exc}")
for message in errors:
    print("ОШИБКА: " + message)
if warnings and args.approve_editorial:
    for message in warnings:
        print("СОГЛАСОВАННАЯ РЕДАКТОРСКАЯ ОГОВОРКА: " + message)
if errors:
    print(f"Проверка не пройдена: ошибок {len(errors)}.")
    sys.exit(1)
print("PASS: структура, постоянный текст, расчетная экономика и редакторские ограничения.")
print("Отдельно проверить источники рынка, условия сделки и визуальное соответствие HTML/PDF.")
