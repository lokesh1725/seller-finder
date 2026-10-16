// Central API client for the Seller Finder backend.
// The base URL is injected at build time. When empty, requests use relative
// paths so the Vite dev proxy (or same-origin deployment) handles /api.

const ENV =
  (typeof import.meta !== "undefined" && import.meta && import.meta.env) || {};
const API_BASE = (ENV.VITE_API_BASE_URL || "").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(message, status, code) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

async function request(path, options = {}) {
  let response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      headers: { "Content-Type": "application/json", ...(options.headers || {}) },
      ...options,
    });
  } catch (err) {
    throw new ApiError(
      "Could not reach the server. Please check your connection and try again.",
      0,
      "network_error"
    );
  }

  const contentType = response.headers.get("content-type") || "";
  const isJson = contentType.includes("application/json");
  const body = isJson ? await response.json() : await response.text();

  if (!response.ok) {
    const message =
      (isJson && body?.error?.message) || "Something went wrong. Please try again.";
    const code = (isJson && body?.error?.code) || "error";
    throw new ApiError(message, response.status, code);
  }
  return body;
}

export const api = {
  baseUrl: API_BASE,

  health: () => request("/api/health"),

  search: (query, opts = {}) => {
    const params = new URLSearchParams({ q: query });
    if (opts.category) params.set("category", opts.category);
    if (opts.city) params.set("city", opts.city);
    if (opts.limit) params.set("limit", opts.limit);
    return request(`/api/search?${params.toString()}`);
  },

  getBusiness: (identifier) =>
    request(`/api/businesses/${encodeURIComponent(identifier)}`),

  refreshBusiness: (identifier) =>
    request(`/api/businesses/${encodeURIComponent(identifier)}/refresh`, {
      method: "POST",
    }),

  listLeads: () => request("/api/leads"),

  createLead: (payload) =>
    request("/api/leads", { method: "POST", body: JSON.stringify(payload) }),

  updateLead: (leadId, payload) =>
    request(`/api/leads/${encodeURIComponent(leadId)}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),

  deleteLead: (leadId) =>
    request(`/api/leads/${encodeURIComponent(leadId)}`, { method: "DELETE" }),

  exportCsvUrl: (ids = []) => {
    const params = ids.length ? `?ids=${encodeURIComponent(ids.join(","))}` : "";
    return `${API_BASE}/api/export${params}`;
  },
};
