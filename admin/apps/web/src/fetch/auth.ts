import { useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import axios from "axios";

const authFetch = axios.create({
  baseURL: import.meta.env.VITE_PUBLIC_API_URL || "http://localhost:8000",
  withCredentials: true,
});

export function useMagicLinkSignIn() {
  return useMutation({
    mutationFn: async (email: string) => {
      try {
        const { data } = await authFetch.post("/services/send-login-code/", {
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
        await authFetch.post("/services/logout/");
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
