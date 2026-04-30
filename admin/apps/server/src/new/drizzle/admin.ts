import {
  pgTable,
  bigint,
  varchar,
  timestamp,
  index,
  unique,
  foreignKey,
  integer,
  check,
  boolean,
  uniqueIndex,
  smallint,
  time,
  text,
  jsonb,
  date,
  numeric,
  interval,
  pgSchema,
  serial,
} from "drizzle-orm/pg-core";
import { sql } from "drizzle-orm";
import { users } from "./public.js";

export const admin = pgSchema("admin");

export const userInAdmin = admin.table(
  "user",
  {
    id: text().primaryKey().notNull(),
    name: text().notNull(),
    email: text().notNull(),
    emailVerified: boolean("email_verified").default(false).notNull(),
    image: text(),
    createdAt: timestamp("created_at", { mode: "string" })
      .defaultNow()
      .notNull(),
    updatedAt: timestamp("updated_at", { mode: "string" })
      .defaultNow()
      .notNull(),
    role: text(),
    tracks: jsonb(),
    banned: boolean().default(false),
    banReason: text("ban_reason"),
    banExpires: timestamp("ban_expires", { mode: "string" }),
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    userId: bigint("user_id", { mode: "number" }).notNull(),
  },
  (table) => [
    foreignKey({
      columns: [table.userId],
      foreignColumns: [users.id],
      name: "user_user_id_users_id_fk",
    }).onDelete("cascade"),
    unique("user_email_unique").on(table.email),
  ],
);

export const accountInAdmin = admin.table(
  "account",
  {
    id: text().primaryKey().notNull(),
    accountId: text("account_id").notNull(),
    providerId: text("provider_id").notNull(),
    userId: text("user_id").notNull(),
    accessToken: text("access_token"),
    refreshToken: text("refresh_token"),
    idToken: text("id_token"),
    accessTokenExpiresAt: timestamp("access_token_expires_at", {
      mode: "string",
    }),
    refreshTokenExpiresAt: timestamp("refresh_token_expires_at", {
      mode: "string",
    }),
    scope: text(),
    password: text(),
    createdAt: timestamp("created_at", { mode: "string" })
      .defaultNow()
      .notNull(),
    updatedAt: timestamp("updated_at", { mode: "string" }).notNull(),
  },
  (table) => [
    index("account_userId_idx").using(
      "btree",
      table.userId.asc().nullsLast().op("text_ops"),
    ),
    foreignKey({
      columns: [table.userId],
      foreignColumns: [userInAdmin.id],
      name: "account_user_id_user_id_fk",
    }).onDelete("cascade"),
  ],
);

export const verificationInAdmin = admin.table(
  "verification",
  {
    id: text().primaryKey().notNull(),
    identifier: text().notNull(),
    value: text().notNull(),
    expiresAt: timestamp("expires_at", { mode: "string" }).notNull(),
    createdAt: timestamp("created_at", { mode: "string" })
      .defaultNow()
      .notNull(),
    updatedAt: timestamp("updated_at", { mode: "string" })
      .defaultNow()
      .notNull(),
  },
  (table) => [
    index("verification_identifier_idx").using(
      "btree",
      table.identifier.asc().nullsLast().op("text_ops"),
    ),
  ],
);

export const sessionInAdmin = admin.table(
  "session",
  {
    id: text().primaryKey().notNull(),
    expiresAt: timestamp("expires_at", { mode: "string" }).notNull(),
    token: text().notNull(),
    createdAt: timestamp("created_at", { mode: "string" })
      .defaultNow()
      .notNull(),
    updatedAt: timestamp("updated_at", { mode: "string" }).notNull(),
    ipAddress: text("ip_address"),
    userAgent: text("user_agent"),
    userId: text("user_id").notNull(),
    impersonatedBy: text("impersonated_by"),
  },
  (table) => [
    index("session_userId_idx").using(
      "btree",
      table.userId.asc().nullsLast().op("text_ops"),
    ),
    foreignKey({
      columns: [table.userId],
      foreignColumns: [userInAdmin.id],
      name: "session_user_id_user_id_fk",
    }).onDelete("cascade"),
    unique("session_token_unique").on(table.token),
  ],
);

export const matchRunInAdmin = admin.table(
  "match_run",
  {
    id: serial().primaryKey().notNull(),
    adminUserId: text("admin_user_id").notNull(),
    runType: varchar("run_type", { length: 100 }).notNull(),
    payload: jsonb().notNull(),
    createdAt: timestamp("created_at", {
      precision: 6,
      mode: "string",
    }).notNull(),
    result: jsonb().notNull(),
  },
  (table) => [
    foreignKey({
      columns: [table.adminUserId],
      foreignColumns: [userInAdmin.id],
      name: "match_run_initiated_by_user_id_fkey",
    }),
  ],
);
