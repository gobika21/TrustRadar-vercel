import React from "react";

export function TrustRadarLogo() {
  return (
    <svg className="brand-logo text-only-logo" viewBox="0 0 210 52" role="img" aria-label="TrustRadar">
      <defs>
        <linearGradient id="trust-radar-word-gradient" x1="104" y1="12" x2="206" y2="42" gradientUnits="userSpaceOnUse">
          <stop stopColor="#7c3aed">
            <animate attributeName="stop-color" values="#7c3aed;#00b8d9;#7c3aed" dur="5.8s" repeatCount="indefinite" />
          </stop>
          <stop offset="1" stopColor="#f97316">
            <animate attributeName="stop-color" values="#f97316;#d946ef;#f97316" dur="5.8s" repeatCount="indefinite" />
          </stop>
        </linearGradient>
        <linearGradient id="trust-radar-shine" x1="-90" y1="0" x2="-20" y2="0" gradientUnits="userSpaceOnUse">
          <stop offset="0" stopColor="#ffffff" stopOpacity="0" />
          <stop offset="0.45" stopColor="#ffffff" stopOpacity="0" />
          <stop offset="0.5" stopColor="#ffffff" stopOpacity="0.85" />
          <stop offset="0.55" stopColor="#ffffff" stopOpacity="0" />
          <stop offset="1" stopColor="#ffffff" stopOpacity="0" />
          <animate attributeName="x1" values="-90;230" dur="4.6s" repeatCount="indefinite" />
          <animate attributeName="x2" values="-20;300" dur="4.6s" repeatCount="indefinite" />
        </linearGradient>
      </defs>

      <text className="brand-logo-text" x="0" y="29">
        <tspan className="brand-logo-text-primary">Trust</tspan>
        <tspan fill="url(#trust-radar-word-gradient)">Radar</tspan>
      </text>
      <text className="brand-logo-text brand-logo-shine" x="0" y="29">TrustRadar</text>
    </svg>
  );
}
