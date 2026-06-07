let DASHBOARD = {};
let MRR = [];
let PLANS = [];
let CHURN = [];
let REGIONS = [];
let SEGMENTS = [];
let RISK = [];
let COHORT = { headers: [], rows: [] };

let mrrChart;
let planChart;
let regionChart;
let churnChart;
let segChart;

const BORDER = "#d7cfbf";
const MUTED = "#6f716b";
const TEXT = "#22262b";
const PAL = ["#253f5c", "#3e6655", "#947637", "#916140", "#5a6570", "#3b6d70"];

if (window.Chart) {
  Chart.defaults.font.family = "Arial, Helvetica, sans-serif";
  Chart.defaults.font.size = 11;
  Chart.defaults.color = MUTED;
  Chart.defaults.borderColor = BORDER;
  Chart.defaults.plugins.tooltip.titleFont = {
    family: "Georgia, 'Times New Roman', serif",
    size: 13,
    weight: "bold"
  };
  Chart.defaults.plugins.tooltip.bodyFont = {
    family: "Arial, Helvetica, sans-serif",
    size: 12
  };
}

function fmt$(value) {
  const n = Number(value || 0);
  if (n >= 1e6) return "$" + (n / 1e6).toFixed(2) + "M";
  if (n >= 1e3) return "$" + (n / 1e3).toFixed(1) + "K";
  return "$" + n.toFixed(0);
}

function fmtNumber(value) {
  return Number(value || 0).toLocaleString();
}

function pct(value) {
  return `${Number(value || 0).toFixed(1)}%`;
}

function setText(id, value) {
  const el = document.getElementById(id);
  if (el) el.textContent = value;
}

function clean(value) {
  const n = Number(value);
  return Number.isFinite(n) ? n : 0;
}

async function loadDashboardData() {
  const response = await fetch("../analytics_summary.json", { cache: "no-store" });
  if (!response.ok) throw new Error(`Could not load analytics_summary.json (${response.status})`);

  const text = await response.text();
  const data = JSON.parse(text.replace(/\bNaN\b/g, "null"));

  DASHBOARD = data || {};
  MRR = Array.isArray(data.mrr_by_month) ? data.mrr_by_month : [];
  PLANS = Array.isArray(data.plan_performance) ? data.plan_performance : [];
  CHURN = Array.isArray(data.churn_by_plan) ? data.churn_by_plan : [];
  REGIONS = Array.isArray(data.region_performance) ? data.region_performance : [];
  SEGMENTS = Array.isArray(data.customer_segments) ? data.customer_segments : [];
  RISK = Array.isArray(data.high_risk_customers) ? data.high_risk_customers : [];
  COHORT = data.cohort || { headers: [], rows: [] };

  initDashboard();
}

function initDashboard() {
  renderSummary();
  renderKpis();
  buildMrrChart();
  buildPlanChart();
  buildRegionChart();
  buildChurnChart();
  buildSegChart();
  buildRegionTable();
  buildSegmentList();
  buildRiskTable();
  buildCohortTable();
  renderInsights();
}

function renderSummary() {
  const k = DASHBOARD.kpis || {};
  const topPlan = [...PLANS].sort((a, b) => clean(b.mrr) - clean(a.mrr))[0];
  const topRegion = [...REGIONS].sort((a, b) => clean(b.revenue) - clean(a.revenue))[0];

  setText(
    "executiveSummary",
    `The SaaS business reached ${fmt$(k.current_mrr)} in current MRR and ${fmt$(k.arr)} in ARR. ${topPlan?.plan_name || "The top plan"} contributes the strongest plan revenue, while ${topRegion?.region || "the top region"} is the highest-revenue region. Customer churn is ${pct(k.customer_churn_rate)}, with ${fmtNumber(k.high_risk_customers)} active customers marked as higher risk.`
  );
}

function renderKpis() {
  const k = DASHBOARD.kpis || {};

  setText("kpiMrr", fmt$(k.current_mrr));
  setText("kpiArr", fmt$(k.arr));
  setText("kpiChurn", pct(k.customer_churn_rate));
  setText("kpiArpu", fmt$(k.arpu));
  setText("kpiRevenue", fmt$(k.total_revenue));
  setText("kpiActive", fmtNumber(k.active_customers));
  setText("kpiRisk", fmtNumber(k.high_risk_customers));
}

function axisMoney() {
  return {
    grid: { color: BORDER },
    ticks: { color: MUTED, callback: value => fmt$(value) }
  };
}

function buildMrrChart() {
  const canvas = document.getElementById("mrrChart");
  if (!canvas || !window.Chart) return;

  mrrChart = new Chart(canvas.getContext("2d"), {
    type: "line",
    data: {
      labels: MRR.map(row => row.month),
      datasets: [{
        label: "MRR",
        data: MRR.map(row => clean(row.mrr)),
        borderColor: PAL[0],
        backgroundColor: PAL[0] + "18",
        fill: true,
        tension: .3,
        borderWidth: 2,
        pointRadius: 1.5
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: { label: ctx => fmt$(ctx.raw) } }
      },
      scales: {
        x: { grid: { color: BORDER }, ticks: { color: MUTED, maxRotation: 45, maxTicksLimit: 12 } },
        y: axisMoney()
      }
    }
  });
}

function buildPlanChart() {
  const canvas = document.getElementById("planChart");
  if (!canvas || !window.Chart) return;

  const data = [...PLANS].sort((a, b) => clean(a.mrr) - clean(b.mrr));

  planChart = new Chart(canvas.getContext("2d"), {
    type: "bar",
    data: {
      labels: data.map(row => row.plan_name),
      datasets: [{
        label: "MRR",
        data: data.map(row => clean(row.mrr)),
        backgroundColor: data.map((_, i) => PAL[i % PAL.length] + "cc")
      }]
    },
    options: {
      indexAxis: "y",
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: { label: ctx => fmt$(ctx.raw) } }
      },
      scales: {
        x: axisMoney(),
        y: { grid: { display: false }, ticks: { color: MUTED } }
      }
    }
  });
}

function buildRegionChart() {
  const canvas = document.getElementById("regionChart");
  if (!canvas || !window.Chart) return;

  regionChart = new Chart(canvas.getContext("2d"), {
    type: "bar",
    data: {
      labels: REGIONS.map(row => row.region),
      datasets: [{
        data: REGIONS.map(row => clean(row.revenue)),
        backgroundColor: REGIONS.map((_, i) => PAL[i % PAL.length] + "cc")
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false }, tooltip: { callbacks: { label: ctx => fmt$(ctx.raw) } } },
      scales: {
        x: { grid: { display: false }, ticks: { color: MUTED } },
        y: axisMoney()
      }
    }
  });
}

function buildChurnChart() {
  const canvas = document.getElementById("churnChart");
  if (!canvas || !window.Chart) return;

  churnChart = new Chart(canvas.getContext("2d"), {
    type: "bar",
    data: {
      labels: CHURN.map(row => row.plan_name),
      datasets: [{
        label: "Churn rate",
        data: CHURN.map(row => clean(row.churn_rate)),
        backgroundColor: "#9c5047cc"
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false }, tooltip: { callbacks: { label: ctx => pct(ctx.raw) } } },
      scales: {
        x: { grid: { display: false }, ticks: { color: MUTED } },
        y: { grid: { color: BORDER }, ticks: { color: MUTED, callback: value => value + "%" } }
      }
    }
  });
}

function buildSegChart() {
  const canvas = document.getElementById("segChart");
  if (!canvas || !window.Chart) return;

  segChart = new Chart(canvas.getContext("2d"), {
    type: "doughnut",
    data: {
      labels: SEGMENTS.map(row => row.segment),
      datasets: [{
        data: SEGMENTS.map(row => clean(row.customers)),
        backgroundColor: SEGMENTS.map((_, i) => PAL[i % PAL.length] + "dd"),
        borderColor: "#fffdf8",
        borderWidth: 2
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: "62%",
      plugins: {
        legend: { position: "bottom", labels: { boxWidth: 10, padding: 12 } }
      }
    }
  });
}

function buildRegionTable() {
  const el = document.getElementById("regionTbody");
  if (!el) return;

  el.innerHTML = REGIONS.map(row => `
    <tr>
      <td>${row.region}</td>
      <td class="mono">${fmt$(row.revenue)}</td>
      <td>${fmtNumber(row.customers)}</td>
    </tr>
  `).join("");
}

function buildSegmentList() {
  const el = document.getElementById("segList");
  if (!el) return;

  const total = SEGMENTS.reduce((sum, row) => sum + clean(row.total_revenue), 0) || 1;

  el.innerHTML = SEGMENTS.map((row, i) => {
    const share = clean(row.total_revenue) / total * 100;
    const color = PAL[i % PAL.length];

    return `
      <div class="seg-row">
        <div class="seg-swatch" style="background:${color}"></div>
        <div class="seg-body">
          <div class="seg-name">${row.segment}</div>
          <div class="seg-meta">${fmtNumber(row.customers)} customers · avg MRR ${fmt$(row.avg_mrr)} · ${clean(row.avg_active_users).toFixed(1)} active users</div>
          <div class="seg-bar-track"><div class="seg-bar-fill" style="width:${share.toFixed(1)}%;background:${color}"></div></div>
        </div>
        <div class="seg-right">
          <div class="seg-value">${fmt$(row.total_revenue)}</div>
          <div class="seg-count">${share.toFixed(1)}% of revenue</div>
        </div>
      </div>
    `;
  }).join("");
}

function buildRiskTable() {
  const table = document.getElementById("riskTable");
  if (!table) return;

  table.innerHTML = `
    <thead>
      <tr>
        <th>Company</th>
        <th>Plan</th>
        <th>Users</th>
        <th>Tickets</th>
        <th>Revenue</th>
      </tr>
    </thead>
    <tbody>
      ${RISK.slice(0, 10).map(row => `
        <tr>
          <td>${row.company_name}</td>
          <td>${row.plan_name || "—"}</td>
          <td>${fmtNumber(row.active_users)}</td>
          <td>${fmtNumber(row.tickets)}</td>
          <td class="mono">${fmt$(row.total_revenue)}</td>
        </tr>
      `).join("")}
    </tbody>
  `;
}

function buildCohortTable() {
  const table = document.getElementById("cohortTable");
  if (!table) return;

  if (!COHORT.rows || !COHORT.rows.length) {
    table.innerHTML = "<tbody><tr><td>No cohort data available.</td></tr></tbody>";
    return;
  }

  const head = `
    <thead>
      <tr>
        <th>Cohort</th>
        ${COHORT.headers.map(h => `<th>${h}</th>`).join("")}
      </tr>
    </thead>
  `;

  const body = COHORT.rows.map(row => {
    const cells = row.vals.map(value => {
      if (value === null || value === undefined) return `<td style="color:var(--line)">—</td>`;

      const opacity = (clean(value) / 100 * .55 + .08).toFixed(2);
      const background = clean(value) === 100 ? "rgba(37,63,92,.18)" : `rgba(37,63,92,${opacity})`;
      const color = clean(value) > 25 ? TEXT : MUTED;

      return `<td style="background:${background};color:${color}">${value}%</td>`;
    }).join("");

    return `<tr><td style="color:var(--muted)">${row.label}</td>${cells}</tr>`;
  }).join("");

  table.innerHTML = head + `<tbody>${body}</tbody>`;
}

function renderInsights() {
  const grid = document.getElementById("insightGrid");
  if (!grid) return;

  const k = DASHBOARD.kpis || {};
  const topPlan = [...PLANS].sort((a, b) => clean(b.mrr) - clean(a.mrr))[0];
  const highestChurnPlan = [...CHURN].sort((a, b) => clean(b.churn_rate) - clean(a.churn_rate))[0];
  const topSegment = [...SEGMENTS].sort((a, b) => clean(b.total_revenue) - clean(a.total_revenue))[0];

  grid.innerHTML = `
    <article class="insight-card good">
      <div class="insight-head">${topPlan?.plan_name || "Top plan"} drives the most MRR</div>
      <div class="insight-body">${topPlan ? `${topPlan.plan_name} contributes ${fmt$(topPlan.mrr)} in MRR across ${fmtNumber(topPlan.customers)} customers.` : "Plan data is unavailable."}</div>
    </article>

    <article class="insight-card flagged">
      <div class="insight-head">${highestChurnPlan?.plan_name || "A plan"} has the highest churn</div>
      <div class="insight-body">${highestChurnPlan ? `${highestChurnPlan.plan_name} has a churn rate of ${pct(highestChurnPlan.churn_rate)}. This is a good area for onboarding and product adoption analysis.` : "Churn data is unavailable."}</div>
    </article>

    <article class="insight-card neutral">
      <div class="insight-head">${topSegment?.segment || "Top segment"} is the strongest customer segment</div>
      <div class="insight-body">${topSegment ? `${topSegment.segment} generated ${fmt$(topSegment.total_revenue)} in historical revenue with average MRR of ${fmt$(topSegment.avg_mrr)}.` : "Segment data is unavailable."}</div>
    </article>

    <article class="insight-card flagged">
      <div class="insight-head">High-risk accounts need follow-up</div>
      <div class="insight-body">${fmtNumber(k.high_risk_customers)} active customers are flagged as higher risk based on low usage or elevated support activity.</div>
    </article>
  `;
}

function showLoadError(error) {
  const shell = document.querySelector(".report-shell") || document.body;
  const box = document.createElement("section");
  box.className = "report-card";
  box.style.borderLeft = "4px solid #9c5047";
  box.innerHTML = `
    <h2>Data loading error</h2>
    <p style="color:var(--muted)">
      ${error.message}<br>
      Run <code>python -m http.server</code> from the project root and open <code>/dashboard/index.html</code>.
    </p>
  `;
  shell.prepend(box);
}

window.addEventListener("DOMContentLoaded", () => {
  loadDashboardData().catch(error => {
    console.error(error);
    showLoadError(error);
  });
});
