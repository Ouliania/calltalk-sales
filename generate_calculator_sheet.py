import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

wb = openpyxl.Workbook()

# Sheets
ws_main = wb.active
ws_main.title = "Расчёт окупаемости"
ws_ref = wb.create_sheet(title="Справочник")

# Fonts
font_title = Font(name="Calibri", size=15, bold=True, color="14152A")
font_sub = Font(name="Calibri", size=10, italic=True, color="64748B")
font_sec_header = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
font_sec_sub = Font(name="Calibri", size=11, bold=True, color="1E293B")
font_bold = Font(name="Calibri", size=10, bold=True, color="14152A")
font_reg = Font(name="Calibri", size=10, color="14152A")
font_note = Font(name="Calibri", size=9, color="64748B")

font_kpi_huge_teal = Font(name="Calibri", size=16, bold=True, color="0E8A6A")
font_kpi_huge_blue = Font(name="Calibri", size=16, bold=True, color="2563EB")
font_kpi_huge_purple = Font(name="Calibri", size=16, bold=True, color="5B4BD8")
font_kpi_huge_dark = Font(name="Calibri", size=15, bold=True, color="0F172A")
font_concl = Font(name="Calibri", size=10, color="1E1B4B")
font_memo = Font(name="Calibri", size=9, color="475569")

# Fills
fill_primary = PatternFill(start_color="5B4BD8", end_color="5B4BD8", fill_type="solid")
fill_teal = PatternFill(start_color="0E8A6A", end_color="0E8A6A", fill_type="solid")
fill_dark = PatternFill(start_color="14152A", end_color="14152A", fill_type="solid")
fill_yellow_input = PatternFill(start_color="FEF08A", end_color="FEF08A", fill_type="solid")
fill_light_teal = PatternFill(start_color="ECFDF5", end_color="ECFDF5", fill_type="solid")
fill_light_purple = PatternFill(start_color="F5F3FF", end_color="F5F3FF", fill_type="solid")
fill_light_blue = PatternFill(start_color="EFF6FF", end_color="EFF6FF", fill_type="solid")
fill_gray_sec = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")

# Borders
thin_line = Side(border_style="thin", color="CBD5E1")
teal_line = Side(border_style="medium", color="0E8A6A")
box_border = Border(left=thin_line, right=thin_line, top=thin_line, bottom=thin_line)
kpi_border_teal = Border(left=teal_line, right=teal_line, top=teal_line, bottom=teal_line)

# Alignments
align_left = Alignment(horizontal="left", vertical="center")
align_right = Alignment(horizontal="right", vertical="center")
align_center = Alignment(horizontal="center", vertical="center")
align_concl = Alignment(horizontal="left", vertical="top", wrap_text=True)

# -------------------------------------------------------------
# 1. SETUP REFERENCE SHEET
# -------------------------------------------------------------
ws_ref["A1"] = "Справочник условий Call-Talk"
ws_ref["A1"].font = font_title
ws_ref["A2"] = "Значения отсюда подставляются в калькулятор. Цены меняются только здесь."
ws_ref["A2"].font = font_sub

ws_ref["A4"] = "ФИКС ПО СРОКАМ ДОГОВОРА"
ws_ref["A4"].font = font_bold
ws_ref["A5"] = "Срок, мес."
ws_ref["B5"] = "Фикс в месяц, руб."
ws_ref["C5"] = "Фикс за срок, руб."
ws_ref["D5"] = "Примечание"
for col in ["A5", "B5", "C5", "D5"]:
    ws_ref[col].font = font_sec_header
    ws_ref[col].fill = fill_primary
    ws_ref[col].alignment = align_center

fix_data = [
    (2, 56000, "=A6*B6", "Тестовый пилот (по согласованию)"),
    (3, 48000, "=A7*B7", "Промежуточный тариф"),
    (4, 39000, "=A8*B8", "Основной флагманский срок (скидка 46%)")
]
for r_idx, row in enumerate(fix_data, start=6):
    ws_ref[f"A{r_idx}"] = row[0]
    ws_ref[f"B{r_idx}"] = row[1]
    ws_ref[f"C{r_idx}"] = row[2]
    ws_ref[f"D{r_idx}"] = row[3]
    ws_ref[f"A{r_idx}"].alignment = align_center
    ws_ref[f"B{r_idx}"].number_format = "#,##0"
    ws_ref[f"C{r_idx}"].number_format = "#,##0"
    for c in ["A", "B", "C", "D"]:
        ws_ref[f"{c}{r_idx}"].border = box_border

# -------------------------------------------------------------
# 2. SETUP MAIN SHEET: РАСЧЁТ ОКУПАЕМОСТИ
# -------------------------------------------------------------
ws_main["A1"] = "КАЛЬКУЛЯТОР ОКУПАЕМОСТИ B2B-АУТРИЧА CALL-TALK"
ws_main["A1"].font = font_title
ws_main["A2"] = "Жёлтые ячейки заполняются со слов клиента на встрече. Точка безубыточности и выводы — сразу наверху в правом блоке."
ws_main["A2"].font = font_sub

# Section 1: Inputs (Left Column A-C)
ws_main.merge_cells("A3:C3")
ws_main["A3"] = "1. ПАРАМЕТРЫ ПРОЕКТА (ВВОД ДАННЫХ)"
ws_main["A3"].font = font_sec_header
ws_main["A3"].fill = fill_primary
ws_main["A3"].alignment = align_center

inputs = [
    (4, "Срок договора, мес.", 4, "2 или 4 мес. Основной срок — 4", "0"),
    (5, "СРЕДНИЙ ЧЕК СДЕЛКИ, руб.", 1000000, "Сумма контракта / заказа клиента", "#,##0"),
    (6, "МАРЖИНАЛЬНОСТЬ СДЕЛКИ, %", 0.12, "Строго 10–12%, максимум 15% (стандарт B2B)", "0.0%"),
    (7, "Конверсия лида в сделку, %", 0.15, "Оценка отдела продаж клиента (дефолт 15%)", "0.0%"),
    (8, "Почтовые ящики Яндекс 360, шт.", 10, "10, 15, 20 или 30 ящиков", "0"),
    (9, "Ставка за 1 лид, руб.", 2800, "Оплата за лид с подтвержденным интересом", "#,##0"),
    (10, "Фикс в месяц, руб.", "=INDEX('Справочник'!$B$6:$B$8,MATCH(B4,'Справочник'!$A$6:$A$8,0))", "Из справочника по сроку договора", "#,##0"),
    (11, "Прогноз лидов за срок, шт.", "=ROUND(IF(B4=4,78,IF(B4=2,34,56))*(B8/10),0)", "Дефолт тарифа с учетом ящиков (x1, x1.5, x2, x3) или вручную", "0"),
    (12, "Затраты на Яндекс 360 (~300 руб./ящик в мес), руб.", "=B8*B4*300", "Оплачивает клиент Яндексу или нам под ключ", "#,##0")
]

for row_idx, label, val, note, num_fmt in inputs:
    ws_main[f"A{row_idx}"] = label
    ws_main[f"B{row_idx}"] = val
    ws_main[f"C{row_idx}"] = note
    ws_main[f"A{row_idx}"].font = font_bold if "ЧЕК" in label or "МАРЖИН" in label else font_reg
    ws_main[f"B{row_idx}"].font = font_bold
    ws_main[f"C{row_idx}"].font = font_note
    ws_main[f"B{row_idx}"].number_format = num_fmt
    ws_main[f"A{row_idx}"].border = box_border
    ws_main[f"B{row_idx}"].border = box_border
    ws_main[f"C{row_idx}"].border = box_border
    if row_idx in [4, 5, 6, 7, 8, 9, 11]:
        ws_main[f"B{row_idx}"].fill = fill_yellow_input
    else:
        ws_main[f"B{row_idx}"].fill = fill_gray_sec

# Section 2: Payback Focus (Right Column E-I) - САМОЕ ГЛАВНОЕ НАВЕРХУ!
ws_main.merge_cells("E3:I3")
ws_main["E3"] = "2. ГЛАВНОЕ: ОКУПАЕМОСТЬ И ТОЧКА БЕЗУБЫТОЧНОСТИ"
ws_main["E3"].font = font_sec_header
ws_main["E3"].fill = fill_teal
ws_main["E3"].alignment = align_center

# Row 4: Deals to break-even & Profit per deal
ws_main["E4"] = "СДЕЛОК ДЛЯ 100% ОКУПАЕМОСТИ:"
ws_main["E4"].font = font_bold
ws_main["F4"] = "=ROUNDUP(F10/H4, 0)"
ws_main["F4"].font = font_kpi_huge_teal
ws_main["F4"].alignment = align_center
ws_main["F4"].fill = fill_light_teal
ws_main["F4"].border = kpi_border_teal

ws_main["G4"] = "Валовая прибыль с 1 сделки, руб.:"
ws_main["G4"].font = font_bold
ws_main["H4"] = "=B5*B6"
ws_main["H4"].font = font_bold
ws_main["H4"].number_format = "#,##0"
ws_main["H4"].alignment = align_right
ws_main["H4"].border = box_border
ws_main["I4"] = "Чек × Маржа %"
ws_main["I4"].font = font_note

# Row 6: Needed conversion & Net profit
ws_main["E6"] = "НЕОБХОДИМАЯ КОНВЕРСИЯ В СДЕЛКУ:"
ws_main["E6"].font = font_bold
ws_main["F6"] = "=F4/B11"
ws_main["F6"].font = font_kpi_huge_blue
ws_main["F6"].number_format = "0.0%"
ws_main["F6"].alignment = align_center
ws_main["F6"].fill = fill_light_blue
ws_main["F6"].border = box_border

ws_main["G6"] = "ЧИСТАЯ ПРИБЫЛЬ КЛИЕНТА, руб.:"
ws_main["G6"].font = font_bold
ws_main["H6"] = "=H8-F10"
ws_main["H6"].font = font_kpi_huge_teal
ws_main["H6"].number_format = "#,##0"
ws_main["H6"].alignment = align_right
ws_main["H6"].fill = fill_light_teal
ws_main["H6"].border = kpi_border_teal
ws_main["I6"] = "Прибыль сверх затрат"
ws_main["I6"].font = font_note

# Row 8: Closed deals & Total Gross Profit
ws_main["E8"] = "Прогноз закрытых сделок, шт.:"
ws_main["E8"].font = font_bold
ws_main["F8"] = "=ROUND(B11*B7, 0)"
ws_main["F8"].font = font_bold
ws_main["F8"].alignment = align_center
ws_main["F8"].border = box_border

ws_main["G8"] = "Валовая прибыль от договоров, руб.:"
ws_main["G8"].font = font_bold
ws_main["H8"] = "=F8*H4"
ws_main["H8"].font = font_bold
ws_main["H8"].number_format = "#,##0"
ws_main["H8"].alignment = align_right
ws_main["H8"].border = box_border
ws_main["I8"] = "Сделки × Маржа со сделки"
ws_main["I8"].font = font_note

# Row 10: Total Budget & ROI
ws_main["E10"] = "ОБЩИЙ БЮДЖЕТ CALL-TALK, руб.:"
ws_main["E10"].font = font_bold
ws_main["F10"] = "=B10*B4+B11*B9"
ws_main["F10"].font = font_kpi_huge_dark
ws_main["F10"].number_format = "#,##0"
ws_main["F10"].alignment = align_center
ws_main["F10"].fill = fill_gray_sec
ws_main["F10"].border = box_border

ws_main["G10"] = "ОКУПАЕМОСТЬ ЗАТРАТ (ROI), %:"
ws_main["G10"].font = font_bold
ws_main["H10"] = "=H6/F10"
ws_main["H10"].font = font_kpi_huge_purple
ws_main["H10"].number_format = "+0%"
ws_main["H10"].alignment = align_right
ws_main["H10"].fill = fill_light_purple
ws_main["H10"].border = box_border
ws_main["I10"] = "Чистая прибыль ÷ Бюджет"
ws_main["I10"].font = font_note

# Row 12-14: Conclusions for client
ws_main.merge_cells("E12:I12")
ws_main["E12"] = "ВЫВОДЫ ПО ОКУПАЕМОСТИ ДЛЯ КЛИЕНТА:"
ws_main["E12"].font = font_sec_sub
ws_main["E12"].fill = fill_gray_sec

ws_main.merge_cells("E13:I14")
concl_formula = (
    '="1. Для 100% возврата бюджета ("&TEXT(F10,"#,##0")&" руб.) достаточно закрыть ВСЕГО "&F4&" сделок из "&B11&" лидов (конверсия всего "&TEXT(F6,"0.0%")&")."&CHAR(10)&'
    '"2. Финансовый результат: при конверсии "&TEXT(B7,"0%")&" закрывается "&F8&" сделок на "&TEXT(F8*B5,"#,##0")&" руб. выручки и +"&TEXT(H6,"#,##0")&" руб. чистой прибыли (ROI "&TEXT(H10,"+0%")&")."&CHAR(10)&'
    '"3. Инфраструктура: "&B8&" ящиков Яндекс 360. Оплата лидов строго за подтвержденный интерес. Нецелевые ответы — 0 руб."'
)
ws_main["E13"] = concl_formula
ws_main["E13"].font = font_concl
ws_main["E13"].fill = fill_light_purple
ws_main["E13"].alignment = align_concl
ws_main["E13"].border = box_border

# -------------------------------------------------------------
# 3. SECONDARY METRICS (СДВИНУТЫ НИЖЕ)
# -------------------------------------------------------------
ws_main.merge_cells("A16:I16")
ws_main["A16"] = "3. ВТОРОСТЕПЕННЫЕ ПОКАЗАТЕЛИ И ДЕТАЛИЗАЦИЯ (СДВИНУТЫ НИЖЕ)"
ws_main["A16"].font = font_sec_header
ws_main["A16"].fill = fill_dark
ws_main["A16"].alignment = align_center

# Secondary metrics grid
sec_metrics = [
    (18, "Привлеченный оборот (выручка), руб.", "=F8*B5", "Сделки × Чек", "#,##0"),
    (19, "Доля расходов Call-Talk в обороте, %", "=F10/B18", "Бюджет ÷ Выручка", "0.0%"),
    (20, "Стоимость привлечения клиента (CAC), руб.", "=F10/F8", "Бюджет ÷ Сделки", "#,##0"),
    (21, "Платеж при старте (фикс за весь срок), руб.", "=B10*B4", "Оплата инфраструктуры", "#,##0"),
    (22, "Кратность возврата бюджета (ROMI), раз", "=H8/F10", "Валовая прибыль ÷ Бюджет", "0.0x")
]

for r_idx, label, formula, note, num_fmt in sec_metrics:
    ws_main[f"A{r_idx}"] = label
    ws_main[f"B{r_idx}"] = formula
    ws_main[f"C{r_idx}"] = note
    ws_main[f"A{r_idx}"].font = font_reg
    ws_main[f"B{r_idx}"].font = font_bold
    ws_main[f"C{r_idx}"].font = font_note
    ws_main[f"B{r_idx}"].number_format = num_fmt
    ws_main[f"A{r_idx}"].border = box_border
    ws_main[f"B{r_idx}"].border = box_border
    ws_main[f"C{r_idx}"].border = box_border

# Monthly timeline table (Columns E-I, Rows 18-24)
ws_main.merge_cells("E17:I17")
ws_main["E17"] = "ПОМЕСЯЧНАЯ ВОРОНКА И ГРАФИК ПЛАТЕЖЕЙ"
ws_main["E17"].font = font_sec_sub
ws_main["E17"].fill = fill_gray_sec
ws_main["E17"].alignment = align_center

month_headers = ["Месяц", "Лидов, шт.", "Лиды, руб.", "Фикс, руб.", "Итого за месяц, руб."]
for c_idx, h in enumerate(month_headers, start=5):
    col_letter = get_column_letter(c_idx)
    ws_main[f"{col_letter}18"] = h
    ws_main[f"{col_letter}18"].font = font_bold
    ws_main[f"{col_letter}18"].fill = fill_gray_sec
    ws_main[f"{col_letter}18"].border = box_border
    ws_main[f"{col_letter}18"].alignment = align_center

monthly_rows = [
    (19, "1-й мес (прогрев)", 11, "=F19*$B$9", "=IF(1<=$B$4,$B$10,0)", "=G19+H19"),
    (20, "2-й мес (масштаб)", "=ROUND(($B$11-11)/($B$4-1), 0)", "=F20*$B$9", "=IF(2<=$B$4,$B$10,0)", "=G20+H20"),
    (21, "3-й мес (отрасли)", "=IF(3<=$B$4,ROUND(($B$11-11)/($B$4-1), 0),0)", "=F21*$B$9", "=IF(3<=$B$4,$B$10,0)", "=G21+H21"),
    (22, "4-й мес (дожим)", "=IF(4<=$B$4,$B$11-11-F20-F21,0)", "=F22*$B$9", "=IF(4<=$B$4,$B$10,0)", "=G22+H22"),
    (23, "ИТОГО", "=SUM(F19:F22)", "=SUM(G19:G22)", "=SUM(H19:H22)", "=SUM(I19:I22)")
]

for r_idx, name, leads, leads_rub, fix_rub, total_rub in monthly_rows:
    ws_main[f"E{r_idx}"] = name
    ws_main[f"F{r_idx}"] = leads
    ws_main[f"G{r_idx}"] = leads_rub
    ws_main[f"H{r_idx}"] = fix_rub
    ws_main[f"I{r_idx}"] = total_rub
    for c_idx in range(5, 10):
        c_letter = get_column_letter(c_idx)
        ws_main[f"{c_letter}{r_idx}"].border = box_border
        if r_idx == 23:
            ws_main[f"{c_letter}{r_idx}"].font = font_bold
            ws_main[f"{c_letter}{r_idx}"].fill = fill_gray_sec
        else:
            ws_main[f"{c_letter}{r_idx}"].font = font_reg
    ws_main[f"G{r_idx}"].number_format = "#,##0"
    ws_main[f"H{r_idx}"].number_format = "#,##0"
    ws_main[f"I{r_idx}"].number_format = "#,##0"

# Column widths
ws_main.column_dimensions["A"].width = 38
ws_main.column_dimensions["B"].width = 16
ws_main.column_dimensions["C"].width = 36
ws_main.column_dimensions["D"].width = 4
ws_main.column_dimensions["E"].width = 32
ws_main.column_dimensions["F"].width = 14
ws_main.column_dimensions["G"].width = 32
ws_main.column_dimensions["H"].width = 16
ws_main.column_dimensions["I"].width = 24

ws_ref.column_dimensions["A"].width = 18
ws_ref.column_dimensions["B"].width = 20
ws_ref.column_dimensions["C"].width = 22
ws_ref.column_dimensions["D"].width = 45

# Save files
wb.save("КАЛЬКУЛЯТОР_ОКУПАЕМОСТИ_CALLTALK.xlsx")
wb.save("calculator/КАЛЬКУЛЯТОР_ОКУПАЕМОСТИ_CALLTALK.xlsx")
print("Workbook saved successfully!")
