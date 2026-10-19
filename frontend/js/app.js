import { api } from "./api.js";

// State
const state = {
  currentUser: null,
  activeTab: "dashboard",
  sensors: [],
  alerts: [],
  rules: [],
  simulatorStatus: null,
  pollingInterval: null,
  chartData: {
    labels: [],
    temperature: [],
    occupancy: [],
    air_quality: [],
  },
};

// UI Helpers
export function showToast(message, type = "info") {
  const container = document.getElementById("toast-container");
  if (!container) return;

  const toast = document.createElement("div");
  toast.className = `toast toast-${type}`;
  toast.textContent = message;
  container.appendChild(toast);

  setTimeout(() => {
    toast.remove();
  }, 4000);
}

// Formatters
function formatDate(dateStr) {
  if (!dateStr) return "-";
  const d = new Date(dateStr);
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

// Authentication Handlers
async function checkAuth() {
  const userBtn = document.getElementById("auth-btn");
  const userInfo = document.getElementById("user-info");

  if (!api.token) {
    if (userBtn) userBtn.textContent = "Login";
    if (userInfo) userInfo.textContent = "Guest Mode";
    return;
  }

  try {
    const res = await api.getMe();
    state.currentUser = res.data;
    if (userBtn) userBtn.textContent = "Logout";
    if (userInfo) userInfo.textContent = `${state.currentUser.email} (${state.currentUser.role})`;
  } catch (err) {
    api.setToken(null);
    if (userBtn) userBtn.textContent = "Login";
    if (userInfo) userInfo.textContent = "Guest Mode";
  }
}

// Tab Switching
function initTabs() {
  const tabBtns = document.querySelectorAll(".tab-btn");
  tabBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      tabBtns.forEach((b) => b.classList.remove("active"));
      document.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("active"));

      btn.classList.add("active");
      const tabId = btn.getAttribute("data-tab");
      const targetPanel = document.getElementById(`panel-${tabId}`);
      if (targetPanel) targetPanel.classList.add("active");
      state.activeTab = tabId;
    });
  });
}

// Canvas Live Telemetry Chart
function drawChart() {
  const canvas = document.getElementById("telemetry-chart");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const width = canvas.width = canvas.parentElement.clientWidth;
  const height = canvas.height = canvas.parentElement.clientHeight || 280;

  ctx.clearRect(0, 0, width, height);

  // Background Grid Lines
  ctx.strokeStyle = "rgba(255, 255, 255, 0.05)";
  ctx.lineWidth = 1;
  for (let y = 30; y < height; y += 40) {
    ctx.beginPath();
    ctx.moveTo(40, y);
    ctx.lineTo(width, y);
    ctx.stroke();
  }

  const series = [
    { name: "Temp (°C)", data: state.chartData.temperature, color: "#3b82f6" },
    { name: "Occupancy", data: state.chartData.occupancy, color: "#10b981", scale: 0.1 },
    { name: "Air Quality", data: state.chartData.air_quality, color: "#f59e0b", scale: 0.2 },
  ];

  series.forEach((s) => {
    if (s.data.length < 2) return;
    ctx.strokeStyle = s.color;
    ctx.lineWidth = 2;
    ctx.beginPath();

    const stepX = (width - 50) / Math.max(1, s.data.length - 1);
    s.data.forEach((val, idx) => {
      const normalizedVal = (val * (s.scale || 1));
      const posX = 45 + idx * stepX;
      const posY = height - 20 - Math.min(height - 40, normalizedVal * 4);
      if (idx === 0) ctx.moveTo(posX, posY);
      else ctx.lineTo(posX, posY);
    });
    ctx.stroke();
  });
}

// Load Telemetry & Stats
async function refreshDashboard() {
  try {
    // 1. Fetch Health
    const health = await api.getHealth();
    const healthEl = document.getElementById("system-health-badge");
    if (healthEl) {
      healthEl.textContent = health.data?.status === "healthy" ? "Engine Online" : "Degraded";
    }

    // 2. Fetch Alerts
    const alertsRes = await api.listAlerts("", 1, 20);
    state.alerts = alertsRes.data?.items || [];
    const openAlertsCount = state.alerts.filter((a) => a.status === "OPEN").length;

    const alertCountEl = document.getElementById("metric-open-alerts");
    if (alertCountEl) alertCountEl.textContent = openAlertsCount;

    // 3. Fetch Sensors
    const sensorsRes = await api.listSensors(100);
    state.sensors = sensorsRes.data || [];
    const sensorCountEl = document.getElementById("metric-total-sensors");
    if (sensorCountEl) sensorCountEl.textContent = state.sensors.length;

    // 4. Fetch Rules
    const rulesRes = await api.listRules();
    state.rules = rulesRes.data || [];
    const activeRulesCount = state.rules.filter((r) => r.enabled).length;
    const rulesCountEl = document.getElementById("metric-active-rules");
    if (rulesCountEl) rulesCountEl.textContent = activeRulesCount;

    // 5. Simulator Status
    try {
      const simRes = await api.getSimulatorStatus();
      state.simulatorStatus = simRes.data;
      const rateEl = document.getElementById("metric-ingest-rate");
      if (rateEl) {
        rateEl.textContent = `${state.simulatorStatus?.current_rate_per_sec || 0} /s`;
      }
      updateSimulatorUI();
    } catch (_) {}

    renderAlertsTable();
    renderRulesTable();
    renderSensorsTable();

    // Push dummy or sampled point for chart demonstration
    const lastTemp = state.sensors.find((s) => s.sensor_type === "temperature");
    const tempVal = lastTemp ? Math.floor(Math.random() * 15 + 20) : Math.floor(Math.random() * 15 + 20);
    state.chartData.temperature.push(tempVal);
    state.chartData.occupancy.push(Math.floor(Math.random() * 100 + 50));
    state.chartData.air_quality.push(Math.floor(Math.random() * 50 + 20));

    if (state.chartData.temperature.length > 25) {
      state.chartData.temperature.shift();
      state.chartData.occupancy.shift();
      state.chartData.air_quality.shift();
    }
    drawChart();
  } catch (err) {
    console.error("Dashboard refresh error:", err);
  }
}

// Render Alerts Table
function renderAlertsTable() {
  const tbody = document.getElementById("alerts-table-body");
  if (!tbody) return;

  if (state.alerts.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; color:var(--text-muted); padding:2rem;">No alerts recorded</td></tr>`;
    return;
  }

  tbody.innerHTML = state.alerts
    .map(
      (a) => `
    <tr>
      <td><code>${a.sensor_id}</code></td>
      <td><strong>${a.trigger_value}</strong> (th: ${a.threshold})</td>
      <td><span class="badge badge-${a.severity.toLowerCase()}">${a.severity}</span></td>
      <td><span class="badge badge-${a.status.toLowerCase()}">${a.status}</span></td>
      <td>${formatDate(a.triggered_at)}</td>
      <td>
        <div style="display:flex; gap:0.25rem;">
          ${a.status === "OPEN" ? `<button class="btn btn-sm btn-secondary ack-btn" data-id="${a.id}">Ack</button>` : ""}
          ${a.status !== "RESOLVED" ? `<button class="btn btn-sm btn-success resolve-btn" data-id="${a.id}">Resolve</button>` : ""}
          <button class="btn btn-sm btn-danger del-alert-btn" data-id="${a.id}">×</button>
        </div>
      </td>
    </tr>
  `
    )
    .join("");

  // Attach action listeners
  tbody.querySelectorAll(".ack-btn").forEach((b) => {
    b.addEventListener("click", async () => {
      try {
        await api.acknowledgeAlert(b.getAttribute("data-id"));
        showToast("Alert acknowledged", "info");
        refreshDashboard();
      } catch (e) {
        showToast(e.message, "error");
      }
    });
  });

  tbody.querySelectorAll(".resolve-btn").forEach((b) => {
    b.addEventListener("click", async () => {
      try {
        await api.resolveAlert(b.getAttribute("data-id"));
        showToast("Alert resolved", "success");
        refreshDashboard();
      } catch (e) {
        showToast(e.message, "error");
      }
    });
  });

  tbody.querySelectorAll(".del-alert-btn").forEach((b) => {
    b.addEventListener("click", async () => {
      try {
        await api.deleteAlert(b.getAttribute("data-id"));
        showToast("Alert deleted", "info");
        refreshDashboard();
      } catch (e) {
        showToast(e.message, "error");
      }
    });
  });
}

// Render Rules Table
function renderRulesTable() {
  const tbody = document.getElementById("rules-table-body");
  if (!tbody) return;

  if (state.rules.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; color:var(--text-muted); padding:2rem;">No rules configured</td></tr>`;
    return;
  }

  tbody.innerHTML = state.rules
    .map(
      (r) => `
    <tr>
      <td><strong>${r.name}</strong></td>
      <td><code>${r.sensor_type}</code></td>
      <td>${r.rule_type}</td>
      <td>${r.aggregation || ""} ${r.window || ""} ${r.operator} ${r.threshold}</td>
      <td><span class="badge badge-${r.severity.toLowerCase()}">${r.severity}</span></td>
      <td>
        <input type="checkbox" class="rule-toggle" data-id="${r.id}" ${r.enabled ? "checked" : ""}>
      </td>
      <td>
        <button class="btn btn-sm btn-danger del-rule-btn" data-id="${r.id}">Delete</button>
      </td>
    </tr>
  `
    )
    .join("");

  tbody.querySelectorAll(".rule-toggle").forEach((cb) => {
    cb.addEventListener("change", async (e) => {
      try {
        await api.toggleRule(cb.getAttribute("data-id"), e.target.checked);
        showToast(`Rule ${e.target.checked ? "enabled" : "disabled"}`, "info");
        refreshDashboard();
      } catch (err) {
        showToast(err.message, "error");
        e.target.checked = !e.target.checked;
      }
    });
  });

  tbody.querySelectorAll(".del-rule-btn").forEach((b) => {
    b.addEventListener("click", async () => {
      try {
        await api.deleteRule(b.getAttribute("data-id"));
        showToast("Rule deleted", "info");
        refreshDashboard();
      } catch (err) {
        showToast(err.message, "error");
      }
    });
  });
}

// Render Sensors Table
function renderSensorsTable() {
  const tbody = document.getElementById("sensors-table-body");
  if (!tbody) return;

  if (state.sensors.length === 0) {
    tbody.innerHTML = `<tr><td colspan="5" style="text-align:center; color:var(--text-muted); padding:2rem;">No sensors registered</td></tr>`;
    return;
  }

  tbody.innerHTML = state.sensors
    .slice(0, 50)
    .map(
      (s) => `
    <tr>
      <td><code>${s.id}</code></td>
      <td>${s.name}</td>
      <td><span class="badge badge-low">${s.sensor_type}</span></td>
      <td>${s.is_active ? '<span class="status-badge">Active</span>' : "Inactive"}</td>
      <td>${formatDate(s.created_at)}</td>
    </tr>
  `
    )
    .join("");
}

// Update Simulator UI State
function updateSimulatorUI() {
  const startBtn = document.getElementById("start-sim-btn");
  const stopBtn = document.getElementById("stop-sim-btn");
  const statusBadge = document.getElementById("sim-status-badge");

  if (!state.simulatorStatus) return;

  if (state.simulatorStatus.is_running) {
    if (startBtn) startBtn.disabled = true;
    if (stopBtn) stopBtn.disabled = false;
    if (statusBadge) {
      statusBadge.textContent = "RUNNING";
      statusBadge.className = "badge badge-critical";
    }
  } else {
    if (startBtn) startBtn.disabled = false;
    if (stopBtn) stopBtn.disabled = true;
    if (statusBadge) {
      statusBadge.textContent = "IDLE";
      statusBadge.className = "badge badge-resolved";
    }
  }
}

// Modal Handlers
function initModals() {
  // 1. Auth Dialog
  const authModal = document.getElementById("auth-modal");
  const authBtn = document.getElementById("auth-btn");
  const authForm = document.getElementById("auth-form");

  if (authBtn && authModal) {
    authBtn.addEventListener("click", () => {
      if (api.token) {
        api.setToken(null);
        showToast("Logged out successfully", "info");
        checkAuth();
      } else {
        authModal.showModal();
      }
    });
  }

  if (authForm && authModal) {
    authForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const email = document.getElementById("auth-email").value;
      const password = document.getElementById("auth-password").value;
      const isRegister = document.getElementById("auth-is-register").checked;

      try {
        if (isRegister) {
          await api.register(email, password, "Organizer User", "organizer");
          showToast("Account created! Logging in...", "success");
        }
        await api.login(email, password);
        showToast("Authenticated as Organizer", "success");
        authModal.close();
        checkAuth();
      } catch (err) {
        showToast(err.message, "error");
      }
    });
  }

  // 2. Create Rule Dialog
  const ruleModal = document.getElementById("rule-modal");
  const openRuleBtn = document.getElementById("open-rule-modal-btn");
  const ruleForm = document.getElementById("rule-form");

  if (openRuleBtn && ruleModal) {
    openRuleBtn.addEventListener("click", () => ruleModal.showModal());
  }

  if (ruleForm && ruleModal) {
    ruleForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const payload = {
        name: document.getElementById("rule-name").value,
        sensor_type: document.getElementById("rule-sensor-type").value,
        rule_type: document.getElementById("rule-type-select").value,
        operator: document.getElementById("rule-operator").value,
        threshold: parseFloat(document.getElementById("rule-threshold").value),
        severity: document.getElementById("rule-severity").value,
        cooldown_seconds: parseInt(document.getElementById("rule-cooldown").value || "300", 10),
      };

      if (payload.rule_type === "window") {
        payload.aggregation = document.getElementById("rule-aggregation").value;
        payload.window = document.getElementById("rule-window").value;
      }

      try {
        await api.createRule(payload);
        showToast("Rule created successfully", "success");
        ruleModal.close();
        refreshDashboard();
      } catch (err) {
        showToast(err.message, "error");
      }
    });
  }

  // 3. Simulator Controls
  const startSimBtn = document.getElementById("start-sim-btn");
  const stopSimBtn = document.getElementById("stop-sim-btn");

  if (startSimBtn) {
    startSimBtn.addEventListener("click", async () => {
      const config = {
        number_of_sensors: parseInt(document.getElementById("sim-sensors").value, 10),
        duration_seconds: parseInt(document.getElementById("sim-duration").value, 10),
        batch_size: parseInt(document.getElementById("sim-batch-size").value, 10),
        frequency_per_second: parseInt(document.getElementById("sim-frequency").value, 10),
      };
      try {
        await api.startSimulator(config);
        showToast(`Simulator started (${config.number_of_sensors} sensors)`, "success");
        refreshDashboard();
      } catch (err) {
        showToast(err.message, "error");
      }
    });
  }

  if (stopSimBtn) {
    stopSimBtn.addEventListener("click", async () => {
      try {
        await api.stopSimulator();
        showToast("Simulator stopped", "info");
        refreshDashboard();
      } catch (err) {
        showToast(err.message, "error");
      }
    });
  }

  // 4. Test Ingestion Form
  const testIngestForm = document.getElementById("test-ingest-form");
  if (testIngestForm) {
    testIngestForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const payload = {
        sensorId: document.getElementById("test-sensor-id").value,
        type: document.getElementById("test-sensor-type").value,
        value: parseFloat(document.getElementById("test-sensor-value").value),
        timestamp: new Date().toISOString(),
      };

      try {
        const res = await api.ingestReadings(payload);
        showToast(`Ingested! Alerts triggered: ${res.data?.alerts_triggered || 0}`, "success");
        refreshDashboard();
      } catch (err) {
        showToast(err.message, "error");
      }
    });
  }
}

// Initial Boot
document.addEventListener("DOMContentLoaded", () => {
  initTabs();
  initModals();
  checkAuth();
  refreshDashboard();

  // Polling loop
  state.pollingInterval = setInterval(refreshDashboard, 3000);
});
