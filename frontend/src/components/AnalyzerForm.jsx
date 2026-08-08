import React from "react";
import {
  Info,
  Link2,
  Loader2,
  Radar,
  RotateCcw,
  Upload,
} from "lucide-react";

export function AnalyzerForm({
  text,
  setText,
  linkUrl,
  setLinkUrl,
  files,
  setFiles,
  hasInput,
  loading,
  progress,
  onAnalyze,
  showReset,
  onReset,
}) {
  function handlePaste(event) {
    const items = Array.from(event.clipboardData?.items || []);
    const pastedImages = items
      .filter((item) => item.kind === "file" && item.type.startsWith("image/"))
      .map((item) => item.getAsFile())
      .filter(Boolean);

    if (!pastedImages.length) return;

    const namedImages = pastedImages.map((file, index) =>
      file.name && file.name !== "image.png"
        ? file
        : new File([file], `pasted-screenshot-${Date.now()}-${index}.png`, { type: file.type }),
    );

    setFiles((currentFiles) => [...currentFiles, ...namedImages]);
  }

  return (
    <form className="card grid gap-4 p-5.5" onSubmit={onAnalyze}>
      <div className="flex items-center justify-between gap-3">
        <h2 className="m-0 font-display font-semibold text-[1.2rem] uppercase tracking-tight">
          Review a job before you apply
        </h2>
      </div>

      <label className="grid gap-2">
        <span className="flex items-center gap-1.5 text-[0.78rem] font-bold text-muted">
          Paste the job post or recruiter message
        </span>
        <textarea
          className="field-input min-h-[132px] resize-y leading-relaxed"
          value={text}
          onChange={(event) => setText(event.target.value)}
          onPaste={handlePaste}
          placeholder="Add the job description, recruiter email, DM, or screenshot text."
        />
      </label>

      <label className="grid gap-2">
        <span className="flex items-center gap-1.5 text-[0.78rem] font-bold text-muted">
          <Link2 size={15} /> Job or company link
        </span>
        <input
          className="field-input"
          value={linkUrl}
          onChange={(event) => setLinkUrl(event.target.value)}
          placeholder="Paste any relevant URL"
        />
      </label>

      <label className="relative flex items-center justify-center gap-2 rounded-lg border border-dashed border-amber/45 bg-amber/6 px-4 py-3 text-[0.82rem] font-bold text-amber-strong transition-colors hover:bg-amber/12">
        <Upload size={18} />
        <span>
          {files.length
            ? `${files.length} file${files.length === 1 ? "" : "s"} attached`
            : "Attach screenshots or files, or paste an image (Ctrl/Cmd+V)"}
        </span>
        <input
          className="absolute h-px w-px opacity-0 pointer-events-none"
          type="file"
          multiple
          accept="image/*,.pdf,.txt"
          onChange={(event) => {
            const newFiles = Array.from(event.target.files || []);
            if (newFiles.length) setFiles((currentFiles) => [...currentFiles, ...newFiles]);
            event.target.value = "";
          }}
        />
      </label>

      <p className="m-0 flex items-start gap-2 rounded-md border border-amber/30 bg-amber/10 px-3 py-2.5 text-[0.76rem] leading-snug text-amber-strong">
        <Info size={14} className="mt-px flex-none" />
        Avoid uploading passports, IDs, bank details, OTPs, or private offer documents.
      </p>

      <div className="flex items-stretch gap-2.5">
        <button className="btn-primary flex-1" type="submit" disabled={!hasInput || loading}>
          {loading ? (
            <>
              <Loader2 className="animate-spin" size={18} />
              <span>Analyzing</span>
              <strong className="font-extrabold opacity-90">{progress}%</strong>
            </>
          ) : (
            <>
              <Radar size={17} />
              <span>Analyze job</span>
            </>
          )}
        </button>
        {showReset ? (
          <button className="btn-ghost flex-none whitespace-nowrap" type="button" onClick={onReset}>
            <RotateCcw size={14} /> New search
          </button>
        ) : null}
      </div>
    </form>
  );
}
