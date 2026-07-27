import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import { AnalyzerForm } from "./components/AnalyzerForm";
import { AppHeader } from "./components/AppHeader";
import { HistoryPanel } from "./components/HistoryPanel";
import { ResultPanel } from "./components/ResultPanel";
import { Toast } from "./components/Toast";
import { API_URL, HISTORY_URL } from "./config/api";
import { ThemeProvider } from "./context/ThemeProvider";
import "./styles.css";

const HISTORY_STORAGE_KEY = "trustradar:recent-checks";
const MAX_HISTORY_ITEMS = 30;

function App() {
  const [text, setText] = useState("");
  const [linkUrl, setLinkUrl] = useState("");
  const [files, setFiles] = useState([]);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [searchHistory, setSearchHistory] = useState(() => readStoredHistory());

  const hasInput = useMemo(
    () => text.trim() || linkUrl.trim() || files.length,
    [text, linkUrl, files],
  );

  useEffect(() => {
    if (!loading) {
      setProgress(0);
      return undefined;
    }

    setProgress(8);
    const intervalId = window.setInterval(() => {
      setProgress((currentProgress) => {
        if (currentProgress >= 92) return currentProgress;
        return Math.min(92, currentProgress + Math.ceil((94 - currentProgress) / 8));
      });
    }, 360);

    return () => window.clearInterval(intervalId);
  }, [loading]);

  useEffect(() => {
    loadHistory();
  }, []);

  async function loadHistory() {
    try {
      const response = await fetch(HISTORY_URL);
      if (!response.ok) throw new Error(`History returned HTTP ${response.status}`);
      const backendHistory = await response.json();
      setSearchHistory((currentHistory) => persistHistory(mergeHistory(backendHistory, currentHistory)));
    } catch {
      setSearchHistory(readStoredHistory());
    }
  }

  async function analyze(event) {
    event.preventDefault();
    setLoading(true);
    setError(null);
    setResult(null);

    const body = new FormData();
    body.append("text", text);
    body.append("job_url", linkUrl);
    body.append("recruiter_url", "");
    body.append("company_url", "");
    files.forEach((file) => body.append("files", file));

    try {
      const response = await fetch(API_URL, { method: "POST", body });
      if (!response.ok) {
        let message = `Analyzer returned HTTP ${response.status}`;
        try {
          const errorPayload = await response.json();
          if (errorPayload.detail) message = errorPayload.detail;
        } catch {
          // Keep the HTTP status fallback when the server does not return JSON.
        }
        throw new Error(message);
      }
      const analysisResult = await response.json();
      setResult(analysisResult);
      await loadHistory();
      clearInputs();
    } catch (err) {
      setError(formatAnalyzeError(err));
      clearInputs();
    } finally {
      setLoading(false);
    }
  }

  function clearInputs() {
    setText("");
    setLinkUrl("");
    setFiles([]);
  }

  async function selectHistory(entry) {
    let selectedEntry = entry;
    try {
      const response = await fetch(`${HISTORY_URL}/${entry.id}`);
      if (response.ok) selectedEntry = await response.json();
    } catch {
      // Fall back to the list item payload if the detail fetch fails.
    }
    setText(selectedEntry.input.text);
    setLinkUrl(selectedEntry.input.linkUrl || selectedEntry.input.jobUrl || selectedEntry.input.companyUrl || selectedEntry.input.recruiterUrl || "");
    setFiles([]);
    setResult(selectedEntry.result);
    setError(null);
  }

  function startNewSearch() {
    setText("");
    setLinkUrl("");
    setFiles([]);
    setResult(null);
    setError(null);
  }

  async function clearHistory() {
    try {
      await fetch(HISTORY_URL, { method: "DELETE" });
    } finally {
      window.localStorage.removeItem(HISTORY_STORAGE_KEY);
      setSearchHistory([]);
    }
  }

  return (
    <main className="shell">
      <AppHeader />
      <Toast error={error} onDismiss={() => setError(null)} />

      <section className="workspace">
        <section className="left-stack">
          <AnalyzerForm
            text={text}
            setText={setText}
            linkUrl={linkUrl}
            setLinkUrl={setLinkUrl}
            files={files}
            setFiles={setFiles}
            hasInput={hasInput}
            loading={loading}
            progress={progress}
            onAnalyze={analyze}
            showReset={Boolean(hasInput || result) && !loading}
            onReset={startNewSearch}
          />
          <HistoryPanel history={searchHistory} onSelect={selectHistory} onClear={clearHistory} />
        </section>

        <ResultPanel result={result} loading={loading} progress={progress} />
      </section>
    </main>
  );
}

createRoot(document.getElementById("root")).render(
  <ThemeProvider>
    <App />
  </ThemeProvider>,
);

function readStoredHistory() {
  try {
    const rawHistory = window.localStorage.getItem(HISTORY_STORAGE_KEY);
    const parsedHistory = rawHistory ? JSON.parse(rawHistory) : [];
    return Array.isArray(parsedHistory) ? parsedHistory : [];
  } catch {
    return [];
  }
}

function persistHistory(history) {
  const normalizedHistory = history.slice(0, MAX_HISTORY_ITEMS);
  try {
    window.localStorage.setItem(HISTORY_STORAGE_KEY, JSON.stringify(normalizedHistory));
  } catch {
    // If browser storage is unavailable, keep the in-memory history for this session.
  }
  return normalizedHistory;
}

function mergeHistory(...historyGroups) {
  const seen = new Set();
  return historyGroups
    .flat()
    .filter(Boolean)
    .sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime())
    .filter((entry) => {
      const key = historyFingerprint(entry);
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
}

function historyFingerprint(entry) {
  const input = entry.input || {};
  const result = entry.result || {};
  return [
    input.linkUrl || input.jobUrl || input.companyUrl || input.recruiterUrl || "",
    (input.text || "").slice(0, 160),
    entry.label || "",
    result.tier || "",
    result.score ?? "",
  ].join("|");
}


function formatAnalyzeError(error) {
  const message = error?.message || "Analysis failed";
  if (isNetworkError(error)) {
    return {
      title: "Connection issue",
      message: "TrustRadar cannot reach the API right now. Check your connection, then run the check again.",
      action: "Close",
      tone: "danger",
    };
  }
  if (message.includes("could not access the job posting URL") || message.includes("cannot be assessed reliably")) {
    return {
      title: "Unable to review this link",
      message,
      action: "Try another input",
      tone: "warning",
    };
  }
  if (message.includes("Too many requests")) {
    return {
      title: "Slow down a little",
      message,
      action: "Got it",
      tone: "warning",
    };
  }
  if (message.includes("doesn't include enough detail to review")) {
    return {
      title: "Not enough detail to review",
      message,
      action: "Try again",
      tone: "warning",
    };
  }
  return {
    title: "Analysis failed",
    message,
    action: "Try again",
    tone: "danger",
  };
}

function isNetworkError(error) {
  return error instanceof TypeError && /failed to fetch|load failed|networkerror/i.test(error.message || "");
}
