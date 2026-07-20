// Clerk is optional. When VITE_CLERK_PUBLISHABLE_KEY is unset the whole app still
// runs (zero-key demo mode) — we simply don't mount ClerkProvider or render any
// auth UI. Drop the key into web/.env.local to switch accounts on.
export const CLERK_KEY = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY || "";
export const hasClerk = Boolean(CLERK_KEY);
