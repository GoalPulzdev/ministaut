/** One card anatomy for upcoming and archived matches. All source text is escaped by DOM APIs. */
export function createMatchCard(match, { played, formatDate, onSelect }) {
  const el = (tag, className, text) => {
    const node = document.createElement(tag);
    node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  };
  const button = el("button", "match-tile");
  button.type = "button";
  button.dataset.matchId = match.id;
  if (played) button.dataset.played = "true";
  button.setAttribute("aria-label", "Vis billettstatus for " + match.title);
  button.setAttribute("aria-pressed", "false");
  const top = el("span", "tile-top");
  const pill = el("span", "tile-pill", played ? "SPILT" : "SE KAMP");
  top.append(
    el(
      "span",
      "",
      match.kickoff_at
        ? (played ? "Spilt " : "Avspark ") + formatDate(match.kickoff_at)
        : "Kampstart kommer",
    ),
    pill,
  );
  const matchup = el("span", "tile-matchup");
  matchup.append(el("span", "tile-title", match.title));
  const bottom = el("span", "tile-bottom");
  const summary = el("span", "tile-summary");
  const value = el("span", "tile-value", "—");
  summary.append(value, el("span", "tile-unit", "ledige sitteplasser"));
  const foot = el("span", "tile-foot", "Henter siste oppdatering …");
  bottom.append(summary, foot);
  button.append(top, matchup, bottom);
  button.addEventListener("click", onSelect);
  return { button, pill, value, foot, played };
}
