import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, tokenStore, type Me, type Role } from "./api";

const RANK: Record<Role, number> = { viewer: 0, analyst: 1, admin: 2 };

interface AuthState {
  me: Me | null;
  status: "checking" | "anonymous" | "authenticated";
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  can: (minimum: Role) => boolean;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [status, setStatus] = useState<AuthState["status"]>(tokenStore.get() ? "checking" : "anonymous");

  useEffect(() => {
    if (!tokenStore.get()) return;
    api.me()
      .then((m) => {
        setMe(m);
        setStatus("authenticated");
      })
      .catch(() => {
        tokenStore.clear();
        setStatus("anonymous");
      });
  }, []);

  useEffect(() => {
    const onUnauthorized = () => {
      tokenStore.clear();
      setMe(null);
      setStatus("anonymous");
    };
    window.addEventListener("soar:unauthorized", onUnauthorized);
    return () => window.removeEventListener("soar:unauthorized", onUnauthorized);
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    const res = await api.login(username, password);
    tokenStore.set(res.access_token);
    setMe(await api.me());
    setStatus("authenticated");
  }, []);

  const logout = useCallback(async () => {
    try {
      await api.logout();
    } catch {
      /* token may already be invalid: logging out locally is enough */
    }
    tokenStore.clear();
    setMe(null);
    setStatus("anonymous");
  }, []);

  const can = useCallback((minimum: Role) => !!me && RANK[me.role] >= RANK[minimum], [me]);

  const value = useMemo(() => ({ me, status, login, logout, can }), [me, status, login, logout, can]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
