const endpoint = 'https://mcp.okocrm.com/crm';
const token = 'OKOCRM_TOKEN_PLACEHOLDER';

const ANDREY_ID = 28418;
const LEONID_ID = 28419;
const ULIANA_ID = 28415;

const MANAGERS = [
  { id: ANDREY_ID, name: 'Андрей', email: 'andrey.s@calltalk.ru' },
  { id: LEONID_ID, name: 'Лёня', email: 'leonid.g@calltalk.ru' }
];

async function callTool(name, args) {
  const res = await fetch(endpoint, {
    method: 'POST',
    headers: {
      'Authorization': 'Bearer ' + token,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      jsonrpc: '2.0',
      id: Date.now(),
      method: 'tools/call',
      params: { name, arguments: args }
    })
  });
  const data = await res.json();
  if (data.result && data.result.content && data.result.content[0]) {
    try {
      return JSON.parse(data.result.content[0].text);
    } catch(e) {
      return data.result.content[0].text;
    }
  }
  return data;
}

async function getAllLeads(params) {
  let leads = [];
  let cursor = null;
  while (true) {
    const p = { ...params, limit: 100 };
    if (cursor) p.cursor = cursor;
    const res = await callTool('search_leads', p);
    const items = res.items || [];
    leads = leads.concat(items);
    cursor = res.next_cursor;
    if (!cursor || items.length === 0) break;
  }
  return leads;
}

async function getAllTasks(params) {
  let tasks = [];
  let cursor = null;
  while (true) {
    const p = { ...params, limit: 50 };
    if (cursor) p.cursor = cursor;
    const res = await callTool('list_tasks', p);
    const items = res.items || [];
    tasks = tasks.concat(items);
    cursor = res.next_cursor;
    if (!cursor || items.length === 0) break;
  }
  return tasks;
}

function formatDate(d) {
  return d.toISOString().split('T')[0];
}

async function generateDailyReport(targetDateStr) {
  // If targetDateStr not provided, default to yesterday
  let targetDate;
  if (targetDateStr) {
    targetDate = new Date(targetDateStr);
  } else {
    targetDate = new Date();
    targetDate.setDate(targetDate.getDate() - 1);
  }
  const dateStr = formatDate(targetDate);
  const now = new Date();

  console.log(`\n======================================================`);
  console.log(`📊 АНАЛИЗ CRM ЗА ${dateStr} (Срез на ${now.toLocaleString('ru-RU')})`);
  console.log(`======================================================\n`);

  // 1. Leads created yesterday in primary pipeline (30895) and database pool (30944)
  const createdLeads = await getAllLeads({ created_from: dateStr, created_to: dateStr });
  
  // 2. Active leads in B2B pipeline
  const b2bActiveLeads = await getAllLeads({ pipeline_id: 30895, status: 'active' });
  
  // 3. Won leads yesterday
  const wonSummary = await callTool('get_sales_summary', {
    date_from: dateStr,
    date_to: dateStr,
    group_by: 'manager'
  });

  // 4. Tasks
  const allTasks = await getAllTasks({ executor_ids: [ANDREY_ID, LEONID_ID], status: 'all' });
  const closedYesterday = allTasks.filter(t => t.done && t.closed_at && t.closed_at.startsWith(dateStr));
  const createdYesterdayTasks = allTasks.filter(t => t.created_at && t.created_at.startsWith(dateStr));
  const openTasks = allTasks.filter(t => !t.done);
  const overdueTasks = openTasks.filter(t => new Date(t.date_finish) < now);

  // Group leads created yesterday by channel
  // Identifying channel: URL or domain without email syntax -> site/incoming; name with email/re/Fwd or email contact -> email outreach
  function detectSource(l) {
    const name = l.name || '';
    if (/^https?:\/\//i.test(name) || /^[a-z0-9-]+\.(ru|pro|com|net|io|tech|su)$/i.test(name.trim())) {
      return 'Сайт / Входящий';
    }
    if (/@.*\.|\.ru>|\.com>|mail|email|^re:/i.test(name) || /@\w+\.\w+/.test(name)) {
      return 'Email-аутрич';
    }
    return 'Email-аутрич / Прямой контакт';
  }

  const managerReports = [];

  for (const m of MANAGERS) {
    const mLeads = createdLeads.filter(l => l.responsible && l.responsible.id === m.id);
    const mClosedTasks = closedYesterday.filter(t => t.executor && t.executor.id === m.id);
    const mCreatedTasks = createdYesterdayTasks.filter(t => t.executor && t.executor.id === m.id);
    const mOpenTasks = openTasks.filter(t => t.executor && t.executor.id === m.id);
    const mOverdue = overdueTasks.filter(t => t.executor && t.executor.id === m.id);
    
    // Active B2B leads without tasks for this manager
    const mB2BActive = b2bActiveLeads.filter(l => l.responsible && l.responsible.id === m.id);
    const mLeadsNoTask = mB2BActive.filter(l => !l.closest_task_at);

    // Channel split for new leads
    let emailCount = 0;
    let siteCount = 0;
    mLeads.forEach(l => {
      const src = detectSource(l);
      if (src === 'Сайт / Входящий') siteCount++;
      else emailCount++;
    });

    // Key stages count in B2B pipeline currently
    const kpLeads = mB2BActive.filter(l => l.stage && l.stage.id === 148044); // КП отправлено
    const contractLeads = mB2BActive.filter(l => l.stage && l.stage.id === 148045); // Договор на подписи
    const invoiceLeads = mB2BActive.filter(l => l.stage && l.stage.id === 148046); // Счёт направлен

    // Won summary
    const mWonRow = (wonSummary.rows || []).find(r => r.key.id === m.id) || { won_count: 0, won_sum: 0, lost_count: 0 };

    managerReports.push({
      id: m.id,
      name: m.name,
      email: m.email,
      totalNewLeads: mLeads.length,
      emailLeads: emailCount,
      siteLeads: siteCount,
      newLeadsList: mLeads,
      closedTasks: mClosedTasks.length,
      createdTasks: mCreatedTasks.length,
      openTasks: mOpenTasks.length,
      overdueTasksCount: mOverdue.length,
      overdueTasksList: mOverdue,
      leadsNoTaskCount: mLeadsNoTask.length,
      leadsNoTaskList: mLeadsNoTask,
      totalActiveDeals: mB2BActive.length,
      kpCount: kpLeads.length,
      kpList: kpLeads,
      contractCount: contractLeads.length,
      contractList: contractLeads,
      invoiceCount: invoiceLeads.length,
      wonCount: mWonRow.won_count,
      wonSum: mWonRow.won_sum,
      lostCount: mWonRow.lost_count
    });
  }

  // 5. Analytics for "База в проработку" (Pipeline 30944)
  const poolPipelineLeads = await getAllLeads({ pipeline_id: 30944 });
  const poolStageCounts = {
    pool: poolPipelineLeads.filter(l => l.stage && l.stage.id === 148390).length,
    inWork: poolPipelineLeads.filter(l => l.stage && l.stage.id === 148391).length,
    qualified: poolPipelineLeads.filter(l => l.stage && l.stage.id === 148392).length,
    archived: poolPipelineLeads.filter(l => l.stage && l.stage.id === 148393).length
  };

  const poolByManager = {};
  for (const m of MANAGERS) {
    const mPool = poolPipelineLeads.filter(l => l.responsible && l.responsible.id === m.id);
    poolByManager[m.id] = {
      name: m.name,
      pool: mPool.filter(l => l.stage && l.stage.id === 148390).length,
      inWork: mPool.filter(l => l.stage && l.stage.id === 148391).length,
      qualified: mPool.filter(l => l.stage && l.stage.id === 148392).length,
      archived: mPool.filter(l => l.stage && l.stage.id === 148393).length
    };
  }

  // 6. Weekly & Cumulative analytics for B2B pipeline (Pipeline 30895)
  const currentD = new Date(dateStr);
  const dayOfWeek = currentD.getDay();
  const distanceToMonday = (dayOfWeek + 6) % 7;
  const mondayD = new Date(currentD);
  mondayD.setDate(currentD.getDate() - distanceToMonday);
  const mondayStr = formatDate(mondayD);

  const allB2BLeads = await getAllLeads({ pipeline_id: 30895 });
  const weekB2BLeads = allB2BLeads.filter(l => l.created_at && l.created_at.substring(0, 10) >= mondayStr && l.created_at.substring(0, 10) <= dateStr);

  const byDay = {};
  allB2BLeads.forEach(l => {
    const d = l.created_at.substring(0, 10);
    byDay[d] = (byDay[d] || 0) + 1;
  });
  let bestDay = { date: '', count: 0 };
  for (const d in byDay) {
    if (byDay[d] > bestDay.count) {
      bestDay = { date: d, count: byDay[d] };
    }
  }

  const weeklyByManager = {};
  const allTimeByManager = {};
  for (const m of MANAGERS) {
    weeklyByManager[m.id] = weekB2BLeads.filter(l => l.responsible && l.responsible.id === m.id).length;
    allTimeByManager[m.id] = allB2BLeads.filter(l => l.responsible && l.responsible.id === m.id).length;
  }

  return {
    date: dateStr,
    totalCreatedLeads: createdLeads.length,
    managerReports,
    b2bActiveLeads,
    poolStageCounts,
    poolByManager,
    weekStats: {
      mondayStr,
      totalWeekLeads: weekB2BLeads.length,
      weeklyByManager,
      allTimeTotal: allB2BLeads.length,
      allTimeByManager,
      bestDay
    }
  };
}

function formatExecutiveReport(data) {
  const { date, totalCreatedLeads, managerReports, poolStageCounts, poolByManager, weekStats } = data;
  let out = '';
  out += `======================================================\n`;
  out += `👔 УПРАВЛЕНЧЕСКАЯ СВОДКА ДЛЯ РУКОВОДИТЕЛЯ (за ${date})\n`;
  out += `======================================================\n\n`;

  out += `📌 1. ОБЩИЙ ПУЛЬС ОТДЕЛА (ОСНОВНАЯ ВОРОНКА B2B ЗА ВЧЕРА):\n`;
  out += `• Новых лидов за вчера: ${totalCreatedLeads}\n`;
  const totalClosed = managerReports.reduce((s, m) => s + m.closedTasks, 0);
  const totalCreatedTasks = managerReports.reduce((s, m) => s + m.createdTasks, 0);
  const totalOverdue = managerReports.reduce((s, m) => s + m.overdueTasksCount, 0);
  const totalNoTask = managerReports.reduce((s, m) => s + m.leadsNoTaskCount, 0);
  out += `• Задач закрыто: ${totalClosed} | Создано новых: ${totalCreatedTasks}\n`;
  out += `• ⚠️ Просроченных задач на утро: ${totalOverdue} | Сделок в B2B без задач: ${totalNoTask}\n\n`;

  for (const m of managerReports) {
    out += `------------------------------------------------------\n`;
    out += `👤 МЕНЕДЖЕР: ${m.name.toUpperCase()} (${m.email})\n`;
    out += `------------------------------------------------------\n`;
    out += `📥 Новых лидов за день: ${m.totalNewLeads} (Email-аутрич: ${m.emailLeads}, Сайт/Входящие: ${m.siteLeads})\n`;
    out += `✅ Задач закрыто за день: ${mClosedTasksCount(m)} | Поставлено новых: ${m.createdTasks}\n`;
    out += `📂 Всего в работе активных сделок B2B: ${m.totalActiveDeals}\n`;
    out += `🎯 Текущие ключевые этапы: КП — ${m.kpCount}, Договор — ${m.contractCount}, Счёт — ${m.invoiceCount}\n`;
    out += `💰 Выиграно за день: ${m.wonCount} (${m.wonSum} руб.) | Закрыто в отказ: ${m.lostCount}\n\n`;

    out += `🚨 СИГНАЛЫ И ЗОНЫ ВНИМАНИЯ:\n`;
    if (m.overdueTasksCount > 0) {
      out += `  🔴 Просрочено задач: ${m.overdueTasksCount}\n`;
      m.overdueTasksList.forEach(t => {
        const time = t.date_finish ? t.date_finish.substring(11, 16) : '--:--';
        out += `     - [Сделка: ${t.entity ? t.entity.name : 'Без привязки'}] Дедлайн: ${time} | ${t.text.substring(0, 70)}...\n`;
      });
    } else {
      out += `  🟢 Просроченных задач нет — отлично!\n`;
    }

    if (m.leadsNoTaskCount > 0) {
      out += `  🟠 Сделок в работе БЕЗ активных задач: ${m.leadsNoTaskCount}\n`;
      m.leadsNoTaskList.forEach(l => {
        out += `     - [ID ${l.id}] ${l.name} (Этап: «${l.stage.name}»)\n`;
      });
    } else {
      out += `  🟢 Все сделки закрыты задачами — дисциплина 100%!\n`;
    }
    out += `\n`;
  }

  out += `------------------------------------------------------\n`;
  out += `🗂 2. СТАТУС РАЗБОРА СТАРОЙ БАЗЫ («База в проработку»):\n`;
  out += `------------------------------------------------------\n`;
  out += `• В свободном пуле на утро: ${poolStageCounts.pool} сделок (нетронуты)\n`;
  out += `• Взято в работу: ${poolStageCounts.inWork} (факт: никто не перевел ни одной сделки)\n`;
  out += `• Квалифицировано в B2B: ${poolStageCounts.qualified}\n`;
  for (const mId in poolByManager) {
    const pm = poolByManager[mId];
    out += `  - ${pm.name}: в пуле ${pm.pool} сделок | взято в работу: ${pm.inWork} | переведено в B2B: ${pm.qualified}\n`;
  }
  out += `\n`;

  out += `------------------------------------------------------\n`;
  out += `📈 3. НЕДЕЛЬНАЯ И НАКОПИТЕЛЬНАЯ СТАТИСТИКА (С УЧЕТОМ СТАРТА):\n`;
  out += `------------------------------------------------------\n`;
  out += `• Сделок за текущую неделю (с ${weekStats.mondayStr} по ${date}): ${weekStats.totalWeekLeads}\n`;
  for (const m of MANAGERS) {
    const wCount = weekStats.weeklyByManager[m.id] || 0;
    const aCount = weekStats.allTimeByManager[m.id] || 0;
    out += `  - ${m.name}: за неделю ${wCount} сделок | всего в B2B с момента старта: ${aCount}\n`;
  }
  out += `• Рекордный день в воронке: ${weekStats.bestDay.date} (${weekStats.bestDay.count} сделок)\n`;
  out += `• Справка по динамике: Андрей стартовал на 2 дня раньше (база заведена ровно), Лёня оцифровал 3-дневный хвост в ПН и практически выровнял баланс сделок в работе.\n\n`;

  return out;
}

function mClosedTasksCount(m) {
  return m.closedTasks;
}

function formatChatReportCurrent(data) {
  const { date, managerReports, weekStats } = data;
  let out = '';
  out += `======================================================\n`;
  out += `💬 СООБЩЕНИЕ № 1 В ОБЩИЙ ЧАТ (Текущая воронка и фокус)\n`;
  out += `======================================================\n\n`;

  out += `Доброе утро, команда! ☀️\n`;
  out += `Утренний пульс отдела по итогам вчерашнего дня (${date}):\n\n`;

  for (const m of managerReports) {
    out += `⚡️ ${m.name}:\n`;
    out += `• Новых лидов в работе: ${m.totalNewLeads} (Email: ${m.emailLeads} | Сайт/входящие: ${m.siteLeads})\n`;
    out += `• Задач отработано и закрыто: ${m.closedTasks}\n`;
    out += `• Сделок на этапе КП / Согласование: ${m.kpCount + m.contractCount}\n`;
    
    const flags = [];
    if (m.overdueTasksCount > 0) {
      flags.push(`разобрать ${m.overdueTasksCount} хвостов по вчерашним задачам`);
    }
    if (m.leadsNoTaskCount > 0) {
      flags.push(`поставить следующий шаг по ${m.leadsNoTaskCount} ${pluralizeLeads(m.leadsNoTaskCount)} (сейчас без задач)`);
    }

    if (flags.length > 0) {
      out += `• 🎯 Фокус утра: ${flags.join(' и ')}.\n`;
    } else {
      out += `• 🎯 Фокус утра: воронка в порядке, двигаем дальше к оплатам!\n`;
    }
    out += `\n`;
  }

  if (weekStats) {
    out += `🏆 Командный пульс недели:\n`;
    out += `• Всего в работе за неделю: ${weekStats.totalWeekLeads} новых сделок (Лёня: ${weekStats.weeklyByManager[28419] || 0} | Андрей: ${weekStats.weeklyByManager[28418] || 0})\n`;
    out += `• Рекорд недели: ${weekStats.bestDay.count} сделок за один день (${weekStats.bestDay.date})! Отличный общий темп! 🔥\n\n`;
  }

  out += `🔥 Приоритеты в течение дня:\n`;
  out += `1. Скорость реакции: новые заявки с сайта подхватываем в течение 10–15 минут (лиды горячие, важна скорость первого контакта).\n`;
  out += `2. Оперативные задачи и триггеры дня.\n`;
  out += `3. Правило чистоты CRM: ни одна сделка не должна «висеть» без запланированного следующего действия.\n\n`;
  out += `Всем отличного дня и продуктивных переговоров! 🚀\n`;

  return out;
}

function formatChatReportOldBase(data) {
  const { poolStageCounts, poolByManager } = data;
  let out = '';
  out += `======================================================\n`;
  out += `💬 СООБЩЕНИЕ № 2 В ОБЩИЙ ЧАТ (Разбор базы в проработку)\n`;
  out += `======================================================\n\n`;

  out += `Коллеги, важный апдейт по «Базе в проработку» 🗂\n\n`;
  out += `Со вчерашнего дня у нас в пуле распределена 61 сделка:\n`;
  for (const mId in poolByManager) {
    const pm = poolByManager[mId];
    out += `• ${pm.name}: ${pm.pool} сделок в пуле (взято в работу вчера: ${pm.inWork})\n`;
  }
  out += `\nВчера в базу заходили, но в работу пока ни одной сделки не перевели — весь пул так и остался нетронутым.\n\n`;
  out += `🎯 Задача на эту неделю: полностью разобрать эту базу до пятницы (это всего по 6–7 сделок в день на каждого).\n\n`;
  out += `Как с ней работаем после закрытия утренних хвостов:\n`;
  out += `1. Открываем сделку из своего пула и переводим её в этап «Взят в работу» (чтобы было видно, что контакт в проработке).\n`;
  out += `2. Смотрим историю/сайт/контакты и квалифицируем:\n`;
  out += `   - Если клиент живой и целевой ➔ переводим в «Квалифицирован (передать в B2B)» и ставим задачу на созвон/письмо в основной воронке.\n`;
  out += `   - Если отказ / не наш профиль / не актуально ➔ переводим в «Архив / Отказ» с короткой понятной причиной.\n\n`;
  out += `Там уже есть теплый след прошлых коммуникаций, поэтому оттуда можно быстро достать несколько хороших сделок в основную воронку. Давайте сегодня заберём первую пачку в работу! 💪\n`;

  return out;
}

function pluralizeLeads(n) {
  if (n % 10 === 1 && n % 100 !== 11) return 'сделке';
  return 'сделкам';
}

async function main() {
  const targetDateArg = process.argv[2] || '2026-10-12';
  const report = await generateDailyReport(targetDateArg);

  console.log(formatExecutiveReport(report));
  console.log(formatChatReportCurrent(report));
  console.log(formatChatReportOldBase(report));
}

if (require.main === module) {
  main().catch(console.error);
}

module.exports = { generateDailyReport, formatExecutiveReport, formatChatReportCurrent, formatChatReportOldBase, callTool };

