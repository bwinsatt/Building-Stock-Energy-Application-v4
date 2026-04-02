#!/usr/bin/env node

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const PKG_PATH = path.resolve(__dirname, '..', 'package.json');

function bumpPatch(version) {
  const parts = version.split('.');
  if (parts.length !== 3 || parts.some((p) => isNaN(Number(p)))) {
    console.error(`Cannot bump patch: "${version}" is not a valid semver string`);
    process.exit(1);
  }
  parts[2] = String(Number(parts[2]) + 1);
  return parts.join('.');
}

function isValidSemver(str) {
  return /^\d+\.\d+\.\d+(-[\w.]+)?(\+[\w.]+)?$/.test(str);
}

const pkg = JSON.parse(fs.readFileSync(PKG_PATH, 'utf-8'));
const currentVersion = pkg.version;
const requestedVersion = process.argv[2];

let newVersion;
if (requestedVersion) {
  if (!isValidSemver(requestedVersion)) {
    console.error(`"${requestedVersion}" is not a valid semver version`);
    process.exit(1);
  }
  newVersion = requestedVersion;
} else {
  newVersion = bumpPatch(currentVersion);
}

console.log(`${currentVersion} -> ${newVersion}`);

pkg.version = newVersion;
fs.writeFileSync(PKG_PATH, JSON.stringify(pkg, null, 2) + '\n');

console.log('Running npm install...');
execSync('npm install', { stdio: 'inherit', cwd: path.resolve(__dirname, '..') });

console.log(`Version set to ${newVersion}`);
