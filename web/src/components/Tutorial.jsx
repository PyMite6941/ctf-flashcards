import { useState, useEffect } from "react";
import { api } from "../lib/api.js";

// Interactive onboarding tutorial. Walks a new user through:
// capture → add to deck → review → quiz → badges.
// Progress is stored in localStorage so it only shows once (unless reset).
export default function Tutorial({ onComplete }) {
  const [step, setStep] = useState(0);
  const [cards, setCards] = useState([]);
  const [loading, setLoading] = useState(false);
  const [skipped, setSkipped] = useState(false);

  const TOTAL = 5;

  const steps = [
    {
      title: "Welcome to CTF Flashcards 👋",
      body:
        "Learn cybersecurity commands by capturing what you type in the terminal, "
        + "then reviewing them like flashcards. Let's set it up in 5 quick steps.",
      action: null,
    },
    {
      title: "Step 1 — Capture a command",
      body:
        "Anything you type in your terminal (bash/zsh) gets logged automatically "
        + "when you source shell_integration.sh. Failed commands prompt you to add them.",
      action: "Try it: type a command in your terminal, then come back here.",
      cta: "I've captured a command",
      check: () => api.ccStats().then((s) => (s.total || 0) > 0),
    },
    {
      title: "Step 2 — Add to your study deck",
      body:
        "Captured commands live in the pending list until you add them as flashcards. "
        + "Choose how in-depth you want each card: shallow (one-liner), medium, or deep.",
      action: "Go to the Pending tab and add a command to your deck.",
      cta: "I've added a card",
      check: () => api.ccListCards({ due_only: true }).then((c) => c.length > 0),
    },
    {
      title: "Step 3 — Review like flashcards",
      body:
        "Review cards with free recall: type your answer, reveal, then rate yourself "
        + "Again / Hard / Good / Easy. FSRS schedules when you'll see it again.",
      action: "Go to Flashcards and review one card.",
      cta: "I've reviewed a card",
      check: () => true, // user self-confirms
    },
    {
      title: "Step 4 — Quiz yourself",
      body:
        "Test recognition with multiple-choice quizzes, or speed with the Practice Game. "
        + "Earn badges for streaks and perfect scores.",
      action: "Try the Quiz or Practice Game tab.",
      cta: "I've taken a quiz",
      check: () => true, // user self-confirms
    },
    {
      title: "You're all set! 🎉",
      body:
        "Keep capturing commands in your terminal and reviewing them daily. "
        + "Visit Analytics to see your progress heatmap and Badges for achievements.",
      action: null,
      cta: "Finish setup",
      check: () => true,
    },
  ];

  useEffect(() => {
    // Mark tutorial as seen in localStorage once completed
    if (step === TOTAL - 1) {
      try {
        localStorage.setItem("ctf_tutorial_seen", "1");
      } catch { /* ignore */ }
    }
  }, [step]);

  async function handleCheck() {
    const s = steps[step];
    if (!s.check) {
      setStep((s2) => Math.min(s2 + 1, TOTAL - 1));
      return;
    }
    setLoading(true);
    try {
      const ok = await s.check();
      if (ok) {
        setStep((s2) => Math.min(s2 + 1, TOTAL - 1));
      } else {
        alert("Not quite yet — complete the action above, then click again.");
      }
    } catch {
      // If we can't verify (e.g. backend down), let user proceed manually
      setStep((s2) => Math.min(s2 + 1, TOTAL - 1));
    } finally {
      setLoading(false);
    }
  }

  function skip() {
    setSkipped(true);
    try { localStorage.setItem("ctf_tutorial_seen", "1"); } catch { /* ignore */ }
    onComplete?.();
  }

  const s = steps[step];
  const progress = Math.round(((step + 1) / TOTAL) * 100);

  return (
    <div className="tutorial-overlay">
      <div className="tutorial-card">
        <div className="tutorial-header">
          <div className="tutorial-progress">
            <div className="tutorial-progress-bar">
              <div className="tutorial-progress-fill" style={{ width: `${progress}%` }} />
            </div>
            <span className="tutorial-progress-text">{step + 1} / {TOTAL}</span>
          </div>
          {!skipped && <button className="tutorial-skip" onClick={skip}>Skip tutorial</button>}
        </div>

        <div className="tutorial-body">
          <h2>{s.title}</h2>
          <p className="tutorial-text">{s.body}</p>
          {s.action && (
            <div className="tutorial-tip">
              <strong>💡 Tip:</strong> {s.action}
            </div>
          )}
        </div>

        <div className="tutorial-actions">
          {skipped ? null : (
            <>
              {step > 0 && (
                <button className="tutorial-btn tutorial-btn-secondary" onClick={() => setStep(step - 1)}>
                  ← Back
                </button>
              )}
              <button
                className="tutorial-btn tutorial-btn-primary"
                onClick={handleCheck}
                disabled={loading}
              >
                {loading ? "Checking…" : s.cta || "Next"}
              </button>
            </>
          )}
          {skipped && (
            <button className="tutorial-btn tutorial-btn-primary" onClick={onComplete}>
              Done
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
