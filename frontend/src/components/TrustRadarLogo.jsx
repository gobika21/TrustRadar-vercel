import React from "react";

export function TrustRadarLogo() {
  return (
    <div className="flex items-center gap-2.5">
      <span
        aria-hidden="true"
        className="relative inline-grid h-7.5 w-7.5 flex-none place-items-center rounded-full"
        style={{
          background:
            "conic-gradient(from 220deg, var(--color-amber) 0deg, var(--color-amber-strong) 140deg, var(--color-line) 140deg 360deg)",
        }}
      >
        <span className="h-3 w-3 rounded-full bg-panel" />
      </span>
      <span className="font-display font-bold text-[1.2rem] uppercase tracking-tight leading-none">
        <span className="text-ink">Trust</span>
        <span className="text-amber">Radar</span>
      </span>
    </div>
  );
}
