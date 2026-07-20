// AI topic packs — Groq generates flashcards + practice challenges for a topic.
//
// Solvability guarantee: the model never invents an (artifact, flag) pair that
// might not match. It picks a challenge `type` and writes a `flag`; WE render the
// artifact deterministically from the flag (same transforms as the static
// puzzles). `concept` challenges carry their own question as the artifact and the
// flag is the answer — checked by the normal flag matcher.

const enc = new TextEncoder();
const _b64 = (s) => btoa(s);
const _hex = (s) => [...enc.encode(s)].map((b) => b.toString(16).padStart(2, "0")).join("");
const _binary = (s) => [...s].map((c) => c.charCodeAt(0).toString(2).padStart(8, "0")).join(" ");
const _xorHex = (s, key) => [...enc.encode(s)].map((b) => (b ^ key).toString(16).padStart(2, "0")).join("");
const _reverse = (s) => [...s].reverse().join("");
function _caesar(s, shift) {
  let out = "";
  for (const ch of s) {
    const c = ch.charCodeAt(0);
    if (ch >= "A" && ch <= "Z") out += String.fromCharCode(((c - 65 + shift) % 26) + 65);
    else if (ch >= "a" && ch <= "z") out += String.fromCharCode(((c - 97 + shift) % 26) + 97);
    else out += ch;
  }
  return out;
}

// type -> { render(flag) -> artifact, solution(flag) -> text }
const XOR_KEY = 0x42;
const CAESAR_SHIFT = 5;
const RENDERERS = {
  base64: { render: (f) => _b64(f), solution: () => "Base64-decode it (base64 -d / CyberChef 'From Base64')." },
  rot13: { render: (f) => _caesar(f, 13), solution: () => "Apply ROT13 (a Caesar cipher, shift 13; its own inverse)." },
  caesar: { render: (f) => _caesar(f, CAESAR_SHIFT), solution: () => "Caesar cipher shifted by 5 — brute-force the 25 shifts and read the flag." },
  hex: { render: (f) => _hex(f), solution: () => "Hex -> ASCII (xxd -r -p, or bytes.fromhex)." },
  binary: { render: (f) => _binary(f), solution: () => "Read each 8-bit group as one ASCII byte." },
  xor: { render: (f) => _xorHex(f, XOR_KEY), solution: () => "Single-byte XOR. Flags start with 'ctf{' -> key = firstByte XOR 'c' = 0x42; XOR everything." },
  reverse: { render: (f) => _reverse(f), solution: () => "The flag is simply reversed — read it backwards." },
  concept: { render: (f, spec) => spec.question || spec.description, solution: (f) => `The answer is ${f}.` },
};
export const CHALLENGE_TYPES = Object.keys(RENDERERS);

const slugify = (s) => s.toLowerCase().trim().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "").slice(0, 40);
const POINTS = { easy: 50, medium: 100, hard: 150 };

// Render one AI challenge spec into a stored challenge (artifact + solution).
export function renderChallenge(spec, topic, topicSlug) {
  const type = RENDERERS[spec.type] ? spec.type : "base64";
  const r = RENDERERS[type];
  let flag = String(spec.flag || "").trim().toLowerCase();
  if (!flag.startsWith("ctf{")) flag = `ctf{${flag.replace(/[^a-z0-9_]/g, "_")}}`;
  const difficulty = ["easy", "medium", "hard"].includes(spec.difficulty) ? spec.difficulty : "easy";
  return {
    topic, topic_slug: topicSlug,
    title: (spec.title || `${topic} challenge`).slice(0, 120),
    category: "ai",
    difficulty,
    points: POINTS[difficulty],
    description: (spec.description || "").slice(0, 1000),
    hint: (spec.hint || "").slice(0, 500),
    artifact: String(r.render(flag, spec)).slice(0, 4000),
    flag,
    solution: (spec.solution ? spec.solution + " " : "") + r.solution(flag),
    challenge_type: type,
  };
}

const SYSTEM = `You are a cybersecurity CTF instructor building a learning pack.
Return STRICT JSON only, matching this shape:
{
  "topic": string,
  "flashcards": [ { "front": string, "back": string, "tags": [string] } ],   // 5-8 items
  "challenges": [ { "type": string, "flag": string, "title": string, "description": string, "hint": string, "difficulty": "easy"|"medium"|"hard", "question": string } ],  // 2-4 items
  "labkit": string   // markdown: a hands-on lab the learner can run in their OWN environment
}
Rules:
- Flashcards teach the core, testable concepts of the topic (free recall Q/A).
- Each challenge "type" MUST be one of: base64, rot13, caesar, hex, binary, xor, reverse, concept.
- "flag" MUST be lowercase of the form ctf{...} with a short, TOPIC-RELEVANT phrase inside using only [a-z0-9_].
- For encoding types (base64/rot13/caesar/hex/binary/xor/reverse): the learner decodes an artifact WE generate from the flag; write description+hint that teach that encoding AND connect it to the topic.
- For "concept": put a direct question in "question" whose answer IS the inner flag text (e.g. question about the topic, flag ctf{answer_in_snake_case}). This tests topic knowledge.
- Include at least one "concept" challenge so the topic itself is tested, not just decoding.
- labkit: concrete steps, commands, and what to look for — safe, legal, self-contained (local VM / docker / files the learner sets up). No illegal targets.`;

// Call Groq (OpenAI-compatible) and return the parsed pack.
export async function generatePack(env, topic) {
  if (!env.GROQ_API_KEY) throw new Error("AI is not configured (GROQ_API_KEY secret missing).");
  const model = env.GROQ_MODEL || "openai/gpt-oss-120b";
  const res = await fetch("https://api.groq.com/openai/v1/chat/completions", {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${env.GROQ_API_KEY}` },
    body: JSON.stringify({
      model,
      messages: [
        { role: "system", content: SYSTEM },
        { role: "user", content: `Topic: ${topic}. Respond with JSON only.` },
      ],
      reasoning_effort: "low",
      temperature: 0.6,
      max_tokens: 6000,
    }),
  });
  if (!res.ok) {
    const t = await res.text().catch(() => "");
    throw new Error(`Groq error ${res.status}: ${t.slice(0, 200)}`);
  }
  const data = await res.json();
  const content = data.choices?.[0]?.message?.content || "";
  const pack = extractJson(content);
  if (!pack) throw new Error("AI returned unparseable JSON.");
  return normalizePack(pack, topic);
}

// Tolerant JSON extraction — handles ```json fences and surrounding prose.
function extractJson(text) {
  try {
    return JSON.parse(text);
  } catch {
    /* fall through */
  }
  const fenced = text.match(/```(?:json)?\s*([\s\S]*?)```/i);
  if (fenced) {
    try {
      return JSON.parse(fenced[1]);
    } catch {
      /* fall through */
    }
  }
  const start = text.indexOf("{");
  const end = text.lastIndexOf("}");
  if (start !== -1 && end > start) {
    try {
      return JSON.parse(text.slice(start, end + 1));
    } catch {
      /* fall through */
    }
  }
  return null;
}

function normalizePack(pack, topic) {
  const topicSlug = slugify(topic);
  const flashcards = (Array.isArray(pack.flashcards) ? pack.flashcards : [])
    .filter((c) => c && c.front && c.back)
    .slice(0, 10)
    .map((c) => ({
      front: String(c.front).slice(0, 500),
      back: String(c.back).slice(0, 1000),
      tags: [`topic:${topicSlug}`, ...(Array.isArray(c.tags) ? c.tags : []).map((t) => String(t).toLowerCase().slice(0, 30))].slice(0, 6),
    }));
  const challenges = (Array.isArray(pack.challenges) ? pack.challenges : [])
    .filter((c) => c && c.flag)
    .slice(0, 4)
    .map((c) => renderChallenge(c, topic, topicSlug));
  return {
    topic, topic_slug: topicSlug,
    flashcards, challenges,
    labkit: String(pack.labkit || "").slice(0, 12000),
  };
}
