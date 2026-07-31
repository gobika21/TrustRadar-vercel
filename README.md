# TrustRadar

TrustRadar is an agentic AI job-scam detection app for reviewing job posts, recruiter messages, company links, and screenshots before applying.

The app does not return a flat "scam/not scam" answer. It runs a small verification workflow, checks the submitted evidence, and shows the reasoning behind the recommendation -- including a plain-language "what drove this result" summary and concrete next steps, not just a raw score.

## What It Does

- Reviews pasted job descriptions, recruiter emails, DMs, or screenshot text.
- Accepts a related link (job posting URL, recruiter profile, or company site) -- including extracting and analyzing the actual job-description text behind a submitted URL when the page renders it server-side (LinkedIn's public job pages, for example), not just checking that the link is reachable.
- Accepts screenshots or supporting files as evidence.
- Shows a privacy reminder before upload so users avoid sharing IDs, bank details, OTPs, or private documents.
- Detects scam-language patterns such as upfront fees, urgency, generic recruiter signatures, unsubstantiated interview/shortlist claims, and early requests for sensitive information.
- Performs live checks for URL reachability, DNS resolution, domain registration/RDAP data, and public web-search signals -- scoped so known social-platform/ATS domains are never mistaken for the actual employer being checked.
- Separates inaccessible/private job links from actual risk scoring.
- Shows a final recommendation, risk score, key signals, evidence reviewed, agent workflow, and a "what to do next" checklist.
- Persists analysis history (Postgres in production) with a client-side fallback cache, so past checks can be revisited and highlighted.

## Agentic Workflow

For every review, TrustRadar runs these steps:

1. Evidence intake
2. Scam-pattern review (regex/keyword)
3. Structured fact extraction (AI)
4. Link and domain verification (reachability, DNS, RDAP)
5. Public web-signal review
6. Apply recommendation

When `ANTHROPIC_API_KEY` is set, five agent skills (all on **Claude Haiku 4.5**) run as part of this workflow -- each with its own scoped prompt -- and the app falls back to pure regex/keyword heuristics for any skill that's unavailable or fails:

| Agent | File | Job |
|---|---|---|
| **Extractor** | `agents/skills/extractor.py` | Pulls structured facts out of the raw text: company, role, salary, requirements, contact info, application reference, interview date, greeting tone, urgency language, whether a real hiring process is mentioned. |
| **Classifier** | `agents/skills/classifier.py` | Reads the text plus the Extractor's facts and identifies scam-risk signals a regex system would miss -- paraphrased fee requests, subtle pressure tactics, implausible offers, claims unsubstantiated by the extracted facts. |
| **JD Analyzer** | `agents/skills/jd_analyzer.py` | The validation gate. Judges whether a submission has enough real job-description substance (an actual role/title or concrete requirements) to be worth scoring at all. |
| **Search Synthesis** | `agents/skills/search_synthesis.py` | Judges whether public web-search results actually pertain to the specific employer/domain being checked, versus generic platform-level scam-awareness content or unrelated pages. |
| **Vision OCR** | `agents/skills/vision_ocr.py` | Extracts text from uploaded screenshot images so they can be analyzed the same way as pasted text. |

The result includes:

- Recommendation: `Likely safe to apply`, `Apply with caution`, `Do not engage yet`, or `Don't apply to this`
- Risk score (0-100) and tier
- Key signals that drove the result, in plain language
- Evidence reviewed, with source links where available
- A "what to do next" action checklist
- Live-call usage counts

## Tech Stack

**Frontend**
- React 18 + Vite 5 (plain JS)
- Plain CSS with custom properties for light/dark theming -- no CSS framework
- `lucide-react` for icons
- `@vercel/analytics` for usage tracking

**Backend**
- FastAPI (Python 3.12) on Uvicorn, deployed as a Vercel Python serverless function (`api/index.py` wraps `backend/app/main.py`)
- `httpx` for outbound live-verification calls (reachability, RDAP)
- `BeautifulSoup4` for parsing search results and extracting job-description text from fetched pages
- `python-multipart` for file uploads

**AI**
- Anthropic SDK, `claude-haiku-4-5` -- see the five agent skills above
- Gracefully no-ops to regex/heuristic fallbacks when `ANTHROPIC_API_KEY` is unset

**Data & infra**
- Vercel Postgres (via the Prisma provider) for analysis history, accessed through `pg8000` (a pure-Python driver, chosen because `psycopg2` fails to build on Vercel's build system)
- Upstash Redis (`upstash-redis`, via Vercel KV) for rate limiting and response caching

**Core logic**
- A regex/keyword pattern-matching scoring engine (`scoring.py`) combined with live-evidence scoring (domain age, reachability, web-search severity) to produce a 0-100 risk score and tier

## Project Structure

```text
TrustRadar-vercel/
  api/
    index.py           Vercel entrypoint, wraps the FastAPI app
  backend/
    app/
      agents/
        client.py       Anthropic client + model config
        dispatcher.py    Routes calls to each agent skill
        orchestrator.py  Runs extraction -> classification, and the JD gate
        safety.py        PII redaction, untrusted-content wrapping
        skills/
          extractor.py
          classifier.py
          jd_analyzer.py
          search_synthesis.py
          vision_ocr.py
      main.py           FastAPI app and routes
      analysis.py       Recommendation, workflow, evidence links, URL access guard
      cache.py          Response caching (Redis)
      kv.py             Shared Redis client
      metrics.py        In-memory metrics and per-analysis usage counts
      models.py         Shared backend models
      rate_limit.py     Per-IP rate limiting (Redis)
      scoring.py        Scam-pattern detection and risk scoring
      storage.py        Postgres persistence for saved analyses
      text_utils.py     URL, email, domain, and ATS/social-platform helpers
      uploads.py        File-upload decoding (text + OCR handoff)
      verification.py   URL fetch, description extraction, DNS, RDAP, web search
    tests/              116 tests across 7 files (pytest)
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

Without `POSTGRES_URL` / `KV_REST_API_URL` set, history persistence and rate limiting/caching no-op gracefully so the app still runs locally.

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

The frontend API base URL is configured via `VITE_API_BASE_URL` (see `frontend/src/config/api.js`), defaulting to `http://127.0.0.1:8001/api` for local dev.

## API

### `GET /api/health`

Returns backend status.

### `GET /api/metrics`

Returns in-memory usage counters. These reset when the backend restarts.

### `GET /api/history`

Returns saved analysis history from Postgres.

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

- `id`
- `tier`, `tier_level`, `score`
- `summary`
- `recommendation`
- `agent_workflow`
- `usage`
- `pattern_findings`
- `live_evidence`
- `uploaded_files`
- `extracted` (regex-derived URLs/emails)
- `extracted_fields` (AI-extracted structured facts, when agents are enabled)
- `recommendations`

## Testing

Run backend tests:

```bash
cd backend
python -m pytest tests/
```

116 tests across `test_scoring.py`, `test_analysis.py`, `test_agents.py`, `test_cache.py`, `test_main.py`, `test_rate_limit.py`, and `test_description_extraction.py`.

## Current Limitations

- Public web search uses DuckDuckGo HTML parsing; result relevance can vary between calls for the same query.
- RDAP/domain data can be incomplete for some TLDs.
- Some job boards block automated access. In that case, TrustRadar shows an access error instead of scoring the URL as low or high risk.
- Metrics are in-memory per function instance and reset on cold start.
- Scam-signal heuristics were originally tuned for cold recruiter messages (email/DM), and can be miscalibrated for professionally-hosted platform postings where contact/application is handled by the platform itself rather than listed in the text.

## Suggested Next Improvements

- Tune the classifier so platform-hosted postings aren't penalized for lacking direct contact details.
- Add filtering and search for saved history.
- Add structured source cards for each web result.
- Add sample demo scenarios.
- Add authentication if deployed publicly.

## Deploying to Vercel

The frontend and backend deploy as **two separate Vercel projects** from this one repo:

- **Backend** -- Root Directory: repo root. `vercel.json` routes all `/api/*` requests to the Python serverless function at `api/index.py`, which wraps the FastAPI app (`backend/app/main.py`).
- **Frontend** -- Root Directory: `frontend/`. A standard Vite static build, configured with `VITE_API_BASE_URL` pointing at the backend project's deployed URL.

Because serverless functions don't share memory or a local disk between invocations, two pieces of state need managed services:

- **History storage** (`backend/app/storage.py`) -- Postgres.
- **Rate limiting and response caching** (`backend/app/rate_limit.py`, `backend/app/cache.py`) -- Vercel KV (Upstash Redis).

### One-time setup

1. Import this repo as two Vercel projects (backend rooted at `/`, frontend rooted at `/frontend`), each connected to this GitHub repo for git-based deploys.
2. On the **backend** project's **Storage** tab, add the **Postgres** integration and the **KV** integration. Vercel automatically injects the connection env vars this code expects: `POSTGRES_URL` and `KV_REST_API_URL` / `KV_REST_API_TOKEN`.
3. Add `ANTHROPIC_API_KEY` as a backend project environment variable (Settings -> Environment Variables) to enable the five agent skills. Without it, the app still works using the regex/heuristic fallbacks, same as when the key is unset in local dev.
4. Set `VITE_API_BASE_URL` on the **frontend** project to the backend project's deployed URL (e.g. `https://your-backend.vercel.app/api`).
5. Deploy both. The backend serves `api/index.py` under `/api/*`; the frontend builds and serves `frontend/dist` as a static site.

### Notes on behavior differences from the original AWS version

- Rate limiting is a fixed-window counter in Redis (`INCR` + `EXPIRE`) -- functionally equivalent for this app's limits (10 requests / 60s per IP), simpler to implement over a REST-based Redis client than the original sliding-window list.
- The response cache pickles the cached payload (findings + `Evidence` objects) and stores it base64-encoded in KV, since `Evidence` isn't natively JSON-serializable. This is safe because only this app's own code ever writes to that cache namespace.
- Any unhandled exception in a route is caught and re-raised as a proper `HTTPException` with a logged traceback, rather than an unhandled 500 -- Starlette's default error handler sits outside `CORSMiddleware`, so an uncaught exception's response has no CORS headers and shows up client-side as an opaque "Failed to fetch" with no diagnostic information.
