import { useEffect, useState } from "react";
import { api } from "../lib/api.js";

// Study groups / classes (teaching feature).
// Create groups, assign topics to members, track assignment progress.
export default function StudyGroups() {
  const [groups, setGroups] = useState([]);
  const [selected, setSelected] = useState(null);
  const [newName, setNewName] = useState("");
  const [newDesc, setNewDesc] = useState("");

  useEffect(() => {
    api.sgListGroups().then(setGroups).catch(() => {});
  }, []);

  const group = groups.find((g) => g.id === selected);

  async function createGroup() {
    if (!newName.trim()) return;
    const g = await api.sgCreateGroup({ name: newName.trim(), description: newDesc });
    setGroups([...groups, g]);
    setSelected(g.id);
    setNewName("");
    setNewDesc("");
  }

  async function assignTopic() {
    if (!selected || !newTopic.trim() || !newTitle.trim()) return;
    await api.sgAssignTopic(selected, {
      topic_slug: newTopic.trim(),
      title: newTitle.trim(),
    });
    setNewTopic("");
    setNewTitle("");
  }

  const [newTopic, setNewTopic] = useState("");
  const [newTitle, setNewTitle] = useState("");

  return (
    <div className="stack">
      <div className="card">
        <h2 className="nomargin">👥 Study Groups</h2>
        <p className="muted small nomargin">
          Create a class or study group, assign topics, and track member progress.
        </p>
        <div className="row gap wrap" style={{ marginBottom: "16px" }}>
          <input
            className="grow"
            placeholder="Group name"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
          />
          <input
            className="grow"
            placeholder="Description (optional)"
            value={newDesc}
            onChange={(e) => setNewDesc(e.target.value)}
          />
          <button className="primary" onClick={createGroup} disabled={!newName.trim()}>
            Create group
          </button>
        </div>
        {groups.length === 0 && (
          <p className="muted small">No groups yet. Create one above.</p>
        )}
        {groups.map((g) => (
          <div
            key={g.id}
            className={`group-row ${selected === g.id ? "active" : ""}`}
            onClick={() => setSelected(selected === g.id ? null : g.id)}
          >
            <div className="row between">
              <strong>{g.name}</strong>
              <span className={`badge ${g.owner_id === "local" ? "owner" : "member"}`}>
                {g.owner_id === "local" ? "owner" : "member"}
              </span>
            </div>
            {g.description && <p className="muted small">{g.description}</p>}
          </div>
        ))}
      </div>

      {selected && group && (
        <div className="card">
          <div className="row between">
            <h3 className="nomargin">{group.name}</h3>
            <button className="link" onClick={() => setSelected(null)}>
              ← back to groups
            </button>
          </div>
          <div className="row gap wrap" style={{ marginBottom: "16px" }}>
            <input
              className="grow"
              placeholder="Topic slug (e.g. crypto)"
              value={newTopic}
              onChange={(e) => setNewTopic(e.target.value)}
            />
            <input
              className="grow"
              placeholder="Assignment title"
              value={newTitle}
              onChange={(e) => setNewTitle(e.target.value)}
            />
            <button className="primary" onClick={assignTopic}>
              Assign topic
            </button>
          </div>
          <h4 className="nomargin">Assignments</h4>
          {group.assignments?.length === 0 ? (
            <p className="muted small">No assignments yet.</p>
          ) : (
            group.assignments.map((a) => (
              <div key={a.assignment_id} className="assignment-row">
                <div>
                  <strong>{a.title}</strong>
                  <span className="muted small"> &middot; {a.topic_slug}</span>
                </div>
                <div className="muted small">
                  {a.progress?.done ? "✓ complete" : `${a.progress.reviewed}/${a.progress.total} reviewed`}
                </div>
              </div>
            ))
          )}
          <h4 className="nomargin" style={{ marginTop: "16px" }}>Members</h4>
          {group.members?.length === 0 ? (
            <p className="muted small">No members yet.</p>
          ) : (
            group.members.map((m) => (
              <div key={m.user_id} className="row between member-row">
                <span>{m.user_id}</span>
                <span className="badge">{m.role}</span>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}
