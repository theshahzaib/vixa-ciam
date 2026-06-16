# ViXa CIAM — Frontend (React + Vite)

A single-page app that consumes the FastAPI backend. No UI framework beyond
React; styling is a single stylesheet.

## Run

```bash
npm install
npm run dev        # http://localhost:5173  (proxies /api to :8000)
npm run build      # production bundle in dist/
```

## Structure

| Path | Purpose |
| --- | --- |
| `src/api/client.js` | Fetch wrapper: bearer tokens, refresh cookie, problem+json errors |
| `src/context/AuthContext.jsx` | Session state; decodes JWT claims (roles, entitlements) |
| `src/pages/RegisterWizard.jsx` | Drives the five-phase onboarding saga |
| `src/pages/SignIn.jsx` | Login with MFA step-up |
| `src/pages/ProductsHome.jsx` | Entitlement-gated product tiles + subscribe |
| `src/pages/AdminConsole.jsx` | Org overview + audit-log chain |

The SPA mirrors the architecture's authentication surfaces: a first-time visitor
sees the front door (sign in / create account), and only after sign-in are the
entitlement-gated product tiles rendered.
