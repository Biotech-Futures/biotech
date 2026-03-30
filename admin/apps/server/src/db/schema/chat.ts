import {
  pgTable,
  varchar,
  timestamp,
  boolean,
  integer,
  uniqueIndex,
  index,
} from "drizzle-orm/pg-core";
import { users } from "./users.schema"; // adjust import path
import { groups } from "./groups.schema"; // adjust import path

export const messages = pgTable(
  "messages",
  {
    id: integer("id").primaryKey().generatedAlwaysAsIdentity(),
    senderUserId: integer("sender_user_id")
      .notNull()
      .references(() => users.id, { onDelete: "restrict" }),
    groupId: integer("group_id")
      .notNull()
      .references(() => groups.id, { onDelete: "cascade" }),
    messageText: varchar("message_text", { length: 255 }).notNull(),
    sentDatetime: timestamp("sent_datetime", { mode: "date" })
      .notNull()
      .defaultNow(),
    deletedFlag: boolean("deleted_flag").notNull().default(false),
  },
  (table) => [
    uniqueIndex("unique_message_per_user_per_time").on(
      table.senderUserId,
      table.groupId,
      table.sentDatetime,
    ),
    index("messages_group_sent_idx").on(table.groupId, table.sentDatetime),
    index("messages_sender_idx").on(table.senderUserId),
  ],
);

export const messageAttachments = pgTable(
  "message_attachments",
  {
    id: integer("id").primaryKey().generatedAlwaysAsIdentity(),
    messageId: integer("message_id")
      .notNull()
      .references(() => messages.id, { onDelete: "cascade" }),
    attachmentId: varchar("attachment_id", { length: 255 }).notNull().unique(),
    attachmentFilename: varchar("attachment_filename", {
      length: 255,
    }).notNull(),
  },
  (table) => [
    uniqueIndex("unique_filename_per_message").on(
      table.messageId,
      table.attachmentFilename,
    ),
    index("message_attachments_message_idx").on(table.messageId),
  ],
);
