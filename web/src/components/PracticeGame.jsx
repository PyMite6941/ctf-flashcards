import { useEffect, useState, useCallback } from "react";
import { api } from "../lib/api.js";

// Practice game: type the command as fast and accurately as possible.
// Scores speed + accuracy, streaks for consecutive correct answers.
export default function PracticeGame({ depth }) {
  const [cards, setCards] = useState([]);
  const [i, setI] = useState(0);
  const [input, setInput] = useState("");
  const [score, setScore] = useState(0);
  const [streak, setStreak] = useState(0);
  const [result, setResult] = useState(null); // 'correct' | 'wrong'
  const [startTime, setStartTime] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    api.ccListCards({ depth, limit: 40 })
      .then(setCards)
      .catch((e) => setError("Failed to load cards: " + e.message))
      .finally(() => setLoading(false));
  }, [depth]);

  const card = cards[i];

  const elapsed = useCallback(() => {
    if (!startTime) return 0;
    return (Date.now() - startTime) / 1000;
  }, [startTime]);

  useEffect(() => {
    if (card && !startTime) setStartTime(Date.now());
  }, [card, startTime]);

  async function submit() {
    if (result) return;
    const trimmed = input.trim();
    if (!trimmed) return;
    const correct = trimmed === card.command;
    setResult(correct ? "correct" : "wrong");
    if (correct) {
      setScore((s) => s + 1);
      setStreak((s) => s + 1);
    } else {
      setStreak(0);
    }
    await api.ccReview(card.id, correct);
  }

  function next() {
    setInput("");
    setResult(null);
    setStartTime(0);
    setI((i) => i + 1);
  }

  if (loading)
    return <div className="stack"><p className="muted">Loading commands…</p></div>;

  if (error)
    return (
      <div className="stack">
        <p className="wrong-msg">{error}</p>
        <button className="primary" onClick={() => window.location.reload()}>
          Retry
        </button>
      </div>
    );

  if (!card || i >= cards.length) {
    const avg = score > 0 ? (elapsed() / score).toFixed(2) : 0;
    return (
      <div className="stack">
        <div className="card center">
          <h2>🎯 Game over</h2>
          <p className="muted">
            Score: {score} / {cards.length} &nbsp;•&nbsp; Streak: {streak}
          </p>
          <p className="muted small">
            Avg time per command: {avg}s
          </p>
          <button className="primary" onClick={() => window.location.reload()}>
            Play again
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="stack">
      <div className="card">
        <div className="row between">
          <span className={`badge ${card.depth}`}>{card.depth}</span>
          <span className="muted small">{i + 1} / {cards.length}</span>
        </div>
        <div className="row between">
          <span className="muted small">Score: {score}</span>
          <span className="muted small">Streak: {streak} 🔥</span>
          <span className="muted small">⏱ {elapsed().toFixed(1)}s</span>
        </div>
        <h3 className="nomargin">Type this command:</h3>
        <div className="game-prompt">
          <code>{card.front}</code>
        </div>
        <input
          autoFocus
          value={input}
          onChange={(e) => setInput(e.target.value)}
          className={`grow game-input ${result}`}
          placeholder="Type the command…"
          disabled={result}
          onKeyDown={(e) => {
            if (e.key === "Enter") submit();
          }}
        />
        {result === "correct" && <p className="muted small">✓ Correct!</p>}
        {result === "wrong" && (
          <p className="wrong-msg">
            ✗ Expected: <code>{card.command}</code>
          </p>
        )}
        <div className="row gap" style={{ marginTop: "16px" }}>
          <button className="primary" onClick={next} disabled={!result}>
            {result ? "Next" : "Type and press Enter"}
          </button>
          <button className="link" onClick={() => window.location.reload()}>
            New set
          </button>
        </div>
      </div>
    </div>
  );
}
