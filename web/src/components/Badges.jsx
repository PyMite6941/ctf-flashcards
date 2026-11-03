import { useEffect, useState } from "react";
import { api } from "../lib/api.js";

// Badges / achievements display. Shows earned + unearned badges with criteria.
// Teaching/learning feature: gamifies progress to motivate review streaks.
export default function Badges() {
  const [all, setAll] = useState([]);
  const [earned, setEarned] = useState([]);
  const [userId, setUserId] = useState("local");

  useEffect(() => {
    api.badgesList().then(setAll).catch(() => {});
    api.badgesEarned(userId).then(setEarned).catch(() => {});
  }, [userId]);

  const earnedIds = new Set(earned.map((e) => e.badge_id));

  return (
    <div className="stack">
      <div className="card">
        <h2 className="nomargin">🏅 Achievements</h2>
        <p className="muted small nomargin">
          Earn badges by capturing commands, reviewing cards, and completing scenarios.
        </p>
        <div className="badges-grid">
          {all.map((b) => {
            const got = earnedIds.has(b.id);
            return (
              <div key={b.id} className={`badge-card ${got ? "earned" : "locked"}`}>
                <div className="badge-icon">{got ? b.icon : "❓"}</div>
                <div className="badge-info">
                  <div className={`badge-name ${got ? "" : "muted"}`}>{b.name}</div>
                  <div className="badge-desc muted small">{b.description}</div>
                  <div className="badge-criteria muted small">
                    {b.criterion_type}: {b.criterion_value}
                  </div>
                </div>
                {got && <span className="badge-earned">earned</span>}
              </div>
            );
          })}
        </div>
        {all.length === 0 && <p className="muted small">No badges defined yet.</p>}
      </div>

      <div className="card">
        <h3 className="nomargin">🎖️ Your earned badges</h3>
        {earned.length === 0 ? (
          <p className="muted small">No badges earned yet. Keep reviewing!</p>
        ) : (
          <div className="row gap wrap">
            {earned.map((e) => (
              <div key={e.badge_id} className="earned-chip">
                {e.icon} {e.name}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
