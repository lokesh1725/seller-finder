import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import FieldRow from "../components/FieldRow.jsx";
import ShareButtons from "../components/ShareButtons.jsx";
import { Spinner, StateMessage } from "../components/StateMessage.jsx";
import { useSeo } from "../hooks/useSeo.js";
import { api } from "../api.js";
import { displayValue, formatDate } from "../utils/format.js";
import { siteBaseUrl } from "../utils/share.js";

export default function BusinessPage() {
  const { slug } = useParams();
  const [state, setState] = useState({ loading: true, error: null, business: null });
  const [refreshing, setRefreshing] = useState(false);
  const [refreshNote, setRefreshNote] = useState("");
  const [saveState, setSaveState] = useState({ saving: false, saved: false, message: "" });

  useSeo({
    title: state.business?.company_name || "Business profile",
    description: state.business
      ? `${state.business.company_name}  -  ${state.business.business_category || "business"} in ${
          [state.business.city, state.business.state].filter(Boolean).join(", ") || "India"
        }`
      : "Business profile",
    path: `/business/${slug}`,
    image: `${siteBaseUrl()}/og-default.svg`,
  });

  useEffect(() => {
    let cancelled = false;
    setState({ loading: true, error: null, business: null });
    api
      .getBusiness(slug)
      .then((business) => {
        if (!cancelled) setState({ loading: false, error: null, business });
      })
      .catch((err) => {
        if (!cancelled) setState({ loading: false, error: err.message, business: null });
      });
    return () => {
      cancelled = true;
    };
  }, [slug]);

  const refresh = useCallback(async () => {
    if (!state.business) return;
    setRefreshing(true);
    setRefreshNote("");
    try {
      const result = await api.refreshBusiness(state.business.business_id || slug);
      if (!result.provider_available) {
        setRefreshNote("No external search provider is configured, so nothing could be refreshed.");
      } else if (result.updated_fields?.length) {
        setRefreshNote(`Updated: ${result.updated_fields.join(", ")}`);
        const updated = await api.getBusiness(slug);
        setState({ loading: false, error: null, business: updated });
      } else {
        setRefreshNote("No new public information found.");
      }
    } catch (err) {
      setRefreshNote(err.message);
    } finally {
      setRefreshing(false);
    }
  }, [state.business, slug]);

  const saveLead = useCallback(async () => {
    if (!state.business) return;
    setSaveState({ saving: true, saved: false, message: "" });
    try {
      await api.createLead({
        business_id: state.business.business_id,
        company_name: state.business.company_name,
        slug: state.business.slug,
      });
      setSaveState({ saving: false, saved: true, message: "Saved to your leads" });
    } catch (err) {
      setSaveState({ saving: false, saved: false, message: err.message });
    }
  }, [state.business]);

  if (state.loading) return <div className="container page"><Spinner label="Loading business profile..." /></div>;

  if (state.error) {
    return (
      <div className="container page">
        <StateMessage
          variant="error"
          title="Could not load this profile"
          message={state.error}
          action={<Link className="btn btn-outline" to="/">Back to search</Link>}
        />
      </div>
    );
  }

  const b = state.business;
  const summary = b.verification_summary || {};
  const location = [b.city, b.state, b.pincode, b.country].filter(Boolean).join(", ");

  return (
    <div className="container page business-page">
      <nav className="breadcrumb" aria-label="Breadcrumb">
        <Link to="/">Search</Link>
        <span aria-hidden="true">/</span>
        <span>{b.company_name}</span>
      </nav>

      <header className="business-header panel">
        <div>
          <h1>{b.company_name}</h1>
          {b.alternate_names?.length ? (
            <p className="muted">Also known as: {b.alternate_names.join(", ")}</p>
          ) : null}
          <p className="business-category">{b.business_category || "Uncategorised"}</p>
          {b.product_categories?.length ? (
            <p className="muted small">{b.product_categories.join("    -   ")}</p>
          ) : null}
          {location ? <p className="business-location">{location}</p> : null}
        </div>
        <div className="business-header-actions">
          <ShareButtons business={b} />
          <div className="action-row">
            <button
              type="button"
              className="btn btn-outline"
              onClick={saveLead}
              disabled={saveState.saving || saveState.saved}
            >
              {saveState.saved ? "Saved OK" : "Save to Leads"}
            </button>
            <button
              type="button"
              className="btn btn-ghost"
              onClick={refresh}
              disabled={refreshing}
            >
              {refreshing ? "Refreshing..." : "Refresh from web"}
            </button>
          </div>
          {saveState.message ? <p className="muted small">{saveState.message}</p> : null}
          {refreshNote ? <p className="muted small">{refreshNote}</p> : null}
        </div>
      </header>

      <section className="panel">
        <div className="panel-head">
          <h2>Contact & company details</h2>
          <span className="muted small">
            {summary.fields_with_data ?? 0}/{summary.fields_total ?? 0} fields with data
          </span>
        </div>
        <div className="field-list">
          <FieldRow
            label="Official website"
            field="official_website"
            value={b.official_website}
            doc={b}
            href={b.official_website}
          />
          <FieldRow label="Business email" field="business_email" value={b.business_email} doc={b}>
            {b.business_email && (
              <a className="inline-link" href={`mailto:${b.business_email}`}>
                Send email
              </a>
            )}
          </FieldRow>
          <FieldRow label="Business phone" field="business_phone" value={b.business_phone} doc={b} />
          <FieldRow
            label="LinkedIn company page"
            field="linkedin_company_url"
            value={b.linkedin_company_url ? "View LinkedIn page" : null}
            doc={b}
            href={b.linkedin_company_url}
          />
          <FieldRow label="Founder" field="founder_name" value={b.founder_name} doc={b} />
          <FieldRow label="CEO" field="ceo_name" value={b.ceo_name} doc={b} />
          <FieldRow
            label="Founder LinkedIn"
            value={b.founder_linkedin_url ? "View profile" : null}
            doc={b}
            href={b.founder_linkedin_url}
          />
          <FieldRow
            label="Business address"
            field="business_address"
            value={b.business_address}
            doc={b}
          />
          <FieldRow label="City" value={b.city} doc={b} />
          <FieldRow label="State" value={b.state} doc={b} />
          <FieldRow label="Pincode" value={b.pincode} doc={b} />
          <FieldRow label="Country" value={b.country} doc={b} />
        </div>
      </section>

      <section className="panel two-col">
        <div>
          <h2>Marketplace profiles</h2>
          {b.marketplace_profiles?.length ? (
            <ul className="link-list">
              {b.marketplace_profiles.map((profile, index) => (
                <li key={`${profile.label}-${index}`}>
                  {profile.url ? (
                    <a href={profile.url} target="_blank" rel="noopener noreferrer">
                      {profile.label}
                    </a>
                  ) : (
                    <span>
                      {profile.label} <span className="muted">(link not captured)</span>
                    </span>
                  )}
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted">Not found</p>
          )}
        </div>
        <div>
          <h2>Manufacturing & trade</h2>
          <dl className="mini-dl">
            <div>
              <dt>Manufacturing capabilities</dt>
              <dd>
                {displayValue(b.manufacturer_capabilities) || (
                  <span className="muted">Not found</span>
                )}
              </dd>
            </div>
            <div>
              <dt>Minimum order quantity</dt>
              <dd>{displayValue(b.minimum_order_quantity) || <span className="muted">Not found</span>}</dd>
            </div>
            <div>
              <dt>Export capability</dt>
              <dd>
                {b.export_capability === true ? (
                  "Yes (per source)"
                ) : b.export_capability === false ? (
                  "No (per source)"
                ) : (
                  <span className="muted">Not found</span>
                )}
              </dd>
            </div>
          </dl>
        </div>
      </section>

      <section className="panel">
        <h2>Sources</h2>
        {b.source_urls?.length ? (
          <ul className="link-list sources">
            {b.source_urls.map((url) => (
              <li key={url}>
                <a href={url} target="_blank" rel="noopener noreferrer">
                  {url}
                </a>
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted">No source URLs recorded.</p>
        )}
        <p className="muted small">
          Last checked: {formatDate(b.last_verified_at) || "Not independently verified"}
        </p>
      </section>
    </div>
  );
}
