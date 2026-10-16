import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useSeo } from "../hooks/useSeo.js";
import { api } from "../api.js";

export default function ResearchPage() {
  const [name, setName] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const navigate = useNavigate();
  useSeo({ title: "Founder Contact Finder", path: "/research" });

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const res = await api.startResearch({ company_name: name });
      navigate(`/research/${res.job_id}`);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="container page">
      <h1>Founder Contact Finder</h1>
      <form onSubmit={handleSubmit} className="panel">
        <label className="field">
          <span>Company name</span>
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g., HelmetShopee" required />
        </label>
        <button className="btn btn-primary" disabled={loading}>{loading ? "Searching..." : "Start Research"}</button>
        {error && <p className="muted small">{error}</p>}
      </form>
    </div>
  );
}
