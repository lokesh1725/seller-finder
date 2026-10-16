import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import SearchBar from "../components/SearchBar.jsx";
import CompanyCard from "../components/CompanyCard.jsx";
import { Spinner, StateMessage } from "../components/StateMessage.jsx";
import { useSeo } from "../hooks/useSeo.js";
import { useRecentSearches } from "../hooks/useRecentSearches.js";
import { api } from "../api.js";
import { FEATURED_CATEGORIES } from "../constants.js";

function normalize(value) {
  return String(value || "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

export default function ResultsPage() {
  const [params, setParams] = useSearchParams();
  const query = params.get("q") || "";
  const category = params.get("category") || "";
  const city = params.get("city") || "";

  const [state, setState] = useState({ loading: true, error: null, data: null });
  const { add } = useRecentSearches();

  useSeo({
    title: query ? `Results for "${query}"` : "Browse businesses",
    description: query
      ? `Companies matching ${query}`
      : "Browse Indian fashion brands, sellers and manufacturers.",
    path: `/results?${params.toString()}`,
  });

  useEffect(() => {
    let cancelled = false;
    setState({ loading: true, error: null, data: null });
    if (query) add(query);

    api
      .search(query, { category, city, limit: 50 })
      .then((data) => {
        if (!cancelled) setState({ loading: false, error: null, data });
      })
      .catch((err) => {
        if (!cancelled) setState({ loading: false, error: err.message, data: null });
      });

    return () => {
      cancelled = true;
    };
  }, [query, category, city, add]);

  const results = state.data?.results || [];
  const queryNorm = useMemo(() => normalize(query), [query]);

  function setFilter(key, value) {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    setParams(next);
  }

  return (
    <div className="container page">
      <div className="results-search">
        <SearchBar initialValue={query} size="compact" />
      </div>

      <div className="filters" role="group" aria-label="Filters">
        <label>
          <span>Category</span>
          <select value={category} onChange={(e) => setFilter("category", e.target.value)}>
            <option value="">All categories</option>
            {FEATURED_CATEGORIES.map((item) => (
              <option key={item.value} value={item.value}>
                {item.label}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>Location</span>
          <input
            type="text"
            value={city}
            placeholder="City or state"
            onChange={(e) => setFilter("city", e.target.value)}
          />
        </label>
      </div>

      {state.loading && <Spinner label="Searching the database..." />}

      {state.error && (
        <StateMessage variant="error" title="Search failed" message={state.error} />
      )}

      {!state.loading && !state.error && results.length === 0 && (
        <StateMessage
          variant="empty"
          title="No matching businesses found"
          message="We could not find this company in the database. If a web-search provider is configured, new public results appear here automatically."
        />
      )}

      {!state.loading && !state.error && results.length > 0 && (
        <>
          <p className="results-count">
            Showing <strong>{results.length}</strong>
            {state.data.total > results.length ? ` of ${state.data.total}` : ""} result
            {results.length === 1 ? "" : "s"}
            {state.data.source ? <span className="muted">    -   source: {state.data.source}</span> : null}
          </p>

          {state.data.web_search && state.data.web_search.available === false && (
            <StateMessage
              variant="info"
              message="External web search is not configured, so only stored records are shown."
            />
          )}

          <div className="card-grid">
            {results.map((business) => {
              const matchType =
                queryNorm &&
                normalize(business.company_name) === queryNorm
                  ? "exact"
                  : query
                  ? "partial"
                  : null;
              return (
                <CompanyCard
                  key={business.business_id || business.slug}
                  business={business}
                  matchType={matchType}
                />
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}
