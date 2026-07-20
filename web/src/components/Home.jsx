import { useEffect, useState } from "react";
import { api } from "../lib/api.js";

// Landing / dashboard. Explains the loop and links out to the two things you
// actually do: solve challenges, and review the cards they unlock.
export default function Home({ go, limits, openUpgrade }) {
  const [dueCount, setDueCount] = useState(null);
  const [totalCards, setTotalCards] = useState(null);
  const [stats, setStats] = useState({ points: 0, solved: 0, puzzles: 0 });

  useEffect(() => {
    api.health().then((h) => setStats(h)).catch(() => {});
    api.reviewQueue(500).then((q) => setDueCount(q.length)).catch(() => {});
    api.listCards().then((c) => setTotalCards(c.length)).catch(() => {});
  }, []);

  const tiles = [
    { label: "points", value: stats.points, icon: "🚩" },
    { label: "puzzles solved", value: `${stats.solved}/${stats.puzzles}`, icon: "🧩" },
    { label: "cards due now", value: dueCount ?? "…", icon: "⏰" },
    { label: "cards in deck", value: totalCards ?? "…", icon: "🗂️" },
  ];

  return (
    <div className="stack">
      <div className="card hero">
        <h2 className="nomargin">Learn cybersecurity by doing.</h2>
        <p className="muted">
          Solve HackTheBox-style CTF challenges. Each one you capture unlocks the
          concepts behind it as spaced-repetition flashcards — so what you learn in
          the puzzle actually sticks. The puzzles fuel the questions.
        </p>
        <div className="row gap wrap">
          <button className="primary grow" onClick={() => go("learn")}>
            ✨ Learn a topic (AI)
          </button>
          <button className="grow" onClick={() => go("puzzles")}>
            🧩 Solve a challenge
          </button>
          <button className="grow" onClick={() => go("review")}>
            🗂️ Review{dueCount ? ` (${dueCount} due)` : ""}
          </button>
        </div>
      </div>

      <div className="tiles">
        {tiles.map((t) => (
          <div className="tile" key={t.label}>
            <span className="tile-icon">{t.icon}</span>
            <strong className="tile-value">{t.value}</strong>
            <span className="muted small">{t.label}</span>
          </div>
        ))}
      </div>

      {limits && !limits.pro && (
        <div className="card upgrade-card">
          <div>
            <strong>Free tier</strong>
            <p className="muted small nomargin">
              {limits.solves_remaining}/{limits.daily_solve_limit} puzzle solves left today.
              Go Pro for unlimited — $8/mo (USDC on Base), billed through GRID Store.
            </p>
          </div>
          <button className="primary" onClick={openUpgrade}>★ Upgrade to Pro</button>
        </div>
      )}
      {limits?.pro && (
        <div className="card upgrade-card">
          <div>
            <strong>★ Pro active</strong>
            <p className="muted small nomargin">Unlimited puzzle solves. Thanks for supporting the project!</p>
          </div>
        </div>
      )}

      <div className="card">
        <h3 className="nomargin">How it works</h3>
        <ol className="steps">
          <li><strong>Solve</strong> a CTF puzzle — decode, crack, or spot the bug.</li>
          <li><strong>Capture the flag</strong> to unlock that puzzle's concept cards.</li>
          <li><strong>Recall</strong> them over time: type the answer from memory, then rate yourself.</li>
          <li><strong>FSRS</strong> reschedules each card for the moment you're about to forget it.</li>
        </ol>
        <p className="muted small nomargin">
          You can also add your own cards, or let the local monitor turn real
          security events into review candidates (Inbox tab).
        </p>
      </div>
    </div>
  );
}
