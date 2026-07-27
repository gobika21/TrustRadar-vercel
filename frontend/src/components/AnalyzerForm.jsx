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
          placeholder="Add the job description, recruiter email, DM, or screenshot text."
        />
      </label>

      <label className="field">
        <span><Link2 size={15} /> Job or company link</span>
        <input value={linkUrl} onChange={(event) => setLinkUrl(event.target.value)} placeholder="Paste any relevant URL" />
      </label>

      <label className="upload-box">
        <Upload size={18} />
        <span>{files.length ? `${files.length} file attached` : "Attach screenshots or files"}</span>
        <input
          type="file"
          multiple
          accept="image/*,.pdf,.txt"
          onChange={(event) => setFiles(Array.from(event.target.files || []))}
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
