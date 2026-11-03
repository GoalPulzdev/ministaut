"use strict";
const assert = require("node:assert/strict");
const f = require("./assets/models.mjs");
const roea = {
  event_key: "6aaceecebfe408c38e1712dd",
  title: "Rosenborg – Røa",
};
const molde = {
  event_key: "6a9a7e3f3f93920b289b0675",
  title: "Rosenborg – Molde",
};
assert.equal(f.categoryFor(roea), "women");
assert.equal(f.categoryFor(molde), "men");
assert.equal(f.venueFor(roea), "koteng_arena");
assert.equal(f.venueFor(molde), "lerkendal");
assert.equal(f.teamFromURL([roea, molde], "?lag=kvinner"), "women");
assert.equal(
  f.teamFromURL([roea, molde], "?lag=rbk&kamp=6aaceecebfe408c38e1712dd"),
  "women",
  "deep link overrides mismatching team query",
);
assert.equal(
  f.teamFromURL([roea, molde], "?lag=kvinner&kamp=6a9a7e3f3f93920b289b0675"),
  "men",
  "old RBK deep links work",
);
assert.equal(
  f.categoryFor({ team_category: "women", event_key: "new-match" }),
  "women",
);
assert.equal(f.venueFor({ venue_id: "koteng_arena" }), "koteng_arena");
console.log("PASS: metadata, legacy matches and deep-link team selection");
