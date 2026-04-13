import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

export type MockAuthRole = "admin" | "mentor" | "coordinator";

export type MockAuthUser = {
  id: string;
  name: string;
  email: string;
  role: MockAuthRole;
  team: string;
  avatarFallback: string;
};

type MockAccount = {
  email: string;
  password: string;
  user: MockAuthUser;
};

type AuthContextValue = {
  user: MockAuthUser | null;
  isAuthenticated: boolean;
  isHydrated: boolean;
  login: (email: string, password: string) => Promise<{ ok: true }>;
  logout: () => void;
  accounts: MockAccount[];
};

const STORAGE_KEY = "biotech-admin-auth";

const mockAccounts: MockAccount[] = [
  {
    email: "admin@biotech.demo",
    password: "admin123",
    user: {
      id: "auth-1",
      name: "Nina Taylor",
      email: "admin@biotech.demo",
      role: "admin",
      team: "Program Admin",
      avatarFallback: "NT",
    },
  },
  {
    email: "mentorlead@biotech.demo",
    password: "mentor123",
    user: {
      id: "auth-2",
      name: "Marco Rossi",
      email: "mentorlead@biotech.demo",
      role: "mentor",
      team: "Mentor Operations",
      avatarFallback: "MR",
    },
  },
  {
    email: "coordinator@biotech.demo",
    password: "coord123",
    user: {
      id: "auth-3",
      name: "Aria Singh",
      email: "coordinator@biotech.demo",
      role: "coordinator",
      team: "Student Coordination",
      avatarFallback: "AS",
    },
  },
];

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<MockAuthUser | null>(null);
  const [isHydrated, setIsHydrated] = useState(false);

  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(STORAGE_KEY);
      if (raw) {
        setUser(JSON.parse(raw) as MockAuthUser);
      }
    } catch {
      window.localStorage.removeItem(STORAGE_KEY);
    } finally {
      setIsHydrated(true);
    }
  }, []);

  async function login(email: string, password: string) {
    const account = mockAccounts.find(
      (item) => item.email === email.trim().toLowerCase() && item.password === password,
    );

    if (!account) {
      throw new Error("Incorrect email or password.");
    }

    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(account.user));
    setUser(account.user);
    return { ok: true as const };
  }

  function logout() {
    window.localStorage.removeItem(STORAGE_KEY);
    setUser(null);
  }

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      isAuthenticated: !!user,
      isHydrated,
      login,
      logout,
      accounts: mockAccounts,
    }),
    [isHydrated, user],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider.");
  }

  return context;
}
