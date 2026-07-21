import { useEffect, useState } from "react";
import { api, DIFFICULTY_COLOR } from "../lib/api.js";

// AI tutor: name a topic → Groq generates flashcards (into the deck) + practice
// challenges (locked until you've reviewed the flashcards) + a downloadable lab.
export default function Learn({ go, onGenerated, limits, openUpgrade }) {
  const [topic, setTopic] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [packs, setPacks] = useState(null);
  const [selected, setSelected] = useState(null);

  const pro = limits?.pro;
  const gensLeft = limits?.ai_gens_remaining;
  const outOfGens = !pro && gensLeft === 0;

  async function load() {
    setPacks(await api.listPacks());
  }
  useEffect(() => {
    load();
  }, []);

  async function generate(e) {
    e.preventDefault();
    if (!topic.trim()) return;
    setBusy(true);
    setError("");
    try {
      const r = await api.generatePack(topic.trim());
      setTopic("");
      await load();
      setSelected(r.topic_slug);
      onGenerated?.();
    } catch (err) {
      if (err.status === 402) {
        setError(err.body?.detail?.message || "Monthly AI limit reached — upgrade to Pro for unlimited.");
        openUpgrade?.();
      } else {
        setError(err.body?.error || err.message || "Generation failed.");
      }
    } finally {
      setBusy(false);
    }
  }

  if (selected) {
    return <PackDetail slug={selected} go={go} onBack={() => { setSelected(null); load(); }} onSolved={onGenerated} />;
  }

  return (
    <div className="stack">
      <form className="card" onSubmit={generate}>
        <h2 className="nomargin">Learn a topic with AI</h2>
        <p className="muted small nomargin">
          Name any cybersecurity topic. AI writes flashcards for it, then builds
          practice challenges that unlock once you've reviewed the cards.
        </p>
        <div className="row gap wrap">
          <input
            className="grow"
            placeholder="e.g. SQL injection, JWT attacks, buffer overflows, XSS…"
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            disabled={busy || outOfGens}
          />
          <button className="primary" disabled={busy || outOfGens || !topic.trim()}>
            {busy ? "Generating…" : "✨ Generate"}
          </button>
        </div>
        {limits && (
          pro ? (
            <span className="pro-chip" style={{ alignSelf: "flex-start" }}>★ Pro · unlimited AI</span>
          ) : outOfGens ? (
            <button className="free-chip" onClick={openUpgrade}>
              Monthly AI limit reached ({limits.ai_gens_limit}/mo) · Upgrade to Pro
            </button>
          ) : (
            <span className="muted small">{gensLeft}/{limits.ai_gens_limit} free AI generations left this month</span>
          )
        )}
        {busy && <p className="muted small">Asking the model for flashcards + challenges… (a few seconds)</p>}
        {error && <p className="wrong-msg">{error}</p>}
      </form>

      {packs && packs.length > 0 && (
        <>
          <p className="muted small nomargin">Your topics</p>
          {packs.map((p) => (
            <button className="card puzzle" key={p.topic_slug} onClick={() => setSelected(p.topic_slug)}>
              <div className="row between">
                <strong>{p.topic}</strong>
                <span className="muted small">{p.challenge_count} challenge{p.challenge_count === 1 ? "" : "s"}</span>
              </div>
              <ProgressBar prog={p.progress} />
            </button>
          ))}
        </>
      )}
      {packs && packs.length === 0 && !busy && (
        <p className="muted small">No topics yet — generate your first one above.</p>
      )}
    </div>
  );
}

function ProgressBar({ prog }) {
  const pct = prog.total ? Math.round((prog.reviewed / prog.total) * 100) : 0;
  return (
    <div className="progress-wrap">
      <div className="progress-track"><div className="progress-fill" style={{ width: `${pct}%` }} /></div>
      <span className="muted small">
        {prog.done ? "✓ flashcards done — practice unlocked" : `${prog.reviewed}/${prog.total} flashcards reviewed`}
      </span>
    </div>
  );
}

function PackDetail({ slug, go, onBack, onSolved }) {
  const [pack, setPack] = useState(null);

  async function load() {
    setPack(await api.getPack(slug));
  }
  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [slug]);

  if (!pack) return <p className="muted">Loading…</p>;

  return (
    <div className="stack">
      <button className="link" onClick={onBack}>← all topics</button>
      <div className="card">
        <h2 className="nomargin">{pack.topic}</h2>
        <ProgressBar prog={pack.progress} />
        {!pack.unlocked ? (
          <button className="primary" onClick={() => go?.("review")}>
            Review the {pack.progress.total} flashcards →
          </button>
        ) : (
          <p className="muted small nomargin">✓ Flashcards done. Prove it below.</p>
        )}
        <a className="link" href={api.labkitUrl(slug)} target="_blank" rel="noopener noreferrer" download>
          ⬇ Download lab kit (practice in your own environment)
        </a>
      </div>

      <p className="muted small nomargin">Practice challenges</p>
      {pack.challenges.length === 0 && <p className="muted small">No challenges were generated for this topic.</p>}
      {pack.challenges.map((c) => (
        <GenChallenge key={c.id} c={c} locked={!pack.unlocked} onSolved={() => { load(); onSolved?.(); }} />
      ))}
    </div>
  );
}

function GenChallenge({ c, locked, onSolved }) {
  const [flag, setFlag] = useState("");
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    if (!flag.trim()) return;
    setBusy(true);
    try {
      const r = await api.submitGenFlag(c.id, flag.trim());
      if (r.correct) { setResult({ ok: true, solution: r.solution, points: r.points }); onSolved?.(); }
      else setResult({ wrong: true });
    } catch (err) {
      setResult({ wrong: true, message: err.status === 423 ? "Finish the flashcards first." : "Try again." });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card">
      <div className="row between">
        <span className="badge cat-ai">{c.challenge_type}</span>
        <span className="diff" style={{ color: DIFFICULTY_COLOR[c.difficulty] }}>● {c.difficulty} · {c.points} pts</span>
      </div>
      <strong>{c.title}</strong>
      <p className="muted small nomargin">{c.description}</p>
      <pre className="artifact">{c.artifact}</pre>

      {c.solved || result?.ok ? (
        <div className="success">
          <strong>🚩 Solved{result?.points ? ` · +${result.points} pts` : ""}</strong>
          {(result?.solution || c.solution) && <p className="muted small nomargin">{result?.solution || c.solution}</p>}
        </div>
      ) : locked ? (
        <p className="hint-box small">🔒 Locked — review this topic's flashcards to unlock.</p>
      ) : (
        <form onSubmit={submit}>
          {c.hint && <p className="muted small">💡 {c.hint}</p>}
          <div className="row gap">
            <input className={result?.wrong ? "grow shake" : "grow"} placeholder="ctf{...}"
              value={flag} onChange={(e) => setFlag(e.target.value)} />
            <button className="primary" disabled={busy}>{busy ? "…" : "Submit"}</button>
          </div>
          {result?.wrong && <p className="wrong-msg">✗ {result.message || "Not quite."}</p>}
        </form>
      )}
    </div>
  );
}
