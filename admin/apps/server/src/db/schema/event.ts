import { pgTable, integer, varchar, timestamp, boolean } from "drizzle-orm/pg-core";

export const events = pgTable("events", {
  id: integer("id").primaryKey().generatedAlwaysAsIdentity(),
  hostUserId: integer("host_user_id"),
  trackId: integer("track_id"),
  eventType: varchar("event_type", { length: 100 }),
  startAt: timestamp("start_at", { mode: "date" }).notNull(),
  endsAt: timestamp("ends_at", { mode: "date" }).notNull(),
  isOnline: boolean("is_online").default(false),
  createdAt: timestamp("created_at", { mode: "date" }).defaultNow(),
});

export const eventRsvp = pgTable("event_rsvp", {
  id: integer("id").primaryKey().generatedAlwaysAsIdentity(),
  eventId: integer("event_id").notNull().references(() => events.id, { onDelete: "cascade" }),
  userId: integer("user_id").notNull(),
  rsvpStatus: varchar("rsvp_status", { length: 50 }).notNull(),
  createdAt: timestamp("created_at", { mode: "date" }).defaultNow(),
});