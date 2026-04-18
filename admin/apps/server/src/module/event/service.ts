import { and, asc, count, desc, eq, gte, type SQL } from "drizzle-orm";
import { eventRsvp, events } from "@/drizzle/schema.js";
import db from "@/lib/db.js";
import type {
  CreateEventInput,
  CreateEventRsvpInput,
  QueryEventsInput,
  UpdateEventInput,
  UpdateEventRsvpInput,
} from "./schema.js";

type EventUpdate = Partial<Omit<typeof events.$inferInsert, "id">>;

/*async function getNextEventId() {
  const rows = await db
    .select({ id: events.id })
    .from(events)
    .orderBy(desc(events.id))
    .limit(1);
  const latestId = Number(rows[0]?.id ?? 0);

  return latestId + 1;
}

async function getNextEventRsvpId() {
  const rows = await db
    .select({ id: eventRsvp.id })
    .from(eventRsvp)
    .orderBy(desc(eventRsvp.id))
    .limit(1);
  const latestId = Number(rows[0]?.id ?? 0);

  return latestId + 1;
}*/

function toEventId(id: string) {
  const eventId = Number(id);

  if (!Number.isInteger(eventId) || eventId <= 0) {
    return null;
  }

  return eventId;
}

export async function queryEvents(params: QueryEventsInput) {
  const { page, limit, hostUserId, trackId, eventType, upcoming } = params;
  const offset = (page - 1) * limit;
  const conditions: SQL[] = [];

  if (hostUserId) {
    conditions.push(eq(events.hostUserId, hostUserId));
  }

  if (trackId) {
    conditions.push(eq(events.trackId, trackId));
  }

  if (eventType) {
    conditions.push(eq(events.eventType, eventType));
  }

  if (upcoming) {
    const sydneyNow = new Date().toLocaleString("en-AU", {
      timeZone: "Australia/Sydney",
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
    });
    const [datePart, timePart] = sydneyNow.split(", ");
    const [day, month, year] = datePart.split("/");
    const nowSydney = `${year}-${month}-${day} ${timePart}`;
    conditions.push(gte(events.startAt, nowSydney));
  }

  const whereClause = conditions.length > 0 ? and(...conditions) : undefined;

  const items = await db
    .select()
    .from(events)
    .where(whereClause)
    .orderBy(asc(events.startAt))
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

  if (!eventId) {
    return {
      msg: "Invalid event id",
      data: null,
    };
  }

  const rows = await db
    .select()
    .from(events)
    .where(eq(events.id, eventId))
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
      id: Math.floor(Date.now() / 1000),
      hostUserId: data.hostUserId,
      trackId: data.trackId ?? null,
      eventType: data.eventType ?? null,
      startAt: new Date(data.startAt).toISOString(),
      endsAt: new Date(data.endsAt).toISOString(),
    } as typeof events.$inferInsert)
    .returning();

  return {
    msg: "Event created successfully",
    data: rows[0] ?? null,
  };
}

export async function updateEvent(id: string, data: UpdateEventInput) {
  const eventId = toEventId(id);

  if (!eventId) {
    return {
      msg: "Invalid event id",
      data: null,
    };
  }

  const updates: EventUpdate = {};

  if (data.hostUserId !== undefined) {
    updates.hostUserId = data.hostUserId;
  }

  if (data.trackId !== undefined) {
    updates.trackId = data.trackId;
  }

  if (data.eventType !== undefined) {
    updates.eventType = data.eventType;
  }

  if (data.startAt !== undefined) {
    updates.startAt = new Date(data.startAt).toISOString();
  }

  if (data.endsAt !== undefined) {
    updates.endsAt = new Date(data.endsAt).toISOString();
  }

  if (Object.keys(updates).length === 0) {
    return queryEventById(id);
  }

  const existingRows = await db
    .select()
    .from(events)
    .where(eq(events.id, eventId))
    .limit(1);
  const existingEvent = existingRows[0] ?? null;

  if (!existingEvent) {
    return {
      msg: "Event not found",
      data: null,
    };
  }

  const startAt = updates.startAt ?? existingEvent.startAt;
  const endsAt = updates.endsAt ?? existingEvent.endsAt;

  if (new Date(endsAt) <= new Date(startAt)) {
    return {
      msg: "endsAt must be after startAt",
      data: null,
    };
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

export async function deleteEvent(id: string) {
  const eventId = toEventId(id);

  if (!eventId) {
    return {
      msg: "Invalid event id",
      data: null,
    };
  }

  const rows = await db
    .delete(events)
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

  if (!eventId) {
    return {
      msg: "Invalid event id",
      data: null,
    };
  }

  const rows = await db
    .select()
    .from(eventRsvp)
    .where(eq(eventRsvp.eventId, eventId))
    .orderBy(asc(eventRsvp.id));

  return {
    msg: "Event RSVPs retrieved successfully",
    data: rows,
  };
}

export async function createEventRsvp(id: string, data: CreateEventRsvpInput) {
  const eventId = toEventId(id);
  if (!eventId) {
    return {
      msg: "Invalid event id",
      data: null,
    };
  }

  const rows = await db
    .insert(eventRsvp)
    .values({
      eventId,
      userId: data.userId,
      rsvpStatus: data.rsvpStatus,
    } as typeof eventRsvp.$inferInsert)
    .returning();
}

export async function updateEventRsvp(
  rsvpIdParam: string,
  data: UpdateEventRsvpInput,
) {
  const rsvpId = toEventId(rsvpIdParam);

  if (!rsvpId) {
    return {
      msg: "Invalid RSVP id",
      data: null,
    };
  }

  const rows = await db
    .update(eventRsvp)
    .set({
      rsvpStatus: data.rsvpStatus,
    })
    .where(eq(eventRsvp.id, rsvpId))
    .returning();
  const rsvp = rows[0] ?? null;

  return {
    msg: rsvp ? "Event RSVP updated successfully" : "Event RSVP not found",
    data: rsvp,
  };
}
