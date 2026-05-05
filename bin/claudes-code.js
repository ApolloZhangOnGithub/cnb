#!/usr/bin/env node
'use strict';

/**
 * claudes-code — npm entry point.
 *
 * Resolves the project root (works for both local and global npm installs),
 * then delegates to the Bash entry script `bin/claudes-code`.
 */

const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');

// __dirname always resolves to the real file location (not symlink target),
// so this works correctly for `npm install -g` as well as `npm link`.
const PROJECT_ROOT = path.resolve(__dirname, '..');
const BASH_SCRIPT = path.join(PROJECT_ROOT, 'bin', 'claudes-code');

if (!fs.existsSync(BASH_SCRIPT)) {
  console.error(`FATAL: ${BASH_SCRIPT} not found`);
  process.exit(1);
}

const args = process.argv.slice(2);

const child = spawn('bash', [BASH_SCRIPT, ...args], {
  stdio: 'inherit',
  cwd: process.cwd(),
  env: process.env,
});

child.on('exit', (code, signal) => {
  if (signal) {
    process.exit(128 + (require('os').constants.signals[signal] || 0));
  }
  process.exit(code || 0);
});
