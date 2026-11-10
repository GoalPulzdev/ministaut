import {
  HOUR,
  fmt,
  date,
  comparable,
  overdue,
  ageLabel,
  categoryFor,
  venueFor,
  isPlayed,
  isSeasonPass,
  teamFromURL,
  median,
  displayedForecast,
  paceToZero12h,
  dailyPulse,
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
} from "./models.mjs";
import {
  sectionTiles,
  pitchBox,
  stadiumFrame,
  coopStand,
} from "./stadium-layout.mjs";
import { chartDimensions, shortDate } from "./charts.mjs";
import { createMatchCard } from "./match-card.mjs";

const DB = "https://khetbokxbcujwcurvviu.supabase.co";
const KEY = "sb_publishable_0JuYQgbiXWfx103zy7j85Q_muDiicIL";
const $ = (id) => document.getElementById(id);
function chooseByLink(available) {
  try {
    if (typeof window === "undefined") return null;
    const key = new URLSearchParams(window.location.search).get("kamp");
    return available.find((m) => m.event_key === key)?.id || null;
  } catch {
    return null;
  }
}
function updateShareLink(key) {
  try {
    if (typeof window === "undefined" || !window.history?.replaceState) return;
    const url = new URL(window.location.href);
    url.searchParams.set("lag", activeTeam === "women" ? "kvinner" : "rbk");
    if (key && /^[A-Za-z0-9_-]{8,100}$/.test(key))
      url.searchParams.set("kamp", key);
    else url.searchParams.delete("kamp");
    window.history.replaceState(null, "", url.pathname + url.search + url.hash);
  } catch {
    /* URL state is optional; navigation still works. */
  }
}
let allMatches = [],
  matches = [],
  activeTeam = "men",
  selectedVenue = "lerkendal",
  teamInitialized = false;
let current = null,
  cards = new Map(),
  cardSignature = "",
  selectionVersion = 0,
  refreshPromise = null,
  lastObservedAt = null,
  selectedKickoff = null,
  sectionSelection = null;
function updateAgeIndicator() {
  const badge = $("age");
  const played = isPlayed(matches.find((m) => m.id === current));
  badge.textContent = played
    ? "Kampen er spilt · arkiv"
    : ageLabel(lastObservedAt);
  badge.setAttribute("data-stale", String(!played && overdue(lastObservedAt)));
}

// Coalesce overlapping reads without caching or retrying live inventory.
const pendingReads = new Map();
function load(path) {
  if (pendingReads.has(path)) return pendingReads.get(path);
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 12000);
  const request = fetch(DB + "/rest/v1/" + path, {
    headers: { apikey: KEY },
    cache: "no-store",
    signal: controller.signal,
  })
    .then((res) => {
      if (!res.ok) throw new Error("Datakilden svarte " + res.status);
      return res.json();
    })
    .finally(() => {
      clearTimeout(timer);
      pendingReads.delete(path);
    });
  pendingReads.set(path, request);
  return request;
}

let chartSignature = "";
let chartRangeHours = 168,
  latestChartInput = [];
function wrapWidth() {
  return Math.round($("chart").clientWidth);
}
function graph(points) {
  latestChartInput = points;
  const lastPoint = points.at(-1);
  if (chartRangeHours && lastPoint) {
    const cutoff =
      Date.parse(lastPoint.observed_at) - chartRangeHours * 3600000;
    const filtered = points.filter((p) => Date.parse(p.observed_at) >= cutoff);
    if (filtered.length) points = filtered;
  }
  for (const b of document.querySelectorAll("[data-chart-hours]"))
    b.setAttribute(
      "aria-pressed",
      String(Number(b.dataset.chartHours) === chartRangeHours),
    );
  const wrap = $("chart"),
    count = $("chartCount");
  const prediction = displayedForecast(latestChartInput, selectedKickoff);
  const hasProjection = prediction.status === "projected" && points.length > 1;
  $("chartLegend").hidden = !hasProjection;
  $("chartForecastLabel").textContent = prediction.stale
    ? "Eldre prognose"
    : "Prognose";
  count.textContent = points.length
    ? "Oppdatert " + date(points.at(-1).observed_at)
    : "Venter på tall";
  const signature =
    String(wrapWidth()) +
    "|" +
    String(current) +
    "|" +
    selectedKickoff +
    "|" +
    (hasProjection
      ? [prediction.center, prediction.low, prediction.high].join(":")
      : "none") +
    "|" +
    points
      .map(
        (p) =>
          p.observed_at +
          ":" +
          p.available_seated +
          ":" +
          (p.locked_fields || []).join(","),
      )
      .join("|");
  if (signature === chartSignature) return;
  chartSignature = signature;
  if (!points.length) {
    wrap.className = "chart-wrap empty";
    wrap.textContent = "Ingen målinger registrert ennå.";
    $("inspectTime").textContent = "Siste måling";
    $("inspectValue").textContent = "—";
    $("inspectDelta").textContent =
      "Grafen fylles når nye tellinger kommer inn";
    return;
  }
  const { W, H, L, R, T, B } = chartDimensions(wrap.clientWidth);
  const times = points.map((p) => new Date(p.observed_at).getTime());
  const values = points.map((p) => p.available_seated);
  const start = Math.min(...times),
    lastTime = Math.max(...times);
  const kickoffMs = hasProjection
    ? new Date(selectedKickoff).getTime()
    : lastTime;
  const end = Math.max(lastTime + 1, kickoffMs);
  const forecastValues = hasProjection
    ? [prediction.low, prediction.center, prediction.high]
    : [];
  const min = Math.min(...values, ...forecastValues),
    max = Math.max(...values, ...forecastValues),
    padding = Math.max(48, (max - min) * 0.16);
  const limit = selectedVenue === "koteng_arena" ? 601 : 19015;
  const lo = Math.max(0, min - padding),
    hi = Math.min(limit, Math.max(max + padding, lo + 96));
  const x = (t) => L + ((t - start) / (end - start)) * (W - L - R);
  const y = (v) => T + ((hi - v) / (hi - lo)) * (H - T - B);
  const px = times.map((t, i) => ({ x: x(t), y: y(values[i]) }));
  const path = px
    .map((p, i) => (i ? "L" : "M") + p.x.toFixed(2) + " " + p.y.toFixed(2))
    .join(" ");
  const area =
    path +
    " L" +
    px[px.length - 1].x.toFixed(2) +
    " " +
    (H - B) +
    " L" +
    px[0].x.toFixed(2) +
    " " +
    (H - B) +
    " Z";
  const grid = Array.from({ length: 4 }, (_, i) => {
    const v = lo + ((hi - lo) * i) / 3,
      py = y(v);
    return (
      '<line x1="' +
      L +
      '" x2="' +
      (W - R) +
      '" y1="' +
      py.toFixed(2) +
      '" y2="' +
      py.toFixed(2) +
      '" stroke="#766646" stroke-opacity=".64" />' +
      '<text x="' +
      (L - 10) +
      '" y="' +
      (py + 4).toFixed(2) +
      '" text-anchor="end" fill="#dec48d" font-size="12">' +
      fmt(Math.round(v)) +
      "</text>"
    );
  }).join("");
  const dot =
    px.length === 1
      ? '<circle cx="' +
        px[0].x.toFixed(2) +
        '" cy="' +
        px[0].y.toFixed(2) +
        '" r="4" fill="#e9d9bb" />'
      : "";
  const xlabels =
    '<text x="' +
    L +
    '" y="' +
    (H - 11) +
    '" fill="#dec48d" font-size="12">' +
    shortDate(points[0].observed_at, W < 520) +
    "</text>" +
    (hasProjection
      ? '<text x="' +
        (W - R) +
        '" y="' +
        (H - 11) +
        '" text-anchor="end" fill="#dec48d" font-size="12">Avspark ' +
        shortDate(selectedKickoff, W < 520) +
        "</text>"
      : points.length > 1
        ? '<text x="' +
          (W - R) +
          '" y="' +
          (H - 11) +
          '" text-anchor="end" fill="#dec48d" font-size="12">' +
          shortDate(points[points.length - 1].observed_at, W < 520) +
          "</text>"
        : "");
  const projectedMarkup = hasProjection
    ? (() => {
        const leftX = x(lastTime).toFixed(2),
          rightX = x(kickoffMs).toFixed(2);
        const lastY = y(values[values.length - 1]).toFixed(2),
          midY = y(prediction.center).toFixed(2);
        const lowY = y(prediction.low).toFixed(2),
          highY = y(prediction.high).toFixed(2);
        const band =
          leftX +
          "," +
          lastY +
          " " +
          rightX +
          "," +
          highY +
          " " +
          rightX +
          "," +
          lowY;
        return (
          '<polygon points="' +
          band +
          '" fill="#dec48d" fill-opacity=".17" stroke="none"/>' +
          '<line x1="' +
          leftX +
          '" y1="' +
          lastY +
          '" x2="' +
          rightX +
          '" y2="' +
          midY +
          '" stroke="#dec48d" stroke-width="2.8" stroke-dasharray="8 7" />' +
          '<line x1="' +
          rightX +
          '" y1="' +
          highY +
          '" x2="' +
          rightX +
          '" y2="' +
          lowY +
          '" stroke="#dec48d" stroke-width="4" stroke-opacity=".68" />' +
          '<circle cx="' +
          rightX +
          '" cy="' +
          midY +
          '" r="5" fill="#e9d9bb" />' +
          '<text x="' +
          (W - R - 6) +
          '" y="' +
          Math.max(15, y(prediction.high) - 12).toFixed(2) +
          '" text-anchor="end" fill="#dec48d" font-size="12">Mulig spenn</text>'
        );
      })()
    : "";
  wrap.className = "chart-wrap";
  wrap.innerHTML =
    '<svg viewBox="0 0 ' +
    W +
    " " +
    H +
    '" role="img" tabindex="0" aria-label="Interaktiv graf over ledige sitteplasser. Bruk piltastene for å bla mellom målingene.">' +
    '<defs><linearGradient id="pulseFill" x1="0" y1="0" x2="0" y2="1"><stop stop-color="#e9d9bb" stop-opacity=".27" /><stop offset="1" stop-color="#e9d9bb" stop-opacity=".012" /></linearGradient></defs>' +
    grid +
    '<path d="' +
    area +
    '" fill="url(#pulseFill)"/><path d="' +
    path +
    '" fill="none" stroke="#e9d9bb" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"/>' +
    projectedMarkup +
    dot +
    '<line id="chartFocusLine" class="chart-focus-guide" x1="0" x2="0" y1="' +
    T +
    '" y2="' +
    (H - B) +
    '" stroke="#e9d9bb" stroke-opacity=".65" stroke-width="1.5" stroke-dasharray="4 5"/>' +
    '<circle id="chartFocusHalo" class="endpoint-halo" cx="0" cy="0" r="10" fill="#e9d9bb" opacity=".16" />' +
    '<circle id="chartFocusPoint" cx="0" cy="0" r="5.6" fill="#e9d9bb" stroke="#a58a55" stroke-width="2"/>' +
    xlabels +
    "</svg>";
  const svg = wrap.querySelector("svg"),
    line = wrap.querySelector("#chartFocusLine"),
    halo = wrap.querySelector("#chartFocusHalo"),
    focus = wrap.querySelector("#chartFocusPoint");
  let index = -1,
    sticky = false;
  function inspect(i) {
    if (!Number.isInteger(i) || i < 0 || i >= points.length) return;
    if (i === index) return;
    index = i;
    const point = points[i],
      prev = points[i - 1],
      diff = prev ? point.available_seated - prev.available_seated : null,
      position = px[i];
    $("inspectTime").textContent = date(point.observed_at);
    $("inspectValue").textContent =
      fmt(point.available_seated) + " ledige sitteplasser";
    $("inspectDelta").textContent =
      diff === null
        ? "Første måling"
        : diff < 0
          ? fmt(-diff) + " færre ledige siden forrige"
          : diff > 0
            ? fmt(diff) + " flere ledige siden forrige"
            : "Uendret siden forrige";
    line.setAttribute("x1", position.x.toFixed(2));
    line.setAttribute("x2", position.x.toFixed(2));
    halo.setAttribute("cx", position.x.toFixed(2));
    halo.setAttribute("cy", position.y.toFixed(2));
    focus.setAttribute("cx", position.x.toFixed(2));
    focus.setAttribute("cy", position.y.toFixed(2));
  }
  function fromPointer(ev) {
    const box = svg.getBoundingClientRect();
    if (!box.width) return;
    const virtualX = Math.max(
      L,
      Math.min(W - R, ((ev.clientX - box.left) * W) / box.width),
    );
    let nearest = 0,
      dist = Infinity;
    for (let i = 0; i < px.length; i++) {
      const d = Math.abs(px[i].x - virtualX);
      if (d < dist) {
        dist = d;
        nearest = i;
      }
    }
    inspect(nearest);
  }
  svg.addEventListener("pointermove", (ev) => {
    if (ev.pointerType === "mouse" || ev.pointerType === "pen") fromPointer(ev);
  });
  svg.addEventListener("pointerdown", (ev) => {
    sticky = true;
    fromPointer(ev);
  });
  svg.addEventListener("pointerleave", () => {
    if (!sticky) inspect(points.length - 1);
  });
  svg.addEventListener("keydown", (ev) => {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(ev.key)) return;
    ev.preventDefault();
    sticky = true;
    inspect(
      ev.key === "Home"
        ? 0
        : ev.key === "End"
          ? points.length - 1
          : Math.max(
              0,
              Math.min(
                points.length - 1,
                index + (ev.key === "ArrowRight" ? 1 : -1),
              ),
            ),
    );
  });
  inspect(points.length - 1);
}

/* A scenario for remaining available seats, never an official sell-out probability.
 * Require sustained comparable observations, a fresh scan, and a short horizon.
 * Heuristic spread is not a statistical confidence interval. */
function renderPaceForecast(records) {
  const el = $("paceForecast"),
    result = paceToZero12h(records, selectedKickoff);
  el.hidden = !result || result.status !== "before_kickoff";
  if (el.hidden) return;
  const day = new Intl.DateTimeFormat("nb-NO", {
    timeZone: "Europe/Oslo",
    day: "numeric",
    month: "long",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(result.zeroAt));
  $("paceForecastDate").textContent = day;
  $("paceForecastRate").textContent =
    "Hvis tempoet fortsetter · ca. " +
    fmt(Math.round(result.perHour * 24)) +
    " færre ledige per døgn";
}
function renderForecast(records) {
  const result = displayedForecast(records, selectedKickoff);
  const panel = document.querySelector(".forecast-panel");
  panel.dataset.status = result.stale ? "stale" : result.status;
  const label = $("projection-label");
  if (result.status !== "projected") {
    label.textContent = "";
    $("projection-value").textContent = "For tidlig å si";
    // Data-quantity reasons are for us; supporters get a plain promise instead.
    $("projection-range").textContent = /^(Kampen|Mer enn 60)/.test(
      result.reason || "",
    )
      ? result.reason
      : "Kommer når vi har fulgt salget litt lenger.";
    $("projection-subtitle").textContent = "";
    return;
  }
  if (result.stale) {
    const measuredAt = date(result.measuredAt);
    label.textContent = "SISTE PROGNOSE · IKKE OPPDATERT";
    $("projection-subtitle").textContent = "Fra telling " + measuredAt + ".";
    $("projection-value").textContent = fmt(result.center) + " ledige";
    $("projection-range").textContent =
      "Trolig " + fmt(result.low) + "–" + fmt(result.high) + " ledige";
    return;
  }
  label.textContent = "";
  $("projection-subtitle").textContent = result.early
    ? "Tidlig anslag. Mye kan endre seg."
    : result.low === 0
      ? "Det kan bli svært få plasser igjen."
      : "";
  $("projection-value").textContent =
    result.early && result.materiallyUncertain
      ? "Tidlig anslag"
      : fmt(result.center) + " ledige";
  $("projection-range").textContent =
    "Trolig " + fmt(result.low) + "–" + fmt(result.high) + " ledige";
}

// Use an actual prior observed scan near 24 hours ago, never treat a
// shorter scan interval as a full day's change.
function render(scans) {
  const records = scans
    .slice()
    .sort((a, b) => new Date(a.observed_at) - new Date(b.observed_at));
  const last = records.at(-1),
    prev = records.at(-2);
  $("available").textContent = last ? fmt(last.available_seated) : "—";
  lastObservedAt = last?.observed_at || null;
  $("shareMatch").disabled = !last;
  updateAgeIndicator();
  const scoped = last ? records.filter((p) => comparable(p, last)) : [];
  const pulse = dailyPulse(scoped);
  const pulseElement = $("dailyPulse");
  pulseElement.hidden = !pulse;
  if (pulse) {
    const n = fmt(Math.abs(pulse.difference));
    pulseElement.dataset.trend =
      pulse.difference < 0 ? "down" : pulse.difference > 0 ? "up" : "flat";
    pulseElement.textContent =
      "24 t · " +
      (pulse.difference < 0
        ? n + " færre ledige"
        : pulse.difference > 0
          ? n + " flere ledige"
          : "uendret");
    pulseElement.title = pulse.normalized
      ? "24-timers beregnet gjennomsnitt fra " +
        pulse.hours.toFixed(1).replace(".", ",") +
        " timers måleintervall"
      : "Målt endring over omtrent 24 timer";
  }
  const week = weeklyPulse(scoped),
    weekElement = $("weekPulse");
  weekElement.hidden = !week;
  if (week) {
    weekElement.dataset.trend =
      week.difference < 0 ? "down" : week.difference > 0 ? "up" : "flat";
    weekElement.textContent =
      "7 døgn · " +
      (week.difference < 0
        ? fmt(-week.difference) + " færre ledige"
        : week.difference > 0
          ? fmt(week.difference) + " flere ledige"
          : "uendret");
  }
  const momentum = momentumPulse(scoped),
    momentumElement = $("pulseMomentum");
  momentumElement.hidden = !momentum;
  if (momentum) {
    momentumElement.dataset.trend = momentum.state;
    momentumElement.textContent =
      "Tempo · " +
      (momentum.state === "faster"
        ? "øker"
        : momentum.state === "slower"
          ? "avtar"
          : "stabilt");
  }
  renderForecast(records);
  renderPaceForecast(records);
  lastRecords = records;
  renderVerdict();
  graph(scoped);
  // The chart count and inspected point already communicate history.
  // Avoid another text block repeating the same information.
}

function createCard(match) {
  return createMatchCard(match, {
    played: isPlayed(match),
    formatDate: date,
    onSelect() {
      if (match.id === current) return;
      updateShareLink(match.event_key);
      void selectMatch(match.id);
      if (window.matchMedia("(max-width: 640px)").matches) {
        const reduce = window.matchMedia(
          "(prefers-reduced-motion: reduce)",
        ).matches;
        $("match-details").scrollIntoView({
          behavior: reduce ? "auto" : "smooth",
          block: "start",
        });
      }
    },
  });
}

function updateSelectedCards() {
  for (const [id, item] of cards) {
    const selected = id === current;
    item.button.setAttribute("aria-pressed", String(selected));
    item.pill.textContent = selected
      ? "VALGT KAMP"
      : item.played
        ? "SPILT"
        : isSeasonPass(matches.find((m) => m.id === id))
          ? "SESONGKORT"
          : "SE KAMP";
  }
}

function buildCards() {
  const signature = matches
    .map((m) => m.id + "|" + m.title + "|" + m.kickoff_at + "|" + isPlayed(m) + "|" + isSeasonPass(m))
    .join(";");
  if (signature === cardSignature) {
    updateSelectedCards();
    return;
  }
  cardSignature = signature;
  cards = new Map();
  const target = $("matchCards"),
    seasonTarget = $("seasonPassCards"),
    archive = $("playedCards");
  target.replaceChildren();
  seasonTarget.replaceChildren();
  archive.replaceChildren();
  // Played matches move to the archive below, newest first.
  const upcoming = matches.filter((m) => !isSeasonPass(m) && !isPlayed(m)),
    seasonPasses = matches.filter(isSeasonPass),
    played = matches.filter((m) => !isSeasonPass(m) && isPlayed(m)).reverse();
  // Keep the current match above secondary history. With no upcoming matches,
  // the archive becomes the primary selector and stays next to the team tabs.
  if (upcoming.length || seasonPasses.length) $("seasonBoard").before($("playedSection"));
  else target.after($("playedSection"));
  $("playedSection").hidden = !played.length;
  $("seasonPassSection").hidden = !seasonPasses.length;
  $("playedTitle").textContent = "Spilte kamper (" + played.length + ")";
  if (!upcoming.length) {
    const empty = document.createElement("p");
    empty.className = "empty";
    empty.textContent = seasonPasses.length
      ? "Ingen kommende kamper registrert akkurat nå."
      : played.length
        ? "Ingen kommende kamper akkurat nå. Se spilte kamper under."
        : "Ingen kamper er publisert ennå.";
    target.append(empty);
  }
  for (const m of upcoming) {
    const card = createCard(m);
    cards.set(m.id, card);
    target.append(card.button);
  }
  // Season-card inventory is a long-running ticket product, not a fixture.
  // Keep it visible without putting it in the played-match archive.
  for (const m of seasonPasses) {
    const card = createCard(m);
    cards.set(m.id, card);
    seasonTarget.append(card.button);
  }
  for (const m of played) {
    const card = createCard(m);
    cards.set(m.id, card);
    archive.append(card.button);
  }
  updateSelectedCards();
}

async function refreshCardData() {
  await Promise.all(
    matches.map(async (match) => {
      const card = cards.get(match.id);
      if (!card) return;
      try {
        const table =
          categoryFor(match) === "women"
            ? "ministaut_koteng_scans"
            : "ministaut_scans";
        const statusFilter =
          categoryFor(match) === "women"
            ? "in.(observed,accepted)"
            : "eq.accepted";
        const data = await load(
          table +
            "?select=observed_at,available_seated,locked_fields&reading_status=" +
            statusFilter +
            "&match_id=eq." +
            encodeURIComponent(match.id) +
            "&order=observed_at.desc&limit=40",
        );
        if (cards.get(match.id) !== card) return;
        if (!data.length) {
          card.value.textContent = "—";
          card.foot.textContent = card.played ? "" : "Tall kommer snart";
          card.button.setAttribute("data-stale", String(!card.played));
          return;
        }
        const latest = data[0];
        card.value.textContent = fmt(latest.available_seated);
        const pulse = dailyPulse(data);
        const day = pulse ? { sold: -pulse.difference } : null;
        const stale = !card.played && overdue(latest.observed_at);
        card.foot.textContent = card.played
          ? "ledige ved avspark"
          : (day
              ? day.sold > 0
                ? fmt(day.sold) + " færre siste døgn"
                : day.sold < 0
                  ? fmt(-day.sold) + " flere siste døgn"
                  : "Uendret siste døgn"
              : "") +
            (stale ? (day ? " · " : "") + "venter på ny telling" : "");
        card.button.setAttribute("data-stale", String(stale));
      } catch (error) {
        card.foot.textContent = "Kunne ikke oppdatere · prøv igjen";
        card.button.dataset.stale = "true";
      }
    }),
  );
}

const STADIUM_CODES = [
  "A",
  "AA",
  "AB",
  "B",
  "BA",
  "BB",
  "C",
  "CA",
  "CB",
  "D",
  "DA",
  "DB",
  "E",
  "EA",
  "EB",
  "F",
  "FA",
  "FB",
  "G",
  "GA",
  "GB",
  "HB",
  "I",
  "IB",
  "J",
  "JB",
  "K",
  "KB",
  "LB",
  "MA",
  "MB",
  "N",
  "NA",
  "NB",
  "O",
  "OA",
  "OB",
  "P",
  "PA",
  "PB",
  "PRESSE",
  "Q",
  "QA",
  "QB",
  "RA",
  "RB",
  "SA",
  "TA",
  "TB",
  "U",
  "UA",
  "UB",
  "V",
  "VA",
  "VB",
  "W",
  "WA",
  "WB",
  "XA",
  "XB",
];
const SVG_NS = "http://www.w3.org/2000/svg";
let stadiumByCode = new Map(),
  stadiumSelected = null,
  sectionDeltas = new Map(),
  sectionView = "availability",
  visibleSectionRows = [],
  visibleSectionScan = null;
function chooseSectionMode(mode) {
  sectionView = mode;
  $("viewAvailability").setAttribute(
    "aria-pressed",
    String(mode === "availability"),
  );
  $("viewHeat").setAttribute("aria-pressed", String(mode === "heat"));
  $("legendAvailability").hidden = mode !== "availability";
  $("legendHeat").hidden = mode !== "heat";
  $("heatStatus").textContent =
    mode === "heat" ? "Endring i ledige plasser" : "Andel ledige sitteplasser";
  drawStadiumMap(visibleSectionRows, visibleSectionScan);
  if (sectionSelection?.dataset.code)
    activateStadiumSection(sectionSelection.dataset.code);
}
function renderSectionRecords(scans) {
  const box = $("sectionRecords");
  box.replaceChildren();
  const ordered = scans
    .slice()
    .sort((a, b) => Date.parse(a.observed_at) - Date.parse(b.observed_at));
  const last = ordered.at(-1),
    scoped = last ? ordered.filter((s) => comparable(s, last)) : [];
  const lowest = scoped.length
    ? Math.min(...scoped.map((s) => s.available_seated))
    : null;
  const windows = scoped
    .map((end) => {
      const start = historical24(scoped, end);
      return start
        ? {
            fall: start.available_seated - end.available_seated,
            hours:
              (Date.parse(end.observed_at) - Date.parse(start.observed_at)) /
              3600000,
          }
        : null;
    })
    .filter((x) => x && x.fall > 0);
  const largest = windows.length
    ? Math.max(...windows.map((x) => x.fall))
    : null;
  const fastest = windows.length
    ? Math.max(...windows.map((x) => x.fall / x.hours))
    : null;
  for (const [name, num, description] of [
    [
      "Laveste målte ledighet",
      lowest == null ? "—" : fmt(lowest),
      "Samme feltoppsett",
    ],
    [
      "Største døgnreduksjon",
      largest == null ? "—" : fmt(largest),
      "18–30 timers målte intervaller",
    ],
    [
      "Raskeste døgnsnitt",
      fastest == null ? "—" : fmt(Math.round(fastest)) + " / t",
      "Fall i ledige plasser per time",
    ],
  ]) {
    const div = document.createElement("div");
    div.className = "insight-record";
    const label = document.createElement("span");
    label.textContent = name;
    const strong = document.createElement("strong");
    strong.textContent = num;
    const small = document.createElement("span");
    small.textContent = description;
    div.append(label, strong, small);
    box.append(div);
  }
}

function svgEl(name, attrs = {}, textValue = null) {
  const n = document.createElementNS(SVG_NS, name);
  for (const [key, value] of Object.entries(attrs))
    n.setAttribute(key, String(value));
  if (textValue !== null) n.textContent = textValue;
  return n;
}
// Mapping to the four real sides follows published seating-plan groupings.
// Within each stand coordinates are approximate, not ticket vendor exact hitboxes.
// Source: scanner/anchors_v15.json and scanner/bekreftede_posisjoner_v16.json
// These are click/hover reference positions, NOT verified seat-boundary polygons.
// Hand-audited, deterministic Lerkendal section positions in 780 x 710 viewBox.
// Visual layer ONLY. No changes to ticket data, field capacities or scan processing.
const KOTENG_CODES = ["VIP", "FELT-1", "FELT-2", "FELT-3", "FELT-4", "FELT-5"];
function drawKotengMap(rows, scan) {
  const target = $("stadiumMap");
  target.replaceChildren();
  stadiumSelected = null;
  if (!rows || !scan) {
    target.textContent = "Tribunekartet kommer snart.";
    return;
  }
  const byCode = new Map(rows.map((r) => [r.section_code, r]));
  stadiumByCode = byCode;
  const locked = new Set(scan.locked_fields || []);
  const heat = sectionView === "heat";
  const svg = svgEl("svg", {
    viewBox: "0 0 800 520",
    class: "stadium-map",
    role: "group",
    "aria-label": "Skjematisk sitteplasskart Koteng Arena",
  });
  svg.append(
    svgEl("rect", {
      x: 20,
      y: 153,
      width: 760,
      height: 304,
      rx: 6,
      fill: "#244c36",
      stroke: "#4c785e",
      "stroke-width": 3,
    }),
  );
  for (let x = 20; x < 780; x += 95)
    svg.append(
      svgEl("rect", {
        x,
        y: 153,
        width: 47.5,
        height: 304,
        fill: "#346348",
        opacity: ".35",
      }),
    );
  svg.append(
    svgEl("rect", {
      x: 44,
      y: 176,
      width: 712,
      height: 258,
      fill: "none",
      stroke: "#e9d9bb",
      "stroke-width": 3,
    }),
  );
  svg.append(
    svgEl("line", {
      x1: 400,
      y1: 176,
      x2: 400,
      y2: 434,
      stroke: "#e9d9bb",
      "stroke-width": 3,
    }),
  );
  svg.append(
    svgEl("circle", {
      cx: 400,
      cy: 305,
      r: 48,
      fill: "none",
      stroke: "#e9d9bb",
      "stroke-width": 3,
    }),
  );
  svg.append(
    svgEl("rect", {
      x: 44,
      y: 245,
      width: 100,
      height: 120,
      fill: "none",
      stroke: "#e9d9bb",
      "stroke-width": 3,
    }),
  );
  svg.append(
    svgEl("rect", {
      x: 656,
      y: 245,
      width: 100,
      height: 120,
      fill: "none",
      stroke: "#e9d9bb",
      "stroke-width": 3,
    }),
  );
  const tiles = [
    ["FELT-1", 20, 81, 71, 57],
    ["FELT-2", 97, 81, 190, 57],
    ["FELT-3", 293, 81, 190, 57],
    ["FELT-4", 489, 81, 190, 57],
    ["FELT-5", 685, 81, 95, 57],
    ["VIP", 293, 19, 190, 54],
  ];
  for (const [code, x, y, w, height] of tiles) {
    const row = byCode.get(code),
      name = code === "VIP" ? "VIP" : "Felt " + code.slice(5);
    const sector = svgEl("rect", {
      x,
      y,
      width: w,
      height,
      rx: 4,
      class: "seat-sector",
      "data-code": code,
      "data-level": stadiumColor(row, locked.has(code)),
      "data-heat": heat ? sectionHeat(sectionDeltas.get(code)?.day) : "",
      "aria-pressed": "false",
      tabindex: 0,
      role: "button",
      "aria-label":
        name +
        ", " +
        (row
          ? row.free + " ledige av " + row.capacity
          : locked.has(code)
            ? "låst"
            : "ikke målt"),
    });
    sector.append(
      svgEl(
        "title",
        {},
        name +
          " · " +
          (row
            ? row.free + " ledige av " + row.capacity
            : locked.has(code)
              ? "låst"
              : "ikke målt"),
      ),
    );
    sector.addEventListener("click", () => activateStadiumSection(code));
    sector.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        activateStadiumSection(code);
      }
    });
    svg.append(sector);
    svg.append(
      svgEl(
        "text",
        { x: x + w / 2, y: y + height / 2 + 5, class: "seat-label" },
        name,
      ),
    );
  }
  for (const [name, x] of [
    ["STÅPLASS A", 38],
    ["STÅPLASS B", 442],
  ]) {
    svg.append(
      svgEl("rect", {
        x,
        y: 469,
        width: 320,
        height: 37,
        rx: 4,
        fill: "#3c3427",
        stroke: "#c8a664",
        "stroke-dasharray": "5 5",
      }),
    );
    svg.append(
      svgEl(
        "text",
        {
          x: x + 160,
          y: 492,
          "text-anchor": "middle",
          fill: "#dec48d",
          "font-size": 14,
        },
        name,
      ),
    );
  }
  target.append(svg);
}
function drawStadiumMap(rows, scan) {
  if (selectedVenue === "koteng_arena") return drawKotengMap(rows, scan);
  const target = $("stadiumMap");
  target.replaceChildren();
  stadiumSelected = null;
  if (!rows || !scan) {
    target.textContent = "Tribunekartet kommer snart.";
    return;
  }
  const byCode = new Map(rows.map((r) => [r.section_code, r]));
  stadiumByCode = byCode;
  const locks = new Set(scan.locked_fields || []);
  const heat = sectionView === "heat";
  const svg = svgEl("svg", {
    viewBox: "0 0 780 710",
    class: "stadium-map",
    role: "group",
    "aria-label": "Tribunekart for Lerkendal, tilgjengelige sitteplasser",
  });
  const defs = svgEl("defs");
  const grad = svgEl("linearGradient", {
    id: "pitchGrad",
    x1: "0",
    x2: "0",
    y1: "0",
    y2: "1",
  });
  grad.append(
    svgEl("stop", { offset: "0%", "stop-color": "#244d39" }),
    svgEl("stop", { offset: "100%", "stop-color": "#132d22" }),
  );
  defs.append(grad);
  svg.append(defs);
  const field = {
    x: pitchBox.x + 11,
    y: pitchBox.y + 11,
    w: pitchBox.w - 23,
    h: pitchBox.h - 22,
  };
  const fieldCenterX = field.x + field.w / 2,
    fieldCenterY = field.y + field.h / 2;
  svg.append(
    svgEl("rect", {
      x: pitchBox.x,
      y: pitchBox.y,
      width: pitchBox.w,
      height: pitchBox.h,
      rx: 8,
      fill: "#211d18",
      stroke: "#a58a55",
      "stroke-width": 3,
    }),
  );
  svg.append(
    svgEl("rect", {
      x: field.x,
      y: field.y,
      width: field.w,
      height: field.h,
      rx: 1,
      fill: "url(#pitchGrad)",
      stroke: "#e9d9bb",
      "stroke-width": 2,
    }),
  );
  svg.append(
    svgEl("line", {
      x1: fieldCenterX,
      y1: field.y,
      x2: fieldCenterX,
      y2: field.y + field.h,
      stroke: "#dec48d",
      "stroke-width": 2,
    }),
  );
  svg.append(
    svgEl("circle", {
      cx: fieldCenterX,
      cy: fieldCenterY,
      r: 43,
      fill: "none",
      stroke: "#dec48d",
      "stroke-width": 2,
    }),
  );
  svg.append(
    svgEl("rect", {
      x: field.x,
      y: field.y + 66,
      width: 62,
      height: 143,
      fill: "none",
      stroke: "#dec48d",
      "stroke-width": 2,
    }),
  );
  svg.append(
    svgEl("rect", {
      x: field.x + field.w - 62,
      y: field.y + 66,
      width: 62,
      height: 143,
      fill: "none",
      stroke: "#dec48d",
      "stroke-width": 2,
    }),
  );
  svg.append(
    svgEl(
      "text",
      {
        x: fieldCenterX,
        y: fieldCenterY + 5,
        "text-anchor": "middle",
        fill: "#e9d9bb",
        "font-size": 24,
        "font-weight": 850,
        opacity: ".35",
      },
      "LERKENDAL",
    ),
  );
  const labels = [
    ["PEPSI MAX", stadiumFrame.centerX, stadiumFrame.northEdge - 166],
    ["COOP", coopStand.upperX + coopStand.upperW / 2, pitchBox.y - 11],
    ["SPAREBANK 1", stadiumFrame.centerX, stadiumFrame.southEdge + 187],
    ["ADRESSA", pitchBox.x + pitchBox.w + 106, pitchBox.y + 5],
  ];
  labels.forEach(([t, x, y]) =>
    svg.append(
      svgEl(
        "text",
        {
          x,
          y,
          "text-anchor": "middle",
          fill: "#dec48d",
          "font-size": 14,
          "font-weight": 800,
          "letter-spacing": 1.3,
        },
        t,
      ),
    ),
  );
  // Tiny VIP label above the distinct Coop VIP band; seat fills remain data-driven.
  svg.append(
    svgEl(
      "text",
      {
        x: coopStand.vipX + coopStand.vipW / 2,
        y: pitchBox.y + 5,
        "text-anchor": "middle",
        fill: "#dec48d",
        "font-size": 10,
        "font-weight": 900,
      },
      "VIP",
    ),
  );
  sectionTiles().forEach((tile) => {
    const { code, x, y, w, h } = tile,
      row = byCode.get(code),
      level = stadiumColor(row, locks.has(code));
    const sectorName = ["U", "V", "W"].includes(code)
      ? "VIP Coop, felt " + code
      : "Felt " + code;
    const p = svgEl("rect", {
      x,
      y,
      width: w,
      height: h,
      rx: 4,
      class: "seat-sector",
      "data-code": code,
      "data-heat": heat ? sectionHeat(sectionDeltas.get(code)?.day) : "",
      "data-level": level,
      "data-vip": ["U", "V", "W"].includes(code) ? "coop" : "",
      "aria-pressed": "false",
      tabindex: 0,
      role: "button",
      "aria-label":
        sectorName +
        ", " +
        (row
          ? row.free + " ledige av " + row.capacity
          : locks.has(code)
            ? "låst"
            : "mangler måling"),
    });
    p.append(
      svgEl(
        "title",
        {},
        sectorName +
          " · " +
          (row
            ? row.free + " ledige av " + row.capacity
            : locks.has(code)
              ? "låst"
              : "ikke målt"),
      ),
    );
    p.addEventListener("click", () => activateStadiumSection(code));
    p.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        activateStadiumSection(code);
      }
    });
    svg.append(p);
    const labelAttrs = {
      x: x + w / 2,
      y: y + h / 2 + 3.5,
      class: "seat-label",
    };
    if (w < 30 || h < 30) labelAttrs["font-size"] = 8;
    svg.append(svgEl("text", labelAttrs, code));
  });
  // SB and Øvre Øst are contextual standing areas, never counted as seated availability.
  // Position contextual standing areas outside the same pitch-relative rails.
  // They are not part of the 60 seated-sector availability measurements.
  const sbX = pitchBox.x - 81,
    sbY = pitchBox.y - 53;
  const sb = svgEl("rect", {
    x: sbX,
    y: sbY,
    width: 28,
    height: 34,
    rx: 3,
    fill: "#3c3427",
    stroke: "#a58a55",
    "stroke-dasharray": "3 3",
  });
  svg.append(sb);
  svg.append(
    svgEl(
      "text",
      {
        x: sbX + 14,
        y: sbY + 20,
        "text-anchor": "middle",
        fill: "#dec48d",
        "font-size": 10,
      },
      "SB",
    ),
  );
  const standingX = pitchBox.x + pitchBox.w + 143,
    standingY = pitchBox.y + 47;
  const standing = svgEl("rect", {
    x: standingX,
    y: standingY,
    width: 23,
    height: 219,
    rx: 4,
    fill: "#3c3427",
    stroke: "#a58a55",
    "stroke-dasharray": "3 3",
  });
  const standingCX = standingX + 11.5,
    standingCY = standingY + 109.5;
  svg.append(standing);
  svg.append(
    svgEl(
      "text",
      {
        x: standingCX,
        y: standingCY,
        transform: "rotate(90 " + standingCX + " " + standingCY + ")",
        "text-anchor": "middle",
        fill: "#dec48d",
        "font-size": 11,
      },
      "ØVRE ØST",
    ),
  );
  target.append(svg);
}
function activateStadiumSection(code) {
  if (stadiumSelected) stadiumSelected.setAttribute("aria-pressed", "false");
  const sector = document.querySelector(
    '.stadium-map .seat-sector[data-code="' + code + '"]',
  );
  stadiumSelected = sector;
  if (sector) sector.setAttribute("aria-pressed", "true");
  const row = stadiumByCode.get(code);
  const detail = $("sectionDetail");
  renderSectionAlert(code);
  if (!row) {
    detail.textContent =
      "Felt " +
      code +
      ": ikke avlest eller bekreftet låst. Ingen ledighet kan fastslås.";
    return;
  }
  const pct = Math.round((100 * row.free) / row.capacity);
  const change = sectionDeltas.get(code) || {};
  detail.textContent =
    (code === "VIP"
      ? "VIP"
      : code.startsWith("FELT-")
        ? "Felt " + code.slice(5)
        : "Felt " + code) +
    " · " +
    fmt(row.free) +
    " ledige av " +
    fmt(row.capacity) +
    " seter (" +
    pct +
    " %). Målt " +
    date(lastObservedAt) +
    ". Forrige telling: " +
    sectionDeltaLabel(change.previous) +
    ". Omtrent 24 timer: " +
    sectionDeltaLabel(change.day) +
    ".";
  const cell = [...$("sectionGrid").children].find(
    (el) => el.dataset?.code === code,
  );
  if (sectionSelection) sectionSelection.setAttribute("aria-pressed", "false");
  sectionSelection = cell || null;
  if (cell) cell.setAttribute("aria-pressed", "true");
}
// Supporter-facing stand totals use only verified seated section records.
function renderStandSummary(rows) {
  const target = $("standSummary");
  target.replaceChildren();
  if (!rows?.length) {
    target.textContent = "Oversikten er ikke tilgjengelig ennå.";
    return;
  }
  const byCode = new Map(rows.map((row) => [row.section_code, row]));
  const groups =
    selectedVenue === "koteng_arena"
      ? [
          {
            name: "Sittefeltene",
            codes: ["FELT-1", "FELT-2", "FELT-3", "FELT-4", "FELT-5"],
          },
          { name: "VIP", codes: ["VIP"] },
        ]
      : STAND_GROUPS;
  const heading = document.createElement("h3");
  heading.className = "stand-summary-title";
  heading.textContent = "Ledige plasser per tribune";
  target.append(heading);
  for (const group of groups) {
    const parts = group.codes.map((code) => byCode.get(code)).filter(Boolean);
    if (!parts.length) continue;
    const available = parts.reduce((sum, row) => sum + row.free, 0);
    const capacity = parts.reduce((sum, row) => sum + row.capacity, 0);
    if (capacity <= 0) continue;
    const pct = Math.round((100 * available) / capacity);
    const row = document.createElement("div");
    row.className = "stand-summary-item";
    const labels = document.createElement("div");
    labels.className = "stand-summary-labels";
    const name = document.createElement("span");
    name.textContent = group.name;
    const value = document.createElement("strong");
    value.textContent = fmt(available);
    const suffix = document.createElement("span");
    suffix.className = "stand-summary-suffix";
    suffix.textContent = "ledige";
    labels.append(name, value, suffix);
    const meter = document.createElement("div");
    meter.className = "stand-summary-track";
    meter.setAttribute("role", "meter");
    meter.setAttribute(
      "aria-label",
      group.name + " – andel ledige sitteplasser",
    );
    meter.setAttribute("aria-valuenow", String(pct));
    meter.setAttribute("aria-valuemin", "0");
    meter.setAttribute("aria-valuemax", "100");
    const fill = document.createElement("span");
    fill.className = "stand-summary-fill";
    fill.style.width = pct + "%";
    meter.append(fill);
    const percent = document.createElement("span");
    percent.className = "stand-summary-percent";
    percent.textContent = pct + " % ledige";
    row.append(labels, meter, percent);
    target.append(row);
  }
}
function renderSections(rows, scan) {
  const grid = $("sectionGrid"),
    status = $("sectionStatus"),
    detail = $("sectionDetail");
  const previousCode = sectionSelection?.dataset.code;
  grid.replaceChildren();
  if (!scan || !Array.isArray(rows)) {
    drawStadiumMap(null, null);
    renderStandSummary(null);
    visibleSectionRows = [];
    visibleSectionScan = null;
    sectionDeltas = new Map();
    status.textContent = "Tribunekartet er ikke tilgjengelig ennå";
    detail.textContent = "Velg en kamp for å se ledige plasser.";
    return;
  }
  const valid = rows.filter(
    (r) =>
      typeof r.section_code === "string" &&
      Number.isInteger(r.free) &&
      Number.isInteger(r.capacity) &&
      r.capacity > 0 &&
      r.free >= 0 &&
      r.free <= r.capacity,
  );
  const codes = new Set(valid.map((r) => r.section_code));
  const total = valid.reduce((sum, r) => sum + r.free, 0);
  const expected = new Set(
    selectedVenue === "koteng_arena" ? KOTENG_CODES : STADIUM_CODES,
  );
  const locks = scan.locked_fields || [];
  const complete =
    codes.size === valid.length &&
    valid.every((r) => expected.has(r.section_code)) &&
    locks.every((code) => expected.has(code) && !codes.has(code)) &&
    valid.length + locks.length === expected.size &&
    total === scan.available_seated;
  if (!complete) {
    status.textContent = "Tribunekartet er midlertidig utilgjengelig";
    detail.textContent = "Prøv igjen litt senere.";
    renderStandSummary(null);
    drawStadiumMap(null, null);
    return;
  }
  status.textContent = "Oppdatert " + date(scan.observed_at);
  visibleSectionRows = valid.slice();
  visibleSectionScan = scan;
  drawStadiumMap(valid, scan);
  renderStandSummary(valid);
  valid.sort((a, b) =>
    a.section_code.localeCompare(b.section_code, "nb", { numeric: true }),
  );
  sectionSelection = null;
  detail.textContent = "Velg et felt for å se ledige plasser og størrelse.";
  for (const r of valid) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "section-cell";
    btn.dataset.code = r.section_code;
    btn.setAttribute("aria-pressed", "false");
    btn.dataset.level = r.free === 0 ? "none" : r.free <= 10 ? "few" : "normal";
    const name = document.createElement("span");
    name.className = "section-code";
    name.textContent =
      r.section_code === "VIP"
        ? "VIP"
        : r.section_code.startsWith("FELT-")
          ? "Felt " + r.section_code.slice(5)
          : "Felt " + r.section_code;
    const value = document.createElement("span");
    value.className = "section-free";
    value.textContent = fmt(r.free);
    const meta = document.createElement("span");
    meta.className = "section-meta";
    meta.textContent = "ledige av " + fmt(r.capacity);
    btn.append(name, value, meta);
    btn.addEventListener("click", () => activateStadiumSection(r.section_code));
    grid.append(btn);
  }
  if (previousCode && valid.some((r) => r.section_code === previousCode))
    activateStadiumSection(previousCode);
}
async function loadSections(scan, version, id, scans) {
  const grid = $("sectionGrid");
  grid.textContent = "Henter ledige plasser …";
  $("sectionStatus").textContent = "Henter tribunekart …";
  if (!scan) {
    renderSections(null, null);
    return;
  }
  try {
    const prior = scans
      .filter(
        (s) =>
          s.id !== scan.id &&
          Date.parse(s.observed_at) < Date.parse(scan.observed_at) &&
          comparable(s, scan),
      )
      .sort((a, b) => Date.parse(b.observed_at) - Date.parse(a.observed_at))[0];
    const day = historical24(scans, scan);
    const unique = [scan, prior, day].filter(
      (x, i, arr) => x && arr.findIndex((y) => y?.id === x.id) === i,
    );
    const snapshots = await Promise.all(
      unique.map(async (item) => {
        const table =
          selectedVenue === "koteng_arena"
            ? "ministaut_koteng_section_measurements"
            : "ministaut_section_measurements";
        const rows = await load(
          table +
            "?select=section_code,free,capacity&scan_id=eq." +
            encodeURIComponent(item.id) +
            "&order=section_code.asc&limit=80",
        );
        const expected = new Set(
            selectedVenue === "koteng_arena" ? KOTENG_CODES : STADIUM_CODES,
          ),
          locks = item.locked_fields || [];
        const valid =
          rows.length + locks.length === expected.size &&
          rows.every((r) => expected.has(r.section_code)) &&
          locks.every(
            (code) =>
              expected.has(code) && !rows.some((r) => r.section_code === code),
          ) &&
          new Set(rows.map((r) => r.section_code)).size === rows.length &&
          rows.reduce((a, b) => a + b.free, 0) === item.available_seated;
        return { id: item.id, rows: valid ? rows : null };
      }),
    );
    if (version !== selectionVersion || current !== id) return;
    const byId = new Map(snapshots.map((x) => [x.id, x.rows]));
    const rows = byId.get(scan.id);
    if (!rows) {
      renderSections(null, null);
      return;
    }
    // Do not use a comparison snapshot if it covers different field capacities.
    // Full-snapshot checks above already reject missing rows and bad totals.
    const prev = new Map(
      ((prior && byId.get(prior.id)) || []).map((r) => [r.section_code, r]),
    );
    const daily = new Map(
      ((day && byId.get(day.id)) || []).map((r) => [r.section_code, r]),
    );
    sectionDeltas = new Map(
      rows.map((r) => {
        const a = prev.get(r.section_code),
          b = daily.get(r.section_code);
        return [
          r.section_code,
          {
            previous: a && a.capacity === r.capacity ? r.free - a.free : null,
            day: b && b.capacity === r.capacity ? r.free - b.free : null,
          },
        ];
      }),
    );
    renderSections(rows, scan);
  } catch (error) {
    if (version !== selectionVersion || current !== id) return;
    renderSections(null, null);
    $("sectionDetail").textContent = "Kunne ikke hente tribunekartet nå.";
  }
}
$("viewAvailability").addEventListener("click", () =>
  chooseSectionMode("availability"),
);
$("viewHeat").addEventListener("click", () => chooseSectionMode("heat"));
// --- Earlier matches: same clock, history-based forecast, fields that go first ---
// Matches are lined up on hours before kickoff, so a curve from another match
// can be read at the same point in its sales period.
const REF_TTL = 10 * 60000;
const refScanCache = new Map(),
  refSectionCache = new Map();
function scanTables(match) {
  const women = categoryFor(match) === "women";
  return {
    scans: women ? "ministaut_koteng_scans" : "ministaut_scans",
    sections: women
      ? "ministaut_koteng_section_measurements"
      : "ministaut_section_measurements",
    status: women ? "in.(observed,accepted)" : "eq.accepted",
  };
}
function cached(cache, key, ttl, make) {
  const hit = cache.get(key);
  if (hit && (ttl === null || Date.now() - hit.at < ttl)) return hit.promise;
  const promise = make().catch((error) => {
    cache.delete(key);
    throw error;
  });
  cache.set(key, { at: Date.now(), promise });
  return promise;
}
function refScans(match) {
  const t = scanTables(match);
  // A played match no longer changes; upcoming ones are refreshed now and then.
  return cached(refScanCache, match.id, isPlayed(match) ? null : REF_TTL, () =>
    load(
      t.scans +
        "?select=id,observed_at,available_seated,locked_fields&reading_status=" +
        t.status +
        "&match_id=eq." +
        encodeURIComponent(match.id) +
        "&order=observed_at.asc&limit=1000",
    ),
  );
}
function refSections(match, scans) {
  const t = scanTables(match),
    k = Date.parse(match.kickoff_at);
  return cached(refSectionCache, match.id, null, async () => {
    const ids = scans
      .filter((s) => Date.parse(s.observed_at) <= k + 15 * 60000)
      .map((s) => s.id);
    const when = new Map(
      scans.map((s) => [s.id, (k - Date.parse(s.observed_at)) / HOUR]),
    );
    const batches = [];
    for (let i = 0; i < ids.length; i += 15) batches.push(ids.slice(i, i + 15));
    const rows = (
      await Promise.all(
        batches.map((b) =>
          load(
            t.sections +
              "?select=scan_id,section_code,free,capacity&scan_id=in.(" +
              b.join(",") +
              ")&limit=1000",
          ),
        ),
      )
    ).flat();
    const sections = new Map();
    for (const r of rows) {
      if (!sections.has(r.section_code)) sections.set(r.section_code, []);
      sections
        .get(r.section_code)
        .push({ h: when.get(r.scan_id), free: r.free, capacity: r.capacity });
    }
    for (const series of sections.values()) series.sort((a, b) => b.h - a.h);
    return sections;
  });
}
const COMPARE_COLORS = ["#4783b2", "#4e896a", "#c9c9c9", "#c08a4a", "#8a8a8a"];
function drawCompare(mine, refs, title, span) {
  lastComparison = [mine, refs, title, span];
  const {
    W,
    H: Ht,
    L,
    R,
    T,
    B,
  } = chartDimensions($("compareChart").clientWidth);
  const inWindow = (pts) => pts.filter((p) => p.h <= span);
  const lines = [
    ...refs.map((r, i) => ({
      title: r.title,
      color: COMPARE_COLORS[i % COMPARE_COLORS.length],
      pts: inWindow(r.points),
      mine: false,
    })),
    { title, color: "#e9d9bb", pts: inWindow(mine), mine: true },
  ].filter((l) => l.pts.length);
  const top =
    Math.max(1, ...lines.flatMap((l) => l.pts.map((p) => p.v))) * 1.08;
  const x = (h) => L + ((span - h) / span) * (W - L - R),
    y = (v) => T + (1 - v / top) * (Ht - T - B);
  const targetTicks = W < 520 ? 3 : 6;
  const step = Math.max(1, Math.ceil(span / targetTicks / 12)) * 12;
  let svg =
    '<svg viewBox="0 0 ' +
    W +
    " " +
    Ht +
    '" width="100%" role="img" aria-label="Ledige sitteplasser målt mot timer før avspark">';
  for (let i = 0; i <= 4; i++) {
    const v = ((top / 1.08) * i) / 4;
    svg +=
      '<line x1="' +
      L +
      '" x2="' +
      (W - R) +
      '" y1="' +
      y(v).toFixed(1) +
      '" y2="' +
      y(v).toFixed(1) +
      '" stroke="#2c2c2c"/>' +
      '<text x="' +
      (L - 8) +
      '" y="' +
      (y(v) + 4).toFixed(1) +
      '" text-anchor="end" fill="#8d8d8d" font-size="12">' +
      fmt(Math.round(v)) +
      "</text>";
  }
  for (let h = 0; h <= span; h += step) {
    svg +=
      '<text x="' +
      x(h).toFixed(1) +
      '" y="' +
      (Ht - 12) +
      '" text-anchor="middle" fill="#8d8d8d" font-size="12">' +
      (h === 0 ? "Avspark" : "−" + hoursText(h)) +
      "</text>";
  }
  svg +=
    '<line x1="' +
    x(0) +
    '" x2="' +
    x(0) +
    '" y1="' +
    T +
    '" y2="' +
    (Ht - B) +
    '" stroke="#6d5731" stroke-dasharray="3 4"/>';
  for (const l of lines) {
    const d = l.pts
      .map(
        (p, i) => (i ? "L" : "M") + x(p.h).toFixed(1) + " " + y(p.v).toFixed(1),
      )
      .join(" ");
    const end = l.pts.at(-1);
    svg +=
      '<path d="' +
      d +
      '" fill="none" stroke="' +
      l.color +
      '" stroke-width="' +
      (l.mine ? 3 : 1.8) +
      '" stroke-linejoin="round" stroke-linecap="round"' +
      (l.mine ? "" : ' opacity=".85"') +
      "/>" +
      '<circle cx="' +
      x(end.h).toFixed(1) +
      '" cy="' +
      y(end.v).toFixed(1) +
      '" r="' +
      (l.mine ? 4 : 3) +
      '" fill="' +
      l.color +
      '"/>';
  }
  $("compareChart").innerHTML = svg + "</svg>";
  const legend = $("compareLegend");
  legend.replaceChildren();
  for (const l of lines) {
    const item = document.createElement("span");
    const swatch = document.createElement("i");
    swatch.style.background = l.color;
    item.append(swatch, l.mine ? title + " (denne kampen)" : l.title);
    legend.append(item);
  }
}
function renderHistoryForecast(result, played) {
  const el = $("historyForecast");
  el.hidden = !result || played;
  if (el.hidden) return;
  $("historyForecastValue").textContent =
    result.low === result.high
      ? "ca. " + fmt(result.center) + " ledige"
      : fmt(result.low) + "–" + fmt(result.high) + " ledige";
  $("historyForecastNote").textContent =
    "Basert på " +
    result.basis
      .map((b) => b.title + " (" + fmt(b.at) + " → " + fmt(b.final) + ")")
      .join(", ") +
    ". Spennet viser to måter å regne på: samme andel solgt, og samme antall solgt.";
}
function renderFastSections(ranked, refsUsed) {
  const box = $("fastSections"),
    list = $("fastSectionList");
  list.replaceChildren();
  const top = ranked.slice(0, 6);
  box.hidden = !top.length;
  if (!top.length) return;
  for (const s of top) {
    const li = document.createElement("li");
    const button = document.createElement("button");
    button.type = "button";
    const name = document.createElement("strong");
    name.textContent = sectionName(s.code);
    const how = s.emptyCount
      ? "0 ledige " +
        hoursText(s.emptyHours) +
        " før avspark" +
        (s.n > 1 ? " (" + s.emptyCount + " av " + s.n + " kamper)" : "")
      : (s.finalShare < 0.01
          ? "nesten ingen"
          : Math.round(s.finalShare * 100) + " %") + " ledige ved avspark";
    const nowRow = stadiumByCode.get(s.code);
    const detail = document.createElement("span");
    detail.textContent =
      how + (nowRow ? " · nå " + fmt(nowRow.free) + " ledige" : "");
    button.append(name, detail);
    button.addEventListener("click", () => {
      activateStadiumSection(s.code);
      $("stadiumMap").scrollIntoView({ behavior: "smooth", block: "center" });
    });
    li.append(button);
    list.append(li);
  }
  $("fastSectionsNote").textContent =
    "Basert på kampen mot " + refsUsed.join(" og ") + ".";
}
async function renderComparison(match, scans, version, id) {
  const panel = $("comparePanel");
  const venue = venueFor(match),
    played = isPlayed(match);
  const others = allMatches.filter(
    (m) =>
      m.id !== match.id &&
      venueFor(m) === venue &&
      Number.isFinite(Date.parse(m.kickoff_at || "")),
  );
  const mine = curve(scans, match.kickoff_at);
  if (!others.length || mine.length < 2) {
    panel.hidden = true;
    $("historyForecast").hidden = true;
    return;
  }
  let refs;
  try {
    refs = await Promise.all(
      others.map(async (m) => ({
        match: m,
        title: opponentName(m.title),
        scans: await refScans(m),
      })),
    );
  } catch {
    if (version === selectionVersion) panel.hidden = true;
    return;
  }
  if (version !== selectionVersion || current !== id) return;
  refs = refs
    .map((r) => ({ ...r, points: curve(r.scans, r.match.kickoff_at) }))
    .filter((r) => r.points.length > 1);
  if (!refs.length) {
    panel.hidden = true;
    $("historyForecast").hidden = true;
    return;
  }
  panel.hidden = false;
  const title = opponentName(match.title);
  const now = mine.at(-1),
    playedRefs = refs.filter((r) => isPlayed(r.match));
  // Window: from now (or the earliest played reference) to kickoff, at most 30 days.
  const span = Math.max(
    24,
    now.h + 12,
    ...playedRefs.map((r) => r.points[0].h),
  );
  $("compareTitle").textContent = "Salgskurven mot tidligere kamper";
  $("compareChart").hidden = span > 720;
  $("compareLegend").hidden = span > 720;
  if (span <= 720) drawCompare(mine, refs, title, span);
  if (played) {
    $("compareNow").textContent =
      "Kampen er spilt. " +
      fmt(now.v) +
      " ledige ved siste måling, " +
      (now.h >= 0 ? hoursText(now.h) + " før avspark" : "like etter avspark") +
      ".";
  } else {
    const same = playedRefs
      .map((r) => ({ title: r.title, v: valueAt(r.points, now.h) }))
      .filter((r) => r.v !== null);
    if (same.length) {
      $("compareNow").textContent =
        "Nå, " +
        hoursText(now.h) +
        " før avspark: " +
        fmt(now.v) +
        " ledige. " +
        same
          .map((r) => {
            const d = now.v - r.v;
            return (
              "Mot " +
              r.title +
              " var det " +
              fmt(r.v) +
              " på samme tidspunkt (" +
              (d === 0
                ? "likt"
                : d < 0
                  ? fmt(-d) + " færre ledige nå"
                  : fmt(d) + " flere ledige nå") +
              ")"
            );
          })
          .join(". ") +
        ".";
    } else {
      const from = Math.max(0, ...playedRefs.map((r) => r.points[0].h));
      $("compareNow").textContent = from
        ? "Sammenligningen starter " + hoursText(from) + " før avspark."
        : "";
    }
  }
  lastHistory = played ? null : historyForecast(now, playedRefs);
  renderHistoryForecast(lastHistory, played);
  renderVerdict();
  if (!playedRefs.length) {
    $("fastSections").hidden = true;
    return;
  }
  try {
    const withSections = await Promise.all(
      playedRefs.map(async (r) => ({
        title: r.title,
        sections: await refSections(r.match, r.scans),
      })),
    );
    if (version !== selectionVersion || current !== id) return;
    renderFastSections(
      rankFastSections(withSections),
      withSections.map((r) => r.title),
    );
  } catch {
    $("fastSections").hidden = true;
  }
}

// --- Push alerts: new tickets released, or a field running low -------------
// The browser's push endpoint is the only identifier; no account or e-mail.
const PUSH_API = DB + "/functions/v1/ministaut-push";
const VAPID_PUBLIC =
  "BE_by4P9-2fSKhyeBm6Ka5VT4NWNi-xwS8PauHY0twQ9dHns-0sWaGIiD_CCdhbxneMmBkhu0Kair0001wia3as";
const SECTION_THRESHOLDS = [10, 25, 50, 100];
let pushState = { endpoint: null, alerts: [] };
const pushSupported = () =>
  typeof navigator !== "undefined" &&
  "serviceWorker" in navigator &&
  typeof window !== "undefined" &&
  "PushManager" in window &&
  "Notification" in window;
function vapidBytes(key) {
  const raw = atob(
    key.replace(/-/g, "+").replace(/_/g, "/") +
      "=".repeat((4 - (key.length % 4)) % 4),
  );
  return Uint8Array.from(raw, (c) => c.charCodeAt(0));
}
async function pushCall(body) {
  const res = await fetch(PUSH_API, {
    method: "POST",
    headers: { "Content-Type": "application/json", apikey: KEY },
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok)
    throw new Error(data.error || "Varseltjenesten svarte " + res.status);
  return data;
}
async function pushRegistration() {
  return navigator.serviceWorker.register(new URL("../sw.js", import.meta.url));
}
async function pushSubscription(ask) {
  const reg = await pushRegistration();
  await navigator.serviceWorker.ready;
  let sub = await reg.pushManager.getSubscription();
  if (!sub && ask) {
    if ((await Notification.requestPermission()) !== "granted")
      throw new Error(
        "Varsler er blokkert i nettleseren. Tillat varsler for siden og prøv igjen.",
      );
    sub = await reg.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: vapidBytes(VAPID_PUBLIC),
    });
  }
  return sub;
}
async function loadPushState() {
  if (!pushSupported() || Notification.permission !== "granted") return;
  try {
    const sub = await pushSubscription(false);
    if (!sub) return;
    const data = await pushCall({ action: "list", subscription: sub.toJSON() });
    pushState = { endpoint: sub.endpoint, alerts: data.alerts || [] };
    renderAlerts();
  } catch {
    /* Alerts are optional; the page works without them. */
  }
}
const hasAlert = (kind, code = "") =>
  pushState.alerts.some(
    (a) =>
      a.match_id === current &&
      a.kind === kind &&
      (a.section_code || "") === code,
  );
function alertStatus(text) {
  $("alertStatus").textContent = text;
}
async function toggleAlert(kind, code = "", threshold = null) {
  const on = hasAlert(kind, code);
  try {
    const sub = await pushSubscription(!on);
    if (!sub)
      throw new Error("Fant ingen varselregistrering i denne nettleseren.");
    const data = await pushCall({
      action: on ? "unsubscribe" : "subscribe",
      subscription: sub.toJSON(),
      match_id: current,
      kind,
      section_code: code,
      threshold,
    });
    pushState = { endpoint: sub.endpoint, alerts: data.alerts || [] };
    alertStatus(
      on
        ? "Varsel slått av."
        : kind === "release"
          ? "Du får varsel når nye billetter slippes."
          : "Du får varsel når " +
            sectionName(code) +
            " har " +
            threshold +
            " eller færre ledige.",
    );
  } catch (error) {
    alertStatus(error.message || "Kunne ikke endre varselet nå.");
  }
  renderAlerts();
}
function renderAlerts() {
  const match = matches.find((m) => m.id === current);
  const row = $("alertRow"),
    button = $("alertRelease");
  const usable =
    !!match &&
    !isPlayed(match) &&
    Date.parse(match.kickoff_at || "") > Date.now();
  row.hidden = !usable;
  if (!usable) return;
  if (!pushSupported()) {
    button.disabled = true;
    button.textContent = "Varsler støttes ikke her";
    alertStatus(
      /iPhone|iPad/.test(navigator.userAgent)
        ? "På iPhone: Del → «Legg til på Hjem-skjerm», og åpne Ministaut derfra."
        : "Nettleseren støtter ikke varsler.",
    );
    return;
  }
  const on = hasAlert("release");
  button.setAttribute("aria-pressed", String(on));
  button.textContent = on
    ? "Varsler om nye billetter · på"
    : "Varsle meg når nye billetter slippes";
  if (stadiumSelected) renderSectionAlert(stadiumSelected.dataset.code);
}
function renderSectionAlert(code) {
  const box = $("sectionAlert");
  box.replaceChildren();
  const match = matches.find((m) => m.id === current),
    row = stadiumByCode.get(code);
  box.hidden = !code || !row || !match || isPlayed(match) || !pushSupported();
  if (box.hidden) return;
  const active = pushState.alerts.find(
    (a) =>
      a.match_id === current && a.kind === "section" && a.section_code === code,
  );
  if (active) {
    const off = document.createElement("button");
    off.type = "button";
    off.className = "pill alert-pill";
    off.setAttribute("aria-pressed", "true");
    off.textContent =
      "Varsel ved " +
      active.threshold +
      " ledige i " +
      sectionName(code) +
      " · slå av";
    off.addEventListener("click", () => void toggleAlert("section", code));
    box.append(off);
    return;
  }
  const options = SECTION_THRESHOLDS.filter((t) => t < row.free);
  if (!options.length) {
    box.hidden = true;
    return;
  }
  const label = document.createElement("label");
  label.textContent = "Varsle meg når " + sectionName(code) + " har ";
  const select = document.createElement("select");
  select.setAttribute("aria-label", "Antall ledige seter");
  for (const t of options) {
    const o = document.createElement("option");
    o.value = String(t);
    o.textContent = String(t);
    select.append(o);
  }
  select.value = String(options.includes(25) ? 25 : options[0]);
  label.append(select, " eller færre ledige");
  const go = document.createElement("button");
  go.type = "button";
  go.className = "pill alert-pill";
  go.textContent = "Slå på";
  go.addEventListener(
    "click",
    () => void toggleAlert("section", code, Number(select.value)),
  );
  box.append(label, go);
}
$("alertRelease").addEventListener("click", () => void toggleAlert("release"));

// --- Supporters and media: will it sell out, pressure, seats together, when to buy, season, share ---
// Everything here is derived from the same public scans; no extra data points.
const MAPPED_SEATS = { lerkendal: 19015, koteng_arena: 601 };
let lastHistory = null,
  lastRecords = [];
// Sales over ~24 h, scaled to exactly 24 h, for every scan that has a partner 18–30 h earlier.
function standOf(code) {
  if (selectedVenue === "koteng_arena") return "Koteng Arena";
  return STAND_GROUPS.find((g) => g.codes.includes(code))?.name || "Lerkendal";
}
// Sections with the most free seats give the best chance of seats next to each other.
function renderVerdict() {
  const match = matches.find((m) => m.id === current),
    box = $("fullVerdict");
  const last = lastRecords.at(-1);
  const v =
    match && last
      ? fullVerdict({
          available: last.available_seated,
          mapped: MAPPED_SEATS[venueFor(match)],
          forecast: displayedForecast(lastRecords, selectedKickoff),
          hist: lastHistory,
          pace: paceToZero12h(lastRecords, selectedKickoff),
          played: isPlayed(match),
        })
      : null;
  box.hidden = !v;
  if (!v) return;
  box.dataset.level = v.level;
  $("fullVerdictAnswer").textContent = v.answer;
  $("fullVerdictReason").textContent = v.reason;
}
function renderPressure(match, scans, baseline) {
  const el = $("pressureIndex");
  const p = isPlayed(match) || isSeasonPass(match) ? null : pressureIndex(scans, baseline);
  el.hidden = !p;
  if (!p) return null;
  el.dataset.trend = p.value >= 125 ? "down" : p.value < 75 ? "up" : "flat";
  el.textContent = "Trøkk · " + p.label;
  el.title =
    "100 = et vanlig salgsdøgn på denne arenaen (" +
    fmt(p.base) +
    " færre ledige). Siste døgn: " +
    fmt(p.sold) +
    ".";
  return p;
}
function renderTogether() {
  const box = $("togetherList");
  box.replaceChildren();
  const match = matches.find((m) => m.id === current);
  const rows = [...stadiumByCode.values()];
  $("togetherBlock").hidden = !match || isPlayed(match) || !rows.length;
  if ($("togetherBlock").hidden) return;
  const size = Number($("togetherSize").dataset.size || 4);
  const best = seatsTogether(rows, size);
  if (!best.length) {
    const p = document.createElement("p");
    p.className = "fast-note";
    p.textContent = "Ingen felt har " + size + " ledige sitteplasser nå.";
    box.append(p);
    return;
  }
  for (const r of best) {
    const li = document.createElement("li"),
      b = document.createElement("button");
    b.type = "button";
    const name = document.createElement("strong");
    name.textContent = sectionName(r.section_code);
    const info = document.createElement("span");
    info.textContent = fmt(r.free) + " ledige · " + standOf(r.section_code);
    b.append(name, info);
    b.addEventListener("click", () => {
      activateStadiumSection(r.section_code);
      $("stadiumMap").scrollIntoView({ behavior: "smooth", block: "center" });
    });
    li.append(b);
    box.append(li);
  }
}
for (const b of document.querySelectorAll("#togetherSize button"))
  b.addEventListener("click", () => {
    $("togetherSize").dataset.size = b.dataset.size;
    for (const o of document.querySelectorAll("#togetherSize button"))
      o.setAttribute("aria-pressed", String(o === b));
    renderTogether();
  });
function renderTiming(refs) {
  const list = $("timingList");
  list.replaceChildren();
  const groups =
    selectedVenue === "koteng_arena"
      ? KOTENG_CODES.map((c) => ({ name: sectionName(c), codes: [c] }))
      : STAND_GROUPS;
  const rows = refs.flatMap((r) =>
    standTiming(r.sections, groups).map((t) => ({ ...t, title: r.title })),
  );
  $("timingBlock").hidden = !rows.length;
  if (!rows.length) return;
  for (const t of rows.slice(0, 6)) {
    const li = document.createElement("li");
    const name = document.createElement("strong");
    name.textContent = t.name;
    const info = document.createElement("span");
    info.textContent =
      (t.finalShare < 0.01
        ? "nesten fullt"
        : Math.round(t.finalShare * 100) + " % ledige") +
      " ved avspark" +
      (t.share24 !== null
        ? " · " + Math.round(t.share24 * 100) + " % av salget siste døgn"
        : "");
    li.append(name, info);
    list.append(li);
  }
  const late = rows.filter((t) => t.share24 !== null);
  const lateShare = late.length ? median(late.map((t) => t.share24)) : null;
  const fullest = rows[0];
  $("timingAdvice").textContent =
    (fullest.finalShare < 0.15
      ? "Vil du sitte på " +
        fullest.name +
        ", bør du kjøpe tidlig. Den var " +
        (fullest.finalShare < 0.01
          ? "nesten full"
          : "bare " + Math.round(fullest.finalShare * 100) + " % ledig") +
        " ved avspark. "
      : "") +
    (lateShare !== null && lateShare >= 0.4
      ? "Mye av salget kommer det siste døgnet, så de beste plassene forsvinner gjerne da."
      : "") +
    " Basert på kampen mot " +
    [...new Set(rows.map((t) => t.title))].join(" og ") +
    ".";
}
function renderMatchday(match, points) {
  const box = $("matchdayBlock");
  const s = isPlayed(match) ? matchdaySummary(points) : null;
  box.hidden = !s;
  if (!s) return;
  const tiles = [
    ["Ledige ved siste måling", fmt(s.final)],
    [
      "Færre ledige siste døgn",
      s.sold24 === null ? "—" : fmt(Math.max(0, s.sold24)),
    ],
    [
      "Færre ledige siste 3 timer",
      s.sold3 === null ? "—" : fmt(Math.max(0, s.sold3)),
    ],
    [
      "Travleste time",
      s.busiest
        ? "ca. " +
          fmt(Math.round(s.busiest.perHour)) +
          " / t, " +
          hoursText(Math.max(0, s.busiest.h)) +
          " før"
        : "—",
    ],
  ];
  const grid = $("matchdayTiles");
  grid.replaceChildren();
  for (const [k, v] of tiles) {
    const d = document.createElement("div");
    const a = document.createElement("span");
    a.textContent = k;
    const b = document.createElement("strong");
    b.textContent = v;
    d.append(a, b);
    grid.append(d);
  }
}
async function renderSupporter(match, scans, version, id) {
  lastRecords = scans
    .slice()
    .sort((a, b) => Date.parse(a.observed_at) - Date.parse(b.observed_at));
  renderTogether();
  const venue = venueFor(match),
    same = allMatches.filter((m) => venueFor(m) === venue && !isSeasonPass(m));
  let all;
  try {
    all = await Promise.all(
      same.map(async (m) => ({
        match: m,
        title: opponentName(m.title),
        scans: m.id === match.id ? scans : await refScans(m),
      })),
    );
  } catch {
    return;
  }
  if (version !== selectionVersion || current !== id) return;
  const baseline = all.flatMap((r) => dayDrops(r.scans));
  currentPressure = renderPressure(match, scans, baseline);
  renderMatchday(match, curve(scans, match.kickoff_at));
  if (isSeasonPass(match)) $("fullVerdict").hidden = true;
  $("advicePanel").hidden =
    $("togetherBlock").hidden &&
    $("matchdayBlock").hidden &&
    $("timingBlock").hidden;
  const played = all.filter(
    (r) => r.match.id !== match.id && !isSeasonPass(r.match) && isPlayed(r.match),
  );
  if (!played.length) {
    $("timingBlock").hidden = true;
    $("advicePanel").hidden =
      $("togetherBlock").hidden && $("matchdayBlock").hidden;
    return;
  }
  try {
    const refs = await Promise.all(
      played.map(async (r) => ({
        title: r.title,
        sections: await refSections(r.match, r.scans),
      })),
    );
    if (version !== selectionVersion || current !== id) return;
    renderTiming(refs);
  } catch {
    $("timingBlock").hidden = true;
  }
  $("advicePanel").hidden =
    $("togetherBlock").hidden &&
    $("matchdayBlock").hidden &&
    $("timingBlock").hidden;
}
// Season board for the selected team: records across every followed match.
async function renderSeason() {
  const board = $("seasonBoard"),
    team = activeTeam;
  const list = matches.filter((m) => !isSeasonPass(m));
  if (!list.length) {
    board.hidden = true;
    return;
  }
  let all;
  try {
    all = await Promise.all(
      list.map(async (m) => ({
        match: m,
        title: opponentName(m.title),
        scans: await refScans(m),
      })),
    );
  } catch {
    board.hidden = true;
    return;
  }
  if (team !== activeTeam) return;
  all = all.filter((r) => r.scans.length);
  if (!all.length) {
    board.hidden = true;
    return;
  }
  const drops = all.flatMap((r) =>
    dayDrops(r.scans).map((d) => ({ ...d, title: r.title })),
  );
  const bestDay = drops.reduce((a, d) => (!a || d.sold > a.sold ? d : a), null);
  const moved = all
    .map((r) => {
      const s = r.scans
        .slice()
        .sort((a, b) => Date.parse(a.observed_at) - Date.parse(b.observed_at));
      return {
        title: r.title,
        n: s[0].available_seated - s.at(-1).available_seated,
      };
    })
    .reduce((a, x) => (!a || x.n > a.n ? x : a), null);
  const hot = all
    .filter((r) => !isPlayed(r.match))
    .map((r) => ({ title: r.title, p: pressureIndex(r.scans, drops) }))
    .filter((x) => x.p)
    .sort((a, b) => b.p.value - a.p.value)[0];
  const tiles = [
    [
      "Største døgnfall i ledige",
      bestDay && bestDay.sold > 0 ? fmt(bestDay.sold) : "—",
      bestDay && bestDay.sold > 0 ? "mot " + bestDay.title : "",
    ],
    [
      "Størst nedgang i ledige",
      moved && moved.n > 0 ? fmt(moved.n) : "—",
      moved && moved.n > 0 ? "mot " + moved.title : "",
    ],
    ["Hetest nå", hot ? hot.p.label : "—", hot ? hot.title : ""],
  ];
  const grid = $("seasonTiles");
  grid.replaceChildren();
  for (const [k, v, n] of tiles) {
    const d = document.createElement("div");
    d.className = "season-tile";
    const a = document.createElement("span");
    a.className = "caption";
    a.textContent = k;
    const b = document.createElement("strong");
    b.textContent = v;
    const c = document.createElement("small");
    c.textContent = n;
    d.append(a, b, c);
    grid.append(d);
  }
  $("seasonTitle").textContent =
    (team === "women" ? "RBK Kvinner" : "RBK") + " · sesongen så langt";
  board.hidden = false;
}

// --- Share: ready-made text and image for social media --------------------
let currentPressure = null;
function shareText() {
  const match = matches.find((m) => m.id === current),
    last = lastRecords.at(-1);
  if (!match || !last) return "";
  const drops = dayDrops(lastRecords),
    day = drops.at(-1);
  const verdict = $("fullVerdict").hidden
    ? null
    : $("fullVerdictAnswer").textContent;
  const lines = [
    match.title + (match.kickoff_at ? " · " + date(match.kickoff_at) : ""),
    (isPlayed(match)
      ? "Ledige sitteplasser ved siste måling: "
      : "Ledige sitteplasser nå: ") +
      fmt(last.available_seated) +
      (day && day.sold > 0 ? " (" + fmt(day.sold) + " færre siste døgn)" : ""),
  ];
  if (currentPressure) lines.push("Trøkk: " + currentPressure.label);
  if (verdict) lines.push("Blir det fullt? " + verdict);
  lines.push("Følg billettsalget: " + shareURL());
  return lines.join("\n");
}
function shareURL() {
  const match = matches.find((m) => m.id === current);
  return new URL(
    match?.event_key ? "?kamp=" + encodeURIComponent(match.event_key) : "",
    window.location.origin + window.location.pathname,
  ).href;
}
function shareImage() {
  const match = matches.find((m) => m.id === current),
    last = lastRecords.at(-1);
  const c = document.createElement("canvas");
  c.width = 1080;
  c.height = 1080;
  const g = c.getContext("2d");
  g.fillStyle = "#070707";
  g.fillRect(0, 0, 1080, 1080);
  g.strokeStyle = "#d1ad67";
  g.lineWidth = 4;
  g.strokeRect(48, 48, 984, 984);
  const font = (w, s) => w + " " + s + 'px "Segoe UI", system-ui, sans-serif';
  g.fillStyle = "#d8b875";
  g.font = font(800, 30);
  g.fillText("MINISTAUT · BILLETTSTATUS", 100, 140);
  g.fillStyle = "#f7f7f7";
  g.font = font(800, 72);
  g.fillText(match?.title || "", 100, 250, 880);
  g.fillStyle = "#c5c5c5";
  g.font = font(500, 34);
  g.fillText(
    match?.kickoff_at
      ? (isPlayed(match) ? "Spilt " : "Avspark ") + date(match.kickoff_at)
      : "",
    100,
    310,
  );
  g.fillStyle = "#ead6a8";
  g.font = font(850, 200);
  g.fillText(last ? fmt(last.available_seated) : "—", 100, 560, 880);
  g.fillStyle = "#c5c5c5";
  g.font = font(600, 40);
  g.fillText(
    isPlayed(match)
      ? "ledige sitteplasser ved siste måling"
      : "ledige sitteplasser nå",
    100,
    625,
  );
  const day = dayDrops(lastRecords).at(-1);
  let y = 730;
  const line = (t) => {
    g.fillStyle = "#f7f7f7";
    g.font = font(700, 42);
    g.fillText(t, 100, y, 880);
    y += 66;
  };
  if (day && day.sold > 0) line(fmt(day.sold) + " færre ledige siste døgn");
  if (currentPressure) line("Trøkk: " + currentPressure.label);
  if (!$("fullVerdict").hidden)
    line("Blir det fullt? " + $("fullVerdictAnswer").textContent);
  // Recent curve as a faint band above the footnote.
  const pts = lastRecords.slice(-48).map((r) => r.available_seated);
  if (pts.length > 1) {
    const lo = Math.min(...pts),
      hi = Math.max(...pts),
      span = hi - lo || 1;
    g.strokeStyle = "#d8b875";
    g.lineWidth = 5;
    g.beginPath();
    pts.forEach((v, i) => {
      const x = 100 + (i * 880) / (pts.length - 1),
        yy = 890 + ((hi - v) / span) * 50;
      i ? g.lineTo(x, yy) : g.moveTo(x, yy);
    });
    g.globalAlpha = 0.35;
    g.stroke();
    g.globalAlpha = 1;
  }
  g.fillStyle = "#949494";
  g.font = font(500, 26);
  g.fillText(
    "Observerte ledige sitteplasser, ikke bekreftet salg. Ståplasser er ikke med.",
    100,
    990,
    880,
  );
  g.fillText(
    window.location.host + " · uavhengig supporteroversikt",
    100,
    1022,
    880,
  );
  return c;
}
function openShare() {
  const text = shareText();
  if (!text) return;
  $("shareText").value = text;
  const canvas = shareImage();
  $("sharePreview").src = canvas.toDataURL("image/png");
  $("shareStatus").textContent = "";
  $("shareDialog").showModal?.();
}
$("shareMatch").addEventListener("click", openShare);
$("shareClose").addEventListener("click", () => $("shareDialog").close());
$("shareCopy").addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText($("shareText").value);
    $("shareStatus").textContent = "Teksten er kopiert.";
  } catch {
    $("shareText").select();
    $("shareStatus").textContent = "Marker teksten og kopier den manuelt.";
  }
});
$("shareDownload").addEventListener("click", () => {
  const a = document.createElement("a");
  a.href = $("sharePreview").src;
  a.download =
    "ministaut-" +
    (matches.find((m) => m.id === current)?.event_key || "kamp") +
    ".png";
  a.click();
});
$("shareNative").addEventListener("click", async () => {
  try {
    const blob = await new Promise((r) => shareImage().toBlob(r, "image/png"));
    const file = new File([blob], "ministaut.png", { type: "image/png" });
    const data = { text: $("shareText").value, files: [file] };
    if (navigator.canShare?.(data)) await navigator.share(data);
    else await navigator.share({ text: $("shareText").value });
  } catch (error) {
    if (error?.name !== "AbortError")
      $("shareStatus").textContent =
        "Deling er ikke tilgjengelig her. Bruk Kopier tekst og Last ned bilde.";
  }
});

async function selectMatch(id) {
  const match = matches.find((m) => m.id === id);
  if (!match) return;
  const changed = current !== id,
    version = ++selectionVersion;
  selectedVenue = venueFor(match);
  $("availabilityCaption").textContent = "Ledige sitteplasser";
  $("stadiumHeading").textContent =
    selectedVenue === "koteng_arena"
      ? "KOTENG ARENA · TRIBUNEKART"
      : "LERKENDAL · TRIBUNEKART";
  $("stadiumIntro").textContent =
    selectedVenue === "koteng_arena"
      ? "Velg et felt for å se ledige sitteplasser på Koteng Arena. Ståplassene er ikke med i oversikten."
      : "Velg et felt for å se ledige sitteplasser på Lerkendal.";
  $("ticketLabel").textContent = isSeasonPass(match) ? "Se sesongkort hos RBK" : "Finn billetter";
  $("tickets").hidden = isPlayed(match);
  document.querySelector(".forecast-panel").hidden = isPlayed(match) || isSeasonPass(match);
  document.querySelector(".results").dataset.played = String(isPlayed(match));
  $("availabilityCaption").textContent = isSeasonPass(match)
    ? "Registrerte tilgjengelige sitteplasser i sesongkortkartet"
    : isPlayed(match)
      ? "Ledige ved siste måling"
      : "Ledige sitteplasser";
  $("shareMatch").disabled = true;
  $("campaignHeading").textContent =
    "Ses på " +
    (selectedVenue === "koteng_arena" ? "Koteng Arena!" : "Lerkendal!");
  current = id;
  updateSelectedCards();
  if (isPlayed(match)) $("playedSection").open = true;
  $("selectedMatchTitle").textContent = match.title;
  $("matchEyebrow").textContent =
    selectedVenue === "koteng_arena"
      ? "KOTENG ARENA · BILLETTOVERSIKT"
      : "LERKENDAL · BILLETTOVERSIKT";
  selectedKickoff = match.kickoff_at || null;
  $("kickoff").textContent = isSeasonPass(match)
    ? "Sesongkort · ingen kampstart"
    : match.kickoff_at
      ? (isPlayed(match) ? "Spilt " : "Avspark ") + date(match.kickoff_at)
      : "Avspark ikke registrert";
  const key = String(match.event_key || "");
  $("tickets").href = /^[A-Za-z0-9_-]{8,100}$/.test(key)
    ? "https://billett.rbk.no/checkout/" + key
    : "https://billett.rbk.no/";
  if (changed) {
    lastComparison = null;
    $("error").textContent = "";
    render([]);
    renderSectionRecords([]);
    renderSections(null, null);
    $("comparePanel").hidden = true;
    $("historyForecast").hidden = true;
    $("sectionAlert").hidden = true;
    alertStatus("");
    lastHistory = null;
    lastRecords = [];
    currentPressure = null;
    $("advicePanel").hidden = true;
    $("pressureIndex").hidden = true;
    $("fullVerdict").hidden = true;
  }
  renderAlerts();
  $("stats").setAttribute("aria-busy", "true");
  try {
    const table =
      categoryFor(match) === "women"
        ? "ministaut_koteng_scans"
        : "ministaut_scans";
    const statusFilter =
      categoryFor(match) === "women" ? "in.(observed,accepted)" : "eq.accepted";
    const data = await load(
      table +
        "?select=id,observed_at,available_seated,locked_fields&reading_status=" +
        statusFilter +
        "&match_id=eq." +
        encodeURIComponent(id) +
        "&order=observed_at.desc&limit=500",
    );
    if (version !== selectionVersion || id !== current) return;
    render(data);
    renderSectionRecords(data);
    await loadSections(data[0] || null, version, id, data);
    void renderComparison(match, data, version, id);
    void renderSupporter(match, data, version, id);
  } catch (error) {
    if (version === selectionVersion)
      $("error").textContent =
        "Kunne ikke hente tall for valgt kamp. Prøv Oppdater.";
  } finally {
    if (version === selectionVersion) $("stats").removeAttribute("aria-busy");
  }
}

async function showTeam(next, { share = true } = {}) {
  if (next !== "men" && next !== "women") return;
  const changed = next !== activeTeam;
  activeTeam = next;
  if (changed) {
    ++selectionVersion;
    current = null;
    selectedKickoff = null;
    lastObservedAt = null;
    chartSignature = "";
    $("playedSection").open = false;
  }
  matches = allMatches.filter((m) => categoryFor(m) === activeTeam);
  $("teamMen").setAttribute("aria-pressed", String(activeTeam === "men"));
  $("teamWomen").setAttribute("aria-pressed", String(activeTeam === "women"));
  const upcomingCount = (team) =>
    allMatches.filter((m) => categoryFor(m) === team && !isSeasonPass(m) && !isPlayed(m)).length +
    " kommende";
  $("teamMenCount").textContent = upcomingCount("men");
  $("teamWomenCount").textContent = upcomingCount("women");
  $("teamOverline").textContent =
    activeTeam === "women"
      ? "BILLETTSTATUS · RBK KVINNER"
      : "BILLETTSTATUS · RBK";
  $("page-title").innerHTML =
    activeTeam === "women"
      ? "Følg billettsalget<br>til <em>RBK Kvinner.</em>"
      : "Følg billettsalget<br>til <em>Rosenborg.</em>";
  $("teamDescription").textContent =
    activeTeam === "women"
      ? "Følg ledige sitteplasser til RBK Kvinners kamper."
      : "Følg ledige sitteplasser og utviklingen fram mot avspark.";
  $("picker-title").textContent =
    activeTeam === "women"
      ? "RBK Kvinner · kommende kamper"
      : "Kommende hjemmekamper";
  $("womenPending").hidden = activeTeam !== "women" || matches.length > 0;
  if (changed) $("seasonBoard").hidden = true;
  $("match-details").hidden = matches.length === 0;
  if (changed) {
    render([]);
    renderSectionRecords([]);
    renderSections(null, null);
  }
  if (changed) cardSignature = "";
  buildCards();
  void renderSeason();
  if (share) updateShareLink(null);
  if (!matches.length) {
    current = null;
    return;
  }
  // Default to the next match; the archive is only picked when nothing is coming up.
  const chosen = matches.some((m) => m.id === current)
    ? current
    : chooseByLink(matches) ||
      (matches.find((m) => !isSeasonPass(m) && !isPlayed(m)) ||
        matches.find(isSeasonPass) || matches[matches.length - 1]).id;
  await Promise.all([selectMatch(chosen), refreshCardData()]);
}
for (const b of document.querySelectorAll("[data-chart-hours]"))
  b.addEventListener("click", () => {
    const chosen = Number(b.dataset.chartHours);
    if (chosen === chartRangeHours) return;
    chartRangeHours = chosen;
    chartSignature = "";
    graph(latestChartInput);
  });
$("teamMen").addEventListener("click", () => {
  if (activeTeam !== "men") void showTeam("men");
});
$("teamWomen").addEventListener("click", () => {
  if (activeTeam !== "women") void showTeam("women");
});
async function refresh() {
  if (refreshPromise) return refreshPromise;
  refreshPromise = (async () => {
    $("error").textContent = "";
    $("retryLoad").hidden = true;
    const [men, women] = await Promise.all([
      load(
        "ministaut_matches?select=id,event_key,title,kickoff_at&is_published=eq.true&order=kickoff_at.asc",
      ),
      load(
        "ministaut_koteng_matches?select=id,event_key,title,kickoff_at,venue_id,team_category&is_published=eq.true&order=kickoff_at.asc",
      ),
    ]);
    allMatches = men
      .map((m) => ({ ...m, team_category: "men", venue_id: "lerkendal" }))
      .concat(women);
    if (!teamInitialized) {
      activeTeam = teamFromURL(allMatches, window.location.search);
      teamInitialized = true;
    }
    await showTeam(activeTeam, { share: false });
  })()
    .catch((error) => {
      $("error").textContent = "Kunne ikke hente billettdata. Prøv igjen.";
      $("retryLoad").hidden = false;
      if (!allMatches.length) {
        $("matchCards").textContent =
          "Billettoversikten er midlertidig utilgjengelig.";
        $("age").textContent = "Ingen måling tilgjengelig";
        $("match-details").hidden = true;
      }
    })
    .finally(() => {
      refreshPromise = null;
    });
  return refreshPromise;
}
$("refresh").addEventListener("click", () => {
  const btn = $("refresh");
  btn.disabled = true;
  $("refreshLabel").textContent = "Henter…";
  btn.setAttribute("aria-busy", "true");
  void refresh().finally(() => {
    btn.disabled = false;
    $("refreshLabel").textContent = "Oppdater";
    btn.removeAttribute("aria-busy");
  });
});

// A local view change must never fetch inventory or replace the verified geometry.
$("mapExpand").addEventListener("click", () => {
  const expanded = document
    .querySelector(".stadium-map-shell")
    .classList.toggle("is-expanded");
  $("mapExpand").setAttribute("aria-expanded", String(expanded));
  $("mapExpand").textContent = expanded ? "Tilpass kart" : "Forstørr kart";
  if (expanded) $("stadiumMap").focus({ preventScroll: true });
});

// Keep axis type in CSS pixels after rotation, resizing or expanding the map.
let lastChartWidth = 0,
  resizeFrame = 0,
  lastComparison = null;
if (typeof ResizeObserver !== "undefined") {
  const observer = new ResizeObserver(() => {
    const width = wrapWidth();
    if (!width || width === lastChartWidth) return;
    lastChartWidth = width;
    cancelAnimationFrame(resizeFrame);
    resizeFrame = requestAnimationFrame(() => {
      chartSignature = "";
      graph(latestChartInput);
      if (lastComparison) drawCompare(...lastComparison);
    });
  });
  observer.observe($("chart"));
}

// The large field list is an equally useful keyboard and touch path to the map.
const smallScreen = window.matchMedia("(max-width:560px)");
if (smallScreen.matches) document.querySelector(".field-browser").open = true;
smallScreen.addEventListener("change", (event) => {
  if (event.matches) document.querySelector(".field-browser").open = true;
});
if (typeof IntersectionObserver !== "undefined") {
  const links = [...document.querySelectorAll(".top-links a")];
  const sectionObserver = new IntersectionObserver(
    (entries) => {
      const visible = entries
        .filter((entry) => entry.isIntersecting)
        .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)[0];
      if (!visible) return;
      for (const link of links) {
        if (link.hash === "#" + visible.target.id)
          link.setAttribute("aria-current", "location");
        else link.removeAttribute("aria-current");
      }
    },
    { rootMargin: "-5% 0px -65% 0px" },
  );
  for (const link of links) {
    const target = document.querySelector(link.hash);
    if (target) sectionObserver.observe(target);
  }
}
$("retryLoad").addEventListener("click", () => void refresh());
void refresh();
void loadPushState();
document.addEventListener("visibilitychange", () => {
  if (!document.hidden) void refresh();
});
setInterval(() => {
  updateAgeIndicator();
  if (!document.hidden) void refresh();
}, 60000);
