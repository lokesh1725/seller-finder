import { useEffect } from "react";
import { SITE_NAME, SITE_TAGLINE } from "../constants.js";
import { siteBaseUrl } from "../utils/share.js";

function setMeta(attr, key, content) {
  if (!content) return;
  let tag = document.head.querySelector(`meta[${attr}="${key}"]`);
  if (!tag) {
    tag = document.createElement("meta");
    tag.setAttribute(attr, key);
    document.head.appendChild(tag);
  }
  tag.setAttribute("content", content);
}

/**
 * Client-side document metadata. This updates the title, description and Open
 * Graph tags after navigation. Social crawlers that do not execute JavaScript
 * are handled server-side by the Vercel middleware + /api/og function.
 */
export function useSeo({ title, description, path, image }) {
  useEffect(() => {
    const fullTitle = title ? `${title} | ${SITE_NAME}` : SITE_NAME;
    document.title = fullTitle;
    const desc = description || SITE_TAGLINE;
    const url = `${siteBaseUrl()}${path || ""}`;
    const img = image || `${siteBaseUrl()}/og-default.svg`;

    setMeta("name", "description", desc);
    setMeta("property", "og:title", fullTitle);
    setMeta("property", "og:description", desc);
    setMeta("property", "og:url", url);
    setMeta("property", "og:image", img);
    setMeta("name", "twitter:title", fullTitle);
    setMeta("name", "twitter:description", desc);
  }, [title, description, path, image]);
}
