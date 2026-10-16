import { useNavigate } from "react-router-dom";
import SearchBar from "../components/SearchBar.jsx";
import { useRecentSearches } from "../hooks/useRecentSearches.js";
import { useSeo } from "../hooks/useSeo.js";
import { FEATURED_CATEGORIES, FEATURED_CITIES, SITE_NAME, SITE_TAGLINE } from "../constants.js";

const EXAMPLES = ["Bummer", "Gulabo Jaipur", "Bunaai", "A N Knitwear"];

export default function HomePage() {
  const navigate = useNavigate();
  const { recent, add, remove, clear } = useRecentSearches();
  useSeo({ title: "Search", path: "/" });

  function runSearch(query) {
    add(query);
    navigate(`/results?q=${encodeURIComponent(query)}`);
  }

  return (
    <div className="home">
      <section className="hero">
        <div className="container hero-inner">
          <h1>{SITE_NAME}</h1>
          <p className="hero-tagline">{SITE_TAGLINE}</p>
          <SearchBar autoFocus onSubmit={runSearch} />
          <div className="examples">
            <span>Try:</span>
            {EXAMPLES.map((example) => (
              <button
                key={example}
                type="button"
                className="chip"
                onClick={() => runSearch(example)}
              >
                {example}
              </button>
            ))}
          </div>
        </div>
      </section>

      <div className="container home-columns">
        {recent.length > 0 && (
          <section className="panel">
            <div className="panel-head">
              <h2>Recent searches</h2>
              <button type="button" className="link-btn" onClick={clear}>
                Clear
              </button>
            </div>
            <ul className="recent-list">
              {recent.map((query) => (
                <li key={query}>
                  <button type="button" className="recent-item" onClick={() => runSearch(query)}>
                    <span>{query}</span>
                  </button>
                  <button
                    type="button"
                    className="icon-btn"
                    aria-label={`Remove ${query}`}
                    onClick={() => remove(query)}
                  >
                    ×
                  </button>
                </li>
              ))}
            </ul>
          </section>
        )}

        <section className="panel">
          <h2>Featured categories</h2>
          <ul className="category-grid">
            {FEATURED_CATEGORIES.map((category) => (
              <li key={category.value}>
                <button
                  type="button"
                  className="category-card"
                  onClick={() =>
                    navigate(`/results?category=${encodeURIComponent(category.value)}`)
                  }
                >
                  <strong>{category.label}</strong>
                  <span>{category.description}</span>
                </button>
              </li>
            ))}
          </ul>
        </section>

        <section className="panel">
          <h2>Popular manufacturing hubs</h2>
          <div className="city-chips">
            {FEATURED_CITIES.map((city) => (
              <button
                key={city}
                type="button"
                className="chip"
                onClick={() => navigate(`/results?city=${encodeURIComponent(city)}`)}
              >
                {city}
              </button>
            ))}
          </div>
          <p className="muted small">
            Searches are not limited to these cities — any Indian state or city is supported.
          </p>
        </section>
      </div>
    </div>
  );
}
