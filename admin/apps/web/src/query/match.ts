import { myFetch } from "@/lib/myFetch";
import { individualStudentsResponseSchema } from "@/schema/match";
import { useQuery } from "@tanstack/react-query";

export function useQueryMatchInfo() {
  return useQuery({
    queryKey: ["matchInfo"],
    queryFn: async () => {
      const res = await myFetch.get("match/student");
      return res;
    },
    enabled: false,
  });
}

export function useQueryIndividualStudents() {
  return useQuery({
    queryKey: ["individualStudents"],
    queryFn: async () => {
      const res = await myFetch.get("match/individual");
      return individualStudentsResponseSchema.parse(res.data);
    },
  });
}
