#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import base64
import subprocess

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(base_dir)
    photo_path = os.path.join(parent_dir, "photo.jpg")

    if os.path.exists(photo_path):
        with open(photo_path, "rb") as f:
            photo_b64 = base64.b64encode(f.read()).decode("utf-8")
        photo_src = f"data:image/jpeg;base64,{photo_b64}"
    else:
        photo_src = ""

    html_content = f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>CALL-TALK — Коммерческое предложение | Квиз, плиз!</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">
<style>
  :root {{
    --primary: #5B4BD8;
    --primary-dark: #4738B5;
    --primary-light: #F0ECFF;
    --primary-border: #DCD5FA;
    --teal: #0da559;
    --teal-light: #EAF8F3;
    --teal-border: #BCE8DA;
    --coral: #C66E4A;
    --coral-light: #FFF1E9;
    --coral-border: #FAD7C8;
    --dark: #0F172A;
    --text: #14152A;
    --text-muted: #4B5563;
    --text-light: #6B7280;
    --border: #E2E8F0;
    --bg-page: #64748B;
    --bg-card: #FFFFFF;
    --bg-alt: #F8FAFC;
  }}

  * {{
    box-sizing: border-box;
    margin: 0;
    padding: 0;
    -webkit-print-color-adjust: exact !important;
    print-color-adjust: exact !important;
  }}

  body {{
    font-family: 'Manrope', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background-color: var(--bg-page);
    color: var(--text);
    font-size: 14px;
    line-height: 1.5;
    -webkit-font-smoothing: antialiased;
  }}

  .presentation {{
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 24px;
    padding: 24px 0;
  }}

  .slide {{
    width: 1100px;
    height: 618.75px;
    min-width: 1100px;
    min-height: 618.75px;
    max-width: 1100px;
    max-height: 618.75px;
    background: #FFFFFF;
    position: relative;
    overflow: hidden;
    padding: 34px 46px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
  }}

  /* HEADER */
  .slide-header {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    position: relative;
    z-index: 2;
    padding-bottom: 10px;
    border-bottom: 1px solid var(--border);
  }}

  .header-brand {{
    display: flex;
    align-items: center;
    gap: 12px;
  }}

  .logo-box {{
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 16px;
    font-weight: 900;
    color: var(--text);
    letter-spacing: -0.02em;
  }}

  .logo-icon {{
    width: 26px;
    height: 26px;
    background: var(--primary);
    color: white;
    border-radius: 6px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 12px;
    font-weight: 900;
  }}

  .header-badge {{
    background: var(--primary-light);
    color: var(--primary);
    padding: 4px 12px;
    border-radius: 999px;
    font-size: 12px;
    font-weight: 700;
  }}

  .header-link {{
    font-size: 13px;
    font-weight: 700;
    color: var(--primary);
    text-decoration: none;
  }}

  /* BODY */
  .slide-body {{
    flex: 1;
    display: flex;
    flex-direction: column;
    justify-content: center;
    padding: 14px 0;
    position: relative;
    z-index: 2;
  }}

  .category-badge {{
    display: inline-flex;
    align-items: center;
    background: var(--primary-light);
    color: var(--primary);
    padding: 3px 10px;
    border-radius: 999px;
    font-size: 11px;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    width: fit-content;
    margin-bottom: 6px;
  }}

  .slide-title-h1 {{
    font-size: 34px;
    font-weight: 900;
    color: var(--text);
    line-height: 1.2;
    letter-spacing: -0.03em;
  }}

  .slide-title-h2 {{
    font-size: 25px;
    font-weight: 800;
    color: var(--text);
    line-height: 1.25;
    letter-spacing: -0.02em;
  }}

  .slide-lead {{
    font-size: 13.5px;
    color: var(--text-muted);
    line-height: 1.45;
    margin-top: 3px;
    margin-bottom: 12px;
  }}

  /* FOOTER */
  .slide-footer {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding-top: 8px;
    border-top: 1px solid var(--border);
    font-size: 11.5px;
    color: var(--text-light);
    font-weight: 500;
    position: relative;
    z-index: 2;
  }}

  /* CARDS */
  .card {{
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 16px 18px;
  }}

  .card-alt {{
    background: var(--bg-alt);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 14px 16px;
  }}

  /* TABLES */
  .data-table {{
    width: 100%;
    border-collapse: collapse;
    border-radius: 10px;
    overflow: hidden;
    border: 1px solid var(--border);
    background: #FFFFFF;
  }}

  .data-table th {{
    background: var(--bg-alt);
    padding: 8px 12px;
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--text-light);
    text-align: left;
    border-bottom: 1px solid var(--border);
  }}

  .data-table td {{
    padding: 8px 12px;
    font-size: 12.5px;
    color: var(--text);
    border-bottom: 1px solid var(--border);
    vertical-align: middle;
  }}

  .data-table tr:last-child td {{
    border-bottom: none;
  }}

  .data-table tr.total-row td {{
    background: var(--primary-light);
    font-weight: 800;
    color: var(--primary);
    font-size: 12.5px;
    border-top: 2px solid var(--primary-border);
  }}

  .accent-purple {{
    color: var(--primary);
    font-weight: 800;
  }}

  @page {{
    size: 1100px 618.75px;
    margin: 0;
  }}

  @media print {{
    html, body {{
      width: 1100px;
      height: 618.75px;
      margin: 0 !important;
      padding: 0 !important;
      background: #FFFFFF !important;
      -webkit-print-color-adjust: exact !important;
      print-color-adjust: exact !important;
    }}
    .presentation {{
      display: block !important;
      padding: 0 !important;
      margin: 0 !important;
      gap: 0 !important;
    }}
    .slide {{
      width: 1100px !important;
      height: 618.75px !important;
      min-width: 1100px !important;
      min-height: 618.75px !important;
      max-width: 1100px !important;
      max-height: 618.75px !important;
      margin: 0 !important;
      page-break-after: always !important;
      break-after: page !important;
      page-break-inside: avoid !important;
      break-inside: avoid !important;
      overflow: hidden !important;
    }}
    .slide:last-child {{
      page-break-after: avoid !important;
      break-after: avoid !important;
    }}
  }}
</style>
</head>
<body>

<div class="presentation">

  <!-- ==================== СЛАЙД 1: ТИТУЛ ==================== -->
  <div class="slide">
    <div class="slide-header">
      <div class="header-brand">
        <div class="logo-box"><div class="logo-icon">CT</div> Call-Talk</div>
        <div class="header-badge">B2B Лидогенерация & Email-Аутрич</div>
      </div>
      <a href="https://calltalk.ru" class="header-link">calltalk.ru ↗</a>
    </div>

    <div class="slide-body" style="justify-content: center; padding: 36px 0;">
      <div style="max-width: 950px;">
        <div class="category-badge">КОММЕРЧЕСКОЕ ПРЕДЛОЖЕНИЕ</div>
        <h1 class="slide-title-h1" style="margin-top: 10px; margin-bottom: 16px;">
          Привлечение B2B-клиентов для «Квиз, плиз!»<br>через <span style="color: var(--primary);">персонализированный email-аутрич</span>
        </h1>
        <p style="font-size: 15.5px; font-weight: 500; color: var(--text-muted); line-height: 1.5; max-width: 840px;">
          Системный поток целевых запросов на организацию корпоративных интеллектуальных игр от HR-директоров компаний <span class="accent-purple">от 100+ сотрудников</span> и ведущих Event-агентств Москвы и МО. Оплата за результат.
        </p>
      </div>
    </div>

    <div class="slide-footer">
      <div>Call-Talk — Системный аутрич для «Квиз, плиз!»</div>
      <div>Слайд 01 / 09</div>
    </div>
  </div>

  <!-- ==================== СЛАЙД 2: ЦЕЛЕВОЙ РЫНОК И ЕМКОСТЬ ==================== -->
  <div class="slide">
    <div class="slide-header">
      <div class="header-brand">
        <div class="logo-box"><div class="logo-icon">CT</div> Call-Talk</div>
        <div class="header-badge">Анализ рынка: Квиз, плиз!</div>
      </div>
      <a href="https://calltalk.ru" class="header-link">calltalk.ru ↗</a>
    </div>

    <div class="slide-body">
      <div>
        <h2 class="slide-title-h2">Кому и как мы выходим на диалог</h2>
        <div class="slide-lead">
          Фокусируемся на платежеспособных сегментах Москвы и МО с бюджетом на корпоративные события: компании <span class="accent-purple">от 100+ сотрудников</span> и профессиональные Event-агентства.
        </div>
      </div>

      <!-- ПЛАШКА ПАРАМЕТРОВ АУДИТОРИИ -->
      <div class="card-alt" style="margin-bottom: 10px; padding: 10px 14px;">
        <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 14px; font-size: 11.5px; line-height: 1.4;">
          <div>
            <strong style="color: var(--text); display: block; margin-bottom: 2px;">Целевые должности (ЛПР):</strong>
            <span style="color: var(--text-muted);">HR-директор (HRD), руководитель по корпоративной культуре, Head of C&B, Head of Internal Communications, T&D, Event-директора.</span>
          </div>
          <div>
            <strong style="color: var(--text); display: block; margin-bottom: 2px;">Приоритет 1 · Корпорации (60%):</strong>
            <span style="color: var(--text-muted);">IT, финтех, банки, ритейл, FMCG, сырье, фарминдустрия (компании <span class="accent-purple">от 100+ сотрудников</span>, средний рабочий чек 150 000 руб).</span>
          </div>
          <div>
            <strong style="color: var(--text); display: block; margin-bottom: 2px;">Приоритет 2 · Event-агентства (30%):</strong>
            <span style="color: var(--text-muted);">Организаторы корпоративов, MICE и агентства праздников. Повторные заказы под ключ и расширение пула проверенных подрядчиков.</span>
          </div>
        </div>
      </div>

      <!-- ТАБЛИЦА БАЗЫ -->
      <table class="data-table">
        <thead>
          <tr>
            <th style="width: 140px;">ОКВЭД</th>
            <th>Описание сегмента</th>
            <th style="width: 240px; text-align: right;">Оценка базы (Москва и МО)</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td style="font-weight: 700; color: var(--primary);">62.01, 62.02, 63.11</td>
            <td>IT-разработка, системная интеграция, интернет-сервисы и финтех (<span class="accent-purple">от 100+ сотрудников</span>)</td>
            <td style="text-align: right; font-weight: 700;">≈ 1 850 компаний</td>
          </tr>
          <tr>
            <td style="font-weight: 700; color: var(--primary);">64.19, 64.99, 65.12</td>
            <td>Банки, финансовый сектор, страховые и инвестиционные группы (<span class="accent-purple">от 100+ сотрудников</span>)</td>
            <td style="text-align: right; font-weight: 700;">≈ 650 компаний</td>
          </tr>
          <tr>
            <td style="font-weight: 700; color: var(--primary);">46, 47, 70</td>
            <td>Крупный сетевой ритейл, e-commerce, дистрибуция и FMCG-бренды (<span class="accent-purple">от 100+ сотрудников</span>)</td>
            <td style="text-align: right; font-weight: 700;">≈ 2 400 компаний</td>
          </tr>
          <tr>
            <td style="font-weight: 700; color: var(--primary);">10-33, 49, 52</td>
            <td>Производственные холдинги, логистика, транспорт и фармацевтика (<span class="accent-purple">от 100+ сотрудников</span>)</td>
            <td style="text-align: right; font-weight: 700;">≈ 2 100 компаний</td>
          </tr>
          <tr>
            <td style="font-weight: 700; color: var(--primary);">82.30, 90.02, 73.11</td>
            <td>Профессиональные Event-агентства, организаторы конференций и корпоративных праздников</td>
            <td style="text-align: right; font-weight: 700;">≈ 1 200 компаний</td>
          </tr>
          <tr class="total-row">
            <td>ИТОГО</td>
            <td>Суммарная емкость адресного рынка с высоким бюджетом на корпоративы (Москва и МО)</td>
            <td style="text-align: right;">≈ 8 200+ компаний</td>
          </tr>
        </tbody>
      </table>

      <div style="font-size: 11px; color: var(--text-light); margin-top: 8px;">
        * Емкость адресного рынка позволяет вести непрерывный аутрич в течение всего года, системно загружая расписание как в предновогодний сезон, так и на гендерные праздники (23 февраля / 8 марта) и летние тимбилдинги.
      </div>
    </div>

    <div class="slide-footer">
      <div>Call-Talk — Системный аутрич для «Квиз, плиз!»</div>
      <div>Слайд 02 / 09</div>
    </div>
  </div>

  <!-- ==================== СЛАЙД 3: МЕТОДОЛОГИЯ (4 ШАГА В РЯД) ==================== -->
  <div class="slide">
    <div class="slide-header">
      <div class="header-brand">
        <div class="logo-box"><div class="logo-icon">CT</div> Call-Talk</div>
        <div class="header-badge">Методология запуска</div>
      </div>
      <a href="https://calltalk.ru" class="header-link">calltalk.ru ↗</a>
    </div>

    <div class="slide-body">
      <div>
        <h2 class="slide-title-h2">Управляемый цикл лидогенерации</h2>
        <div class="slide-lead">
          Мы берем на себя полный цикл подготовки и запуска. Ваша команда подключается только к диалогам с заинтересованными лицами, принимающими решения.
        </div>
      </div>

      <!-- СЕТКА ИЗ 4 ШАГОВ -->
      <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px;">
        
        <!-- Шаг 1 -->
        <div class="card" style="display: flex; flex-direction: column; justify-content: space-between; height: 320px;">
          <div>
            <div style="font-size: 11px; font-weight: 800; color: var(--primary); text-transform: uppercase; margin-bottom: 6px;">Шаг 01</div>
            <h3 style="font-size: 15.5px; font-weight: 800; color: var(--text); margin-bottom: 8px; line-height: 1.3;">
              Сбор и валидация базы
            </h3>
            <p style="font-size: 11.5px; color: var(--text-muted); line-height: 1.45;">
              Выгружаем компании Москвы и МО по точным фильтрам (компании <span class="accent-purple">от 100+ сотрудников</span>, выручка, отрасли). Вручную отбираем профильных ЛПР (HRD, C&B, Event), верифицируем почты через SMTP-проверку (0% спам-ловушек) и исключаем текущих клиентов.
            </p>
          </div>
          <div style="background: var(--bg-alt); border-radius: 8px; padding: 8px 10px; font-size: 11px; font-weight: 700; color: var(--text);">
            Валидация SMTP и ручной отбор
          </div>
        </div>

        <!-- Шаг 2 -->
        <div class="card" style="display: flex; flex-direction: column; justify-content: space-between; height: 320px;">
          <div>
            <div style="font-size: 11px; font-weight: 800; color: var(--primary); text-transform: uppercase; margin-bottom: 6px;">Шаг 02</div>
            <h3 style="font-size: 15.5px; font-weight: 800; color: var(--text); margin-bottom: 8px; line-height: 1.3;">
              Анализ болей и офферы
            </h3>
            <p style="font-size: 11.5px; color: var(--text-muted); line-height: 1.45;">
              Формируем персонализированные цепочки из 3 писем: для HRD — решение задачи сплочения команды и готовый праздник под ключ без головной боли; для Event-агентств — надежный подрядчик, готовое оборудование, харизматичные ведущие и агентские условия.
            </p>
          </div>
          <div style="background: var(--bg-alt); border-radius: 8px; padding: 8px 10px; font-size: 11px; font-weight: 700; color: var(--text);">
            Отдельные сценарии под каждый сегмент
          </div>
        </div>

        <!-- Шаг 3 -->
        <div class="card" style="display: flex; flex-direction: column; justify-content: space-between; height: 320px;">
          <div>
            <div style="font-size: 11px; font-weight: 800; color: var(--primary); text-transform: uppercase; margin-bottom: 6px;">Шаг 03</div>
            <h3 style="font-size: 15.5px; font-weight: 800; color: var(--text); margin-bottom: 8px; line-height: 1.3;">
              Тестирование гипотез
            </h3>
            <p style="font-size: 11.5px; color: var(--text-muted); line-height: 1.45;">
              Запускаем в ротацию варианты тем и смысловых хуков (раннее бронирование новогодних дат, адаптация вопросов под специфику бизнеса, гибридный/онлайн формат для удаленных филиалов). Замеряем конверсию в подтвержденный интерес.
            </p>
          </div>
          <div style="background: var(--primary-light); border-radius: 8px; padding: 8px 10px; font-size: 11px; font-weight: 800; color: var(--primary);">
            Конверсия в ответ — до 11%
          </div>
        </div>

        <!-- Шаг 4 (акцентная) -->
        <div class="card" style="display: flex; flex-direction: column; justify-content: space-between; height: 320px; border: 1.5px solid var(--primary); background: #FAF9FF;">
          <div>
            <div style="font-size: 11px; font-weight: 800; color: var(--primary); text-transform: uppercase; margin-bottom: 6px;">Шаг 04 · Акцент</div>
            <h3 style="font-size: 15.5px; font-weight: 800; color: var(--primary); margin-bottom: 8px; line-height: 1.3;">
              Масштабирование
            </h3>
            <p style="font-size: 11.5px; color: var(--text-muted); line-height: 1.45;">
              Оставляем только связки с наивысшим откликом и планомерно наращиваем охват целевых компаний до 1 500 контактов в месяц. Передаем вам прямые контакты заинтересованных ЛПР для согласования смет и бронирования дат.
            </p>
          </div>
          <div style="background: var(--teal-light); border-radius: 8px; padding: 8px 10px; font-size: 11px; font-weight: 800; color: var(--teal);">
            Поток 18–27 лидов в месяц
          </div>
        </div>

      </div>
    </div>

    <div class="slide-footer">
      <div>Call-Talk — Системный аутрич для «Квиз, плиз!»</div>
      <div>Слайд 03 / 09</div>
    </div>
  </div>

  <!-- ==================== СЛАЙД 4: РЕЛЕВАНТНЫЕ КЕЙСЫ ==================== -->
  <div class="slide">
    <div class="slide-header">
      <div class="header-brand">
        <div class="logo-box"><div class="logo-icon">CT</div> Call-Talk</div>
        <div class="header-badge">Опыт и релевантные кейсы</div>
      </div>
      <a href="https://calltalk.ru" class="header-link">calltalk.ru ↗</a>
    </div>

    <div class="slide-body">
      <div>
        <h2 class="slide-title-h2">Отработанная механика в схожих B2B-сегментах</h2>
        <div class="slide-lead">
          Прямой аутрич по HR-директорам и организаторам корпоративных мероприятий имеет подтвержденную конверсию. Мы уже привлекали заказчиков в аналогичных нишах со схожей механикой принятия решений.
        </div>
      </div>

      <!-- СЕТКА ИЗ 2 КЕЙСОВ -->
      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 10px;">
        
        <!-- КЕЙС 1: Kitchen Ceremony -->
        <div class="card" style="padding: 14px 18px; display: flex; flex-direction: column; justify-content: space-between;">
          <div>
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
              <span style="font-size: 11px; font-weight: 800; color: var(--primary); text-transform: uppercase; letter-spacing: 0.05em;">
                КЕЙС 01 · КОРПОРАТИВНЫЕ ПОДАРКИ
              </span>
              <span style="font-size: 11px; font-weight: 700; color: var(--teal); background: var(--teal-light); padding: 2px 8px; border-radius: 999px;">
                HRD & Event-агентства
              </span>
            </div>
            <h3 style="font-size: 16px; font-weight: 800; color: var(--text); margin-bottom: 6px;">
              Kitchen Ceremony · Гастрономические корпоративные подарки
            </h3>
            <p style="font-size: 11.5px; color: var(--text-muted); line-height: 1.45; margin-bottom: 8px;">
              <strong>Механика:</strong> Выход на HRD, специалистов по внутренней культуре и event-менеджеров крупных компаний перед праздниками. Предложение премиальных подарков для сотрудников и партнеров под ключ.
            </p>
            <p style="font-size: 11.5px; color: var(--text-muted); line-height: 1.45;">
              <strong>Реализация:</strong> Адресная база компаний <span class="accent-purple">от 100+ сотрудников</span>, цепочки из 3 персонализированных писем с презентацией готовых концепций и бронированием тиражей.
            </p>
          </div>
          
          <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin-top: 10px; background: var(--bg-alt); padding: 8px 10px; border-radius: 8px; text-align: center;">
            <div>
              <div style="font-size: 17px; font-weight: 900; color: var(--primary);">61 лид</div>
              <div style="font-size: 10px; color: var(--text-muted);">Подтвержденный интерес</div>
            </div>
            <div>
              <div style="font-size: 17px; font-weight: 900; color: var(--text);">3 050</div>
              <div style="font-size: 10px; color: var(--text-muted);">Контактов в базе</div>
            </div>
            <div>
              <div style="font-size: 17px; font-weight: 900; color: var(--teal);">2.5 мес</div>
              <div style="font-size: 10px; color: var(--text-muted);">Срок кампании</div>
            </div>
          </div>
        </div>

        <!-- КЕЙС 2: GoGYM -->
        <div class="card" style="padding: 14px 18px; display: flex; flex-direction: column; justify-content: space-between; border: 1.5px solid var(--primary); background: #FAF9FF;">
          <div>
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
              <span style="font-size: 11px; font-weight: 800; color: var(--primary); text-transform: uppercase; letter-spacing: 0.05em;">
                КЕЙС 02 · КОРПОРАТИВНЫЙ СЕРВИС
              </span>
              <span style="font-size: 11px; font-weight: 700; color: var(--teal); background: var(--teal-light); padding: 2px 8px; border-radius: 999px;">
                Выход на HRD в B2B
              </span>
            </div>
            <h3 style="font-size: 16px; font-weight: 800; color: var(--primary); margin-bottom: 6px;">
              GoGYM · Корпоративный спорт и велнес для сотрудников
            </h3>
            <p style="font-size: 11.5px; color: var(--text-muted); line-height: 1.45; margin-bottom: 8px;">
              <strong>Механика:</strong> Аутрич по HRD и руководителям C&B (льготы и компенсации) бизнеса <span class="accent-purple">от 100+ сотрудников</span> для подключения корпоративной программы заботы о здоровье.
            </p>
            <p style="font-size: 11.5px; color: var(--text-muted); line-height: 1.45;">
              <strong>Объемы:</strong> 1-й месяц — 600 контактов (с прогревом), далее 5 месяцев по 1 500 контактов (итого 8 100 контактов в базе, 24 300 отправленных писем).
            </p>
          </div>
          
          <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin-top: 10px; background: #FFFFFF; border: 1px solid var(--primary-border); padding: 8px 10px; border-radius: 8px; text-align: center;">
            <div>
              <div style="font-size: 17px; font-weight: 900; color: var(--teal);">150+ лидов</div>
              <div style="font-size: 10px; color: var(--text-muted);">Одобрены клиентом</div>
            </div>
            <div>
              <div style="font-size: 17px; font-weight: 900; color: var(--text);">8 100</div>
              <div style="font-size: 10px; color: var(--text-muted);">Контактов в базе</div>
            </div>
            <div>
              <div style="font-size: 17px; font-weight: 900; color: var(--primary);">6 мес</div>
              <div style="font-size: 10px; color: var(--text-muted);">Срок кампании</div>
            </div>
          </div>
        </div>

      </div>

      <!-- ВЫВОД ПО КЕЙСАМ -->
      <div style="font-size: 11.5px; color: var(--text-muted); line-height: 1.4; background: var(--bg-alt); padding: 9px 14px; border-radius: 8px; border: 1px solid var(--border);">
        <strong>Ключевой вывод для «Квиз, плиз!»:</strong> Точечный email-аутрич обеспечивает выход на заинтересованных лиц в целевых компаниях и передачу квалифицированных лидов с подтвержденным интересом. Запуск кампании прямо сейчас позволяет занять свободные даты в календаре компаний до того, как они выберут других подрядчиков.
      </div>
    </div>

    <div class="slide-footer">
      <div>Call-Talk — Системный аутрич для «Квиз, плиз!»</div>
      <div>Слайд 04 / 09</div>
    </div>
  </div>

  <!-- ==================== СЛАЙД 5: СТОИМОСТЬ И УСЛОВИЯ ==================== -->
  <div class="slide">
    <div class="slide-header">
      <div class="header-brand">
        <div class="logo-box"><div class="logo-icon">CT</div> Call-Talk</div>
        <div class="header-badge">Условия сотрудничества</div>
      </div>
      <a href="https://calltalk.ru" class="header-link">calltalk.ru ↗</a>
    </div>

    <div class="slide-body">
      <div>
        <h2 class="slide-title-h2">Прозрачная модель: фикс + оплата за результат</h2>
        <div class="slide-lead">
          Разделяем финансовые риски: базовая часть обеспечивает работу выделенной инфраструктуры и ручной сбор базы, а оплата за лиды происходит только по факту их подтверждения.
        </div>
      </div>

      <!-- 2 ТАРИФА НА ВЫБОР -->
      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 10px;">
        
        <!-- Тариф 1: 4 месяца (Рекомендуемый) -->
        <div class="card" style="padding: 12px 16px; border: 1.5px solid var(--primary); background: #FAF9FF; position: relative;">
          <div style="position: absolute; top: -9px; right: 14px; background: var(--primary); color: #FFFFFF; font-size: 9.5px; font-weight: 800; padding: 2px 8px; border-radius: 999px; text-transform: uppercase;">
            РЕКОМЕНДУЕМЫЙ ФОРМАТ
          </div>
          <div style="font-size: 11px; font-weight: 800; color: var(--primary); text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 2px;">
            ТАРИФ НА 4 МЕСЯЦА · СИСТЕМНЫЙ ПОТОК
          </div>
          <div style="display: flex; align-items: baseline; justify-content: space-between; flex-wrap: nowrap; gap: 6px; margin-bottom: 4px;">
            <div style="white-space: nowrap;">
              <span style="font-size: 26px; font-weight: 900; color: var(--primary); line-height: 1;">39 000 руб</span>
              <span style="font-size: 13px; font-weight: 700; color: var(--primary); margin-left: 2px;">/мес</span>
            </div>
            <span style="font-size: 10.5px; color: var(--text-light); white-space: nowrap;">(156 000 руб за 4 месяца)</span>
          </div>
          <p style="font-size: 11px; color: var(--text-muted); line-height: 1.35; margin: 0;">
            Охватывает весь сезон: бронь Нового года (сентябрь-ноябрь), проведение корпоративов (декабрь), игры на 23 февраля и 8 марта (январь-февраль). База 5 100 контактов, прогноз: <strong>63–95 лидов</strong>.
          </p>
        </div>

        <!-- Тариф 2: 2 месяца -->
        <div class="card" style="padding: 12px 16px;">
          <div style="font-size: 11px; font-weight: 800; color: var(--text-light); text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 2px;">
            ТАРИФ НА 2 МЕСЯЦА · НОВОГОДНИЙ СЕЗОН
          </div>
          <div style="display: flex; align-items: baseline; justify-content: space-between; flex-wrap: nowrap; gap: 6px; margin-bottom: 4px;">
            <div style="white-space: nowrap;">
              <span style="font-size: 26px; font-weight: 900; color: var(--text); line-height: 1;">56 000 руб</span>
              <span style="font-size: 13px; font-weight: 700; color: var(--text-muted); margin-left: 2px;">/мес</span>
            </div>
            <span style="font-size: 10.5px; color: var(--text-light); white-space: nowrap;">(112 000 руб за 2 месяца)</span>
          </div>
          <p style="font-size: 11px; color: var(--text-muted); line-height: 1.35; margin: 0;">
            Сфокусирован на оперативной загрузке новогоднего слота корпоративов (сентябрь-ноябрь). База 2 100 контактов, прогноз: <strong>27–41 лид</strong>.
          </p>
        </div>

      </div>

      <!-- ПЛАШКА ОПЛАТЫ ЗА РЕЗУЛЬТАТ -->
      <div class="card-alt" style="margin-bottom: 10px; padding: 10px 16px; display: flex; justify-content: space-between; align-items: center; border: 1px solid var(--border);">
        <div style="display: flex; align-items: center; gap: 14px;">
          <div style="font-size: 22px; font-weight: 900; color: var(--primary); white-space: nowrap;">
            2 800 руб <span style="font-size: 13px; font-weight: 700; color: var(--text-muted);">/лид</span>
          </div>
          <div style="font-size: 11px; color: var(--text-muted); line-height: 1.35;">
            Фиксированная ставка за квалифицированный лид. Оплата по факту по итогам каждого месяца.
          </div>
        </div>
      </div>

      <!-- 2 ПЛАШКИ: КРИТЕРИИ И ЗАЩИТА БЮДЖЕТА -->
      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px;">
        
        <!-- Зеленая: Критерий лида -->
        <div style="background: var(--teal-light); border: 1px solid var(--teal-border); border-radius: 10px; padding: 10px 14px;">
          <div style="font-size: 10.5px; font-weight: 800; color: var(--teal); text-transform: uppercase; margin-bottom: 4px;">
            ✓ КРИТЕРИИ ВАЛИДНОГО ЛИДА
          </div>
          <ul style="margin: 0; padding-left: 14px; font-size: 10px; color: #064E3B; line-height: 1.35; display: flex; flex-direction: column; gap: 2px;">
            <li>Подтвердил интерес к проведению корпоративного квиза или запросил смету / презентацию;</li>
            <li>Не возражает против дальнейшего общения в рамках предложения «Квиз, плиз!»;</li>
            <li>Запросил созвон, встречу или согласование свободных дат проведения;</li>
            <li>Передал прямые контакты ответственного ЛПР (HRD, организатора праздника, продюсера).</li>
          </ul>
        </div>

        <!-- Красная: Что не оплачивается -->
        <div style="background: var(--coral-light); border: 1px solid var(--coral-border); border-radius: 10px; padding: 10px 14px;">
          <div style="font-size: 10.5px; font-weight: 800; color: #9A3412; text-transform: uppercase; margin-bottom: 4px;">
            ✕ ЧТО НЕ ОПЛАЧИВАЕТСЯ (100% ЗАЩИТА БЮДЖЕТА)
          </div>
          <ul style="margin: 0; padding-left: 14px; font-size: 9.5px; color: #7C2D12; line-height: 1.3; display: flex; flex-direction: column; gap: 2px;">
            <li>Отказы («не актуально», «уже выбрали подрядчика», «уберите из рассылки» и т. п.);</li>
            <li>Автоответы и технические уведомления почтовых серверов;</li>
            <li>Ответы действующих клиентов «Квиз, плиз!»;</li>
            <li>Диалоги, в которых ЛПР прямо подтвердил отсутствие потребности в играх.</li>
          </ul>
        </div>

      </div>
    </div>

    <div class="slide-footer">
      <div>Call-Talk — Системный аутрич для «Квиз, плиз!»</div>
      <div>Слайд 05 / 09</div>
    </div>
  </div>

  <!-- ==================== СЛАЙД 6: ВОРОНКА И ОКУПАЕМОСТЬ (4 МЕСЯЦА) ==================== -->
  <div class="slide">
    <div class="slide-header">
      <div class="header-brand">
        <div class="logo-box"><div class="logo-icon">CT</div> Call-Talk</div>
        <div class="header-badge">Экономика: Тариф 4 месяца</div>
      </div>
      <a href="https://calltalk.ru" class="header-link">calltalk.ru ↗</a>
    </div>

    <div class="slide-body">
      <div>
        <h2 class="slide-title-h2">Воронка и экономика окупаемости · Договор на 4 месяца</h2>
        <div class="slide-lead" style="margin-bottom: 8px;">
          Прогноз генерации, конверсия в сделки 20% и расчет окупаемости инвестиций (фикс 39 000 руб/мес + лид 2 800 руб).
        </div>
      </div>

      <!-- ТАБЛИЦА ВОРОНКИ ПО МЕСЯЦАМ -->
      <table class="data-table" style="margin-bottom: 8px;">
        <thead>
          <tr>
            <th style="padding: 6px 12px;">Период кампании</th>
            <th style="padding: 6px 12px;">База в обработке</th>
            <th style="padding: 6px 12px;">Отправлено писем (цепочки)</th>
            <th style="padding: 6px 12px; text-align: right;">Лиды с интересом</th>
            <th style="padding: 6px 12px; text-align: right;">Сделки (конверсия 20%)</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td style="padding: 6px 12px;"><strong>Месяц 1</strong> (прогрев доменов, сбор базы и первые брони)</td>
            <td style="padding: 6px 12px;">600 контактов</td>
            <td style="padding: 6px 12px;">1 800 писем</td>
            <td style="padding: 6px 12px; text-align: right; font-weight: 700;">9 – 14 лидов</td>
            <td style="padding: 6px 12px; text-align: right; font-weight: 700; color: var(--teal);">2 – 3 сделки</td>
          </tr>
          <tr>
            <td style="padding: 6px 12px;"><strong>Месяц 2</strong> (расчет лидов без учета пика предновогодних бронирований)</td>
            <td style="padding: 6px 12px;">1 500 контактов</td>
            <td style="padding: 6px 12px;">4 500 писем</td>
            <td style="padding: 6px 12px; text-align: right; font-weight: 700;">18 – 27 лидов</td>
            <td style="padding: 6px 12px; text-align: right; font-weight: 700; color: var(--teal);">4 – 5 сделок</td>
          </tr>
          <tr>
            <td style="padding: 6px 12px;"><strong>Месяцы 3–4</strong> (гендерные праздники: 23 февраля и 8 марта)</td>
            <td style="padding: 6px 12px;">3 000 контактов (по 1 500/мес)</td>
            <td style="padding: 6px 12px;">9 000 писем</td>
            <td style="padding: 6px 12px; text-align: right; font-weight: 700;">36 – 54 лида</td>
            <td style="padding: 6px 12px; text-align: right; font-weight: 700; color: var(--teal);">7 – 11 сделок</td>
          </tr>
          <tr class="total-row">
            <td style="padding: 6px 12px;"><strong>ИТОГО ЗА 4 МЕСЯЦА</strong></td>
            <td style="padding: 6px 12px;"><strong>5 100 контактов</strong></td>
            <td style="padding: 6px 12px;"><strong>15 300 писем</strong></td>
            <td style="padding: 6px 12px; text-align: right;"><strong>63 – 95 лидов</strong></td>
            <td style="padding: 6px 12px; text-align: right; color: var(--primary);"><strong>13 – 19 закрытых сделок</strong></td>
          </tr>
        </tbody>
      </table>

      <!-- АКЦЕНТНАЯ ПЛАШКА ROI (4 ЯЧЕЙКИ) -->
      <div style="display: grid; grid-template-columns: 1fr 1.15fr 1.15fr 1.1fr; gap: 10px; margin-bottom: 8px;">
        
        <div class="card-alt" style="padding: 8px 10px; text-align: center;">
          <div style="font-size: 19px; font-weight: 900; color: var(--primary);">13 – 19 сделок</div>
          <div style="font-size: 10.5px; font-weight: 700; color: var(--text); margin-top: 1px;">Закрытых сделок</div>
          <div style="font-size: 9.5px; color: var(--text-light);">Конверсия 20% из лидов</div>
        </div>

        <div class="card-alt" style="padding: 8px 10px; text-align: center;">
          <div style="font-size: 19px; font-weight: 900; color: var(--teal);">~2.25 млн руб</div>
          <div style="font-size: 10.5px; font-weight: 700; color: var(--text); margin-top: 1px;">Привлеченная выручка</div>
          <div style="font-size: 9.5px; color: var(--text-light);">15 сделок × 150 000 руб</div>
        </div>

        <div class="card-alt" style="padding: 8px 10px; text-align: center;">
          <div style="font-size: 19px; font-weight: 900; color: var(--coral);">~366 000 руб</div>
          <div style="font-size: 10.5px; font-weight: 700; color: var(--text); margin-top: 1px;">Все расходы за 4 мес</div>
          <div style="font-size: 9.5px; color: var(--text-light);">~16% от выручки</div>
        </div>

        <div style="background: var(--primary); color: #FFFFFF; border-radius: 10px; padding: 10px 8px; text-align: center; display: flex; flex-direction: column; justify-content: center;">
          <div style="font-size: 17.5px; font-weight: 900; color: #FFFFFF; line-height: 1.2;">С ~8-й сделки + LTV</div>
          <div style="font-size: 11px; font-weight: 700; color: #FFFFFF; margin-top: 3px;">Окупаемость с маржой</div>
        </div>

      </div>

      <div style="font-size: 10.5px; color: var(--text-muted); line-height: 1.4; background: var(--bg-alt); padding: 6px 12px; border-radius: 8px; border: 1px solid var(--border);">
        <div><strong>Расчет окупаемости:</strong> Аутрич ведется строго по компаниям <span class="accent-purple">от 100+ сотрудников</span> с бюджетом на корпоративы. В расчете заложены ориентиры ниши: конверсия из лида в сделку 20% и средний чек 150 000 руб. Точные цифры зафиксированы только на услуги Call-Talk.</div>
        <div style="margin-top: 3px;"><strong>Логика расчета:</strong> 79 лидов × 20% = ~15 закрытых сделок (прогноз: 13–19) → 15 сделок × 150 000 руб = ~2 250 000 руб выручки. Расходы на Call-Talk: 156 000 руб (фикс) + ~210 000 руб (лиды) = ~366 000 руб (~16% от выручки). С учетом себестоимости проведения мероприятий (при марже ~30%) полная окупаемость наступает с ~8-й сделки + LTV без дополнительных затрат на маркетинг.</div>
      </div>
    </div>

    <div class="slide-footer">
      <div>Call-Talk — Системный аутрич для «Квиз, плиз!»</div>
      <div>Слайд 06 / 09</div>
    </div>
  </div>

  <!-- ==================== СЛАЙД 7: ВОРОНКА И ОКУПАЕМОСТЬ (2 МЕСЯЦА) ==================== -->
  <div class="slide">
    <div class="slide-header">
      <div class="header-brand">
        <div class="logo-box"><div class="logo-icon">CT</div> Call-Talk</div>
        <div class="header-badge">Экономика: Тариф 2 месяца</div>
      </div>
      <a href="https://calltalk.ru" class="header-link">calltalk.ru ↗</a>
    </div>

    <div class="slide-body">
      <div>
        <h2 class="slide-title-h2">Воронка и экономика окупаемости · Договор на 2 месяца</h2>
        <div class="slide-lead" style="margin-bottom: 8px;">
          Экспресс-воронка для быстрой загрузки расписания на предновогодний сезон корпоративов (фикс 56 000 руб/мес + лид 2 800 руб).
        </div>
      </div>

      <!-- ТАБЛИЦА ВОРОНКИ ПО МЕСЯЦАМ -->
      <table class="data-table" style="margin-bottom: 8px;">
        <thead>
          <tr>
            <th style="padding: 6px 12px;">Период кампании</th>
            <th style="padding: 6px 12px;">База в обработке</th>
            <th style="padding: 6px 12px;">Отправлено писем (цепочки)</th>
            <th style="padding: 6px 12px; text-align: right;">Лиды с интересом</th>
            <th style="padding: 6px 12px; text-align: right;">Сделки (конверсия 20%)</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td style="padding: 6px 12px;"><strong>Месяц 1</strong> (прогрев доменов, сбор базы и первые брони)</td>
            <td style="padding: 6px 12px;">600 контактов</td>
            <td style="padding: 6px 12px;">1 800 писем</td>
            <td style="padding: 6px 12px; text-align: right; font-weight: 700;">9 – 14 лидов</td>
            <td style="padding: 6px 12px; text-align: right; font-weight: 700; color: var(--teal);">2 – 3 сделки</td>
          </tr>
          <tr>
            <td style="padding: 6px 12px;"><strong>Месяц 2</strong> (расчет лидов без учета пика предновогодних бронирований)</td>
            <td style="padding: 6px 12px;">1 500 контактов</td>
            <td style="padding: 6px 12px;">4 500 писем</td>
            <td style="padding: 6px 12px; text-align: right; font-weight: 700;">18 – 27 лидов</td>
            <td style="padding: 6px 12px; text-align: right; font-weight: 700; color: var(--teal);">4 – 5 сделок</td>
          </tr>
          <tr class="total-row">
            <td style="padding: 6px 12px;"><strong>ИТОГО ЗА 2 МЕСЯЦА</strong></td>
            <td style="padding: 6px 12px;"><strong>2 100 контактов</strong></td>
            <td style="padding: 6px 12px;"><strong>6 300 писем</strong></td>
            <td style="padding: 6px 12px; text-align: right;"><strong>27 – 41 лид</strong></td>
            <td style="padding: 6px 12px; text-align: right; color: var(--primary);"><strong>6 – 8 закрытых сделок</strong></td>
          </tr>
        </tbody>
      </table>

      <!-- АКЦЕНТНАЯ ПЛАШКА ROI (4 ЯЧЕЙКИ) -->
      <div style="display: grid; grid-template-columns: 1fr 1.15fr 1.15fr 1.1fr; gap: 10px; margin-bottom: 8px;">
        
        <div class="card-alt" style="padding: 8px 10px; text-align: center;">
          <div style="font-size: 19px; font-weight: 900; color: var(--primary);">6 – 8 сделок</div>
          <div style="font-size: 10.5px; font-weight: 700; color: var(--text); margin-top: 1px;">Закрытых сделок</div>
          <div style="font-size: 9.5px; color: var(--text-light);">Конверсия 20% из лидов</div>
        </div>

        <div class="card-alt" style="padding: 8px 10px; text-align: center;">
          <div style="font-size: 19px; font-weight: 900; color: var(--teal);">900 000 – 1.2 млн руб</div>
          <div style="font-size: 10.5px; font-weight: 700; color: var(--text); margin-top: 1px;">Привлеченная выручка</div>
          <div style="font-size: 9.5px; color: var(--text-light);">7 сделок × 150 000 руб</div>
        </div>

        <div class="card-alt" style="padding: 8px 10px; text-align: center;">
          <div style="font-size: 19px; font-weight: 900; color: var(--coral);">~207 000 руб</div>
          <div style="font-size: 10.5px; font-weight: 700; color: var(--text); margin-top: 1px;">Все расходы за 2 мес</div>
          <div style="font-size: 9.5px; color: var(--text-light);">~20% от выручки</div>
        </div>

        <div style="background: var(--primary); color: #FFFFFF; border-radius: 10px; padding: 10px 8px; text-align: center; display: flex; flex-direction: column; justify-content: center;">
          <div style="font-size: 17.5px; font-weight: 900; color: #FFFFFF; line-height: 1.2;">С ~8-й сделки + LTV</div>
          <div style="font-size: 11px; font-weight: 700; color: #FFFFFF; margin-top: 3px;">Окупаемость с маржой</div>
        </div>

      </div>

      <div style="font-size: 10.5px; color: var(--text-muted); line-height: 1.4; background: var(--bg-alt); padding: 6px 12px; border-radius: 8px; border: 1px solid var(--border);">
        <div><strong>Расчет окупаемости:</strong> Аутрич ведется строго по компаниям <span class="accent-purple">от 100+ сотрудников</span> Москвы и МО с бюджетом на корпоративы. В расчете заложены ориентиры ниши: конверсия из лида в сделку 20% и средний чек 150 000 руб. Точные цифры зафиксированы только на услуги Call-Talk.</div>
        <div style="margin-top: 3px;"><strong>Логика расчета:</strong> 34 лида × 20% = ~7 закрытых сделок (прогноз: 6–8) → 7 сделок × 150 000 руб = ~1 050 000 руб выручки (диапазон: 900 000 – 1 200 000 руб). Расходы на Call-Talk: 112 000 руб (фикс) + ~95 000 руб (лиды) = ~207 000 руб (~20% от выручки). С учетом повышенной доли фикса в коротком договоре и себестоимости мероприятий окупаемость наступает с ~8-й сделки + LTV (за счет повторных заказов компаний весной).</div>
      </div>
    </div>

    <div class="slide-footer">
      <div>Call-Talk — Системный аутрич для «Квиз, плиз!»</div>
      <div>Слайд 07 / 09</div>
    </div>
  </div>

  <!-- ==================== СЛАЙД 8: ПЛАН ЗАПУСКА (ТАЙМЛАЙН) ==================== -->
  <div class="slide">
    <div class="slide-header">
      <div class="header-brand">
        <div class="logo-box"><div class="logo-icon">CT</div> Call-Talk</div>
        <div class="header-badge">График запуска</div>
      </div>
      <a href="https://calltalk.ru" class="header-link">calltalk.ru ↗</a>
    </div>

    <div class="slide-body">
      <div>
        <h2 class="slide-title-h2">План реализации проекта</h2>
        <div class="slide-lead">
          Четкий график перехода от согласования договора к первым целевым откликам и бронированиям корпоративных игр.
        </div>
      </div>

      <!-- СПИСОК ИЗ 4 КАРТОЧЕК-ЭТАПОВ -->
      <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px;">
        
        <div class="card" style="padding: 16px 14px; height: 325px; display: flex; flex-direction: column; justify-content: space-between;">
          <div>
            <div style="font-size: 11px; font-weight: 800; color: var(--primary); margin-bottom: 6px;">ЭТАП 01 · 1–2 ДНЯ</div>
            <h3 style="font-size: 14px; font-weight: 800; color: var(--text); margin-bottom: 8px;">Подготовка почты</h3>
            <p style="font-size: 11.5px; color: var(--text-muted); line-height: 1.4;">
              Клиент подключает почтовые ящики по нашей инструкции (или подключаем под ключ). Проверяем настройки DNS (SPF/DKIM/DMARC) для защиты репутации домена.
            </p>
          </div>
          <div style="font-size: 11px; font-weight: 700; color: var(--primary); background: var(--primary-light); padding: 6px 10px; border-radius: 6px;">
            Подключение ящиков + аудит DNS
          </div>
        </div>

        <div class="card" style="padding: 16px 14px; height: 325px; display: flex; flex-direction: column; justify-content: space-between;">
          <div>
            <div style="font-size: 11px; font-weight: 800; color: var(--primary); margin-bottom: 6px;">ЭТАП 02 · 3–10 ДНЕЙ</div>
            <h3 style="font-size: 14px; font-weight: 800; color: var(--text); margin-bottom: 8px;">Сбор базы и цепочки писем</h3>
            <p style="font-size: 11.5px; color: var(--text-muted); line-height: 1.4;">
              Собираем адресную базу HRD и Event-агентств Москвы/МО, валидируем контакты. Готовим сценарии писем. Параллельно подключаем ящики к прогреву.
            </p>
          </div>
          <div style="font-size: 11px; font-weight: 700; color: var(--primary); background: var(--primary-light); padding: 6px 10px; border-radius: 6px;">
            Сбор базы + прогрев почт
          </div>
        </div>

        <div class="card" style="padding: 16px 14px; height: 325px; display: flex; flex-direction: column; justify-content: space-between;">
          <div>
            <div style="font-size: 11px; font-weight: 800; color: var(--primary); margin-bottom: 6px;">ЭТАП 03 · 10–14 ДНЕЙ</div>
            <h3 style="font-size: 14px; font-weight: 800; color: var(--text); margin-bottom: 8px;">Запуск и первые лиды</h3>
            <p style="font-size: 11.5px; color: var(--text-muted); line-height: 1.4;">
              Запускаем цепочки писем с постепенным наращиванием объема отправок. Передаем первые входящие отклики и заявки на бронирование дат.
            </p>
          </div>
          <div style="font-size: 11px; font-weight: 700; color: var(--teal); background: var(--teal-light); padding: 6px 10px; border-radius: 6px;">
            Передача первых лидов
          </div>
        </div>

        <div class="card" style="padding: 16px 14px; height: 325px; display: flex; flex-direction: column; justify-content: space-between; border: 1.5px solid var(--primary); background: #FAF9FF;">
          <div>
            <div style="font-size: 11px; font-weight: 800; color: var(--primary); margin-bottom: 6px;">ЭТАП 04 · ПОСТОЯННО</div>
            <h3 style="font-size: 14px; font-weight: 800; color: var(--primary); margin-bottom: 8px;">Поток лидов и отчетность</h3>
            <p style="font-size: 11.5px; color: var(--text-muted); line-height: 1.4;">
              Передаем вам лиды. Регулярно пополняем базу новыми компаниями и докручиваем сценарии писем для максимальной конверсии. Ежемесячно предоставляем отчет.
            </p>
          </div>
          <div style="font-size: 11px; font-weight: 700; color: var(--primary); background: var(--primary-light); padding: 6px 10px; border-radius: 6px;">
            Передача лидов + отчетность
          </div>
        </div>

      </div>
    </div>

    <div class="slide-footer">
      <div>Call-Talk — Системный аутрич для «Квиз, плиз!»</div>
      <div>Слайд 08 / 09</div>
    </div>
  </div>

  <!-- ==================== СЛАЙД 9: СЛЕДУЮЩИЙ ШАГ И КОНТАКТЫ ==================== -->
  <div class="slide">
    <div class="slide-header">
      <div class="header-brand">
        <div class="logo-box"><div class="logo-icon">CT</div> Call-Talk</div>
        <div class="header-badge">Следующий шаг</div>
      </div>
      <a href="https://calltalk.ru" class="header-link">calltalk.ru ↗</a>
    </div>

    <div class="slide-body">
      <div>
        <h2 class="slide-title-h2">Как мы начинаем</h2>
        <div class="slide-lead">
          Прозрачный алгоритм старта или открытый диалог для ответов на ваши вопросы перед защитой у стейкхолдера.
        </div>
      </div>

      <!-- СЕТКА ИЗ 2 КОЛОНОК -->
      <div style="display: grid; grid-template-columns: 1.15fr 1fr; gap: 20px;">
        
        <!-- Левая колонка: 2 карточки -->
        <div style="display: flex; flex-direction: column; gap: 12px;">
          
          <div class="card" style="padding: 16px 20px;">
            <div style="font-size: 11px; font-weight: 800; color: var(--teal); text-transform: uppercase; margin-bottom: 4px;">
              ЕСЛИ ВСЁ ПОДХОДИТ
            </div>
            <h4 style="font-size: 15.5px; font-weight: 800; color: var(--text); margin-bottom: 4px;">
              Фиксация договоренностей и старт
            </h4>
            <p style="font-size: 11.5px; color: var(--text-muted); line-height: 1.45;">
              Выбираем комфортный период договора (2 месяца по 56 000 руб/мес или 4 месяца по 39 000 руб/мес, ставка 2 800 руб за подтвержденный лид). Подписываем договор и на следующий день после оплаты запускаем техническую подготовку.
            </p>
          </div>

          <div class="card" style="padding: 16px 20px;">
            <div style="font-size: 11px; font-weight: 800; color: var(--primary); text-transform: uppercase; margin-bottom: 4px;">
              ЕСЛИ ОСТАЛИСЬ ВОПРОСЫ
            </div>
            <h4 style="font-size: 15.5px; font-weight: 800; color: var(--text); margin-bottom: 4px;">
              Открытый диалог перед защитой
            </h4>
            <p style="font-size: 11.5px; color: var(--text-muted); line-height: 1.45;">
              Задайте их прямо сейчас — поможем подготовить аргументы для руководства, согласуем нюансы сегментации по отраслям или скорректируем параметры кампании под задачи «Квиз, плиз!».
            </p>
          </div>

        </div>

        <!-- Правая колонка: ФИОЛЕТОВАЯ БРЕНДОВАЯ КАРТОЧКА КОНТАКТОВ (#5B4BD8) -->
        <div style="background: linear-gradient(145deg, #5B4BD8 0%, #4738B5 100%); color: #FFFFFF; border-radius: 14px; padding: 18px 22px; display: flex; flex-direction: column; justify-content: space-between; border: 1px solid rgba(255,255,255,0.15);">
          <div>
            <div style="display: flex; align-items: center; gap: 14px; margin-bottom: 12px;">
              <img src="{photo_src}" alt="Ульяна" style="width: 56px; height: 56px; border-radius: 50%; object-fit: cover; border: 2.5px solid #FFFFFF;">
              <div>
                <div style="font-size: 16.5px; font-weight: 900; color: #FFFFFF;">Ульяна Кирпичникова</div>
                <div style="font-size: 11px; color: rgba(255,255,255,0.85); font-weight: 600;">Ведущий специалист B2B-лидогенерации</div>
              </div>
            </div>

            <div style="display: flex; flex-direction: column; gap: 7px; font-size: 12px; margin-bottom: 12px; background: rgba(255,255,255,0.1); padding: 9px 12px; border-radius: 10px;">
              <div style="display: flex; align-items: center; gap: 8px;">
                <span style="color: rgba(255,255,255,0.75); width: 68px;">Telegram:</span>
                <a href="https://t.me/calltalk_ru" style="color: #FFFFFF; font-weight: 800; text-decoration: none;">@calltalk_ru</a>
              </div>
              <div style="display: flex; align-items: center; gap: 8px;">
                <span style="color: rgba(255,255,255,0.75); width: 68px;">E-mail:</span>
                <span style="color: #FFFFFF; font-weight: 700;">ulyana.k@calltalk.ru</span>
              </div>
              <div style="display: flex; align-items: center; gap: 8px;">
                <span style="color: rgba(255,255,255,0.75); width: 68px;">Сайт:</span>
                <a href="https://calltalk.ru" style="color: #FFFFFF; font-weight: 700; text-decoration: none;">calltalk.ru ↗</a>
              </div>
            </div>
          </div>

          <!-- Блок основателя -->
          <div style="border-top: 1px solid rgba(255,255,255,0.2); padding-top: 8px;">
            <div style="font-size: 9.5px; text-transform: uppercase; color: rgba(255,255,255,0.75); letter-spacing: 0.06em; margin-bottom: 2px; font-weight: 700;">ОСНОВАТЕЛЬ CALL-TALK</div>
            <div style="font-size: 13px; font-weight: 800; color: #FFFFFF; margin-bottom: 2px;">Ермолаев Игорь</div>
            <div style="font-size: 10px; color: rgba(255,255,255,0.85); line-height: 1.35;">
              15 лет в маркетинге и управлении, лидогенерация в 22 отраслях.<br>
              Вырастил Airo в 14 раз за 2,5 года (инвесторы — МТС и Т-Банк) — совладелец.
            </div>
          </div>

        </div>

      </div>
    </div>

    <div class="slide-footer">
      <div>Call-Talk — Системный аутрич для «Квиз, плиз!»</div>
      <div>Слайд 09 / 09</div>
    </div>
  </div>

</div>

</body>
</html>
"""

    output_html = os.path.join(base_dir, "CALL-TALK_КП_Квиз_плиз.html")
    output_pdf = os.path.join(base_dir, "CALL-TALK — Коммерческое предложение _ Квиз, плиз!.pdf")

    with open(output_html, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"✓ Обновлен HTML файл: {output_html}")

if __name__ == '__main__':
    main()
