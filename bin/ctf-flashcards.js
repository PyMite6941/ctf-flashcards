#!/usr/bin/env node
'use strict';

const { execSync } = require('child_process');
const { join } = require('path');
const { existsSync } = require('fs');

/**
 * CTF Flashcards CLI — Node.js entry point.
 *
 * Shells out to the bundled Python CLI. Requires Python 3.11+ to be on PATH.
 * The Python CLI (cli/) is bundled with this package.
 */

const PYTHON_CMDS = [
  process.env.CTF_PYTHON,
  process.env.PYTHON,
  'python3',
  'python',
  'py',
].filter(Boolean);

function findPython() {
  for (const cmd of PYTHON_CMDS) {
    try {
      execSync(`"${cmd}" --version`, { stdio: 'pipe', timeout: 5000 });
      return cmd;
    } catch (_) {
      // not available
    }
  }
  return null;
}

function findCliDir() {
  // The cli/ directory is bundled with this package at <pkg_root>/cli/
  const pkgRoot = join(__dirname, '..');
  const cliDir = join(pkgRoot, 'cli');
  if (existsSync(join(cliDir, '__main__.py'))) {
    return cliDir;
  }
  // Fallback: check cwd
  const cwdCli = join(process.cwd(), 'cli');
  if (existsSync(join(cwdCli, '__main__.py'))) {
    return cwdCli;
  }
  return null;
}

function main() {
  const python = findPython();
  if (!python) {
    console.error('ctf-flashcards: Python 3.11+ is required but not found on PATH.');
    console.error('Install Python from https://python.org and try again.');
    process.exit(1);
  }

  const pkgRoot = join(__dirname, '..');
  const cliDir = findCliDir();
  if (!cliDir) {
    console.error(
      'ctf-flashcards: Could not locate the bundled Python CLI (cli/). ' +
      'The package may be corrupted. Reinstall with npm.',
    );
    process.exit(1);
  }

  const args = process.argv.slice(2);

  // If no args, show help
  if (args.length === 0) {
    args.push('--help');
  }

  try {
    execSync(`"${python}" -m cli ${args.map(a => `"${a}"`).join(' ')}`, {
      cwd: pkgRoot,
      stdio: 'inherit',
      env: { ...process.env, PYTHONPATH: pkgRoot },
    });
  } catch (err) {
    if (err.exitCode !== undefined) {
      process.exit(err.exitCode);
    }
    console.error(`ctf-flashcards: ${err.message}`);
    process.exit(1);
  }
}

main();
