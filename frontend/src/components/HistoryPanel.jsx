import React from "react";
import { Clock3, Trash2 } from "lucide-react";

const TIER_BADGE = {
  critical: "badge-critical",
  high: "badge-critical",
  medium: "badge-medium",
  low: "badge-info",
};

export function HistoryPanel({ history, onSelect, onClear, selectedId }) {
  return (
    <section className="card grid gap-3 p-4.5 pb-2 min-h-[460px] content-start">
      <div className="flex items-center justify-between">
        <div>
          <strong className="text-[0.86rem] font-bold">Recent checks</strong>
          <p className="m-0 mt-0.5 text-[0.74rem] text-muted">Select one to see the full analysis</p>
        </div>
        <button
          className="grid h-7.5 w-7.5 place-items-center rounded-full border border-line text-muted transition-colors hover:not-disabled:text-red hover:not-disabled:border-red/40 disabled:opacity-40"
          type="button"
          onClick={onClear}
          disabled={!history.length}
          aria-label="Clear history"
        >
          <Trash2 size={14} />
        </button>
      </div>

      {history.length ? (
        <div className="grid gap-2 max-h-[560px] overflow-y-auto pb-3">
          {history.map((entry) => (
            <button
              className={`flex items-center gap-2.5 w-full rounded-lg border px-3 py-2.5 text-left text-ink transition-transform hover:-translate-y-px ${
                entry.id === selectedId
                  ? "border-amber/55 bg-amber/8 shadow-[inset_3px_0_0_var(--color-amber)] hover:translate-y-0"
                  : "border-line bg-field"
              }`}
              type="button"
              key={entry.id}
              aria-current={entry.id === selectedId}
              onClick={() => onSelect(entry)}
            >
              <Clock3 size={15} className="flex-none text-muted-2" />
              <span className="min-w-0 flex-1 grid gap-0.5">
                <strong className="text-[0.82rem] font-semibold whitespace-nowrap overflow-hidden text-ellipsis">
                  {entry.label}
                </strong>
                <small className="text-[0.72rem] text-muted">
                  {formatDateTime(entry.createdAt)} &middot; {entry.result.tier}
                </small>
              </span>
              <em className={`badge not-italic font-extrabold ${TIER_BADGE[entry.result.tier_level] || ""}`}>
                {entry.result.score}
              </em>
            </button>
          ))}
        </div>
      ) : (
        <p className="m-0 mb-3.5 rounded-lg border border-dashed border-line px-3 py-5.5 text-center text-[0.82rem] text-muted-2">
          No checks yet.
        </p>
      )}
    </section>
  );
}

function formatDateTime(value) {
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}
