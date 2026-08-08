import React, { useEffect, useRef } from "react";
import { AlertTriangle, Info, ShieldAlert, X } from "lucide-react";

const TONE_ICONS = {
  danger: ShieldAlert,
  warning: AlertTriangle,
  info: Info,
};

export function Toast({ error, message, onDismiss }) {
  const normalizedError = normalizeError(error || message);
  const modalRef = useRef(null);
  const previouslyFocusedRef = useRef(null);
  const isOpen = Boolean(normalizedError.message);

  useEffect(() => {
    if (!isOpen) return undefined;

    previouslyFocusedRef.current = document.activeElement;
    const modal = modalRef.current;
    const focusable = modal.querySelectorAll("button, a[href], input, textarea, [tabindex]:not([tabindex='-1'])");
    (focusable[0] || modal).focus();

    function handleKeyDown(event) {
      if (event.key === "Escape") {
        onDismiss();
        return;
      }
      if (event.key !== "Tab") return;
      const items = modal.querySelectorAll("button, a[href], input, textarea, [tabindex]:not([tabindex='-1'])");
      if (!items.length) return;
      const first = items[0];
      const last = items[items.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }

    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      previouslyFocusedRef.current?.focus?.();
    };
  }, [isOpen, onDismiss]);

  if (!isOpen) return null;

  const ToneIcon = TONE_ICONS[normalizedError.tone] || AlertTriangle;
  const toneClass =
    normalizedError.tone === "danger" ? "tone-danger" : normalizedError.tone === "info" ? "tone-review" : "tone-warning";

  return (
    <div
      className="fixed inset-0 z-50 grid place-items-center p-6 bg-black/50 backdrop-blur-sm animate-[fade-in_0.15s_ease]"
      role="presentation"
    >
      <section
        className={`card relative w-[min(440px,100%)] grid justify-items-center gap-4 px-7 py-8 pb-6.5 text-center shadow-[var(--shadow-pop)] ${toneClass}`}
        style={{
          background: "color-mix(in srgb, var(--tone) 5%, var(--color-panel))",
          animation: "modal-pop-in 0.18s cubic-bezier(0.16,1,0.3,1)",
        }}
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="error-modal-title"
        ref={modalRef}
        tabIndex={-1}
      >
        <button
          className="absolute top-4 right-4 grid h-7.5 w-7.5 place-items-center rounded-full border border-line bg-field text-muted transition-colors hover:text-ink hover:border-[color:var(--tone)]/45"
          type="button"
          onClick={onDismiss}
          aria-label="Close error"
        >
          <X size={16} />
        </button>
        <div
          className="grid h-15 w-15 place-items-center rounded-full border-2 text-[color:var(--tone-strong)]"
          style={{
            background: "color-mix(in srgb, var(--tone) 14%, var(--color-panel))",
            borderColor: "color-mix(in srgb, var(--tone) 45%, var(--color-line))",
          }}
        >
          <ToneIcon size={26} />
        </div>
        <div>
          <h2 id="error-modal-title" className="m-0 mb-1.5 font-display font-semibold text-[1.15rem] uppercase tracking-tight">
            {normalizedError.title}
          </h2>
          <p className="m-0 text-[0.88rem] leading-relaxed text-muted">{normalizedError.message}</p>
        </div>
        <button
          className="rounded-lg border-none px-6.5 py-3 font-bold text-[0.88rem] text-white transition-transform hover:-translate-y-px"
          style={{ background: "var(--tone-strong)" }}
          type="button"
          onClick={onDismiss}
        >
          {normalizedError.action}
        </button>
      </section>
    </div>
  );
}

function normalizeError(error) {
  if (!error) return { title: "", message: "", action: "Close", tone: "warning" };
  if (typeof error === "string") {
    return {
      title: "Unable to review this input",
      message: error,
      action: "Try again",
      tone: "warning",
    };
  }
  return {
    title: error.title || "Unable to review this input",
    message: error.message || "",
    action: error.action || "Try again",
    tone: error.tone || "warning",
  };
}
