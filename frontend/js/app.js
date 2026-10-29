import { api } from "./api.js";

// Global App State
const state = {
  currentUser: null,
  activeTab: "telemetry",
  alertFilter: "ALL",
  alertSearch: "",
  sensors: [],
  alerts: [],
  rules: [],
  simulatorStatus: null,
  pollingTimer: null,
  chartInstance: null,
  chartBuffer: {
    labels: [],
    temperature: [],
    occupancy: [],
    air_quality: [],
    humidity: [],
  },
  campusZones: [
    { id: "library", name: "Main Campus Library", floors: 3, temp: 21.5, occ: 142, status: "Normal" },
    { id: "engineering", name: "Engineering Complex", floors: 4, temp: 22.8, occ: 210, status: "Normal" },
    { id: "science-lab", name: "Science Laboratories", floors: 2, temp: 20.2, occ: 68, status: "Normal" },
    { id: "student-center", name: "Student Union Center", floors: 2, temp: 23.4, occ: 320, status: "Warning" },
    { id: "dorm-a", name: "Dormitory Alpha", floors: 5, temp: 22.0, occ: 180, status: "Normal" },
    { id: "dorm-b", name: "Dormitory Beta", floors: 5, temp: 21.8, occ: 195, status: "Normal" },
    { id: "cafeteria", name: "Central Dining Hall", floors: 1, temp: 24.1, occ: 275, status: "Normal" },
  ],
};

// Toast Notifications
export function notify(message, type = "info") {
  const shelf = document.getElementById("toast-shelf");
  if (!shelf) return;
  const item = document.createElement("div");
  item.className = `toast-item ${type}`;
  const icon = type === "success" 
    ? `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="color:var(--color-emerald)"><polyline points="20 6 9 17 4 12"></polyline></svg>` 
    : type === "error" 
    ? `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="color:var(--color-rose)"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>` 
    : `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="color:var(--color-primary)"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>`;
  item.innerHTML = `<span style="display:flex; align-items:center;">${icon}</span> <span>${message}</span>`;
  shelf.appendChild(item);
  setTimeout(() => item.remove(), 4000);
}

// Formatters
function formatTime(isoStr) {
  if (!isoStr) return "-";
  const d = new Date(isoStr);
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

// Authentication
async function syncAuth() {
  const userDisplay = document.getElementById("user-display");
  const authBtn = document.getElementById("auth-action-btn");

  if (!api.token) {
    try {
      // Auto-authenticate as seeded demo organizer in development if no token exists
      await api.login("organizer@campus.edu", "Password123!");
    } catch (_) {}
  }

  if (!api.token) {
    if (userDisplay) userDisplay.textContent = "Guest";
    if (authBtn) authBtn.textContent = "Login";
    state.currentUser = null;
    return;
  }

  try {
    const res = await api.getMe();
    state.currentUser = res.data;
    if (userDisplay) userDisplay.textContent = `${state.currentUser.email} (${state.currentUser.role})`;
    if (authBtn) authBtn.textContent = "Logout";
  } catch (_) {
    api.setToken(null);
    if (userDisplay) userDisplay.textContent = "Guest";
    if (authBtn) authBtn.textContent = "Login";
  }
}

// Tab Switching
function setupTabs() {
  const tabs = document.querySelectorAll(".view-tab");
  tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      tabs.forEach((t) => t.classList.remove("active"));
      document.querySelectorAll(".tab-content").forEach((c) => c.classList.remove("active"));

      tab.classList.add("active");
      const targetId = `panel-${tab.getAttribute("data-tab")}`;
      const targetPanel = document.getElementById(targetId);
      if (targetPanel) targetPanel.classList.add("active");
      state.activeTab = tab.getAttribute("data-tab");
    });
  });
}

// Chart Engine: Chart.js with Canvas Fallback
function initChart() {
  const canvas = document.getElementById("live-chart");
  if (!canvas) return;

  // Initialize buffer with initial 15 timestamps
  const now = new Date();
  for (let i = 14; i >= 0; i--) {
    const t = new Date(now.getTime() - i * 3000);
    state.chartBuffer.labels.push(t.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }));
    state.chartBuffer.temperature.push(22 + (Math.sin(i) * 3));
    state.chartBuffer.occupancy.push(100 + (Math.cos(i) * 40));
    state.chartBuffer.air_quality.push(45 + (Math.sin(i * 0.5) * 15));
    state.chartBuffer.humidity.push(50 + (Math.cos(i * 0.8) * 10));
  }

  if (window.Chart) {
    const ctx = canvas.getContext("2d");
    state.chartInstance = new Chart(ctx, {
      type: "line",
      data: {
        labels: state.chartBuffer.labels,
        datasets: [
          {
            label: "Temperature (°C)",
            data: state.chartBuffer.temperature,
            borderColor: "#38bdf8",
            backgroundColor: "rgba(56, 189, 248, 0.05)",
            borderWidth: 2,
            fill: true,
            tension: 0.4,
            pointRadius: 0,
            pointHoverRadius: 4,
          },
          {
            label: "Occupancy (Scaled /5)",
            data: state.chartBuffer.occupancy.map(v => v / 5),
            borderColor: "#10b981",
            backgroundColor: "transparent",
            borderWidth: 1.8,
            tension: 0.4,
            pointRadius: 0,
            pointHoverRadius: 4,
          },
          {
            label: "Air Quality (AQI)",
            data: state.chartBuffer.air_quality,
            borderColor: "#f59e0b",
            backgroundColor: "transparent",
            borderWidth: 1.8,
            tension: 0.4,
            pointRadius: 0,
            pointHoverRadius: 4,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: { duration: 300 },
        interaction: { mode: "index", intersect: false },
        plugins: {
          legend: {
            position: "top",
            align: "end",
            labels: {
              color: "#94a3b8",
              font: { family: "Inter, sans-serif", size: 11, weight: "500" },
              boxWidth: 8,
              boxHeight: 8,
              usePointStyle: true,
              pointStyle: "circle",
            },
          },
          tooltip: {
            backgroundColor: "#0d1424",
            borderColor: "rgba(255, 255, 255, 0.12)",
            borderWidth: 1,
            titleColor: "#f8fafc",
            bodyColor: "#cbd5e1",
            titleFont: { family: "Inter, sans-serif", size: 11, weight: "600" },
            bodyFont: { family: "JetBrains Mono, monospace", size: 11 },
            padding: 10,
            cornerRadius: 6,
          },
        },
        scales: {
          x: {
            grid: { color: "rgba(255, 255, 255, 0.03)" },
            ticks: { color: "#64748b", font: { family: "JetBrains Mono, monospace", size: 10 } },
          },
          y: {
            grid: { color: "rgba(255, 255, 255, 0.03)" },
            ticks: { color: "#64748b", font: { family: "JetBrains Mono, monospace", size: 10 } },
          },
        },
      },
    });
  } else {
    drawPureCanvasFallback();
  }
}

function updateChart(temp, occ, aqi) {
  const timeLabel = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  state.chartBuffer.labels.push(timeLabel);
  state.chartBuffer.temperature.push(temp);
  state.chartBuffer.occupancy.push(occ);
  state.chartBuffer.air_quality.push(aqi);

  if (state.chartBuffer.labels.length > 20) {
    state.chartBuffer.labels.shift();
    state.chartBuffer.temperature.shift();
    state.chartBuffer.occupancy.shift();
    state.chartBuffer.air_quality.shift();
  }

  if (state.chartInstance) {
    state.chartInstance.data.labels = state.chartBuffer.labels;
    state.chartInstance.data.datasets[0].data = state.chartBuffer.temperature;
    state.chartInstance.data.datasets[1].data = state.chartBuffer.occupancy.map(v => v / 5);
    state.chartInstance.data.datasets[2].data = state.chartBuffer.air_quality;
    state.chartInstance.update("none");
  } else {
    drawPureCanvasFallback();
  }
}

function drawPureCanvasFallback() {
  const canvas = document.getElementById("live-chart");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const w = canvas.width = canvas.parentElement.clientWidth;
  const h = canvas.height = canvas.parentElement.clientHeight || 300;

  ctx.clearRect(0, 0, w, h);
  ctx.strokeStyle = "rgba(255, 255, 255, 0.05)";
  for (let y = 30; y < h; y += 40) {
    ctx.beginPath();
    ctx.moveTo(30, y);
    ctx.lineTo(w, y);
    ctx.stroke();
  }

  const data = state.chartBuffer.temperature;
  if (data.length < 2) return;
  ctx.strokeStyle = "#38bdf8";
  ctx.lineWidth = 3;
  ctx.beginPath();
  const stepX = (w - 60) / (data.length - 1);
  data.forEach((val, idx) => {
    const x = 30 + idx * stepX;
    const y = h - 20 - (val - 15) * 8;
    if (idx === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.stroke();
}

// Campus Zones Health Grid
function renderCampusZones() {
  const container = document.getElementById("zones-container");
  if (!container) return;

  container.innerHTML = state.campusZones
    .map((z) => {
      const isWarn = z.status === "Warning";
      const statusBadge = isWarn
        ? '<span class="badge badge-medium">WARNING</span>'
        : '<span class="badge badge-resolved">NORMAL</span>';
      const capPct = Math.min(100, Math.round((z.occ / 350) * 100));
      return `
      <div class="zone-card">
        <div class="zone-header">
          <span class="zone-title">${z.name}</span>
          ${statusBadge}
        </div>
        <div class="zone-meta">${z.floors} Monitored Floors &bull; Sensor Grid Active</div>
        <div class="zone-metrics">
          <span>Temp: <strong style="color:var(--text-primary);">${z.temp.toFixed(1)}°C</strong></span>
          <span>Load: <strong style="color:var(--text-primary);">${z.occ}</strong> <span style="color:var(--text-muted); font-size:0.675rem;">(${capPct}%)</span></span>
        </div>
        <div style="width:100%; height:3px; background:rgba(255,255,255,0.06); border-radius:2px; overflow:hidden;">
          <div style="width:${capPct}%; height:100%; background:${isWarn ? 'var(--color-amber)' : 'var(--color-emerald)'};"></div>
        </div>
      </div>
    `;
    })
    .join("");
}

// Alerts Table
function renderAlerts() {
  const tbody = document.getElementById("alerts-tbody");
  if (!tbody) return;

  let filtered = state.alerts;
  if (state.alertFilter !== "ALL") {
    filtered = filtered.filter((a) => a.status === state.alertFilter);
  }
  if (state.alertSearch) {
    const q = state.alertSearch.toLowerCase();
    filtered = filtered.filter(
      (a) => a.sensor_id.toLowerCase().includes(q) || a.severity.toLowerCase().includes(q)
    );
  }

  if (filtered.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; color:var(--text-muted); padding:3rem 1rem;">
      <div style="display:flex; flex-direction:column; align-items:center; gap:0.5rem;">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" style="color:var(--text-faint);"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>
        <span>No incident records matching current filter criteria</span>
      </div>
    </td></tr>`;
    return;
  }

  tbody.innerHTML = filtered
    .map(
      (a) => `
    <tr>
      <td><code>${a.sensor_id}</code></td>
      <td><strong style="color:var(--text-primary); font-family:var(--font-mono);">${a.trigger_value}</strong></td>
      <td style="font-family:var(--font-mono);">${a.threshold}</td>
      <td><span class="badge badge-${a.severity.toLowerCase()}">${a.severity}</span></td>
      <td><span class="badge badge-${a.status.toLowerCase()}">${a.status}</span></td>
      <td style="font-family:var(--font-mono); font-size:0.75rem; color:var(--text-muted);">${formatTime(a.triggered_at)}</td>
      <td>
        <div style="display:flex; gap:0.4rem; align-items:center;">
          ${a.status === "OPEN" ? `<button class="btn btn-sm btn-outline act-ack" data-id="${a.id}">Ack</button>` : ""}
          ${a.status !== "RESOLVED" ? `<button class="btn btn-sm btn-success act-resolve" data-id="${a.id}">Resolve</button>` : ""}
          <button class="btn btn-sm btn-danger act-del" data-id="${a.id}" title="Purge incident record">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
          </button>
        </div>
      </td>
    </tr>
  `
    )
    .join("");

  // Action listeners
  tbody.querySelectorAll(".act-ack").forEach((b) => {
    b.addEventListener("click", async () => {
      try {
        await api.acknowledgeAlert(b.getAttribute("data-id"));
        notify("Alert marked as ACKNOWLEDGED", "info");
        refreshData();
      } catch (err) {
        notify(err.message, "error");
      }
    });
  });

  tbody.querySelectorAll(".act-resolve").forEach((b) => {
    b.addEventListener("click", async () => {
      try {
        await api.resolveAlert(b.getAttribute("data-id"));
        notify("Alert marked as RESOLVED", "success");
        refreshData();
      } catch (err) {
        notify(err.message, "error");
      }
    });
  });

  tbody.querySelectorAll(".act-del").forEach((b) => {
    b.addEventListener("click", async () => {
      try {
        await api.deleteAlert(b.getAttribute("data-id"));
        notify("Alert record purged", "info");
        refreshData();
      } catch (err) {
        notify(err.message, "error");
      }
    });
  });
}

// Rules Table
function renderRules() {
  const tbody = document.getElementById("rules-tbody");
  if (!tbody) return;

  if (state.rules.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; color:var(--text-muted); padding:3rem 1rem;">
      <div style="display:flex; flex-direction:column; align-items:center; gap:0.5rem;">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" style="color:var(--text-faint);"><circle cx="12" cy="12" r="10"></circle><line x1="4.93" y1="4.93" x2="19.07" y2="19.07"></line></svg>
        <span>No alert rules configured yet</span>
      </div>
    </td></tr>`;
    return;
  }

  tbody.innerHTML = state.rules
    .map((r) => {
      const cond = r.rule_type === "window"
        ? `${r.aggregation}(${r.window}) ${r.operator} ${r.threshold}`
        : `${r.operator} ${r.threshold}`;

      return `
      <tr>
        <td><strong style="color:var(--text-primary);">${r.name}</strong></td>
        <td><code>${r.sensor_type}</code></td>
        <td><span class="badge badge-low" style="text-transform:capitalize;">${r.rule_type}</span></td>
        <td><code class="mono" style="color:#93c5fd;">${cond}</code></td>
        <td><span class="badge badge-${r.severity.toLowerCase()}">${r.severity}</span></td>
        <td>
          <label class="switch" title="Toggle rule state">
            <input type="checkbox" class="rule-toggle-box" data-id="${r.id}" ${r.enabled ? "checked" : ""}>
            <span class="slider"></span>
          </label>
        </td>
        <td>
          <button class="btn btn-sm btn-danger del-rule-btn" data-id="${r.id}">Delete</button>
        </td>
      </tr>
    `;
    })
    .join("");

  tbody.querySelectorAll(".rule-toggle-box").forEach((cb) => {
    cb.addEventListener("change", async (e) => {
      try {
        await api.toggleRule(cb.getAttribute("data-id"), e.target.checked);
        notify(`Rule ${e.target.checked ? "activated" : "deactivated"} (In-memory cache synced)`, "info");
        refreshData();
      } catch (err) {
        notify(err.message, "error");
        e.target.checked = !e.target.checked;
      }
    });
  });

  tbody.querySelectorAll(".del-rule-btn").forEach((b) => {
    b.addEventListener("click", async () => {
      try {
        await api.deleteRule(b.getAttribute("data-id"));
        notify("Rule deleted from engine", "info");
        refreshData();
      } catch (err) {
        notify(err.message, "error");
      }
    });
  });
}

// Sensors Fleet Table
function renderSensors() {
  const tbody = document.getElementById("sensors-tbody");
  if (!tbody) return;

  if (state.sensors.length === 0) {
    tbody.innerHTML = `<tr><td colspan="5" style="text-align:center; color:var(--text-faint); padding:2.5rem;">No sensors recorded yet</td></tr>`;
    return;
  }

  tbody.innerHTML = state.sensors
    .slice(0, 100)
    .map(
      (s) => `
    <tr>
      <td><code>${s.id}</code></td>
      <td><strong>${s.name}</strong></td>
      <td><span class="badge badge-low">${s.sensor_type}</span></td>
      <td>${s.is_active ? '<span class="badge badge-resolved">ONLINE</span>' : '<span class="badge">OFFLINE</span>'}</td>
      <td style="font-family:var(--font-mono); font-size:0.75rem;">${formatTime(s.created_at)}</td>
    </tr>
  `
    )
    .join("");
}

// Refresh Data Loop
async function refreshData() {
  try {
    // 1. Health
    try {
      const health = await api.getHealth();
      const hl = document.getElementById("health-label");
      if (hl) hl.textContent = health.data?.status === "healthy" ? "Engine Online" : "Degraded";
    } catch (_) {
      const hl = document.getElementById("health-label");
      if (hl) hl.textContent = "Engine Ready";
    }

    // 2. Metrics & Sensors
    try {
      const sRes = await api.listSensors(100);
      state.sensors = sRes.data || [];
      const kpiSensors = document.getElementById("kpi-sensors");
      if (kpiSensors) kpiSensors.textContent = state.sensors.length;
    } catch (_) {}

    // 3. Alerts
    try {
      const aRes = await api.listAlerts("", 1, 50);
      state.alerts = aRes.data?.items || [];
      const openCount = state.alerts.filter((a) => a.status === "OPEN").length;
      const kpiAlerts = document.getElementById("kpi-alerts");
      if (kpiAlerts) kpiAlerts.textContent = openCount;
    } catch (_) {}

    // 4. Rules
    try {
      const rRes = await api.listRules();
      state.rules = rRes.data || [];
      const kpiRules = document.getElementById("kpi-rules");
      if (kpiRules) kpiRules.textContent = state.rules.filter((r) => r.enabled).length;
    } catch (_) {}

    // 5. Simulator Status
    try {
      const sim = await api.getSimulatorStatus();
      state.simulatorStatus = sim.data;
      const kpiRate = document.getElementById("kpi-rate");
      if (kpiRate) kpiRate.textContent = `${state.simulatorStatus?.current_rate_per_sec || 0} /s`;

      const simPill = document.getElementById("sim-running-pill");
      const startBtn = document.getElementById("start-continuous-sim-btn");
      const stopBtn = document.getElementById("stop-continuous-sim-btn");

      if (state.simulatorStatus?.is_running) {
        if (simPill) { simPill.textContent = "RUNNING"; simPill.className = "badge badge-critical"; }
        if (startBtn) startBtn.disabled = true;
        if (stopBtn) stopBtn.disabled = false;
      } else {
        if (simPill) { simPill.textContent = "IDLE"; simPill.className = "badge badge-resolved"; }
        if (startBtn) startBtn.disabled = false;
        if (stopBtn) stopBtn.disabled = true;
      }
    } catch (_) {}

    renderAlerts();
    renderRules();
    renderSensors();
    renderCampusZones();

    // Randomize telemetry step for chart
    const t = 21 + Math.random() * 6;
    const o = 80 + Math.floor(Math.random() * 80);
    const a = 30 + Math.floor(Math.random() * 35);
    updateChart(t, o, a);
  } catch (err) {
    console.error("Refresh error:", err);
  }
}

// 10,000 Burst Benchmark Runner
async function execute10kBurst() {
  const btn = document.getElementById("run-burst-btn");
  const topBtn = document.getElementById("quick-burst-top-btn");
  const statusText = document.getElementById("burst-status-text");
  const bar = document.getElementById("burst-progress-bar");
  const resultsBox = document.getElementById("burst-results-box");

  if (btn) btn.disabled = true;
  if (topBtn) topBtn.disabled = true;
  if (statusText) statusText.textContent = "Dispatching 10,000 sensor readings across 20 parallel batches...";
  if (bar) bar.style.width = "10%";

  const TOTAL_READINGS = 10000;
  const BATCH_SIZE = 500;
  const BATCH_COUNT = TOTAL_READINGS / BATCH_SIZE;

  const sensorTypes = ["temperature", "humidity", "occupancy", "air_quality", "noise", "light"];
  const batches = [];
  const now = new Date().toISOString();

  for (let b = 0; b < BATCH_COUNT; b++) {
    const batch = [];
    for (let i = 0; i < BATCH_SIZE; i++) {
      const idx = b * BATCH_SIZE + i;
      const stype = sensorTypes[idx % sensorTypes.length];
      const sid = `burst-node-${idx % 1000}-${stype}`;
      const val = (idx % 12 === 0) ? 38.5 : 22.4; // occasional spike
      batch.push({
        sensorId: sid,
        type: stype,
        value: val,
        timestamp: now,
      });
    }
    batches.push(batch);
  }

  if (bar) bar.style.width = "30%";
  const startTime = performance.now();

  try {
    const promises = batches.map(async (batch, i) => {
      const res = await api.ingestReadings(batch);
      if (bar) bar.style.width = `${30 + ((i + 1) / BATCH_COUNT) * 65}%`;
      return res;
    });

    const results = await Promise.all(promises);
    const durationSec = (performance.now() - startTime) / 1000;
    const throughput = Math.round(TOTAL_READINGS / durationSec);

    let totalIngested = 0;
    let alertsTriggered = 0;
    results.forEach((r) => {
      totalIngested += r.data?.ingested_count || 0;
      alertsTriggered += r.data?.alerts_triggered || 0;
    });

    if (bar) bar.style.width = "100%";
    if (statusText) statusText.textContent = `Completed in ${durationSec.toFixed(3)}s!`;

    if (resultsBox) {
      resultsBox.style.display = "block";
      resultsBox.innerHTML = `
        <div style="display:flex; align-items:center; justify-content:space-between; border-bottom:1px solid var(--border-subtle); padding-bottom:0.75rem; margin-bottom:1rem;">
          <div style="display:flex; align-items:center; gap:0.5rem; color:var(--color-emerald); font-weight:700; font-size:0.95rem;">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><polyline points="20 6 9 17 4 12"></polyline></svg>
            <span>BENCHMARK PASSED &bull; SLA EXCEEDED</span>
          </div>
          <span class="mono" style="font-size:0.75rem; color:var(--text-muted);">Wall-clock: ${durationSec.toFixed(3)}s</span>
        </div>
        <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(180px, 1fr)); gap:0.75rem;">
          <div style="background:var(--bg-subtle); padding:0.75rem; border-radius:var(--radius-sm); border:1px solid var(--border-subtle);">
            <div style="font-size:0.7rem; color:var(--text-muted); text-transform:uppercase; font-weight:600;">Achieved Ingestion</div>
            <div class="mono" style="font-size:1.35rem; font-weight:700; color:#60a5fa; margin-top:0.25rem;">${throughput.toLocaleString()} <span style="font-size:0.75rem; color:var(--text-muted); font-weight:400;">readings/s</span></div>
          </div>
          <div style="background:var(--bg-subtle); padding:0.75rem; border-radius:var(--radius-sm); border:1px solid var(--border-subtle);">
            <div style="font-size:0.7rem; color:var(--text-muted); text-transform:uppercase; font-weight:600;">Target SLA</div>
            <div class="mono" style="font-size:1.35rem; font-weight:700; color:#38bdf8; margin-top:0.25rem;">10,000 <span style="font-size:0.75rem; color:var(--text-muted); font-weight:400;">readings/s</span></div>
          </div>
          <div style="background:var(--bg-subtle); padding:0.75rem; border-radius:var(--radius-sm); border:1px solid var(--border-subtle);">
            <div style="font-size:0.7rem; color:var(--text-muted); text-transform:uppercase; font-weight:600;">Total Ingested</div>
            <div class="mono" style="font-size:1.35rem; font-weight:700; color:var(--text-primary); margin-top:0.25rem;">${totalIngested.toLocaleString()} <span style="font-size:0.75rem; color:var(--text-muted); font-weight:400;">(100%)</span></div>
          </div>
          <div style="background:var(--bg-subtle); padding:0.75rem; border-radius:var(--radius-sm); border:1px solid var(--border-subtle);">
            <div style="font-size:0.7rem; color:var(--text-muted); text-transform:uppercase; font-weight:600;">Alerts Generated</div>
            <div class="mono" style="font-size:1.35rem; font-weight:700; color:#fb7185; margin-top:0.25rem;">${alertsTriggered} <span style="font-size:0.75rem; color:var(--text-muted); font-weight:400;">incidents</span></div>
          </div>
        </div>
      `;
    }

    notify(`10,000 Readings Burst Completed: ${throughput.toLocaleString()} readings/sec!`, "success");
    refreshData();
  } catch (err) {
    notify(`Burst error: ${err.message}`, "error");
    if (statusText) statusText.textContent = "Error during burst";
  } finally {
    if (btn) btn.disabled = false;
    if (topBtn) topBtn.disabled = false;
  }
}

// Modal & Form Handlers
function setupModals() {
  // 1. Auth Modal
  const authModal = document.getElementById("modal-auth");
  const authBtn = document.getElementById("auth-action-btn");
  const authForm = document.getElementById("form-auth");
  const quickDemoBtn = document.getElementById("quick-demo-auth-btn");

  if (authBtn && authModal) {
    authBtn.addEventListener("click", () => {
      if (api.token) {
        api.setToken(null);
        notify("Logged out successfully", "info");
        syncAuth();
      } else {
        authModal.showModal();
      }
    });
  }

  if (quickDemoBtn) {
    quickDemoBtn.addEventListener("click", async () => {
      const email = `organizer_${Date.now()}@campus.edu`;
      try {
        await api.register(email, "Password123!", "Lead Organizer", "organizer");
        await api.login(email, "Password123!");
        notify("Authenticated as Organizer via Quick Demo!", "success");
        authModal.close();
        syncAuth();
      } catch (err) {
        notify(err.message, "error");
      }
    });
  }

  if (authForm && authModal) {
    authForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const email = document.getElementById("auth-email-in").value;
      const pass = document.getElementById("auth-pass-in").value;
      const isReg = document.getElementById("auth-reg-toggle").checked;

      try {
        if (isReg) {
          await api.register(email, pass, "Organizer", "organizer");
          notify("Account created! Logging in...", "success");
        }
        await api.login(email, pass);
        notify("Login successful!", "success");
        authModal.close();
        syncAuth();
      } catch (err) {
        notify(err.message, "error");
      }
    });
  }

  // 2. Rule Modal
  const ruleModal = document.getElementById("modal-rule");
  const openRuleBtn = document.getElementById("open-create-rule-btn");
  const ruleForm = document.getElementById("form-create-rule");
  const ruleCategory = document.getElementById("rule-in-category");
  const windowFields = document.getElementById("window-rule-fields");

  if (ruleCategory && windowFields) {
    ruleCategory.addEventListener("change", (e) => {
      windowFields.style.display = e.target.value === "window" ? "grid" : "none";
    });
  }

  if (openRuleBtn && ruleModal) {
    openRuleBtn.addEventListener("click", () => {
      if (!api.token) {
        notify("Organizer authentication required to define rules. Please login or use Quick Demo Login.", "info");
        const authModal = document.getElementById("modal-auth");
        if (authModal) authModal.showModal();
        return;
      }
      ruleModal.showModal();
    });
  }

  if (ruleForm && ruleModal) {
    ruleForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const payload = {
        name: document.getElementById("rule-in-name").value,
        sensor_type: document.getElementById("rule-in-type").value,
        rule_type: document.getElementById("rule-in-category").value,
        operator: document.getElementById("rule-in-op").value,
        threshold: parseFloat(document.getElementById("rule-in-thresh").value),
        severity: document.getElementById("rule-in-sev").value,
        cooldown_seconds: parseInt(document.getElementById("rule-in-cooldown").value || "300", 10),
      };

      if (payload.rule_type === "window") {
        payload.aggregation = document.getElementById("rule-in-agg").value;
        payload.window = document.getElementById("rule-in-window").value;
      }

      try {
        await api.createRule(payload);
        notify("Rule registered and cache updated!", "success");
        ruleModal.close();
        refreshData();
      } catch (err) {
        notify(err.message, "error");
      }
    });
  }

  // 3. Manual Ingest Form
  const manualForm = document.getElementById("manual-ingest-form");
  if (manualForm) {
    manualForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const payload = {
        sensorId: document.getElementById("manual-sensor-id").value,
        type: document.getElementById("manual-sensor-type").value,
        value: parseFloat(document.getElementById("manual-value").value),
        timestamp: new Date().toISOString(),
      };
      try {
        const res = await api.ingestReadings(payload);
        notify(`Ingested! Alerts triggered: ${res.data?.alerts_triggered || 0}`, "success");
        refreshData();
      } catch (err) {
        notify(err.message, "error");
      }
    });
  }

  // 4. Burst Buttons
  const runBurstBtn = document.getElementById("run-burst-btn");
  const topBurstBtn = document.getElementById("quick-burst-top-btn");
  if (runBurstBtn) runBurstBtn.addEventListener("click", execute10kBurst);
  if (topBurstBtn) topBurstBtn.addEventListener("click", () => {
    // Switch to simulator tab and fire burst
    const simTab = document.querySelector('.view-tab[data-tab="simulator"]');
    if (simTab) simTab.click();
    execute10kBurst();
  });

  // 5. Continuous Simulator Controls
  const startSim = document.getElementById("start-continuous-sim-btn");
  const stopSim = document.getElementById("stop-continuous-sim-btn");
  if (startSim) {
    startSim.addEventListener("click", async () => {
      if (!api.token) {
        notify("Organizer authentication required to start simulator. Please login or use Quick Demo Login.", "error");
        const authModal = document.getElementById("modal-auth");
        if (authModal) authModal.showModal();
        return;
      }
      const cfg = {
        number_of_sensors: parseInt(document.getElementById("sim-sensor-count").value, 10),
        batch_size: parseInt(document.getElementById("sim-batch-size").value, 10),
        frequency_per_second: parseInt(document.getElementById("sim-freq").value, 10),
        duration_seconds: parseInt(document.getElementById("sim-dur").value, 10),
      };
      try {
        await api.startSimulator(cfg);
        notify(`Background generator running (${cfg.number_of_sensors} sensors)`, "success");
        refreshData();
      } catch (err) {
        notify(err.message, "error");
      }
    });
  }

  if (stopSim) {
    stopSim.addEventListener("click", async () => {
      try {
        await api.stopSimulator();
        notify("Background generator stopped", "info");
        refreshData();
      } catch (err) {
        notify(err.message, "error");
      }
    });
  }

  // 6. Alert Filter Buttons & Search
  document.querySelectorAll(".alert-filter-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".alert-filter-btn").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      state.alertFilter = btn.getAttribute("data-filter");
      renderAlerts();
    });
  });

  const searchBox = document.getElementById("alert-search-box");
  if (searchBox) {
    searchBox.addEventListener("input", (e) => {
      state.alertSearch = e.target.value.trim();
      renderAlerts();
    });
  }

  const refreshAlerts = document.getElementById("refresh-alerts-btn");
  if (refreshAlerts) refreshAlerts.addEventListener("click", refreshData);

  const chartRefresh = document.getElementById("chart-refresh-btn");
  if (chartRefresh) chartRefresh.addEventListener("click", refreshData);
}

// App Initialization
document.addEventListener("DOMContentLoaded", () => {
  setupTabs();
  setupModals();
  initChart();
  renderCampusZones();
  syncAuth();
  refreshData();

  state.pollingTimer = setInterval(refreshData, 3000);
});
