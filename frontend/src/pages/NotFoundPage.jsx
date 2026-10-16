import { Link } from "react-router-dom";
import { useSeo } from "../hooks/useSeo.js";

export default function NotFoundPage() {
  useSeo({ title: "Page not found", path: "/404" });
  return (
    <div className="container page">
      <div className="state state-empty">
        <strong className="state-title">Page not found</strong>
        <p className="state-message">The page you are looking for does not exist.</p>
        <Link className="btn btn-primary" to="/">
          Back to search
        </Link>
      </div>
    </div>
  );
}
