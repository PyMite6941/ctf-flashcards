import { useEffect, useState } from "react";
import { api } from "../lib/api.js";

// Review inbox (plan §5 safeguard): candidate cards from the local monitor land
// here. Nothing enters the real spaced-repetition deck without an explicit
// approve — you can edit before accepting, or reject junk outright.
export default function Inbox({ onApproved }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [edits, setEdits] = useState({});

  async function load() {
    setLoading(true);
    try {
      setItems(await api.listInbox("pending"));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  function editVal(item, field) {
    return edits[item.id]?.[field] ?? item[field];
  }
  function setEdit(id, field, value) {
    setEdits((e) => ({ ...e, [id]: { ...e[id], [field]: value } }));
  }

  async function approve(item) {
    await api.approveInbox(item.id, {
      front: editVal(item, "front"),
      back: editVal(item, "back"),
      kind: editVal(item, "kind"),
      deck: edits[item.id]?.deck || "monitor",
      tags: (edits[item.id]?.tags || "")
        .split(",").map((t) => t.trim()).filter(Boolean),
    });
    await load();
    onApproved?.();
  }

  async function reject(item) {
    await api.rejectInbox(item.id);
    await load();
  }

  if (loading) return <p className="muted">Loading inbox…</p>;

  if (items.length === 0)
    return (
      <div className="card center">
        <h2>Review inbox is empty</h2>
        <p className="muted">
          Candidate cards from the local monitor will appear here for approval
          before they join your deck.
        </p>
      </div>
    );

  return (
    <div className="stack">
      <p className="muted small">
        {items.length} candidate{items.length === 1 ? "" : "s"} awaiting your review.
      </p>
      {items.map((item) => (
        <div className="card" key={item.id}>
          <div className="row between">
            <span className={`badge ${item.kind}`}>{item.kind}</span>
            <span className="muted small">source: {item.source}</span>
          </div>
          <label>
            Prompt
            <textarea
              value={editVal(item, "front")}
              onChange={(e) => setEdit(item.id, "front", e.target.value)}
            />
          </label>
          <label>
            Answer
            <textarea
              value={editVal(item, "back")}
              onChange={(e) => setEdit(item.id, "back", e.target.value)}
            />
          </label>
          {item.detail && <p className="detail">context: {item.detail}</p>}
          <div className="row gap">
            <input
              className="grow"
              placeholder="deck (default: monitor)"
              value={edits[item.id]?.deck || ""}
              onChange={(e) => setEdit(item.id, "deck", e.target.value)}
            />
            <input
              className="grow"
              placeholder="tags, comma-separated"
              value={edits[item.id]?.tags || ""}
              onChange={(e) => setEdit(item.id, "tags", e.target.value)}
            />
          </div>
          <div className="row gap">
            <button className="primary grow" onClick={() => approve(item)}>
              Approve → deck
            </button>
            <button className="danger" onClick={() => reject(item)}>
              Reject
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
