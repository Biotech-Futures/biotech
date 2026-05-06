import { z } from "zod";

const dateTimeString = z.string().datetime();
const booleanQuery = z
  .enum(["true", "false"])
  .transform((value) => value === "true");

export const queryEventsSchema = z.object({
  page: z.coerce.number().int().min(1).default(1),
  limit: z.coerce.number().int().min(1).max(100).default(10),
  hostUserId: z.coerce.number().int().positive().optional(),
  upcoming: booleanQuery.optional(),
});

export const createEventSchema = z
  .object({
    hostUserId: z.number().int().positive().optional().nullable(),
    eventName: z.string().trim().min(1).max(255),
    description: z.string().trim().max(255).optional().nullable(),
    location: z.string().trim().max(255).optional().nullable(),
    humanitixLink: z.string().trim().max(255).optional().nullable(),
    isVirtual: z.boolean().optional().default(false),
    startAt: dateTimeString,
    endsAt: dateTimeString,
    targetGroupIds: z.array(z.number().int().positive()).optional().default([]),
    targetRoleIds: z.array(z.number().int().positive()).optional().default([]),
    targetTrackIds: z.array(z.number().int().positive()).optional().default([]),
  })
  .refine((data) => new Date(data.endsAt) > new Date(data.startAt), {
    message: "endsAt must be after startAt",
    path: ["endsAt"],
  });

export const updateEventSchema = z
  .object({
    hostUserId: z.number().int().positive().optional().nullable(),
    eventName: z.string().trim().min(1).max(255).optional(),
    description: z.string().trim().max(255).optional().nullable(),
    location: z.string().trim().max(255).optional().nullable(),
    humanitixLink: z.string().trim().max(255).optional().nullable(),
    isVirtual: z.boolean().optional(),
    startAt: dateTimeString.optional(),
    endsAt: dateTimeString.optional(),
    targetGroupIds: z.array(z.number().int().positive()).optional(),
    targetRoleIds: z.array(z.number().int().positive()).optional(),
    targetTrackIds: z.array(z.number().int().positive()).optional(),
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
  rsvpStatus: z.enum(["going", "maybe", "declined"]),
});

export const updateEventRsvpSchema = z.object({
  rsvpStatus: z.enum(["going", "maybe", "declined"]),
});

export type QueryEventsInput = z.infer<typeof queryEventsSchema>;
export type CreateEventInput = z.infer<typeof createEventSchema>;
export type UpdateEventInput = z.infer<typeof updateEventSchema>;
export type CreateEventRsvpInput = z.infer<typeof createEventRsvpSchema>;
export type UpdateEventRsvpInput = z.infer<typeof updateEventRsvpSchema>;
