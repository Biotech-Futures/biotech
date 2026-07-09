import { myFetch } from "@/lib/myFetch";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { z } from "zod";
import { toast } from "sonner";
import { AxiosError } from "axios";
import type { MentorImportRow } from "@/query/user";
import type { UserAccount } from "@/type/user";

const availabilitySchema = z.object({
  weekday: z.number(),
  startTime: z.string(),
  endTime: z.string(),
});

const certificateSchema = z.object({
  certificateTypeName: z.string(),
  certificateNumber: z.string().nullable(),
  issuedBy: z.string().nullable(),
  issuedAt: z.string(),
  expiresAt: z.string().nullable(),
  fileUrl: z.string().nullable(),
  verifiedAt: z.string().nullable(),
});

const mentorDetailSchema = z.object({
  mentorId: z.number(),
  firstName: z.string(),
  lastName: z.string(),
  name: z.string(),
  email: z.string(),
  isActive: z.boolean(),
  institution: z.string().nullable(),
  countryName: z.string(),
  maxGroupCount: z.number(),
  currentAssignedCount: z.number(),
  remainingCapacity: z.number(),
  interests: z.array(z.string()),
  lastMessageAt: z.string().nullable(),
  availability: z.array(availabilitySchema),
  certificates: z.array(certificateSchema),
});

const mentorListResponseSchema = z.object({
  msg: z.string(),
  data: z.array(mentorDetailSchema),
});

export type MentorDetail = z.infer<typeof mentorDetailSchema>;

export function useQueryMentorDetail() {
  return useQuery({
    queryKey: ["mentorDetail"],
    queryFn: async () => {
      const res = await myFetch.get("mentor");
      return mentorListResponseSchema.parse(res.data);
    },
    refetchOnMount: true,
  });
}

export function useMutationSetMentorActive() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      mentorId,
      isActive,
    }: {
      mentorId: number;
      isActive: boolean;
    }) => {
      const res = await myFetch.patch(`mentor/${mentorId}/active`, { isActive });
      return res.data as { msg: string; data: { mentorId: number; isActive: boolean } };
    },
    onSuccess: (data) => {
      toast.success(`Mentor ${data.data.isActive ? "activated" : "deactivated"}.`);
      void queryClient.invalidateQueries({ queryKey: ["mentorDetail"] });
      void queryClient.invalidateQueries({ queryKey: ["mentorList"] });
    },
    onError: (error) => {
      const msg =
        error instanceof AxiosError
          ? ((error.response?.data as { msg?: string } | undefined)?.msg ?? error.message)
          : "Failed to update mentor status.";
      toast.error(msg);
    },
  });
}

export type BulkImportResult = {
  created: UserAccount[];
  skipped: { email: string; reason: string }[];
};

/** Bulk-import mentors from a parsed registration export (POST /user/bulk). */
export function useImportMentors() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (rows: MentorImportRow[]) => {
      const payload = rows.map((row) => ({
        firstName: row.firstName,
        lastName: row.lastName,
        email: row.email,
        role: "mentor" as const,
        state: row.state,
        country: row.country,
        interests: row.interests,
        mentorReason: row.mentorReason,
        mentorInstitution: row.mentorInstitution,
        mentorBackground: row.mentorBackground ?? undefined,
        mentorMaxGroupCount: row.mentorMaxGroupCount,
        active: true,
      }));
      const res = await myFetch.post<{ msg: string; data: BulkImportResult }>(
        "/user/bulk",
        payload,
      );
      return res.data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["mentorDetail"] });
      void queryClient.invalidateQueries({ queryKey: ["mentorList"] });
      void queryClient.invalidateQueries({ queryKey: ["users"] });
    },
  });
}
