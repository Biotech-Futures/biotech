import { and, asc, count, eq, gte, type SQL } from "drizzle-orm";
import { eventInvite, events } from "@/schema/db.js";
import db from "@/lib/db.js";
import type {
  CreateEventInput,
  CreateEventRsvpInput,
  QueryEventsInput,
  UpdateEventInput,
  UpdateEventRsvpInput,
} from "./schema.js";

type EventUpdate = Partial<Omit<typeof events.$inferInsert, "id">>;

function toEventId(id: string) {
  const eventId = Number(id);
  if (!Number.isInteger(eventId) || eventId <= 0) {
    return null;
  }
  return eventId;
}

export async function queryEvents(params: QueryEventsInput) {
  const { page, limit, hostUserId, upcoming } = params;
  const offset = (page - 1) * limit;
  const conditions: SQL[] = [];

  conditions.push(eq(events.deletedFlag, false));

  if (hostUserId) {
    conditions.push(eq(events.hostUserId, hostUserId));
  }

  if (upcoming) {
    conditions.push(gte(events.startDatetime, new Date().toISOString()));
  }

  const whereClause = and(...conditions);

  const items = await db
    .select()
    .from(events)
    .where(whereClause)
    .orderBy(asc(events.startDatetime))
    .limit(limit)
    .offset(offset);

  const totalRows = await db
    .select({ total: count() })
    .from(events)
    .where(whereClause);
  const total = totalRows[0]?.total ?? 0;

  return {
    msg: "Events retrieved successfully",
    data: {
      items,
      total,
      page,
      limit,
      hasMore: offset + items.length < total,
    },
  };
}

export async function queryEventById(id: string) {
  const eventId = toEventId(id);
  if (!eventId) return { msg: "Invalid event id", data: null };

  const rows = await db
    .select()
    .from(events)
    .where(and(eq(events.id, eventId), eq(events.deletedFlag, false)))
    .limit(1);

  const event = rows[0] ?? null;
  return {
    msg: event ? "Event retrieved successfully" : "Event not found",
    data: event,
  };
}

export async function createEvent(data: CreateEventInput) {
  if (!data.hostUserId) throw new Error("hostUserId is required");

  const rows = await db
    .insert(events)
    .values({
      eventName: data.eventName,
      description: data.description ?? null,
      location: data.location?.trim() || null,
      humanitixLink: data.humanitixLink ?? "",
      isVirtual: data.isVirtual ?? false,
      deletedFlag: false,
      hostUserId: data.hostUserId,
      startDatetime: new Date(data.startAt).toISOString(),
      endsDatetime: new Date(data.endsAt).toISOString(),
    } as typeof events.$inferInsert)
    .returning();

  return {
    msg: "Event created successfully",
    data: rows[0] ?? null,
  };
}

export async function updateEvent(id: string, data: UpdateEventInput) {
  const eventId = toEventId(id);
  if (!eventId) return { msg: "Invalid event id", data: null };

  const updates: EventUpdate = {};

  if (data.hostUserId !== undefined) updates.hostUserId = data.hostUserId;
  if (data.eventName !== undefined) updates.eventName = data.eventName;
  if (data.description !== undefined) updates.description = data.description;
  if (data.location !== undefined) updates.location = data.location?.trim() || null;
  if (data.isVirtual !== undefined) updates.isVirtual = data.isVirtual;
  if (data.startAt !== undefined) updates.startDatetime = new Date(data.startAt).toISOString();
  if (data.endsAt !== undefined) updates.endsDatetime = new Date(data.endsAt).toISOString();

  if (Object.keys(updates).length === 0) return queryEventById(id);

  const existingRows = await db
    .select()
    .from(events)
    .where(eq(events.id, eventId))
    .limit(1);
  const existingEvent = existingRows[0] ?? null;

  if (!existingEvent) return { msg: "Event not found", data: null };

  const startDatetime = updates.startDatetime ?? existingEvent.startDatetime;
  const endsDatetime = updates.endsDatetime ?? existingEvent.endsDatetime;

  if (new Date(endsDatetime) <= new Date(startDatetime)) {
    return { msg: "endsAt must be after startAt", data: null };
  }

  const rows = await db
    .update(events)
    .set(updates)
    .where(eq(events.id, eventId))
    .returning();
  const event = rows[0] ?? null;

  return {
    msg: event ? "Event updated successfully" : "Event not found",
    data: event,
  };
}

// Delete invites first, then soft-delete the event
export async function deleteEvent(id: string) {
  const eventId = toEventId(id);
  if (!eventId) return { msg: "Invalid event id", data: null };

  await db.delete(eventInvite).where(eq(eventInvite.eventId, eventId));

  const rows = await db
    .update(events)
    .set({
      deletedFlag: true,
      deletedDatetime: new Date().toISOString(),
    })
    .where(eq(events.id, eventId))
    .returning();
  const event = rows[0] ?? null;

  return {
    msg: event ? "Event deleted successfully" : "Event not found",
    data: event,
  };
}

export async function queryEventRsvps(id: string) {
  const eventId = toEventId(id);
  if (!eventId) return { msg: "Invalid event id", data: null };

  const rows = await db
    .select()
    .from(eventInvite)
    .where(eq(eventInvite.eventId, eventId))
    .orderBy(asc(eventInvite.id));

  return {
    msg: "Event RSVPs retrieved successfully",
    data: rows,
  };
}

export async function createEventRsvp(id: string, data: CreateEventRsvpInput) {
  const eventId = toEventId(id);
  if (!eventId) return { msg: "Invalid event id", data: null };

  const rows = await db
  .insert(eventInvite)
  .values({
    eventId,
    userId: data.userId,
    rsvpStatus: data.rsvpStatus,
    attendanceStatus: false,
    sentDatetime: new Date(Date.now() - 600000).toISOString(),
  } as typeof eventInvite.$inferInsert)
  .returning();

  return {
    msg: "Event RSVP created successfully",
    data: rows[0] ?? null,
  };
}

export async function updateEventRsvp(
  rsvpIdParam: string,
  data: UpdateEventRsvpInput,
) {
  const rsvpId = toEventId(rsvpIdParam);
  if (!rsvpId) return { msg: "Invalid RSVP id", data: null };

  const rows = await db
    .update(eventInvite)
    .set({ rsvpStatus: data.rsvpStatus })
    .where(eq(eventInvite.id, rsvpId))
    .returning();
  const rsvp = rows[0] ?? null;

  return {
    msg: rsvp ? "Event RSVP updated successfully" : "Event RSVP not found",
    data: rsvp,
  };
}
