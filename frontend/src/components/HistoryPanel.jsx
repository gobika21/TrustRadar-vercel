import React from "react";
import { Clock3, Trash2 } from "lucide-react";

export function HistoryPanel({ history, onSelect, onClear }) {
  return (
    <section className="history-panel">
      <div className="section-title">
        <div>
          <strong>Recent checks</strong>
        </div>
        <button type="button" onClick={onClear} disabled={!history.length} aria-label="Clear history">
          <Trash2 size={14} />
        </button>
      </div>

      {history.length ? (
        <div className="history-list inline-history">
          {history.map((entry) => (
            <button className="history-item" type="button" key={entry.id} onClick={() => onSelect(entry)}>
              <Clock3 size={15} />
              <span>
                <strong>{entry.label}</strong>
                <small>{formatTime(entry.createdAt)} · {entry.result.tier}</small>
              </span>
              <em className={entry.result.tier_level}>{entry.result.score}</em>
            </button>
          ))}
        </div>
      ) : (
        <p className="history-empty"><span>No checks yet.</span></p>
      )}
    </section>
  );
}

function formatTime(value) {
  return new Intl.DateTimeFormat(undefined, { hour: "2-digit", minute: "2-digit" }).format(new Date(value));
}
