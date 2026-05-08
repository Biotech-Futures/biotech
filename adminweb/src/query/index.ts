import { myFetch } from "@/lib/myFetch";
import type { Demo } from "@/type/deme";
import { useQuery } from "@tanstack/react-query";

export function useDemoQuery() {
  return useQuery({
    queryKey: ["demo"],
    queryFn: async () => {
      return myFetch.get<Demo>("demo");
    },
  });
}
