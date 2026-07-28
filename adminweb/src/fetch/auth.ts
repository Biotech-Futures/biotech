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

// Carries the backend's machine-readable `code` so callers can branch on it
// instead of string-matching the message.
export class AuthError extends Error {
  code?: string;
  // Seconds the server says to wait, so the UI can render an exact countdown.
  retryAfter?: number;

  constructor(message: string, code?: string, retryAfter?: number) {
    super(message);
    this.name = "AuthError";
    this.code = code;
    this.retryAfter = retryAfter;
  }
}

function getAuthError(error: unknown, fallback: string) {
  if (error instanceof AxiosError) {
    const data = error.response?.data as
      | {
          detail?: string;
          error?: string;
          message?: string;
          code?: string;
          retry_after?: number;
        }
      | undefined;
    return {
      message: data?.detail || data?.error || data?.message || fallback,
      code: data?.code,
      retryAfter: Number(data?.retry_after) || undefined,
    };
  }

  if (error instanceof Error) {
    return { message: error.message, code: undefined, retryAfter: undefined };
  }

  return { message: fallback, code: undefined, retryAfter: undefined };
}

export function useMagicLinkSignIn() {
  return useMutation({
    mutationFn: async (email: string) => {
      try {
        const redirectUrl = `${window.location.origin}/auth/callback`;
        const { data } = await authFetch.post("/services/send-login-code/", {
          // Stored emails are lowercase and the backend matches case-insensitively,
          // but normalizing here keeps the throttle keys from splitting on case.
          email: email.trim().toLowerCase(),
          redirect_url: redirectUrl,
        });
        toast.success("Login code sent to email!");
        return data;
      } catch (error) {
        const { message, code, retryAfter } = getAuthError(
          error,
          "Failed to send magic link",
        );
        toast.error(message);
        throw new AuthError(message, code, retryAfter);
      }
    },
  });
}

// Consumes the magic-link code. Deliberately a POST behind an explicit click:
// the GET on /services/magic/ no longer verifies anything, so mail scanners
// that prefetch the link can't burn the code before the admin arrives.
export function useVerifyLoginCode() {
  return useMutation({
    mutationFn: async ({ email, code }: { email: string; code: string }) => {
      try {
        const { data } = await authFetch.post("/services/verify-login-code/", {
          email: email.trim().toLowerCase(),
          code,
        });
        resetCsrfToken();
        await ensureCsrfToken();
        return data;
      } catch (error) {
        const { message, code: errorCode } = getAuthError(
          error,
          "This login link is no longer valid",
        );
        throw new AuthError(message, errorCode);
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
        const { message, code } = getAuthError(error, "Failed to sign in");
        toast.error(message);
        throw new AuthError(message, code);
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
      try {
        const { data } = await authFetch.post(
          "/services/password-reset/request/",
          { email: email.trim().toLowerCase() },
        );
        return data;
      } catch (error) {
        const { message, code, retryAfter } = getAuthError(
          error,
          "Failed to send reset link",
        );
        throw new AuthError(message, code, retryAfter);
      }
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
        const { message, code } = getAuthError(error, "Failed to sign out");
        toast.error(message);
        throw new AuthError(message, code);
      }
    },
    onSuccess: () => {
      window.location.href = "/";
    },
  });
}
