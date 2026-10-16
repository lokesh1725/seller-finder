import { Link, NavLink, useNavigate } from "react-router-dom";
import { SITE_NAME } from "../constants.js";
import { useAuth } from "../hooks/useAuth.jsx";
import { useTheme } from "../hooks/useTheme.jsx";

export default function Header() {
  const { user, logout, isAuthenticated } = useAuth();
  const { isDark, toggle } = useTheme();
  const navigate = useNavigate();

  function handleLogout() {
    logout();
    navigate("/login", { replace: true });
  }

  return (
    <header className="site-header">
      <div className="container header-inner">
        <Link to="/" className="brand" aria-label={`${SITE_NAME} home`}>
          <span className="brand-mark">SF</span>
          <span className="brand-text">
            <strong>Seller Finder</strong>
            <small>India business intelligence</small>
          </span>
        </Link>

        {isAuthenticated && (
          <nav className="main-nav" aria-label="Main">
            <NavLink to="/" end>
              Search
            </NavLink>
            <NavLink to="/saved">Saved Leads</NavLink>
          </nav>
        )}

        <div className="header-actions">
          <button
            type="button"
            className="theme-toggle"
            onClick={toggle}
            aria-label={isDark ? "Switch to light theme" : "Switch to dark theme"}
            title={isDark ? "Switch to light theme" : "Switch to dark theme"}
            aria-pressed={isDark}
          >
            {isDark ? (
              <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
                <circle
                  cx="12"
                  cy="12"
                  r="4.2"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                />
                <path
                  d="M12 2v2.6M12 19.4V22M2 12h2.6M19.4 12H22M4.9 4.9l1.8 1.8M17.3 17.3l1.8 1.8M19.1 4.9l-1.8 1.8M6.7 17.3l-1.8 1.8"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                />
              </svg>
            ) : (
              <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
                <path
                  d="M21 12.8A9 9 0 1111.2 3a7 7 0 009.8 9.8z"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinejoin="round"
                />
              </svg>
            )}
          </button>
          {isAuthenticated ? (
            <div className="user-menu">
              <span className="user-email" title={user?.email}>
                {user?.email}
              </span>
              <button type="button" className="btn btn-outline" onClick={handleLogout}>
                Log out
              </button>
            </div>
          ) : (
            <NavLink to="/login" className="btn btn-primary">
              Log in
            </NavLink>
          )}
        </div>
      </div>
    </header>
  );
}
