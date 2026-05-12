const API_BASE = window.location.port === "8000" ? window.location.origin : "http://127.0.0.1:8000";
const state = {
  page: 1,
  pageSize: 25,
  sortBy: "risk",
  sortDir: "desc",
  search: "",
  risk: "all",
  vip: "all",
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
  return englishItems.map((item, index) => `
    <li class="bilingual-item">
      <span class="english">${escapeHtml(item)}</span>
      <span class="arabic" dir="rtl">${escapeHtml(arabicItems[index] || "")}</span>
    </li>
  `).join("");
}

function renderBilingualTimeline(englishItems = [], arabicItems = []) {
  return englishItems.map((item, index) => {
    const arabic = arabicItems[index] || {};
    return `
      <div class="timeline-item bilingual-timeline">
        <div>
          <strong>${escapeHtml(item.step)}</strong>
          <span>${escapeHtml(item.owner)} | Deadline: ${escapeHtml(item.deadline)}</span>
        </div>
        <div class="arabic timeline-ar" dir="rtl">
          <strong>${escapeHtml(arabic.step || "")}</strong>
          <span>${escapeHtml(arabic.owner || "")} | الموعد النهائي: ${escapeHtml(arabic.deadline || "")}</span>
        </div>
      </div>
    `;
  }).join("");
}

function renderBilingualValue(english, arabic) {
  return `
    <strong>${escapeHtml(english)}</strong>
    <strong class="arabic mini-ar" dir="rtl">${escapeHtml(arabic || "")}</strong>
  `;
}

function renderFeatureEffects(effects = []) {
  if (!effects.length) return `<div class="table-loading">No feature contribution data available yet.</div>`;
  return `
    <div class="feature-list">
      ${effects.map((effect) => {
        const increases = effect.direction === "increases_churn";
        return `
          <article class="feature-effect">
            <header>
              <div>
                <strong>${escapeHtml(effect.label)}</strong>
                <span class="arabic" dir="rtl">${escapeHtml(effect.label_ar || "")}</span>
              </div>
              ${renderBadge(increases ? "Increases churn" : "Reduces churn", increases ? "danger" : "success")}
            </header>
            <div class="impact-meter ${increases ? "increases" : "reduces"}" style="--value:${Math.max(4, effect.relative_strength || 0)}%"><span></span></div>
            <p>Value: <strong>${escapeHtml(effect.value)}</strong> | SHAP impact: <strong>${escapeHtml(effect.impact)}</strong></p>
            <p>${escapeHtml(effect.explanation)}</p>
            <p class="arabic" dir="rtl">${escapeHtml(effect.explanation_ar || "")}</p>
          </article>
        `;
      }).join("")}
    </div>
  `;
}

function renderNbaRecommendation(nba = {}) {
  const offers = nba.ranked_offers || [];
  if (!offers.length) return `<div class="table-loading">No NBA offer ranking available yet.</div>`;
  return `
    <div class="offer-list">
      <p>${escapeHtml(nba.architecture || "Candidate Generation -> Scoring -> Final Recommendation")}</p>
      <p>${escapeHtml(nba.ranking_reason || "")}</p>
      <p class="arabic" dir="rtl">${escapeHtml(nba.ranking_reason_ar || "")}</p>
      ${offers.map((offer, index) => `
        <article class="offer-card">
          <header>
            <div class="offer-rank">#${index + 1}</div>
            <div>
              <strong>${escapeHtml(offer.title)}</strong>
              <span class="arabic" dir="rtl">${escapeHtml(offer.title_ar || "")}</span>
            </div>
            ${index === 0 ? renderBadge("Selected NBA", "success") : renderBadge(`Score ${offer.net_value_score}`, "")}
          </header>
          <p>${escapeHtml(offer.action)}</p>
          <p class="arabic" dir="rtl">${escapeHtml(offer.action_ar || "")}</p>
          <p>Effectiveness: <strong>${escapeHtml(offer.effectiveness_score)}</strong> | Cost: <strong>${money.format(Number(offer.estimated_cost || 0))}</strong></p>
        </article>
      `).join("")}
    </div>
  `;
}

function renderLlamaReport(report = {}) {
  const english = report.english || {};
  const arabic = report.arabic || {};
  const sections = [
    ["Churn Risk Summary", "churn_risk_summary"],
    ["Behavioral Diagnosis", "behavioral_diagnosis"],
    ["Root Causes Ranked", "root_causes_ranked"],
    ["Recommended Rescue Strategy", "recommended_rescue_strategy"],
    ["Empathy Guidance", "empathy_guidance"],
    ["Suggested Agent Script", "suggested_agent_script"],
    ["Executive Takeaway", "executive_takeaway"],
    ["Retention Priority Analysis", "retention_priority_analysis"],
    ["Behavioral Trend Interpretation", "behavioral_trend_interpretation"],
    ["Business Risk Framing", "business_risk_framing"],
    ["Intervention Confidence", "intervention_confidence"],
    ["Communication Strategy", "communication_strategy"],
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
            <h4>${escapeHtml(title)}</h4>
            <p class="arabic" dir="rtl">${escapeHtml(arValue || "")}</p>
            <p>${escapeHtml(enValue || "")}</p>
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
    ["Total Customers", fmt.format(overview.total_customers), "Saved tested/uploaded customers", ""],
    ["Low Risk", fmt.format(overview.low_risk_users), "Risk below 40%", "success"],
    ["Medium Risk", fmt.format(overview.medium_risk_users), "Risk from 40% to 63.99%", "warning"],
    ["High Risk", fmt.format(overview.high_risk_band_users), "Risk from 64% to 84.99%", "critical"],
    ["Critical Risk", fmt.format(overview.critical_risk_users), "Risk at 85% or higher", "critical"],
    ["Revenue at Risk", money.format(overview.revenue_at_risk), "Projected exposed revenue", "critical"],
    ["VIP Customers", fmt.format(overview.vip_customers), "Premium monitored accounts", ""],
    ["Average Churn", `${overview.average_churn}%`, "Blended risk score", ""],
    ["AI Interventions", fmt.format(overview.ai_interventions_triggered), "Triggered workflows", ""],
    ["Retention Success", `${overview.retention_success_rate}%`, "Modeled retention health", "success"],
  ];
  $("kpiGrid").innerHTML = cards.map(([label, value, hint, tone]) => `
    <article class="kpi-card ${tone}">
      <span>${label}</span>
      <strong>${value}</strong>
      <small>${hint}</small>
    </article>
  `).join("");
  $("modelStatus").textContent = overview.model_status === "online" ? "Model online" : "Model offline";
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
        { label: "Retention", data: analytics.monthly_retention_trends.map((item) => item.retention), borderColor: c.green, backgroundColor: "rgba(52, 211, 153, 0.12)", fill: true, tension: 0.35 },
        { label: "Risk", data: analytics.monthly_retention_trends.map((item) => item.risk), borderColor: c.red, backgroundColor: "rgba(251, 113, 133, 0.08)", tension: 0.35 },
      ],
    },
  });
  createChart("revenueChart", {
    type: "bar",
    data: {
      labels: Object.keys(analytics.revenue_impact),
      datasets: [{ label: "Revenue", data: Object.values(analytics.revenue_impact), backgroundColor: [c.green, c.yellow, c.red], borderRadius: 8 }],
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
        { label: "Customers", data: analytics.customer_segmentation.map((item) => item.count), backgroundColor: c.blue, borderRadius: 8 },
        { label: "Avg risk", data: analytics.customer_segmentation.map((item) => item.avg_risk), backgroundColor: c.red, borderRadius: 8 },
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
    $("riskHeatmap").innerHTML = `<div class="table-loading">No segment data yet.</div>`;
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
  });
  return `/api/v1/customers?${params.toString()}`;
}

async function loadCustomers() {
  $("customersBody").innerHTML = `<tr><td colspan="11"><div class="table-loading">Loading customers...</div></td></tr>`;
  const data = await api(customerQuery());
  if (!data.items.length) {
    $("customersBody").innerHTML = `
      <tr><td colspan="11"><div class="table-loading">No saved customers yet. Analyze one customer or upload a CSV file to populate this dashboard.</div></td></tr>
    `;
    $("paginationText").textContent = `Page ${data.page} of ${data.pages} | ${fmt.format(data.total)} customers`;
    $("prevPage").disabled = true;
    $("nextPage").disabled = true;
    return;
  }
  $("customersBody").innerHTML = data.items.map((row) => {
    const tone = riskClass(row.priority, row.risk);
    return `
      <tr class="${tone === "critical" ? "row-critical" : ""}" data-customer-id="${escapeHtml(row.customer_id)}">
        <td><strong>${escapeHtml(row.customer_id)}</strong></td>
        <td>${row.risk.toFixed(2)}<div class="risk-bar ${tone}" style="--value:${row.risk}%"><span></span></div></td>
        <td>${renderBadge(row.vip_status, row.vip_status === "VIP" ? "success" : "")}</td>
        <td>${money.format(row.revenue)}</td>
        <td>${fmt.format(row.tenure)}d</td>
        <td>${(row.cancel_rate * 100).toFixed(1)}%</td>
        <td>${escapeHtml(row.retention_status)}</td>
        <td>${escapeHtml(row.ai_decision.replaceAll("_", " "))}</td>
        <td>${renderBadge(`${row.priority} ${row.priority_score}`, tone === "critical" ? "danger" : tone === "high" ? "warning" : "")}</td>
        <td>${new Date(row.last_activity).toLocaleDateString()}</td>
        <td><button class="small-button danger-action" type="button" data-delete-customer="${escapeHtml(row.customer_id)}" aria-label="Delete ${escapeHtml(row.customer_id)}"><i data-lucide="trash-2"></i></button></td>
      </tr>
    `;
  }).join("");
  $("paginationText").textContent = `Page ${data.page} of ${data.pages} | ${fmt.format(data.total)} customers`;
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
        <p class="eyebrow">Structured LLM Result</p>
        <h2>Executive Summary</h2>
        <p>${escapeHtml(analysis.summary)}</p>
        ${renderBadge(analysis.risk_level, tone === "critical" ? "danger" : tone === "high" ? "warning" : "success")}
      </div>
      <div class="score-ring" style="--score:${Number(meta.risk || analysis.priority_score)};--risk-color:${riskColor}">
        <div><strong>${Number(meta.risk || analysis.priority_score).toFixed(0)}%</strong><span>risk score</span></div>
      </div>
    </div>

    <div class="insight-grid">
      <div class="mini-card"><span>Priority Score</span><strong>${analysis.priority_score}</strong></div>
      <div class="mini-card"><span>AI Confidence</span><strong>${analysis.ai_confidence_score}%</strong></div>
      <div class="mini-card"><span>Sentiment</span><strong>${escapeHtml(analysis.customer_sentiment)}</strong></div>
      <div class="mini-card"><span>Human Intervention</span><strong>${analysis.human_intervention_required ? "Required" : "Not required"}</strong></div>
      <div class="mini-card"><span>Next Best Action</span>${renderBilingualValue(analysis.next_best_action, analysis.next_best_action_ar)}</div>
      <div class="mini-card"><span>Personalized Offer</span>${renderBilingualValue(analysis.personalized_offer, analysis.personalized_offer_ar)}</div>
    </div>

    <details class="collapsible" open>
      <summary>Root Causes | الأسباب الرئيسية</summary>
      <div class="collapsible-content"><ul class="bullet-list">${renderBilingualList(analysis.main_reasons, analysis.main_reasons_ar)}</ul></div>
    </details>
    <details class="collapsible" open>
      <summary>AI Recommendations | توصيات الذكاء الاصطناعي</summary>
      <div class="collapsible-content"><ul class="bullet-list">${renderBilingualList(analysis.recommended_actions, analysis.recommended_actions_ar)}</ul></div>
    </details>
    <details class="collapsible" open>
      <summary>Retention Strategy | استراتيجية الاحتفاظ</summary>
      <div class="collapsible-content">
        <p>${escapeHtml(analysis.retention_strategy)}</p>
        <p class="arabic strategy-ar" dir="rtl">${escapeHtml(analysis.retention_strategy_ar || "")}</p>
      </div>
    </details>
    <details class="collapsible" open>
      <summary>Action Timeline | الجدول الزمني للإجراءات</summary>
      <div class="collapsible-content timeline">
        ${renderBilingualTimeline(analysis.timeline, analysis.timeline_ar)}
      </div>
    </details>
    <details class="collapsible" open>
      <summary>Feature Effects | XGBoost SHAP</summary>
      <div class="collapsible-content">${renderFeatureEffects(analysis.feature_effects)}</div>
    </details>
    <details class="collapsible" open>
      <summary>Next Best Action Ranking | NBA</summary>
      <div class="collapsible-content">${renderNbaRecommendation(analysis.nba_recommendation)}</div>
    </details>
    <details class="collapsible" open>
      <summary>LLaMA Strategy Report | Groq</summary>
      <div class="collapsible-content">${renderLlamaReport(analysis.llama_report)}</div>
    </details>
  `;
}

function readPredictionPayload() {
  return {
    user_id: $("user_id").value.trim(),
    avg_plan_price: Number($("avg_plan_price").value),
    total_amount_paid: Number($("total_amount_paid").value),
    total_transactions: Number($("total_transactions").value),
    billing_tenure_days: Number($("billing_tenure_days").value),
    auto_renew_count: Number($("auto_renew_count").value),
    total_cancellations: Number($("total_cancellations").value),
    cancel_rate: Number($("cancel_rate").value),
  };
}

async function analyzeCustomer(event) {
  event.preventDefault();
  const button = $("analyzeBtn");
  button.disabled = true;
  button.querySelector("span").textContent = "Analyzing...";
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
          <span>Run Advanced AI Analysis (SHAP + LLaMA)</span>
        </button>
        <p style="margin:8px 0 0;font-size:12px;color:var(--muted);">Runs real SHAP explainability + Groq LLaMA deep reasoning</p>
      </div>
    `;
    runIcons();
    const advBtn = $("advancedAnalysisBtn");
    if (advBtn) {
      advBtn.addEventListener("click", () => runAdvancedAnalysis(readPredictionPayload()));
    }
    await Promise.all([loadOverview(), loadCustomers(), loadRealtime()]);
    toast(`Structured analysis ready for ${result.customer_id}`);
  } catch (error) {
    $("insightsPanel").innerHTML = `<div class="empty-state"><h2>Analysis failed</h2><p>${escapeHtml(error.message)}</p></div>`;
  } finally {
    button.disabled = false;
    button.querySelector("span").textContent = "Analyze Customer";
    runIcons();
  }
}

async function runAdvancedAnalysis(payload) {
  const advBtn = $("advancedAnalysisBtn");
  if (advBtn) {
    advBtn.disabled = true;
    advBtn.querySelector("span").textContent = "Running SHAP + LLaMA...";
  }
  try {
    const result = await api("/api/v1/analyze-risk-detailed", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    $("insightsPanel").innerHTML = `
      <div style="display:flex;gap:8px;margin-bottom:12px;flex-wrap:wrap;">
        ${renderBadge("SHAP: " + (result.shap_available ? "Active" : "Fallback"), result.shap_available ? "success" : "warning")}
        ${renderBadge("LLM: " + (result.llm_source || "unknown"), result.llm_source === "groq_llama" ? "success" : "warning")}
      </div>
    ` + renderInsights(result.llm_analysis, {
      risk: result.churn_risk_percentage,
      priority: result.priority,
    });
    await Promise.all([loadOverview(), loadCustomers(), loadRealtime()]);
    toast(`Advanced AI analysis complete for ${result.customer_id}`);
  } catch (error) {
    toast("Advanced analysis failed: " + error.message);
    if (advBtn) {
      advBtn.disabled = false;
      advBtn.querySelector("span").textContent = "Run Advanced AI Analysis (SHAP + LLaMA)";
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
    toast("Choose a CSV file first");
    return;
  }
  const button = $("uploadCsvBtn");
  button.disabled = true;
  button.querySelector("span").textContent = "Analyzing CSV...";
  $("csvUploadStatus").textContent = "Reading and scoring CSV rows...";
  try {
    const csvText = await readCsvFile(file);
    const result = await api("/api/v1/customers/upload-csv", {
      method: "POST",
      body: JSON.stringify({ csv_text: csvText }),
    });
    $("csvUploadStatus").textContent = `Imported ${result.imported} customers. ${result.errors.length ? `${result.errors.length} rows skipped.` : "No row errors."}`;
    await Promise.all([loadOverview(), loadCustomers(), loadRealtime()]);
    toast(`CSV analysis complete: ${result.imported} customers saved`);
  } catch (error) {
    $("csvUploadStatus").textContent = error.message;
    toast("CSV upload failed");
  } finally {
    button.disabled = false;
    button.querySelector("span").textContent = "Analyze CSV";
    runIcons();
  }
}

async function deleteCustomer(customerId) {
  if (!confirm(`Remove ${customerId} from saved dashboard data?`)) return;
  await api(`/api/v1/customer/${encodeURIComponent(customerId)}`, { method: "DELETE" });
  closeDrawer();
  await Promise.all([loadOverview(), loadCustomers(), loadRealtime()]);
  toast(`${customerId} removed`);
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
          <div><h2>Profile Analytics</h2><p>Saved data for this analyzed customer.</p></div>
          <div class="report-actions">
            <button class="small-button" type="button" data-print-customer="${escapeHtml(customer.customer_id)}" aria-label="Save ${escapeHtml(customer.customer_id)} PDF"><i data-lucide="file-down"></i></button>
            <button class="small-button danger-action" type="button" data-delete-customer="${escapeHtml(customer.customer_id)}" aria-label="Delete ${escapeHtml(customer.customer_id)}"><i data-lucide="trash-2"></i></button>
          </div>
        </div>
        <div class="insight-grid">
          <div class="mini-card"><span>Revenue</span><strong>${money.format(customer.revenue)}</strong></div>
          <div class="mini-card"><span>Tenure</span><strong>${fmt.format(customer.tenure)}d</strong></div>
          <div class="mini-card"><span>Cancel Rate</span><strong>${(customer.cancel_rate * 100).toFixed(1)}%</strong></div>
          <div class="mini-card"><span>Segment</span><strong>${escapeHtml(customer.segment)}</strong></div>
          <div class="mini-card"><span>AI Decision</span><strong>${escapeHtml(customer.ai_decision.replaceAll("_", " "))}</strong></div>
          <div class="mini-card"><span>Status</span><strong>${escapeHtml(customer.retention_status)}</strong></div>
        </div>
        <div class="chart-wrap"><canvas id="detailTrendChart"></canvas></div>
      </section>
      <section class="panel">${renderInsights(customer.llm_analysis, { risk: customer.risk, priority: customer.priority })}</section>
      <section class="panel">
        <div class="panel-header"><div><h2>Action History</h2><p>Recent workflow and model events.</p></div></div>
        <div class="timeline">
          ${customer.action_history.map((item) => `
            <div class="timeline-item"><strong>${escapeHtml(item.event)}</strong><span>${escapeHtml(item.owner)} | ${new Date(item.timestamp).toLocaleString()}</span></div>
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
    $("drawerContent").innerHTML = `<div class="empty-state"><h2>Unable to load customer</h2><p>${escapeHtml(error.message)}</p></div>`;
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
    <html>
    <head>
      <meta charset="utf-8" />
      <title>${escapeHtml(title)}</title>
      <style>
        body { font-family: Arial, sans-serif; margin: 32px; color: #111827; line-height: 1.5; }
        h1 { margin: 0 0 8px; font-size: 28px; }
        h2 { margin-top: 24px; border-bottom: 1px solid #d1d5db; padding-bottom: 6px; }
        h3 { margin-bottom: 6px; }
        .meta { color: #64748b; margin-bottom: 24px; }
        .grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
        .card, .section { border: 1px solid #d1d5db; border-radius: 8px; padding: 12px; margin: 10px 0; }
        .badge { display: inline-block; padding: 4px 8px; border-radius: 999px; background: #e0f2fe; color: #075985; font-weight: 700; }
        .arabic { direction: rtl; text-align: right; font-family: Arial, sans-serif; }
        table { width: 100%; border-collapse: collapse; margin-top: 12px; }
        th, td { border: 1px solid #d1d5db; padding: 8px; text-align: left; }
        th { background: #f8fafc; }
        @media print { button { display: none; } body { margin: 18mm; } }
      </style>
    </head>
    <body>
      <button onclick="window.print()">Save as PDF</button>
      <h1>${escapeHtml(title)}</h1>
      <div class="meta">Generated ${new Date().toLocaleString()} from Retention AI Command Center</div>
      ${body}
      <script>setTimeout(() => window.print(), 350);</script>
    </body>
    </html>
  `;
}

function openPrintWindow(title, body) {
  const win = window.open("", "_blank");
  if (!win) {
    toast("Allow popups to save PDF reports");
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
      <div class="card"><strong>Total Customers</strong><br>${fmt.format(overview.total_customers)}</div>
      <div class="card"><strong>Low Risk</strong><br>${fmt.format(overview.low_risk_users)}</div>
      <div class="card"><strong>Medium Risk</strong><br>${fmt.format(overview.medium_risk_users)}</div>
      <div class="card"><strong>High Risk</strong><br>${fmt.format(overview.high_risk_band_users)}</div>
      <div class="card"><strong>Critical Risk</strong><br>${fmt.format(overview.critical_risk_users)}</div>
      <div class="card"><strong>Revenue at Risk</strong><br>${money.format(overview.revenue_at_risk)}</div>
    </section>
    <h2>Risk Distribution</h2>
    <table><tbody>${Object.entries(analytics.churn_distribution).map(([key, value]) => `<tr><th>${escapeHtml(key)}</th><td>${fmt.format(value)}</td></tr>`).join("")}</tbody></table>
    <h2>Top Risk Customers</h2>
    <table>
      <thead><tr><th>Customer</th><th>Risk</th><th>Priority</th><th>Decision</th><th>Revenue</th></tr></thead>
      <tbody>${customers.items.map((row) => `<tr><td>${escapeHtml(row.customer_id)}</td><td>${row.risk}%</td><td>${escapeHtml(row.priority)}</td><td>${escapeHtml(row.ai_decision)}</td><td>${money.format(row.revenue)}</td></tr>`).join("")}</tbody>
    </table>
    <h2>Executive Notes</h2>
    <p>This overview is based only on customers saved through manual analysis or CSV upload.</p>
  `;
  openPrintWindow("AI Risk Operations Overview Report", body);
}

async function saveCustomerPdf(customerId) {
  const customer = await api(`/api/v1/customer/${encodeURIComponent(customerId)}`);
  const analysis = customer.llm_analysis || {};
  const report = analysis.llama_report || {};
  const en = report.english || {};
  const ar = report.arabic || {};
  const body = `
    <section class="grid">
      <div class="card"><strong>Risk</strong><br>${customer.risk}%</div>
      <div class="card"><strong>Priority</strong><br>${escapeHtml(customer.priority)}</div>
      <div class="card"><strong>Revenue</strong><br>${money.format(customer.revenue)}</div>
      <div class="card"><strong>VIP</strong><br>${escapeHtml(customer.vip_status)}</div>
      <div class="card"><strong>Cancel Rate</strong><br>${(customer.cancel_rate * 100).toFixed(1)}%</div>
      <div class="card"><strong>AI Decision</strong><br>${escapeHtml(customer.ai_decision)}</div>
    </section>
    <h2>Next Best Action</h2>
    <div class="section">
      <p>${escapeHtml(analysis.next_best_action)}</p>
      <p class="arabic">${escapeHtml(analysis.next_best_action_ar || "")}</p>
    </div>
    <h2>Feature Effects</h2>
    ${renderFeatureEffects(analysis.feature_effects || customer.feature_effects || [])}
    <h2>NBA Offer Ranking</h2>
    ${renderNbaRecommendation(analysis.nba_recommendation || customer.nba_recommendation || {})}
    <h2>LLaMA Retention Report</h2>
    <div class="section"><h3>Arabic</h3><p class="arabic">${escapeHtml(ar.churn_risk_summary || "")}</p><p class="arabic">${escapeHtml(ar.behavioral_diagnosis || "")}</p></div>
    <div class="section"><h3>English</h3><p>${escapeHtml(en.churn_risk_summary || "")}</p><p>${escapeHtml(en.behavioral_diagnosis || "")}</p></div>
    <h2>Timeline</h2>
    <table><tbody>${(analysis.timeline || []).map((item) => `<tr><td>${escapeHtml(item.step)}</td><td>${escapeHtml(item.owner)}</td><td>${escapeHtml(item.deadline)}</td></tr>`).join("")}</tbody></table>
  `;
  openPrintWindow(`Customer Retention Report - ${customer.customer_id}`, body);
}

function renderRealtimeOverview(overview) {
  $("alertList").innerHTML = overview.alerts.length ? overview.alerts.map((alert) => `
    <div class="alert-item">
      <strong>${escapeHtml(alert.customer_id)} | ${alert.risk.toFixed(2)}%</strong>
      <span>${escapeHtml(alert.message)}</span>
    </div>
  `).join("") : `<div class="alert-item"><strong>No saved high-risk customers</strong><span>Analyze customers or upload a CSV to populate alerts.</span></div>`;
  $("activityFeed").innerHTML = overview.activity_feed.length ? overview.activity_feed.map((item) => `
    <div class="activity-item">
      <strong>${escapeHtml(item.message)}</strong>
      <span>${new Date(item.timestamp).toLocaleString()}</span>
    </div>
  `).join("") : `<div class="activity-item"><strong>No activity yet</strong><span>Saved analyses will appear here.</span></div>`;
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
    toast("Dashboard refreshed");
  });
  $("overviewPdfBtn").addEventListener("click", () => {
    saveOverviewPdf().catch((error) => toast(error.message));
  });

  $("predictionForm").addEventListener("submit", analyzeCustomer);
  $("uploadCsvBtn").addEventListener("click", uploadCsvCustomers);
  $("csvFileInput").addEventListener("change", (event) => {
    const file = event.target.files[0];
    $("csvFileLabel").textContent = file ? file.name : "Choose CSV file";
  });
  $("fillExampleBtn").addEventListener("click", () => {
    $("user_id").value = "VIP-USER-777";
    $("avg_plan_price").value = 1200;
    $("total_amount_paid").value = 8600;
    $("total_transactions").value = 8;
    $("billing_tenure_days").value = 95;
    $("auto_renew_count").value = 0;
    $("total_cancellations").value = 3;
    $("cancel_rate").value = 0.42;
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

async function init() {
  document.documentElement.dataset.theme = localStorage.getItem("retention-theme") || "dark";
  bindEvents();
  setView((location.hash || "#overview").slice(1));
  runIcons();
  try {
    await Promise.all([loadOverview(), loadCustomers()]);
    await loadRealtime();
  } catch (error) {
    toast(error.message);
    console.error(error);
  }
}

init();
