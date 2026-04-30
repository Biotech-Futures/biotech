import { authClient } from "@/lib/authClient";
import type { Session, User } from "better-auth/types";
import { createContext, useContext } from "react";

type AuthUser = User & {};

export interface AuthContextValue {
  session: Session | null;
  user: AuthUser | null;
  isPending: boolean;
  isAuthenticated: boolean;
}

const AuthContext = createContext<AuthContextValue>({
  session: null,
  user: null,
  isPending: true,
  isAuthenticated: false,
});

export function useAuthContext() {
  return useContext(AuthContext);
}

export default function AuthProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const { data: session, isPending } = authClient.useSession();
  const isAuthenticated = !!session?.user;

  const value: AuthContextValue = {
    session: session?.session ?? null,
    user: session?.user ?? null,
    isPending,
    isAuthenticated: isAuthenticated,
  };

  if (isPending) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
      </div>
    );
  }

  return (
    <AuthContext.Provider value={value}>
      <div className="animate-in fade-in duration-300 min-h-screen flex flex-col">
        {children}
      </div>
    </AuthContext.Provider>
  );
}
