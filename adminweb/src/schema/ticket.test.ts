import { describe, expect, it } from "vitest";
import {
  TICKET_CATEGORY_OPTIONS,
  ticketDetailSchema,
  ticketQueueSchema,
  ticketRowSchema,
  ticketSummarySchema,
} from "./ticket";

// A ticket raised by the platform's own message screening has no requester at
// all: created_by is null, so the row comes back with user.name === null. A
// non-nullable name here would fail the whole array and empty the queue with
// no error anyone would see.
const SCREENING_ROW = {
  id: 88,
  ticketNumber: "SUP-2026-00042",
  user: { name: null, region: "", anonymous: false },
  subject: 'AI screening: personal_contact — group "Team Photosynthesis"',
  status: "open",
  priority: "high",
  assignee: null,
  supportUpdatedAt: "2026-08-25T09:58:00Z",
  overdue: false,
};

const HUMAN_ROW = {
  ...SCREENING_ROW,
  id: 89,
  ticketNumber: "SUP-2026-00043",
  user: { name: "Mia Thompson", region: "Australia", anonymous: false },
  subject: "Cannot access group workspace",
  priority: "normal",
  assignee: { id: 4, name: "Sam Reid" },
};

describe("the queue row tolerates a ticket with no requester", () => {
  it("accepts a screening-raised row", () => {
    expect(() => ticketRowSchema.parse(SCREENING_ROW)).not.toThrow();
  });

  it("does not let one such row empty the whole page", () => {
    const parsed = ticketQueueSchema.parse({
      items: [SCREENING_ROW, HUMAN_ROW],
      total: 2,
      page: 1,
      limit: 10,
      hasMore: false,
    });
    expect(parsed.items).toHaveLength(2);
  });

  it("keeps anonymous false on a screening row", () => {
    // Anonymous submission was never built. The only tickets without a
    // requester are the ones the platform raises, and labelling those
    // "anonymous" in the queue would be telling agents something untrue.
    expect(ticketRowSchema.parse(SCREENING_ROW).user.anonymous).toBe(false);
  });
});

describe("the detail schema", () => {
  it("accepts a ticket that has never been answered or resolved", () => {
    const detail = {
      ...HUMAN_ROW,
      body: "I get an error opening my group.",
      category: "programs_groups",
      channel: "portal",
      region: "Australia",
      requester: {
        id: 1,
        name: "Mia Thompson",
        email: "mia@example.com",
        region: "Australia",
        registeredAt: "2026-05-01T00:00:00Z",
      },
      createdAt: "2026-08-25T09:00:00Z",
      updatedAt: "2026-08-25T09:00:00Z",
      supportUpdatedAt: "2026-08-25T09:00:00Z",
      firstResponseAt: null,
      resolvedAt: null,
      messages: [],
    };
    expect(() => ticketDetailSchema.parse(detail)).not.toThrow();
  });
});

describe("the counter cards", () => {
  it("expects the four keys the summary endpoint returns", () => {
    const parsed = ticketSummarySchema.parse({
      unassigned: 12,
      open: 38,
      pendingUser: 17,
      overdue: 4,
    });
    expect(Object.keys(parsed).sort()).toEqual([
      "open",
      "overdue",
      "pendingUser",
      "unassigned",
    ]);
  });
});

describe("the category filter", () => {
  it("offers the three the requester can choose, and no internal one", () => {
    const values = TICKET_CATEGORY_OPTIONS.map((c) => c.value);
    expect(values).toEqual([
      "account_access",
      "programs_groups",
      "certificates_records",
    ]);
  });
});
