#!/usr/bin/env node
'use strict';

const { spawnSync } = require('child_process');
const { join } = require('path');
const { existsSync } = require('fs');

/**
 * CTF Flashcards CLI — Node.js entry point.
 *
 * Shells out to the bundled Python CLI (cli/). Requires Python 3.11+ on PATH
 * (override with CTF_PYTHON). Arguments are passed as an argv array — never
 * through a shell — and the CLI runs in the caller's working directory so
 * `fix` re-runs commands where the user actually is.
 */

const MIN_PY = [3, 11];
const PKG_ROOT = join(__dirname, '..');

// Each candidate is [command, ...prefixArgs]; `py -3` is the Windows launcher.
const CANDIDATES = [
  process.env.CTF_PYTHON && [process.env.CTF_PYTHON],
  process.env.PYTHON && [process.env.PYTHON],
  ['python3'],
  ['python'],
  process.platform === 'win32' && ['py', '-3'],
].filter(Boolean);

function pythonVersion(cand) {
  const [cmd, ...pre] = cand;
  const r = spawnSync(cmd, [...pre, '-c', 'import sys; print(sys.version_info[0], sys.version_info[1])'], {
    encoding: 'utf8',
    timeout: 5000,
    windowsHide: true,
  });
  if (r.status !== 0 || !r.stdout) return null;
  const [maj, min] = r.stdout.trim().split(/\s+/).map(Number);
  return Number.isFinite(maj) && Number.isFinite(min) ? [maj, min] : null;
}

function findPython() {
  let tooOld = null;
  for (const cand of CANDIDATES) {
    const v = pythonVersion(cand);
    if (!v) continue;
    if (v[0] > MIN_PY[0] || (v[0] === MIN_PY[0] && v[1] >= MIN_PY[1])) return { cand, tooOld: null };
    tooOld = tooOld || `${cand.join(' ')} (${v.join('.')})`;
  }
  return { cand: null, tooOld };
}

function main() {
  const { cand, tooOld } = findPython();
  if (!cand) {
    console.error(`ctf-flashcards: Python ${MIN_PY.join('.')}+ is required but was not found on PATH.`);
    if (tooOld) console.error(`  Found ${tooOld}, which is too old.`);
    console.error('  Install Python from https://python.org, or set CTF_PYTHON to an interpreter path.');
    process.exit(1);
  }

  if (!existsSync(join(PKG_ROOT, 'cli', '__main__.py'))) {
    console.error('ctf-flashcards: the bundled Python CLI (cli/) is missing. Reinstall the package.');
    process.exit(1);
  }

  const args = process.argv.slice(2);
  if (args.length === 0) args.push('--help');

  // Put the package root first on sys.path so a `cli/` directory in the
  // user's cwd can never shadow the bundled one, then run it as __main__.
  const bootstrap =
    'import sys, runpy; sys.path.insert(0, sys.argv.pop(1)); ' +
    "sys.argv[0] = 'ctf-flashcards'; runpy.run_module('cli', run_name='__main__', alter_sys=True)";

  const [cmd, ...pre] = cand;
  const r = spawnSync(cmd, [...pre, '-c', bootstrap, PKG_ROOT, ...args], {
    stdio: 'inherit',
    env: { ...process.env, PYTHONIOENCODING: process.env.PYTHONIOENCODING || 'utf-8' },
  });

  if (r.error) {
    console.error(`ctf-flashcards: failed to start Python: ${r.error.message}`);
    process.exit(1);
  }
  if (r.signal) process.kill(process.pid, r.signal);
  process.exit(r.status === null ? 1 : r.status);
}

main();
