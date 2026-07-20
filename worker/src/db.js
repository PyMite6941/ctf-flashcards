// D1 data layer. All SQL lives here; the D1 binding is `env.DB`.
// Mirrors the Python app/db.py so the two backends behave identically.

const uid = () => crypto.randomUUID().replace(/-/g, "");
const now = () => Date.now() / 1000;

function rowToCard(r) {
  return {
    id: r.id,
    front: r.front,
    back: r.back,
    kind: r.kind,
    deck: r.deck,
    tags: JSON.parse(r.tags),
    fsrs: JSON.parse(r.fsrs),
    due: r.due,
    created_at: r.created_at,
    updated_at: r.updated_at,
  };
}

// ---------- cards ----------

export async function insertCard(env, { front, back, kind, deck, tags, fsrs, due }) {
  const id = uid();
  const ts = now();
  await env.DB.prepare(
    "INSERT INTO cards (id, front, back, kind, deck, tags, fsrs, due, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)"
  )
    .bind(id, front, back, kind, deck, JSON.stringify(tags), JSON.stringify(fsrs), due, ts, ts)
    .run();
  return getCard(env, id);
}

export async function getCard(env, id) {
  const r = await env.DB.prepare("SELECT * FROM cards WHERE id = ?").bind(id).first();
  return r ? rowToCard(r) : null;
}

export async function listCards(env, { deck, tag } = {}) {
  const where = [];
  const params = [];
  if (deck) { where.push("deck = ?"); params.push(deck); }
  if (tag) { where.push("tags LIKE ?"); params.push(`%"${tag}"%`); }
  let q = "SELECT * FROM cards";
  if (where.length) q += " WHERE " + where.join(" AND ");
  q += " ORDER BY created_at DESC";
  const { results } = await env.DB.prepare(q).bind(...params).all();
  return results.map(rowToCard);
}

export async function dueCards(env, nowIso, limit, tag) {
  let q = "SELECT * FROM cards WHERE due <= ?";
  const params = [nowIso];
  if (tag) { q += " AND tags LIKE ?"; params.push(`%"${tag}"%`); }
  q += " ORDER BY due ASC LIMIT ?";
  params.push(limit);
  const { results } = await env.DB.prepare(q).bind(...params).all();
  return results.map(rowToCard);
}

export async function cardExistsByFront(env, front) {
  const r = await env.DB.prepare("SELECT 1 FROM cards WHERE front = ? LIMIT 1").bind(front).first();
  return !!r;
}

export async function updateCardFsrs(env, id, fsrs, due) {
  await env.DB.prepare("UPDATE cards SET fsrs = ?, due = ?, updated_at = ? WHERE id = ?")
    .bind(JSON.stringify(fsrs), due, now(), id)
    .run();
}

export async function deleteCard(env, id) {
  await env.DB.prepare("DELETE FROM cards WHERE id = ?").bind(id).run();
}

export async function topics(env) {
  const nowIso = new Date().toISOString();
  const { results } = await env.DB.prepare("SELECT tags, due FROM cards").all();
  const counts = {};
  for (const r of results) {
    const isDue = r.due <= nowIso;
    for (const t of JSON.parse(r.tags)) {
      const slot = (counts[t] ||= { total: 0, due: 0 });
      slot.total += 1;
      if (isDue) slot.due += 1;
    }
  }
  return Object.keys(counts).sort().map((t) => ({ tag: t, total: counts[t].total, due: counts[t].due }));
}

// ---------- reviews ----------

export async function insertReview(env, cardId, rating) {
  await env.DB.prepare("INSERT INTO reviews (id, card_id, rating, reviewed_at) VALUES (?,?,?,?)")
    .bind(uid(), cardId, rating, now())
    .run();
}

export async function reviewCount(env) {
  const r = await env.DB.prepare("SELECT COUNT(*) AS n FROM reviews").first();
  return r.n;
}

// ---------- inbox ----------

export async function insertInbox(env, { front, back, kind, source, detail }) {
  const id = uid();
  await env.DB.prepare(
    "INSERT INTO inbox (id, front, back, kind, source, detail, status, created_at) VALUES (?,?,?,?,?,?, 'pending', ?)"
  ).bind(id, front, back, kind, source, detail, now()).run();
  return env.DB.prepare("SELECT * FROM inbox WHERE id = ?").bind(id).first();
}

export async function listInbox(env, status = "pending") {
  const { results } = await env.DB.prepare(
    "SELECT * FROM inbox WHERE status = ? ORDER BY created_at DESC"
  ).bind(status).all();
  return results;
}

export async function getInbox(env, id) {
  return env.DB.prepare("SELECT * FROM inbox WHERE id = ?").bind(id).first();
}

export async function setInboxStatus(env, id, status) {
  await env.DB.prepare("UPDATE inbox SET status = ? WHERE id = ?").bind(status, id).run();
}

// ---------- solves ----------

export async function recordSolve(env, puzzleId, points) {
  await env.DB.prepare("INSERT OR IGNORE INTO solves (puzzle_id, solved_at, points) VALUES (?,?,?)")
    .bind(puzzleId, now(), points).run();
}

export async function isSolved(env, puzzleId) {
  const r = await env.DB.prepare("SELECT 1 FROM solves WHERE puzzle_id = ? LIMIT 1").bind(puzzleId).first();
  return !!r;
}

export async function solvedIds(env) {
  const { results } = await env.DB.prepare("SELECT puzzle_id FROM solves").all();
  return new Set(results.map((r) => r.puzzle_id));
}

export async function totalPoints(env) {
  const r = await env.DB.prepare("SELECT COALESCE(SUM(points),0) AS p FROM solves").first();
  return r.p;
}

// ---------- daily metering ----------

export async function solvesToday(env, day, identity) {
  const r = await env.DB.prepare("SELECT solves FROM daily_usage WHERE day = ? AND identity = ?")
    .bind(day, identity).first();
  return r ? r.solves : 0;
}

export async function bumpSolvesToday(env, day, identity) {
  await env.DB.prepare(
    "INSERT INTO daily_usage (day, identity, solves) VALUES (?, ?, 1) " +
      "ON CONFLICT(day, identity) DO UPDATE SET solves = solves + 1"
  ).bind(day, identity).run();
  const r = await env.DB.prepare("SELECT solves FROM daily_usage WHERE day = ? AND identity = ?")
    .bind(day, identity).first();
  return r.solves;
}

// ---------- AI topic packs ----------

export async function upsertPack(env, { topic, topic_slug, labkit, card_count, challenge_count }) {
  await env.DB.prepare(
    "INSERT INTO gen_packs (id, topic, topic_slug, labkit, card_count, challenge_count, created_at) VALUES (?,?,?,?,?,?,?) " +
      "ON CONFLICT(topic_slug) DO UPDATE SET topic=excluded.topic, labkit=excluded.labkit, " +
      "card_count=excluded.card_count, challenge_count=excluded.challenge_count"
  ).bind(uid(), topic, topic_slug, labkit, card_count, challenge_count, now()).run();
}

export async function insertGenChallenge(env, c) {
  const id = uid();
  await env.DB.prepare(
    "INSERT INTO gen_challenges (id, topic_slug, title, category, difficulty, points, description, hint, artifact, flag, solution, challenge_type, created_at) " +
      "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)"
  ).bind(id, c.topic_slug, c.title, c.category, c.difficulty, c.points, c.description, c.hint, c.artifact, c.flag, c.solution, c.challenge_type, now()).run();
  return id;
}

export async function deleteGenChallengesForSlug(env, slug) {
  await env.DB.prepare("DELETE FROM gen_challenges WHERE topic_slug = ?").bind(slug).run();
}

export async function listPacks(env) {
  const { results } = await env.DB.prepare("SELECT * FROM gen_packs ORDER BY created_at DESC").all();
  return results;
}

export async function getPack(env, slug) {
  return env.DB.prepare("SELECT * FROM gen_packs WHERE topic_slug = ?").bind(slug).first();
}

export async function genChallengesForSlug(env, slug) {
  const { results } = await env.DB.prepare(
    "SELECT * FROM gen_challenges WHERE topic_slug = ? ORDER BY created_at ASC"
  ).bind(slug).all();
  return results;
}

export async function getGenChallenge(env, id) {
  return env.DB.prepare("SELECT * FROM gen_challenges WHERE id = ?").bind(id).first();
}

// A topic's flashcards are "finished" once every card tagged topic:<slug> has
// been reviewed at least once (FSRS reps >= 1). Returns {total, reviewed, done}.
export async function topicCardProgress(env, slug) {
  const { results } = await env.DB.prepare("SELECT fsrs FROM cards WHERE tags LIKE ?")
    .bind(`%"topic:${slug}"%`).all();
  const total = results.length;
  let reviewed = 0;
  for (const r of results) {
    try { if ((JSON.parse(r.fsrs).reps || 0) >= 1) reviewed++; } catch { /* skip */ }
  }
  return { total, reviewed, done: total > 0 && reviewed >= total };
}
