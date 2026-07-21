// Free-tier metering + Pro entitlement — verified through the GRID Store worker.
// Same idea as app/billing.py: free users get a daily cap; a valid ctf_pro
// license (checked via the store worker's /verify) lifts it.

const PRO_TIERS = new Set(["ctf_pro"]);
const CACHE_TTL_MS = 300_000;
const cache = new Map();

export const freeDailySolves = (env) => parseInt(env.CTF_FREE_DAILY_SOLVES || "3", 10);
export const freeMonthlyAiGens = (env) => parseInt(env.CTF_FREE_MONTHLY_AI_GENS || "9", 10);
const workerUrl = (env) =>
  env.GRID_STORE_WORKER_URL || "https://grid-store-worker.greshamd27.workers.dev";

export function today() {
  return new Date().toISOString().slice(0, 10); // YYYY-MM-DD (UTC)
}

export function thisMonth() {
  return new Date().toISOString().slice(0, 7); // YYYY-MM (UTC)
}

// Cloudflare gives us the real client IP for free.
export function clientIdentity(request) {
  return (
    request.headers.get("cf-connecting-ip") ||
    (request.headers.get("x-forwarded-for") || "").split(",")[0].trim() ||
    "unknown"
  );
}

export async function verifyLicense(env, token) {
  if (!token) return { pro: false, tier: null, expired: false };
  token = token.trim();

  const hit = cache.get(token);
  if (hit && Date.now() - hit.at < CACHE_TTL_MS) return hit.result;

  let result = { pro: false, tier: null, expired: false };
  try {
    const res = await fetch(workerUrl(env).replace(/\/$/, "") + "/verify", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token }),
    });
    const data = await res.json();
    const tier = (data.tier || "").toLowerCase();
    result = {
      pro: !!data.valid && PRO_TIERS.has(tier),
      tier: tier || null,
      expired: !!data.expired,
    };
  } catch {
    result = { pro: false, tier: null, expired: false }; // fail closed on entitlement
  }

  cache.set(token, { at: Date.now(), result });
  return result;
}
