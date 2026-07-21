// Verify a Clerk session JWT (RS256) against the instance's JWKS, so metering can
// be keyed to the signed-in user instead of their IP. Pure Web Crypto — no deps.

const jwksCache = new Map(); // iss -> { at, keys }
const JWKS_TTL = 3_600_000;

function b64urlToBytes(s) {
  s = s.replace(/-/g, "+").replace(/_/g, "/");
  const pad = s.length % 4;
  if (pad) s += "=".repeat(4 - pad);
  const bin = atob(s);
  const arr = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) arr[i] = bin.charCodeAt(i);
  return arr;
}
const decodeSeg = (s) => JSON.parse(new TextDecoder().decode(b64urlToBytes(s)));

async function getJwks(iss) {
  const c = jwksCache.get(iss);
  if (c && Date.now() - c.at < JWKS_TTL) return c.keys;
  const r = await fetch(iss.replace(/\/$/, "") + "/.well-known/jwks.json");
  if (!r.ok) return null;
  const j = await r.json();
  jwksCache.set(iss, { at: Date.now(), keys: j.keys || [] });
  return j.keys || [];
}

// Only trust tokens whose issuer is our Clerk instance (pinned) or a *.clerk.* host.
function issuerAllowed(env, iss) {
  if (env.CLERK_ISSUER) return iss === env.CLERK_ISSUER;
  try {
    const host = new URL(iss).host;
    return /(^|\.)clerk\.accounts\.dev$/.test(host) || /\.clerk\./.test(host);
  } catch {
    return false;
  }
}

// Returns the user id (sub) if the token is valid, else null. Never throws.
export async function verifyClerkToken(env, token) {
  try {
    const [h, p, s] = token.split(".");
    if (!h || !p || !s) return null;
    const header = decodeSeg(h);
    const payload = decodeSeg(p);
    if (header.alg !== "RS256") return null;
    if (!payload.iss || !issuerAllowed(env, payload.iss)) return null;
    if (payload.exp && Date.now() / 1000 > payload.exp + 5) return null;

    const keys = await getJwks(payload.iss);
    const jwk = keys && keys.find((k) => k.kid === header.kid);
    if (!jwk) return null;

    const key = await crypto.subtle.importKey(
      "jwk", jwk, { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" }, false, ["verify"]
    );
    const ok = await crypto.subtle.verify(
      "RSASSA-PKCS1-v1_5", key, b64urlToBytes(s), new TextEncoder().encode(`${h}.${p}`)
    );
    return ok ? payload.sub || null : null;
  } catch {
    return null;
  }
}
