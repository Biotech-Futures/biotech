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

// The client's own list and wording, given 2026-09-04, in their order.
// "General Question" is title case while the rest are sentence case; that is
// how they wrote it.
export const TICKET_CATEGORY_OPTIONS = [
  { value: "account_access", label: "Account and access" },
  { value: "registration", label: "Registration" },
  { value: "help_student_group", label: "Help with a student or group" },
  { value: "help_mentor", label: "Help with a mentor" },
  { value: "technical_issue", label: "Technical issue" },
  { value: "certificates_records", label: "Certificates and records" },
  { value: "general_question", label: "General Question" },
  { value: "other", label: "Other" },
  // Never offered in the portal — message screening files its own tickets
  // under it. Listed here because this list also builds the queue's category
  // filter and the re-file control on the detail panel: a bucket support
  // cannot filter for is a bucket they cannot work through, and a ticket
  // screening filed here needs a way out.
  { value: "flagged_content", label: "Flagged content" },
];

/** The wording the requester picked from, not the database value.
 *
 *  The empty case still has an answer rather than falling through to a dash
 *  that reads like data was lost: screening tickets carry a category now, but
 *  rows written before it did are still readable. */
export function categoryLabel(category: string): string {
  if (!category) return "Not categorised";
  return (
    TICKET_CATEGORY_OPTIONS.find((option) => option.value === category)?.label ??
    category
  );
}

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
  // The two halves of one walk, and neither means anything alone.
  //
  // `asOf` is the moment this walk is a picture of: which tickets are in it
  // and in what order. `after` is the place the reader has reached, the sort
  // key of the last row on this page. Next sends both back and gets the rows
  // strictly after that place.
  //
  // Why a cursor and not the page number: the queue is ordered by last support
  // activity, which moves while somebody reads it. No ordering makes an offset
  // safe against that — a row that changes position either crosses the reader
  // or pushes the rows behind it across the reader. Measured before this
  // changed: an internal note on three of two hundred tickets, and those three
  // were served on no page while the footer still read "20 of 20".
  //
  // `after` is null on an empty page: there is no last row to continue from.
  asOf: z.string(),
  after: z.string().nullable(),
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

export const assigneeOptionSchema = personSchema.extend({
  /** Whether the write path will accept this person as an assignee, which is
   *  membership of the backend's `support_capable_users()`. False covers both
   *  a deactivated account and one whose support role was revoked while the
   *  account stayed active — not the same set, and reading it as only the
   *  first is the defect that offered a name `PATCH` then refused with a 400.
   *
   *  Such a person can still OWN tickets, so they belong in the filter
   *  dropdown; they must not be offered as somebody to hand work to.
   *
   *  Required, deliberately. It carried `.default(true)` and the endpoint
   *  always sends the key, so the default could only ever fire when the field
   *  went missing — and it defaulted to the permissive answer, quietly making
   *  everybody assignable, including the people this flag exists to exclude.
   *  Absent, the parse should fail loudly rather than open the dropdown up. */
  assignable: z.boolean(),
});

export const supportAgentSchema = personSchema.extend({
  email: z.string(),
  // What revoking would strand. Resolved tickets are not counted: nobody has
  // to pick those up again.
  openTickets: z.number(),
  /** The account's own status, straight from the users table.
   *
   *  Queue access and account status are kept apart on purpose, so switching
   *  an agent off leaves their row on the roster exactly where it was. The
   *  cost is that a name on this list may be an account nobody can sign into,
   *  and the endpoint sends this field so the screen can say which.
   *
   *  A plain string and not an enum, unlike status and priority above. Those
   *  two are the ticket module's own and a new value there is a defect worth
   *  failing loudly over. This one belongs to the users app, which has five
   *  values today and may gain a sixth for reasons that have nothing to do
   *  with support, and a parse failure would take the whole roster off the
   *  screen over a word this page only reads. accountStatusNote below decides
   *  what to make of it and has an answer for a value it does not know. */
  accountStatus: z.string(),
});

// Cannot sign in, so cannot work the queue. Mirrors
// users.User.INACTIVE_LOGIN_STATUSES, which deliberately leaves out "invited"
// and "pending": those are is_active=False as well, and they can still sign in
// with a usable password. Reading this off is_active instead is how an invited
// colleague gets marked as switched off.
const SIGN_IN_BLOCKED: Record<string, string> = {
  suspended: "Suspended",
  deactivated: "Deactivated",
};

/** What to say beside a roster name whose account cannot sign in, or null.
 *
 *  Null for every other status, this being a mark and not a status column: an
 *  account that can sign in is the ordinary case and needs no comment. */
export function accountStatusNote(accountStatus: string): string | null {
  return SIGN_IN_BLOCKED[accountStatus] ?? null;
}

export const ticketAuditRowSchema = z.object({
  id: z.number(),
  ticketId: z.number(),
  action: z.string(),
  actor: personSchema.nullable(),
  // Free-form JSON. For a deletion it carries the ticket number and subject,
  // which is the only way to name a ticket that no queryset returns any more.
  beforeState: z.record(z.string(), z.unknown()).nullable(),
  afterState: z.record(z.string(), z.unknown()).nullable(),
  createdAt: z.string(),
});

// Every value the ticket module actually writes to AuditLog.action. Only three
// of these are in the model's own ActionChoices — log_audit_event does not
// validate against it — so this list comes from the code that writes, not the
// enum. It also builds the audit page's action filter, which is why it is a
// list of pairs and not a map.
export const TICKET_AUDIT_ACTIONS = [
  { value: "create", label: "Created" },
  { value: "assign", label: "Assigned" },
  { value: "status", label: "Status changed" },
  { value: "priority", label: "Priority changed" },
  { value: "category", label: "Category changed" },
  { value: "resolve", label: "Resolved" },
  { value: "reopen", label: "Reopened" },
  { value: "delete", label: "Deleted" },
];

/** An audit action as words.
 *
 *  Shared by the audit page's Action column and the History list on the
 *  detail panel, which show the same AuditLog rows through two endpoints.
 *  The panel printed the stored value, so one screen said "Status changed"
 *  and the other said "status" about the same row.
 *
 *  An unrecognised value comes back unchanged rather than as a dash: the
 *  column exists to be read, and a stored word beats nothing at all. */
export function auditActionLabel(action: string): string {
  return TICKET_AUDIT_ACTIONS.find((a) => a.value === action)?.label ?? action;
}

/** Who an audit row names, when it names nobody.
 *
 *  One wording in one place because two screens print it: the Who column on
 *  the audit page, and the History list on the detail panel. Both read the
 *  same AuditLog rows through two endpoints, and until this existed the same
 *  row read "Account removed" on one screen and "system" on the other.
 *
 *  Two different things arrive here as a missing actor, and they are told
 *  apart rather than flattened into one careful sentence. AuditLog.actor_user
 *  is SET_NULL, so a row outlives the account that made it. The screening
 *  handoff writes its rows with no actor on purpose, because no person opened
 *  those tickets, and handoff.py is the only writer in the ticket module that
 *  passes actor=None — every other row had a real person on it when it was
 *  written. So a row that is not screening's and names nobody really is an
 *  account that has since been deleted, and "Account removed" is a statement
 *  about it rather than a guess.
 *
 *  Screening's rows are the ones carrying `channel` in their snapshot, which
 *  is what tells the two apart. Calling one of those a removed account
 *  invents an account that never existed, on the child-safety rows of all
 *  things.
 *
 *  The messages on the detail panel are a different question with a different
 *  answer. Those carry TicketMessage.author, which goes null for three
 *  reasons the payload cannot tell apart, so that label stays vague on
 *  purpose. See the comment on MessageRow. */
export function auditActorName(
  actor: { name: string } | null,
  afterState: unknown,
): string {
  if (actor) return actor.name;
  const after = (afterState ?? {}) as Record<string, unknown>;
  return after.channel === "ai_screening"
    ? "Automated screening"
    : "Account removed";
}

export const ticketAuditPageSchema = z.object({
  items: z.array(ticketAuditRowSchema),
  total: z.number(),
  page: z.number(),
  limit: z.number(),
  hasMore: z.boolean(),
});

const bucketSchema = z.object({ value: z.string(), count: z.number() });

export const ticketAnalyticsSchema = z.object({
  window: z.object({
    from: z.string().nullable(),
    to: z.string().nullable(),
  }),
  demand: z.object({
    volume: z.number(),
    categoryMix: z.array(bucketSchema),
    channelMix: z.array(bucketSchema),
  }),
  flow: z.object({
    unassignedBacklog: z.number(),
    ageByStatus: z.array(
      z.object({ status: z.string(), averageSeconds: z.number().nullable() }),
    ),
    reopens: z.number(),
    handOffs: z.number(),
  }),
  service: z.object({
    firstResponseSeconds: z.number().nullable(),
    answeredCount: z.number(),
    resolutionSeconds: z.number().nullable(),
    resolvedCount: z.number(),
    overdue: z.number(),
  }),
  quality: z.object({
    // Null, not zero, for an empty window: nought percent resolved is a
    // damning number to invent.
    resolutionRate: z.number().nullable(),
    resolvedCount: z.number(),
    totalCount: z.number(),
    repeatContacts: z.number(),
    satisfaction: z.number().nullable(),
    satisfactionAvailable: z.boolean(),
  }),
  segment: z
    .object({ dimension: z.string(), buckets: z.array(bucketSchema) })
    .nullable(),
  dimensions: z.array(z.string()),
});

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

// "Nobody owns this one" as a filter value. An empty string reads as "no
// filter" on both sides, so the bucket needs a value it can actually travel
// as. Must match services/queue.py UNASSIGNED.
export const UNASSIGNED = "__unassigned__";

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

export type TicketAnalytics = z.infer<typeof ticketAnalyticsSchema>;
export type TicketAuditRow = z.infer<typeof ticketAuditRowSchema>;
export type SupportAgent = z.infer<typeof supportAgentSchema>;
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
