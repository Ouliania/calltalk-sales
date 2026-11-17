#!/usr/bin/env python3
"""Generate a clearly marked TEST example for the V4 validator; never send it to a client."""
from __future__ import annotations
import argparse
import json
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MASTER = ROOT / "CALL-TALK_Эталон_КП_9_слайдов_v4.html"

def rub(x: float) -> str:
    return f"{round(x):,}".replace(",", " ")

def generate(mode: str = "terms", boxes: int = 10, output: Path | None = None, one_month: bool = False) -> tuple[Path, Path]:
    if mode not in ("terms", "qualification"):
        raise ValueError("mode must be terms or qualification")
    if boxes < 1:
        raise ValueError("boxes must be positive")
    touches = 3
    # Tests use explicit 1%-2% response scenarios, not a promise about any real audience.
    factor = boxes / 10
    months = (4, 2) if mode == "terms" else ((1, 1) if one_month else (2, 2))
    monthly = (39000, 56000) if mode == "terms" else (56000, 56000)
    price = (4800, 4800) if mode == "terms" else (4800, 15000)
    variants = []
    for idx in range(2):
        counts = [round(100 * factor), round(500 * factor)] if one_month and mode == "qualification" else [round(600 * factor), round(1500 * (months[idx]-1) * factor)]
        rates = [(0, .01), (.006, .008)] if one_month and idx == 0 else ([(0, 0), (.002, .006)] if one_month else [(.01, .02), (.01, .02)])
        periods = [{"contacts": n, "rate_low": r[0], "rate_high": r[1]} for n,r in zip(counts,rates)]
        lower = [round(n*r[0]) for n,r in zip(counts,rates)]
        upper = [round(n*r[1]) for n,r in zip(counts,rates)]
        min_leads, max_leads = sum(lower), sum(upper)
        leads = round((min_leads + max_leads)/2)
        variants.append(dict(
            months=months[idx], monthly_fixed_rub=monthly[idx], lead_price_rub=price[idx],
            leads_calc=leads, periods=periods))
    cfg = {
        "client":"Тестовая компания", "mode":mode, "boxes":boxes, "touches":touches,
        "avg_check_rub":2_000_000, "conversion":.15, "margin":.15, "variants":variants
    }
    data={
        "КОМПАНИЯ":cfg["client"],"ПРОДУКТ":"систему управления финансами",
        "ВСЕГО":"1 500",
        "РОЛИ_АДРЕСАТОВ":"финансовых директоров",
        "КРИТЕРИИ_ОТБОРА":"согласованным признакам бизнеса",
        "ЦЕЛЕВЫЕ_КОМПАНИИ":"крупных компаний",
        "ЦА_ДЛЯ_ПИСЕМ":"финансовых руководителей",
        "КЕЙС_ОТРАСЛЬ":"IT","КЕЙС_НАЗВАНИЕ":"Тестовый пример",
        "КЕЙС_ЗАДАЧА_И_АУДИТОРИЯ":"Корпоративный софт для предприятий",
        "КЕЙС_КОНТАКТЫ":"1 870", "КЕЙС_ПИСЬМА":"7 480",
        "КЕЙС_ПРЕДЛОЖЕНИЕ":"Предложили автоматизацию учета.",
        "КЕЙС_ЛИДЫ":"23","КЕЙС_СДЕЛКИ":"2","КЕЙС_СРОК":"3 месяца",
        "ЧИСЛО_ЯЩИКОВ":str(boxes),"ЧИСЛО_КАСАНИЙ":str(touches),
        "ЗАГОЛОВОК_СРАВНЕНИЯ":"Два тарифа: на 2 и 4 месяца" if mode=="terms" else "Два формата квалификации",
        "ОПИСАНИЕ_УСЛОВИЙ":"Фикс зависит от срока сотрудничества." if mode=="terms" else "Фикс общий, ставка зависит от глубины квалификации.",
        "КРИТЕРИЙ_ОПЛАТЫ":"Представитель целевой компании подтвердил интерес и запросил предметное обсуждение.",
        "ЭКОНОМИКА_ИСХОДНЫЕ_ДАННЫЕ":"Чек 2 000 000 руб. · конверсия 15% · маржинальность 15%",
        "ОХВАТ_1_МЕСЯЦ":rub(600*factor),
        "ОХВАТ_ДАЛЕЕ_МЕСЯЦ":rub(1500*factor),
    }
    for n in range(1,6):
        data.update({f"СЕГМЕНТ_{n}":f"Отрасль {n}",f"ЗАДАЧА_{n}":"Автоматизация финансов",
            f"ОКВЭД_{n}":"62.01",f"ЧИСЛО_{n}":"300"})
    for i,v in enumerate(variants,1):
        prefix=f"ВАРИАНТ_{i}_"
        contacts=[x["contacts"] for x in v["periods"]]
        lo=[round(n*p["rate_low"]) for n,p in zip(contacts,v["periods"])];hi=[round(n*p["rate_high"]) for n,p in zip(contacts,v["periods"])]
        leads=sum(lo)+sum(hi);leads=round(leads/2)
        months_=v["months"]
        mfix=v["monthly_fixed_rub"];leadprice=v["lead_price_rub"]
        budget=months_*mfix+leads*leadprice
        deals=leads*.15
        revenue=deals*cfg["avg_check_rub"]
        profit=revenue*.15-budget
        payback=math.ceil(budget/(cfg["avg_check_rub"]*.15))
        label="Подтвержденный интерес" if i==1 or mode=="terms" else "Углубленная квалификация"
        data.update({
            prefix+"МЕТКА":"Основной вариант" if i==1 else "Тестовый вариант",
            prefix+"НАЗВАНИЕ":f"Тариф на {months_} месяца" if mode=="terms" else label,
            prefix+"ФИКС_МЕС":rub(mfix),
            prefix+"ЦЕНА_ЛИДА":rub(leadprice),
            prefix+"ФИКС_ВСЕГО":rub(months_*mfix),
            prefix+"СРОК_ТЕКСТ":f"{months_} месяца",
            prefix+"КОНТАКТЫ":rub(sum(contacts)),
            prefix+"ПИСЬМА":rub(sum(contacts)*touches),
            prefix+"ПРОГНОЗ":f"{sum(lo)}–{sum(hi)}",
            prefix+"ТИП_ЛИДА":label,
            prefix+"ЭКОНОМИКА_МЕТКА":f"Воронка и окупаемость · Вариант {i}",
            prefix+"ЭКОНОМИКА_ЗАГОЛОВОК":f"Экономика работы за {months_} месяца",
            prefix+"ВЫРУЧКА":rub(revenue)+" руб.",
            prefix+"ПРИБЫЛЬ":rub(profit)+" руб.",
            prefix+"ОКУПАЕМОСТЬ":f"С {payback}-го договора",
            prefix+"ДОГОВОРЫ":f"≈ {round(deals)} договоров",
            prefix+"БЮДЖЕТ":rub(budget)+" руб.",
            prefix+"ПЕРИОД_1":"Недели 1–2" if one_month else "Месяц 1",
            prefix+"ПЕРИОД_2":"Недели 3–4" if one_month else ("Месяц 2" if months_==2 else f"Месяцы 2–{months_}"),
        })
        for n,t in enumerate((1,2)):
            data.update({prefix+f"КОНТАКТЫ_{t}":rub(contacts[n]),
                prefix+f"ПИСЬМА_{t}":rub(contacts[n]*touches),
                prefix+f"ЛИДЫ_{t}":f"{lo[n]}–{hi[n]}"})
    template=MASTER.read_text(encoding="utf-8")
    missing=set(re.findall(r"\{\{([^{}]+)\}\}",template))-set(data)
    if missing:
        raise ValueError(f"Unfilled keys: {sorted(missing)}")
    filled=re.sub(r"\{\{([^{}]+)\}\}",lambda m:data[m.group(1)],template)
    output=Path(output or (ROOT/"_test_kp_v4.html"))
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(filled,encoding="utf-8")
    cfg_path=output.with_suffix(".json")
    cfg_path.write_text(json.dumps(cfg,ensure_ascii=False,indent=2),encoding="utf-8")
    return output,cfg_path

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--mode",choices=("terms","qualification"),default="terms")
    p.add_argument("--boxes",type=int,default=10)
    p.add_argument("--output",type=Path,default=ROOT/"_test_kp_v4.html")
    p.add_argument("--one-month",action="store_true",help="Synthetic one-month qualification example")
    a=p.parse_args()
    html,config=generate(a.mode,a.boxes,a.output,one_month=a.one_month)
    print(html,config,sep="\n")
