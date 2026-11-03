import { useState } from "react";

// Lets the user choose how in-depth each flashcard should be:
// shallow = one-liner summary, medium = usage + key flags, deep = full man-page detail.
export default function DepthToggle({ value, onChange }) {
  const depths = [
    { id: "shallow", label: "Shallow", desc: "One-liner summary" },
    { id: "medium", label: "Medium", desc: "Usage + key flags" },
    { id: "deep", label: "Deep", desc: "Full description + examples" },
  ];

  return (
    <div className="depth-toggle">
      <span className="muted small">Depth:</span>
      {depths.map((d) => (
        <button
          key={d.id}
          className={`depth-btn ${value === d.id ? "active" : ""}`}
          onClick={() => onChange(d.id)}
          title={d.desc}
        >
          {d.label}
        </button>
      ))}
    </div>
  );
}
