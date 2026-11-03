// Verified schematic geometry; inventory and scanner coordinates are unchanged.
const SEAT_LAYOUT = [
  ["SA", 209, 58, 48, 52],
  ["RA", 264, 58, 52, 52],
  ["QA", 323, 58, 71, 52],
  ["PA", 401, 58, 79, 52],
  ["OA", 487, 58, 78, 52],
  ["NA", 572, 58, 48, 52],
  ["MA", 627, 58, 41, 52],
  ["Q", 272, 117, 75, 28],
  ["P", 354, 117, 75, 28],
  ["O", 436, 117, 75, 28],
  ["N", 518, 117, 75, 28],
  ["RB", 193, 152, 88, 45],
  ["QB", 287, 152, 78, 45],
  ["PB", 371, 152, 79, 45],
  ["OB", 456, 152, 79, 45],
  ["NB", 541, 152, 56, 45],
  ["MB", 603, 152, 47, 45],
  ["TA", 74, 215, 70, 60],
  ["UA", 74, 282, 70, 63],
  ["VA", 74, 352, 70, 63],
  ["WA", 74, 422, 70, 65],
  ["XA", 74, 494, 70, 58],
  ["TB", 149, 215, 40, 24],
  ["UB", 149, 244, 40, 26],
  ["U", 149, 277, 40, 58],
  ["VB", 149, 342, 40, 24],
  ["V", 149, 373, 40, 42],
  ["WB", 149, 423, 40, 24],
  ["W", 149, 453, 40, 47],
  ["XB", 149, 507, 40, 45],
  ["LB", 592, 205, 41, 43],
  ["KB", 592, 255, 41, 49],
  ["JB", 592, 312, 41, 62],
  ["IB", 592, 381, 41, 74],
  ["HB", 592, 462, 41, 89],
  ["K", 658, 277, 46, 67],
  ["J", 658, 352, 46, 68],
  ["I", 658, 428, 46, 70],
  ["AB", 196, 514, 49, 42],
  ["BB", 251, 514, 59, 42],
  ["CB", 316, 514, 64, 42],
  ["DB", 386, 514, 79, 42],
  ["EB", 471, 514, 54, 42],
  ["FB", 531, 514, 26, 42],
  ["GB", 563, 514, 26, 42],
  ["A", 279, 564, 34, 25],
  ["B", 320, 564, 34, 25],
  ["C", 361, 564, 34, 25],
  ["D", 402, 564, 34, 25],
  ["E", 443, 564, 34, 25],
  ["F", 484, 564, 34, 25],
  ["G", 525, 564, 34, 25],
  ["PRESSE", 395, 595, 85, 23],
  ["AA", 205, 624, 49, 40],
  ["BA", 260, 624, 56, 40],
  ["CA", 322, 624, 67, 40],
  ["DA", 395, 624, 85, 40],
  ["EA", 486, 624, 72, 40],
  ["FA", 564, 624, 52, 40],
  ["GA", 622, 624, 43, 40],
];
// Pitch geometry is the single anchor for both longside stands and the rendered turf.
// SEAT_LAYOUT retains field widths + the already checked west/east arrangement;
// sectionTiles() overrides the north/south rail coordinates from this frame.
const pitchBox = Object.freeze({ x: 211, y: 205, w: 364, h: 300 });
const stadiumFrame = Object.freeze({
  centerX: pitchBox.x + pitchBox.w / 2,
  northEdge: pitchBox.y,
  southEdge: pitchBox.y + pitchBox.h,
});
// Real Coop topology: upper TA/UA/VA/WA/XA, separate VIP U/V/W,
// and lower TB/UB/VB/WB/XB against the pitch. Three distinct west lanes.
const coopStand = Object.freeze({
  upperX: pitchBox.x - 158,
  upperW: 69,
  vipX: pitchBox.x - 83,
  vipW: 27,
  lowerX: pitchBox.x - 50,
  lowerW: 32,
});
function sectionTiles() {
  const tiles = SEAT_LAYOUT.map(([code, x, y, w, h]) => ({ code, x, y, w, h }));
  const byCode = new Map(tiles.map((t) => [t.code, t]));
  // Center each continuous north/south rail on the exact pitch midline.
  // Gaps are distances from the outer pitch frame, not absolute SVG Y values.
  const alignRail = (codes, side, pitchGap, spacing = 6) => {
    const rail = codes.map((code) => byCode.get(code));
    if (rail.some((t) => !t || t.h !== rail[0].h))
      throw Error("Invalid stadium rail");
    const span =
      rail.reduce((sum, t) => sum + t.w, 0) + (rail.length - 1) * spacing;
    const y =
      side === "north"
        ? stadiumFrame.northEdge - pitchGap - rail[0].h
        : stadiumFrame.southEdge + pitchGap;
    let x = stadiumFrame.centerX - span / 2;
    rail.forEach((t) => {
      t.x = x;
      t.y = y;
      x += t.w + spacing;
    });
  };
  // North: Pepsi Max outer, VIP middle and the front rail nearest the field.
  alignRail(["SA", "RA", "QA", "PA", "OA", "NA", "MA"], "north", 95);
  alignRail(["Q", "P", "O", "N"], "north", 60, 7);
  alignRail(["RB", "QB", "PB", "OB", "NB", "MB"], "north", 8);
  // South: front rail, VIP boxes, the central press box, then upper rail.
  alignRail(["AB", "BB", "CB", "DB", "EB", "FB", "GB"], "south", 9);
  alignRail(["A", "B", "C", "D", "E", "F", "G"], "south", 59, 7);
  alignRail(["PRESSE"], "south", 90);
  alignRail(["AA", "BA", "CA", "DA", "EA", "FA", "GA"], "south", 119);
  // Position VIP Coop as a dedicated lower-tier band between the A and B
  // sections. Previously VIP U/V/W were interleaved in the same x lane as
  // TB/UB/VB/WB/XB and therefore appeared on the wrong line.
  const coopRows = [
    { upper: "TA", lower: "TB", y: 215, h: 60 },
    { upper: "UA", vip: "U", lower: "UB", y: 282, h: 63 },
    { upper: "VA", vip: "V", lower: "VB", y: 352, h: 63 },
    { upper: "WA", vip: "W", lower: "WB", y: 422, h: 65 },
    { upper: "XA", lower: "XB", y: 494, h: 58 },
  ];
  const placeCoop = (code, x, w, y, h) => {
    if (!code) return;
    const tile = byCode.get(code);
    if (!tile) throw Error("Missing Coop sector " + code);
    Object.assign(tile, { x, y, w, h });
  };
  coopRows.forEach(({ upper, vip, lower, y, h }) => {
    placeCoop(upper, coopStand.upperX, coopStand.upperW, y, h);
    placeCoop(vip, coopStand.vipX, coopStand.vipW, y, h);
    placeCoop(lower, coopStand.lowerX, coopStand.lowerW, y, h);
  });
  if (!(
    coopStand.upperX + coopStand.upperW < coopStand.vipX &&
    coopStand.vipX + coopStand.vipW < coopStand.lowerX &&
    coopStand.lowerX + coopStand.lowerW < pitchBox.x
  ))
    throw Error("Invalid Coop lane spacing");
  if (tiles.length !== 60 || byCode.size !== 60)
    throw Error("Expected 60 distinct stadium sections");
  for (let i = 0; i < tiles.length; i++) {
    const a = tiles[i];
    if (
      a.x < 0 ||
      a.y < 0 ||
      a.w <= 0 ||
      a.h <= 0 ||
      a.x + a.w > 780 ||
      a.y + a.h > 710
    )
      throw Error("Out-of-bounds sector " + a.code);
    if (
      Math.max(a.x, pitchBox.x) <
        Math.min(a.x + a.w, pitchBox.x + pitchBox.w) &&
      Math.max(a.y, pitchBox.y) < Math.min(a.y + a.h, pitchBox.y + pitchBox.h)
    )
      throw Error("Sector inside pitch " + a.code);
    for (let j = i + 1; j < tiles.length; j++) {
      const b = tiles[j];
      if (
        Math.max(a.x, b.x) < Math.min(a.x + a.w, b.x + b.w) &&
        Math.max(a.y, b.y) < Math.min(a.y + a.h, b.y + b.h)
      )
        throw Error("Overlapping sectors " + a.code + " / " + b.code);
    }
  }
  return tiles;
}

export { sectionTiles, pitchBox, stadiumFrame, coopStand };
