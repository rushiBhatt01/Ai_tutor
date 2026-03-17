const path = require('path');
const { createRequire } = require('module');

const packageDir = __dirname;
const command = process.argv[2] || 'dev';
const extraArgs = process.argv.slice(3);

process.chdir(packageDir);

const localRequire = createRequire(path.join(packageDir, 'package.json'));
const nextBin = localRequire.resolve('next/dist/bin/next');

process.argv = [process.execPath, nextBin, command, ...extraArgs];
localRequire(nextBin);
