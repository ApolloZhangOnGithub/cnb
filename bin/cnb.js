#!/usr/bin/env node
'use strict';

/**
 * cnb — npm entry point.
 */

const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');

const PROJECT_ROOT = path.resolve(__dirname, '..');
const BASH_SCRIPT = path.join(PROJECT_ROOT, 'bin', 'cnb');

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
