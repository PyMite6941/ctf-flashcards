import { useEffect, useState, useCallback } from "react";
import { api } from "../lib/api.js";

// Quiz mode: multiple-choice questions about command cards.
// Generates distractors from other cards' content.
export default function QuizMode({ depth }) {
  const [cards, setCards] = useState([]);
  const [i, setI] = useState(0);
  const [score, setScore] = useState(0);
  const [selected, setSelected] = useState(null);
  const [showAnswer, setShowAnswer] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    api.ccListCards({ depth, limit: 50 })
      .then(setCards)
      .catch((e) => setError("Failed to load cards: " + e.message))
      .finally(() => setLoading(false));
  }, [depth]);

  const card = cards[i];

  const options = useCallback(() => {
    if (!card) return [];
    const correct = card.command;
    const others = cards
      .filter((c) => c.id !== card.id)
      .map((c) => c.command)
      .slice(0, 3);
    const pool = [correct, ...others];
    return pool.sort(() => Math.random() - 0.5);
  }, [card, cards]);

  const answerIndex = useCallback(() => {
    if (!card) return -1;
    return options().indexOf(card.command);
  }, [card, options]);

  async function pick(cmd) {
    if (showAnswer) return;
    setSelected(cmd);
    setShowAnswer(true);
    if (cmd === card.command) setScore((s) => s + 1);
    await api.ccReview(card.id, cmd === card.command);
  }

  function next() {
    setSelected(null);
    setShowAnswer(false);
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
    return (
      <div className="stack">
        <div className="card center">
          <h2>✅ Quiz complete</h2>
          <p className="muted">
            Score: {score} / {cards.length}
          </p>
          <button className="primary" onClick={() => window.location.reload()}>
            Try again
          </button>
        </div>
      </div>
    );
  }

  const opts = options();
  const correctIdx = answerIndex();

  return (
    <div className="stack">
      <div className="card">
        <div className="row between">
          <span className={`badge ${card.depth}`}>{card.depth}</span>
          <span className="muted small">{i + 1} / {cards.length}</span>
        </div>
        <h3 className="nomargin">Which command is this?</h3>
        <p className="muted small">{card.front}</p>
        <p className="muted small">Command hint: <code>{card.command.charAt(0)}…</code></p>
        <div className="quiz-options">
          {opts.map((opt, idx) => (
            <button
              key={idx}
              className={`quiz-opt ${showAnswer ? (idx === correctIdx ? "correct" : selected === opt ? "wrong" : "") : ""}`}
              onClick={() => pick(opt)}
              disabled={showAnswer}
            >
              {opt}
            </button>
          ))}
        </div>
        {showAnswer && selected !== card.command && (
          <p className="wrong-msg">
            ✗ Correct answer was: <strong>{card.command}</strong>
          </p>
        )}
        {showAnswer && selected === card.command && (
          <p className="muted small">✓ Correct!</p>
        )}
        <div className="row gap" style={{ marginTop: "16px" }}>
          <button className="primary" onClick={next} disabled={!showAnswer}>
            {showAnswer ? "Next" : "Select an answer"}
          </button>
          <button className="link" onClick={() => window.location.reload()}>
            New set
          </button>
        </div>
      </div>
    </div>
  );
}
