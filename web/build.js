// Create the explicit static output directory expected by Vercel.
const fs = require('node:fs');
const path = require('node:path');
const output = path.join(__dirname, 'public');
fs.mkdirSync(output, { recursive: true });
// V2 is now the main site. Keep V1 at /v1 as a rollback/reference page.
fs.copyFileSync(path.join(__dirname, 'index.html'), path.join(output, 'index.html'));
fs.copyFileSync(path.join(__dirname, 'index.html'), path.join(output, 'v2.html'));
fs.copyFileSync(path.join(__dirname, 'v1.html'), path.join(output, 'v1.html'));
// Push alerts: service worker, install manifest and icons.
for (const file of ['sw.js', 'manifest.webmanifest', 'icon-192.png', 'icon-512.png', 'status.html']) {
  fs.copyFileSync(path.join(__dirname, file), path.join(output, file));
}
console.log('Ministaut V2 production build: /, /v2, V1 backup at /v1, service worker, manifest and /status ready');
