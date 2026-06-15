import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import {
  type CurrentUser,
  clearToken,
  fetchMe,
  getToken,
  login as apiLogin,
  setToken as storeToken,
  setUnauthorizedHandler,
} from "../api/client";

interface AuthState {
  token: string | null;
  user: CurrentUser | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthState | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setTokenState] = useState<string | null>(() => getToken());
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  // Any API 401 (expired/invalid token) clears auth and the ProtectedLayout
  // then redirects to /login.
  useEffect(() => {
    setUnauthorizedHandler(() => {
      clearToken();
      setTokenState(null);
      setUser(null);
    });
    return () => setUnauthorizedHandler(null);
  }, []);

  useEffect(() => {
    let active = true;
    async function load() {
      if (!token) {
        setUser(null);
        setLoading(false);
        return;
      }
      try {
        const me = await fetchMe();
        if (active) setUser(me);
      } catch {
        if (active) {
          clearToken();
          setTokenState(null);
          setUser(null);
        }
      } finally {
        if (active) setLoading(false);
      }
    }
    setLoading(true);
    void load();
    return () => {
      active = false;
    };
  }, [token]);

  async function login(email: string, password: string) {
    const newToken = await apiLogin(email, password);
    storeToken(newToken);
    setTokenState(newToken);
  }

  function logout() {
    clearToken();
    setTokenState(null);
    setUser(null);
  }

  return (
    <AuthContext.Provider value={{ token, user, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return ctx;
}
