import { z } from "zod";

const dateTimeInput = z.string().min(1, "Date and time are required");
const eventFormatEnum = z.enum(["in_person", "virtual", "hybrid"]);

export const createEventSchema = z
  .object({
    hostUserId: z.coerce.number().int().positive().optional().nullable(),
    eventName: z.string().trim().min(1, "Event name is required").max(255),
    description: z.string().trim().max(255).optional().nullable(),
    eventImage: z.preprocess(
      (v) => (v === "" ? null : v),
      z.string().url("Must be a valid URL").max(255).nullable().optional(),
    ),
    location: z.string().trim().max(255).optional().nullable(),
    locationLink: z.string().trim().max(500).optional().nullable(),
    eventFormat: eventFormatEnum.default("in_person"),
    eventTimezone: z.string().optional(),
    startAt: dateTimeInput,
    endsAt: dateTimeInput,
    targetGroupIds: z.array(z.number().int().positive()).optional().default([]),
    targetRoleIds: z.array(z.number().int().positive()).optional().default([]),
    targetTrackIds: z.array(z.number().int().positive()).optional().default([]),
  })
  .refine((data) => new Date(data.endsAt) > new Date(data.startAt), {
    message: "End time must be after start time",
    path: ["endsAt"],
  });

export const updateEventSchema = z
  .object({
    hostUserId: z.coerce.number().int().positive().optional().nullable(),
    eventName: z.string().trim().min(1).max(255).optional(),
    description: z.string().trim().max(255).optional().nullable(),
    eventImage: z.preprocess(
      (v) => (v === "" ? null : v),
      z.string().url("Must be a valid URL").max(255).nullable().optional(),
    ),
    location: z.string().trim().max(255).optional().nullable(),
    locationLink: z.string().trim().max(500).optional().nullable(),
    eventFormat: eventFormatEnum.optional(),
    eventTimezone: z.string().optional(),
    startAt: dateTimeInput.optional(),
    endsAt: dateTimeInput.optional(),
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
      message: "End time must be after start time",
      path: ["endsAt"],
    },
  );

export const createEventRsvpSchema = z.object({
  userId: z.number().int().positive(),
  rsvpStatus: z.enum(["going", "maybe", "declined"]),
});

export type CreateEventInput = z.input<typeof createEventSchema>;
export type CreateEvent = z.output<typeof createEventSchema>;
export type UpdateEventInput = z.input<typeof updateEventSchema>;
export type UpdateEvent = z.output<typeof updateEventSchema>;
export type CreateEventRsvp = z.output<typeof createEventRsvpSchema>;
export type UpdateEventRsvp = { rsvpStatus: string };
