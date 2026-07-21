import { Show, SignInButton, SignUpButton, UserButton } from "@clerk/react";

// Header auth surface. Only rendered when Clerk is configured (see App.jsx), so
// these Clerk components are always inside a ClerkProvider. The UserButton's
// "Manage account" panel is where users connect social accounts (Google, GitHub…).
export default function AuthControls() {
  return (
    <>
      <Show when="signed-out">
        <SignInButton mode="modal">
          <button className="signin-btn">Sign in</button>
        </SignInButton>
        <SignUpButton mode="modal">
          <button className="free-chip">Sign up</button>
        </SignUpButton>
      </Show>
      <Show when="signed-in">
        <UserButton afterSignOutUrl="/" />
      </Show>
    </>
  );
}
