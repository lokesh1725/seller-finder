import { Link } from "react-router-dom";
import { categoryShort } from "../utils/format.js";

function availabilityLabel(item) {
  const parts = [];
  if (item.has_email) parts.push("Email");
  if (item.has_phone) parts.push("Phone");
  if (item.has_linkedin) parts.push("LinkedIn");
  return parts.length ? parts.join(" · ") : "No public contacts yet";
}

export default function CompanyCard({ business, matchType }) {
  const location = [business.city, business.state].filter(Boolean).join(", ");
  return (
    <article className="company-card">
      <div className="company-card-head">
        <h3>
          <Link to={`/business/${business.slug}`}>{business.company_name}</Link>
        </h3>
        {matchType ? <span className={`match-tag match-${matchType}`}>{matchType} match</span> : null}
      </div>

      <p className="company-category">{categoryShort(business.business_category)}</p>

      <dl className="company-meta">
        <div>
          <dt>Location</dt>
          <dd>{location || "Not found"}</dd>
        </div>
        <div>
          <dt>Website</dt>
          <dd>
            {business.official_website ? (
              <a href={business.official_website} target="_blank" rel="noopener noreferrer">
                {business.official_website.replace(/^https?:\/\//, "")}
              </a>
            ) : (
              <span className="muted">Not found</span>
            )}
          </dd>
        </div>
        <div>
          <dt>Public contacts</dt>
          <dd>{availabilityLabel(business)}</dd>
        </div>
      </dl>

      {Array.isArray(business.alternate_names) && business.alternate_names.length > 0 && (
        <p className="company-alias">
          Also known as: {business.alternate_names.join(", ")}
        </p>
      )}

      <Link className="btn btn-outline company-card-cta" to={`/business/${business.slug}`}>
        View profile
      </Link>
    </article>
  );
}
