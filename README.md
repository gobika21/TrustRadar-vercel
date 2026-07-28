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
- Metrics are in-memory per function instance and reset on cold start.
- History is stored in Vercel Postgres; rate limiting and response caching use Vercel KV -- both required for the app to run on Vercel (see below).

## Suggested Next Improvements

- Add OCR for screenshots.
- Add filtering and search for saved history.
- Add structured source cards for each web result.
- Add sample demo scenarios.
- Add authentication if deployed publicly.

## Deploying to Vercel

This repo is a copy of the AWS-deployed TrustRadar app, ported to run on Vercel
instead of EC2/S3/CloudFront. The frontend and backend deploy together as a
single Vercel project: static assets are served from `frontend/dist`, and all
`/api/*` requests are routed to a Python serverless function at `api/index.py`
that wraps the same FastAPI app (`backend/app/main.py`) used locally.

Because serverless functions don't share memory or a local disk between
invocations, two pieces of state that used to live on the EC2 box had to move
to managed services:

- **History storage** (`backend/app/storage.py`) -- was SQLite, now Postgres.
- **Rate limiting and response caching** (`backend/app/rate_limit.py`,
  `backend/app/cache.py`) -- was in-memory, now Vercel KV (Upstash Redis).

### One-time setup

1. Import this repo as a new Vercel project (connects it to this GitHub repo
   for git-based deploys).
2. In the Vercel project's **Storage** tab, add the **Postgres** integration
   and the **KV** integration. Vercel automatically injects the connection
   env vars this code expects: `POSTGRES_URL` and `KV_REST_API_URL` /
   `KV_REST_API_TOKEN`.
3. Add `ANTHROPIC_API_KEY` as a project environment variable (Settings ->
   Environment Variables) to enable the agentic skills (JD analyzer, scam
   classifier, vision OCR, search-relevance judge). Without it, the app still
   works using the regex/heuristic fallbacks, same as when the key is unset
   in local dev.
4. Deploy. Vercel runs `frontend && npm install && npm run build` (see
   `vercel.json`) and serves `frontend/dist` as static output, with
   `api/index.py` handling everything under `/api/`.

### Notes on behavior differences from the AWS version

- Rate limiting is now a fixed-window counter in Redis (`INCR` + `EXPIRE`)
  rather than the original sliding-window list -- functionally equivalent for
  this app's limits (10 requests / 60s per IP), simpler to implement over a
  REST-based Redis client.
- The response cache pickles the cached payload (findings + `Evidence`
  objects) and stores it base64-encoded in KV, since Evidence isn't natively
  JSON-serializable. This is safe because only this app's own code ever
  writes to that cache namespace.
- Add production-safe logging and rate limiting.
