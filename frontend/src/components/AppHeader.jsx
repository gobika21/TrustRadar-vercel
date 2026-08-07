import React from "react";
import { TrustRadarLogo } from "./TrustRadarLogo";

const TABS = [
  { id: "scan", label: "New Scan" },
  { id: "history", label: "History" },
];

export function AppHeader({ activeTab, onTabChange, historyCount = 0 }) {
  return (
    <section className="flex items-center justify-between gap-3 pt-2 pb-6">
      <div className="flex items-center gap-8">
        <TrustRadarLogo />
        {onTabChange ? (
          <nav className="flex items-center gap-6">
            {TABS.map((tab) => (
              <button
                key={tab.id}
                type="button"
                onClick={() => onTabChange(tab.id)}
                className={`flex items-center gap-1.5 border-b-2 pb-1 font-sans text-[0.86rem] font-semibold transition-colors ${
                  activeTab === tab.id
                    ? "border-amber text-ink"
                    : "border-transparent text-muted hover:text-ink"
                }`}
              >
                {tab.label}
                {tab.id === "history" && historyCount > 0 ? (
                  <span className="badge badge-info px-1.5">{historyCount}</span>
                ) : null}
              </button>
            ))}
          </nav>
        ) : null}
      </div>
      <div className="flex items-center gap-3">
        <span className="hidden sm:inline-flex items-center rounded-lg border border-line bg-panel px-3.5 py-2 font-mono text-[0.72rem] font-semibold uppercase tracking-wide text-muted">
          Verify before you apply
        </span>
      </div>
    </section>
  );
}
