// Client for the backend API (server/main.py, started with `python -m server`).
//
// In development the Vite dev server forwards /api to http://localhost:8000 (vite.config.js),
// so the same relative URLs also work when the app is opened from a phone on the same Wi-Fi.
// Set VITE_API_URL to talk to another address, e.g. VITE_API_URL=http://192.168.1.20:8000/api

export const API_BASE = (import.meta.env?.VITE_API_URL ?? "/api").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(status, detail) {
    super(typeof detail === "string" ? detail : `Request failed (${status})`);
    this.status = status;
    this.detail = detail;
  }
}

async function request(method, path, body, { timeoutMs = 6000 } = {}) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const res = await fetch(API_BASE + path, {
      method,
      headers: body === undefined ? undefined : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: ctrl.signal,
    });
    const data = res.headers.get("content-type")?.includes("application/json") ? await res.json() : null;
    if (!res.ok) throw new ApiError(res.status, data?.detail);
    return data;
  } finally {
    clearTimeout(timer);
  }
}

export const api = {
  health: () => request("GET", "/health", undefined, { timeoutMs: 1500 }),
  status: () => request("GET", "/status", undefined, { timeoutMs: 3000 }),
  settings: () => request("GET", "/settings"),

  dogs: () => request("GET", "/dogs"),
  selectDog: (dogId) => request("POST", `/dogs/${dogId}/select`),
  setStage: (dogId, exerciseId, stage) => request("PATCH", `/dogs/${dogId}/exercises/${exerciseId}`, { stage }),

  schedules: () => request("GET", "/schedules"),
  updateSchedule: (id, patch) => request("PATCH", `/schedules/${id}`, patch),

  daily: (days = 7) => request("GET", `/stats/daily?days=${days}`),

  command: (exercise) => request("POST", "/commands", { exercise }),
  treat: () => request("POST", "/treat"),
  testTreat: () => request("POST", "/feeder/test"),

  videoUrl: () => `${API_BASE}/video`,
};
