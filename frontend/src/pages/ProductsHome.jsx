import { useEffect, useState } from "react";
import { api } from "../api/client.js";
import { useAuth } from "../context/AuthContext.jsx";

export default function ProductsHome({ goAdmin }) {
  const { session, establish, logout } = useAuth();
  const [home, setHome] = useState(null);
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);

  const load = async () => {
    try { setHome(await api.products()); } catch (e) { setMsg(e.message); }
  };
  useEffect(() => { load(); }, []);

  const subscribe = async (productId) => {
    setBusy(true); setMsg("");
    try {
      const res = await api.subscribe(productId);
      setMsg(res.detail);
      // Entitlements refresh on the next token cycle — rotate the token now.
      try {
        const t = await api.refresh();
        establish(t.access_token, session.email);
      } catch { /* fall back to re-login */ }
      await load();
    } catch (e) { setMsg(e.message); }
    finally { setBusy(false); }
  };

  const tryVault = async () => {
    setMsg("");
    try { const r = await api.openVault(); setMsg(r.detail); }
    catch (e) { setMsg(`Gate refused: ${e.message}`); }
  };

  return (
    <div className="home">
      <header className="topbar">
        <div>
          <strong>Welcome to Ost Infinity</strong>
          <span className="muted"> · {session?.email}</span>
        </div>
        <nav>
          {session?.roles?.includes("admin") && <button className="ghost" onClick={goAdmin}>Admin console</button>}
          <button className="ghost" onClick={tryVault}>Test Vault gate</button>
          <button className="ghost" onClick={logout}>Sign out</button>
        </nav>
      </header>

      {msg && <div className="alert info">{msg}</div>}

      <div className="tiles">
        {home?.tiles?.map((t) => (
          <div key={t.id} className={`tile ${t.state}`}>
            <div className="tile-head">
              <h3>{t.name}</h3>
              {t.base && <span className="badge">Base</span>}
            </div>
            <p className="muted">{t.id}</p>
            {t.state === "active" ? (
              <span className="state active">Active</span>
            ) : (
              <button disabled={busy} onClick={() => subscribe(t.id)}>Subscribe</button>
            )}
          </div>
        ))}
      </div>

      <p className="muted small">
        Entitlements are read directly from your JWT claims — the gateway authorises each
        navigation against the token, with no database lookup on the hot path.
      </p>
    </div>
  );
}
