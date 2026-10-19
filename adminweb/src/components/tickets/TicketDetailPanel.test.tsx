import { act, fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { AssigneeOption } from "@/schema/ticket";

// Every hook this panel uses is a network call. Stubbing the query module
// keeps the test about what the panel renders and does, which is the part
// that had no cover at all.
const detail = vi.fn();
const update = {
  mutate: vi.fn(),
  reset: vi.fn(),
  isError: false,
  isPending: false,
  error: undefined as unknown,
};
const reply = { mutateAsync: vi.fn(), reset: vi.fn(), isError: false, isPending: false };
// The History list behind the Details tab. It was stubbed to an empty array
// and so had no cover at all, which is how it went on printing the stored
// action and calling every empty actor "system".
const history = { data: [] as unknown[] };
const remove = {
  mutate: vi.fn(),
  reset: vi.fn(),
  isError: false,
  isPending: false,
  error: undefined as unknown,
};

/** A failure shaped the way the server really sends one.
 *
 *  Response bodies here are copied from a probe against the ticket admin
 *  endpoints, not invented. Two envelopes are in play and the difference is
 *  the point: anything raised comes back as `{error, code, request_id}`,
 *  while the 404 is answered directly as `{msg, data}`.
 */
function failure(status: number, data: Record<string, unknown>) {
  return Object.assign(new Error(`Request failed with status code ${status}`), {
    isAxiosError: true,
    response: { status, data },
  });
}

/** A 400 the backend wrote for a person: an attachment rule or a serializer. */
function refusal(reason: string) {
  return failure(400, { error: reason, code: "invalid", request_id: "06cba68950f1" });
}

/** What every ticket admin view answers once the ticket is gone. */
function ticketGone() {
  return failure(404, { msg: "Ticket not found", data: null });
}

vi.mock("@/query/ticket", () => ({
  useTicketDetail: (id: number | null) => detail(id),
  useTicketHistory: () => history,
  useUpdateTicket: () => update,
  useReplyTicket: () => reply,
  useDeleteTicket: () => remove,
}));

const { TicketDetailPanel } = await import("./TicketDetailPanel");

const OWNER: AssigneeOption = { id: 3, name: "Gone Agent", assignable: false };
const ACTIVE: AssigneeOption = { id: 1, name: "Sam Reid", assignable: true };

function ticketWith(overrides: Record<string, unknown> = {}) {
  return {
    id: 7,
    ticketNumber: "SUP-2026-00007",
    subject: "Cannot access group workspace",
    status: "in_progress",
    priority: "normal",
    category: "help_student_group",
    channel: "portal",
    region: "Australia",
    overdue: false,
    createdAt: "2026-08-01T00:00:00Z",
    updatedAt: "2026-08-02T00:00:00Z",
    supportUpdatedAt: "2026-08-02T00:00:00Z",
    user: { id: 9, name: "Mia Thompson", email: "mia@example.com", anonymous: false },
    assignee: null,
    messages: [],
    attachments: [],
    ...overrides,
  };
}

function show(
  ticket: Record<string, unknown>,
  assignees = [ACTIVE, OWNER],
  canDelete = false,
) {
  detail.mockReturnValue({ data: ticket, isLoading: false, isError: false });
  return render(
    <TicketDetailPanel
      ticketId={ticket.id as number}
      assignees={assignees}
      onClose={vi.fn()}
      canDelete={canDelete}
      onDeleted={vi.fn()}
    />,
  );
}

beforeEach(() => {
  update.isError = false;
  update.error = undefined;
  update.mutate.mockClear();
  update.reset.mockClear();
  remove.isError = false;
  remove.error = undefined;
  reply.mutateAsync.mockReset();
  history.data = [];
});

describe("assignee control", () => {
  it("still names the current owner after they stop being assignable", () => {
    // The bug: the fallback row asked "are they missing from `assignees`",
    // and the endpoint deliberately keeps past owners in that list so the
    // filter dropdown can find their tickets. So the row never rendered, the
    // list below it filtered them out, no option matched the current value,
    // and Radix fell back to the placeholder — a ticket with an owner showed
    // as "Unassigned".
    show(ticketWith({ assignee: { id: OWNER.id, name: OWNER.name } }));

    const trigger = screen.getByRole("combobox", { name: /change assignee/i });
    expect(trigger.textContent).toContain("Gone Agent");
    expect(trigger.textContent).not.toBe("Unassigned");
  });

  it("does not offer an unassignable person as a new owner", () => {
    show(ticketWith({ assignee: { id: OWNER.id, name: OWNER.name } }));

    fireEvent.keyDown(screen.getByRole("combobox", { name: /change assignee/i }), {
      key: "ArrowDown",
    });

    expect(screen.getByRole("option", { name: "Sam Reid" })).toBeTruthy();
    // Present once, as the current-owner row, and marked as off the queue.
    expect(
      screen.getByRole("option", { name: /Gone Agent \(no longer on the queue\)/ }),
    ).toBeTruthy();
    // ⚠️ The line above cannot fail alone, and the first version stopped
    // there — a test named "does not offer" that never asserted an absence.
    // Deleting the .filter(assignable) in the component leaves the
    // current-owner row in place AND adds a plain "Gone Agent" entry below
    // it, so both positive assertions still pass. This is the twin of the
    // A8-01 bug, in the test named after preventing it. The anchored name
    // matches the plain entry only, never the current-owner row.
    expect(screen.queryByRole("option", { name: /^Gone Agent$/ })).toBeNull();
  });

  it("does not call a revoked agent inactive, which is a different thing", () => {
    // Two things drop the owner off the assignable list: a deactivated
    // account, and queue access revoked on the support agents page. The
    // second leaves the account active, and People shows "Active" for the
    // same person at the same moment, so "(inactive)" sent admins to switch
    // an account back on that was never switched off.
    show(ticketWith({ assignee: { id: OWNER.id, name: OWNER.name } }));

    const trigger = screen.getByRole("combobox", { name: /change assignee/i });
    expect(trigger.textContent).toBe("Gone Agent (no longer on the queue)");
    expect(trigger.textContent).not.toMatch(/inactive/i);
  });

  it("shows the placeholder when there really is no owner", () => {
    show(ticketWith({ assignee: null }));

    expect(
      screen.getByRole("combobox", { name: /change assignee/i }).textContent,
    ).toContain("Unassigned");
  });
});

describe("when a change is refused", () => {
  it("says so instead of letting the dropdown snap back in silence", () => {
    // All three controls are driven by `ticket`, so a rejected PATCH leaves
    // them showing the old value and nothing else. A 404 here is ordinary:
    // somebody else deleting the ticket while this panel is open produces it.
    update.isError = true;
    show(ticketWith());

    expect(screen.getByRole("alert").textContent).toMatch(/was not saved/i);
  });

  it("passes on the server's reason instead of guessing at one", () => {
    // The standing sentence guesses "deleted or changed by someone else",
    // which is the wrong thing to go and check when the server has already
    // said what is wrong.
    update.isError = true;
    update.error = refusal("Send a status or an assignee, not both.");
    show(ticketWith());

    expect(screen.getByRole("alert").textContent).toBe(
      "That change was not saved. Send a status or an assignee, not both.",
    );
  });

  it("keeps the whole sentence when the ticket has simply gone", () => {
    // The 404 does not come through the exception handler, so it has no
    // `error` key and no code at all: views_admin.py:258 answers
    // {"msg": "Ticket not found"}. Reading `msg` as a reason replaced the
    // one sentence on this screen that says what to do next with two words
    // that do not, on the failure this panel meets most often.
    update.isError = true;
    update.error = ticketGone();
    show(ticketWith());

    expect(screen.getByRole("alert").textContent).toBe(
      "That change was not saved. The ticket may have been deleted or changed" +
        " by someone else — close the panel and reopen it to see where it" +
        " stands.",
    );
  });

  it("does not read a database key out to the agent", () => {
    // The assignee dropdown is built from a cached query. Revoke someone's
    // queue access in another tab and they are still in this list; picking
    // them is refused with DRF's own words, which name a primary key and
    // suggest nothing. Reopening the panel refetches the list, which is
    // exactly what the standing sentence already says to do.
    update.isError = true;
    update.error = failure(400, {
      error: 'Invalid pk "18" - object does not exist.',
      code: "does_not_exist",
      request_id: "048bd2752e81",
      fields: { assignee: ['Invalid pk "18" - object does not exist.'] },
    });
    show(ticketWith());

    const alert = screen.getByRole("alert").textContent ?? "";
    expect(alert).not.toMatch(/invalid pk/i);
    expect(alert).toMatch(/close the panel and reopen it/i);
  });

  it("stays quiet while everything is working", () => {
    show(ticketWith());
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("clears the warning when the panel moves to another ticket", () => {
    // Without this the red text follows the agent to the next ticket and
    // reads as a problem with the one they are now looking at.
    const { rerender } = show(ticketWith({ id: 7 }));

    // ⚠️ Load-bearing. The reset effect also fires once on mount, and that
    // call alone satisfied toHaveBeenCalled — with the effect's dependency
    // array emptied (the A8-03 regression, verbatim) this test stayed green.
    // Only calls caused by the ticket CHANGING may count.
    update.reset.mockClear();

    detail.mockReturnValue({
      data: ticketWith({ id: 8 }),
      isLoading: false,
      isError: false,
    });
    rerender(
      <TicketDetailPanel
        ticketId={8}
        assignees={[ACTIVE, OWNER]}
        onClose={vi.fn()}
        canDelete={false}
        onDeleted={vi.fn()}
      />,
    );

    expect(update.reset).toHaveBeenCalled();
  });
});

describe("category control", () => {
  it("shows the ticket's current category as a control, not as read-only text", () => {
    // Before the client's eight-category list there was no way, in any
    // interface, to change a ticket's category after submission. Two of their
    // eight are near-synonyms, so mis-filing is now routine and the p52
    // category breakdown depends on someone being able to fix it.
    show(ticketWith({ category: "help_mentor" }));
    const control = screen.getByLabelText("Change category");
    expect(control.textContent).toContain("Help with a mentor");
  });

  it("offers the screening category too, so a mis-screened ticket has a way out", () => {
    show(ticketWith({ category: "flagged_content" }));
    const control = screen.getByLabelText("Change category");
    // Radix renders the trigger's current value; the list itself only mounts
    // on open. Showing the label rather than the raw value is the part that
    // proves flagged_content is a known option here and not a fall-through.
    expect(control.textContent).toContain("Flagged content");
  });

  it("sends the new category as a patch", () => {
    show(ticketWith({ category: "account_access" }));
    // Opened with the keyboard for the reason BulkAssignBar.test.tsx records:
    // Radix opens on pointerdown, which needs a real PointerEvent with pointer
    // capture, and jsdom provides neither. ArrowDown is a documented way in.
    fireEvent.keyDown(
      screen.getByRole("combobox", { name: /change category/i }),
      { key: "ArrowDown" },
    );
    fireEvent.click(screen.getByRole("option", { name: "Technical issue" }));
    expect(update.mutate).toHaveBeenCalledWith({
      id: 7,
      patch: { category: "technical_issue" },
    });
  });

  it("does not send a status or an assignee alongside the category", () => {
    // The backend refuses status and assignee together, and re-filing must
    // never look like either of those transitions: it writes no timeline
    // message and does not move the requester's clock.
    show(ticketWith({ category: "account_access" }));
    fireEvent.keyDown(
      screen.getByRole("combobox", { name: /change category/i }),
      { key: "ArrowDown" },
    );
    fireEvent.click(screen.getByRole("option", { name: "Other" }));
    expect(update.mutate).toHaveBeenCalledTimes(1);
    expect(Object.keys(update.mutate.mock.calls[0][0].patch)).toEqual([
      "category",
    ]);
  });
});

describe("the two attachment pickers and the two message boxes", () => {
  /**
   * Reads the name a screen reader computes, in the order the accname spec
   * resolves it. Placeholder is deliberately excluded: it is the last-resort
   * source, the two Playwright specs locate these boxes by it, and treating it
   * as a name here would let the very gap this guards against pass.
   */
  function accessibleName(el: Element): string {
    const labelledBy = el.getAttribute("aria-labelledby");
    if (labelledBy) {
      return labelledBy
        .split(/\s+/)
        .map((id) => document.getElementById(id)?.textContent?.trim() ?? "")
        .join(" ")
        .trim();
    }
    const label = el.getAttribute("aria-label");
    if (label) return label.trim();
    const labels = (el as HTMLInputElement).labels;
    if (labels && labels.length) {
      return Array.from(labels).map((l) => l.textContent?.trim() ?? "").join(" ").trim();
    }
    return "";
  }

  it("gives the reply and the internal note different names", () => {
    show(ticketWith());

    const names = Array.from(
      document.querySelectorAll('input[type="file"], textarea'),
    ).map(accessibleName);

    // Four controls, four names, none of them blank. A blank name is what a
    // bare file input computes to — the "Choose File" text belongs to a
    // button inside the browser's own shadow DOM and is not a name.
    expect(names).toHaveLength(4);
    expect(names.filter((n) => n === "")).toEqual([]);
    expect(new Set(names).size).toBe(4);
  });

  it("says which box the requester will read and which they will not", () => {
    show(ticketWith());

    // Written out rather than read from the components, so that renaming a
    // control has to be a deliberate edit here too. One of these attaches to
    // an email a student receives; the other to a note they must never see,
    // and telling them apart cannot depend on hearing them in order.
    const names = Array.from(
      document.querySelectorAll('input[type="file"], textarea'),
    ).map(accessibleName);

    expect(names).toContain("Reply to the requester");
    expect(names).toContain("Attach files to this reply");
    expect(names).toContain("Internal note, not visible to the requester");
    expect(names).toContain("Attach files to this internal note");
  });
});

describe("when a message is refused", () => {
  /** Types something into one of the two boxes and sends it. */
  async function sendFrom(boxLabel: string, buttonName: RegExp) {
    fireEvent.change(screen.getByLabelText(boxLabel), {
      target: { value: "Here is the form you asked for." },
    });
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: buttonName }));
    });
  }

  it("shows what the server said about the reply, not 'try again'", async () => {
    // An 11 MB attachment is refused for a reason the agent can act on, and
    // the same send fails the same way however many times they retry. The
    // wording is written out here rather than read from the component, so
    // that losing it has to be a deliberate edit in this file too.
    reply.mutateAsync.mockRejectedValue(
      refusal("Attachment exceeds the maximum allowed size of 10 MB."),
    );
    show(ticketWith());

    await sendFrom("Reply to the requester", /send reply/i);

    expect(screen.getByRole("alert").textContent).toBe(
      "Attachment exceeds the maximum allowed size of 10 MB. Your text is still here.",
    );
  });

  it("shows what the server said about an internal note too", async () => {
    reply.mutateAsync.mockRejectedValue(
      refusal("Attach at most 5 files to one message."),
    );
    show(ticketWith());

    await sendFrom("Internal note, not visible to the requester", /add internal note/i);

    expect(screen.getByRole("alert").textContent).toBe(
      "Attach at most 5 files to one message. Your text is still here.",
    );
  });

  it("still says try again when the failure carries no reason", async () => {
    // A dropped connection is the case the old wording was written for, and
    // it is the one case where trying again is the right advice.
    reply.mutateAsync.mockRejectedValue(new Error("Network Error"));
    show(ticketWith());

    await sendFrom("Reply to the requester", /send reply/i);

    expect(screen.getByRole("alert").textContent).toBe(
      "That did not send. Your text is still here — try again.",
    );
  });

  it("falls back to try again when the ticket has gone", async () => {
    // Sending to a ticket a colleague deleted is a 404 in the older envelope.
    // Pasting its two words after the standing sentence produced "Ticket not
    // found Your text is still here.", two sentences run together with no
    // stop between them.
    reply.mutateAsync.mockRejectedValue(ticketGone());
    show(ticketWith());

    await sendFrom("Reply to the requester", /send reply/i);

    expect(screen.getByRole("alert").textContent).toBe(
      "That did not send. Your text is still here — try again.",
    );
  });

  it("does not put CSRF on the screen", async () => {
    // A stale token is refused as permission_denied like a real access
    // problem, but its wording is about the request machinery. myFetch.ts
    // already retries this once with a fresh token.
    reply.mutateAsync.mockRejectedValue(
      failure(403, {
        error: "CSRF Failed: CSRF cookie not set.",
        code: "permission_denied",
        request_id: "ae7172323949",
      }),
    );
    show(ticketWith());

    await sendFrom("Reply to the requester", /send reply/i);

    expect(screen.getByRole("alert").textContent).toBe(
      "That did not send. Your text is still here — try again.",
    );
  });

  it("keeps what was typed either way", async () => {
    reply.mutateAsync.mockRejectedValue(
      refusal("Attachment must use an allowed file extension."),
    );
    show(ticketWith());

    await sendFrom("Reply to the requester", /send reply/i);

    expect(
      (screen.getByLabelText("Reply to the requester") as HTMLTextAreaElement).value,
    ).toBe("Here is the form you asked for.");
  });
});

describe("who a message is from", () => {
  const NO_AUTHOR = {
    id: 1,
    messageType: "internal_note",
    author: null,
    body: "A message was flagged by automated screening.",
    createdAt: "2026-08-01T00:00:00Z",
    attachments: [],
  };

  it("does not claim an account was removed when none ever existed", () => {
    // Three kinds of support row arrive with no author: an agent whose
    // account was deleted, screening's evidence note, and the note recording
    // an undeliverable email. Nothing in the payload tells them apart, so
    // two rows in three were signed with a deletion that never happened.
    show(ticketWith({ messages: [NO_AUTHOR] }));

    expect(screen.getByText("Support (author not recorded)")).toBeTruthy();
    expect(screen.queryByText(/account removed/i)).toBeNull();
  });

  it("still keeps an unsigned support row off the requester's name", () => {
    // What the old label was there to prevent, and the reason this cannot
    // simply fall through to the user_message branch: an internal note is
    // written ABOUT the student, so calling it theirs is worse than saying
    // nothing.
    show(ticketWith({ messages: [NO_AUTHOR] }));

    expect(screen.queryByText("Requester")).toBeNull();
  });

  it("names the person when there is one", () => {
    show(ticketWith({
      messages: [{ ...NO_AUTHOR, author: { id: 4, name: "Sam Reid" } }],
    }));

    expect(screen.getByText("Sam Reid")).toBeTruthy();
    expect(screen.queryByText(/author not recorded/i)).toBeNull();
  });
});

describe("when a delete is refused", () => {
  /** The delete block and its warning live behind the Details tab. */
  function openDetails() {
    fireEvent.click(screen.getByRole("button", { name: /^details$/i }));
  }

  it("says what the server said, on top of saying nothing changed", () => {
    // An admin who had their admin access taken away mid-session still has
    // the button on screen, because canDelete came from a cached session.
    // "Nothing has changed" alone leaves them clicking it again.
    remove.isError = true;
    remove.error = failure(403, {
      error: "You do not have admin privileges.",
      code: "permission_denied",
      request_id: "c3fbf345963e",
    });
    show(ticketWith(), [ACTIVE, OWNER], true);
    openDetails();

    expect(screen.getByRole("alert").textContent).toBe(
      "That did not delete. Nothing has changed. You do not have admin privileges.",
    );
  });

  it("says nothing more when the ticket was already deleted", () => {
    // Two admins pressing Delete on the same ticket. The second one gets the
    // 404, and its two words add nothing to the sentence already there.
    remove.isError = true;
    remove.error = ticketGone();
    show(ticketWith(), [ACTIVE, OWNER], true);
    openDetails();

    expect(screen.getByRole("alert").textContent).toBe(
      "That did not delete. Nothing has changed.",
    );
  });

  it("still sends the delete when the button is pressed", () => {
    // Load-bearing for the two above: they assert on an alert that only
    // appears once remove.isError is set by hand, so without this nothing
    // proves the button under it is still wired to the mutation.
    remove.mutate.mockClear();
    show(ticketWith(), [ACTIVE, OWNER], true);
    openDetails();
    fireEvent.click(screen.getByRole("button", { name: /delete ticket/i }));
    fireEvent.click(screen.getByRole("button", { name: /^delete$/i }));

    expect(remove.mutate.mock.calls[0][0]).toBe(7);
  });
});

describe("the ticket's own history", () => {
  /** The History block lives behind the Details tab. */
  function openDetails() {
    fireEvent.click(screen.getByRole("button", { name: /^details$/i }));
  }

  function entry(overrides: Record<string, unknown> = {}) {
    return {
      id: 1,
      action: "status",
      actor: { id: 4, name: "Sam Reid" },
      beforeState: { status: "open" },
      afterState: { status: "in_progress" },
      createdAt: "2026-08-02T00:00:00Z",
      ...overrides,
    };
  }

  function line() {
    const list = screen.getByText("History").nextElementSibling as HTMLElement;
    return list.textContent ?? "";
  }

  it("names an action the way the audit page names it", () => {
    // These are the same AuditLog rows the audit page lists, for one ticket
    // instead of all of them. This list printed the stored value, so one
    // screen said "Status changed" and the other said "status" about rows
    // sitting on top of each other.
    history.data = [entry()];
    show(ticketWith());
    openDetails();

    expect(line()).toContain("Status changed");
    expect(line()).not.toContain("status");
  });

  it("names the person when the row still has one", () => {
    history.data = [entry()];
    show(ticketWith());
    openDetails();

    expect(line()).toContain("Sam Reid");
  });

  it("does not call a row the platform wrote 'system'", () => {
    // The screening handoff writes with no actor on purpose, because no
    // person opened that ticket, and its snapshot carries the channel that
    // says so.
    history.data = [
      entry({
        action: "create",
        actor: null,
        beforeState: null,
        afterState: { channel: "ai_screening", ticket_number: "SUP-2026-00262" },
      }),
    ];
    show(ticketWith());
    openDetails();

    expect(line()).toContain("Automated screening");
    expect(line()).not.toContain("system");
  });

  it("says the account is gone on a row that had a person on it", () => {
    // ⚠️ Load-bearing next to the case above: printing "Automated screening"
    // for every empty actor passes that one on its own. actor_user is
    // SET_NULL, so this is the commonest way a row loses its name, and
    // "system" said a person had never been involved.
    history.data = [entry({ actor: null })];
    show(ticketWith());
    openDetails();

    expect(line()).toContain("Account removed");
    expect(line()).not.toContain("system");
  });
});

describe("the times this panel prints", () => {
  const RAISED = "2026-08-01T00:00:00Z";

  // Built from the clock this machine is on rather than matched against a
  // list of zone spellings. The short name is "UTC" here, "AEST" in Sydney,
  // "GMT-3" in Sao Paulo and "GMT+5:30" in Kolkata, and a hand-written list
  // of those turns the suite red on whichever machine it happens to miss.
  const stamp = {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  } as const;

  function openDetails() {
    fireEvent.click(screen.getByRole("button", { name: /^details$/i }));
  }

  it("names the time zone on a timestamp", () => {
    // Rendered in whatever zone the reader's machine is in, so the same row
    // reads 03:37 pm in Sydney and 02:37 am in Sao Paulo. Two of the three
    // ticket screens left the zone off, and agents quote these times to each
    // other and check them against the overdue windows.
    show(ticketWith({ createdAt: RAISED }));
    openDetails();

    const raised =
      screen.getByText("Raised").nextElementSibling?.textContent ?? "";
    const withoutZone = new Date(RAISED).toLocaleString("en-AU", stamp);
    const withZone = new Date(RAISED).toLocaleString("en-AU", {
      ...stamp,
      timeZoneName: "short",
    });

    expect(raised).toBe(withZone);
    // The zone name is an addition, not a replacement: the timestamp is still
    // in front of it, and there is something after it.
    expect(withZone.startsWith(withoutZone)).toBe(true);
    expect(raised).not.toBe(withoutZone);
  });

  it("leaves Member since a plain date, with no zone on it", () => {
    // Deliberately not the same treatment. The field answers "new account or
    // long-standing participant", so it carries no clock time for a zone name
    // to qualify, and "26 Aug 2026 AEST" would read as an event.
    show(
      ticketWith({
        requester: {
          id: 9,
          name: "Mia Thompson",
          email: "mia@example.com",
          region: "Australia",
          registeredAt: RAISED,
        },
      }),
    );
    openDetails();

    const since =
      screen.getByText("Member since").nextElementSibling?.textContent ?? "";
    expect(since).toBe(
      new Date(RAISED).toLocaleDateString("en-AU", {
        day: "numeric",
        month: "short",
        year: "numeric",
      }),
    );
  });
});
