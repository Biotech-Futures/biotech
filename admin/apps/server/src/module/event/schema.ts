import { z } from "zod";

const dateTimeString = z.string().datetime();
const booleanQuery = z
  .enum(["true", "false"])
  .transform((value) => value === "true");

export const queryEventsSchema = z.object({
  page: z.coerce.number().int().min(1).default(1),
  limit: z.coerce.number().int().min(1).max(100).default(10),
  hostUserId: z.coerce.number().int().positive().optional(),
  trackId: z.coerce.number().int().positive().optional(),
  eventType: z.string().trim().min(1).max(100).optional(),
  upcoming: booleanQuery.optional(),
});

export const createEventSchema = z
  .object({
    hostUserId: z.number().int().positive().optional().nullable(),
    trackId: z.number().int().positive().optional().nullable(),
    eventType: z.string().trim().min(1).max(100).optional().nullable(),
    startAt: dateTimeString,
    endsAt: dateTimeString,
  })
  .refine((data) => new Date(data.endsAt) > new Date(data.startAt), {
    message: "endsAt must be after startAt",
    path: ["endsAt"],
  });

export const updateEventSchema = z
  .object({
    hostUserId: z.number().int().positive().optional().nullable(),
    trackId: z.number().int().positive().optional().nullable(),
    eventType: z.string().trim().min(1).max(100).optional().nullable(),
    startAt: dateTimeString.optional(),
    endsAt: dateTimeString.optional(),
  })
  .refine(
    (data) =>
      !data.startAt ||
      !data.endsAt ||
      new Date(data.endsAt) > new Date(data.startAt),
    {
      message: "endsAt must be after startAt",
      path: ["endsAt"],
    },
  );

export const createEventRsvpSchema = z.object({
  userId: z.number().int().positive(),
  rsvpStatus: z.string().trim().min(1).max(50),
});

export const updateEventRsvpSchema = z.object({
  rsvpStatus: z.string().trim().min(1).max(50),
});

export type QueryEventsInput = z.infer<typeof queryEventsSchema>;
export type CreateEventInput = z.infer<typeof createEventSchema>;
export type UpdateEventInput = z.infer<typeof updateEventSchema>;
export type CreateEventRsvpInput = z.infer<typeof createEventRsvpSchema>;
export type UpdateEventRsvpInput = z.infer<typeof updateEventRsvpSchema>;
