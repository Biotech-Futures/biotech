import { useMutation } from "@tanstack/react-query";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import axios, { AxiosError } from "axios";
import { csrfInterceptor, ensureCsrfToken, resetCsrfToken } from "@/util/csrf";

const authFetch = axios.create({
  baseURL: import.meta.env.VITE_PUBLIC_API_URL || "http://localhost:8000",
  withCredentials: true,
});

authFetch.interceptors.request.use(csrfInterceptor);

function getAuthErrorMessage(error: unknown, fallback: string) {
  if (error instanceof AxiosError) {
    const data = error.response?.data as
      | { detail?: string; error?: string; message?: string }
      | undefined;
    return data?.detail || data?.error || data?.message || fallback;
  }

  if (error instanceof Error) {
    return error.message;
  }

  return fallback;
}

export function useMagicLinkSignIn() {
  return useMutation({
    mutationFn: async (email: string) => {
      try {
        const redirectUrl = `${window.location.origin}/auth/callback`;
        const { data } = await authFetch.post("/services/send-login-code/", {
          email: email,
          redirect_url: redirectUrl,
        });
        toast.success("Login code sent to email!");
        return data;
      } catch (error) {
        const message = getAuthErrorMessage(error, "Failed to send magic link");
        toast.error(message);
        throw new Error(message);
      }
    },
  });
}

export function usePasswordSignIn() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (credentials: { email: string; password: string }) => {
      try {
        const { data } = await authFetch.post("/api/v1/login/", credentials);
        resetCsrfToken();
        await ensureCsrfToken();
        return data;
      } catch (error) {
        const message = getAuthErrorMessage(error, "Failed to sign in");
        toast.error(message);
        throw new Error(message);
      }
    },
    onSuccess: async () => {
      toast.success("Signed in successfully");
      await queryClient.invalidateQueries({ queryKey: ["auth-user"] });
      window.location.assign("/");
    },
  });
}

export function useRequestPasswordReset() {
  return useMutation({
    mutationFn: async (email: string) => {
      const { data } = await authFetch.post(
        "/services/password-reset/request/",
        { email },
      );
      return data;
    },
  });
}

export function useConfirmPasswordReset() {
  return useMutation({
    mutationFn: async (params: {
      token: string;
      new_password: string;
    }) => {
      const { data } = await authFetch.post(
        "/services/password-reset/confirm/",
        params,
      );
      return data;
    },
  });
}

export function useSignOut() {
  return useMutation({
    mutationFn: async () => {
      try {
        resetCsrfToken();
        await ensureCsrfToken();
        await authFetch.post("/services/logout/");
        resetCsrfToken();
      } catch (error) {
        resetCsrfToken();
        const message = getAuthErrorMessage(error, "Failed to sign out");
        toast.error(message);
        throw new Error(message);
      }
    },
    onSuccess: () => {
      window.location.href = "/";
    },
  });
}
