// API Client for Campus Sensor Monitoring Backend

const API_BASE = window.location.origin.startsWith("http")
  ? `${window.location.origin}/api/v1`
  : "http://localhost:8080/api/v1";

class ApiClient {
  constructor() {
    this.token = localStorage.getItem("sensor_access_token") || null;
  }

  setToken(token) {
    this.token = token;
    if (token) {
      localStorage.setItem("sensor_access_token", token);
    } else {
      localStorage.removeItem("sensor_access_token");
    }
  }

  getHeaders() {
    const headers = {
      "Content-Type": "application/json",
    };
    if (this.token) {
      headers["Authorization"] = `Bearer ${this.token}`;
    }
    return headers;
  }

  async request(endpoint, options = {}) {
    const url = `${API_BASE}${endpoint}`;
    const config = {
      ...options,
      headers: {
        ...this.getHeaders(),
        ...(options.headers || {}),
      },
    };

    try {
      const response = await fetch(url, config);
      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        throw new Error(data.message || `HTTP ${response.status}: Request failed`);
      }
      return data;
    } catch (err) {
      console.error(`API Error on ${endpoint}:`, err);
      throw err;
    }
  }

  // Auth Endpoints
  async register(email, password, fullName, role = "organizer") {
    return this.request("/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password, full_name: fullName, role }),
    });
  }

  async login(email, password) {
    const res = await this.request("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
    if (res.data?.access_token) {
      this.setToken(res.data.access_token);
    }
    return res;
  }

  async getMe() {
    return this.request("/auth/me", { method: "GET" });
  }

  // Readings Ingestion
  async ingestReadings(readings) {
    return this.request("/readings", {
      method: "POST",
      body: JSON.stringify(readings),
    });
  }

  // Sensors
  async listSensors(limit = 100) {
    return this.request(`/sensors?limit=${limit}`, { method: "GET" });
  }

  async getSensorReadings(sensorId, limit = 50) {
    return this.request(`/sensors/${sensorId}/readings?limit=${limit}`, { method: "GET" });
  }

  // Rules
  async listRules() {
    return this.request("/rules", { method: "GET" });
  }

  async createRule(ruleData) {
    return this.request("/rules", {
      method: "POST",
      body: JSON.stringify(ruleData),
    });
  }

  async toggleRule(ruleId, enabled) {
    const action = enabled ? "enable" : "disable";
    return this.request(`/rules/${ruleId}/${action}`, { method: "PATCH" });
  }

  async deleteRule(ruleId) {
    return this.request(`/rules/${ruleId}`, { method: "DELETE" });
  }

  // Alerts
  async listAlerts(status = "", page = 1, pageSize = 50) {
    let url = `/alerts?page=${page}&page_size=${pageSize}`;
    if (status) url += `&status=${status}`;
    return this.request(url, { method: "GET" });
  }

  async acknowledgeAlert(alertId) {
    return this.request(`/alerts/${alertId}/acknowledge`, { method: "PATCH" });
  }

  async resolveAlert(alertId) {
    return this.request(`/alerts/${alertId}/resolve`, { method: "PATCH" });
  }

  async deleteAlert(alertId) {
    return this.request(`/alerts/${alertId}`, { method: "DELETE" });
  }

  // Simulator
  async startSimulator(config) {
    return this.request("/simulator/start", {
      method: "POST",
      body: JSON.stringify(config),
    });
  }

  async stopSimulator() {
    return this.request("/simulator/stop", { method: "POST" });
  }

  async getSimulatorStatus() {
    return this.request("/simulator/status", { method: "GET" });
  }

  // Health
  async getHealth() {
    return this.request("/health", { method: "GET" });
  }
}

export const api = new ApiClient();
