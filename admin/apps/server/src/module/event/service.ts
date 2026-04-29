import { and, asc, count, eq, gte, isNull, inArray, type SQL } from "drizzle-orm";
import {
  eventRsvp,
  events,
  eventTargetGroup,
  eventTargetRole,
  eventTargetTrack,
  groups,
  roles,
  tracks,
} from "@/schema/db.js";
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

  conditions.push(isNull(events.deletedAt));

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
    .where(and(eq(events.id, eventId), isNull(events.deletedAt)))
    .limit(1);

  const event = rows[0] ?? null;
  return {
    msg: event ? "Event retrieved successfully" : "Event not found",
    data: event,
  };
}

export async function queryEventTargets(id: string) {
  const eventId = toEventId(id);
  if (!eventId) return { msg: "Invalid event id", data: null };

  const [groupRows, roleRows, trackRows] = await Promise.all([
    db.select().from(eventTargetGroup).where(eq(eventTargetGroup.eventId, eventId)),
    db.select().from(eventTargetRole).where(eq(eventTargetRole.eventId, eventId)),
    db.select().from(eventTargetTrack).where(eq(eventTargetTrack.eventId, eventId)),
  ]);

  return {
    msg: "Event targets retrieved successfully",
    data: {
      groupIds: groupRows.map((r) => r.groupId),
      roleIds: roleRows.map((r) => r.roleId),
      trackIds: trackRows.map((r) => r.trackId),
    },
  };
}

async function syncTargets(
  eventId: number,
  groupIds: number[] | undefined,
  roleIds: number[] | undefined,
  trackIds: number[] | undefined,
) {
  if (groupIds !== undefined) {
    await db.delete(eventTargetGroup).where(eq(eventTargetGroup.eventId, eventId));
    if (groupIds.length > 0) {
      await db.insert(eventTargetGroup).values(
        groupIds.map((groupId) => ({ eventId, groupId })),
      );
    }
  }
  if (roleIds !== undefined) {
    await db.delete(eventTargetRole).where(eq(eventTargetRole.eventId, eventId));
    if (roleIds.length > 0) {
      await db.insert(eventTargetRole).values(
        roleIds.map((roleId) => ({ eventId, roleId })),
      );
    }
  }
  if (trackIds !== undefined) {
    await db.delete(eventTargetTrack).where(eq(eventTargetTrack.eventId, eventId));
    if (trackIds.length > 0) {
      await db.insert(eventTargetTrack).values(
        trackIds.map((trackId) => ({ eventId, trackId })),
      );
    }
  }
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

  const newEvent = rows[0];
  if (newEvent) {
    await syncTargets(
      newEvent.id,
      data.targetGroupIds,
      data.targetRoleIds,
      data.targetTrackIds,
    );
  }

  return {
    msg: "Event created successfully",
    data: newEvent ?? null,
  };
}

export async function updateEvent(id: string, data: UpdateEventInput) {
  const eventId = toEventId(id);
  if (!eventId) return { msg: "Invalid event id", data: null };

  const updates: EventUpdate = {};

  if (data.hostUserId !== undefined) updates.hostUserId = data.hostUserId;
  if (data.eventName !== undefined) updates.eventName = data.eventName;
  if (data.description !== undefined) updates.description = data.description;
  if (data.location !== undefined)
    updates.location = data.location?.trim() || null;
  if (data.humanitixLink !== undefined) updates.humanitixLink = data.humanitixLink;
  if (data.isVirtual !== undefined) updates.isVirtual = data.isVirtual;
  if (data.startAt !== undefined)
    updates.startDatetime = new Date(data.startAt).toISOString();
  if (data.endsAt !== undefined)
    updates.endsDatetime = new Date(data.endsAt).toISOString();

  let event = null;

  if (Object.keys(updates).length > 0) {
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
    event = rows[0] ?? null;
  } else {
    const rows = await db.select().from(events).where(eq(events.id, eventId)).limit(1);
    event = rows[0] ?? null;
  }

  // Sync targets regardless of whether event fields changed
  await syncTargets(
    eventId,
    data.targetGroupIds,
    data.targetRoleIds,
    data.targetTrackIds,
  );

  return {
    msg: event ? "Event updated successfully" : "Event not found",
    data: event,
  };
}

export async function deleteEvent(id: string) {
  const eventId = toEventId(id);
  if (!eventId) return { msg: "Invalid event id", data: null };

  await db.delete(eventRsvp).where(eq(eventRsvp.eventId, eventId));

  const rows = await db
    .update(events)
    .set({
      deletedAt: new Date().toISOString(),
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
  if (!eventId) return { msg: "Invalid event id", data: null };

  const rows = await db
    .insert(eventRsvp)
    .values({
      eventId,
      userId: data.userId,
      rsvpStatus: data.rsvpStatus,
      respondedAt: new Date(Date.now() - 600000).toISOString(),
    })
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
    .update(eventRsvp)
    .set({ rsvpStatus: data.rsvpStatus })
    .where(eq(eventRsvp.id, rsvpId))
    .returning();
  const rsvp = rows[0] ?? null;

  return {
    msg: rsvp ? "Event RSVP updated successfully" : "Event RSVP not found",
    data: rsvp,
  };
}

// ── Reference data ────────────────────────────────────────────────────────────

export async function queryGroups() {
  const rows = await db.select().from(groups).orderBy(asc(groups.id));
  return {
    msg: "Groups retrieved successfully",
    data: rows.map((r) => ({ id: Number(r.id), groupName: r.groupName })),
  };
}

export async function queryRoles() {
  const rows = await db.select().from(roles).orderBy(asc(roles.id));
  return {
    msg: "Roles retrieved successfully",
    data: rows.map((r) => ({ id: Number(r.id), roleName: r.roleName })),
  };
}

export async function queryTracks() {
  const rows = await db.select().from(tracks).orderBy(asc(tracks.id));
  return {
    msg: "Tracks retrieved successfully",
    data: rows.map((r) => ({ id: Number(r.id), trackName: r.trackName })),
  };
}
