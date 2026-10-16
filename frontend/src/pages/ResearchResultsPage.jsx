import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { api } from "../api.js";

export default function ResearchResultsPage() {
  const { jobId } = useParams();
  const [job, setJob] = useState(null);
  const [loading, setLoading] = useState(true);

  async function load() {
    const j = await api.getResearch(jobId);
    setJob(j);
    setLoading(false);
  }

  async function refresh() {
    setLoading(true);
    const j = await api.refreshResearch(jobId);
    setJob(j);
    setLoading(false);
  }

  useEffect(() => { load(); }, [jobId]);
  if (loading) return <div className="container page">Loading...</div>;
  if (!job) return <div className="container page">Not found</div>;
  const results = job.results || {};
  return (
    <div className="container page">
      <h1>Research: {job.company_name}</h1>
      <p>Status: {job.status} | Progress: {job.progress}% | Step: {job.current_step}</p>
      <div className="panel">
        <h2>Company</h2>
        <p>{results.company_name || "-"}</p>
        <h2>Founders</h2>
        <pre style={{whiteSpace:"pre-wrap"}}>{JSON.stringify(results.founders, null, 2)}</pre>
        <h2>Contacts</h2>
        <pre style={{whiteSpace:"pre-wrap"}}>{JSON.stringify(results.contacts, null, 2)}</pre>
        <h2>Sources</h2>
        {results.source_urls?.map((u, i) => <a key={i} href={u} target="_blank" rel="noreferrer">{u}</a>)}
        <h2>Field Evidence</h2>
        <pre style={{whiteSpace:"pre-wrap"}}>{JSON.stringify(results.field_evidence, null, 2)}</pre>
      </div>
      <div>
        <button className="btn btn-primary" onClick={refresh}>Refresh Research</button>{" "}
        <a href={api.exportResearchCsvUrl(jobId)} target="_blank" rel="noreferrer" className="btn btn-outline">Export CSV</a>{" "}
        <Link to="/research" className="btn btn-outline">New Search</Link>
      </div>
    </div>
  );
}
