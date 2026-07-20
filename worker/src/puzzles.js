// CTF puzzle catalog — JS port of app/puzzles.py. Artifacts are derived from the
// flags at module load, so data can never drift from answers. Identical flags +
// transforms => identical artifacts to the Python backend.

const enc = new TextEncoder();

const _b64 = (s) => btoa(s);
const _b64url = (o) =>
  btoa(JSON.stringify(o)).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
const _hex = (s) => [...enc.encode(s)].map((b) => b.toString(16).padStart(2, "0")).join("");
const _xorHex = (s, key) =>
  [...enc.encode(s)].map((b) => (b ^ key).toString(16).padStart(2, "0")).join("");
const _binary = (s) => [...s].map((c) => c.charCodeAt(0).toString(2).padStart(8, "0")).join(" ");
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

export const CATALOG = [
  {
    id: "base64-basement", title: "Base64 Basement", category: "crypto", difficulty: "easy", points: 50,
    description: "Someone left this string lying around. It looks scrambled, but it isn't encrypted - just encoded.",
    hint: "Ends in '=' padding and uses A-Z, a-z, 0-9, +, /. That's a big tell.",
    flag: "ctf{base64_is_just_encoding}",
    artifact: _b64("ctf{base64_is_just_encoding}"),
    solution: "Base64-decode it: echo '<string>' | base64 -d. Base64 is reversible with no key, so it's encoding, not encryption.",
    cards: [
      { front: "What is the difference between encoding and encryption?", back: "Encoding (e.g. Base64) is reversible with no secret - for data transport. Encryption needs a key and provides confidentiality.", tags: ["crypto", "encoding", "base64"] },
      { front: "How do you recognise Base64 at a glance?", back: "A-Z, a-z, 0-9, +, / charset; length a multiple of 4; often '='/'==' padding at the end.", tags: ["crypto", "encoding", "base64"] },
    ],
  },
  {
    id: "caesar-cipher", title: "Hail Caesar", category: "crypto", difficulty: "easy", points: 75,
    description: "A message shifted along the alphabet. The shift is unknown - but there are only so many it could be.",
    hint: "Only 25 non-trivial shifts exist for a Caesar cipher. Brute force them all and read the one that makes sense.",
    flag: "ctf{et_tu_brute_force}",
    artifact: _caesar("ctf{et_tu_brute_force}", 7),
    solution: "It's a Caesar cipher shifted by 7. Try all 25 shifts and pick the readable one - the flag itself hints at the method.",
    cards: [
      { front: "How do you break a Caesar cipher with an unknown shift?", back: "Brute force all 25 shifts and pick the readable output, or use letter-frequency analysis (E is most common in English).", tags: ["crypto", "classical-cipher", "caesar"] },
      { front: "What is ROT13?", back: "A Caesar cipher with a fixed shift of 13. It's its own inverse - applying it twice returns the original.", tags: ["crypto", "classical-cipher", "caesar"] },
    ],
  },
  {
    id: "hex-dump", title: "Hexadecimal Homework", category: "forensics", difficulty: "easy", points: 50,
    description: "A blob of hex bytes recovered from a memory dump. Turn the bytes back into text.",
    hint: "Each pair of hex digits is one byte / one ASCII character. 0x63 = 'c'.",
    flag: "ctf{hex_to_ascii}",
    artifact: _hex("ctf{hex_to_ascii}"),
    solution: "Convert hex to ASCII: echo <hex> | xxd -r -p, or Python bytes.fromhex(...).",
    cards: [
      { front: "What ASCII character is the hex byte 0x41?", back: "'A' (65 decimal). 0x61 is 'a'. Hex 0x30-0x39 map to digits '0'-'9'.", tags: ["forensics", "encoding", "hex"] },
      { front: "Which tool reverses a plain hex dump back to raw bytes?", back: "xxd -r -p (or CyberChef 'From Hex', or Python bytes.fromhex).", tags: ["forensics", "tools", "hex"] },
    ],
  },
  {
    id: "binary-message", title: "Ones and Zeros", category: "misc", difficulty: "easy", points: 50,
    description: "Intercepted transmission. Just bits - group them and decode.",
    hint: "Eight bits per group = one byte = one ASCII character.",
    flag: "ctf{01_to_ascii}",
    artifact: _binary("ctf{01_to_ascii}"),
    solution: "Split into 8-bit groups, read each as a binary number, map to ASCII. int('01100011', 2) == 99 == 'c'.",
    cards: [
      { front: "How many bits are in one byte, and what does one byte usually encode in ASCII?", back: "8 bits = 1 byte = one ASCII character (values 0-127 for standard ASCII).", tags: ["misc", "encoding", "binary"] },
    ],
  },
  {
    id: "hash-cracker", title: "Identify and Crack", category: "crypto", difficulty: "easy", points: 75,
    description: "A password hash pulled from a leaked database. Identify the algorithm, crack it, and wrap the plaintext as ctf{plaintext}.",
    hint: "32 hex characters = one very common (and broken) algorithm. This particular hash is THE textbook example.",
    flag: "ctf{password}",
    artifact: "5f4dcc3b5aa765d61d8327deb882cf99",
    solution: "32 hex chars = MD5. This is the well-known MD5 of 'password' - found instantly in any rainbow table / hashcat wordlist. Flag: ctf{password}.",
    cards: [
      { front: "A hash is exactly 32 hexadecimal characters. Which algorithm is it most likely?", back: "MD5 (128-bit). SHA-1 is 40 hex chars, SHA-256 is 64. MD5 is broken - never use it for passwords.", tags: ["crypto", "hashing", "md5"] },
      { front: "Why is an unsalted MD5 password hash easy to crack?", back: "It's fast to compute and unsalted, so precomputed rainbow tables / huge wordlists reverse common passwords instantly. Salting + slow KDFs (bcrypt/argon2) defend against this.", tags: ["crypto", "hashing", "passwords"] },
    ],
  },
  {
    id: "xor-single-byte", title: "XOR Marks the Spot", category: "reversing", difficulty: "medium", points: 125,
    description: "Ciphertext (hex) produced by XORing the plaintext with a single secret byte. Recover the plaintext.",
    hint: "You KNOW every flag starts with 'ctf{'. XOR the first ciphertext byte with 'c' to recover the key, then XOR everything.",
    flag: "ctf{xor_key_recovered}",
    artifact: _xorHex("ctf{xor_key_recovered}", 0x2a),
    solution: "Known-plaintext attack: key = firstCipherByte XOR ord('c') = 0x2A. XOR every byte with 0x2A to get the flag.",
    cards: [
      { front: "What property makes XOR reversible in a cipher?", back: "XOR is its own inverse: (P ^ K) ^ K = P. Encrypt and decrypt use the identical operation with the same key.", tags: ["reversing", "crypto", "xor"] },
      { front: "How do you recover a single-byte XOR key when you know part of the plaintext?", back: "Known-plaintext attack: key = ciphertextByte XOR knownPlaintextByte. One known byte reveals the whole key.", tags: ["reversing", "crypto", "xor"] },
    ],
  },
  {
    id: "jwt-none", title: "None Shall Pass", category: "web", difficulty: "medium", points: 100,
    description: "A JSON Web Token from an API. It was signed with the 'none' algorithm - read what's inside.",
    hint: "A JWT is three base64url parts split by dots: header.payload.signature. Decode the middle part.",
    flag: "ctf{alg_none_is_dangerous}",
    artifact:
      _b64url({ alg: "none", typ: "JWT" }) + "." +
      _b64url({ user: "guest", role: "admin", flag: "ctf{alg_none_is_dangerous}" }) + ".",
    solution: "Base64url-decode the payload (middle segment). The 'none' algorithm means the token is unsigned and fully trusted - an attacker can forge any claims.",
    cards: [
      { front: "What are the three dot-separated parts of a JWT?", back: "header.payload.signature - each base64url-encoded. Header + payload are readable by anyone; the signature only proves integrity.", tags: ["web", "auth", "jwt"] },
      { front: "Why is the JWT 'alg: none' setting dangerous?", back: "It tells the server to accept the token with no signature verification, so an attacker can forge arbitrary claims (e.g. role=admin). Servers must reject 'none'.", tags: ["web", "auth", "jwt"] },
    ],
  },
  {
    id: "log-detective", title: "Log Detective", category: "network", difficulty: "medium", points: 100,
    description: "An auth log from a compromised box. One IP is clearly brute-forcing SSH. Flag is ctf{<attacker_ip>_<their_failed_count>}.",
    hint: "Count the 'Failed password' lines per source IP. The worst offender is your answer.",
    flag: "ctf{203.0.113.7_5}",
    artifact:
      "Jul 19 06:10:01 host sshd[2201]: Failed password for root from 203.0.113.7 port 51002 ssh2\n" +
      "Jul 19 06:10:02 host sshd[2202]: Accepted password for deploy from 198.51.100.9 port 51010 ssh2\n" +
      "Jul 19 06:10:03 host sshd[2203]: Failed password for root from 203.0.113.7 port 51014 ssh2\n" +
      "Jul 19 06:10:04 host sshd[2204]: Failed password for admin from 192.0.2.44 port 51020 ssh2\n" +
      "Jul 19 06:10:05 host sshd[2205]: Failed password for invalid user test from 203.0.113.7 port 51026 ssh2\n" +
      "Jul 19 06:10:06 host sshd[2206]: Failed password for root from 192.0.2.44 port 51030 ssh2\n" +
      "Jul 19 06:10:07 host sshd[2207]: Failed password for root from 203.0.113.7 port 51036 ssh2\n" +
      "Jul 19 06:10:08 host sshd[2208]: Accepted publickey for git from 198.51.100.9 port 51040 ssh2\n" +
      "Jul 19 06:10:09 host sshd[2209]: Failed password for oracle from 203.0.113.7 port 51044 ssh2\n",
    solution: "Tally 'Failed password ... from <ip>' by IP. 203.0.113.7 appears 5 times (vs 192.0.2.44's 2). Flag: ctf{203.0.113.7_5}.",
    cards: [
      { front: "In an SSH auth log, which line pattern signals a failed login attempt?", back: "Failed password for <user> from <ip>. A burst of these from one IP indicates brute-force / password spraying.", tags: ["network", "blue-team", "logs"] },
      { front: "How do you defend against SSH brute-force attacks?", back: "Disable password auth (keys only), disable root login, rate-limit with fail2ban, and alert on repeated failures per source IP.", tags: ["network", "blue-team", "hardening"] },
    ],
  },
  {
    id: "sqli-spot", title: "Injection Inspection", category: "web", difficulty: "easy", points: 75,
    description: "Spot the vulnerability class in this backend code. Flag is ctf{<vuln_name>} in lower_snake_case (two words).",
    hint: "User input is concatenated straight into a database query string. What class of bug is that?",
    flag: "ctf{sql_injection}",
    artifact: "query = \"SELECT * FROM users WHERE name = '\" + request.args[\"name\"] + \"'\"\ncursor.execute(query)",
    solution: "Untrusted input is concatenated into SQL - this is SQL injection. Fix with parameterised queries / prepared statements. Flag: ctf{sql_injection}.",
    cards: [
      { front: "What is the root cause of SQL injection, and the correct fix?", back: "Cause: untrusted input concatenated into a query string. Fix: parameterised queries / prepared statements so input is data, never executable SQL.", tags: ["web", "appsec", "sqli"] },
    ],
  },
];

const BY_ID = Object.fromEntries(CATALOG.map((p) => [p.id, p]));

function stripFlag(p, solved, includeArtifact = true) {
  const out = {
    id: p.id, title: p.title, category: p.category, difficulty: p.difficulty,
    points: p.points, description: p.description, hint: p.hint,
    card_count: p.cards.length, solved,
  };
  if (includeArtifact) out.artifact = p.artifact;
  if (solved) out.solution = p.solution;
  return out;
}

export function listPuzzles(solved, { category, difficulty, status } = {}) {
  const items = [];
  for (const p of CATALOG) {
    if (category && p.category !== category) continue;
    if (difficulty && p.difficulty !== difficulty) continue;
    const isSolved = solved.has(p.id);
    if (status === "solved" && !isSolved) continue;
    if (status === "unsolved" && isSolved) continue;
    items.push(stripFlag(p, isSolved, false));
  }
  return items;
}

export function getPuzzle(id, solved) {
  const p = BY_ID[id];
  return p ? stripFlag(p, solved) : null;
}

export function categories() {
  return [...new Set(CATALOG.map((p) => p.category))].sort();
}

function normalize(flag) {
  let f = flag.trim().toLowerCase();
  if (!f.startsWith("ctf{") && !f.endsWith("}")) f = `ctf{${f}}`;
  return f;
}

export function checkFlag(id, submission) {
  const p = BY_ID[id];
  if (!p) return { correct: false, puzzle: null };
  return { correct: normalize(submission) === p.flag.toLowerCase(), puzzle: p };
}

export const total = () => CATALOG.length;
