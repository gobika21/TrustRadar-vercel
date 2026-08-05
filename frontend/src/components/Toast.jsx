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

  return (
    <div className="error-modal-backdrop" role="presentation">
      <section
        className={`error-modal ${normalizedError.tone}`}
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="error-modal-title"
        ref={modalRef}
        tabIndex={-1}
      >
        <button className="error-modal-close" type="button" onClick={onDismiss} aria-label="Close error">
          <X size={16} />
        </button>
        <div className="error-modal-icon">
          <ToneIcon size={26} />
        </div>
        <div>
          <h2 id="error-modal-title">{normalizedError.title}</h2>
          <p>{normalizedError.message}</p>
        </div>
        <button className="error-modal-action" type="button" onClick={onDismiss}>
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
