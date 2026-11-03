import { useCallback, useEffect, useState, Suspense, lazy } from "react";
import { api } from "./lib/api.js";
import Home from "./components/Home.jsx";
import ReviewSession from "./components/ReviewSession.jsx";
import Puzzles from "./components/Puzzles.jsx";
import Learn from "./components/Learn.jsx";
import AddCard from "./components/AddCard.jsx";
import Inbox from "./components/Inbox.jsx";
import QuizMode from "./components/QuizMode.jsx";
import TestMode from "./components/TestMode.jsx";
import PracticeGame from "./components/PracticeGame.jsx";
import DepthToggle from "./components/DepthToggle.jsx";
import AuthControls from "./components/AuthControls.jsx";
import ClerkTokenBridge from "./components/ClerkTokenBridge.jsx";
import UpgradeModal from "./components/UpgradeModal.jsx";
import { hasClerk } from "./lib/clerk.js";

// Lazy-loaded heavy components (resource efficiency — not bundled into initial load).
const Analytics = lazy(() => import("./components/Analytics.jsx"));
const Badges = lazy(() => import("./components/Badges.jsx"));
const StudyGroups = lazy(() => import("./components/StudyGroups.jsx"));
const Scenarios = lazy(() => import("./components/Scenarios.jsx"));
const ImportExport = lazy(() => import("./components/ImportExport.jsx"));

const Fallback = () => <p className="muted small">Loading…</p>;

const TABS = [
  { id: "home", label: "Home" },
  { id: "learn", label: "Learn (AI)" },
  { id: "puzzles", label: "Puzzles" },
  { id: "review", label: "Flashcards" },
  { id: "quiz", label: "Quiz" },
  { id: "test", label: "Test" },
  { id: "game", label: "Practice Game" },
  { id: "analytics", label: "Analytics" },
  { id: "badges", label: "Badges" },
  { id: "groups", label: "Study Groups" },
  { id: "scenarios", label: "Scenarios" },
  { id: "import-export", label: "Import/Export" },
  { id: "add", label: "Add" },
  { id: "inbox", label: "Inbox" },
];

export default function App() {
  const [tab, setTab] = useState("home");
  const [online, setOnline] = useState(null);
  const [inboxCount, setInboxCount] = useState(0);
  const [stats, setStats] = useState({ points: 0, solved: 0, puzzles: 0 });
  const [limits, setLimits] = useState(null); // { pro, solves_remaining, daily_solve_limit }
  const [showUpgrade, setShowUpgrade] = useState(false);
  // Bumping this key remounts the active view so it refetches after a mutation.
  const [refresh, setRefresh] = useState(0);
  const bump = useCallback(() => setRefresh((r) => r + 1), []);
  const openUpgrade = useCallback(() => setShowUpgrade(true), []);
  // Depth level for command flashcards: shallow | medium | deep
  const [reviewDepth, setReviewDepth] = useState("medium");
  const [quizDepth, setQuizDepth] = useState("medium");
  const [testDepth, setTestDepth] = useState("medium");
  const [gameDepth, setGameDepth] = useState("medium");
  const [ccStats, setCCStats] = useState(null);

  useEffect(() => {
    api
      .health()
      .then((h) => {
        setOnline(true);
        setStats({ points: h.points, solved: h.solved, puzzles: h.puzzles });
      })
      .catch(() => setOnline(false));
    api.limits().then(setLimits).catch(() => {});
    api.ccStats().then(setCCStats).catch(() => {});
  }, [refresh]);

  useEffect(() => {
    api.listInbox("pending").then((x) => setInboxCount(x.length)).catch(() => {});
  }, [refresh]);

  return (
    <div className="app">
      {/* Signed-in session → per-account metering; also re-fetch quotas on sign in/out. */}
      {hasClerk && <ClerkTokenBridge onAuthChange={bump} />}
      <header>
        <div>
          <h1>CTF Flashcards</h1>
          <p className="muted small">Active-recall cybersecurity training · FSRS-scheduled</p>
        </div>
        <div className="header-right">
          {online && (
            <span className="points-chip" title={`${stats.solved}/${stats.puzzles} puzzles solved`}>
              🚩 {stats.points} pts
            </span>
          )}
          {limits &&
            (limits.pro ? (
              <span className="pro-chip" title="Pro — unlimited puzzle solves">★ Pro</span>
            ) : (
              <button className="free-chip" onClick={openUpgrade}
                title="Free tier — daily solve limit. Click to upgrade.">
                {limits.solves_remaining}/{limits.daily_solve_limit} free · Upgrade
              </button>
            ))}
          {hasClerk && <AuthControls />}
          {["quiz", "test", "game", "review"].includes(tab) && (
            <div className="depth-row">
              <DepthToggle
                value={tab === "review" ? reviewDepth : tab === "quiz" ? quizDepth : tab === "test" ? testDepth : gameDepth}
                onChange={v => {
                  if (tab === "review") setReviewDepth(v);
                  if (tab === "quiz") setQuizDepth(v);
                  if (tab === "test") setTestDepth(v);
                  if (tab === "game") setGameDepth(v);
                }}
              />
            </div>
          )}
          {ccStats && (
            <span className="cc-chip" title="Command cards">
              🃏 {ccStats.total} cards
            </span>
          )}
          <span className={`dot ${online === false ? "off" : online ? "on" : ""}`} title={online === false ? "backend offline" : "backend online"} />
        </div>
      </header>

      {online === false && (
        <div className="card warn">
          Can't reach the backend at <code>{import.meta.env.VITE_API_URL || "http://localhost:8000"}</code>.
          Start it with <code>uvicorn app.main:app --reload</code> in <code>backend/</code>.
        </div>
      )}

      <nav className="tabs">
        {TABS.map((t) => (
          <button
            key={t.id}
            className={tab === t.id ? "tab active" : "tab"}
            onClick={() => setTab(t.id)}
          >
            {t.label}
            {t.id === "inbox" && inboxCount > 0 && <span className="pill">{inboxCount}</span>}
          </button>
        ))}
      </nav>

      <main>
        {tab === "home" && <Home key={`h${refresh}`} go={setTab} limits={limits} openUpgrade={openUpgrade} />}
        {tab === "learn" && <Learn go={setTab} onGenerated={bump} limits={limits} openUpgrade={openUpgrade} />}
        {tab === "review" && <ReviewSession key={`r${refresh}`} depth={reviewDepth} setDepth={setReviewDepth} />}
        {/* stable key: solving refreshes header stats via onSolved without
            remounting (which would kick the user out of the solve view). */}
        {tab === "puzzles" && <Puzzles onSolved={bump} openUpgrade={openUpgrade} />}
        {tab === "quiz" && <QuizMode depth={quizDepth} />}
        {tab === "test" && <TestMode depth={testDepth} />}
        {tab === "game" && <PracticeGame depth={gameDepth} />}
        {tab === "analytics" && (
          <Suspense fallback={<Fallback />}>
            <Analytics />
          </Suspense>
        )}
        {tab === "badges" && (
          <Suspense fallback={<Fallback />}>
            <Badges />
          </Suspense>
        )}
        {tab === "groups" && (
          <Suspense fallback={<Fallback />}>
            <StudyGroups />
          </Suspense>
        )}
        {tab === "scenarios" && (
          <Suspense fallback={<Fallback />}>
            <Scenarios />
          </Suspense>
        )}
        {tab === "import-export" && (
          <Suspense fallback={<Fallback />}>
            <ImportExport />
          </Suspense>
        )}
        {tab === "add" && <AddCard key={`a${refresh}`} onAdded={bump} />}
        {tab === "inbox" && <Inbox key={`i${refresh}`} onApproved={bump} />}
      </main>

      <footer className="muted small">
        Free: {limits?.daily_solve_limit ?? 3} puzzle solves/day · Pro ($8/mo, USDC on Base) =
        unlimited. Billing runs through GRID Store.
      </footer>

      {showUpgrade && (
        <UpgradeModal
          onClose={() => setShowUpgrade(false)}
          onActivated={() => bump()}
        />
      )}
    </div>
  );
}
