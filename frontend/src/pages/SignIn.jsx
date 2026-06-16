import { useState } from "react";
import { api } from "../api/client.js";
import { useAuth } from "../context/AuthContext.jsx";

export default function SignIn({ onSignedIn, goRegister }) {
  const { establish } = useAuth();
  const [email, setEmail] = useState("founder@acme-corp.com");
  const [password, setPassword] = useState("Sup3rSecret!pw");
  const [challenge, setChallenge] = useState(null); // { challenge_id }
  const [otp, setOtp] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [hint, setHint] = useState("");

  const submit = async () => {
    setBusy(true); setError("");
    try {
      const res = await api.login(email, password);
      if (res.mfa_required) {
        setChallenge(res);
        // Dev convenience: surface the OTP so the demo flows without a real inbox.
        try {
          const { code } = await api.devLoginOtp(res.challenge_id);
          if (code) setOtp(code);
        } catch { /* non-dev: user reads it from their email */ }
        setHint("A step-up code was sent to your email (admin accounts require MFA).");
      } else {
        establish(res.access_token, email);
        onSignedIn();
      }
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  };

  const submitMfa = async () => {
    setBusy(true); setError("");
    try {
      const res = await api.loginMfa(challenge.challenge_id, otp, email);
      establish(res.access_token, email);
      onSignedIn();
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  };

  return (
    <div className="card signin">
      <h2>Sign in</h2>
      {error && <div className="alert error">{error}</div>}
      {hint && <div className="alert info">{hint}</div>}

      {!challenge ? (
        <div className="grid">
          <label>Email<input value={email} onChange={(e) => setEmail(e.target.value)} /></label>
          <label>Password<input type="password" value={password} onChange={(e) => setPassword(e.target.value)} /></label>
          <button disabled={busy} onClick={submit}>{busy ? "…" : "Sign in"}</button>
        </div>
      ) : (
        <div className="grid">
          <p>Enter the step-up code to finish signing in.</p>
          <label>One-time code<input value={otp} onChange={(e) => setOtp(e.target.value)} /></label>
          <button disabled={busy || !otp} onClick={submitMfa}>Verify & continue</button>
        </div>
      )}

      <p className="switch">New here? <a onClick={goRegister}>Create an organisation account</a></p>
    </div>
  );
}
