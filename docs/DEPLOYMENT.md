# Deployment Guide

This guide deploys **Seller Information Finder** to production:

- **MongoDB Atlas** - cloud database
- **Render** - Flask backend (public HTTPS API)
- **Vercel** - React/Vite frontend (public HTTPS site + WhatsApp previews)
- **GitHub** - source of truth for both platforms

The end result is a public HTTPS URL you can share through WhatsApp.

> **Important:** Vercel subdomains are globally unique. The name
> `seller-finder.vercel.app` is already taken by an **unrelated third-party
> app** (a Korean Instagram tool). Your project must use its own unique
> production domain, for example:
>
> - `https://seller-finder-lokesh.vercel.app`, or
> - a deployment URL like `https://seller-finder-<hash>-<team>.vercel.app`
>
> Never assume a URL belongs to this project until you have opened it and
> seen this app's UI (login page with "Seller Finder" branding).

---

## 0. Push the code to GitHub

```bash
cd seller-finder
git init
git add .
git commit -m "Seller Information Finder: full stack"

# create an empty repo on GitHub first, then:
git remote add origin https://github.com/<you>/seller-finder.git
git branch -M main
git push -u origin main
```

`.env` files and `node_modules/` are already git-ignored. Never commit secrets.

---

## 1. MongoDB Atlas

1. Create a free account at <https://www.mongodb.com/cloud/atlas>.
2. Create a **free (M0) cluster**.
3. **Database Access** -> add a database user (e.g. `seller_finder_app`) with a
   strong password and *Read and write to any database* (or scope to
   `seller_finder`).
4. **Network Access** -> add an IP access list entry. For Render's dynamic IPs,
   add `0.0.0.0/0` (allow from anywhere) and rely on strong credentials +
   TLS - or use Render's static outbound IPs on a paid plan and allow only those.
5. **Connect -> Drivers** -> copy the `mongodb+srv://...` connection string. Use it
   as `MONGODB_URI` (append `/seller_finder?retryWrites=true&w=majority` or set
   `MONGODB_DATABASE=seller_finder`).

The database is never exposed directly to browsers; only the backend connects.

---

## 2. Backend on Render

### Option A - Blueprint (recommended)

`backend/render.yaml` defines the service. In Render: **New -> Blueprint**,
connect the repo, point to `backend/render.yaml`.

### Option B - Manual web service

- **New -> Web Service**, connect the GitHub repo.
- **Root Directory:** `backend`
- **Runtime:** Python 3
- **Build Command:** `pip install -r requirements.txt`
- **Start Command:**
  `gunicorn wsgi:app --bind 0.0.0.0:$PORT --workers 2 --timeout 60`
- **Health Check Path:** `/api/health`

### Environment variables

| Key                   | Value / notes                                             |
| --------------------- | --------------------------------------------------------- |
| `FLASK_ENV`           | `production`                                              |
| `MONGODB_URI`         | your Atlas connection string (secret)                     |
| `MONGODB_DATABASE`    | `seller_finder`                                           |
| `FRONTEND_URL`        | `https://<your-app>.vercel.app` (CORS allow-list)         |
| `PUBLIC_FRONTEND_URL` | `https://<your-app>.vercel.app`                           |
| `SEARCH_PROVIDER`     | `brave` or `bing` (or `none`)                             |
| `SEARCH_API_KEY`      | your search API key (secret, optional)                    |
| `AI_API_KEY`          | AI model API key (secret, optional - research extraction) |
| `AI_API_BASE_URL`     | AI API base URL (secret, optional)                        |
| `AI_API_MODEL`        | e.g. `gpt-4o-mini` (optional)                             |
| `HUNTER_API_KEY`      | Hunter.io key (secret, optional - email enrichment)       |
| `ADMIN_API_TOKEN`     | a long random string (protects `/api/admin/*`)            |
| `SECRET_KEY`          | a long random string                                      |
| `AUTH_EMAIL`          | login email (default `admin@gmail.com`)                   |
| `AUTH_PASSWORD`       | login password (default `Test@123` - change in production)|
| `RATE_LIMIT_PER_MINUTE` | `60`                                                    |

> The app is gated: visitors must log in (`/login`) before browsing, except
> public share links (`/business/<slug>`). Set `AUTH_EMAIL` / `AUTH_PASSWORD`
> to your own credentials before going live.

Deploy, then confirm `https://<api>.onrender.com/api/health` returns `ok`.

### Seed the production database

From your machine (with the Atlas URI), run the importer pointed at Atlas:

```bash
cd backend
MONGODB_URI="mongodb+srv://..." MONGODB_DATABASE=seller_finder \
  python scripts/import_excel.py
```

Or, since `data/India_Product_Photography_Leads.xlsx` is in the repo, call the
protected endpoint:

```bash
curl -X POST https://<api>.onrender.com/api/admin/import \
  -H "X-Admin-Token: $ADMIN_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{}'
```

---

## 3. Frontend on Vercel

1. **New Project** -> import the GitHub repo.
2. **Root Directory:** `frontend`
3. Framework preset: **Vite** (Build: `npm run build`, Output: `dist`).
4. Environment variables:

   | Key                       | Value                                  |
   | ------------------------- | -------------------------------------- |
   | `VITE_API_BASE_URL`       | `https://<api>.onrender.com`           |
   | `VITE_PUBLIC_SITE_URL`    | `https://<your-app>.vercel.app`        |
   | `BACKEND_URL`             | `https://<api>.onrender.com` (for /api/og) |
   | `PUBLIC_SITE_URL`         | `https://<your-app>.vercel.app`        |

5. Deploy.

`vercel.json` handles:

- **SPA fallback** so `/business/<slug>` opens on refresh/deep link.
- **Crawler rewrite**: requests from WhatsApp/Facebook/LinkedIn/etc. for
  `/business/<slug>` are served by `/api/og`, which returns Open Graph tags
  (company name, description, URL, image) so shared links show a rich preview.

Finally, update **Render's `FRONTEND_URL`** to the Vercel domain and redeploy so
CORS allows the site.

---

## 4. Custom domain (optional)

Add your domain in Vercel (frontend) and Render (API), then update
`VITE_PUBLIC_SITE_URL`, `PUBLIC_SITE_URL`, `PUBLIC_FRONTEND_URL` and
`FRONTEND_URL` accordingly.

---

## Verification checklist

- [ ] `https://<api>.onrender.com/api/health` -> `{"status":"ok"}`
- [ ] `https://<app>.vercel.app` loads over HTTPS
- [ ] Visiting the site prompts **login**; `admin@gmail.com` / `Test@123` works
- [ ] Logout returns to `/login`; protected pages redirect when logged out
- [ ] Search returns seeded companies; unknown names show an empty state
- [ ] `/business/<slug>` deep link works on refresh (and is public)
- [ ] `/research` starts a research job and `/research/<id>` shows progress/results
- [ ] Research results show per-field sources + verification labels (no invented data)
- [ ] Research CSV export works
- [ ] Share Website / Copy Link / Share Business work
- [ ] WhatsApp preview shows the company name (test on a mobile device)
- [ ] Saved leads + CSV export work
- [ ] No CORS / mixed-content errors in the browser console

Only report the site as live once every box above is ticked against the real
deployment.
