import { useState } from "react";
import { api } from "../api/client.js";

const PHASES = ["Account", "Verify contact", "Payment", "Domain", "Done"];

// Dummy initial form data to speed up testing. In production these would all be blank.

const initialForm = {
  email: "founder@acme-corp.com",
  password: "Sup3rSecret!pw",
  full_name: "Ada Founder",
  org_name: "Acme Corp",
  country: "UK",
  city: "London",
  address: "1 High Street",
  postcode: "EC1A 1BB",
  telephone: "+44 20 7946 0000",
  site_name: "Headquarters",
  site_location: "London",
};

export default function RegisterWizard({ onDone, goSignIn }) {
  const [form, setForm] = useState(initialForm);
  const [saga, setSaga] = useState(null);
  const [step, setStep] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [emailCode, setEmailCode] = useState("");
  const [mobileCode, setMobileCode] = useState("");
  const [card, setCard] = useState("tok_visa_demo");
  const [domainRecord, setDomainRecord] = useState(null);

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  const run = async (fn) => {
    setBusy(true); setError("");
    try { await fn(); }
    catch (err) { setError(err.message); }
    finally { setBusy(false); }
  };

  const start = () => run(async () => {
    const payload = {
      email: form.email, password: form.password, full_name: form.full_name,
      recaptcha_token: "human", consent_gdpr: true,
      organisation: {
        name: form.org_name, country: form.country, city: form.city,
        address: form.address, postcode: form.postcode, telephone: form.telephone,
        directors: [form.full_name],
      },
      sites: [{ name: form.site_name, location: form.site_location, responsible_managers: [form.full_name] }],
    };
    const state = await api.startOnboarding(payload);
    setSaga(state);
    const otp = await api.devOtp(state.saga_id);
    setEmailCode(otp.email_code || "");
    setStep(1);
  });

  const doEmail = () => run(async () => {
    const state = await api.verifyEmail(saga.saga_id, emailCode);
    setSaga(state);
    const otp = await api.devOtp(state.saga_id);
    setMobileCode(otp.mobile_code || "");
  });

  const doMobile = () => run(async () => {
    const state = await api.verifyMobile(saga.saga_id, mobileCode);
    setSaga(state);
    setStep(2);
  });

  const doCard = () => run(async () => {
    const state = await api.verifyCard(saga.saga_id, card);
    setSaga(state);
    const rec = await api.domainRecord(saga.saga_id);
    setDomainRecord(rec);
    setStep(3);
  });

  const doDomain = () => run(async () => {
    const state = await api.verifyDomain(saga.saga_id);
    setSaga(state);
    setStep(4);
  });

  return (
    <div className="card wizard">
      <h2>Create your organisation account</h2>
      <ol className="phases">
        {PHASES.map((p, i) => (
          <li key={p} className={i === step ? "active" : i < step ? "done" : ""}>{p}</li>
        ))}
      </ol>

      {error && <div className="alert error">{error}</div>}

      {step === 0 && (
        <div className="grid">
          <label>Full name<input value={form.full_name} onChange={set("full_name")} /></label>
          <label>Work email<input value={form.email} onChange={set("email")} /></label>
          <label>Password<input type="password" value={form.password} onChange={set("password")} /></label>
          <label>Organisation<input value={form.org_name} onChange={set("org_name")} /></label>
          <label>Country<input value={form.country} onChange={set("country")} /></label>
          <label>City<input value={form.city} onChange={set("city")} /></label>
          <label>Address<input value={form.address} onChange={set("address")} /></label>
          <label>Postcode<input value={form.postcode} onChange={set("postcode")} /></label>
          <label>Telephone<input value={form.telephone} onChange={set("telephone")} /></label>
          <label>Primary site<input value={form.site_name} onChange={set("site_name")} /></label>
          <p className="consent">By continuing you provide GDPR consent. A reCAPTCHA score is taken in the background.</p>
          <button disabled={busy} onClick={start}>{busy ? "Working…" : "Begin onboarding"}</button>
        </div>
      )}

      {step === 1 && (
        <div className="grid">
          <p>We sent one-time codes to your email and phone. (Dev mode pre-fills them.)</p>
          <label>Email code<input value={emailCode} onChange={(e) => setEmailCode(e.target.value)} /></label>
          <button disabled={busy} onClick={doEmail}>Verify email</button>
          <label>Mobile code<input value={mobileCode} onChange={(e) => setMobileCode(e.target.value)} /></label>
          <button disabled={busy || !mobileCode} onClick={doMobile}>Verify mobile</button>
        </div>
      )}

      {step === 2 && (
        <div className="grid">
          <p>Card verification places a refundable €1 hold via 3-D Secure. Card data is tokenised by the gateway and never reaches our platform.</p>
          <label>Payment method token<input value={card} onChange={(e) => setCard(e.target.value)} /></label>
          <p className="hint">Tip: enter <code>decline</code> to simulate a declined card.</p>
          <button disabled={busy} onClick={doCard}>Verify card</button>
        </div>
      )}

      {step === 3 && (
        <div className="grid">
          <p>Add this TXT record to your domain's DNS, then confirm. (Dev mode pre-publishes it.)</p>
          {domainRecord && (
            <pre className="record">
{`${domainRecord.record_type}  ${domainRecord.host}
"${domainRecord.value}"  (TTL ${domainRecord.ttl_seconds}s)`}
            </pre>
          )}
          <button disabled={busy} onClick={doDomain}>Confirm domain & activate</button>
        </div>
      )}

      {step === 4 && (
        <div className="grid">
          <div className="alert success">Account activated. Organisation <code>{saga?.organisation_id}</code> is live.</div>
          <p>Sign in to reach your Products &amp; Services home.</p>
          <button onClick={goSignIn}>Go to sign in</button>
        </div>
      )}

      <p className="switch">Already have an account? <a onClick={goSignIn}>Sign in</a></p>
    </div>
  );
}
