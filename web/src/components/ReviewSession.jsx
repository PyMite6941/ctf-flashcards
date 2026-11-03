import { useEffect, useState } from "react";
import { api, RATINGS } from "../lib/api.js";

// The heart of the app: real active recall.
// 1. Show the prompt. 2. User types their answer BEFORE revealing (free recall,
//    not multiple choice). 3. Reveal the correct answer. 4. User self-rates,
//    which feeds FSRS to schedule the next appearance.
export default function ReviewSession({ depth = "" }) {
  const [queue, setQueue] = useState([]);
  const [loading, setLoading] = useState(true);
  const [i, setI] = useState(0);
  const [attempt, setAttempt] = useState("");
  const [revealed, setRevealed] = useState(false);
  const [done, setDone] = useState(0);
  const [topics, setTopics] = useState([]);
  const [topic, setTopic] = useState(""); // "" = all topics

  async function load(tag = topic) {
    setLoading(true);
    try {
      setQueue(await api.reviewQueue(50, tag || null));
      setI(0);
      setAttempt("");
      setRevealed(false);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    api.topics().then(setTopics).catch(() => {});
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function changeTopic(tag) {
    setTopic(tag);
    setDone(0);
    load(tag);
  }

  const card = queue[i];

  async function rate(rating) {
    await api.submitReview(card.id, rating);
    setDone((d) => d + 1);
    if (i + 1 < queue.length) {
      setI(i + 1);
      setAttempt("");
      setRevealed(false);
    } else {
      setQueue([]); // session cleared
    }
  }

  const topicBar = (
    <div className="filters">
      <select value={topic} onChange={(e) => changeTopic(e.target.value)}>
        <option value="">All topics</option>
        {topics.map((t) => (
          <option key={t.tag} value={t.tag}>
            {t.tag} ({t.due} due)
          </option>
        ))}
      </select>
    </div>
  );

  if (loading)
    return (
      <div className="stack">
        {topicBar}
        <p className="muted">Loading your due cards…</p>
      </div>
    );

  if (!card) {
    return (
      <div className="stack">
        {topicBar}
        <div className="card center">
          <h2>✅ All caught up</h2>
          <p className="muted">
            {done > 0
              ? `You reviewed ${done} card${done === 1 ? "" : "s"} this session.`
              : topic
              ? `Nothing due in "${topic}" right now. Try another topic or come back later.`
              : "Nothing is due right now. Come back when FSRS schedules more, or add cards."}
          </p>
          <button onClick={() => load()}>Check again</button>
        </div>
      </div>
    );
  }

  return (
    <div className="stack">
      {topicBar}
      <div className="card">
      <div className="row between">
        <span className={`badge ${card.kind}`}>{card.kind}</span>
        <span className="muted small">
          {i + 1} / {queue.length} · deck: {card.deck}
        </span>
      </div>

      <p className="prompt">{card.front}</p>

      {!revealed ? (
        <>
          <textarea
            autoFocus
            placeholder="Type your answer from memory first…"
            value={attempt}
            onChange={(e) => setAttempt(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) setRevealed(true);
            }}
          />
          <button className="primary" onClick={() => setRevealed(true)}>
            Reveal answer (Ctrl/⌘+Enter)
          </button>
        </>
      ) : (
        <>
          {attempt && (
            <div className="your-answer">
              <span className="muted small">your recall</span>
              <p>{attempt}</p>
            </div>
          )}
          <div className="answer">
            <span className="muted small">correct answer</span>
            <p>{card.back}</p>
          </div>
          <p className="muted small">How well did you recall it?</p>
          <div className="rating-row">
            {RATINGS.map((r) => (
              <button
                key={r.value}
                className="rating"
                style={{ borderColor: r.color, color: r.color }}
                onClick={() => rate(r.value)}
              >
                <strong>{r.label}</strong>
                <span className="hint">{r.hint}</span>
              </button>
            ))}
          </div>
        </>
      )}
      </div>
    </div>
  );
}
