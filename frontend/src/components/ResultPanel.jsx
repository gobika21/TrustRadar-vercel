import React from "react";
import {
  AlertTriangle,
  Bell,
  Briefcase,
  Check,
  Clock3,
  ExternalLink,
  Globe,
  Lock,
  Mail,
  Radar,
  Search,
  ShieldAlert,
  ShieldCheck,
  ShieldOff,
  Sparkles,
  Users,
} from "lucide-react";
import { tierClass } from "../utils/risk";

const loadingSteps = [
  { at: 8, label: "Reading the job post" },
  { at: 28, label: "Scanning for scam language" },
  { at: 50, label: "Checking links and domains" },
  { at: 72, label: "Searching for public warnings" },
  { at: 88, label: "Building your recommendation" },
];

export function ResultPanel({ result, loading, progress = 0, emptyHint = "scan" }) {
  if (loading) return <LoadingPanel progress={progress} />;
  if (!result) return <EmptyPanel hint={emptyHint} />;

  const recommendation = result.recommendation || fallbackRecommendation(result);
  const evidence = buildEvidenceList(result);
  const tone = tierClass(result.tier_level);
  const categories = deriveCategoryScores(result, evidence);

  return (
    <aside className={`card tone-${tone} @container grid content-start gap-4 p-5.5 min-h-[460px]`}>
      <section
        className="flex items-start gap-6 pb-5 border-b"
        style={{ borderColor: "color-mix(in srgb, var(--tone) 30%, var(--color-line))" }}
      >
        <ScoreGauge score={result.score} tierLevel={result.tier_level} />
        <div>
          <h2
            className="m-0 mb-2 font-display font-semibold text-[1.5rem] uppercase tracking-tight"
            style={{ color: "var(--tone-strong)" }}
          >
            {recommendation.label}
          </h2>
          <p className="m-0 max-w-[520px] text-[0.88rem] leading-relaxed text-muted">{recommendation.detail}</p>
        </div>
      </section>

      <SubScores categories={categories} />

      <div className="grid grid-cols-1 @lg:grid-cols-2 items-start gap-x-6 gap-y-4">
        <WhyThisScore evidence={evidence} />
        <NextSteps recommendations={result.recommendations} />
      </div>
    </aside>
  );
}

const CATEGORY_DEFS = [
  { key: "domain", label: "Domain & Hosting", icon: Globe, keywords: ["domain", "whois", "registra", "hosting", "dns", "nameserver", "ssl", "certificate"] },
  { key: "content", label: "Content Signals", icon: ShieldAlert, keywords: ["scam", "urgen", "language", "promise", "fee", "salary", "pattern", "phrase", "grammar", "pressure"] },
  { key: "company", label: "Company Presence", icon: Briefcase, keywords: ["website", "footprint", "company", "profile", "about", "linkedin"] },
  { key: "social", label: "Social & Reputation", icon: Users, keywords: ["search", "review", "complaint", "reputation", "report", "fraud", "warning"] },
  { key: "technical", label: "Technical Trust", icon: Lock, keywords: ["ssl", "certificate", "https", "security", "encrypt", "technical"] },
];

function deriveCategoryScores(result, evidence) {
  const overall = Math.max(0, Math.min(100, result.score ?? 50));

  return CATEGORY_DEFS.map((def) => {
    const matches = evidence.filter((item) => {
      const haystack = `${item.label || ""} ${item.detail || ""} ${item.takeaway || ""}`.toLowerCase();
      return def.keywords.some((keyword) => haystack.includes(keyword));
    });

    let score = overall;
    let touched = false;
    matches.forEach((item) => {
      touched = true;
      if (item.severity === "critical" || item.severity === "high") score -= 30;
      else if (item.severity === "medium") score -= 15;
      else if (item.severity === "info" || item.severity === "positive") score += 8;
    });

    score = Math.max(0, Math.min(100, Math.round(score)));
    return { ...def, score, tier: scoreTier(score), touched };
  });
}

function scoreTier(score) {
  if (score < 30) return { label: "Very Low", tone: "var(--color-red)" };
  if (score < 55) return { label: "Low", tone: "var(--color-amber)" };
  if (score < 75) return { label: "Moderate", tone: "var(--color-amber)" };
  return { label: "High", tone: "var(--color-green)" };
}

function SubScores({ categories }) {
  return (
    <section className="grid grid-cols-2 @sm:grid-cols-3 @lg:grid-cols-5 gap-px bg-line rounded-lg overflow-hidden border border-line">
      {categories.map((category) => {
        const Icon = category.icon;
        return (
          <div key={category.key} className="bg-panel p-3.5">
            <div className="flex items-start gap-1.5 mb-2.5 min-h-[2.4em] text-[0.72rem] font-semibold leading-tight text-muted">
              <Icon size={13} className="flex-none mt-0.5" />
              <span>{category.label}</span>
            </div>
            <div className="font-display font-bold text-[1.4rem] leading-none text-ink">
              {category.score}
              <span className="font-sans font-normal text-[0.78rem] text-muted">/100</span>
            </div>
            <div
              className="mt-1.5 mb-2.5 text-[0.68rem] font-extrabold uppercase tracking-wide"
              style={{ color: category.tier.tone }}
            >
              {category.tier.label}
            </div>
            <div className="h-1 rounded-full bg-field overflow-hidden">
              <div
                className="h-full rounded-full"
                style={{ width: `${category.score}%`, background: category.tier.tone }}
              />
            </div>
          </div>
        );
      })}
    </section>
  );
}

const IMPACT_TONE_CLASSES = {
  red: { badge: "bg-red-strong" },
  amber: { badge: "bg-amber-strong" },
  green: { badge: "bg-green-strong" },
};

function WhyThisScore({ evidence }) {
  const notable = evidence.filter((item) => item.severity);
  const items = notable.length
    ? notable
    : [
        {
          label: "No notable scam signals",
          severity: "positive",
          detail: "No scam-language patterns or negative public signals were found for this posting.",
        },
      ];

  return (
    <section>
      <h3 className="m-0 mb-2.5 text-[0.82rem] font-bold uppercase tracking-wide text-muted">Why this score?</h3>
      <ul className="m-0 grid p-0 list-none rounded-lg border border-line overflow-hidden bg-panel">
        {items.map((item, index) => {
          const isPositive = item.severity === "info" || item.severity === "positive";
          const isHigh = item.severity === "critical" || item.severity === "high";
          const toneClasses = IMPACT_TONE_CLASSES[isPositive ? "green" : isHigh ? "red" : "amber"];
          return (
            <li
              key={index}
              className={`flex items-start gap-3 px-4 py-3.5 ${index < items.length - 1 ? "border-b border-line" : ""}`}
            >
              <span
                className={`grid h-8 w-8 flex-none place-items-center rounded-full text-white ${toneClasses.badge}`}
              >
                {isPositive ? <Check size={17} strokeWidth={3} /> : <AlertTriangle size={16} strokeWidth={2.5} />}
              </span>
              <div className="min-w-0 flex-1">
                <div className="text-[0.85rem] font-semibold text-ink">{item.label}</div>
                <div className="text-[0.78rem] text-muted leading-relaxed">{item.takeaway || item.detail}</div>
                {item.links?.length ? (
                  <div className="flex flex-wrap gap-2 mt-2">
                    <span className="w-full -mb-0.5 text-[0.68rem] font-bold uppercase tracking-wide text-muted-2">
                      Sources
                    </span>
                    {item.links.slice(0, 3).map((link) => (
                      <a
                        className="inline-flex items-center gap-1 rounded-full border border-line bg-field px-2.5 py-1.5 text-[0.72rem] font-semibold text-amber-strong no-underline hover:border-amber/45"
                        href={link.url}
                        target="_blank"
                        rel="noreferrer"
                        key={`${item.label}-${link.url}`}
                      >
                        {link.label} <ExternalLink size={12} />
                      </a>
                    ))}
                  </div>
                ) : null}
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

const NEXT_STEP_ICONS = [ShieldOff, Search, Mail, Users, Bell];

function NextSteps({ recommendations }) {
  if (!recommendations?.length) return null;
  return (
    <section>
      <h3 className="m-0 mb-2.5 text-[0.82rem] font-bold uppercase tracking-wide text-muted">Recommended next steps</h3>
      <ul className="m-0 grid p-0 list-none rounded-lg border border-line overflow-hidden bg-panel">
        {recommendations.map((tip, index) => {
          const Icon = NEXT_STEP_ICONS[index % NEXT_STEP_ICONS.length];
          return (
            <li
              key={index}
              className={`flex items-center gap-3 px-4 py-3.5 ${
                index < recommendations.length - 1 ? "border-b border-line" : ""
              }`}
            >
              <span className="grid h-8 w-8 flex-none place-items-center rounded-md bg-amber/15 text-amber-strong">
                <Icon size={14} />
              </span>
              <div className="text-[0.85rem] leading-relaxed text-ink">{tip}</div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

const TIER_TONE = {
  critical: { color: "var(--color-red)", label: "Very Low" },
  high: { color: "var(--color-red)", label: "Low" },
  medium: { color: "var(--color-amber)", label: "Moderate" },
  low: { color: "var(--color-green)", label: "High" },
};

function ScoreGauge({ score, tierLevel }) {
  const clamped = Math.max(0, Math.min(100, score));
  const tone = TIER_TONE[tierLevel] || TIER_TONE.medium;

  return (
    <div className="relative h-[130px] w-[130px] flex-none">
      <svg viewBox="0 0 200 200" className="h-full w-full -rotate-90 overflow-visible">
        <circle cx="100" cy="100" r="80" pathLength="100" fill="none" stroke="var(--color-line)" strokeWidth="13" />
        <circle
          cx="100"
          cy="100"
          r="80"
          pathLength="100"
          fill="none"
          stroke="var(--color-panel)"
          strokeWidth="3"
          strokeDasharray="0.6 24.4"
          strokeDashoffset="-0.3"
        />
        <circle
          cx="100"
          cy="100"
          r="80"
          pathLength="100"
          fill="none"
          stroke={tone.color}
          strokeWidth="13"
          strokeLinecap="round"
          style={{
            "--gauge-value": `${clamped} 100`,
            strokeDasharray: `${clamped} 100`,
            animation: "gauge-sweep 1.1s cubic-bezier(.16,1,.3,1) 0.2s backwards",
          }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <div className="font-display font-bold text-[2.15rem] leading-none text-ink">{score}</div>
        <div className="mt-0.5 font-mono text-[0.62rem] text-muted">OUT OF 100</div>
        <span
          className="mt-1.5 inline-flex items-center gap-1.5 font-mono text-[0.62rem] font-bold uppercase tracking-wide"
          style={{ color: tone.color }}
        >
          <span className="h-1.5 w-1.5 rounded-full" style={{ background: "currentColor" }} />
          {tone.label}
        </span>
      </div>
    </div>
  );
}

function EmptyPanel({ hint = "scan" }) {
  if (hint === "history") {
    return (
      <aside className="card grid content-center justify-items-center gap-3.5 p-12 py-14 text-center min-h-[460px]">
        <div className="grid h-15.5 w-15.5 place-items-center rounded-xl bg-amber/16 text-amber-strong">
          <Clock3 size={30} />
        </div>
        <h2 className="m-0 font-display font-semibold text-[1.5rem] uppercase tracking-tight">Pick a check to review</h2>
        <p className="m-0 max-w-[440px] text-[0.9rem] leading-relaxed text-muted">
          Select any entry from Recent checks to see its full score breakdown, evidence, and recommendation again.
        </p>
      </aside>
    );
  }

  return (
    <aside className="card grid content-center justify-items-center gap-3.5 p-12 py-14 text-center min-h-[460px]">
      <div className="grid h-15.5 w-15.5 place-items-center rounded-xl bg-amber/16 text-amber-strong">
        <Radar size={30} />
      </div>
      <h2 className="m-0 font-display font-semibold text-[1.5rem] uppercase tracking-tight">Know before you apply.</h2>
      <p className="m-0 max-w-[440px] text-[0.9rem] leading-relaxed text-muted">
        Paste a job post, recruiter message, or link. TrustRadar checks scam patterns, employer signals, domains, and
        public web results, then gives a clear recommendation.
      </p>
      <div className="flex flex-wrap justify-center gap-2.5 mt-1.5">
        <span className="flex items-center gap-1.5 rounded-full border border-line bg-field px-3.5 py-2 text-[0.78rem] font-semibold text-muted">
          <ShieldCheck size={16} /> Scam patterns
        </span>
        <span className="flex items-center gap-1.5 rounded-full border border-line bg-field px-3.5 py-2 text-[0.78rem] font-semibold text-muted">
          <Globe size={16} /> Employer proof
        </span>
        <span className="flex items-center gap-1.5 rounded-full border border-line bg-field px-3.5 py-2 text-[0.78rem] font-semibold text-muted">
          <Sparkles size={16} /> Apply guidance
        </span>
      </div>
    </aside>
  );
}

function LoadingPanel({ progress }) {
  const activeStep = [...loadingSteps].reverse().find((step) => progress >= step.at) || loadingSteps[0];

  return (
    <aside className="card grid content-center justify-items-center gap-1.5 p-12 py-14 text-center min-h-[460px]">
      <div className="relative grid place-items-center h-27 w-27 mb-2.5">
        <svg viewBox="0 0 100 100" className="h-full w-full -rotate-90">
          <circle cx="50" cy="50" r="42" fill="none" stroke="var(--color-line)" strokeWidth="8" />
          <circle
            cx="50"
            cy="50"
            r="42"
            fill="none"
            stroke="var(--color-amber)"
            strokeWidth="8"
            strokeLinecap="round"
            strokeDasharray="264"
            style={{ strokeDashoffset: 264 - (264 * progress) / 100, transition: "stroke-dashoffset 0.3s ease" }}
          />
        </svg>
        <strong className="absolute font-display text-[1.2rem] font-bold tabular-nums">{progress}%</strong>
      </div>
      <p className="m-0 mb-1 text-[0.7rem] font-extrabold uppercase tracking-widest text-amber-strong opacity-85">
        Review in progress
      </p>
      <h2 className="m-0 font-display font-semibold text-[1.35rem] uppercase tracking-tight">Checking the posting</h2>
      <p className="m-0 min-h-[1.4em] text-[0.88rem] text-muted" aria-live="polite">
        {activeStep.label}&hellip;
      </p>
    </aside>
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
  const liveEvidence = (result.live_evidence || []).map((item) => ({
    ...item,
    takeaway: item.label === "Web search" ? webSearchTakeaway(item) : undefined,
  }));
  return [...patternEvidence, ...liveEvidence];
}

function webSearchTakeaway(item) {
  const llmMatch = item.detail?.match(/LLM assessment:\s*(.+)$/);
  if (llmMatch) return llmMatch[1].trim();
  if (item.status === "skipped" || item.status === "not_found" || item.status === "failed") {
    return item.detail;
  }
  const resultCount = item.links?.length || 0;
  if (item.severity === "high") {
    return `Public search turned up ${resultCount || "several"} result(s) referencing scam, fraud, or impersonation warnings tied to this employer or domain.`;
  }
  if (item.severity === "medium") {
    return `Public search found ${resultCount || "some"} result(s) worth a closer look, including reputation or complaint-related coverage.`;
  }
  return "No scam, fraud, or complaint-related coverage showed up in public search results.";
}
