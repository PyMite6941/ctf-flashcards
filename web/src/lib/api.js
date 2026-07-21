// Thin client for the shared backend. The same code runs in the browser and,
// once wrapped by Capacitor, inside the native Android / iOS shells — so the
// base URL comes from an env var (VITE_API_URL) rather than being hardcoded.
import { getLicense } from "./license.js";

const BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

// Optional Clerk session-token provider — registered by ClerkTokenBridge when a
// user is signed in, so the backend can meter per-account instead of per-IP.
let tokenGetter = null;
export function setTokenGetter(fn) {
  tokenGetter = fn;
}

async function req(path, options = {}) {
  const license = getLicense();
  let clerkToken = null;
  if (tokenGetter) {
    try {
      clerkToken = await tokenGetter();
    } catch {
      clerkToken = null;
    }
  }
  const res = await fetch(BASE + path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(license ? { "X-License": license } : {}),
      ...(clerkToken ? { "X-Clerk-Token": clerkToken } : {}),
      ...(options.headers || {}),
    },
  });
  if (!res.ok) {
    // Preserve status + parsed body so callers can react (e.g. 402 -> upgrade).
    let body = null;
    try {
      body = await res.json();
    } catch {
      body = await res.text().catch(() => "");
    }
    const err = new Error(`${res.status} ${res.statusText}`);
    err.status = res.status;
    err.body = body;
    throw err;
  }
  if (res.status === 204) return null;
  return res.json();
}

export const api = {
  health: () => req("/health"),
  listCards: (deck) => req("/cards" + (deck ? `?deck=${encodeURIComponent(deck)}` : "")),
  createCard: (card) => req("/cards", { method: "POST", body: JSON.stringify(card) }),
  deleteCard: (id) => req(`/cards/${id}`, { method: "DELETE" }),

  limits: () => req("/limits"),
  topics: () => req("/topics"),
  reviewQueue: (limit = 20, tag = null) =>
    req(`/review/queue?limit=${limit}` + (tag ? `&tag=${encodeURIComponent(tag)}` : "")),
  submitReview: (id, rating) =>
    req(`/cards/${id}/review`, { method: "POST", body: JSON.stringify({ rating }) }),

  // AI topic packs
  generatePack: (topic) => req("/ai/generate", { method: "POST", body: JSON.stringify({ topic }) }),
  listPacks: () => req("/ai/packs"),
  getPack: (slug) => req(`/ai/packs/${slug}`),
  submitGenFlag: (id, flag) =>
    req(`/ai/challenges/${id}/submit`, { method: "POST", body: JSON.stringify({ flag }) }),
  labkitUrl: (slug) => `${BASE}/ai/packs/${slug}/labkit`,

  listPuzzles: (params = {}) => {
    const q = new URLSearchParams(
      Object.entries(params).filter(([, v]) => v)
    ).toString();
    return req("/puzzles" + (q ? `?${q}` : ""));
  },
  getPuzzle: (id) => req(`/puzzles/${id}`),
  submitFlag: (id, flag) =>
    req(`/puzzles/${id}/submit`, { method: "POST", body: JSON.stringify({ flag }) }),

  listInbox: (status = "pending") => req(`/inbox?status=${status}`),
  addInbox: (item) => req("/inbox", { method: "POST", body: JSON.stringify(item) }),
  approveInbox: (id, edit) =>
    req(`/inbox/${id}/approve`, { method: "POST", body: JSON.stringify(edit) }),
  rejectInbox: (id) => req(`/inbox/${id}/reject`, { method: "POST" }),
};

export const DIFFICULTY_COLOR = {
  easy: "#22c55e",
  medium: "#f59e0b",
  hard: "#ef4444",
};

// Rating scale shared with the backend + FSRS. Order matters (1..4).
export const RATINGS = [
  { value: 1, label: "Again", hint: "blanked / wrong", color: "#ef4444" },
  { value: 2, label: "Hard", hint: "recalled with effort", color: "#f59e0b" },
  { value: 3, label: "Good", hint: "recalled correctly", color: "#22c55e" },
  { value: 4, label: "Easy", hint: "instant", color: "#3b82f6" },
];
