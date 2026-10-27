# Seller Information Finder

A business-intelligence and contact-discovery web app for Indian fashion D2C
brands, e-commerce sellers, garment/textile manufacturers, wholesalers and
suppliers.

Enter a company name -> the app searches its MongoDB database -> falls back to a
permitted public web-search provider for missing companies -> shows a full
business profile with **sourced, field-level verification**.

- **Frontend:** React + Vite (deploy to Vercel)
- **Backend:** Flask REST API (deploy to Render)
- **Database:** MongoDB (local Community Server / MongoDB Compass / MongoDB Atlas)

> **Data honesty:** the app never invents emails, phone numbers or other contact
> details. Every important field carries a source and a verification status
> (`verified` / `unverified` / `unavailable`). Missing values are shown as
> **Not found**.

---

## Table of contents

1. [Project layout](#project-layout)
2. [Local setup](#local-setup)
3. [Importing the Excel dataset](#importing-the-excel-dataset)
4. [API reference](#api-reference)
5. [Tests](#tests)
6. [Deployment](#deployment)
7. [Production verification checklist](#production-verification-checklist)
8. [Security & privacy](#security--privacy)

---

## Project layout

```
seller-finder/
|-- backend/                 Flask REST API
|   |-- app/
|   |   |-- __init__.py      App factory, CORS, ISO JSON, security headers
|   |   |-- config.py        Env-driven configuration
|   |   |-- db.py            Lazy MongoDB connection + collection accessors
|   |   |-- schema.py        Idempotent index creation
|   |   |-- utils.py         Normalisation, parsing, SSRF-safe URL checks
|   |   |-- errors.py        Structured JSON errors
|   |   |-- limiter.py       In-process rate limiter
|   |   |-- routes/          health, search, businesses, leads, export, admin
|   |   `-- services/        importer, aggregator, search_provider, verification, cache
|   |-- scripts/import_excel.py   CLI importer
|   |-- tests/               pytest suite (mocked API calls)
|   |-- requirements.txt
|   |-- render.yaml          Render blueprint
|   |-- wsgi.py / run.py
|   `-- .env.example
|-- frontend/                React + Vite SPA
|   |-- src/
|   |   |-- api.js           Typed fetch client
|   |   |-- pages/           Home, Results, Business, SavedLeads, NotFound
|   |   |-- components/      Header, SearchBar, CompanyCard, FieldRow, ShareButtons...
|   |   |-- hooks/           useSeo, useRecentSearches
|   |   `-- utils/           share.js (WhatsApp/Web Share), format.js
|   |-- api/og.js            Vercel function: OG previews for crawlers (WhatsApp)
|   |-- tests/               Node test runner (share utilities)
|   |-- vercel.json          SPA + crawler rewrites
|   `-- .env.example
|-- data/
|   `-- India_Product_Photography_Leads.xlsx
|-- docs/DEPLOYMENT.md
`-- README.md
```

---

## Local setup

### Prerequisites

- Python 3.11+
- Node.js 18+
- MongoDB Community Server (running locally) and optionally MongoDB Compass

### 1. Backend

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate   # optional but recommended
pip install -r requirements.txt

cp .env.example .env        # then edit if needed
python run.py               # http://localhost:5000
```

Check it is alive:

```bash
curl http://localhost:5000/api/health
# {"database":{"connected":true,"detail":"ok"},"service":"seller-finder-api","status":"ok"}
```

### 2. Frontend

```bash
cd frontend
npm install
cp .env.example .env        # leave VITE_API_BASE_URL empty for the dev proxy
npm run dev                 # http://localhost:5173
```

The Vite dev server proxies `/api/*` to `http://localhost:5000`, so no CORS
setup is needed locally.

### 3. Logging in

The app is gated behind a login. Default credentials (override with the
`AUTH_EMAIL` / `AUTH_PASSWORD` backend env vars):

| Field    | Value           |
| -------- | --------------- |
| Email    | admin@gmail.com |
| Password | Test@123        |

Login issues a signed, time-limited token stored by the SPA; protected routes
(Search, Saved Leads) redirect to `/login` when no valid session exists. Public
business profiles (`/business/<slug>`) stay reachable without login so links
shared over WhatsApp open directly for recipients.

### MongoDB Compass

1. Open MongoDB Compass and connect to `mongodb://localhost:27017`.
2. Database: `seller_finder` -> collections: `businesses`, `leads`, `prospects`,
   `import_runs`, `search_cache`.

Compass is an administration tool only; the app always talks to the real
MongoDB server/Atlas cluster.

---

## Importing the Excel dataset

The workbook lives at `data/India_Product_Photography_Leads.xlsx` and contains
three sheets:

| Sheet              | Handling                                             |
| ------------------ | ---------------------------------------------------- |
| `Leads`            | Imported as business documents                       |
| `Top 10 Prospects` | Stored as ranking metadata in the `prospects` collection |
| `Notes`            | Reference text stored with the import run (not companies) |

Run the idempotent importer:

```bash
cd backend
python scripts/import_excel.py            # import
python scripts/import_excel.py --dry-run  # validate without writing
python scripts/import_excel.py --path /path/to/other.xlsx
```

**Guarantees**

- Re-running never creates duplicate companies (matched by normalised name).
- Empty spreadsheet cells never overwrite valid stored values.
- Company names are normalised; punctuation/parenthetical aliases are extracted
  (e.g. `Bunaai (now trading as Bunai)` -> aliases `["Bunai"]`).
- Imported values are marked **unverified** with the source URL preserved.

The same import is available over a protected endpoint:

```bash
curl -X POST http://localhost:5000/api/admin/import \
  -H "X-Admin-Token: $ADMIN_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"dry_run": false}'
```

---

## API reference

| Method | Path                              | Purpose |
| ------ | --------------------------------- | ------- |
| GET    | `/api/health`                     | Liveness + DB connectivity |
| GET    | `/api/search?q=...&category=&city=&limit=&offset=` | DB-first search |
| POST   | `/api/search`                     | Search with `{query, category, city, allow_web}` |
| GET    | `/api/businesses/:idOrSlug`       | Full business profile |
| POST   | `/api/businesses/:idOrSlug/refresh` | Re-check permitted public sources |
| GET    | `/api/leads`                      | List saved leads |
| POST   | `/api/leads`                      | Save a business as a lead |
| PATCH  | `/api/leads/:leadId`              | Update notes / tags / outreach status |
| DELETE | `/api/leads/:leadId`              | Remove a lead |
| GET    | `/api/export?ids=a,b`             | CSV export |
| POST   | `/api/admin/import`               | Protected Excel import |
| GET    | `/api/admin/cache/clear`          | Protected cache flush |

Errors are always structured:

```json
{ "error": { "code": "not_found", "message": "Business not found" } }
```

### External search provider

Configure `SEARCH_PROVIDER=brave` (or `bing`) and `SEARCH_API_KEY` to enable
live web search. With no key, the provider reports
`search_provider_not_configured` and the app simply shows stored records - it
**never fabricates** results. Results are cached in MongoDB (TTL) to limit API
usage.

---

## Tests

```bash
# Backend (mocked external APIs; uses a separate seller_finder_test database)
cd backend && python3 -m pytest -q

# Frontend share utilities (Node built-in test runner)
cd frontend && npm test
```

Covered: Excel import + idempotency, duplicate detection, exact/partial/alias
search, missing-contact handling, provider failures, profile retrieval, DB
failure (503), leads CRUD, CSV export, direct profile access, admin auth, SSRF
and URL validation, and WhatsApp URL generation.

---

## Deployment

Full step-by-step instructions live in [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md).
Summary:

1. **MongoDB Atlas** - create a free cluster, database user and network access.
2. **Render** - deploy `backend/`; set `MONGODB_URI`, `MONGODB_DATABASE`,
   `FRONTEND_URL`, `PUBLIC_FRONTEND_URL`, `SEARCH_PROVIDER`, `SEARCH_API_KEY`,
   `ADMIN_API_TOKEN`, `SECRET_KEY`, `AUTH_EMAIL`, `AUTH_PASSWORD`. Health check:
   `/api/health`.
3. **Import data** - run `python scripts/import_excel.py` locally against the
   Atlas URI, or `POST /api/admin/import` with the admin token.
4. **Vercel** - deploy `frontend/`; set `VITE_API_BASE_URL` to the Render URL and
   `VITE_PUBLIC_SITE_URL` to the Vercel URL. Set the same `BACKEND_URL` and
   `PUBLIC_SITE_URL` env vars for the `/api/og` preview function.
5. Set `FRONTEND_URL` on Render to the Vercel domain so CORS is restricted.

---

## Production verification checklist

After deployment, verify from a mobile browser:

- [ ] `https://<your-unique-app>.vercel.app` loads over HTTPS and shows **this**
      app's login page (note: `seller-finder.vercel.app` is owned by someone else).
- [ ] `https://<api>.onrender.com/api/health` returns `status: ok`.
- [ ] Searching a known company (e.g. `Bummer`) returns a result from the DB.
- [ ] Searching an unknown company shows a clear empty state (no invented data).
- [ ] `/business/<slug>` opens directly (refresh / deep link) without going home.
- [ ] **Share Website** and **Copy Link** work; the copied link opens the site.
- [ ] Sharing a business via WhatsApp shows the company name in the preview.
- [ ] Saving a lead, adding notes/tags, and exporting CSV all work.
- [ ] Browser console shows no CORS or mixed-content errors.

> A live URL is marked as verified only after these checks pass against a real
> deployment.

---

## Security & privacy

- Inputs validated; identifiers matched against a strict pattern.
- Non-http(s) and private/loopback URLs rejected (SSRF protection in `utils.py`).
- CORS restricted to configured production origins.
- Admin endpoints token-protected.
- Rate limiting on the API.
- Secrets only via environment variables; `.env` files git-ignored.
- Only public professional contact information is stored; source URLs are kept
  for traceability. Respect website terms, API limits and applicable privacy
  laws when reaching out.
