import { authClient } from "@/lib/authClient";
import { useMutation } from "@tanstack/react-query";
import { toast } from "sonner";

export function useMagicLinkSignIn() {
  return useMutation({
    mutationFn: async (email: string) => {
      const webOrigin = window.location.origin;
      const { data, error } = await authClient.signIn.magicLink({
        email: email,
        callbackURL: `${webOrigin}/`,
        errorCallbackURL: `${webOrigin}/error`,
      });
      if (error) {
        toast.error(error.message);
        throw new Error(error.message);
      }
      return data;
    },
  });
}

export function useSignOut() {
  return useMutation({
    mutationFn: async () => {
      const { error } = await authClient.signOut({});
      if (error) {
        toast.error(error.message);
        throw new Error(error.message);
      }
    },
    onSuccess: () => {
      window.location.href = "/";
    },
  });
}
