import { statusLabel } from "../utils/format.js";

export default function VerificationBadge({ status, source, lastVerified }) {
  const resolved = status || "unavailable";
  return (
    <span className={`badge badge-${resolved}`} title={source ? `Source: ${source}` : undefined}>
      {statusLabel(resolved)}
      {lastVerified ? <span className="badge-date"> · {lastVerified}</span> : null}
    </span>
  );
}
