#!/usr/bin/env python3
"""Валидатор КП Call-Talk V4: BLOCK / WARN / OK.

Проверяет структурную идентичность утвержденному HTML, текстовые договоренности
и арифметику. НЕ подтверждает источники рынка, реальные продажи или рендер PDF.
"""
from __future__ import annotations

import argparse
import json
import hashlib
import math
import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup, Comment, NavigableString, Tag

REFERENCE_NAME = "CALL-TALK_Эталон_КП_9_слайдов_v4.html"
# SHA Git blob V4. При изменении эталона обновлять SHA и тесты вместе.
REFERENCE_BLOB_SHA = "7606cf061a26a66c4821b08d8ead9c9785e39c3f"
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
parser.add_argument("--config", type=Path, help="Параметры экономики и двух вариантов (JSON)")
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
    (r"\b(?:жестк\w*\s+(?:аутрич|outreach)|агрессивн\w*\s+(?:аутрич|outreach))\b", "недопустимый рекламный оборот"),
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
    """Проверка реальных параметров конфигурации, не универсальных 25–42/60–100."""
    if not args.config or not args.config.is_file():
        check(False, "CONFIG-001 | Для готового КП нужен JSON с параметрами (--config)")
        return
    try:
        cfg = json.loads(args.config.read_text(encoding="utf-8"))
        mode = cfg["mode"]
        boxes = int(cfg["boxes"])
        touches = int(cfg["touches"])
        avg_check = float(cfg["avg_check_rub"])
        conversion = float(cfg["conversion"])
        margin = float(cfg["margin"])
        variants = cfg["variants"]
        if mode not in ("terms", "qualification"):
            raise ValueError("mode должен быть terms или qualification")
        if len(variants) != 2 or boxes <= 0 or touches <= 0 or avg_check <= 0 or not 0 < conversion <= 1 or not 0 < margin <= 1:
            raise ValueError("некорректные параметры конфигурации")
    except (KeyError, ValueError, TypeError, json.JSONDecodeError) as exc:
        check(False, f"CONFIG-002 | Неверный JSON: {exc}")
        return

    def shown_number(name: str) -> float:
        return parse_number(values[name])

    def shown_money(name: str) -> float:
        return parse_money(values[name] + " руб." if not re.search(r"руб", values[name]) else values[name])[0]

    def check_equal(name: str, expected: float, location: str, tolerance: float = 0.5) -> None:
        try:
            found = shown_number(name)
            check(abs(found - expected) <= tolerance,
                  f"MATH-{location} | {name}: указано {found:g}, нужно {expected:g}")
        except (KeyError, ValueError) as exc:
            check(False, f"MATH-{location} | {name}: {exc}")

    def check_amount(name: str, expected: float, location: str, tolerance: float = 1) -> None:
        try:
            found = shown_money(name)
            check(abs(found - expected) <= tolerance,
                  f"MATH-{location} | {name}: указано {found:g} руб., нужно {expected:g} руб.")
        except (KeyError, ValueError) as exc:
            check(False, f"MATH-{location} | {name}: {exc}")

    check_equal("ЧИСЛО_ЯЩИКОВ", boxes, "BOXES")
    check_equal("ЧИСЛО_КАСАНИЙ", touches, "TOUCHES")
    if boxes != 10:
        warnings.append(f"CONFIG-BOXES | Использовано {boxes} почтовых ящиков вместо стандартных 10; сверить согласование и охват")
    if touches != 3:
        warnings.append(f"CONFIG-TOUCHES | {touches} касаний вместо стандартных 3")
    if conversion != .15:
        warnings.append(f"CONFIG-CONVERSION | Конверсия {conversion:.1%} вместо стандартного сценария 15%; проверьте источник")
    if margin != .15:
        warnings.append(f"CONFIG-MARGIN | Маржинальность {margin:.1%} вместо стандартного сценария 15%; проверьте источник")
    if mode == "terms" and [int(v.get("months", 0)) for v in variants] != [4, 2]:
        warnings.append("CONFIG-TERM | Сроки отличаются от стандартных 4 и 2 месяцев")
    if mode == "qualification" and variants[0].get("months") != variants[1].get("months"):
        warnings.append("CONFIG-MODE | В сравнении квалификации указаны разные сроки")
    if mode == "terms":
        for i, default in enumerate((39000, 56000)):
            if int(variants[i].get("monthly_fixed_rub", 0)) != default:
                warnings.append(f"CONFIG-PRICE | Вариант {i+1}: фикс отличается от стандартного {default} руб./мес")

    try:
        displayed = values["ЭКОНОМИКА_ИСХОДНЫЕ_ДАННЫЕ"]
        percents = [float(x.replace(",", ".")) / 100 for x in re.findall(r"(\d+(?:[.,]\d+)?)\s*%", displayed)]
        shown_check = parse_money(displayed)[0]
        check(len(percents) >= 2 and abs(percents[0] - conversion) <= .00001 and abs(percents[1] - margin) <= .00001,
              "MATH-ASSUMPTIONS | Конверсия и маржа в подписи не совпадают с JSON")
        check(abs(shown_check - avg_check) <= 1,
              "MATH-ASSUMPTIONS | Чек в подписи не совпадает с JSON")
    except (KeyError, ValueError) as exc:
        check(False, f"MATH-ASSUMPTIONS | Не удалось разобрать исходные параметры: {exc}")

    # Оба периода и суммы сопоставляются с одной конфигурацией; карточка 1 соответствует слайду 7.
    for i, (variant, slide_no) in enumerate(zip(variants, (7, 6)), 1):
        loc = f"SLIDE-{slide_no}"
        prefix = f"ВАРИАНТ_{i}_"
        try:
            months = int(variant["months"])
            monthly = float(variant["monthly_fixed_rub"])
            lead_price = float(variant["lead_price_rub"])
            estimate_leads = int(variant["leads_calc"])
            periods = variant["periods"]
            if months <= 0 or monthly < 0 or lead_price <= 0 or len(periods) != 2:
                raise ValueError("некорректные срок, цены или количество периодов")
            counts = [int(p["contacts"]) for p in periods]
            rates = [(float(p["rate_low"]), float(p["rate_high"])) for p in periods]
            if any(n <= 0 for n in counts) or any(not 0 <= lo <= hi <= 1 for lo, hi in rates):
                raise ValueError("некорректный охват или интервалы конверсии контакта в лид")
            lows = [round(n * lo) for n, (lo, hi) in zip(counts, rates)]
            highs = [round(n * hi) for n, (lo, hi) in zip(counts, rates)]
            total_contacts = sum(counts)
            letters = total_contacts * touches
            leads_min, leads_max = sum(lows), sum(highs)
            if not leads_min <= estimate_leads <= leads_max:
                raise ValueError(f"расчет {estimate_leads} лидов вне диапазона {leads_min}–{leads_max}")
        except (KeyError, ValueError, TypeError) as exc:
            check(False, f"CONFIG-{loc} | Параметры варианта {i}: {exc}")
            continue
        budget = months * monthly + estimate_leads * lead_price
        deals = estimate_leads * conversion
        revenue = deals * avg_check
        profit = revenue * margin - budget
        payback = math.ceil(budget / (avg_check * margin))
        check_equal(prefix + "ФИКС_МЕС", monthly, loc)
        check_equal(prefix + "ФИКС_ВСЕГО", months * monthly, loc)
        check_equal(prefix + "ЦЕНА_ЛИДА", lead_price, loc)
        check_equal(prefix + "КОНТАКТЫ", total_contacts, loc)
        check_equal(prefix + "ПИСЬМА", letters, loc)
        check_amount(prefix + "БЮДЖЕТ", budget, loc)
        check_amount(prefix + "ВЫРУЧКА", revenue, loc, tolerance=max(1, abs(revenue) * .00001))
        check_amount(prefix + "ПРИБЫЛЬ", profit, loc, tolerance=max(1, abs(profit) * .00001))
        for t in (1, 2):
            check_equal(prefix + f"КОНТАКТЫ_{t}", counts[t-1], loc)
            check_equal(prefix + f"ПИСЬМА_{t}", counts[t-1] * touches, loc)
            try:
                lo, hi = parse_forecast(values[prefix + f"ЛИДЫ_{t}"])
                check((lo, hi) == (lows[t-1], highs[t-1]),
                      f"MATH-{loc} | Диапазон лидов периода {t}: {lo}–{hi}, нужно {lows[t-1]}–{highs[t-1]}")
            except (KeyError, ValueError) as exc:
                check(False, f"MATH-{loc} | Диапазон периода {t}: {exc}")
        try:
            lo, hi = parse_forecast(values[prefix + "ПРОГНОЗ"])
            check((lo, hi) == (leads_min, leads_max),
                  f"MATH-{loc} | Итоговый прогноз {lo}–{hi}, рассчитано {leads_min}–{leads_max}")
            shown_deals = parse_number(re.search(r"\d+(?:[,.]\d+)?", values[prefix + "ДОГОВОРЫ"]).group())
            shown_payback = parse_number(re.search(r"\d+", values[prefix + "ОКУПАЕМОСТЬ"]).group())
            check(abs(shown_deals - deals) <= 0.51, f"MATH-{loc} | Число договоров: {shown_deals:g}, ожидалось {deals:g}")
            check(shown_payback == payback, f"MATH-{loc} | Окупаемость с {payback}-го договора, не с {shown_payback:g}-го")
        except (KeyError, AttributeError, ValueError) as exc:
            check(False, f"MATH-{loc} | Итоговая воронка: {exc}")
        # Любой вариант имеет те же блоки, строку итогов и защиту значимых чисел.
        table = slides[slide_no-1].select_one(".benefit-table")
        check(table is not None and len(table.select("tbody tr")) == 4, f"STRUCT-{loc} | Ожидаются два периода, итог и бюджет")
        if table:
            rows = table.select("tbody tr")
            if len(rows) == 4:
                total = rows[2].select("td")
                check(len(total) == 4, f"STRUCT-{loc} | В итоговой строке четыре ячейки")
                if len(total) == 4:
                    try:
                        check(parse_number(text(total[1])) == total_contacts,
                              f"MATH-{loc} | Итог контактов не равен {total_contacts}")
                        check(parse_number(text(total[2])) == letters,
                              f"MATH-{loc} | Итог писем не равен {letters}")
                    except ValueError:
                        check(False, f"MATH-{loc} | Нечисловой итог контактов или писем")
        if boxes == 10:
            standard_first = 600
            standard_follow = 1500 * (months - 1)
            if counts != [standard_first, standard_follow]:
                warnings.append(f"CONFIG-REACH | Вариант {i}: охват {counts}, стандарт для {months} мес. [600, {standard_follow}]")
    try:
        expected = cfg.get("client", "").strip()
        check(expected and values.get("КОМПАНИЯ", "").casefold() == expected.casefold(),
              "CONFIG-CLIENT | Клиент в JSON и КП не совпадает")
    except (AttributeError, TypeError):
        check(False, "CONFIG-CLIENT | Некорректное имя клиента")

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
              "Шаблон не совпадает с эталоном V4")
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
def outcome() -> int:
    for message in errors:
        print("BLOCK | " + message)
    for message in warnings:
        print("WARN | " + message)
    if errors:
        print(f"BLOCK | Отправка запрещена: {len(errors)} ошибок, {len(warnings)} предупреждений.")
        return 1
    print("OK | STRUCT-001 | 9 слайдов, исходные CSS и HTML-структура подтверждены.")
    print("OK | COPY-001 | Нет незаполненных полей, запрещенной терминологии и внутренних пометок.")
    if args.template:
        print("OK | TEMPLATE-001 | SHA Git blob V4 совпадает с утвержденным эталоном.")
    else:
        print("OK | MATH-001 | Финансовая модель и диапазоны проверены по конфигурации.")
        print("OK | MARKET-001 | Пять сегментов и сумма базы проверены.")
    print(f"ИТОГ: {'WARN' if warnings else 'OK'}; предупреждений {len(warnings)}.")
    print("Источники рыночных чисел, кейсы и визуальные переполнения сверяются отдельно.")
    return 0

sys.exit(outcome())
