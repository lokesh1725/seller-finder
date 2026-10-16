import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth.jsx";
import { useSeo } from "../hooks/useSeo.js";
import { SITE_NAME } from "../constants.js";

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useSeo({ title: "Log in", path: "/login" });

  const redirectTo = location.state?.from?.pathname || "/";

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      await login(email.trim(), password);
      navigate(redirectTo, { replace: true });
    } catch (err) {
      setError(err.message || "Login failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="login-wrap">
      <form className="login-card panel" onSubmit={handleSubmit}>
        <div className="login-brand">
          <span className="brand-mark">SF</span>
          <h1>{SITE_NAME}</h1>
          <p className="muted">Log in to search brands, save leads and export data.</p>
        </div>

        {error && (
          <div className="login-error" role="alert">
            {error}
          </div>
        )}

        <label className="field">
          <span>Email</span>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@example.com"
            autoComplete="username"
            required
          />
        </label>

        <label className="field">
          <span>Password</span>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Your password"
            autoComplete="current-password"
            required
          />
        </label>

        <button type="submit" className="btn btn-primary btn-block" disabled={submitting}>
          {submitting ? "Signing in..." : "Log in"}
        </button>

        <p className="muted small login-hint">
          Public business profiles remain viewable without logging in when shared via a
          direct link. <Link to="/">Continue to a shared profile</Link>.
        </p>
      </form>
    </div>
  );
}
