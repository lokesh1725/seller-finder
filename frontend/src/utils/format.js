import { VERIFICATION_LABELS } from "../constants.js";

export function displayValue(value) {
  if (value === null || value === undefined) return null;
  if (Array.isArray(value)) return value.length ? value.join(", ") : null;
  const text = String(value).trim();
  if (!text || /^not found$/i.test(text)) return null;
  return text;
}

export function statusLabel(status) {
  return VERIFICATION_LABELS[status] || "Not available";
}

export function verificationEntry(doc, field) {
  return doc?.field_verification_status?.[field] || null;
}

export function formatDate(value) {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return date.toLocaleDateString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

export function titleCase(value) {
  if (!value) return "";
  return value
    .split(/[-\s]/)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

export function categoryShort(value) {
  if (!value) return "Uncategorised";
  if (value.includes("/")) return value.split("/")[0].trim();
  return value;
}
