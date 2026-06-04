const API_BASE = window.location.port === "8000" ? window.location.origin : "http://127.0.0.1:8000";
const state = {
  page: 1,
  pageSize: 25,
  sortBy: "risk",
  sortDir: "desc",
  search: "",
  risk: "all",
  vip: "all",
  dateFrom: "",
  dateTo: "",
  commPriority: "all",
  commStatus: "all",
  assignedTo: "all",
  charts: {},
  detailChart: null,
  lastAnalyzedCustomerId: null,
};

const $ = (id) => document.getElementById(id);
const fmt = new Intl.NumberFormat("en-US");
const money = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

async function api(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.detail || data.message || `Request failed: ${response.status}`);
  }
  return data;
}

function runIcons() {
  if (window.lucide) {
    window.lucide.createIcons();
  }
}

function toast(message) {
  const node = document.createElement("div");
  node.className = "toast";
  node.textContent = message;
  $("toastStack").appendChild(node);
  setTimeout(() => node.remove(), 3200);
}

function riskClass(priority, risk) {
  if (priority === "CRITICAL" || risk >= 85) return "critical";
  if (priority === "HIGH" || risk >= 64) return "high";
  if (priority === "MEDIUM" || risk >= 40) return "medium";
  return "low";
}

function renderBadge(text, tone) {
  return `<span class="badge ${tone || ""}">${escapeHtml(text)}</span>`;
}

function renderBilingualList(englishItems = [], arabicItems = []) {
  return arabicItems.map((item, index) => `
    <li class="bilingual-item">
      <span class="arabic" dir="rtl" style="font-size: 1.1em; color: var(--text);">${escapeHtml(item || "")}</span>
      <span class="english" style="font-size: 0.85em; color: var(--muted);">${escapeHtml(englishItems[index] || "")}</span>
    </li>
  `).join("");
}

function renderBilingualTimeline(englishItems = [], arabicItems = []) {
  return arabicItems.map((item, index) => {
    const english = englishItems[index] || {};
    return `
      <div class="timeline-item bilingual-timeline">
        <div class="arabic timeline-ar" dir="rtl">
          <strong>${escapeHtml(item.step || "")}</strong>
          <span>المسؤول: ${escapeHtml(item.owner || "")} | الموعد النهائي: ${escapeHtml(item.deadline || "")}</span>
        </div>
        <div>
          <strong style="color: var(--muted); font-size: 0.9em;">${escapeHtml(english.step)}</strong>
          <span style="font-size: 0.85em;">${escapeHtml(english.owner)} | Deadline: ${escapeHtml(english.deadline)}</span>
        </div>
      </div>
    `;
  }).join("");
}

function renderBilingualValue(english, arabic) {
  return `
    <strong class="arabic mini-ar" dir="rtl">${escapeHtml(arabic || "")}</strong>
    <span style="color: var(--muted); font-size: 0.85em; font-weight: normal;">${escapeHtml(english)}</span>
  `;
}

function renderFeatureEffects(effects = []) {
  if (!effects.length) return `<div class="table-loading">لا تتوفر بيانات عن تأثير الميزات حتى الآن.</div>`;
  return `
    <div class="feature-list">
      ${effects.map((effect) => {
        const increases = effect.direction === "increases_churn";
        return `
          <article class="feature-effect">
            <header>
              <div>
                <strong class="arabic" dir="rtl" style="font-size: 1.1em;">${escapeHtml(effect.label_ar || "")}</strong>
                <span style="font-size: 0.85em; color: var(--muted);">${escapeHtml(effect.label)}</span>
              </div>
              ${renderBadge(increases ? "يزيد من الخطر" : "يقلل من الخطر", increases ? "danger" : "success")}
            </header>
            <div class="impact-meter ${increases ? "increases" : "reduces"}" style="--value:${Math.max(4, effect.relative_strength || 0)}%"><span></span></div>
            <p>القيمة: <strong>${escapeHtml(effect.value)}</strong> | تأثير SHAP: <strong dir="ltr">${escapeHtml(effect.impact)}</strong></p>
            <p class="arabic" dir="rtl" style="font-size: 1.1em;">${escapeHtml(effect.explanation_ar || "")}</p>
            <p style="font-size: 0.85em; color: var(--muted);">${escapeHtml(effect.explanation)}</p>
          </article>
        `;
      }).join("")}
    </div>
  `;
}

function renderNbaRecommendation(nba = {}) {
  const offers = nba.ranked_offers || [];
  if (!offers.length) return `<div class="table-loading">لا يتوفر تصنيف لعروض الإجراء الأفضل حتى الآن.</div>`;
  return `
    <div class="offer-list">
      <p style="font-size: 0.85em; color: var(--muted);">${escapeHtml(nba.architecture || "توليد المرشحين -> التقييم -> التوصية النهائية")}</p>
      <p class="arabic" dir="rtl" style="font-size: 1.1em; margin-bottom: 4px;">${escapeHtml(nba.ranking_reason_ar || "")}</p>
      <p style="font-size: 0.85em; color: var(--muted);">${escapeHtml(nba.ranking_reason || "")}</p>
      ${offers.map((offer, index) => `
        <article class="offer-card">
          <header>
            <div class="offer-rank">#${index + 1}</div>
            <div>
              <strong class="arabic" dir="rtl" style="font-size: 1.1em;">${escapeHtml(offer.title_ar || "")}</strong>
              <span style="font-size: 0.85em; color: var(--muted);">${escapeHtml(offer.title)}</span>
            </div>
            ${index === 0 ? renderBadge("الإجراء المختار", "success") : renderBadge(`التقييم ${offer.net_value_score}`, "")}
          </header>
          <p class="arabic" dir="rtl" style="font-size: 1.1em; margin-bottom: 4px;">${escapeHtml(offer.action_ar || "")}</p>
          <p style="font-size: 0.85em; color: var(--muted);">${escapeHtml(offer.action)}</p>
          <p>الفعالية: <strong>${escapeHtml(offer.effectiveness_score)}</strong> | التكلفة: <strong dir="ltr">${money.format(Number(offer.estimated_cost || 0))}</strong></p>
        </article>
      `).join("")}
    </div>
  `;
}

function renderLlamaReport(report = {}) {
  const english = report.english || {};
  const arabic = report.arabic || {};
  const sections = [
    ["الملخص التنفيذي للأعمال", "executive_summary"],
    ["الأسباب الجذرية لخطر الإلغاء", "key_drivers"],
    ["التأثير المالي والإيرادات", "revenue_impact"],
    ["خطة العمل الاستراتيجية", "action_plan"],
    ["مسودة التخاطب مع العميل", "agent_script"]
  ];
  return `
    <div class="llama-report">
      ${renderBadge(report.source || "local_fallback", report.source === "groq_llama" ? "success" : "warning")}
      ${sections.map(([title, key]) => {
        const enValue = Array.isArray(english[key]) ? english[key].join(" | ") : english[key];
        const arValue = Array.isArray(arabic[key]) ? arabic[key].join(" | ") : arabic[key];
        if (!enValue && !arValue) return "";
        return `
          <article class="llama-section">
            <h4 class="arabic" dir="rtl" style="margin-bottom: 12px; border-bottom: 1px solid var(--line); padding-bottom: 4px;">${escapeHtml(title)}</h4>
            <p class="arabic" dir="rtl" style="font-size: 1.1em; line-height: 1.7; margin-bottom: 8px;">${escapeHtml(arValue || "")}</p>
            <p style="font-size: 0.85em; color: var(--muted);">${escapeHtml(enValue || "")}</p>
          </article>
        `;
      }).join("")}
    </div>
  `;
}

function chartColors() {
  const text = getComputedStyle(document.documentElement).getPropertyValue("--muted").trim();
  return {
    text,
    grid: "rgba(148, 163, 184, 0.16)",
    teal: "#2dd4bf",
    blue: "#60a5fa",
    yellow: "#fbbf24",
    red: "#fb7185",
    green: "#34d399",
    violet: "#a78bfa",
  };
}

function createChart(id, config) {
  if (!window.Chart) return;
  const canvas = $(id);
  if (!canvas) return;
  if (state.charts[id]) state.charts[id].destroy();
  const colors = chartColors();
  const baseOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { labels: { color: colors.text, boxWidth: 12 } },
      tooltip: { intersect: false, mode: "index" },
    },
    scales: {
      x: { ticks: { color: colors.text }, grid: { color: colors.grid } },
      y: { ticks: { color: colors.text }, grid: { color: colors.grid } },
    },
  };
  state.charts[id] = new Chart(canvas, {
    ...config,
    options: { ...baseOptions, ...(config.options || {}) },
  });
}

function renderKpis(overview) {
  const cards = [
    ["إجمالي العملاء", fmt.format(overview.total_customers), "العملاء المحفوظون", ""],
    ["مخاطر منخفضة", fmt.format(overview.low_risk_users), "المخاطرة أقل من 40%", "success"],
    ["مخاطر متوسطة", fmt.format(overview.medium_risk_users), "المخاطرة من 40% إلى 63.99%", "warning"],
    ["مخاطر عالية", fmt.format(overview.high_risk_band_users), "المخاطرة من 64% إلى 84.99%", "critical"],
    ["مخاطر حرجة", fmt.format(overview.critical_risk_users), "المخاطرة 85% أو أعلى", "critical"],
    ["الإيرادات المعرضة للخطر", money.format(overview.revenue_at_risk), "الإيرادات المتوقع فقدانها", "critical"],
    ["عملاء VIP", fmt.format(overview.vip_customers), "الحسابات المميزة المراقبة", ""],
    ["متوسط التسرب", `${overview.average_churn}%`, "نقاط المخاطرة المدمجة", ""],
    ["تدخلات الذكاء الاصطناعي", fmt.format(overview.ai_interventions_triggered), "سير العمل المفعّل", ""],
    ["نجاح الاحتفاظ", `${overview.retention_success_rate}%`, "الصحة النموذجية للاحتفاظ", "success"],
  ];
  $("kpiGrid").innerHTML = cards.map(([label, value, hint, tone]) => `
    <article class="kpi-card ${tone}">
      <span>${label}</span>
      <strong dir="ltr">${value}</strong>
      <small>${hint}</small>
    </article>
  `).join("");
  $("modelStatus").textContent = overview.model_status === "online" ? "النموذج متصل" : "النموذج غير متصل";
}

function renderOverviewCharts(analytics) {
  const c = chartColors();
  createChart("churnChart", {
    type: "doughnut",
    data: {
      labels: Object.keys(analytics.churn_distribution),
      datasets: [{ data: Object.values(analytics.churn_distribution), backgroundColor: [c.green, c.yellow, c.blue, c.red], borderWidth: 0 }],
    },
    options: { cutout: "62%", scales: {} },
  });
  createChart("trendChart", {
    type: "line",
    data: {
      labels: analytics.monthly_retention_trends.map((item) => item.month),
      datasets: [
        { label: "الاحتفاظ", data: analytics.monthly_retention_trends.map((item) => item.retention), borderColor: c.green, backgroundColor: "rgba(52, 211, 153, 0.12)", fill: true, tension: 0.35 },
        { label: "المخاطرة", data: analytics.monthly_retention_trends.map((item) => item.risk), borderColor: c.red, backgroundColor: "rgba(251, 113, 133, 0.08)", tension: 0.35 },
      ],
    },
  });
  createChart("revenueChart", {
    type: "bar",
    data: {
      labels: Object.keys(analytics.revenue_impact),
      datasets: [{ label: "الإيرادات", data: Object.values(analytics.revenue_impact), backgroundColor: [c.green, c.yellow, c.red], borderRadius: 8 }],
    },
  });
  createChart("actionChart", {
    type: "polarArea",
    data: {
      labels: Object.keys(analytics.ai_action_distribution),
      datasets: [{ data: Object.values(analytics.ai_action_distribution), backgroundColor: [c.green, c.yellow, c.blue, c.red, c.violet] }],
    },
    options: { scales: { r: { ticks: { color: c.text, backdropColor: "transparent" }, grid: { color: c.grid } } } },
  });
  createChart("segmentChart", {
    type: "bar",
    data: {
      labels: analytics.customer_segmentation.map((item) => item.segment),
      datasets: [
        { label: "العملاء", data: analytics.customer_segmentation.map((item) => item.count), backgroundColor: c.blue, borderRadius: 8 },
        { label: "متوسط المخاطرة", data: analytics.customer_segmentation.map((item) => item.avg_risk), backgroundColor: c.red, borderRadius: 8 },
      ],
    },
  });
  createChart("vipChart", {
    type: "doughnut",
    data: {
      labels: Object.keys(analytics.vip_vs_non_vip),
      datasets: [{ data: Object.values(analytics.vip_vs_non_vip), backgroundColor: [c.teal, c.blue], borderWidth: 0 }],
    },
    options: { cutout: "64%", scales: {} },
  });
  renderHeatmap(analytics.risk_heatmap);
}

function renderHeatmap(rows) {
  if (!rows.length) {
    $("riskHeatmap").innerHTML = `<div class="table-loading">لا تتوفر بيانات للشرائح حتى الآن.</div>`;
    return;
  }
  const maxValue = Math.max(...rows.flatMap((row) => [row.low, row.medium, row.high, row.critical]));
  $("riskHeatmap").innerHTML = rows.map((row) => `
    <div class="heat-row">
      <strong>${escapeHtml(row.segment)}</strong>
      <div class="heat-cell" style="--intensity:${Math.max(0.18, row.low / maxValue)}">${row.low}</div>
      <div class="heat-cell medium" style="--intensity:${Math.max(0.18, row.medium / maxValue)}">${row.medium}</div>
      <div class="heat-cell high" style="--intensity:${Math.max(0.18, row.high / maxValue)}">${row.high}</div>
      <div class="heat-cell critical" style="--intensity:${Math.max(0.18, row.critical / maxValue)}">${row.critical}</div>
    </div>
  `).join("");
}

async function loadOverview() {
  const [overview, analytics] = await Promise.all([
    api("/api/v1/dashboard-overview"),
    api("/api/v1/analytics"),
  ]);
  renderKpis(overview);
  renderOverviewCharts(analytics);
  renderRealtimeOverview(overview);
  runIcons();
}

function customerQuery() {
  const params = new URLSearchParams({
    page: state.page,
    page_size: state.pageSize,
    search: state.search,
    risk: state.risk,
    vip: state.vip,
    sort_by: state.sortBy,
    sort_dir: state.sortDir,
    date_from: state.dateFrom,
    date_to: state.dateTo,
    comm_priority: state.commPriority,
    comm_status: state.commStatus,
    assigned_to: state.assignedTo,
  });
  return `/api/v1/customers?${params.toString()}`;
}

async function loadCustomers() {
  $("customersBody").innerHTML = `<tr><td colspan="11"><div class="table-loading">جاري تحميل العملاء...</div></td></tr>`;
  const data = await api(customerQuery());
  if (!data.items.length) {
    $("customersBody").innerHTML = `
      <tr><td colspan="11"><div class="table-loading">لا يوجد عملاء محفوظون حتى الآن. قم بتحليل عميل واحد أو ارفع ملف CSV لملء هذه اللوحة.</div></td></tr>
    `;
    $("paginationText").textContent = `الصفحة ${data.page} من ${data.pages} | ${fmt.format(data.total)} عميل`;
    $("prevPage").disabled = true;
    $("nextPage").disabled = true;
    return;
  }
  $("customersBody").innerHTML = data.items.map((row) => {
    const tone = riskClass(row.priority, row.risk);
    const cp = row.communication_plan || {};
    const overdueClass = cp.status === "Overdue" ? "status-overdue" : "";
    
    return `
      <tr class="${tone === "critical" ? "row-critical" : ""} ${overdueClass}" data-customer-id="${escapeHtml(row.customer_id)}">
        <td><strong>${escapeHtml(row.customer_id)}</strong></td>
        <td>${row.risk.toFixed(2)}<div class="risk-bar ${tone}" style="--value:${row.risk}%"><span></span></div></td>
        <td>${renderBadge(row.vip_status, row.vip_status === "VIP" ? "success" : "")}</td>
        <td dir="ltr">${money.format(row.revenue)}</td>
        <td>
          <div class="comm-plan-cell">
            <div class="comm-date-row">
              <strong dir="ltr">${escapeHtml(cp.followup_date)}</strong>
              ${renderBadge(cp.status, cp.status === 'Overdue' ? 'danger' : cp.status === 'Completed' ? 'success' : 'warning')}
            </div>
            <div style="font-size: 12px; color: var(--muted); margin-bottom: 4px;">
              ${escapeHtml(cp.followup_type)} • <span style="color: var(--text);">${escapeHtml(cp.assigned_to)}</span> • 
              ${renderBadge(cp.priority, cp.priority === 'High' ? 'danger' : cp.priority === 'Medium' ? 'warning' : 'success')}
            </div>
            <div style="font-size: 12px; max-width: 250px; white-space: normal;">${escapeHtml(cp.notes)}</div>
          </div>
        </td>
        <td>${renderBadge(`${row.priority} ${row.priority_score}`, tone === "critical" ? "danger" : tone === "high" ? "warning" : "")}</td>
        <td dir="ltr">${new Date(row.last_activity).toLocaleDateString()}</td>
        <td><button class="small-button danger-action" type="button" data-delete-customer="${escapeHtml(row.customer_id)}" aria-label="حذف ${escapeHtml(row.customer_id)}"><i data-lucide="trash-2"></i></button></td>
      </tr>
    `;
  }).join("");
  $("paginationText").textContent = `الصفحة ${data.page} من ${data.pages} | ${fmt.format(data.total)} عميل`;
  $("prevPage").disabled = data.page <= 1;
  $("nextPage").disabled = data.page >= data.pages;
  runIcons();
}

function renderInsights(analysis, meta = {}) {
  const tone = riskClass(meta.priority || analysis.risk_level, meta.risk || analysis.priority_score);
  const riskColor = tone === "critical" ? "var(--danger)" : tone === "high" ? "var(--warning)" : tone === "medium" ? "var(--brand-2)" : "var(--success)";
  return `
    <div class="insights-head">
      <div>
        <p class="eyebrow">نتائج نموذج اللغة المنظمة</p>
        <h2>الملخص التنفيذي</h2>
        <p class="arabic" dir="rtl">${escapeHtml(analysis.summary_ar || "")}</p>
        <p style="font-size: 0.85em; color: var(--muted);">${escapeHtml(analysis.summary)}</p>
        ${renderBadge(analysis.risk_level, tone === "critical" ? "danger" : tone === "high" ? "warning" : "success")}
      </div>
      <div class="score-ring" style="--score:${Number(meta.risk || analysis.priority_score)};--risk-color:${riskColor}">
        <div><strong>${Number(meta.risk || analysis.priority_score).toFixed(0)}%</strong><span>درجة المخاطرة</span></div>
      </div>
    </div>

    <div class="insight-grid">
      <div class="mini-card"><span>درجة الأولوية</span><strong>${analysis.priority_score}</strong></div>
      <div class="mini-card"><span>ثقة الذكاء الاصطناعي</span><strong>${analysis.ai_confidence_score}%</strong></div>
      <div class="mini-card"><span>الانطباع</span>${renderBilingualValue(analysis.customer_sentiment, analysis.customer_sentiment_ar)}</div>
      <div class="mini-card"><span>التدخل البشري</span><strong>${analysis.human_intervention_required ? "مطلوب" : "غير مطلوب"}</strong></div>
      <div class="mini-card"><span>الإجراء الأفضل التالي</span>${renderBilingualValue(analysis.next_best_action, analysis.next_best_action_ar)}</div>
      <div class="mini-card"><span>عرض مخصص</span>${renderBilingualValue(analysis.personalized_offer, analysis.personalized_offer_ar)}</div>
    </div>

    <details class="collapsible" open>
      <summary>الأسباب الرئيسية | Root Causes</summary>
      <div class="collapsible-content"><ul class="bullet-list">${renderBilingualList(analysis.main_reasons, analysis.main_reasons_ar)}</ul></div>
    </details>
    <details class="collapsible" open>
      <summary>توصيات الذكاء الاصطناعي | AI Recommendations</summary>
      <div class="collapsible-content"><ul class="bullet-list">${renderBilingualList(analysis.recommended_actions, analysis.recommended_actions_ar)}</ul></div>
    </details>
    <details class="collapsible" open>
      <summary>استراتيجية الاحتفاظ | Retention Strategy</summary>
      <div class="collapsible-content">
        <p class="arabic strategy-ar" dir="rtl">${escapeHtml(analysis.retention_strategy_ar || "")}</p>
        <p style="font-size: 0.85em; color: var(--muted); margin-top: 10px;">${escapeHtml(analysis.retention_strategy)}</p>
      </div>
    </details>
    <details class="collapsible" open>
      <summary>الجدول الزمني للإجراءات | Action Timeline</summary>
      <div class="collapsible-content timeline">
        ${renderBilingualTimeline(analysis.timeline, analysis.timeline_ar)}
      </div>
    </details>
    <details class="collapsible" open>
      <summary>تأثير الميزات | XGBoost SHAP</summary>
      <div class="collapsible-content">${renderFeatureEffects(analysis.feature_effects)}</div>
    </details>
    <details class="collapsible" open>
      <summary>تصنيف الإجراء الأفضل | NBA</summary>
      <div class="collapsible-content">${renderNbaRecommendation(analysis.nba_recommendation)}</div>
    </details>
    <details class="collapsible" open>
      <summary>تقرير استراتيجية LLaMA | Groq</summary>
      <div class="collapsible-content">${renderLlamaReport(analysis.llama_report)}</div>
    </details>
  `;
}

function readPredictionPayload() {
  return {
    user_id: ($("user_id")?.value || "").trim(),
    avg_plan_price: Number($("avg_plan_price")?.value || 0),
    total_amount_paid: Number($("total_amount_paid")?.value || 0),
    total_transactions: Number($("total_transactions")?.value || 0),
    billing_tenure_days: Number($("billing_tenure_days")?.value || 0),
    auto_renew_count: Number($("auto_renew_count")?.value || 0),
    total_cancellations: Number($("total_cancellations")?.value || 0),
  };
}

async function analyzeCustomer(event) {
  event.preventDefault();
  const button = $("analyzeBtn");
  button.disabled = true;
  button.querySelector("span").textContent = "جاري التحليل...";
  $("insightsPanel").innerHTML = `<div class="empty-state skeleton"></div>`;
  try {
    const result = await api(`/api/v1/analyze-risk?use_llm=${$("useLlama").checked ? "true" : "false"}`, {
      method: "POST",
      body: JSON.stringify(readPredictionPayload()),
    });
    state.lastAnalyzedCustomerId = result.customer_id;
    $("insightsPanel").innerHTML = renderInsights(result.llm_analysis, {
      risk: result.churn_risk_percentage,
      priority: result.priority,
    }) + `
      <div class="advanced-analysis-cta" style="margin-top:16px;text-align:center;">
        <button class="primary-button" id="advancedAnalysisBtn" type="button" style="max-width:420px;margin:0 auto;">
          <i data-lucide="brain-circuit"></i>
          <span>تشغيل التحليل المتقدم (SHAP + LLaMA)</span>
        </button>
        <p style="margin:8px 0 0;font-size:12px;color:var(--muted);">تشغيل توضيح SHAP الفعلي + استنتاج Groq LLaMA العميق</p>
      </div>
    `;
    runIcons();
    const advBtn = $("advancedAnalysisBtn");
    if (advBtn) {
      advBtn.addEventListener("click", () => runAdvancedAnalysis(readPredictionPayload()));
    }
    await Promise.all([loadOverview(), loadCustomers(), loadRealtime()]);
    toast(`التحليل المنظم جاهز لـ ${result.customer_id}`);
  } catch (error) {
    $("insightsPanel").innerHTML = `<div class="empty-state"><h2>فشل التحليل</h2><p>${escapeHtml(error.message)}</p></div>`;
  } finally {
    button.disabled = false;
    button.querySelector("span").textContent = "تحليل العميل";
    runIcons();
  }
}

async function runAdvancedAnalysis(payload) {
  const advBtn = $("advancedAnalysisBtn");
  if (advBtn) {
    advBtn.disabled = true;
    advBtn.querySelector("span").textContent = "جاري تشغيل SHAP + LLaMA...";
  }
  try {
    const result = await api("/api/v1/analyze-risk-detailed", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    $("insightsPanel").innerHTML = `
      <div style="display:flex;gap:8px;margin-bottom:12px;flex-wrap:wrap;">
        ${renderBadge("SHAP: " + (result.shap_available ? "نشط" : "احتياطي"), result.shap_available ? "success" : "warning")}
        ${renderBadge("LLM: " + (result.llm_source || "غير معروف"), result.llm_source === "groq_llama" ? "success" : "warning")}
      </div>
    ` + renderInsights(result.llm_analysis, {
      risk: result.churn_risk_percentage,
      priority: result.priority,
    });
    await Promise.all([loadOverview(), loadCustomers(), loadRealtime()]);
    toast(`اكتمل التحليل المتقدم للذكاء الاصطناعي لـ ${result.customer_id}`);
  } catch (error) {
    toast("فشل التحليل المتقدم: " + error.message);
    if (advBtn) {
      advBtn.disabled = false;
      advBtn.querySelector("span").textContent = "تشغيل التحليل المتقدم (SHAP + LLaMA)";
    }
  }
  runIcons();
}

function readCsvFile(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ""));
    reader.onerror = () => reject(reader.error || new Error("Could not read CSV file."));
    reader.readAsText(file);
  });
}

async function uploadCsvCustomers() {
  const file = $("csvFileInput").files[0];
  if (!file) {
    toast("اختر ملف CSV أولاً");
    return;
  }
  const button = $("uploadCsvBtn");
  if(button) {
      button.disabled = true;
      button.querySelector("span").textContent = "جاري تحليل CSV...";
  }
  if($("csvUploadStatus")) $("csvUploadStatus").textContent = "جاري قراءة وتقييم صفوف CSV...";
  try {
    const csvText = await readCsvFile(file);
    const result = await api("/api/v1/customers/upload-csv", {
      method: "POST",
      body: JSON.stringify({ csv_text: csvText }),
    });
    if($("csvUploadStatus")) $("csvUploadStatus").textContent = `تم استيراد ${result.imported} عميل. ${result.errors.length ? `تم تخطي ${result.errors.length} صف.` : "لا توجد أخطاء في الصفوف."}`;
    await Promise.all([loadOverview(), loadCustomers(), loadRealtime()]);
    toast(`اكتمل تحليل CSV: تم حفظ ${result.imported} عميل`);
  } catch (error) {
    if($("csvUploadStatus")) $("csvUploadStatus").textContent = error.message;
    toast("فشل رفع CSV");
  } finally {
    if(button) {
        button.disabled = false;
        button.querySelector("span").textContent = "تحليل CSV";
    }
    runIcons();
  }
}

async function deleteCustomer(customerId) {
  if (!confirm(`هل تريد إزالة ${customerId} من بيانات اللوحة المحفوظة؟`)) return;
  await api(`/api/v1/customer/${encodeURIComponent(customerId)}`, { method: "DELETE" });
  closeDrawer();
  await Promise.all([loadOverview(), loadCustomers(), loadRealtime()]);
  toast(`تم إزالة ${customerId}`);
}

async function openCustomer(customerId) {
  $("customerDrawer").classList.add("open");
  $("customerDrawer").setAttribute("aria-hidden", "false");
  $("drawerContent").innerHTML = `<div class="empty-state skeleton"></div>`;
  try {
    const customer = await api(`/api/v1/customer/${encodeURIComponent(customerId)}`);
    $("drawerTitle").textContent = customer.customer_id;
    $("drawerContent").innerHTML = `
      <section class="panel">
        <div class="panel-header">
          <div><h2>تحليلات الملف الشخصي</h2><p>البيانات المحفوظة لهذا العميل.</p></div>
          <div class="report-actions">
            <button class="small-button" type="button" data-print-customer="${escapeHtml(customer.customer_id)}" aria-label="حفظ PDF ${escapeHtml(customer.customer_id)}"><i data-lucide="file-down"></i></button>
            <button class="small-button danger-action" type="button" data-delete-customer="${escapeHtml(customer.customer_id)}" aria-label="حذف ${escapeHtml(customer.customer_id)}"><i data-lucide="trash-2"></i></button>
          </div>
        </div>
        <div class="insight-grid">
          <div class="mini-card"><span>الإيرادات</span><strong dir="ltr">${money.format(customer.revenue)}</strong></div>
          <div class="mini-card"><span>مدة الاشتراك</span><strong dir="ltr">${fmt.format(customer.tenure)} يوم</strong></div>
          <div class="mini-card"><span>معدل الإلغاء</span><strong dir="ltr">${(customer.cancel_rate * 100).toFixed(1)}%</strong></div>
          <div class="mini-card"><span>الشريحة</span><strong>${escapeHtml(customer.segment)}</strong></div>
          <div class="mini-card"><span>قرار الذكاء الاصطناعي</span><strong>${escapeHtml(customer.ai_decision.replaceAll("_", " "))}</strong></div>
          <div class="mini-card"><span>الحالة</span><strong>${escapeHtml(customer.retention_status)}</strong></div>
        </div>
        <div class="chart-wrap"><canvas id="detailTrendChart"></canvas></div>
      </section>
      <section class="panel">${renderInsights(customer.llm_analysis, { risk: customer.risk, priority: customer.priority })}</section>
      <section class="panel">
        <div class="panel-header"><div><h2>سجل الإجراءات</h2><p>أحداث سير العمل والنموذج الأخيرة.</p></div></div>
        <div class="timeline">
          ${customer.action_history.map((item) => `
            <div class="timeline-item"><strong>${escapeHtml(item.event)}</strong><span>${escapeHtml(item.owner)} | <span dir="ltr">${new Date(item.timestamp).toLocaleString()}</span></span></div>
          `).join("")}
        </div>
      </section>
    `;
    if (window.Chart) {
      if (state.detailChart) state.detailChart.destroy();
      const c = chartColors();
      state.detailChart = new Chart($("detailTrendChart"), {
        type: "line",
        data: {
          labels: customer.monthly_risk.map((item) => `M${item.month}`),
          datasets: [{ label: "Churn trend", data: customer.monthly_risk.map((item) => item.risk), borderColor: c.red, backgroundColor: "rgba(251, 113, 133, 0.12)", fill: true, tension: 0.35 }],
        },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { labels: { color: c.text } } }, scales: { x: { ticks: { color: c.text }, grid: { color: c.grid } }, y: { ticks: { color: c.text }, grid: { color: c.grid } } } },
      });
    }
  } catch (error) {
    $("drawerContent").innerHTML = `<div class="empty-state"><h2>تعذر تحميل العميل</h2><p>${escapeHtml(error.message)}</p></div>`;
  }
  runIcons();
}

function closeDrawer() {
  $("customerDrawer").classList.remove("open");
  $("customerDrawer").setAttribute("aria-hidden", "true");
}

function reportShell(title, body) {
  return `
    <!doctype html>
    <html lang="ar" dir="rtl">
    <head>
      <meta charset="utf-8" />
      <title>${escapeHtml(title)}</title>
      <style>
        body { font-family: Tajawal, Arial, sans-serif; margin: 32px; color: #111827; line-height: 1.5; direction: rtl; text-align: right; }
        h1 { margin: 0 0 8px; font-size: 28px; }
        h2 { margin-top: 24px; border-bottom: 1px solid #d1d5db; padding-bottom: 6px; }
        h3 { margin-bottom: 6px; }
        .meta { color: #64748b; margin-bottom: 24px; }
        .grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
        .card, .section { border: 1px solid #d1d5db; border-radius: 8px; padding: 12px; margin: 10px 0; }
        .badge { display: inline-block; padding: 4px 8px; border-radius: 999px; background: #e0f2fe; color: #075985; font-weight: 700; }
        .arabic { direction: rtl; text-align: right; font-family: Tajawal, Arial, sans-serif; }
        table { width: 100%; border-collapse: collapse; margin-top: 12px; }
        th, td { border: 1px solid #d1d5db; padding: 8px; text-align: right; }
        th { background: #f8fafc; }
        @media print { button { display: none; } body { margin: 18mm; } }
      </style>
    </head>
    <body>
      <button onclick="window.print()">حفظ كـ PDF</button>
      <h1>${escapeHtml(title)}</h1>
      <div class="meta" dir="ltr" style="text-align: right;">تم الإنشاء في ${new Date().toLocaleString()} من مركز القيادة</div>
      ${body}
      <script>setTimeout(() => window.print(), 350);</script>
    </body>
    </html>
  `;
}

function openPrintWindow(title, body) {
  const win = window.open("", "_blank");
  if (!win) {
    toast("يرجى السماح بالنوافذ المنبثقة لحفظ تقارير PDF");
    return;
  }
  win.document.open();
  win.document.write(reportShell(title, body));
  win.document.close();
}

async function saveOverviewPdf() {
  const [overview, analytics, customers] = await Promise.all([
    api("/api/v1/dashboard-overview"),
    api("/api/v1/analytics"),
    api("/api/v1/customers?page_size=100&sort_by=risk&sort_dir=desc"),
  ]);
  const body = `
    <section class="grid">
      <div class="card"><strong>إجمالي العملاء</strong><br>${fmt.format(overview.total_customers)}</div>
      <div class="card"><strong>مخاطر منخفضة</strong><br>${fmt.format(overview.low_risk_users)}</div>
      <div class="card"><strong>مخاطر متوسطة</strong><br>${fmt.format(overview.medium_risk_users)}</div>
      <div class="card"><strong>مخاطر عالية</strong><br>${fmt.format(overview.high_risk_band_users)}</div>
      <div class="card"><strong>مخاطر حرجة</strong><br>${fmt.format(overview.critical_risk_users)}</div>
      <div class="card"><strong>الإيرادات المعرضة للخطر</strong><br><span dir="ltr">${money.format(overview.revenue_at_risk)}</span></div>
    </section>
    <h2>توزيع المخاطر</h2>
    <table><tbody>${Object.entries(analytics.churn_distribution).map(([key, value]) => `<tr><th>${escapeHtml(key)}</th><td>${fmt.format(value)}</td></tr>`).join("")}</tbody></table>
    <h2>أكثر العملاء عرضة للخطر</h2>
    <table>
      <thead><tr><th>العميل</th><th>الخطر</th><th>الأولوية</th><th>القرار</th><th>الإيرادات</th></tr></thead>
      <tbody>${customers.items.map((row) => `<tr><td>${escapeHtml(row.customer_id)}</td><td>${row.risk}%</td><td>${escapeHtml(row.priority)}</td><td>${escapeHtml(row.ai_decision)}</td><td dir="ltr">${money.format(row.revenue)}</td></tr>`).join("")}</tbody>
    </table>
    <h2>ملاحظات تنفيذية</h2>
    <p>تستند هذه النظرة العامة فقط إلى العملاء المحفوظين من خلال التحليل اليدوي أو رفع CSV.</p>
  `;
  openPrintWindow("تقرير نظرة عامة لعمليات مخاطر الذكاء الاصطناعي", body);
}

async function saveCustomerPdf(customerId) {
  const customer = await api(`/api/v1/customer/${encodeURIComponent(customerId)}`);
  const analysis = customer.llm_analysis || {};
  const report = analysis.llama_report || {};
  const en = report.english || {};
  const ar = report.arabic || {};
  const body = `
    <section class="grid">
      <div class="card"><strong>الخطر</strong><br>${customer.risk}%</div>
      <div class="card"><strong>الأولوية</strong><br>${escapeHtml(customer.priority)}</div>
      <div class="card"><strong>الإيرادات</strong><br><span dir="ltr">${money.format(customer.revenue)}</span></div>
      <div class="card"><strong>VIP</strong><br>${escapeHtml(customer.vip_status)}</div>
      <div class="card"><strong>معدل الإلغاء</strong><br>${(customer.cancel_rate * 100).toFixed(1)}%</div>
      <div class="card"><strong>قرار الذكاء الاصطناعي</strong><br>${escapeHtml(customer.ai_decision)}</div>
    </section>
    <h2>الإجراء الأفضل التالي</h2>
    <div class="section">
      <p class="arabic">${escapeHtml(analysis.next_best_action_ar || "")}</p>
      <p style="font-size: 0.85em; color: var(--muted);">${escapeHtml(analysis.next_best_action)}</p>
    </div>
    <h2>تأثير الميزات</h2>
    ${renderFeatureEffects(analysis.feature_effects || customer.feature_effects || [])}
    <h2>تصنيف الإجراء الأفضل (NBA)</h2>
    ${renderNbaRecommendation(analysis.nba_recommendation || customer.nba_recommendation || {})}
    <h2>تقرير الاحتفاظ LLaMA</h2>
    <div class="section"><h3>عربي</h3><p class="arabic">${escapeHtml(ar.churn_risk_summary || "")}</p><p class="arabic">${escapeHtml(ar.behavioral_diagnosis || "")}</p></div>
    <div class="section"><h3>إنجليزي</h3><p>${escapeHtml(en.churn_risk_summary || "")}</p><p>${escapeHtml(en.behavioral_diagnosis || "")}</p></div>
    <h2>الجدول الزمني</h2>
    <table><tbody>${(analysis.timeline || []).map((item) => `<tr><td>${escapeHtml(item.step)}</td><td>${escapeHtml(item.owner)}</td><td>${escapeHtml(item.deadline)}</td></tr>`).join("")}</tbody></table>
  `;
  openPrintWindow(`تقرير الاحتفاظ بالعميل - ${customer.customer_id}`, body);
}

function renderRealtimeOverview(overview) {
  $("alertList").innerHTML = overview.alerts.length ? overview.alerts.map((alert) => `
    <div class="alert-item">
      <strong>${escapeHtml(alert.customer_id)} | <span dir="ltr">${alert.risk.toFixed(2)}%</span></strong>
      <span>${escapeHtml(alert.message)}</span>
    </div>
  `).join("") : `<div class="alert-item"><strong>لا يوجد عملاء ذوي مخاطر عالية محفوظون</strong><span>قم بتحليل العملاء أو رفع CSV لملء التنبيهات.</span></div>`;
  $("activityFeed").innerHTML = overview.activity_feed.length ? overview.activity_feed.map((item) => `
    <div class="activity-item">
      <strong>${escapeHtml(item.message)}</strong>
      <span dir="ltr">${new Date(item.timestamp).toLocaleString()}</span>
    </div>
  `).join("") : `<div class="activity-item"><strong>لا يوجد نشاط بعد</strong><span>التحليلات المحفوظة ستظهر هنا.</span></div>`;
}

async function loadRealtime() {
  const realtime = await api("/api/v1/realtime");
  const extra = realtime.alerts.map((alert) => `
    <div class="alert-item">
      <strong>${escapeHtml(alert.title)}</strong>
      <span>${escapeHtml(alert.detail)}</span>
    </div>
  `).join("");
  $("alertList").insertAdjacentHTML("afterbegin", extra);
}

function setView(view) {
  if (!$(`${view}View`)) view = "overview";
  document.querySelectorAll(".view").forEach((node) => node.classList.remove("active"));
  document.querySelectorAll(".nav-item").forEach((node) => node.classList.toggle("active", node.dataset.view === view));
  $(`${view}View`).classList.add("active");
}

function bindEvents() {
  document.querySelectorAll(".nav-item").forEach((item) => {
    item.addEventListener("click", (event) => {
      event.preventDefault();
      const view = item.dataset.view;
      history.replaceState(null, "", `#${view}`);
      setView(view);
    });
  });

  $("themeToggle").addEventListener("click", () => {
    const next = document.documentElement.dataset.theme === "light" ? "dark" : "light";
    document.documentElement.dataset.theme = next;
    localStorage.setItem("retention-theme", next);
    setTimeout(() => loadOverview().catch(console.error), 80);
  });

  $("refreshBtn").addEventListener("click", async () => {
    await Promise.all([loadOverview(), loadCustomers(), loadRealtime()]);
    toast("تم تحديث اللوحة");
  });
  $("overviewPdfBtn").addEventListener("click", () => {
    saveOverviewPdf().catch((error) => toast(error.message));
  });

  $("predictionForm").addEventListener("submit", analyzeCustomer);

  // Smart CSV Drag & Drop Support
  ['ready', 'raw'].forEach(mode => {
    const dropzone = $(`dropzone-${mode}`);
    if (!dropzone) return;

    ['dragover', 'dragleave', 'drop'].forEach(evt => {
      dropzone.addEventListener(evt, (e) => {
        e.preventDefault();
        e.stopPropagation();
      });
    });

    dropzone.addEventListener('dragover', () => dropzone.style.borderColor = 'var(--brand)');
    dropzone.addEventListener('dragleave', () => dropzone.style.borderColor = '');
    dropzone.addEventListener('drop', (e) => {
      dropzone.style.borderColor = '';
      const file = e.dataTransfer.files[0];
      if (file && file.name.endsWith('.csv')) {
        const reader = new FileReader();
        reader.onload = (evt) => {
          csvFiles[mode] = evt.target.result;
          toast(`الملف "${file.name}" جاهز لوضع ${mode}`);
          const span = dropzone.querySelector('span');
          if (span) span.textContent = `✓ ${file.name}`;
        };
        reader.readAsText(file);
      } else {
        toast("يرجى سحب ملف .csv صالح");
      }
    });
  });

  $("fillExampleBtn").addEventListener("click", () => {
    $("user_id").value = "VIP-USER-777";
    $("avg_plan_price").value = 1200;
    $("total_amount_paid").value = 8600;
    $("total_transactions").value = 8;
    $("billing_tenure_days").value = 95;
    $("auto_renew_count").value = 0;
    $("total_cancellations").value = 3;
  });

  $("customerSearch").addEventListener("input", (event) => {
    state.search = event.target.value;
    state.page = 1;
    clearTimeout(state.searchTimer);
    state.searchTimer = setTimeout(() => loadCustomers().catch(console.error), 250);
  });
  $("riskFilter").addEventListener("change", (event) => {
    state.risk = event.target.value;
    state.page = 1;
    loadCustomers().catch(console.error);
  });
  $("vipFilter").addEventListener("change", (event) => {
    state.vip = event.target.value;
    state.page = 1;
    loadCustomers().catch(console.error);
  });
  
  // Advanced filters binding
  const advancedFiltersPanel = $("advancedFilters");
  const toggleAdvBtn = $("toggleAdvancedFiltersBtn");
  
  if (toggleAdvBtn) {
    toggleAdvBtn.addEventListener("click", () => {
      const isHidden = advancedFiltersPanel.style.display === "none";
      advancedFiltersPanel.style.display = isHidden ? "block" : "none";
      toggleAdvBtn.classList.toggle("active", isHidden);
      toggleAdvBtn.setAttribute("aria-expanded", isHidden);
    });
  }

  const bindFilter = (id, stateKey) => {
    const el = $(id);
    if (el) {
      el.addEventListener("change", (e) => {
        state[stateKey] = e.target.value;
        state.page = 1;
        loadCustomers().catch(console.error);
      });
    }
  };

  bindFilter("dateFromFilter", "dateFrom");
  bindFilter("dateToFilter", "dateTo");
  bindFilter("commPriorityFilter", "commPriority");
  bindFilter("commStatusFilter", "commStatus");
  bindFilter("assignedToFilter", "assignedTo");

  const resetBtn = $("resetFiltersBtn");
  if (resetBtn) {
    resetBtn.addEventListener("click", () => {
      $("dateFromFilter").value = "";
      $("dateToFilter").value = "";
      $("commPriorityFilter").value = "all";
      $("commStatusFilter").value = "all";
      $("assignedToFilter").value = "all";
      
      state.dateFrom = "";
      state.dateTo = "";
      state.commPriority = "all";
      state.commStatus = "all";
      state.assignedTo = "all";
      state.page = 1;
      
      loadCustomers().catch(console.error);
    });
  }
  document.querySelectorAll("th[data-sort]").forEach((th) => {
    th.addEventListener("click", () => {
      const sort = th.dataset.sort;
      state.sortDir = state.sortBy === sort && state.sortDir === "desc" ? "asc" : "desc";
      state.sortBy = sort;
      loadCustomers().catch(console.error);
    });
  });
  $("prevPage").addEventListener("click", () => {
    state.page = Math.max(1, state.page - 1);
    loadCustomers().catch(console.error);
  });
  $("nextPage").addEventListener("click", () => {
    state.page += 1;
    loadCustomers().catch(console.error);
  });
  $("customersBody").addEventListener("click", (event) => {
    const deleteButton = event.target.closest("[data-delete-customer]");
    if (deleteButton) {
      event.stopPropagation();
      deleteCustomer(deleteButton.dataset.deleteCustomer).catch((error) => toast(error.message));
      return;
    }
    const row = event.target.closest("tr[data-customer-id]");
    if (row) openCustomer(row.dataset.customerId);
  });
  $("drawerContent").addEventListener("click", (event) => {
    const printButton = event.target.closest("[data-print-customer]");
    if (printButton) {
      saveCustomerPdf(printButton.dataset.printCustomer).catch((error) => toast(error.message));
      return;
    }
    const deleteButton = event.target.closest("[data-delete-customer]");
    if (deleteButton) {
      deleteCustomer(deleteButton.dataset.deleteCustomer).catch((error) => toast(error.message));
    }
  });
  $("closeDrawer").addEventListener("click", closeDrawer);
  $("drawerBackdrop").addEventListener("click", closeDrawer);
}

// ============================================================================
// CONNECTORS & SMART CSV BATCH UPLOAD ENGINE
// ============================================================================

function capitalize(str) {
  if (!str) return "";
  return str.charAt(0).toUpperCase() + str.slice(1);
}

// Tab switching
function switchCsvTab(tab) {
  document.querySelectorAll('.csv-tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.csv-tab-content').forEach(t => t.style.display = 'none');
  const targetBtn = document.querySelector(`[data-tab="${tab}"]`);
  if (targetBtn) targetBtn.classList.add('active');
  const targetTab = document.getElementById(`tab-${tab}`);
  if (targetTab) targetTab.style.display = 'block';
}

// Store file content per mode
const csvFiles = { ready: null, raw: null };

function handleCsvFile(event, mode) {
  const file = event.target.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = e => { 
    csvFiles[mode] = e.target.result; 
    const dropzone = $(`dropzone-${mode}`);
    if (dropzone) {
      const span = dropzone.querySelector('span');
      if (span) span.textContent = `✓ ${file.name}`;
    }
  };
  reader.readAsText(file);
  toast(`File selected for ${mode} mode`);
}

// Template downloads
function downloadTemplate(mode) {
  const templates = {
    ready: `user_id,avg_plan_price,total_amount_paid,total_transactions,billing_tenure_days,auto_renew_count,total_cancellations
cust_001,199.99,2399.88,12,365,10,1
cust_002,49.99,149.97,3,45,0,2
cust_003,999.99,11999.88,12,540,11,0`,

    raw: `customer_id,transaction_date,amount,plan_name,is_cancellation,is_auto_renew
cust_001,2023-01-15,199.99,Pro,0,1
cust_001,2023-02-15,199.99,Pro,0,1
cust_001,2023-03-15,199.99,Pro,0,0
cust_002,2024-01-10,49.99,Starter,0,1
cust_002,2024-02-10,49.99,Starter,1,0
cust_002,2024-03-01,49.99,Starter,0,0`
  };
  const blob = new Blob([templates[mode]], { type: 'text/csv' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = mode === 'ready' ? 'retention_template_formatted.csv' : 'retention_template_raw.csv';
  a.click();
  toast(`Downloaded template (${mode})`);
}

function showCsvLoading(msg) {
  const status = document.getElementById("csvUploadStatus");
  if (status) status.innerHTML = `<span style="color:var(--brand)">⟳ ${msg}</span>`;
  toast(msg);
}

function showCsvError(err, hint = "") {
  const status = document.getElementById("csvUploadStatus");
  if (status) status.innerHTML = `<span style="color:var(--danger)">✗ ${err}${hint ? `<br><small style="color:var(--warning)">Hint: ${hint}</small>` : ""}</span>`;
  toast("CSV upload error");
}

function showCsvSuccess(msg) {
  const status = document.getElementById("csvUploadStatus");
  if (status) status.innerHTML = `<span style="color:var(--success)">${msg}</span>`;
  toast(msg);
  if (typeof loadCustomers === 'function') loadCustomers();
  Promise.all([loadOverview(), loadRealtime()]).catch(console.error);
}

// Upload and score
async function uploadCsv(mode) {
  const csvText = csvFiles[mode];
  if (!csvText) { alert('يرجى اختيار ملف CSV أولاً.'); return; }

  const loadingMsg = mode === 'raw'
    ? 'جاري هندسة الميزات من العمليات...'
    : 'جاري تقييم العملاء...';
  showCsvLoading(loadingMsg);

  try {
    const res = await fetch('/api/v1/customers/upload-csv', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ csv_text: csvText, mode })
    });

    const data = await res.json();

    if (!res.ok) {
      if (data.error === 'missing_columns') {
        showCsvError(`أعمدة مفقودة: ${data.missing.join(', ')}`, data.hint);
      } else {
        showCsvError(data.detail || 'فشل الرفع');
      }
      return;
    }

    renderCsvResults(data, mode);
    renderBatchOverview(data, `CSV ${capitalize(mode)} Batch Results`);
  } catch (err) {
    showCsvError('Network error: ' + err.message);
  }
}

function renderBatchOverview(data, title = "ملخص تحليل الدفعة") {
  const results = data.results || [];
  if (!results.length) return;

  const total = results.length;
  const avgRisk = results.reduce((acc, c) => acc + c.risk_percentage, 0) / total;
  const highRiskCount = results.filter(c => c.priority === 'HIGH' || c.priority === 'CRITICAL').length;
  const avgTenure = results.reduce((acc, c) => acc + c.billing_tenure_days, 0) / total;

  // Get top 3 riskiest
  const riskiest = [...results].sort((a, b) => b.risk_percentage - a.risk_percentage).slice(0, 3);

  const html = `
    <div class="batch-summary">
      <header class="panel-header" style="margin-bottom: 20px; border-bottom: 1px solid var(--line); padding-bottom: 12px;">
        <div>
          <h2 style="color: var(--brand)">${title}</h2>
          <p>نتائج من أحدث اختبار لك (${total} سجلات)</p>
        </div>
        <span class="badge success">أحدث تشغيل</span>
      </header>

      <div class="kpi-grid" style="grid-template-columns: repeat(2, 1fr); gap: 10px; margin-bottom: 20px;">
        <div class="mini-card" style="padding: 12px;">
          <span style="font-size: 10px; color: var(--muted); text-transform: uppercase;">متوسط درجة المخاطرة</span>
          <strong dir="ltr" style="display: block; margin-top: 4px; font-size: 20px; color: ${avgRisk > 50 ? 'var(--danger)' : 'var(--success)'}">${avgRisk.toFixed(1)}%</strong>
        </div>
        <div class="mini-card" style="padding: 12px;">
          <span style="font-size: 10px; color: var(--muted); text-transform: uppercase;">أصول عالية المخاطر</span>
          <strong dir="ltr" style="display: block; margin-top: 4px; font-size: 20px; color: var(--danger)">${highRiskCount}</strong>
        </div>
        <div class="mini-card" style="padding: 12px;">
          <span style="font-size: 10px; color: var(--muted); text-transform: uppercase;">متوسط مدة الاشتراك</span>
          <strong dir="ltr" style="display: block; margin-top: 4px; font-size: 20px;">${Math.round(avgTenure)} يوم</strong>
        </div>
        <div class="mini-card" style="padding: 12px;">
          <span style="font-size: 10px; color: var(--muted); text-transform: uppercase;">إجمالي السجلات</span>
          <strong dir="ltr" style="display: block; margin-top: 4px; font-size: 20px;">${total}</strong>
        </div>
      </div>

      <h3 style="font-size: 13px; margin-bottom: 12px; color: var(--muted); text-transform: uppercase;">أكثر 3 عملاء عرضة للمخاطر</h3>
      <div class="table-wrap" style="min-width: 0; border-radius: 8px; border-color: rgba(148, 163, 184, 0.1);">
        <table style="min-width: 0;">
          <thead style="background: rgba(148, 163, 184, 0.05);">
            <tr><th style="font-size: 10px; padding: 8px;">المعرف</th><th style="font-size: 10px; padding: 8px;">الخطر</th><th style="font-size: 10px; padding: 8px;">المصدر</th><th style="font-size: 10px; padding: 8px;">إجراء</th></tr>
          </thead>
          <tbody>
            ${riskiest.map(c => `
              <tr>
                <td style="padding: 8px; font-size: 12px;"><strong>${c.customer_id.substring(0, 14)}${c.customer_id.length > 14 ? '..' : ''}</strong></td>
                <td style="padding: 8px;"><span class="badge ${riskClass(c.priority, c.risk_percentage)}" style="font-size: 10px; min-height: 20px; padding: 0 6px;">${c.risk_percentage}%</span></td>
                <td style="padding: 8px;"><small style="font-size: 10px; color: var(--muted);">${c.connector_source || 'CSV'}</small></td>
                <td style="padding: 8px;"><button class="small-button text" onclick="loadIntoForm('${c.customer_id}')" style="font-size: 10px; height: 22px; padding: 0 6px;">تجربة</button></td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      </div>
      
      <div style="margin-top: 16px; text-align: center;">
        <p class="form-note" style="font-size: 11px;">عرض القائمة الكاملة في جدول جميع العملاء.</p>
      </div>
    </div>
  `;

  const insightsPanel = document.getElementById('insightsPanel');
  if (insightsPanel) {
    insightsPanel.innerHTML = html;
    insightsPanel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }
}

function renderCsvResults(data, mode) {
  const count = data.customers_scored || data.results?.length || 0;
  const engineered = mode === 'raw' ? ` (engineered from ${data.rows_received} rows)` : '';
  showCsvSuccess(`✓ ${count} customers scored${engineered}`);
  if (typeof loadCustomers === 'function') loadCustomers();
}

// Connectors sync panel handlers
async function loadConnectorStatus() {
  try {
    const res = await fetch('/api/v1/connectors/status');
    const data = await res.json();
    renderConnectorPanel(data.connectors);
  } catch (err) {
    console.error("Failed to load connector statuses", err);
  }
}

function renderConnectorPanel(connectors) {
  const panel = document.getElementById('connector-panel');
  if (!panel) return;
  const icons = { hubspot: '🟠', salesforce: '🔵', mixpanel: '🟣', stripe: '💳' };
  panel.innerHTML = Object.entries(connectors).map(([name, info]) => `
    <div class="connector-row">
      <div class="connector-info" style="display: flex; flex-direction: column; gap: 4px;">
        <span class="connector-name">${icons[name] || '🔌'} ${capitalize(name)}</span>
        <span class="connector-badge ${info.mode === 'live' ? 'badge-live' : 'badge-mock'}">
          ${info.mode === 'live' ? '● مباشر' : '● وهمي'}
        </span>
      </div>
      <div class="connector-actions" style="display: flex; gap: 8px;">
        <button class="small-button text" onclick="testConnector('${name}')" title="اختبار الاتصال" type="button">اختبار</button>
        <button class="small-button text" onclick="tryFirstRecord('${name}')" title="تجربة سجل حقيقي" type="button" style="color: var(--brand);">تجربة</button>
        <button class="small-button text" onclick="syncConnector('${name}')" type="button">مزامنة ←</button>
      </div>
    </div>
  `).join('') + `
    <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 12px; padding-top: 12px; border-top: 1px dashed var(--line);">
      <button class="primary-button" onclick="syncAllConnectors()" type="button" style="padding: 0 16px; min-height: 40px; flex: 1;">⟳ مزامنة جميع المصادر</button>
      <span id="sync-last-time" class="form-note" style="margin-right: 12px;"></span>
    </div>
  `;
}

async function testConnector(source) {
  toast(`جاري اختبار اتصال ${source}...`);
  try {
    // Call sync with limit=1 and score=false to just test the pipe
    const res = await fetch(`/api/v1/connectors/${source}/sync?limit=1&score=false`, { method: 'POST' });
    const data = await res.json();
    if (res.ok) {
      toast(`✓ ${capitalize(source)} في وضع ${data.mode}. تم العثور على ${data.total_fetched} سجل.`);
    } else {
      toast(`✗ فشل اختبار ${capitalize(source)}: ${data.detail || 'خطأ في الاتصال'}`);
    }
  } catch (err) {
    toast(`خطأ في الشبكة عند اختبار ${source}`);
  }
}

async function loadIntoForm(customerId) {
  $("user_id").value = customerId;
  setView('analysis');
  await fetchFromCrm();
}

async function tryFirstRecord(source) {
  toast(`جاري البحث عن سجل في ${source}...`);
  try {
    const res = await fetch(`/api/v1/connectors/${source}/sync?limit=1&score=false`, { method: 'POST' });
    const data = await res.json();
    if (res.ok && data.results && data.results.length > 0) {
      const firstId = data.results[0].customer_id;
      await loadIntoForm(firstId);
    } else {
      toast(`لم يتم العثور على سجلات في ${source}`);
    }
  } catch (err) {
    toast(`خطأ في تجربة ${source}`);
  }
}

async function syncConnector(source) {
  toast(`جاري مزامنة ${source}...`);
  try {
    const res = await fetch(`/api/v1/connectors/${source}/sync?limit=50&score=true`, { method: 'POST' });
    const data = await res.json();
    toast(`✓ تم تحميل ${data.scored_count} عميل من ${source} (${data.mode})`);
    if (typeof loadCustomers === 'function') loadCustomers();
    renderBatchOverview(data, `ملخص مزامنة ${capitalize(source)}`);
    Promise.all([loadOverview(), loadRealtime()]).catch(console.error);
  } catch (err) {
    toast(`فشل المزامنة لـ ${source}`);
  }
}

async function syncAllConnectors() {
  toast('جاري مزامنة جميع المصادر...');
  try {
    const res = await fetch('/api/v1/connectors/sync-all?limit_per_source=25&score=true', { method: 'POST' });
    const data = await res.json();
    const lastTime = document.getElementById('sync-last-time');
    if (lastTime) lastTime.textContent = `آخر مزامنة: الآن`;
    toast(`✓ تم تحميل ${data.scored_count} عميل من ${data.total_synced} سجل`);
    if (typeof loadCustomers === 'function') loadCustomers();
    renderBatchOverview(data, `ملخص المزامنة الشاملة`);
    Promise.all([loadOverview(), loadRealtime()]).catch(console.error);
  } catch (err) {
    toast('فشل المزامنة الشاملة');
  }
}

async function fetchFromCrm() {
  const cid = $("user_id").value.trim();
  if (!cid) {
    toast("أدخل معرف العميل للبحث");
    return;
  }
  toast(`جاري البحث عن ${cid}...`);
  try {
    const data = await api(`/api/v1/connectors/lookup/${encodeURIComponent(cid)}`);
    $("avg_plan_price").value = data.avg_plan_price;
    $("total_amount_paid").value = data.total_amount_paid;
    $("total_transactions").value = data.total_transactions;
    $("billing_tenure_days").value = data.billing_tenure_days;
    $("auto_renew_count").value = data.auto_renew_count;
    $("total_cancellations").value = data.total_cancellations;
    toast(`✓ تم تحميل البيانات لـ ${cid} من ${data._connector_source}`);
  } catch (err) {
    toast(`فشل البحث: ${err.message}`);
  }
}

async function init() {
  document.documentElement.dataset.theme = localStorage.getItem("retention-theme") || "dark";
  bindEvents();
  setView((location.hash || "#overview").slice(1));
  runIcons();
  loadConnectorStatus();
  try {
    await Promise.all([loadOverview(), loadCustomers()]);
    await loadRealtime();
  } catch (error) {
    toast(error.message);
    console.error(error);
  }
}

init();

