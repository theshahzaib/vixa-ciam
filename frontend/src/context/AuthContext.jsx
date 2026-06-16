import { createContext, useContext, useState, useCallback } from "react";
import { api, setAccessToken } from "../api/client.js";

const AuthContext = createContext(null);
export const useAuth = () => useContext(AuthContext);

function decodeClaims(token) {
  try {
    const payload = token.split(".")[1];
    return JSON.parse(atob(payload.replace(/-/g, "+").replace(/_/g, "/")));
  } catch {
    return {};
  }
}

export function AuthProvider({ children }) {
  const [session, setSession] = useState(null); // { email, roles, entitlements, org }

  const establish = useCallback((token, email) => {
    setAccessToken(token);
    const claims = decodeClaims(token);
    setSession({
      email,
      subject: claims.sub,
      roles: claims.roles || [],
      entitlements: claims.ent || [],
      organisationId: claims.org || null,
    });
  }, []);

  const logout = useCallback(async () => {
    try { await api.logout(); } catch { /* ignore */ }
    setAccessToken(null);
    setSession(null);
  }, []);

  return (
    <AuthContext.Provider value={{ session, establish, logout }}>
      {children}
    </AuthContext.Provider>
  );
}
