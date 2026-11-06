#!/usr/bin/env python3
"""Положительные и негативные проверки обновленного КП v3 (10 ящиков)."""
import math
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VALIDATOR = ROOT / "validate_kp_v3.py"
REFERENCE = ROOT / "CALL-TALK_Эталон_КП_9_слайдов_v3.html"


def run(html, *extra):
    with tempfile.TemporaryDirectory() as directory:
        test_file = Path(directory) / "proposal.html"
        test_file.write_text(html, encoding="utf-8")
        return subprocess.run(
            [sys.executable, str(VALIDATOR), "--ready", str(test_file),
             "--reference", str(REFERENCE), "--client", "ТестКлиент", *extra],
            capture_output=True, text=True, check=False
        )


def make_ready(template: str) -> str:
    fields = {
        "КОМПАНИЯ": "ТестКлиент",
        "ПРОДУКТ": "продукт Тест",
        "РОЛИ_АДРЕСАТОВ": "директоров по продажам",
        "ЦЕЛЕВЫЕ_КОМПАНИИ": "B2B-компании",
        "КРИТЕРИИ_ОТБОРА": "отрасли и выручке",
        "ВСЕГО": "1 500",
        "ЦЕНА_ЛИДА": "2 800",
        "M2_10": "25–42",
        "M4_10": "60–100",
        "SLIDE6_TITLE": "Воронка и окупаемость за 2 месяца",
        "SLIDE7_TITLE": "Воронка и окупаемость за 4 месяца",
        "ECONOMY_ASSUMPTIONS": (
            "Средний годовой чек — 600 000 руб. · Конверсия в договоры 15% "
            "· Маржинальность 15%"
        ),
        "FORMULA_NOTE_2M": "Расходы: фикс 112 000 руб. и 2 800 руб. за оплачиваемый лид.",
        "FORMULA_NOTE_4M": "Расходы: фикс 156 000 руб. и 2 800 руб. за оплачиваемый лид.",
        "КЕЙС_ЛИДЫ": "31", "КЕЙС_СДЕЛКИ": "4", "КЕЙС_КОНТАКТЫ": "2 100",
        "КЕЙС_ПИСЬМА": "6 300", "КЕЙС_СРОК": "2 месяца",
    }
    for i in range(1, 6):
        fields[f"СЕГМЕНТ_{i}"] = f"Сегмент {i}"
        fields[f"ЗАДАЧА_{i}"] = f"Задача {i}"
        fields[f"ОКВЭД_{i}"] = f"62.0{i}"
        fields[f"ЧИСЛО_{i}"] = f"{i * 100}"
    for months, lead_count, fixed in ((2, 34, 112000), (4, 78, 156000)):
        prefix = f"{months}M_10"
        budget = fixed + lead_count * 2800
        contracts = lead_count * .15
        revenue = contracts * 600000
        profit = revenue * .15 - budget
        fields.update({
            f"LEADS_CALC_{prefix}": str(lead_count),
            f"BUDGET_{prefix}": f"{budget:,} руб.".replace(",", " "),
            f"REV_{prefix}": f"{revenue:,.0f} руб.".replace(",", " "),
            f"PROFIT_{prefix}": f"{profit:,.0f} руб.".replace(",", " "),
            f"PAYBACK_{prefix}": f"С {math.ceil(budget/90000)}-го договора",
            f"DEALS_{prefix}": f"≈{round(contracts)} договоров",
        })
    return re.sub(r"\{\{([^{}]+)\}\}",
                  lambda m: fields.get(m.group(1), "Тест"), template)


class KPValidatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.template = REFERENCE.read_text(encoding="utf-8")
        cls.ready = make_ready(cls.template)

    def assert_pass(self, html, *extra):
        result = run(html, *extra)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def assert_fails(self, html, fragment):
        result = run(html)
        self.assertNotEqual(result.returncode, 0, "Намеренно испорченное КП прошло проверку")
        self.assertIn(fragment, result.stdout + result.stderr)

    def test_python_compiles(self):
        proc = subprocess.run([sys.executable, "-m", "py_compile", str(VALIDATOR)],
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_approved_reference(self):
        proc = subprocess.run([sys.executable, str(VALIDATOR), "--template", str(REFERENCE)],
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_valid_ready(self):
        self.assert_pass(self.ready)

    def test_add_badge_fails(self):
        modified = self.ready.replace(
            '<div class="benefit-cards">',
            '<div class="badge">Лишняя подпись</div><div class="benefit-cards">', 1)
        self.assert_fails(modified, "изменено число блоков")

    def test_add_subtitle_in_existing_card_fails(self):
        modified = self.ready.replace(
            "потенциальная годовая выручка",
            "потенциальная годовая выручка (расчет ориентировочный)", 1)
        self.assert_fails(modified, "постоянная подпись")

    def test_change_styles_fails(self):
        modified = self.ready.replace("border-radius:11px", "border-radius:2px", 1)
        self.assert_fails(modified, "стили или атрибуты")

    def test_change_head_css_fails(self):
        modified = self.ready.replace("--primary: #5B4BD8", "--primary: #ff0000", 1)
        self.assert_fails(modified, "CSS-стили")

    def test_unfilled_placeholder_in_attribute_fails(self):
        modified = self.ready.replace('href="https://calltalk.ru"', 'href="{{EMPTY}}"', 1)
        self.assert_fails(modified, "незаполненные поля")

    def test_company_repeated_inconsistently(self):
        modified = self.ready.replace("ТестКлиент", "ЧужаяКомпания", 1)
        self.assert_fails(modified, "неодинаковое заполнение")

    def test_market_total_fails(self):
        modified = self.ready.replace("около 1 500 организаций", "около 1 600 организаций", 1)
        self.assert_fails(modified, "неодинаковое заполнение")

    def test_budget_fails(self):
        self.assert_fails(self.ready.replace("207 200 руб.", "209 200 руб.", 1), "бюджет неверен")

    def test_payback_fails(self):
        self.assert_fails(self.ready.replace("С 3-го договора", "С 4-го договора", 1),
                          "окупаемость")

    def test_profit_fails(self):
        self.assert_fails(self.ready.replace("251 800 руб.", "259 000 руб.", 1),
                          "неверна прибыль")

    def test_forecast_fails(self):
        self.assert_fails(self.ready.replace("25–42", "1–4", 1),
                          "число расчетных лидов вне прогноза")

    def test_old_mailbox_offer_fails(self):
        modified = self.ready.replace("отрасли и выручке", "отрасли и 20 ящикам", 1)
        self.assert_fails(modified, "спецоффер 20/30")

    def test_case_source_disclaimer_fails(self):
        modified = self.ready.replace("Тест</", "Тест (с его слов)</", 1)
        self.assert_fails(modified, "служебная атрибуция")

    def test_unapproved_lead_guarantee_fails(self):
        modified = self.ready.replace("Тест</", "Гарантия количества лидов</", 1)
        self.assert_fails(modified, "несогласованное обещание")

    def test_sales_abbreviation_fails(self):
        modified = self.ready.replace("отрасли и выручке", "отрасли и MQL", 1)
        self.assert_fails(modified, "маркетинговая терминология")

    def test_ruble_symbol_fails(self):
        modified = self.ready.replace("отрасли и выручке", "отрасли и ₽", 1)
        self.assert_fails(modified, "знак рубля")

    def test_uncertain_note_requires_review(self):
        modified = self.ready.replace("отрасли и выручке", "отрасли (возможны пересечения)", 1)
        self.assert_fails(modified, "Требуется редакторское согласование")
        self.assert_pass(modified, "--approve-editorial")

    def test_corrupt_reference_rejected(self):
        modified = self.template.replace("80+ клиентов", "60+ клиентов", 1)
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / "template.html"
            file.write_text(modified, encoding="utf-8")
            proc = subprocess.run([sys.executable, str(VALIDATOR), "--template", str(file),
                                   "--reference", str(REFERENCE)],
                                  capture_output=True, text=True)
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("не совпадает", proc.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
