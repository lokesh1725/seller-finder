// Vercel serverless function: /api/og?slug=helmetshopee
//
// Social crawlers (WhatsApp, Facebook, LinkedIn, etc.) do not execute
// JavaScript, so the SPA cannot inject Open Graph tags for them. The Vercel
// rewrite sends crawler requests for /business/:slug here, where we fetch the
// business from the API and return a tiny HTML document carrying the correct
// og:title / og:description / og:url / og:image. Human visitors are never
// routed here; they always receive the normal SPA.

const CRAWLER_TIMEOUT_MS = 5000;

function escapeHtml(value) {
  return String(value || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

async function fetchBusiness(slug) {
  const base = (process.env.BACKEND_URL || "").replace(/\/$/, "");
  if (!base || !slug) return null;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), CRAWLER_TIMEOUT_MS);
  try {
    const response = await fetch(
      `${base}/api/businesses/${encodeURIComponent(slug)}`,
      { signal: controller.signal }
    );
    if (!response.ok) return null;
    return await response.json();
  } catch {
    return null;
  } finally {
    clearTimeout(timer);
  }
}

export default async function handler(req, res) {
  const slug = (req.query?.slug || "").toString();
  const business = await fetchBusiness(slug);

  const host = req.headers.host || "";
  const site = (process.env.PUBLIC_SITE_URL || `https://${host}`).replace(/\/$/, "");
  const profileUrl = `${site}/business/${encodeURIComponent(slug)}`;
  const image = `${site}/og-default.svg`;

  const title = business?.company_name
    ? `${business.company_name} | Seller Information Finder`
    : "Seller Information Finder";
  const location = [business?.city, business?.state].filter(Boolean).join(", ");
  const description = business?.company_name
    ? `${business.company_name}${location ? ` — ${location}` : ""}. Business profile, public contacts and sources.`
    : "Business intelligence and contact discovery for Indian fashion, D2C and manufacturing brands.";

  const html = `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<title>${escapeHtml(title)}</title>
<meta name="description" content="${escapeHtml(description)}" />
<meta property="og:type" content="website" />
<meta property="og:site_name" content="Seller Information Finder" />
<meta property="og:title" content="${escapeHtml(title)}" />
<meta property="og:description" content="${escapeHtml(description)}" />
<meta property="og:url" content="${escapeHtml(profileUrl)}" />
<meta property="og:image" content="${escapeHtml(image)}" />
<meta name="twitter:card" content="summary_large_image" />
<meta name="twitter:title" content="${escapeHtml(title)}" />
<meta name="twitter:description" content="${escapeHtml(description)}" />
<meta name="twitter:image" content="${escapeHtml(image)}" />
<meta http-equiv="refresh" content="0;url=${escapeHtml(profileUrl)}" />
<link rel="canonical" href="${escapeHtml(profileUrl)}" />
</head>
<body>
<p>Redirecting to <a href="${escapeHtml(profileUrl)}">${escapeHtml(title)}</a>...</p>
</body>
</html>`;

  res.setHeader("Content-Type", "text/html; charset=utf-8");
  res.setHeader("Cache-Control", "public, max-age=300");
  res.status(200).send(html);
}
