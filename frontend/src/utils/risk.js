export function severityLabel(level) {
  return level === "critical" ? "Critical" : level === "high" ? "High" : level === "medium" ? "Medium" : "Info";
}

export function tierClass(level) {
  if (level === "critical") return "danger";
  if (level === "high") return "warning";
  if (level === "medium") return "review";
  return "clear";
}
