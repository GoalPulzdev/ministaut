// Pure ticket calculations. No DOM, network, storage, or scanner writes.
const HOUR = 3_600_000;

const fmt = (value) =>
  typeof value === "number" && Number.isFinite(value)
    ? new Intl.NumberFormat("nb-NO").format(value)
    : "—";
const date = (value) =>
  new Date(value).toLocaleString("nb-NO", {
    timeZone: "Europe/Oslo",
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
const comparable = (a, b) =>
  !!(
    a &&
    b &&
    JSON.stringify([...(a.locked_fields || [])].sort()) ===
      JSON.stringify([...(b.locked_fields || [])].sort())
  );
const signed = (n) =>
  n === null || n === undefined ? "—" : (n > 0 ? "+" : "") + fmt(n);
const ageInMinutes = (time) =>
  Math.max(0, Math.floor((Date.now() - new Date(time).getTime()) / 60000));
const overdue = (time) => !time || ageInMinutes(time) > 95;
const ageLabel = (time) => {
  if (!time) return "Venter på første telling";
  const minutes = ageInMinutes(time);
  const elapsed =
    minutes < 2
      ? "akkurat nå"
      : minutes < 60
        ? "for " + minutes + " min siden"
        : minutes < 180
          ? "for " +
            Math.floor(minutes / 60) +
            " t" +
            (minutes % 60 ? " " + (minutes % 60) + " min" : "") +
            " siden"
          : minutes < 1440
            ? "for " + Math.floor(minutes / 60) + " timer siden"
            : "den " + date(time);
  return overdue(time)
    ? "Ny telling avventes · målt " + elapsed
    : "Sist målt " + elapsed;
};

const WOMEN_KEYS = new Set(["6aaceecebfe408c38e1712dd"]);
function categoryFor(match) {
  return match.team_category === "women"
    ? "women"
    : match.team_category === "men"
      ? "men"
      : WOMEN_KEYS.has(match.event_key)
        ? "women"
        : "men";
}
function venueFor(match) {
  return match.venue_id === "koteng_arena" || match.venue_id === "lerkendal"
    ? match.venue_id
    : WOMEN_KEYS.has(match.event_key)
      ? "koteng_arena"
      : "lerkendal";
}
// A match counts as played this long after kickoff (same rule as Scanner Control's archive).
const PLAYED_AFTER_MS = 2 * 3600000;
function isPlayed(match, now = Date.now()) {
  const k = Date.parse(match?.kickoff_at || "");
  return Number.isFinite(k) && now >= k + PLAYED_AFTER_MS;
}
// Season passes share the verified seat inventory but have no kickoff or match forecast.
// The scanner currently records them in the same match table; do not treat a
// missing kickoff alone as proof that an event is a season pass.
function isSeasonPass(match) {
  return String(match?.title || "").toLocaleLowerCase("nb-NO").includes("sesongkort");
}
function teamFromURL(items, search = "") {
  try {
    const q = new URLSearchParams(search),
      linked = items.find((m) => m.event_key === q.get("kamp"));
    return linked
      ? categoryFor(linked)
      : q.get("lag") === "kvinner"
        ? "women"
        : "men";
  } catch {
    return "men";
  }
}

const PROJECTION_HORIZON_DAYS = 60,
  PROJECTION_MAX_SEATED = 19015;
function median(numbers) {
  const sorted = [...numbers].sort((a, b) => a - b),
    m = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[m] : (sorted[m - 1] + sorted[m]) / 2;
}
function kickoffForecast(
  records,
  kickoffUtc,
  now = Date.now(),
  allowStale = false,
) {
  const kickoff = new Date(kickoffUtc || "").getTime();
  if (!Number.isFinite(kickoff))
    return { status: "unavailable", reason: "Kampstart er ikke bekreftet" };
  const horizon = kickoff - now;
  if (horizon <= 0)
    return { status: "unavailable", reason: "Kampen har startet" };
  if (horizon > PROJECTION_HORIZON_DAYS * 86400000)
    return { status: "unavailable", reason: "Mer enn 60 dager til kampstart" };
  const sorted = records
    .filter(
      (p) =>
        Number.isFinite(p.available_seated) &&
        Number.isFinite(new Date(p.observed_at).getTime()) &&
        p.available_seated >= 0 &&
        p.available_seated <= PROJECTION_MAX_SEATED,
    )
    .sort((a, b) => new Date(a.observed_at) - new Date(b.observed_at));
  if (!sorted.length)
    return { status: "unavailable", reason: "Venter på første telling" };
  const last = sorted.at(-1);
  if (overdue(last.observed_at) && !allowStale)
    return { status: "unavailable", reason: "Avventer en fersk måling" };
  const lastTime = new Date(last.observed_at).getTime();
  const sample = sorted
    .filter(
      (p) =>
        comparable(p, last) &&
        new Date(p.observed_at).getTime() >= lastTime - 10 * 86400000,
    )
    .slice(-60);
  if (sample.length < 5)
    return {
      status: "unavailable",
      reason: "Trenger minst fem sammenlignbare tellinger",
    };
  const span =
    new Date(sample.at(-1).observed_at) - new Date(sample[0].observed_at);
  if (span < 12 * 3600000)
    return {
      status: "unavailable",
      reason: "Trenger målinger over minst 12 timer",
    };
  const slopes = [];
  for (let i = 0; i < sample.length; i++) {
    for (let j = i + 1; j < sample.length; j++) {
      const hours =
        (new Date(sample[j].observed_at) - new Date(sample[i].observed_at)) /
        3600000;
      if (hours >= 2)
        slopes.push(
          (sample[j].available_seated - sample[i].available_seated) / hours,
        );
    }
  }
  if (slopes.length < 3)
    return {
      status: "unavailable",
      reason: "Trenger flere målinger med tidsavstand",
    };
  const longPace = Math.max(
    0,
    (sample[0].available_seated - last.available_seated) /
      ((lastTime - new Date(sample[0].observed_at).getTime()) / 3600000),
  );
  const recent = sample.slice(-3);
  const recentHours =
    (new Date(recent.at(-1).observed_at) - new Date(recent[0].observed_at)) /
    3600000;
  const recentPace =
    recentHours >= 4
      ? Math.max(
          0,
          (recent[0].available_seated - last.available_seated) / recentHours,
        )
      : longPace;
  const rate = -(recentHours >= 6
    ? recentPace
    : 0.65 * recentPace + 0.35 * longPace);
  const mad = median(slopes.map((x) => Math.abs(x - rate)));
  const forwardHours = (kickoff - lastTime) / 3600000;
  if (forwardHours <= 0)
    return { status: "unavailable", reason: "Kampstart er passert" };
  // Conservative business rule: inventory in our forecast must never grow
  // beyond the latest observed available seats. Do not extrapolate increases.
  const ceiling = last.available_seated;
  const effectiveRate = Math.min(0, rate);
  // Gradually reduce long-horizon extrapolation instead of extending an early rush for weeks.
  const pacedHours = 14 * 24 * (1 - Math.exp(-forwardHours / (14 * 24)));
  const projected = Math.max(
    0,
    Math.min(ceiling, ceiling + effectiveRate * pacedHours),
  );
  /* Scenario spread, not a statistical confidence interval. */
  // Pace-based uncertainty: a fraction of expected decrease, not a multi-week MAD extrapolation.
  const predictedReduction = ceiling - projected;
  const spread = Math.max(
    15,
    Math.min(
      ceiling * 0.12,
      predictedReduction * (0.12 + Math.min(0.08, forwardHours / 1440)),
    ),
  );
  const low = Math.max(0, Math.min(ceiling, Math.floor(projected - spread)));
  const high = Math.max(low, Math.min(ceiling, Math.ceil(projected + spread)));
  const materiallyUncertain =
    high - low > Math.max(2500, last.available_seated * 0.75);
  const early = forwardHours > 14 * 24;
  if (materiallyUncertain && !early)
    return {
      status: "unavailable",
      reason: "Utviklingen er for ujevn til et meningsfullt anslag",
    };
  return {
    status: "projected",
    center: Math.round(projected),
    low,
    high,
    count: sample.length,
    early,
    materiallyUncertain,
  };
}

/**
 * A non-live snapshot may still carry a useful historical estimate.
 * Return it clearly labeled as stale; never imply it uses current inventory.
 * The ordinary calculation keeps its original V1 freshness threshold.
 */
function displayedForecast(records, kickoffUtc) {
  const live = kickoffForecast(records, kickoffUtc);
  if (live.status === "projected") return { ...live, stale: false };
  if (live.reason !== "Avventer en fersk måling") return live;
  const last = records.at(-1);
  const measured = Date.parse(last?.observed_at || "");
  const kickoff = Date.parse(kickoffUtc || "");
  const now = Date.now();
  // Never display a frozen forecast after kickoff or when the last
  // accepted measurement is more than 12 hours old.
  if (
    !Number.isFinite(measured) ||
    !Number.isFinite(kickoff) ||
    kickoff <= now ||
    now - measured > 12 * 3600000 ||
    now - measured < 0
  )
    return live;
  const historical = kickoffForecast(records, kickoffUtc, measured, true);
  return historical.status === "projected"
    ? { ...historical, stale: true, measuredAt: last.observed_at }
    : live;
}

// Separate, deliberately linear "what if" scenario. NOT a verified sell-out forecast.
// Compare the last accepted snapshot with the nearest same-scope snapshot 10–14h earlier.
function paceToZero12h(records, kickoffUtc, now = Date.now()) {
  const kickoff = Date.parse(kickoffUtc || "");
  if (!Number.isFinite(kickoff) || kickoff <= now) return null;
  const sorted = records
    .filter(
      (x) =>
        Number.isFinite(x.available_seated) &&
        x.available_seated >= 0 &&
        Number.isFinite(Date.parse(x.observed_at)),
    )
    .slice()
    .sort((a, b) => Date.parse(a.observed_at) - Date.parse(b.observed_at));
  const latest = sorted.at(-1);
  if (!latest || overdue(latest.observed_at) || latest.available_seated === 0)
    return null;
  const end = Date.parse(latest.observed_at);
  const past = sorted
    .slice(0, -1)
    .filter((x) => comparable(x, latest))
    .map((x) => ({ x, hours: (end - Date.parse(x.observed_at)) / 3600000 }))
    .filter((x) => x.hours >= 10 && x.hours <= 14)
    .sort((a, b) => Math.abs(a.hours - 12) - Math.abs(b.hours - 12))[0];
  if (!past) return null;
  const decrease = past.x.available_seated - latest.available_seated;
  if (decrease <= 0) return null;
  const perHour = decrease / past.hours;
  if (perHour < 0.25) return null;
  const zeroAt = end + (latest.available_seated / perHour) * 3600000;
  // Don't present a date after kickoff as a pre-match zero-availability event.
  if (zeroAt >= kickoff)
    return { status: "after_kickoff", perHour, hours: past.hours };
  return { status: "before_kickoff", zeroAt, perHour, hours: past.hours };
}

function dailyPulse(records) {
  if (!records.length) return null;
  const sorted = records
    .slice()
    .sort((a, b) => new Date(a.observed_at) - new Date(b.observed_at));
  const latest = sorted.at(-1),
    end = new Date(latest.observed_at).getTime();
  const candidates = sorted.slice(0, -1).filter((p) => {
    const hours = (end - new Date(p.observed_at).getTime()) / 3600000;
    return comparable(p, latest) && hours >= 18 && hours <= 30;
  });
  if (!candidates.length) return null;
  const near = candidates.reduce((best, p) =>
    Math.abs((end - new Date(p.observed_at).getTime()) / 3600000 - 24) <
    Math.abs((end - new Date(best.observed_at).getTime()) / 3600000 - 24)
      ? p
      : best,
  );
  const hours = (end - new Date(near.observed_at).getTime()) / 3600000;
  // A 26-hour raw delta is not a 24-hour delta. Normalize explicitly.
  // This is a constant-rate estimate, not a measurement at exactly 24h.
  const exact = Math.abs(hours - 24) <= 0.25;
  const raw = latest.available_seated - near.available_seated;
  const difference = exact ? raw : Math.round((raw * 24) / hours);
  return { hours, difference, normalized: !exact, raw };
}
function referencePulse(records, targetHours, toleranceHours) {
  if (!records.length) return null;
  const sorted = records
    .slice()
    .sort((a, b) => new Date(a.observed_at) - new Date(b.observed_at));
  const latest = sorted.at(-1),
    end = new Date(latest.observed_at).getTime();
  const relevant = sorted.slice(0, -1).filter((p) => {
    const hours = (end - new Date(p.observed_at).getTime()) / 3600000;
    return (
      comparable(p, latest) && Math.abs(hours - targetHours) <= toleranceHours
    );
  });
  if (!relevant.length) return null;
  const previous = relevant.reduce((best, p) =>
    Math.abs(
      (end - new Date(p.observed_at).getTime()) / 3600000 - targetHours,
    ) <
    Math.abs(
      (end - new Date(best.observed_at).getTime()) / 3600000 - targetHours,
    )
      ? p
      : best,
  );
  return {
    hours: (end - new Date(previous.observed_at).getTime()) / 3600000,
    difference: latest.available_seated - previous.available_seated,
    previous,
  };
}
function weeklyPulse(records) {
  return referencePulse(records, 168, 24);
}
function momentumPulse(records) {
  // Compare two actual, adjacent ~24h periods, never infer from a one-hour jump.
  const last24 = referencePulse(records, 24, 6);
  if (!last24) return null;
  const previous = last24.previous;
  const older = records.filter(
    (p) =>
      comparable(p, previous) &&
      new Date(p.observed_at) <= new Date(previous.observed_at),
  );
  const old24 = referencePulse(older, 24, 6);
  if (!old24) return null;
  const rateNow = Math.max(0, -last24.difference) / last24.hours;
  const rateOld = Math.max(0, -old24.difference) / old24.hours;
  // Ignore small changes that could simply be measurement noise.
  if (rateNow < 1 && rateOld < 1) return { state: "stable" };
  if (rateOld < 0.25) return { state: rateNow >= 1 ? "faster" : "stable" };
  const ratio = rateNow / rateOld;
  return {
    state: ratio >= 1.3 ? "faster" : ratio <= 0.7 ? "slower" : "stable",
  };
}

const historical24 = (scans, end) => {
  if (!end) return null;
  const endTime = Date.parse(end.observed_at);
  return (
    scans
      .filter((s) => s.id !== end.id && comparable(s, end))
      .map((s) => ({ s, gap: endTime - Date.parse(s.observed_at) }))
      .filter((x) => x.gap >= 18 * 3600000 && x.gap <= 30 * 3600000)
      .sort(
        (a, b) => Math.abs(a.gap - 86400000) - Math.abs(b.gap - 86400000),
      )[0]?.s || null
  );
};
const sectionDeltaLabel = (n) =>
  n == null
    ? "mangler sammenlignbar måling"
    : n < 0
      ? fmt(-n) + " færre ledige"
      : n > 0
        ? fmt(n) + " flere ledige"
        : "uendret";
const sectionHeat = (n) =>
  n == null
    ? "unknown"
    : n > 0
      ? "increase"
      : n === 0
        ? "flat"
        : n <= -40
          ? "strong"
          : n <= -15
            ? "medium"
            : "low";

function stadiumColor(row, locked) {
  if (locked) return "locked";
  if (!row) return "missing";
  if (row.free === 0) return "none";
  const pct = row.free / row.capacity;
  return pct >= 0.5
    ? "ample"
    : pct >= 0.2
      ? "some"
      : pct >= 0.08
        ? "few"
        : "critical";
}

const STAND_GROUPS = [
  {
    name: "Pepsi Max-tribunen",
    codes: "SA RA QA PA OA NA MA Q P O N RB QB PB OB NB MB".split(" "),
  },
  { name: "Adressa-tribunen", codes: "LB KB JB IB HB K J I".split(" ") },
  {
    name: "SpareBank 1-tribunen",
    codes:
      "AB BB CB DB EB FB GB A B C D E F G PRESSE AA BA CA DA EA FA GA".split(
        " ",
      ),
  },
  {
    name: "Coop-tribunen",
    codes: "TA UA VA WA XA TB UB U VB V WB W XB".split(" "),
  },
];

const opponentName = (title) =>
  String(title || "")
    .split(/\s[–-]\s/)
    .pop()
    .trim() || String(title || "");
const sectionName = (code) =>
  code === "VIP"
    ? "VIP"
    : code.startsWith("FELT-")
      ? "Felt " + code.slice(5)
      : "Felt " + code;
const hoursText = (h) =>
  h < 48
    ? Math.round(h) + " t"
    : (Math.round((h / 24) * 10) / 10).toString().replace(".", ",") + " døgn";
function curve(scans, kickoffUtc) {
  const k = Date.parse(kickoffUtc || "");
  if (!Number.isFinite(k)) return [];
  // Keep the scan taken just after kickoff (the last planned slot), drop later ones.
  return scans
    .map((s) => ({
      h: (k - Date.parse(s.observed_at)) / HOUR,
      v: Number(s.available_seated),
    }))
    .filter((p) => Number.isFinite(p.h) && Number.isFinite(p.v) && p.h >= -0.25)
    .sort((a, b) => b.h - a.h);
}
// Linear reading of a curve at h hours before kickoff; null outside the measured
// period or across a gap too long to interpolate honestly.
function valueAt(points, h) {
  if (!points.length || h > points[0].h || h < points.at(-1).h) return null;
  const exact = points.find((p) => p.h === h);
  if (exact) return exact.v;
  for (let i = 0; i < points.length - 1; i++) {
    const a = points[i],
      b = points[i + 1];
    if (a.h >= h && h >= b.h) {
      if (a.h - b.h > 12) return null;
      return a.h === b.h
        ? b.v
        : Math.round(a.v + ((b.v - a.v) * (a.h - h)) / (a.h - b.h));
    }
  }
  return null;
}
// What happened in earlier matches from the same point to kickoff, applied to now.
// Two readings per match: the same share of seats left, and the same seat count sold.
function historyForecast(now, refs) {
  if (!now || now.h <= 0.5) return null;
  const basis = [];
  for (const r of refs) {
    const at = valueAt(r.points, now.h),
      last = r.points.at(-1);
    if (at === null || !last || last.h > 2 || at <= 0) continue;
    const ratio = Math.min(
      now.v,
      Math.max(0, Math.round((now.v * last.v) / at)),
    );
    const diff = Math.min(now.v, Math.max(0, now.v + last.v - at));
    basis.push({ title: r.title, at, final: last.v, ratio, diff });
  }
  if (!basis.length) return null;
  const all = basis.flatMap((b) => [b.ratio, b.diff]);
  return {
    center: Math.round(median(basis.map((b) => (b.ratio + b.diff) / 2))),
    low: Math.min(...all),
    high: Math.max(...all),
    basis,
  };
}
// Rank fields by how early they ran out in earlier matches. A field already at 0
// when tracking began is left out: we cannot tell when it went.
function rankFastSections(refs) {
  const stats = new Map();
  for (const r of refs) {
    for (const [code, series] of r.sections) {
      if (!series.length || series[0].free === 0 || code === "PRESSE") continue;
      const empty = series.find((p) => p.free === 0),
        last = series.at(-1);
      const s = stats.get(code) || {
        code,
        emptyHours: [],
        finalShare: [],
        titles: [],
      };
      if (empty) s.emptyHours.push(empty.h);
      s.finalShare.push(last.capacity ? last.free / last.capacity : 1);
      s.titles.push(r.title);
      stats.set(code, s);
    }
  }
  return [...stats.values()]
    .map((s) => ({
      code: s.code,
      n: s.titles.length,
      titles: s.titles,
      emptyCount: s.emptyHours.length,
      emptyHours: s.emptyHours.length ? median(s.emptyHours) : null,
      finalShare: median(s.finalShare),
    }))
    .filter((s) => s.emptyCount > 0 || s.finalShare < 0.1)
    .sort(
      (a, b) =>
        b.emptyCount / b.n - a.emptyCount / a.n ||
        (b.emptyHours ?? -1) - (a.emptyHours ?? -1) ||
        a.finalShare - b.finalShare,
    );
}

function dayDrops(scans) {
  const s = scans
    .map((x) => ({
      t: Date.parse(x.observed_at),
      v: Number(x.available_seated),
      locks: JSON.stringify([...(x.locked_fields || [])].sort()),
      at: x.observed_at,
    }))
    .filter((x) => Number.isFinite(x.t) && Number.isFinite(x.v))
    .sort((a, b) => a.t - b.t);
  const out = [];
  for (let i = 0; i < s.length; i++) {
    let best = null;
    for (let j = i - 1; j >= 0; j--) {
      const gap = (s[i].t - s[j].t) / HOUR;
      if (gap > 30) break;
      if (
        gap >= 18 &&
        s[j].locks === s[i].locks &&
        (!best || Math.abs(gap - 24) < Math.abs(best.gap - 24))
      )
        best = { gap, v: s[j].v };
    }
    if (best)
      out.push({
        sold: Math.round(((best.v - s[i].v) * 24) / best.gap),
        at: s[i].at,
      });
  }
  return out;
}
// 100 = a normal day of sales at this venue; above = hotter than usual.
function pressureIndex(scans, baselineDrops) {
  const mine = dayDrops(scans),
    last = mine.at(-1);
  const pool = baselineDrops.map((d) => d.sold).filter((n) => n > 0);
  if (!last || pool.length < 5) return null;
  const base = median(pool);
  if (!(base > 0)) return null;
  const value = Math.max(0, Math.round((100 * last.sold) / base));
  const label =
    value >= 180
      ? "Rekordtrøkk"
      : value >= 125
        ? "Høyt trøkk"
        : value >= 75
          ? "Normalt"
          : value >= 30
            ? "Rolig"
            : "Stille";
  return { value, label, sold: last.sold, base: Math.round(base) };
}
function fullVerdict({ available, mapped, forecast, hist, pace, played }) {
  if (played || !Number.isFinite(available) || !mapped) return null;
  if (available <= mapped * 0.01)
    return {
      level: "hot",
      answer: "Nesten utsolgt",
      reason: "Bare " + fmt(available) + " sitteplasser er ledige nå.",
    };
  if (pace?.status === "before_kickoff")
    return {
      level: "hot",
      answer: "Kan bli utsolgt",
      reason:
        "Med tempoet de siste 12 timene kan sitteplassene være borte før avspark.",
    };
  const est = hist
    ? hist.center
    : forecast?.status === "projected"
      ? forecast.center
      : null;
  if (est === null || !Number.isFinite(est))
    return {
      level: "unknown",
      answer: "For tidlig å si",
      reason: "Svaret kommer nærmere kampen.",
    };
  const share = est / mapped,
    why =
      "Rundt " +
      Math.max(1, Math.round(share * 100)) +
      " % av sitteplassene ser ut til å bli ledige ved avspark.";
  if (share <= 0.01)
    return { level: "hot", answer: "Kan bli utsolgt", reason: why };
  if (share <= 0.05)
    return { level: "warm", answer: "Det blir trangt", reason: why };
  if (share <= 0.2)
    return {
      level: "mild",
      answer: "Godt salg, men plasser igjen",
      reason: why,
    };
  return { level: "calm", answer: "Det blir plasser igjen", reason: why };
}

function seatsTogether(rows, size) {
  return rows
    .filter((r) => r.free >= size && r.section_code !== "PRESSE")
    .sort(
      (a, b) => b.free - a.free || b.free / b.capacity - a.free / a.capacity,
    )
    .slice(0, 6);
}
// Per stand in a played match: share left at kickoff and how much of the sales came in the last 24 h.
function standTiming(sections, groups) {
  const out = [];
  for (const g of groups) {
    // Like the field ranking: a field already at 0 when tracking began was likely never on sale.
    const series = g.codes
      .map((c) => sections.get(c))
      .filter((s) => s && s.length && s[0].free > 0);
    if (!series.length) continue;
    const hours = [...new Set(series.flatMap((s) => s.map((p) => p.h)))].sort(
      (a, b) => b - a,
    );
    const points = hours
      .map((h) => {
        const parts = series.map((s) => s.find((p) => p.h === h));
        return parts.every(Boolean)
          ? { h, v: parts.reduce((a, p) => a + p.free, 0) }
          : null;
      })
      .filter(Boolean);
    if (points.length < 2) continue;
    const capacity = series.reduce((a, s) => a + s[0].capacity, 0),
      first = points[0],
      last = points.at(-1);
    const sold = first.v - last.v,
      at24 = valueAt(points, 24);
    out.push({
      name: g.name,
      capacity,
      finalFree: last.v,
      finalShare: capacity ? last.v / capacity : 1,
      sold,
      share24:
        sold > 0 && at24 !== null
          ? Math.max(0, Math.min(1, (at24 - last.v) / sold))
          : null,
      trackedHours: first.h,
    });
  }
  return out.sort((a, b) => a.finalShare - b.finalShare);
}
// How the last day before kickoff went for a played match.
function matchdaySummary(points) {
  if (points.length < 2) return null;
  const last = points.at(-1),
    at = (h) => valueAt(points, h);
  let busiest = null;
  for (let i = 1; i < points.length; i++) {
    const a = points[i - 1],
      b = points[i],
      span = a.h - b.h;
    if (b.h > 24 || span <= 0 || span > 3) continue;
    const perHour = (a.v - b.v) / span;
    if (!busiest || perHour > busiest.perHour) busiest = { perHour, h: b.h };
  }
  const d24 = at(24),
    d3 = at(3);
  return {
    final: last.v,
    finalH: last.h,
    sold24: d24 === null ? null : d24 - last.v,
    sold3: d3 === null ? null : d3 - last.v,
    busiest,
  };
}

export {
  HOUR,
  fmt,
  date,
  comparable,
  signed,
  ageInMinutes,
  overdue,
  ageLabel,
  WOMEN_KEYS,
  categoryFor,
  venueFor,
  PLAYED_AFTER_MS,
  isPlayed,
  isSeasonPass,
  teamFromURL,
  PROJECTION_HORIZON_DAYS,
  median,
  kickoffForecast,
  displayedForecast,
  paceToZero12h,
  dailyPulse,
  referencePulse,
  weeklyPulse,
  momentumPulse,
  historical24,
  sectionDeltaLabel,
  sectionHeat,
  stadiumColor,
  STAND_GROUPS,
  opponentName,
  sectionName,
  hoursText,
  curve,
  valueAt,
  historyForecast,
  rankFastSections,
  dayDrops,
  pressureIndex,
  fullVerdict,
  seatsTogether,
  standTiming,
  matchdaySummary,
  PROJECTION_MAX_SEATED,
};
