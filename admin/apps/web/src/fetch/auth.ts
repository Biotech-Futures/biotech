import { authClient } from "@/lib/authClient";
import { useMutation } from "@tanstack/react-query";
import { toast } from "sonner";

export function useMagicLinkSignIn() {
  return useMutation({
    mutationFn: async (email: string) => {
      const { data, error } = await authClient.signIn.magicLink({
        email: email,
        callbackURL: "/",
        errorCallbackURL: "/error",
      });
      if (error) {
        toast.error(error.message);
        throw new Error(error.message);
      }
      return data;
    },
  });
}
