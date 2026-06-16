// Thin fetch wrapper around the FastAPI backend.
// Handles bearer-token injection, refresh-token cookies (credentials: include)
// and RFC 7807 problem+json error parsing.

const BASE = "/api/v1";

let accessToken = null;
export const setAccessToken = (t) => { accessToken = t; };
export const getAccessToken = () => accessToken;

async function request(path, { method = "GET", body, auth = false, query } = {}) {
  const headers = { "Content-Type": "application/json" };
  if (auth && accessToken) headers["Authorization"] = `Bearer ${accessToken}`;

  let url = `${BASE}${path}`;
  if (query) url += "?" + new URLSearchParams(query).toString();

  const res = await fetch(url, {
    method,
    headers,
    credentials: "include", // send/receive the HTTP-only refresh cookie
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  const text = await res.text();
  const data = text ? JSON.parse(text) : null;
  if (!res.ok) {
    const detail = data?.detail || data?.title || `Request failed (${res.status})`;
    const err = new Error(detail);
    err.status = res.status;
    err.problem = data;
    throw err;
  }
  return data;
}

export const api = {
  // --- onboarding saga ---
  startOnboarding: (payload) => request("/onboarding", { method: "POST", body: payload }),
  verifyEmail: (sagaId, code) =>
    request(`/onboarding/${sagaId}/email`, { method: "POST", body: { challenge_id: "", code } }),
  verifyMobile: (sagaId, code) =>
    request(`/onboarding/${sagaId}/mobile`, { method: "POST", body: { challenge_id: "", code } }),
  verifyCard: (sagaId, token) =>
    request(`/onboarding/${sagaId}/card`, { method: "POST", body: { payment_method_token: token } }),
  domainRecord: (sagaId) => request(`/onboarding/${sagaId}/domain-record`),
  verifyDomain: (sagaId) => request(`/onboarding/${sagaId}/domain`, { method: "POST" }),
  devOtp: (sagaId) => request(`/onboarding/${sagaId}/dev/otp`),

  // --- auth ---
  login: (email, password) =>
    request("/auth/login", { method: "POST", body: { email, password, recaptcha_token: "human" } }),
  loginMfa: (challengeId, code, email) =>
    request("/auth/login/mfa", { method: "POST", query: { challenge_id: challengeId, code, email } }),
  refresh: () => request("/auth/refresh", { method: "POST" }),
  logout: () => request("/auth/logout", { method: "POST", auth: true }),
  devLoginOtp: (challengeId) => request("/auth/dev/otp", { query: { challenge_id: challengeId } }),

  // --- products / subscriptions ---
  products: () => request("/products", { auth: true }),
  subscribe: (product) => request("/subscribe", { method: "POST", auth: true, body: { product } }),
  openVault: () => request("/products/vault/open", { auth: true }),

  // --- admin ---
  adminOrg: () => request("/admin/organisation", { auth: true }),

  // --- system ---
  audit: () => request("/system/audit", { auth: false }),
};
