/** Render in CSS pixels so SVG text stays legible at every viewport. */
export function chartDimensions(containerWidth) {
  const W = Math.max(220, Math.round(containerWidth || 640));
  return { W, H: W < 520 ? 260 : 290, L: 54, R: 20, T: 24, B: 40 };
}

export function shortDate(value, compact = false) {
  return new Intl.DateTimeFormat("nb-NO", {
    timeZone: "Europe/Oslo",
    day: "numeric",
    month: "short",
    ...(compact ? {} : { hour: "2-digit", minute: "2-digit" }),
  }).format(new Date(value));
}
