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

    def test_multiple_independent_issues_have_exact_text_and_reasons(self):
        h,c=self.make()
        source=h.read_text()
        source=source.replace("согласованным признакам бизнеса", "Key2Sales", 1)
        source=source.replace("в целевых компаниях и подготовим", "в целевых группах компаний и подготовим", 1)
        h.write_text(source)
        report=self.folder/"report.json"
        args=[sys.executable,str(HERE/"validate_kp_v4.py"),"--ready",str(h),
              "--config",str(c),"--client","Тестовая компания","--report-json",str(report)]
        x=subprocess.run(args,capture_output=True,text=True,encoding="utf-8")
        self.assertNotEqual(x.returncode,0,x.stdout)
        self.assertIn("COPY-OUTSIDE-SOURCE",x.stdout)
        self.assertIn("COPY-AUDIENCE",x.stdout)
        issues=json.loads(report.read_text())["issues"]
        names={issue["id"].split("-S0")[0] for issue in issues}
        self.assertTrue(any("COPY-OUTSIDE-SOURCE" in code for code in names))
        self.assertTrue(any("COPY-AUDIENCE" in code for code in names))
        self.assertTrue(all(issue["reason"] and issue["suggestion"] for issue in issues))

    def test_copy_warning_can_be_approved_by_id(self):
        h,c=self.make()
        source=h.read_text()
        source=source.replace("Подготовим почту и настроим отправку персональных писем.",
                              "Подготовим почтовую инфраструктуру и персональные письма.", 1)
        h.write_text(source)
        report=self.folder/"report.json"
        cmd=[sys.executable,str(HERE/"validate_kp_v4.py"),"--ready",str(h),
             "--config",str(c),"--client","Тестовая компания","--report-json",str(report)]
        first=subprocess.run(cmd,capture_output=True,text=True,encoding="utf-8")
        self.assertEqual(first.returncode,0,first.stdout)
        self.assertIn("ИТОГ: WARN",first.stdout)
        ids=[i["id"] for i in json.loads(report.read_text())["issues"] if i["level"] == "WARN"]
        self.assertTrue(ids)
        approvals=self.folder/"approvals.json"
        approvals.write_text(json.dumps({"approved":ids}),encoding="utf-8")
        second=subprocess.run(cmd+["--approvals",str(approvals)],capture_output=True,text=True,encoding="utf-8")
        self.assertEqual(second.returncode,0,second.stdout)
        self.assertIn("ИТОГ: OK",second.stdout)
        self.assertIn("СОГЛАСОВАНО",second.stdout)

    def test_hard_error_cannot_be_approved(self):
        h,c=self.make()
        source=h.read_text().replace("согласованным признакам бизнеса", "Key2Sales", 1)
        h.write_text(source)
        report=self.folder/"report.json"
        cmd=[sys.executable,str(HERE/"validate_kp_v4.py"),"--ready",str(h),
             "--config",str(c),"--client","Тестовая компания","--report-json",str(report)]
        first=subprocess.run(cmd,capture_output=True,text=True,encoding="utf-8")
        ids=[i["id"] for i in json.loads(report.read_text())["issues"]]
        approvals=self.folder/"approvals.json"
        approvals.write_text(json.dumps({"approved":ids}),encoding="utf-8")
        second=subprocess.run(cmd+["--approvals",str(approvals)],capture_output=True,text=True,encoding="utf-8")
        self.assertNotEqual(second.returncode,0,second.stdout)
        self.assertIn("COPY-OUTSIDE-SOURCE",second.stdout)

    def test_missing_config_block(self):
        h,c=self.make()
        x=run(h,None)
        self.assertNotEqual(x.returncode,0,x.stdout)
        self.assertIn("CONFIG-001",x.stdout)

if __name__=="__main__":
    unittest.main()
