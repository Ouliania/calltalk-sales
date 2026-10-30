#!/usr/bin/env python3
"""Регрессионные и негативные тесты валидатора коммерческого предложения."""
import math
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
VALIDATOR = HERE / "validate_kp_v3.py"
REFERENCE = HERE / "CALL-TALK_Эталон_КП_9_слайдов_v3.html"


def run_validator(html, mode="template", extra_args=()):
    with tempfile.TemporaryDirectory() as folder:
        candidate = Path(folder) / "kp.html"
        candidate.write_text(html, encoding="utf-8")
        return subprocess.run(
            [sys.executable, str(VALIDATOR), "--" + mode, str(candidate),
             "--reference", str(REFERENCE), *extra_args],
            capture_output=True, text=True, check=False,
        )


def make_ready(template):
    scenarios = {2: ([34, 67, 100], 112000), 4: ([78, 157, 236], 156000)}
    data = {
        "ECONOMY_ASSUMPTIONS": (
            "Годовой договор — 600 000 руб. · Конверсия лидов в договоры — 15% "
            "· Расчетная маржинальность — 15%"
        ),
        "FORMULA_NOTE_2M": (
            "Расходы включают фикс 112 000 руб. и 2 800 руб. за каждый расчетный лид."
        ),
        "FORMULA_NOTE_4M": (
            "Расходы включают фикс 156 000 руб. и 2 800 руб. за каждый расчетный лид."
        ),
    }
    for period, (leads_list, fixed) in scenarios.items():
        for boxes, leads in zip((10, 20, 30), leads_list):
            deals = leads * .15
            budget = fixed + leads * 2800
            revenue = deals * 600000
            profit = revenue * .15 - budget
            key = f"{period}M_{boxes}"
            count = {2: {10: 2100, 20: 4200, 30: 6300},
                     4: {10: 5100, 20: 10200, 30: 15300}}[period][boxes]
            data.update({
                "CONTACTS_" + key: str(count),
                "LEADS_" + key: f"{leads-5}–{leads+5}",
                "LEADS_CALC_" + key: str(leads),
                "BUDGET_" + key: f"{budget:,} руб.".replace(",", " "),
                "REV_" + key: f"{revenue:,.0f} руб.".replace(",", " "),
                "PROFIT_" + key: f"{profit:,.0f} руб.".replace(",", " "),
                "DEALS_" + key: f"≈{round(deals)} договоров",
                "PAYBACK_" + key: f"С {math.ceil(budget/90000)}-го договора",
            })
    return re.sub(r"\{\{([^}]+)\}\}",
                  lambda m: data.get(m.group(1), "Тест"), template)


class ValidatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.template = REFERENCE.read_text(encoding="utf-8")
        cls.ready = make_ready(cls.template)

    def assert_ok(self, html, mode="template"):
        result = run_validator(html, mode)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def assert_error(self, html, fragment, mode="template"):
        result = run_validator(html, mode)
        self.assertNotEqual(result.returncode, 0, "Испорченное КП прошло валидацию")
        self.assertIn(fragment, result.stdout + result.stderr)

    def test_compile(self):
        result = subprocess.run(
            [sys.executable, "-m", "py_compile", str(VALIDATOR)],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_template_is_valid(self):
        self.assert_ok(self.template)

    def test_ready_is_valid(self):
        self.assert_ok(self.ready, "ready")

    def test_extra_badge_rejected(self):
        modified = self.template.replace(
            '<div class="benefit-cards">',
            '<div class="badge">Новая подпись</div><div class="benefit-cards">', 1,
        )
        self.assert_error(modified, "структура")

    def test_extra_subtitle_rejected(self):
        modified = self.template.replace(
            '<!-- 4 КАРТОЧКИ В РЯД -->',
            '<p>Новый подзаголовок</p><!-- 4 КАРТОЧКИ В РЯД -->', 1,
        )
        self.assert_error(modified, "структура")

    def test_css_changed_rejected(self):
        self.assert_error(self.template.replace("width: 1100px;", "width: 900px;", 1), "CSS")

    def test_missing_template_field_rejected(self):
        changed = self.template.replace(
            "{{REV_4M_20}}", "{{САМОСТОЯТЕЛЬНЫЙ_РЕЗУЛЬТАТ}}", 1,
        )
        self.assert_error(changed, "обязательные поля")

    def test_internal_annotation_rejected(self):
        source = "Отберем компании по Тест и найдем профильных сотрудников."
        changed = self.ready.replace(source, source + " (со слов клиента)", 1)
        self.assert_error(changed, "служебная атрибуция", "ready")

    def test_footer_note_rejected(self):
        changed = self.template.replace(
            "Слайд 03 / 09", "Слайд 03 / 09 · Гарантия", 1,
        )
        self.assert_error(changed, "номер страницы")

    def test_placeholder_inside_attribute_rejected(self):
        changed = self.ready.replace(
            'href="https://calltalk.ru"', 'href="{{UNFILLED}}"', 1,
        )
        self.assert_error(changed, "поля шаблона", "ready")

    def test_profit_error_rejected(self):
        self.assert_error(self.ready.replace("251 800 руб.", "259 000 руб.", 1),
                          "маржинальная прибыль", "ready")

    def test_payback_error_rejected(self):
        self.assert_error(self.ready.replace("С 3-го договора", "С 4-го договора", 1),
                          "окупаемость", "ready")


    def test_regional_market_label_is_allowed(self):
        changed = self.ready.replace("Организаций в РФ", "В Иркутске и миллионниках", 1)
        self.assert_ok(changed, "ready")

    def test_self_comparison_does_not_hide_template_change(self):
        import shutil
        with tempfile.TemporaryDirectory() as tmp:
            validator = Path(tmp) / "validate_kp_v3.py"
            template = Path(tmp) / "CALL-TALK_Эталон_КП_9_слайдов_v3.html"
            shutil.copyfile(VALIDATOR, validator)
            template.write_text(
                self.template.replace("{{REV_4M_20}}", "{{НЕСОГЛАСОВАННОЕ_ПОЛЕ}}", 1),
                encoding="utf-8",
            )
            result = subprocess.run(
                [sys.executable, str(validator), "--template", str(template)],
                capture_output=True, text=True, check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("контрольного списка", result.stdout)


    def test_internal_note_in_existing_paragraph_rejected(self):
        source = "Отберем компании по Тест и найдем профильных сотрудников."
        self.assertIn(source, self.ready)
        changed = self.ready.replace(source, source + " (с его слов)", 1)
        self.assert_error(changed, "служебный источник", "ready")

    def test_manager_attribution_rejected(self):
        source = "Отберем компании по Тест и найдем профильных сотрудников."
        changed = self.ready.replace(source, source + " (по словам менеджера)", 1)
        self.assert_error(changed, "служебная атрибуция", "ready")

    def test_preliminary_hypothesis_requires_review(self):
        source = "Отберем компании по Тест и найдем профильных сотрудников."
        changed = self.ready.replace(source, source + " Это лишь предварительная гипотеза.", 1)
        self.assert_error(changed, "Редакторское согласование", "ready")

    def test_unnecessary_overlap_disclaimer_requires_review(self):
        source = "Отберем компании по Тест и найдем профильных сотрудников."
        changed = self.ready.replace(source, source + " Возможны пересечения.", 1)
        self.assert_error(changed, "Редакторское согласование", "ready")

    def test_legal_disclaimer_can_be_approved_explicitly(self):
        source = "Отберем компании по Тест и найдем профильных сотрудников."
        changed = self.ready.replace(source, source + " Не является гарантией результата.", 1)
        self.assert_error(changed, "Редакторское согласование", "ready")
        result = run_validator(changed, "ready", ("--allow-editorial-warnings",))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("НА РУЧНОМ СОГЛАСОВАНИИ:", result.stdout)

    def test_static_label_cannot_acquire_explanation(self):
        source = '<div class="revenue-label">потенциальная годовая выручка</div>'
        self.assertIn(source, self.ready)
        changed = self.ready.replace(source, '<div class="revenue-label">потенциальная годовая выручка (примечание)</div>', 1)
        self.assert_error(changed, "фиксированная подпись", "ready")

    def test_normal_forecast_wording_is_allowed(self):
        source = "Отберем компании по Тест и найдем профильных сотрудников."
        changed = self.ready.replace(source, "Отберем компании по расчетным критериям и найдем профильных сотрудников.", 1)
        self.assert_ok(changed, "ready")


if __name__ == "__main__":
    unittest.main(verbosity=2)
