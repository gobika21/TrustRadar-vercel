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
    <form className="input-panel" onSubmit={onAnalyze}>
      <div className="panel-heading">
        <div>
          <h2>Review a job before you apply</h2>
        </div>
      </div>

      <label className="field large-field">
        <span>Paste the job post or recruiter message</span>
        <textarea
          value={text}
          onChange={(event) => setText(event.target.value)}
          onPaste={handlePaste}
          placeholder="Add the job description, recruiter email, DM, or screenshot text."
        />
      </label>

      <label className="field">
        <span><Link2 size={15} /> Job or company link</span>
        <input value={linkUrl} onChange={(event) => setLinkUrl(event.target.value)} placeholder="Paste any relevant URL" />
      </label>

      <label className="upload-box">
        <Upload size={18} />
        <span>
          {files.length
            ? `${files.length} file${files.length === 1 ? "" : "s"} attached`
            : "Attach screenshots or files, or paste an image (Ctrl/Cmd+V)"}
        </span>
        <input
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

      <p className="privacy-note">
        <Info size={14} />
        Avoid uploading passports, IDs, bank details, OTPs, or private offer documents.
      </p>

      <div className="form-actions">
        <button className={`analyze-button${loading ? " is-loading" : ""}`} type="submit" disabled={!hasInput || loading}>
          {loading ? (
            <>
              <Loader2 className="spin" size={18} />
              <span>Analyzing</span>
              <strong>{progress}%</strong>
            </>
          ) : (
            <>
              <Radar size={17} />
              <span>Analyze job</span>
            </>
          )}
        </button>
        {showReset ? (
          <button className="reset-button" type="button" onClick={onReset}>
            <RotateCcw size={14} /> New search
          </button>
        ) : null}
      </div>
    </form>
  );
}
