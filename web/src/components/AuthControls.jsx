import { SignedIn, SignedOut, SignInButton, UserButton } from "@clerk/clerk-react";

// Header auth surface. Only rendered when Clerk is configured (see App.jsx), so
// these Clerk components are always inside a ClerkProvider. The UserButton's
// "Manage account" panel is where users connect social accounts (Google, GitHub…).
export default function AuthControls() {
  return (
    <>
      <SignedOut>
        <SignInButton mode="modal">
          <button className="signin-btn">Sign in</button>
        </SignInButton>
      </SignedOut>
      <SignedIn>
        <UserButton afterSignOutUrl="/" />
      </SignedIn>
    </>
  );
}
