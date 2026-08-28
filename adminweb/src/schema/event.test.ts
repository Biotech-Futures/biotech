import { describe, expect, it } from "vitest";

import { createEventSchema, updateEventSchema } from "./event";

const longRichText = `<p>${"Event details ".repeat(30)}</p>`;

describe("event description validation", () => {
  it("accepts rich-text descriptions longer than 255 characters when creating", () => {
    const result = createEventSchema.safeParse({
      eventName: "Rich-text event",
      description: longRichText,
      eventFormat: "in_person",
      eventTimezone: "Australia/Sydney",
      startAt: "2026-09-01T10:00",
      endsAt: "2026-09-01T11:00",
      targetGroupIds: [],
      targetRoleIds: [],
    });

    expect(result.success).toBe(true);
  });

  it("accepts rich-text descriptions longer than 255 characters when updating", () => {
    const result = updateEventSchema.safeParse({
      description: longRichText,
    });

    expect(result.success).toBe(true);
  });
});
