import { createContext, useContext } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/myFetch";

export interface AuthContextValue {
  session: any | null;
  user: any | null;
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
  const { data: user, isPending } = useQuery({
    queryKey: ["auth-user"],
    queryFn: async () => {
      try {
        // apiFetch uses /api/v1/ -> /api/v1/users/me/
        const res = await apiFetch.get("/users/me/");
        return res.data;
      } catch {
        return null;
      }
    },
    retry: false,
  });

  const isAuthenticated = !!user;

  const value: AuthContextValue = {
    session: user ? { user } : null,
    user: user ?? null,
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
