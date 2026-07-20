import { useEffect, useState } from "react";
import { api, DIFFICULTY_COLOR } from "../lib/api.js";

// HackTheBox-style challenge board. Pick a puzzle, work the artifact, submit the
// flag. A correct flag unlocks the puzzle's concept cards straight into the
// review deck — the puzzles fuel the flashcards.
export default function Puzzles({ onSolved, openUpgrade }) {
  const [data, setData] = useState(null);
  const [filters, setFilters] = useState({ category: "", difficulty: "", status: "" });
  const [selected, setSelected] = useState(null);
  const [limits, setLimits] = useState(null);

  async function load() {
    setData(await api.listPuzzles(filters));
    api.limits().then(setLimits).catch(() => {});
  }
  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters]);

  if (selected) {
    return (
      <PuzzleSolve
        id={selected}
        openUpgrade={openUpgrade}
        onBack={() => setSelected(null)}
        onSolved={() => {
          load();
          onSolved?.();
        }}
      />
    );
  }

  if (!data) return <p className="muted">Loading challenges…</p>;

  return (
    <div className="stack">
      <div className="card score">
        <div>
          <strong className="big">{data.points}</strong> <span className="muted">pts</span>
        </div>
        <div className="col-right">
          <span className="muted small">{data.solved} / {data.total} solved</span>
          {limits && !limits.pro && (
            <button className="free-chip" onClick={openUpgrade}>
              {limits.solves_remaining}/{limits.daily_solve_limit} free solves today · Go Pro
            </button>
          )}
          {limits?.pro && <span className="pro-chip">★ Pro · unlimited</span>}
        </div>
      </div>

      <div className="filters">
        <select
          value={filters.category}
          onChange={(e) => setFilters({ ...filters, category: e.target.value })}
        >
          <option value="">All categories</option>
          {data.categories.map((c) => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>
        <select
          value={filters.difficulty}
          onChange={(e) => setFilters({ ...filters, difficulty: e.target.value })}
        >
          <option value="">Any difficulty</option>
          <option value="easy">easy</option>
          <option value="medium">medium</option>
          <option value="hard">hard</option>
        </select>
        <select
          value={filters.status}
          onChange={(e) => setFilters({ ...filters, status: e.target.value })}
        >
          <option value="">All</option>
          <option value="unsolved">Unsolved</option>
          <option value="solved">Solved</option>
        </select>
      </div>

      {data.puzzles.length === 0 && <p className="muted">No challenges match those filters.</p>}

      {data.puzzles.map((p) => (
        <button className="card puzzle" key={p.id} onClick={() => setSelected(p.id)}>
          <div className="row between">
            <span className={`badge cat-${p.category}`}>{p.category}</span>
            <span className="muted small">{p.points} pts</span>
          </div>
          <div className="row between">
            <strong>{p.title}</strong>
            {p.solved && <span className="solved-tag">✓ solved</span>}
          </div>
          <p className="muted small nomargin">{p.description}</p>
          <div className="row between">
            <span className="diff" style={{ color: DIFFICULTY_COLOR[p.difficulty] }}>
              ● {p.difficulty}
            </span>
            <span className="muted small">unlocks {p.card_count} card{p.card_count === 1 ? "" : "s"}</span>
          </div>
        </button>
      ))}
    </div>
  );
}

function PuzzleSolve({ id, onBack, onSolved, openUpgrade }) {
  const [p, setP] = useState(null);
  const [flag, setFlag] = useState("");
  const [showHint, setShowHint] = useState(false);
  const [result, setResult] = useState(null); // {correct, ...} or {wrong:true} or {limit:true}
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.getPuzzle(id).then(setP);
  }, [id]);

  async function submit(e) {
    e.preventDefault();
    if (!flag.trim()) return;
    setBusy(true);
    try {
      const r = await api.submitFlag(id, flag.trim());
      if (r.correct) {
        setResult(r);
        onSolved?.();
        setP(await api.getPuzzle(id)); // refresh to reveal solution/solved state
      } else {
        setResult({ wrong: true });
      }
    } catch (err) {
      if (err.status === 402) {
        // Free daily solve limit hit — the flag was right, just gated.
        setResult({ limit: true, message: err.body?.detail?.message });
        openUpgrade?.();
      } else {
        setResult({ wrong: true, message: "Something went wrong — try again." });
      }
    } finally {
      setBusy(false);
    }
  }

  if (!p) return <p className="muted">Loading…</p>;

  return (
    <div className="stack">
      <button className="link" onClick={onBack}>← back to challenges</button>

      <div className="card">
        <div className="row between">
          <span className={`badge cat-${p.category}`}>{p.category}</span>
          <span className="diff" style={{ color: DIFFICULTY_COLOR[p.difficulty] }}>
            ● {p.difficulty} · {p.points} pts
          </span>
        </div>
        <h2 className="nomargin">{p.title}</h2>
        <p>{p.description}</p>

        <span className="muted small">artifact</span>
        <pre className="artifact">{p.artifact}</pre>

        {!showHint ? (
          <button className="link" onClick={() => setShowHint(true)}>Need a hint?</button>
        ) : (
          <p className="hint-box">💡 {p.hint}</p>
        )}

        {p.solved && result?.correct ? (
          <div className="success">
            <h3 className="nomargin">🚩 Flag captured! +{result.points} pts</h3>
            <p className="muted small">{p.solution}</p>
            {result.added_cards.length > 0 ? (
              <p className="small">
                Unlocked <strong>{result.added_cards.length}</strong> new review card
                {result.added_cards.length === 1 ? "" : "s"} → check the Review tab.
              </p>
            ) : (
              <p className="muted small">Cards already in your deck.</p>
            )}
          </div>
        ) : p.solved ? (
          <div className="success">
            <h3 className="nomargin">✓ Already solved</h3>
            <p className="muted small">{p.solution}</p>
          </div>
        ) : (
          <form onSubmit={submit}>
            <label>
              Submit flag
              <input
                autoFocus
                placeholder="ctf{...}"
                value={flag}
                onChange={(e) => setFlag(e.target.value)}
                className={result?.wrong ? "shake" : ""}
              />
            </label>
            {result?.wrong && <p className="wrong-msg">✗ {result.message || "Not quite — try again."}</p>}
            {result?.limit && (
              <div className="hint-box small">
                🔒 {result.message || "Daily free solve limit reached."}{" "}
                <button className="link inline" type="button" onClick={openUpgrade}>Upgrade to Pro →</button>
              </div>
            )}
            <button className="primary" disabled={busy}>
              {busy ? "Checking…" : "Capture flag"}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
