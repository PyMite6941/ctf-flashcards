import { useEffect, useState } from "react";
import { api } from "../lib/api.js";

// Command chaining scenarios — multi-step challenges (pipes, redirects, etc.).
// Learner runs commands and we check against expected patterns.
export default function Scenarios() {
  const [scenarios, setScenarios] = useState([]);
  const [selected, setSelected] = useState(null);
  const [attemptId, setAttemptId] = useState(null);
  const [commands, setCommands] = useState("");
  const [result, setResult] = useState(null); // 'success' | 'fail' | null
  const [history, setHistory] = useState([]);

  useEffect(() => {
    api.scenarioList().then(setScenarios).catch(() => {});
  }, []);

  const scenario = scenarios.find((s) => s.id === selected);

  async function startAttempt() {
    if (!selected) return;
    const a = await api.scenarioAttemptStart(selected);
    setAttemptId(a.attempt_id);
    setCommands("");
    setResult(null);
    setHistory([]);
  }

  async function runCommand() {
    if (!attemptId) return;
    const cmdLine = commands.trim();
    if (!cmdLine) return;
    setHistory([...history, cmdLine]);
    setResult(null);
    await api.scenarioAttemptRecord(attemptId, [...history, cmdLine]);
    // Check completion: client-side heuristic — if user typed something containing
    // the expected pattern fragment (simple substring match), mark success.
    const patterns = (scenario?.expected_patterns || []).filter(Boolean);
    const joined = history.join(" ");
    const matched = patterns.some((p) => joined.includes(p));
    if (matched && patterns.length > 0) {
      await api.scenarioAttemptRecord(attemptId, [...history, cmdLine], true);
      setResult("success");
    }
  }

  return (
    <div className="stack">
      <div className="card">
        <h2 className="nomargin">🧩 Command Chaining Scenarios</h2>
        <p className="muted small nomargin">
          Practice multi-step terminal scenarios (pipes, redirects, grep, etc.).
          Run commands in order to meet the objective.
        </p>
        <div className="row gap wrap" style={{ marginBottom: "16px" }}>
          <select className="grow" onChange={(e) => setSelected(e.target.value)}>
            <option value="">Select a scenario…</option>
            {scenarios.map((s) => (
              <option key={s.id} value={s.id}>
                {s.title} ({s.difficulty})
              </option>
            ))}
          </select>
          <button className="primary" onClick={startAttempt} disabled={!selected || attemptId}>
            Start scenario
          </button>
        </div>
      </div>

      {selected && scenario && (
        <div className="card">
          <div className="row between">
            <h3 className="nomargin">{scenario.title}</h3>
            <span className={`badge ${scenario.difficulty}`}>{scenario.difficulty}</span>
          </div>
          <p>{scenario.description}</p>
          <div className="muted small">🎯 Objective: {scenario.objective}</div>
          {scenario.hints && scenario.hints.length > 0 && (
            <details className="hint-box" style={{ marginTop: "8px" }}>
              <summary>💡 Show hint</summary>
              <p className="muted small">{scenario.hints[0]}</p>
            </details>
          )}
          <div style={{ marginTop: "16px" }}>
            <h4 className="nomargin">Terminal</h4>
            <div className="game-prompt">
              {history.map((c, i) => (
                <div key={i} className="term-line">
                  <span className="prompt">$</span> {c}
                </div>
              ))}
              {result === null && (
                <div className="term-line">
                  <span className="prompt">$</span>
                  <input
                    autoFocus
                    value={commands}
                    onChange={(e) => setCommands(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && runCommand()}
                    placeholder="type a command…"
                    className="grow"
                  />
                </div>
              )}
              {result === "success" && (
                <div className="term-line success">
                  <span className="prompt">✓</span> Scenario complete!
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
