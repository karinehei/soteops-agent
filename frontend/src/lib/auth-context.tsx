"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { useRouter } from "next/navigation";

import type { MeResponse } from "@/lib/api-types";
import { ApiError, api } from "@/lib/api";

interface AuthContextValue {
  user: MeResponse | null;
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  login: (email: string, password: string) => Promise<MeResponse>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const [user, setUser] = useState<MeResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const me = await api.me();
      setUser(me);
    } catch (err) {
      setUser(null);
      if (err instanceof ApiError && err.status === 401) {
        setError(null);
      } else {
        setError(err instanceof Error ? err.message : "Istunnon tarkistus epäonnistui");
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const me = await api.me();
        if (!cancelled) {
          setUser(me);
          setError(null);
        }
      } catch (err) {
        if (!cancelled) {
          setUser(null);
          if (!(err instanceof ApiError && err.status === 401)) {
            setError(err instanceof Error ? err.message : "Istunnon tarkistus epäonnistui");
          }
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const login = useCallback(
    async (email: string, password: string) => {
      setError(null);
      const me = await api.login(email, password);
      setUser(me);
      router.push(me.role === "requester" ? "/requests" : "/review");
      return me;
    },
    [router],
  );

  const logout = useCallback(async () => {
    try {
      await api.logout();
    } finally {
      setUser(null);
      router.push("/login");
    }
  }, [router]);

  const value = useMemo(
    () => ({ user, loading, error, refresh, login, logout }),
    [user, loading, error, refresh, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth requires AuthProvider");
  }
  return ctx;
}

export function useRequireAuth(allowedRoles?: MeResponse["role"][]): {
  user: MeResponse;
  loading: boolean;
} {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !user) {
      router.replace("/login");
    }
    if (!loading && user && allowedRoles && !allowedRoles.includes(user.role)) {
      router.replace("/");
    }
  }, [allowedRoles, loading, router, user]);

  if (loading || !user) {
    return { user: user as MeResponse, loading: true };
  }
  if (allowedRoles && !allowedRoles.includes(user.role)) {
    return { user, loading: true };
  }
  return { user, loading: false };
}
