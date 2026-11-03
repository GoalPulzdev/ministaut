"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs"),
  path = require("node:path");
const html = fs.readFileSync(path.join(__dirname, "index.html"), "utf8");
const result = require("./assets/models.mjs");
const measure = (id, h, available, locked = []) => ({
  id,
  observed_at: new Date(Date.UTC(2026, 9, 24, h, 0, 0)).toISOString(),
  available_seated: available,
  locked_fields: locked,
});
const scans = [measure("a", 1, 100), measure("b", 3, 90), measure("c", 23, 70)];

assert.equal(
  result.historical24(scans, scans[2]).id,
  "a",
  "nearest 24-hour reading",
);
assert.equal(
  result.historical24(scans, scans[1]),
  null,
  "avoid fabricating 24h",
);
assert.equal(
  result.historical24([...scans, measure("locked", 1, 99, ["AA"])], scans[2])
    .id,
  "a",
  "scope differs",
);
assert.equal(result.sectionHeat(-50), "strong");
assert.equal(result.sectionHeat(-20), "medium");
assert.equal(result.sectionHeat(-1), "low");
assert.equal(result.sectionHeat(0), "flat");
assert.equal(result.sectionHeat(7), "increase");
assert.equal(result.sectionHeat(null), "unknown");
assert.match(result.sectionDeltaLabel(-3), /færre ledige/);
assert.match(result.sectionDeltaLabel(4), /flere ledige/);
for (const id of [
  "viewAvailability",
  "viewHeat",
  "sectionRecords",
  "heatStatus",
])
  assert.ok(html.includes('id="' + id + '"'), id + " HTML hook");
console.log(
  "PASS: JS parser, missing 24h, scope, heat bands, delta semantics and DOM hooks",
);
