const assert = require("node:assert/strict");
const { chartDimensions, shortDate } = require("./assets/charts.mjs");
for (const width of [248, 320, 358, 768, 964]) {
  const { W, H, L, R, T, B } = chartDimensions(width);
  assert.equal(
    W,
    width,
    "Axis type must not shrink with a fixed large viewBox",
  );
  assert.ok(W - L - R > 150, "Useful plotting width on a 320px phone");
  assert.ok(H - T - B >= 196, "Useful plot height, independent of width");
}
assert.match(shortDate("2026-11-03T09:23:00Z", true), /3/);
console.log("PASS: chart geometry at 320px phones through desktop");
