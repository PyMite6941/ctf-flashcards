import { useEffect, useState } from "react";
import { api } from "../lib/api.js";

// Analytics dashboard: progress heatmap, stats, and streak.
// Teaching/learning feature: lets learners and instructors see progress over time.
export default function Analytics() {
  const [stats, setStats] = useState(null);
  const [snapshots, setSnapshots] = useState([]);
  const [userId, setUserId] = useState("local");

  useEffect(() => {
    api.progressStats(userId).then(setStats).catch(() => {});
    api.progressSnapshots(userId, 30).then(setSnapshots).catch(() => {});
  }, [userId]);

  const heatmap = snapshots.map((s) => {
    const total = s.total_count || 0;
    const level = total === 0 ? 0 : total >= 20 ? 4 : total >= 10 ? 3 : total >= 5 ? 2 : 1;
    return { date: s.date, count: total, level, correct: s.correct_count, reviewed: s.cards_reviewed };
  });

  const accuracy = stats ? stats.accuracy : 0;
  const daysActive = stats ? stats.days_active : 0;
  const minutes = stats ? stats.minutes_spent : 0;

  return (
    <div className="stack">
      <div className="card">
        <h2 className="nomargin">📊 Progress Analytics</h2>
        <p className="muted small nomargin">
          Track your review streak, accuracy, and time spent over the last 30 days.
        </p>
        <div className="row gap wrap" style={{ marginBottom: "24px" }}>
          <div className="tile stat-tile">
            <div className="tile-value">{accuracy}%</div>
            <div className="tile-label">review accuracy</div>
          </div>
          <div className="tile stat-tile">
            <div className="tile-value">{daysActive}</div>
            <div className="tile-label">active days (30d)</div>
          </div>
          <div className="tile stat-tile">
            <div className="tile-value">{Math.round(minutes / 60)}h {minutes % 60}m</div>
            <div className="tile-label">time reviewed</div>
          </div>
          <div className="tile stat-tile">
            <div className="tile-value">{stats?.cards_reviewed ?? 0}</div>
            <div className="tile-label">cards reviewed</div>
          </div>
        </div>
      </div>

      <div className="card">
        <div className="row between">
          <h3 className="nomargin">📅 Review heatmap (last 30 days)</h3>
          <div className="muted small">{userId}</div>
        </div>
        <div className="heatmap">
          {heatmap.map((d) => (
            <div
              key={d.date}
              className={`heat-cell level-${d.level}`}
              title={`${d.date}: ${d.count} reviews (${d.correct}/${d.reviewed} correct)`}
            />
          ))}
        </div>
        <div className="muted small heatmap-legend">
          <span>no activity</span>
          {[1, 2, 3, 4].map((l) => (
            <span key={l} className={`heat-cell level-${l}`} />
          ))}
          <span>heavy</span>
        </div>
      </div>

      <div className="card">
        <h3 className="nomargin">📝 Recent activity</h3>
        {snapshots.length === 0 ? (
          <p className="muted small">No activity yet. Start reviewing cards to see your heatmap.</p>
        ) : (
          snapshots.map((s) => (
            <div key={s.date} className="row between activity-row">
              <div>
                <strong>{s.date}</strong>
                <span className="muted small"> &middot; {s.cards_reviewed} reviewed</span>
              </div>
              <div className="muted small">
                {s.correct_count}/{s.total_count} correct &middot; {Math.round((s.minutes_spent || 0) / 60)}m
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
