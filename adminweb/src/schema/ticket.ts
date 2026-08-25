import { z } from "zod";

// Mirrors the backend's TicketStatus / TicketPriority. Parsing rather than
// trusting means a value the backend starts sending that we have not handled
// fails loudly here instead of rendering as a blank cell.
export const ticketStatusSchema = z.enum([
  "open",
  "in_progress",
  "pending_user",
  "resolved",
]);

export const ticketPrioritySchema = z.enum(["high", "normal", "low"]);

export const TICKET_STATUS_LABELS: Record<TicketStatus, string> = {
  open: "Open",
  in_progress: "In progress",
  pending_user: "Pending user",
  resolved: "Resolved",
};

export const TICKET_PRIORITY_LABELS: Record<TicketPriority, string> = {
  high: "High",
  normal: "Normal",
  low: "Low",
};

export const TICKET_CATEGORY_OPTIONS = [
  { value: "account_access", label: "Account & Access" },
  { value: "programs_groups", label: "Programs & Groups" },
  { value: "certificates_records", label: "Certificates & Records" },
];

const personSchema = z.object({
  id: z.number(),
  name: z.string(),
});

export const ticketRowSchema = z.object({
  id: z.number(),
  ticketNumber: z.string(),
  user: z.object({
    // Null on tickets the platform raised itself, which have no requester.
    name: z.string().nullable(),
    region: z.string(),
    anonymous: z.boolean(),
  }),
  subject: z.string(),
  status: ticketStatusSchema,
  priority: ticketPrioritySchema,
  assignee: personSchema.nullable(),
  // The support clock, not the requester's: this column means "when did
  // anything last happen", internal notes included.
  supportUpdatedAt: z.string(),
  overdue: z.boolean(),
});

export const ticketQueueSchema = z.object({
  items: z.array(ticketRowSchema),
  total: z.number(),
  page: z.number(),
  limit: z.number(),
  hasMore: z.boolean(),
});

export const ticketSummarySchema = z.object({
  unassigned: z.number(),
  open: z.number(),
  pendingUser: z.number(),
  overdue: z.number(),
});

export const ticketAttachmentSchema = z.object({
  id: z.number(),
  filename: z.string(),
  mimeType: z.string(),
  size: z.number(),
});

export const ticketMessageSchema = z.object({
  id: z.number(),
  messageType: z.enum([
    "user_message",
    "support_reply",
    "internal_note",
    "system",
  ]),
  body: z.string(),
  author: personSchema.nullable(),
  createdAt: z.string(),
  attachments: z.array(ticketAttachmentSchema),
});

export const ticketDetailSchema = z.object({
  id: z.number(),
  ticketNumber: z.string(),
  subject: z.string(),
  body: z.string(),
  category: z.string(),
  status: ticketStatusSchema,
  priority: ticketPrioritySchema,
  channel: z.string(),
  region: z.string(),
  requester: z
    .object({
      id: z.number(),
      name: z.string(),
      email: z.string(),
      region: z.string(),
      registeredAt: z.string(),
    })
    .nullable(),
  assignee: personSchema.nullable(),
  createdAt: z.string(),
  updatedAt: z.string(),
  supportUpdatedAt: z.string(),
  firstResponseAt: z.string().nullable(),
  resolvedAt: z.string().nullable(),
  overdue: z.boolean(),
  messages: z.array(ticketMessageSchema),
});

export const ticketHistoryEntrySchema = z.object({
  id: z.number(),
  action: z.string(),
  actor: personSchema.nullable(),
  beforeState: z.unknown().nullable(),
  afterState: z.unknown().nullable(),
  createdAt: z.string(),
});

export const assigneeOptionSchema = personSchema;

export const regionOptionSchema = z.object({
  value: z.string(),
  label: z.string(),
});

export const bulkAssignResultSchema = z.object({
  results: z.array(
    z.object({
      ticketId: z.number(),
      ok: z.boolean(),
      error: z.string().optional(),
    }),
  ),
});

// The five filter dimensions plus search, all optional. An empty string means
// "no filter", matching how the backend reads them.
export const ticketFiltersSchema = z.object({
  region: z.string().optional(),
  status: z.string().optional(),
  category: z.string().optional(),
  assignee: z.string().optional(),
  priority: z.string().optional(),
  search: z.string().optional(),
});

export type TicketStatus = z.infer<typeof ticketStatusSchema>;
export type TicketPriority = z.infer<typeof ticketPrioritySchema>;
export type TicketRow = z.infer<typeof ticketRowSchema>;
export type TicketQueue = z.infer<typeof ticketQueueSchema>;
export type TicketSummary = z.infer<typeof ticketSummarySchema>;
export type TicketMessage = z.infer<typeof ticketMessageSchema>;
export type TicketDetail = z.infer<typeof ticketDetailSchema>;
export type TicketHistoryEntry = z.infer<typeof ticketHistoryEntrySchema>;
export type AssigneeOption = z.infer<typeof assigneeOptionSchema>;
export type RegionOption = z.infer<typeof regionOptionSchema>;
export type TicketFilters = z.infer<typeof ticketFiltersSchema>;

// The bucket for tickets whose requester had no country on file. It needs a
// value of its own because an empty query parameter reads as "no filter"
// everywhere else on the platform.
export const UNKNOWN_REGION = "__unknown__";
