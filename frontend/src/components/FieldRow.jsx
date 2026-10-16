import VerificationBadge from "./VerificationBadge.jsx";
import { displayValue, formatDate, verificationEntry } from "../utils/format.js";

/**
 * A single labeled field in a business profile. Shows the value or "Not found",
 * the verification badge and the source link so every claim is traceable.
 */
export default function FieldRow({ label, field, value, doc, href, children }) {
  const entry = field ? verificationEntry(doc, field) : null;
  const shown = displayValue(value);
  const lastVerified = entry?.last_verified_at ? formatDate(entry.last_verified_at) : null;

  return (
    <div className="field-row">
      <div className="field-label">{label}</div>
      <div className="field-value">
        {shown ? (
          href ? (
            <a href={href} target="_blank" rel="noopener noreferrer">
              {shown}
            </a>
          ) : (
            <span>{shown}</span>
          )
        ) : (
          <span className="muted">Not found</span>
        )}
        {children}
        <div className="field-meta">
          {entry ? (
            <VerificationBadge
              status={entry.status}
              source={entry.source}
              lastVerified={lastVerified}
            />
          ) : null}
          {entry?.source ? (
            <a
              className="source-link"
              href={entry.source}
              target="_blank"
              rel="noopener noreferrer"
            >
              source
            </a>
          ) : null}
        </div>
      </div>
    </div>
  );
}
