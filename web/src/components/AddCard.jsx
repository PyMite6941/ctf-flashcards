import { useState } from "react";
import { api } from "../lib/api.js";

// Manual content input (plan §6). Add either a plain flashcard or an applied
// challenge; both flow through the same recall loop.
export default function AddCard({ onAdded }) {
  const [front, setFront] = useState("");
  const [back, setBack] = useState("");
  const [kind, setKind] = useState("flashcard");
  const [deck, setDeck] = useState("default");
  const [tags, setTags] = useState("");
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState("");

  async function submit(e) {
    e.preventDefault();
    if (!front.trim() || !back.trim()) return;
    setSaving(true);
    try {
      await api.createCard({
        front: front.trim(),
        back: back.trim(),
        kind,
        deck: deck.trim() || "default",
        tags: tags.split(",").map((t) => t.trim()).filter(Boolean),
      });
      setFront("");
      setBack("");
      setTags("");
      setMsg("Card added ✓");
      onAdded?.();
      setTimeout(() => setMsg(""), 2000);
    } catch (err) {
      setMsg(err.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <form className="card" onSubmit={submit}>
      <h2>Add a card</h2>
      <label>
        Prompt / question
        <textarea value={front} onChange={(e) => setFront(e.target.value)} required />
      </label>
      <label>
        Answer / solution
        <textarea value={back} onChange={(e) => setBack(e.target.value)} required />
      </label>
      <div className="row gap">
        <label className="grow">
          Type
          <select value={kind} onChange={(e) => setKind(e.target.value)}>
            <option value="flashcard">flashcard</option>
            <option value="challenge">challenge</option>
          </select>
        </label>
        <label className="grow">
          Deck
          <input value={deck} onChange={(e) => setDeck(e.target.value)} placeholder="default" />
        </label>
      </div>
      <label>
        Tags (comma-separated)
        <input value={tags} onChange={(e) => setTags(e.target.value)} placeholder="crypto, hashes" />
      </label>
      <button className="primary" disabled={saving}>
        {saving ? "Saving…" : "Add card"}
      </button>
      {msg && <p className="muted small">{msg}</p>}
    </form>
  );
}
