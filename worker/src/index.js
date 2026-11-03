// CTF Flashcards backend — Cloudflare Worker + D1.
// Port of the FastAPI app (backend/app). Same routes, same behaviour; FSRS via
// ts-fsrs, storage via D1, Pro entitlement verified through the GRID Store worker.

import * as db from "./db.js";
import * as puzzles from "./puzzles.js";
import * as billing from "./billing.js";
import * as aigen from "./aigen.js";
import { newCardState, review as fsrsReview } from "./scheduler.js";

// Public view of a generated challenge (never leak the flag).
function stripGen(c, solved) {
  const out = {
    id: c.id, topic_slug: c.topic_slug, title: c.title, category: c.category,
    difficulty: c.difficulty, points: c.points, description: c.description,
    hint: c.hint, artifact: c.artifact, challenge_type: c.challenge_type, solved,
  };
  if (solved) out.solution = c.solution;
  return out;
}

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, POST, DELETE, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type, Authorization, X-License",
};

const json = (data, status = 200) =>
  new Response(data === null ? "" : JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json", ...CORS },
  });
const nowIso = () => new Date().toISOString();

async function body(request) {
  try {
    return await request.json();
  } catch {
    return {};
  }
}

export default {
  async fetch(request, env) {
    if (request.method === "OPTIONS") return new Response(null, { status: 204, headers: CORS });
    try {
      return await route(request, env);
    } catch (e) {
      return json({ error: String(e && e.message ? e.message : e) }, 500);
    }
  },
};

async function route(request, env) {
  const url = new URL(request.url);
  const path = url.pathname.replace(/\/$/, "") || "/";
  const method = request.method;
  const q = url.searchParams;
  const seg = path.split("/").filter(Boolean); // e.g. ["cards", "<id>", "review"]
  const license = request.headers.get("x-license");

  // ---- health ----
  if (path === "/health" && method === "GET") {
    return json({
      ok: true,
      reviews: await db.reviewCount(env),
      points: await db.totalPoints(env),
      solved: (await db.solvedIds(env)).size,
      puzzles: puzzles.total(),
    });
  }

  // ---- one-time seed (idempotent; only if deck empty) ----
  if (path === "/admin/seed" && method === "POST") {
    if (env.ADMIN_KEY && request.headers.get("authorization") !== `Bearer ${env.ADMIN_KEY}`)
      return json({ error: "unauthorized" }, 401);
    const existing = await db.listCards(env);
    if (existing.length) return json({ seeded: 0, note: "deck not empty" });
    let n = 0;
    for (const c of STARTER_CARDS) {
      const [fsrs, due] = newCardState();
      await db.insertCard(env, { ...c, fsrs, due });
      n++;
    }
    return json({ seeded: n });
  }

  // ---- topics ----
  if (path === "/topics" && method === "GET") return json(await db.topics(env));

  // ---- cards ----
  if (path === "/cards" && method === "GET")
    return json(await db.listCards(env, { deck: q.get("deck"), tag: q.get("tag") }));

  if (path === "/cards" && method === "POST") {
    const b = await body(request);
    if (!b.front || !b.back) return json({ error: "front and back required" }, 422);
    const [fsrs, due] = newCardState();
    const card = await db.insertCard(env, {
      front: b.front, back: b.back, kind: b.kind || "flashcard",
      deck: b.deck || "default", tags: b.tags || [], fsrs, due,
    });
    return json(card, 201);
  }

  if (seg[0] === "cards" && seg.length === 2 && method === "GET") {
    const card = await db.getCard(env, seg[1]);
    return card ? json(card) : json({ error: "card not found" }, 404);
  }

  if (seg[0] === "cards" && seg.length === 2 && method === "DELETE") {
    if (!(await db.getCard(env, seg[1]))) return json({ error: "card not found" }, 404);
    await db.deleteCard(env, seg[1]);
    return json(null, 204);
  }

  // ---- review queue + submit ----
  if (path === "/review/queue" && method === "GET") {
    const limit = parseInt(q.get("limit") || "20", 10);
    return json(await db.dueCards(env, nowIso(), limit, q.get("tag")));
  }

  if (seg[0] === "cards" && seg[2] === "review" && method === "POST") {
    const card = await db.getCard(env, seg[1]);
    if (!card) return json({ error: "card not found" }, 404);
    const b = await body(request);
    const rating = b.rating;
    if (![1, 2, 3, 4].includes(rating)) return json({ error: "rating must be 1-4" }, 422);
    const [fsrs, due] = fsrsReview(card.fsrs, rating);
    await db.updateCardFsrs(env, seg[1], fsrs, due);
    await db.insertReview(env, seg[1], rating);
    return json(await db.getCard(env, seg[1]));
  }

  // ---- limits ----
  if (path === "/limits" && method === "GET") {
    const ent = await billing.verifyLicense(env, license);
    const identity = await billing.resolveIdentity(env, request);
    const used = await db.solvesToday(env, billing.today(), identity);
    const cap = billing.freeDailySolves(env);
    const aiUsed = await db.aiGensThisMonth(env, billing.thisMonth(), identity);
    const aiCap = billing.freeMonthlyAiGens(env);
    return json({
      pro: ent.pro, tier: ent.tier,
      daily_solve_limit: cap,
      solves_used_today: used,
      solves_remaining: ent.pro ? null : Math.max(0, cap - used),
      ai_gens_limit: aiCap,
      ai_gens_used_this_month: aiUsed,
      ai_gens_remaining: ent.pro ? null : Math.max(0, aiCap - aiUsed),
      price_usdc: 8, tier_id: "ctf_pro",
    });
  }

  // ---- puzzles ----
  if (path === "/puzzles" && method === "GET") {
    const solved = await db.solvedIds(env);
    return json({
      puzzles: puzzles.listPuzzles(solved, {
        category: q.get("category"), difficulty: q.get("difficulty"), status: q.get("status"),
      }),
      categories: puzzles.categories(),
      points: await db.totalPoints(env),
      solved: solved.size,
      total: puzzles.total(),
    });
  }

  if (seg[0] === "puzzles" && seg.length === 2 && method === "GET") {
    const p = puzzles.getPuzzle(seg[1], await db.isSolved(env, seg[1]));
    return p ? json(p) : json({ error: "puzzle not found" }, 404);
  }

  if (seg[0] === "puzzles" && seg[2] === "submit" && method === "POST") {
    const pid = seg[1];
    const b = await body(request);
    if (!b.flag) return json({ error: "flag required" }, 422);
    const { correct, puzzle } = puzzles.checkFlag(pid, b.flag);
    if (!puzzle) return json({ error: "puzzle not found" }, 404);
    if (!correct) return json({ correct: false });

    const already = await db.isSolved(env, pid);
    if (!already) {
      const ent = await billing.verifyLicense(env, license);
      if (!ent.pro) {
        const identity = await billing.resolveIdentity(env, request);
        const used = await db.solvesToday(env, billing.today(), identity);
        const cap = billing.freeDailySolves(env);
        if (used >= cap) {
          return json({
            detail: {
              error: "daily_limit_reached",
              message: `Free tier is ${cap} puzzle solves per day. Upgrade to Pro ($8/mo) for unlimited.`,
              daily_solve_limit: cap, tier_id: "ctf_pro", price_usdc: 8,
            },
          }, 402);
        }
        await db.bumpSolvesToday(env, billing.today(), identity);
      }
    }

    await db.recordSolve(env, pid, puzzle.points);
    const added = [];
    for (const card of puzzle.cards) {
      if (await db.cardExistsByFront(env, card.front)) continue;
      const [fsrs, due] = newCardState();
      await db.insertCard(env, {
        front: card.front, back: card.back, kind: "flashcard",
        deck: puzzle.category, tags: card.tags || [puzzle.category], fsrs, due,
      });
      added.push(card.front);
    }
    return json({
      correct: true, already_solved: already, points: puzzle.points,
      total_points: await db.totalPoints(env), solution: puzzle.solution, added_cards: added,
    });
  }

  // ---- AI topic packs ----
  // Generate a pack: flashcards (into the deck) + practice challenges (locked
  // until the flashcards are reviewed) + a downloadable lab kit.
  if (path === "/ai/generate" && method === "POST") {
    const b = await body(request);
    const topic = (b.topic || "").trim();
    if (!topic) return json({ error: "topic required" }, 422);
    if (topic.length > 120) return json({ error: "topic too long" }, 422);

    // Free tier: cap AI generations per month. Pro = unlimited.
    const gEnt = await billing.verifyLicense(env, license);
    const gIdentity = await billing.resolveIdentity(env, request);
    const gMonth = billing.thisMonth();
    if (!gEnt.pro) {
      const used = await db.aiGensThisMonth(env, gMonth, gIdentity);
      const cap = billing.freeMonthlyAiGens(env);
      if (used >= cap) {
        return json({
          detail: {
            error: "ai_limit_reached",
            message: `Free tier is ${cap} AI generations per month. Upgrade to Pro ($8/mo) for unlimited.`,
            ai_gens_limit: cap, tier_id: "ctf_pro", price_usdc: 8,
          },
        }, 402);
      }
    }

    let pack;
    try {
      pack = await aigen.generatePack(env, topic);
    } catch (e) {
      return json({ error: String(e.message || e) }, 502);
    }
    if (!pack.flashcards.length && !pack.challenges.length)
      return json({ error: "AI returned an empty pack — try rephrasing the topic." }, 502);

    // Add flashcards to the deck (dedup by front).
    let added = 0;
    for (const c of pack.flashcards) {
      if (await db.cardExistsByFront(env, c.front)) continue;
      const [fsrs, due] = newCardState();
      await db.insertCard(env, {
        front: c.front, back: c.back, kind: "flashcard",
        deck: pack.topic_slug, tags: c.tags, fsrs, due,
      });
      added++;
    }
    // Replace any prior challenges for this topic, then store the new ones.
    await db.deleteGenChallengesForSlug(env, pack.topic_slug);
    for (const ch of pack.challenges) await db.insertGenChallenge(env, ch);
    await db.upsertPack(env, {
      topic: pack.topic, topic_slug: pack.topic_slug, labkit: pack.labkit,
      card_count: pack.flashcards.length, challenge_count: pack.challenges.length,
    });

    // Count the generation against the free monthly quota (only on success).
    if (!gEnt.pro) await db.bumpAiGens(env, gMonth, gIdentity);

    return json({
      topic: pack.topic, topic_slug: pack.topic_slug,
      cards_added: added, flashcards: pack.flashcards.length,
      challenges: pack.challenges.length, has_labkit: pack.labkit.length > 0,
    }, 201);
  }

  if (path === "/ai/packs" && method === "GET") {
    const packs = await db.listPacks(env);
    const out = [];
    for (const p of packs) {
      const prog = await db.topicCardProgress(env, p.topic_slug);
      out.push({ ...p, progress: prog });
    }
    return json(out);
  }

  if (seg[0] === "ai" && seg[1] === "packs" && seg.length === 3 && method === "GET") {
    const slug = seg[2];
    const pack = await db.getPack(env, slug);
    if (!pack) return json({ error: "pack not found" }, 404);
    const prog = await db.topicCardProgress(env, slug);
    const solved = await db.solvedIds(env);
    const challenges = (await db.genChallengesForSlug(env, slug)).map((c) =>
      stripGen(c, solved.has(c.id))
    );
    // Practice is gated until the topic's flashcards are finished.
    return json({ ...pack, progress: prog, unlocked: prog.done, challenges });
  }

  if (seg[0] === "ai" && seg[1] === "packs" && seg[3] === "labkit" && method === "GET") {
    const pack = await db.getPack(env, seg[2]);
    if (!pack) return json({ error: "pack not found" }, 404);
    return new Response(pack.labkit || `# ${seg[2]}\n\n(no lab kit)`, {
      headers: {
        "Content-Type": "text/markdown; charset=utf-8",
        "Content-Disposition": `attachment; filename="${seg[2]}-labkit.md"`,
        ...CORS,
      },
    });
  }

  if (seg[0] === "ai" && seg[1] === "challenges" && seg[3] === "submit" && method === "POST") {
    const c = await db.getGenChallenge(env, seg[2]);
    if (!c) return json({ error: "challenge not found" }, 404);
    // Gate: the topic's flashcards must be finished first.
    const prog = await db.topicCardProgress(env, c.topic_slug);
    if (!prog.done)
      return json({ error: "locked", message: "Finish this topic's flashcards first." }, 423);
    const b = await body(request);
    let sub = String(b.flag || "").trim().toLowerCase();
    if (!sub) return json({ error: "flag required" }, 422);
    if (!sub.startsWith("ctf{") && !sub.endsWith("}")) sub = `ctf{${sub}}`;
    if (sub !== c.flag.toLowerCase()) return json({ correct: false });

    const already = await db.isSolved(env, c.id);
    await db.recordSolve(env, c.id, c.points);
    return json({
      correct: true, already_solved: already, points: c.points,
      total_points: await db.totalPoints(env), solution: c.solution,
    });
  }

  // ---- inbox ----
  if (path === "/inbox" && method === "GET") return json(await db.listInbox(env, q.get("status") || "pending"));

  if (path === "/inbox" && method === "POST") {
    const b = await body(request);
    if (!b.front || !b.back) return json({ error: "front and back required" }, 422);
    return json(await db.insertInbox(env, {
      front: b.front, back: b.back, kind: b.kind || "flashcard",
      source: b.source || "manual", detail: b.detail || "",
    }), 201);
  }

  if (seg[0] === "inbox" && seg[2] === "approve" && method === "POST") {
    const item = await db.getInbox(env, seg[1]);
    if (!item) return json({ error: "inbox item not found" }, 404);
    if (item.status !== "pending") return json({ error: `item already ${item.status}` }, 409);
    const e = await body(request);
    const [fsrs, due] = newCardState();
    const card = await db.insertCard(env, {
      front: e.front || item.front, back: e.back || item.back, kind: e.kind || item.kind,
      deck: e.deck || "default", tags: e.tags || [], fsrs, due,
    });
    await db.setInboxStatus(env, seg[1], "approved");
    return json(card, 201);
  }

  if (seg[0] === "inbox" && seg[2] === "reject" && method === "POST") {
    const item = await db.getInbox(env, seg[1]);
    if (!item) return json({ error: "inbox item not found" }, 404);
    await db.setInboxStatus(env, seg[1], "rejected");
    return json({ ok: true });
  }

  return json({ error: "not found", path }, 404);
}

// Starter cards for /admin/seed (mirrors backend/seed.py).
const STARTER_CARDS = [
  { front: "What port does HTTPS use by default?", back: "TCP 443", kind: "flashcard", deck: "networking", tags: ["ports"] },
  { front: "What does the CIA triad stand for?", back: "Confidentiality, Integrity, Availability", kind: "flashcard", deck: "concepts", tags: ["fundamentals"] },
  { front: "Which HTTP header mitigates clickjacking?", back: "X-Frame-Options (or Content-Security-Policy frame-ancestors)", kind: "flashcard", deck: "web", tags: ["headers"] },
  { front: "What is the difference between a hash and encryption?", back: "Hashing is one-way (no key, not reversible); encryption is two-way (reversible with a key).", kind: "flashcard", deck: "crypto", tags: ["fundamentals"] },
  { front: "What nmap flag runs a SYN 'stealth' scan?", back: "-sS", kind: "flashcard", deck: "tools", tags: ["nmap"] },
  { front: "What is the purpose of a salt in password hashing?", back: "A unique random value per password so identical passwords hash differently, defeating rainbow tables.", kind: "flashcard", deck: "crypto", tags: ["passwords"] },
  { front: "CHALLENGE: Spot the flaw — `query = \\\"SELECT * FROM users WHERE name = '\\\" + name + \\\"'\\\"`", back: "SQL injection: `name` is concatenated straight into the query. Fix with parameterized queries / prepared statements.", kind: "challenge", deck: "web", tags: ["sqli"] },
  { front: "CHALLENGE: Decode this Base64 — `Y3RmezBrX3RoYXRzX2Jhc2U2NH0=`", back: "ctf{0k_thats_base64}", kind: "challenge", deck: "crypto", tags: ["encoding"] },
  { front: "CHALLENGE: A log line reads `sshd: Failed password for root from 203.0.113.9 port 22 ssh2` repeated 400x in 1 min. What is it?", back: "An SSH brute-force / password-spray attempt. Mitigate: disable root SSH, use keys, rate-limit (fail2ban).", kind: "challenge", deck: "blue-team", tags: ["logs"] },
  { front: "CHALLENGE: What kind of hash is `5f4dcc3b5aa765d61d8327deb882cf99` and what does it hash?", back: "32 hex chars = MD5. This is the well-known MD5 of the string 'password'.", kind: "challenge", deck: "crypto", tags: ["hashes"] },
];
