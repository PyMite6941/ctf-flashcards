import { useCallback, useEffect, useState } from "react";
import { api } from "./lib/api.js";
import Home from "./components/Home.jsx";
import ReviewSession from "./components/ReviewSession.jsx";
import Puzzles from "./components/Puzzles.jsx";
import AddCard from "./components/AddCard.jsx";
import Inbox from "./components/Inbox.jsx";
import AuthControls from "./components/AuthControls.jsx";
import UpgradeModal from "./components/UpgradeModal.jsx";
import { hasClerk } from "./lib/clerk.js";

const TABS = [
  { id: "home", label: "Home" },
  { id: "puzzles", label: "Puzzles" },
  { id: "review", label: "Flashcards" },
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

  useEffect(() => {
    api
      .health()
      .then((h) => {
        setOnline(true);
        setStats({ points: h.points, solved: h.solved, puzzles: h.puzzles });
      })
      .catch(() => setOnline(false));
    api.limits().then(setLimits).catch(() => {});
  }, [refresh]);

  useEffect(() => {
    api.listInbox("pending").then((x) => setInboxCount(x.length)).catch(() => {});
  }, [refresh]);

  return (
    <div className="app">
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
          <span className={`dot ${online === false ? "off" : online ? "on" : ""}`}
            title={online === false ? "backend offline" : "backend online"} />
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
        {tab === "review" && <ReviewSession key={`r${refresh}`} />}
        {/* stable key: solving refreshes header stats via onSolved without
            remounting (which would kick the user out of the solve view). */}
        {tab === "puzzles" && <Puzzles onSolved={bump} openUpgrade={openUpgrade} />}
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
