# TrustRadar

TrustRadar is an agentic AI job-scam detection app for reviewing job posts, recruiter messages, company links, and screenshots before applying.

The app does not return a flat "scam/not scam" answer. It runs a small verification workflow, checks the submitted evidence, and shows the reasoning behind the recommendation.

## What It Does

- Reviews pasted job descriptions, recruiter emails, DMs, or screenshot text.
- Accepts one related link, such as a job posting URL, recruiter profile, or company website.
- Accepts screenshots or supporting files as evidence.
- Shows a privacy reminder before upload so users avoid sharing IDs, bank details, OTPs, or private documents.
- Detects scam-language patterns such as upfront fees, urgency, generic recruiter signatures, and early requests for sensitive information.
- Performs live checks for URL reachability, DNS resolution, domain registration/RDAP data, and public web-search signals.
- Separates inaccessible/private job links from actual risk scoring.
- Shows a final recommendation, red flags, trust signals, evidence reviewed, agent workflow, and live-check usage counts.
- Stores analysis history in a local SQLite database for later review.

## Agentic Workflow

For every review, TrustRadar runs these steps:

1. Evidence intake
2. Scam-pattern review
3. Link and domain verification
4. Public web-signal review
5. Apply recommendation

The result includes:

- Recommendation: `Likely safe to apply`, `Apply with caution`, or `Do not engage yet`
- Risk score and tier
- Signals to investigate
- Trust signals
- Evidence with source links when available
- Live-call usage counts

## Tech Stack

- Frontend: React + Vite
- Backend: FastAPI
- Database: SQLite
- Live verification: HTTP checks, DNS lookup, RDAP/domain checks, DuckDuckGo HTML search parsing
- Styling: Custom CSS with light/dark theme support

## Project Structure

```text
TrustRadar/
  backend/
    app/
      main.py          FastAPI app and routes
      analysis.py      Recommendation, workflow, evidence links, URL access guard
      metrics.py       In-memory metrics and per-analysis usage counts
      models.py        Shared backend models
      scoring.py       Scam-pattern detection and risk scoring
      storage.py       SQLite persistence for saved analyses
      text_utils.py    URL, email, domain, and ATS helpers
      verification.py  URL fetch, DNS, RDAP, and web search checks
    tests/
      test_scoring.py
  frontend/
    src/
      components/
      context/
      config/
      utils/
      styles.css
```

## Run Locally

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload
```

Backend health check:

```bash
curl http://127.0.0.1:8001/api/health
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open:

```text
http://127.0.0.1:5173/
```

The frontend API URL is configured in:

```text
frontend/src/config/api.js
```

## API

### `GET /api/health`

Returns backend status.

### `GET /api/metrics`

Returns in-memory usage counters. These reset when the backend restarts.

### `GET /api/history`

Returns saved analysis history from SQLite.

### `GET /api/history/{entry_id}`

Returns one saved analysis with the original input and full result.

### `DELETE /api/history`

Clears saved analysis history.

### `POST /api/analyze`

Multipart form fields:

- `text`: job post, recruiter message, email, DM, or screenshot text
- `job_url`: one related URL
- `recruiter_url`: supported by backend for compatibility
- `company_url`: supported by backend for compatibility
- `files`: optional screenshots or supporting files

The response includes:

- `tier`
- `tier_level`
- `score`
- `summary`
- `recommendation`
- `agent_workflow`
- `usage`
- `pattern_findings`
- `live_evidence`
- `uploaded_files`
- `extracted`
- `recommendations`

## Testing

Run backend tests:

```bash
cd backend
python -m unittest tests/test_scoring.py
```

## Current Limitations

- Uploaded screenshots/files are accepted, but OCR is not bundled yet. Paste screenshot text into the message box for best results.
- Public web search uses DuckDuckGo HTML parsing and may vary by network availability.
- RDAP/domain data can be incomplete for some TLDs.
- Some job boards block automated access. In that case, TrustRadar shows an access error instead of scoring the URL as low or high risk.
- Metrics are in-memory only and reset when the backend restarts.
- History is stored locally in `backend/data/trustradar.sqlite3`, which is ignored by Git.

## Suggested Next Improvements

- Add OCR for screenshots.
- Add filtering and search for saved history.
- Add structured source cards for each web result.
- Add sample demo scenarios.
- Add authentication if deployed publicly.
- Add production-safe logging and rate limiting.
