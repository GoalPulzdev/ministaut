import fs from "node:fs";
import path from "node:path";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import { execFileSync } from "node:child_process";
import { displayedForecast, STAND_GROUPS } from "../assets/models.mjs";

const root = fileURLToPath(new URL("../", import.meta.url));
execFileSync(process.execPath, [path.join(root, "build.js")]);
const html = fs.readFileSync(path.join(root, "index.html"), "utf8");
const app = fs.readFileSync(path.join(root, "assets/app.mjs"), "utf8");
assert.equal(
  fs.readFileSync(path.join(root, "public/index.html"), "utf8"),
  html,
);
assert.equal(fs.readFileSync(path.join(root, "public/v2.html"), "utf8"), html);
assert.equal(
  fs.readFileSync(path.join(root, "public/v1.html"), "utf8"),
  fs.readFileSync(path.join(root, "v1.html"), "utf8"),
);
for (const asset of [
  "styles.css",
  "app.mjs",
  "models.mjs",
  "stadium-layout.mjs",
  "charts.mjs",
  "match-card.mjs",
]) {
  assert.ok(
    fs.statSync(path.join(root, "public/assets", asset)).size > 0,
    asset,
  );
}
assert.ok(!html.includes("<style>"), "Styles have one owner");
const ids = [...html.matchAll(/\bid="([^"]+)"/g)].map((m) => m[1]);
assert.equal(ids.length, new Set(ids).size, "Unique DOM hooks");
for (const m of app.matchAll(/\$\(['"]([^'"]+)['"]\)/g))
  assert.ok(ids.includes(m[1]), `Missing DOM hook: ${m[1]}`);
assert.equal((html.match(/data-chart-hours="/g) || []).length, 4);
const codes = STAND_GROUPS.flatMap((g) => g.codes);
assert.equal(codes.length, 60);
assert.equal(new Set(codes).size, 60);
const now = Date.now(),
  kickoff = new Date(now + 5 * 86400000).toISOString();
const readings = (age) =>
  Array.from({ length: 20 }, (_, i) => ({
    observed_at: new Date(now - (age + 19 - i) * 3600000).toISOString(),
    available_seated: 4100 - i * 18,
    locked_fields: [],
  }));
assert.equal(displayedForecast(readings(0.5), kickoff).stale, false);
assert.equal(displayedForecast(readings(3), kickoff).stale, true);
assert.notEqual(displayedForecast(readings(13), kickoff).status, "projected");
console.log(
  `PASS: production aliases, asset packaging, ${ids.length} DOM hooks, 60 sectors, forecast freshness`,
);
