#!/usr/bin/env python3
"""Regression tests: OK, WARN, BLOCK, two modes, and hard financial consistency."""
from __future__ import annotations
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from generate_test_example import generate

def run(html:Path,config:Path|None=None)->subprocess.CompletedProcess:
    args=[sys.executable,str(HERE/"validate_kp_v4.py"),"--ready",str(html),"--client","Тестовая компания"]
    if config is not None:
        args.extend(["--config",str(config)])
    return subprocess.run(args,capture_output=True,text=True,encoding="utf-8")

class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder=Path(self.tmp.name)

    def make(self,mode="terms",boxes=10):
        return generate(mode,boxes,self.folder/"ready.html")

    def test_reference_is_original_v4(self):
        cp=subprocess.run([sys.executable,str(HERE/"validate_kp_v4.py"),
            "--template",str(HERE/"CALL-TALK_Эталон_КП_9_слайдов_v4.html")],
            capture_output=True,text=True,encoding="utf-8")
        self.assertEqual(cp.returncode,0,cp.stdout+cp.stderr)
        self.assertIn("ИТОГ: OK",cp.stdout)

    def test_standard_two_four_months_ok(self):
        h,c=self.make()
        x=run(h,c)
        self.assertEqual(x.returncode,0,x.stdout+x.stderr)
        self.assertIn("ИТОГ: OK",x.stdout)

    def test_qualification_ok(self):
        h,c=self.make("qualification")
        x=run(h,c)
        self.assertEqual(x.returncode,0,x.stdout+x.stderr)
        self.assertIn("ИТОГ: OK",x.stdout)

    def test_twenty_boxes_warn(self):
        h,c=self.make(boxes=20)
        x=run(h,c)
        self.assertEqual(x.returncode,0,x.stdout+x.stderr)
        self.assertIn("WARN | CONFIG-BOXES",x.stdout)
        self.assertIn("ИТОГ: WARN",x.stdout)

    def test_thirty_boxes_warn(self):
        h,c=self.make(boxes=30)
        x=run(h,c)
        self.assertEqual(x.returncode,0,x.stdout+x.stderr)
        self.assertIn("CONFIG-BOXES",x.stdout)

    def test_illegal_hard_outreach_block(self):
        h,c=self.make(boxes=20)
        s=h.read_text()
        s=s.replace("Подготовим почту и настроим отправку персональных писем.",
                    "Жесткий outreach 20 почтовыми ящиками.")
        h.write_text(s)
        x=run(h,c)
        self.assertNotEqual(x.returncode,0,x.stdout)
        self.assertIn("BLOCK",x.stdout)

    def test_wrong_budget_block(self):
        h,c=self.make()
        s=h.read_text()
        cfg=json.loads(c.read_text())
        v=cfg["variants"][1]
        expected=v["months"]*v["monthly_fixed_rub"]+v["leads_calc"]*v["lead_price_rub"]
        target=f"{expected:,}".replace(","," ")+" руб."
        # Replace a single matching occurrence in the budget cell, not formulas.
        self.assertIn(target,s)
        s=s.replace(target,"9 999 999 руб.",1)
        h.write_text(s)
        x=run(h,c)
        self.assertNotEqual(x.returncode,0,x.stdout)
        self.assertIn("MATH",x.stdout)

    def test_missing_placeholder_block(self):
        h,c=self.make()
        s=h.read_text().replace("Тестовая компания","{{КОМПАНИЯ}}",1)
        h.write_text(s)
        x=run(h,c)
        self.assertNotEqual(x.returncode,0,x.stdout)
        self.assertIn("незаполненные",x.stdout)

    def test_added_explainer_block(self):
        h,c=self.make()
        s=h.read_text().replace("Выручка от заключенных договоров.",
         "Выручка от заключенных договоров. Следует отметить, что мы не уверены в расчетах.",1)
        h.write_text(s)
        x=run(h,c)
        self.assertNotEqual(x.returncode,0,x.stdout)
        self.assertIn("BLOCK",x.stdout)

    def test_structural_change_block(self):
        h,c=self.make()
        s=h.read_text().replace('<div class="benefit-cards">','<div class="benefit-cards"><div>Extra</div>',1)
        h.write_text(s)
        x=run(h,c)
        self.assertNotEqual(x.returncode,0,x.stdout)
        self.assertIn("STRUCT",x.stdout+" STRUCT" if "изменено число" in x.stdout else x.stdout)

    def test_changed_assumptions_block(self):
        h,c=self.make()
        s=h.read_text().replace("конверсия 15%","конверсия 25%")
        h.write_text(s)
        x=run(h,c)
        self.assertNotEqual(x.returncode,0,x.stdout)
        self.assertIn("MATH-ASSUMPTIONS",x.stdout)

    def test_missing_config_block(self):
        h,c=self.make()
        x=run(h,None)
        self.assertNotEqual(x.returncode,0,x.stdout)
        self.assertIn("CONFIG-001",x.stdout)

if __name__=="__main__":
    unittest.main()
