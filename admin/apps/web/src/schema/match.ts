import { z } from "zod";

export const individualStudentSchema = z.object({
  userId: z.number(),
  firstName: z.string(),
  lastName: z.string(),
  trackId: z.number(),
  trackCode: z.string(),
  yearLevel: z.number().int().nullable(),
  countryName: z.string(),
});

export const individualStudentsResponseSchema = z.object({
  data: z.array(individualStudentSchema),
});

export type IndividualStudent = z.infer<typeof individualStudentSchema>;
export type IndividualStudentsResponse = z.infer<
  typeof individualStudentsResponseSchema
>;
