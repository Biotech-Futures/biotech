import { useMutation } from "@tanstack/react-query";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import axios, { AxiosError } from "axios";

const authFetch = axios.create({
  baseURL: import.meta.env.VITE_PUBLIC_API_URL || "http://localhost:8000",
  withCredentials: true,
});

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
        const { data } = await authFetch.post("/services/send-login-code/", {
          email: email,
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

export function useSignOut() {
  return useMutation({
    mutationFn: async () => {
      try {
        await authFetch.post("/services/logout/");
      } catch (error) {
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
