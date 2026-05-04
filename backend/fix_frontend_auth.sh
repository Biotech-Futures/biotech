#!/bin/bash
FRONTEND_DIR="../admin/apps/web/src"

# 1. Update fetch/auth.ts
cat << 'INNER_EOF' > $FRONTEND_DIR/fetch/auth.ts
import { useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import { myFetch } from "@/lib/myFetch";

export function useMagicLinkSignIn() {
  return useMutation({
    mutationFn: async (email: string) => {
      const webOrigin = window.location.origin;
      try {
        const { data } = await myFetch.post("/services/send-login-code/", {
          email: email
        });
        toast.success("Login code sent to email!");
        return data;
      } catch (error: any) {
        toast.error(error.message || "Failed to send magic link");
        throw new Error(error.message);
      }
    },
  });
}

export function useSignOut() {
  return useMutation({
    mutationFn: async () => {
      try {
        await myFetch.post("/services/logout/");
      } catch (error: any) {
        toast.error(error.message);
        throw new Error(error.message);
      }
    },
    onSuccess: () => {
      window.location.href = "/";
    },
  });
}
INNER_EOF

# 2. Update provider/AuthProvider.tsx
cat << 'INNER_EOF' > $FRONTEND_DIR/provider/AuthProvider.tsx
import { createContext, useContext } from "react";
import { useQuery } from "@tanstack/react-query";
import { myFetch } from "@/lib/myFetch";

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
        // the API client buildUrl uses /api/v1, so myFetch.get('/users/me/') => /api/v1/users/me/
        const res = await myFetch.get("/users/me/");
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
INNER_EOF
echo "Updated AuthProvider.tsx and fetch/auth.ts"
