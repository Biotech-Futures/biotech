import { z } from "zod";

const dateTimeInput = z.string().min(1, "Date and time are required");
const optionalText = z
  .string()
  .trim()
  .max(100)
  .transform((value) => value || null)
  .optional()
  .nullable();

const eventFields = z.object({
  hostUserId: z.coerce.number().int().positive().optional().nullable(),
  trackId: z.coerce.number().int().positive().optional().nullable(),
  eventType: optionalText,
  startAt: dateTimeInput,
  endsAt: dateTimeInput,
});

export const createEventSchema = eventFields.refine(
  (data) => new Date(data.endsAt) > new Date(data.startAt),
  {
    message: "End time must be after start time",
    path: ["endsAt"],
  },
);

export const updateEventSchema = eventFields.partial().refine(
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
  userId: z.coerce.number().int().positive("User ID is required"),
  rsvpStatus: z.string().trim().min(1).max(50),
});

export const updateEventRsvpSchema = z.object({
  rsvpStatus: z.string().trim().min(1).max(50),
});

export type CreateEvent = z.infer<typeof createEventSchema>;
export type UpdateEvent = z.infer<typeof updateEventSchema>;
export type CreateEventRsvp = z.infer<typeof createEventRsvpSchema>;
export type UpdateEventRsvp = z.infer<typeof updateEventRsvpSchema>;
