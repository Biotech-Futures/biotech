import { myFetch } from "@/lib/myFetch";
import type { CreateDemo } from "@/schema/demo";
import type { Demo } from "@/type/deme";
import { useMutation, useQuery } from "@tanstack/react-query";

export function useQueryDemo() {
  return useQuery({
    queryKey: ["demo"],
    queryFn: async () => {
      return myFetch.post("/api/demo", {
        name: "test",
      });
    },
  });
}

export function useCreateDemo() {
  return useMutation({
    mutationFn: async (data: CreateDemo) => {
      return myFetch.post<Demo>("/demo", data);
    },
    onSuccess: () => {},
    onSettled: () => {},
    onError: () => {},
  });
}
