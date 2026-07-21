import { useAuth } from "@clerk/react";
import { useEffect } from "react";
import { setTokenGetter } from "../lib/api.js";

// Bridges the Clerk session into api.js: while signed in, API calls carry the
// user's session token (X-Clerk-Token) so metering is per-account. Rendered only
// inside ClerkProvider (App renders it only when Clerk is configured). No UI.
export default function ClerkTokenBridge({ onAuthChange }) {
  const { getToken, isSignedIn } = useAuth();

  useEffect(() => {
    setTokenGetter(isSignedIn ? () => getToken() : null);
    onAuthChange?.();
    return () => setTokenGetter(null);
  }, [isSignedIn, getToken, onAuthChange]);

  return null;
}
