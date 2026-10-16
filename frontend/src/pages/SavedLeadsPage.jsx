import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Spinner, StateMessage } from "../components/StateMessage.jsx";
import { useSeo } from "../hooks/useSeo.js";
import { api } from "../api.js";
import { OUTREACH_STATES } from "../constants.js";
import { formatDate } from "../utils/format.js";

function LeadRow({ lead, onChanged, onDeleted }) {
  const [notes, setNotes] = useState(lead.notes || "");
  const [tags, setTags] = useState((lead.tags || []).join(", "));
  const [status, setStatus] = useState(lead.outreach_status || "new");
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");

  async function save(patch) {
    setSaving(true);
    setMessage("");
    try {
      const updated = await api.updateLead(lead.lead_id, patch);
      onChanged(updated);
      setMessage("Saved");
      window.setTimeout(() => setMessage(""), 1500);
    } catch (err) {
      setMessage(err.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <article className="lead-card panel">
      <div className="lead-head">
        <h3>
          <Link to={`/business/${lead.slug || lead.business_id}`}>
            {lead.company_name || lead.business_id}
          </Link>
        </h3>
        <span className={`status-pill status-${status}`}>{status}</span>
      </div>
      <p className="muted small">Saved {formatDate(lead.created_at) || ""}</p>

      <label className="field">
        <span>Outreach status</span>
        <select
          value={status}
          onChange={(e) => {
            setStatus(e.target.value);
            save({ outreach_status: e.target.value });
          }}
        >
          {OUTREACH_STATES.map((state) => (
            <option key={state} value={state}>
              {state}
            </option>
          ))}
        </select>
      </label>

      <label className="field">
        <span>Tags (comma separated)</span>
        <input
          type="text"
          value={tags}
          onChange={(e) => setTags(e.target.value)}
          onBlur={() => save({ tags })}
          placeholder="e.g. d2c, priority, jaipur"
        />
      </label>

      <label className="field">
        <span>Notes</span>
        <textarea
          rows={3}
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          onBlur={() => save({ notes })}
          placeholder="Outreach notes..."
        />
      </label>

      <div className="lead-actions">
        <button
          type="button"
          className="btn btn-ghost"
          disabled={saving}
          onClick={() => save({ notes, tags, outreach_status: status })}
        >
          {saving ? "Saving..." : "Save changes"}
        </button>
        <button
          type="button"
          className="btn btn-danger-ghost"
          onClick={() => onDeleted(lead.lead_id)}
        >
          Remove
        </button>
        {message ? <span className="muted small">{message}</span> : null}
      </div>
    </article>
  );
}

export default function SavedLeadsPage() {
  const [state, setState] = useState({ loading: true, error: null, leads: [] });
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");

  useSeo({ title: "Saved Leads", path: "/saved" });

  useEffect(() => {
    let cancelled = false;
    api
      .listLeads()
      .then((data) => {
        if (!cancelled) setState({ loading: false, error: null, leads: data.leads || [] });
      })
      .catch((err) => {
        if (!cancelled) setState({ loading: false, error: err.message, leads: [] });
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const filtered = useMemo(() => {
    const term = search.trim().toLowerCase();
    return state.leads.filter((lead) => {
      const matchesTerm =
        !term ||
        (lead.company_name || "").toLowerCase().includes(term) ||
        (lead.tags || []).join(",").toLowerCase().includes(term);
      const matchesStatus = !statusFilter || lead.outreach_status === statusFilter;
      return matchesTerm && matchesStatus;
    });
  }, [state.leads, search, statusFilter]);

  function handleChanged(updated) {
    setState((prev) => ({
      ...prev,
      leads: prev.leads.map((l) => (l.lead_id === updated.lead_id ? updated : l)),
    }));
  }

  async function handleDeleted(leadId) {
    try {
      await api.deleteLead(leadId);
      setState((prev) => ({ ...prev, leads: prev.leads.filter((l) => l.lead_id !== leadId) }));
    } catch (err) {
      setState((prev) => ({ ...prev, error: err.message }));
    }
  }

  function exportCsv() {
    const ids = filtered.map((lead) => lead.business_id).filter(Boolean);
    window.open(api.exportCsvUrl(ids), "_blank", "noopener");
  }

  return (
    <div className="container page">
      <div className="page-head">
        <h1>Saved Leads</h1>
        <button
          type="button"
          className="btn btn-primary"
          onClick={exportCsv}
          disabled={filtered.length === 0}
        >
          Export CSV
        </button>
      </div>

      <div className="filters">
        <label>
          <span>Search saved</span>
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Company or tag"
          />
        </label>
        <label>
          <span>Status</span>
          <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
            <option value="">All statuses</option>
            {OUTREACH_STATES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </label>
      </div>

      {state.loading && <Spinner label="Loading saved leads..." />}
      {state.error && <StateMessage variant="error" title="Could not load leads" message={state.error} />}

      {!state.loading && !state.error && filtered.length === 0 && (
        <StateMessage
          variant="empty"
          title="No saved leads yet"
          message="Open a business profile and click 'Save to Leads' to build your outreach list."
          action={
            <Link className="btn btn-outline" to="/">
              Find businesses
            </Link>
          }
        />
      )}

      {!state.loading && !state.error && filtered.length > 0 && (
        <div className="lead-grid">
          {filtered.map((lead) => (
            <LeadRow
              key={lead.lead_id}
              lead={lead}
              onChanged={handleChanged}
              onDeleted={handleDeleted}
            />
          ))}
        </div>
      )}
    </div>
  );
}
