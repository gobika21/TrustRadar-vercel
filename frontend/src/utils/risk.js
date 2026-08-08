export function tierClass(level) {
  if (level === "critical") return "danger";
  if (level === "high") return "warning";
  if (level === "medium") return "review";
  return "clear";
}
