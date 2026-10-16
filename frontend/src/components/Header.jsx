import { Link, NavLink, useNavigate } from "react-router-dom";
import { SITE_NAME } from "../constants.js";
import { useAuth } from "../hooks/useAuth.jsx";

export default function Header() {
  const { user, logout, isAuthenticated } = useAuth();
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
