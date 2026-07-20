import React from "react";
import { createRoot } from "react-dom/client";
import { ClerkProvider } from "@clerk/clerk-react";
import App from "./App.jsx";
import { CLERK_KEY, hasClerk } from "./lib/clerk.js";
import "./styles.css";

// Mount ClerkProvider only when a publishable key is configured. Without it the
// app renders exactly as before — no auth, shared demo deck — so nothing breaks
// while there's no key.
const tree = hasClerk ? (
  <ClerkProvider publishableKey={CLERK_KEY} afterSignOutUrl="/">
    <App />
  </ClerkProvider>
) : (
  <App />
);

createRoot(document.getElementById("root")).render(
  <React.StrictMode>{tree}</React.StrictMode>
);
