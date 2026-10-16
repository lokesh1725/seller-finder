# Founder Contact Finder - Research Features

## What it does
- Single-input research (company name) that:
  1. Checks existing DB (companies)
  2. Searches web via configured provider (Brave/Bing/none) 
  3. Extracts structured founder/company info (AI optional, deterministic fallback)
  4. Enriches via Hunter if configured
  5. Creates per-field evidence with source URL/type/date/status/confidence
  6. Stores results in research_jobs and source_evidence

## Endpoints
- POST /api/research (auth) - start research
- GET /api/research/:id (auth) - status/results
- POST /api/research/:id/refresh (auth) - refresh
- GET /api/companies (auth) - list/saved
- GET /api/companies/:id (auth)
- POST /api/companies/:id/save (auth)
- GET /api/companies/:id/sources (auth)
- GET /api/export/research/:job_id (auth)

## Config (env)
- SEARCH_PROVIDER, SEARCH_API_KEY
- AI_API_KEY, AI_API_BASE_URL, AI_API_MODEL
- HUNTER_API_KEY
- MONGODB_URI (default 27018/27017 as per env)
- AUTH_EMAIL/AUTH_PASSWORD

## UI
- /research - enter company name
- /research/:jobId - view progress, results, sources, field evidence, export CSV, refresh

## Notes
No fabricated data; if no evidence, fields remain empty/unverified. External calls are gated by credentials; without keys, deterministic fallback is used.
