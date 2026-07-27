import React from "react";
import { ExternalLink, Globe, Radar, ShieldCheck, Sparkles } from "lucide-react";
import { severityLabel, tierClass } from "../utils/risk";

const loadingSteps = [
  { at: 8, label: "Reading the job post" },
  { at: 28, label: "Scanning for scam language" },
  { at: 50, label: "Checking links and domains" },
  { at: 72, label: "Searching for public warnings" },
  { at: 88, label: "Building your recommendation" },
];

export function ResultPanel({ result, loading, progress = 0 }) {
  if (loading) return <LoadingPanel progress={progress} />;
  if (!result) return <EmptyPanel />;

  const recommendation = result.recommendation || fallbackRecommendation(result);

  return (
    <aside className={`result-panel verdict-panel ${tierClass(result.tier_level)}`}>
      <section className="verdict-hero">
        <div>
          <h2>{recommendation.label}</h2>
          <p>{recommendation.detail}</p>
        </div>
        <ScoreGauge score={result.score} />
      </section>

      <LiveVerification evidence={buildEvidenceList(result)} />
    </aside>
  );
}

const GAUGE_TICKS = 26;
const GAUGE_STOPS = [
  { t: 0, rgb: [22, 163, 74] },
  { t: 0.25, rgb: [132, 204, 22] },
  { t: 0.5, rgb: [234, 179, 8] },
  { t: 0.75, rgb: [249, 115, 22] },
  { t: 1, rgb: [239, 68, 68] },
];

function gaugeColor(t) {
  for (let i = 0; i < GAUGE_STOPS.length - 1; i += 1) {
    const start = GAUGE_STOPS[i];
    const end = GAUGE_STOPS[i + 1];
    if (t >= start.t && t <= end.t) {
      const span = end.t - start.t || 1;
      const localT = (t - start.t) / span;
      const rgb = start.rgb.map((channel, index) => Math.round(channel + (end.rgb[index] - channel) * localT));
      return `rgb(${rgb.join(",")})`;
    }
  }
  return `rgb(${GAUGE_STOPS[GAUGE_STOPS.length - 1].rgb.join(",")})`;
}

function ScoreGauge({ score }) {
  const activeT = Math.max(0, Math.min(100, score)) / 100;
  return (
    <div className="score-gauge">
      <svg viewBox="0 0 120 68" aria-hidden="true">
        {Array.from({ length: GAUGE_TICKS }).map((_, index) => {
          const t = index / (GAUGE_TICKS - 1);
          const angle = -90 + t * 180;
          const isActive = t <= activeT;
          return (
            <line
              key={index}
              x1="60"
              y1="8"
              x2="60"
              y2="21"
              stroke={isActive ? gaugeColor(t) : "var(--line)"}
              strokeWidth="4.4"
              strokeLinecap="round"
              transform={`rotate(${angle} 60 64)`}
            />
          );
        })}
      </svg>
      <div className="score-gauge-readout">
        <strong>{score}</strong>
        <span>out of 100</span>
      </div>
    </div>
  );
}

function EmptyPanel() {
  return (
    <aside className="result-panel intro-panel">
      <div className="intro-icon"><Radar size={30} /></div>
      <h2>Know before you apply.</h2>
      <p>
        Paste a job post, recruiter message, or link. TrustRadar checks scam patterns,
        employer signals, domains, and public web results, then gives a clear recommendation.
      </p>
      <div className="trust-cards">
        <span><ShieldCheck size={16} /> Scam patterns</span>
        <span><Globe size={16} /> Employer proof</span>
        <span><Sparkles size={16} /> Apply guidance</span>
      </div>
    </aside>
  );
}

function LoadingPanel({ progress }) {
  const activeStep = [...loadingSteps].reverse().find((step) => progress >= step.at) || loadingSteps[0];

  return (
    <aside className="result-panel loading-panel">
      <div className="loading-ring" aria-hidden="true">
        <svg viewBox="0 0 100 100">
          <circle className="ring-track" cx="50" cy="50" r="42" />
          <circle
            className="ring-progress"
            cx="50"
            cy="50"
            r="42"
            style={{ strokeDashoffset: 264 - (264 * progress) / 100 }}
          />
        </svg>
        <strong>{progress}%</strong>
      </div>
      <p className="eyebrow">Review in progress</p>
      <h2>Checking the posting</h2>
      <p className="loading-step" aria-live="polite">{activeStep.label}&hellip;</p>
    </aside>
  );
}

function LiveVerification({ evidence }) {
  const reviewedEvidence = evidence || [];

  return (
    <section className="report-section compact-live">
      <h3>Evidence reviewed</h3>
      <div className="evidence-list">
        {reviewedEvidence.length ? reviewedEvidence.map((item, index) => (
          <article className="evidence" key={`${item.label}-${index}`}>
            <Globe size={16} />
            <div>
              <div className="evidence-title">
                <strong>{item.label}</strong>
                <span className={item.severity}>{severityLabel(item.severity)}</span>
              </div>
              <p>{item.detail}</p>
              {item.links?.length ? (
                <div className="evidence-links">
                  {item.links.slice(0, 3).map((link) => (
                    <a href={link.url} target="_blank" rel="noreferrer" key={`${item.label}-${link.url}`}>
                      {link.label} <ExternalLink size={12} />
                    </a>
                  ))}
                </div>
              ) : null}
            </div>
          </article>
        )) : (
          <article className="evidence">
            <Globe size={16} />
            <div>
              <div className="evidence-title">
                <strong>No live evidence found</strong>
                <span className="medium">Review</span>
              </div>
              <p>Paste a public job link or company site if you want TrustRadar to verify domains and web signals.</p>
            </div>
          </article>
        )}
      </div>
    </section>
  );
}

function fallbackRecommendation(result) {
  if (result.tier_level === "critical") {
    return {
      label: "Don't apply to this",
      detail: result.summary,
    };
  }
  if (result.tier_level === "high") {
    return {
      label: "Do not engage yet",
      detail: result.summary,
    };
  }
  if (result.tier_level === "medium") {
    return {
      label: "Apply with caution",
      detail: result.summary,
    };
  }
  return {
    label: "Likely safe to apply",
    detail: "No strong scam indicators were found. Confirm the employer identity before sharing personal information.",
  };
}

function buildEvidenceList(result) {
  const patternEvidence = (result.pattern_findings || []).map((item) => ({
    label: item.label,
    severity: item.severity,
    detail: item.explanation,
    source: "pattern",
    links: [],
  }));
  return [...patternEvidence, ...(result.live_evidence || [])];
}
