// Sharing helpers: Web Share API with a WhatsApp fallback, plus clipboard copy.
// No secrets are ever placed in URLs.

// Safe accessor so the pure helpers are unit-testable outside Vite.
const ENV =
  (typeof import.meta !== "undefined" && import.meta && import.meta.env) || {};

export function siteBaseUrl() {
  const configured = (ENV.VITE_PUBLIC_SITE_URL || "").replace(/\/$/, "");
  if (configured) return configured;
  if (typeof window !== "undefined") return window.location.origin;
  return "";
}

export function businessUrl(slug) {
  const base = siteBaseUrl();
  return slug ? `${base}/business/${slug}` : base;
}

export function websiteUrl() {
  return siteBaseUrl();
}

export function whatsappShareUrl(message) {
  return `https://wa.me/?text=${encodeURIComponent(message)}`;
}

export async function copyText(text) {
  if (navigator.clipboard && window.isSecureContext) {
    await navigator.clipboard.writeText(text);
    return true;
  }
  // Fallback for non-secure contexts / older browsers.
  const area = document.createElement("textarea");
  area.value = text;
  area.style.position = "fixed";
  area.style.opacity = "0";
  document.body.appendChild(area);
  area.focus();
  area.select();
  try {
    document.execCommand("copy");
    return true;
  } finally {
    document.body.removeChild(area);
  }
}

/**
 * Try the native Web Share API. Returns true if the share sheet was opened,
 * false if the caller should fall back to WhatsApp / copy.
 */
export async function nativeShare({ title, text, url }) {
  if (typeof navigator !== "undefined" && navigator.share) {
    try {
      await navigator.share({ title, text, url });
      return true;
    } catch (err) {
      if (err && err.name === "AbortError") return true; // user cancelled
      return false;
    }
  }
  return false;
}

export function buildWebsiteMessage() {
  return `Check out Seller Information Finder — search Indian fashion brands, D2C sellers & garment manufacturers: ${websiteUrl()}`;
}

export function buildBusinessMessage(business) {
  const name = business?.company_name || "this business";
  const where = [business?.city, business?.state].filter(Boolean).join(", ");
  const lines = [`${name}${where ? ` (${where})` : ""}`];
  if (business?.official_website) lines.push(business.official_website);
  lines.push(`Business profile: ${businessUrl(business?.slug)}`);
  return lines.join("\n");
}
