import { useEffect, useState } from "react";
import { api } from "../api/client.js";

export default function AdminConsole({ goHome }) {
  const [org, setOrg] = useState(null);
  const [audit, setAudit] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    (async () => {
      try {
        setOrg(await api.adminOrg());
        setAudit(await api.audit());
      } catch (e) { setError(e.message); }
    })();
  }, []);

  return (
    <div className="home">
      <header className="topbar">
        <strong>Admin console</strong>
        <button className="ghost" onClick={goHome}>← Back to products</button>
      </header>

      {error && <div className="alert error">{error}</div>}

      {org && (
        <div className="card">
          <h3>{org.profile?.name}</h3>
          <p className="muted">Organisation {org.organisation_id} · domain verified: {String(org.domain_verified)}</p>
          <p>Entitlements: {org.entitlements?.join(", ")}</p>
          <h4>Sites</h4>
          <ul>{org.sites?.map((s) => <li key={s.id}>{s.name} — {s.location}</li>)}</ul>
        </div>
      )}

      {audit && (
        <div className="card">
          <h3>Audit log <span className={`badge ${audit.chain_valid ? "ok" : "bad"}`}>
            chain {audit.chain_valid ? "valid" : "broken"}</span></h3>
          <table className="audit">
            <thead><tr><th>When</th><th>Action</th><th>Actor</th><th>Target</th></tr></thead>
            <tbody>
              {audit.entries?.slice(-12).reverse().map((e, i) => (
                <tr key={i}>
                  <td className="muted small">{e.at?.slice(11, 19)}</td>
                  <td>{e.action}</td>
                  <td className="muted small">{e.actor || "—"}</td>
                  <td className="muted small">{e.target || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
