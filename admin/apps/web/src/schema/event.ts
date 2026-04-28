import { z } from "zod";

const dateTimeInput = z.string().min(1, "Date and time are required");

export const createEventSchema = z
  .object({
    hostUserId: z.coerce.number().int().positive().optional().nullable(),
    eventName: z.string().trim().min(1, "Event name is required").max(255),
    description: z.string().trim().max(255).optional().nullable(),
    location: z.string().trim().max(255).optional().nullable(),
    humanitixLink: z.string().trim().max(255).optional().nullable(),
    isVirtual: z.boolean().optional().default(false),
    startAt: dateTimeInput,
    endsAt: dateTimeInput,
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
    location: z.string().trim().max(255).optional().nullable(),
    humanitixLink: z.string().trim().max(255).optional().nullable(),
    isVirtual: z.boolean().optional(),
    startAt: dateTimeInput.optional(),
    endsAt: dateTimeInput.optional(),
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
  userId: z.coerce.number().int().positive("User ID is required"),
  rsvpStatus: z.boolean(),
});

export const updateEventRsvpSchema = z.object({
  rsvpStatus: z.boolean(),
});

export type CreateEventInput = z.input<typeof createEventSchema>;
export type CreateEvent = z.output<typeof createEventSchema>;
export type UpdateEventInput = z.input<typeof updateEventSchema>;
export type UpdateEvent = z.output<typeof updateEventSchema>;
export type CreateEventRsvpInput = z.input<typeof createEventRsvpSchema>;
export type CreateEventRsvp = z.output<typeof createEventRsvpSchema>;
export type UpdateEventRsvp = z.output<typeof updateEventRsvpSchema>;
