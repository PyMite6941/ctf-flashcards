// Pro license = the JWT the GRID Store worker mints after verifying an on-chain
// USDC payment. We store it locally and send it as the X-License header on API
// calls; the backend verifies it through the worker's /verify. Payment + record
// live entirely in GRID Store (grid-store.pages.dev / grid-store-worker).

const KEY = "ctf_license";

// Same worker + wallet as the GRID Store. Override via env for staging.
export const WORKER_URL =
  import.meta.env.VITE_LICENSE_API || "https://grid-store-worker.greshamd27.workers.dev";
export const WALLET_ADDRESS =
  import.meta.env.VITE_PAYMENT_WALLET || "0x8069408a17B77895cb7Cd0B0D804aB46f59Bc4c3";
export const STORE_URL =
  import.meta.env.VITE_STORE_URL || "https://grid-store.pages.dev";
export const PRICE_USDC = 8;
export const TIER_ID = "ctf_pro";

export const getLicense = () => localStorage.getItem(KEY) || "";
export const setLicense = (t) => t && localStorage.setItem(KEY, t);
export const clearLicense = () => localStorage.removeItem(KEY);
export const hasLicense = () => Boolean(getLicense());

// In-page checkout: verify the buyer's USDC-on-Base payment and mint the license.
// Hits the SAME grid-store-worker the store uses, so the sale is recorded in your
// Supabase alongside every other GRID Store purchase.
export async function redeem({ email, txHash }) {
  const res = await fetch(WORKER_URL.replace(/\/$/, "") + "/redeem", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email: email.trim(), tx_hash: txHash.trim(), tier: TIER_ID }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || data.error || "Could not verify the payment.");
  return data; // { token, tier, email, ... }
}
