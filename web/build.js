// Create the explicit static output directory expected by Vercel.
const fs = require('node:fs');
const path = require('node:path');
const output = path.join(__dirname, 'public');
fs.mkdirSync(output, { recursive: true });
fs.copyFileSync(path.join(__dirname, 'index.html'), path.join(output, 'index.html'));
fs.copyFileSync(path.join(__dirname, 'v2.html'), path.join(output, 'v2.html'));
console.log('Ministaut static build: public/index.html ready');
