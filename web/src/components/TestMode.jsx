import { useEffect, useState, useCallback } from "react";
import { api } from "../lib/api.js";

// Test mode: timed recall. User types the command or answer.
// Shows front, user types, we check against the command/back.
export default function TestMode({ depth, timeLimit = 60 }) {
  const [cards, setCards] = useState([]);
  const [i, setI] = useState(0);
  const [answer, setAnswer] = useState("");
  const [score, setScore] = useState(0);
  const [timeLeft, setTimeLeft] = useState(timeLimit);
  const [result, setResult] = useState(null); // 'correct' | 'wrong' | null
  const [showAnswer, setShowAnswer] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [timerId, setTimerId] = useState(null);

  useEffect(() => {
    api.ccListCards({ depth, limit: 30 })
      .then(setCards)
      .catch((e) => setError("Failed to load cards: " + e.message))
      .finally(() => setLoading(false));
  }, [depth]);

  useEffect(() => {
    if (timeLeft > 0 && i < cards.length && !showAnswer) {
      const id = setInterval(() => setTimeLeft((t) => t - 1), 1000);
      setTimerId(id);
      return () => clearInterval(id);
    }
    return () => {};
  }, [timeLeft, i, showAnswer, cards.length]);

  const card = cards[i];

  useEffect(() => {
    if (timeLeft === 0) {
      setShowAnswer(true);
    }
  }, [timeLeft]);

  async function submit() {
    if (showAnswer) return;
    const trimmed = answer.trim();
    if (!trimmed) return;
    const correct = trimmed === card.command || trimmed === card.front;
    setResult(correct ? "correct" : "wrong");
    setShowAnswer(true);
    if (correct) setScore((s) => s + 1);
    await api.ccReview(card.id, correct);
  }

  function next() {
    setAnswer("");
    setResult(null);
    setShowAnswer(false);
    setTimeLeft(timeLimit);
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

  if (!card || i >= cards.length || timeLeft === 0) {
    return (
      <div className="stack">
        <div className="card center">
          <h2>✅ Test complete</h2>
          <p className="muted">
            Score: {score} / {Math.min(i, cards.length)}
            {timeLeft === 0 ? " — time ran out" : ""}
          </p>
          <button className="primary" onClick={() => window.location.reload()}>
            Try again
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
          <span className="muted small">⏱ {timeLeft}s</span>
        </div>
        <div className="row between">
          <span className="muted small">{i + 1} / {cards.length}</span>
          <span className="muted small">Score: {score}</span>
        </div>
        <h3 className="nomargin">Type the command</h3>
        <p className="muted small">{card.front}</p>
        <input
          autoFocus
          value={answer}
          onChange={(e) => setAnswer(e.target.value)}
          className={`grow ${result}`}
          placeholder="e.g. nmap -sS target"
          disabled={showAnswer}
        />
        {result === "correct" && (
          <p className="muted small">✓ Correct!</p>
        )}
        {result === "wrong" && (
          <p className="wrong-msg">
            ✗ Incorrect. Expected: <code>{card.command}</code>
          </p>
        )}
        <div className="row gap" style={{ marginTop: "16px" }}>
          <button className="primary" onClick={submit} disabled={showAnswer || !answer.trim()}>
            {showAnswer ? "Next" : "Submit"}
          </button>
          <button className="link" onClick={() => window.location.reload()}>
            New set
          </button>
        </div>
      </div>
    </div>
  );
}
