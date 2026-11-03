#!/usr/bin/env node
'use strict';

// Smoke test for the npm package: packs the tarball, unpacks it, and runs the
// bundled CLI from an unrelated directory against a throwaway DB. Catches
// files missing from package.json "files" and launcher regressions.

const { execSync, spawnSync } = require('child_process');
const { mkdtempSync, readdirSync, rmSync } = require('fs');
const { join } = require('path');
const os = require('os');

const root = join(__dirname, '..');
const tmp = mkdtempSync(join(os.tmpdir(), 'ctf-smoke-'));
let failed = 0;

function check(name, cond, detail = '') {
  console.log(`${cond ? 'ok' : 'FAIL'}: ${name}${cond || !detail ? '' : `\n${detail}`}`);
  if (!cond) failed++;
}

try {
  execSync(`npm pack --silent --pack-destination "${tmp}"`, { cwd: root, stdio: 'pipe' });
  const tgz = readdirSync(tmp).find((f) => f.endsWith('.tgz'));
  execSync(`tar xzf "${tgz}"`, { cwd: tmp });

  const bin = join(tmp, 'package', 'bin', 'ctf-flashcards.js');
  const work = join(tmp, 'elsewhere');
  require('fs').mkdirSync(work);
  const env = { ...process.env, CTF_CLI_DB: join(tmp, 'smoke.db') };
  const run = (...args) => spawnSync(process.execPath, [bin, ...args], { cwd: work, env, encoding: 'utf8' });

  let r = run('--help');
  check('--help exits 0', r.status === 0, r.stderr);
  check('--help lists subcommands', /capture/.test(r.stdout));

  r = run('init');
  check('init exits 0', r.status === 0, r.stderr);

  r = run('capture', 'ls -la "/tmp/a b"', '--exit-code', '0');
  check('capture with quoted arg exits 0', r.status === 0, r.stderr);

  r = run('stats');
  check('stats exits 0', r.status === 0, r.stderr);
  check('stats counts the captured command', /"total":\s*1\b/.test(r.stdout), r.stdout);

  r = run('no-such-subcommand');
  check('bad subcommand propagates non-zero exit', r.status !== 0 && r.status !== null);
} finally {
  rmSync(tmp, { recursive: true, force: true });
}

if (failed) {
  console.error(`\n${failed} smoke check(s) failed`);
  process.exit(1);
}
console.log('\nALL SMOKE CHECKS PASSED');
