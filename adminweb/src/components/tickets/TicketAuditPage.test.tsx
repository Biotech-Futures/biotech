import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

// TanStack Router's Link needs a router in context; nothing here is about
// navigation, so it becomes a plain anchor carrying the same destination.
vi.mock("@tanstack/react-router", () => ({
  Link: ({
    to,
    search,
    children,
    ...rest
  }: {
    to: string;
    search: { ticket: number };
    children: React.ReactNode;
  }) => (
    <a href={`${to}?ticket=${search.ticket}`} {...rest}>
      {children}
    </a>
  ),
}));

const audit = { data: undefined as unknown, isLoading: false, isError: false,
  error: undefined as unknown };

// What the page last asked the server for. The filter is only useful if the
// person picked reaches the query.
const asked = { filters: undefined as unknown };

vi.mock("@/query/ticket", () => ({
  useTicketAudit: (_page: number, _limit: number, filters: unknown) => {
    asked.filters = filters;
    return audit;
  },
  useAssignees: () => ({ data: [{ id: 4, name: "Sam Reid", assignable: true }] }),
}));

// Generated from, not hand-picked: every action the ticket module writes,
// read off the code that writes them. handoff.py writes create, lifecycle.py
// writes assign, status, priority, category, resolve and reopen, and
// views_admin.py writes delete. A pair of sample rows is how a column that
// has to work on all eight ends up covered on two.
const EVERY_ACTION = [
  "create",
  "assign",
  "status",
  "priority",
  "category",
  "resolve",
  "reopen",
  "delete",
] as const;

const PLAIN_ENGLISH = [
  ["a status change", { action: "status", beforeState: { status: "in_progress" },
    afterState: { status: "pending_user" } }, "In progress → Pending user"],
  ["a priority change", { action: "priority", beforeState: { priority: "low" },
    afterState: { priority: "high" } }, "Low → High"],
] as const;

import { TicketAuditPage } from "./TicketAuditPage";

function row(overrides: Record<string, unknown> = {}) {
  return {
    id: 1,
    ticketId: 42,
    action: "status",
    actor: { id: 4, name: "Sam Reid" },
    beforeState: { status: "open" },
    afterState: { status: "in_progress" },
    createdAt: "2026-09-01T09:00:00Z",
    ...overrides,
  };
}

function page(items: unknown[]) {
  return { items, total: items.length, page: 1, limit: 25, hasMore: false };
}

// One row per action, each about a different ticket.
function oneOfEach() {
  return EVERY_ACTION.map((action, index) =>
    row({ id: index + 1, ticketId: 100 + index, action,
          beforeState: {}, afterState: {} }),
  );
}

const openSelect = (name: RegExp) =>
  fireEvent.keyDown(screen.getByRole("combobox", { name }), { key: "ArrowDown" });

function cellsOfEachRow() {
  return screen
    .getAllByRole("row")
    .slice(1)
    .map((line) => within(line).getAllByRole("cell").map((c) => c.textContent));
}

describe("TicketAuditPage", () => {
  it("names a deleted ticket from the snapshot the deletion wrote", () => {
    /**
     * This is the whole reason the screen exists. The delete dialog promises
     * "a record of the deletion is kept in the history", and that history
     * used to live only inside the ticket's own detail panel — which 404s the
     * moment the ticket is gone. So the promise was true of the database and
     * false of the interface.
     *
     * The number cannot be read back off the ticket, because no queryset
     * returns it any more. It has to come out of the before-state the
     * deletion recorded, which is what this asserts.
     */
    audit.data = page([
      row({
        action: "delete",
        beforeState: {
          ticket_number: "SUP-2026-00042",
          subject: "Cannot access group workspace",
        },
        afterState: null,
      }),
    ]);
    render(<TicketAuditPage />);

    const [cells] = cellsOfEachRow();
    expect(cells[1]).toBe("#42");
    expect(cells[4]).toBe("SUP-2026-00042 · Cannot access group workspace");
    // And it is the one row with nothing to open. This row records the
    // ticket going away, so a link would send the reader after the very
    // thing the row says is gone. Rows about a ticket deleted later do link,
    // and land on the detail panel's "That ticket could not be opened. It
    // may have been deleted.", which is that panel answering on purpose.
    expect(screen.queryAllByRole("link")).toEqual([]);
  });

  it("still says something when a deletion recorded no snapshot", () => {
    // Older rows, or a deletion whose snapshot failed to write. A blank cell
    // reads like the screen is broken; this says what is known.
    audit.data = page([
      row({ id: 1, action: "delete", beforeState: null, afterState: null }),
      // Half a snapshot. Whichever half survived is still worth printing.
      row({ id: 2, action: "delete", afterState: null,
            beforeState: { subject: "Cannot access group workspace" } }),
    ]);
    render(<TicketAuditPage />);

    expect(cellsOfEachRow().map((cells) => cells[4])).toEqual([
      "Ticket removed from the queue",
      "Cannot access group workspace",
    ]);
  });

  it.each(PLAIN_ENGLISH)(
    "writes %s the way the rest of the product writes it",
    (_what, overrides, expected) => {
      /**
       * This screen exists to be read, so it must not be the one place that
       * prints database values. Every other place a status appears — the
       * queue badge, the dashboard axis, all three emails — says
       * "In progress", not "in_progress".
       */
      audit.data = page([row(overrides as Record<string, unknown>)]);
      render(<TicketAuditPage />);

      expect(screen.getByText(expected)).toBeTruthy();
    },
  );

  it("names the new owner instead of printing their id", () => {
    // The Who column beside this one already prints names, so "#4" here reads
    // as a different kind of thing entirely.
    audit.data = page([
      row({ action: "assign", beforeState: { assignee_id: null },
            afterState: { assignee_id: 4 } }),
    ]);
    render(<TicketAuditPage />);

    expect(screen.getByText("Owner set to Sam Reid")).toBeTruthy();
  });

  it("falls back to the id when that person is no longer on the roster", () => {
    // Poor, but better than a blank cell: the row still says what happened.
    audit.data = page([
      row({ action: "assign", beforeState: { assignee_id: null },
            afterState: { assignee_id: 99 } }),
    ]);
    render(<TicketAuditPage />);

    expect(screen.getByText("Owner set to #99")).toBeTruthy();
  });

  it("distinguishes handing a ticket back from picking one up", () => {
    /**
     * Both are an "assign" row, and reading the second as the first would
     * tell an agent somebody took a ticket that in fact nobody owns.
     *
     * Both directions in one render on purpose. With only the hand-back row
     * in the fixture, a summariser that called every assign row "Handed back
     * to the pool" passed this test — the sample it would have got wrong was
     * not there to get wrong.
     */
    audit.data = page([
      row({
        id: 1,
        action: "assign",
        beforeState: { assignee_id: 4 },
        afterState: { assignee_id: null },
      }),
      row({
        id: 2,
        action: "assign",
        beforeState: { assignee_id: null },
        afterState: { assignee_id: 4 },
      }),
    ]);
    render(<TicketAuditPage />);

    expect(screen.getByText("Handed back to the pool")).toBeTruthy();
    expect(screen.getByText("Owner set to Sam Reid")).toBeTruthy();
  });

  it("says which ticket every row is about, whatever the action was", () => {
    /**
     * The page listed when, what, who and what changed, and never which
     * ticket. "Resolved · Sana Reid · Pending user → Resolved" is a sentence
     * with no subject, and every row was one except the deletions, which name
     * their ticket out of the snapshot they had to write anyway.
     *
     * One row per action rather than a couple of samples. The number lives in
     * the snapshot for two of the eight and nowhere for the other six, so a
     * fixture of hand-picked rows is exactly how six of them stay uncovered.
     */
    audit.data = page(oneOfEach());
    render(<TicketAuditPage />);

    expect(cellsOfEachRow().map((cells) => cells[1])).toEqual(
      oneOfEach().map((line) => `#${line.ticketId}`),
    );
    // A column, not an extra cell per row. Dropping the heading alone leaves
    // five cells under four headings, which slides every value one column to
    // the left of the word that names it.
    expect(
      screen.getAllByRole("columnheader").map((head) => head.textContent),
    ).toEqual(["When", "Ticket", "Action", "Who", "What changed"]);
  });

  it("opens the ticket a row is about", () => {
    // The id was in the response all along and the queue already reads
    // ?ticket=, so the log needed the one thing that joins them up.
    audit.data = page(oneOfEach());
    render(<TicketAuditPage />);

    expect(
      screen.getAllByRole("link").map((link) => link.getAttribute("href")),
    ).toEqual(
      oneOfEach()
        .filter((line) => line.action !== "delete")
        .map((line) => `/tickets?ticket=${line.ticketId}`),
    );
  });

  it("gives one ticket one name, whatever the row records", () => {
    /**
     * The number is in the snapshot of a creation and of a deletion and
     * nowhere else. Naming those two by number and the other six by id
     * printed one ticket as SUP-2026-00250 on one row and #250 on the next,
     * with nothing on the screen saying the two rows were the same ticket.
     * The id is also the only one of the pair that every row carries, and the
     * two are not the same value: the counter restarts each year.
     *
     * The number is not dropped. A deletion still prints it under what
     * changed, that being the row whose ticket cannot be opened to read it.
     */
    audit.data = page([
      row({ id: 1, ticketId: 250, action: "resolve",
            beforeState: { status: "in_progress" },
            afterState: { status: "resolved" } }),
      row({ id: 2, ticketId: 250, action: "delete",
            beforeState: { ticket_number: "SUP-2026-00250",
                           subject: "Cannot access group workspace" },
            afterState: null }),
      row({ id: 3, ticketId: 251, action: "create", actor: null,
            beforeState: null,
            afterState: { channel: "ai_screening",
                          ticket_number: "SUP-2026-00251",
                          screening_category: "self_harm" } }),
    ]);
    render(<TicketAuditPage />);

    expect(cellsOfEachRow().map((cells) => cells[1])).toEqual([
      "#250",
      "#250",
      "#251",
    ]);
    expect(cellsOfEachRow().map((cells) => cells[4])).toEqual([
      "In progress → Resolved",
      "SUP-2026-00250 · Cannot access group workspace",
      "Flagged as Self harm",
    ]);
  });

  it("spans the whole table with the rows that stand in for data", () => {
    // Loading and empty each print one cell across the table. Both spans
    // were written for four columns, and the Ticket column made five: a span
    // left behind stops one column short of the edge.
    audit.isLoading = true;
    audit.data = undefined;
    const view = render(<TicketAuditPage />);

    expect(screen.getByText("Loading…").getAttribute("colspan")).toBe("5");

    audit.isLoading = false;
    audit.data = page([]);
    view.rerender(<TicketAuditPage />);

    expect(
      screen
        .getByText("Nothing recorded for this filter.")
        .getAttribute("colspan"),
    ).toBe("5");
  });

  it("tells a row the platform wrote apart from one whose account is gone", () => {
    /**
     * Two different things arrive as an empty actor. actor_user is SET_NULL,
     * so a row outlives the account that made it; and the screening handoff
     * writes its rows with no actor on purpose, because no person opened
     * those tickets. Calling the second one "Account removed" invented a
     * deleted account on the child-safety rows.
     *
     * Both kinds in one render on purpose. With only the screening row in the
     * fixture, printing "Automated screening" for every empty actor passes.
     */
    audit.data = page([
      row({ id: 1, action: "create", actor: null, beforeState: null,
            afterState: { channel: "ai_screening",
                          ticket_number: "SUP-2026-00262",
                          screening_category: "self_harm" } }),
      row({ id: 2, action: "resolve", actor: null,
            beforeState: { status: "in_progress" },
            afterState: { status: "resolved" } }),
    ]);
    render(<TicketAuditPage />);

    expect(screen.getByText("Automated screening")).toBeTruthy();
    expect(screen.getByText("Account removed")).toBeTruthy();
  });

  it("says why the screener raised a ticket", () => {
    // The row that most needs reading said "—". The verdict that raised it is
    // in the snapshot, and it is the only thing about that ticket this page
    // can show.
    audit.data = page([
      row({ action: "create", actor: null, beforeState: null,
            afterState: { channel: "ai_screening",
                          ticket_number: "SUP-2026-00262",
                          screening_category: "self_harm" } }),
    ]);
    render(<TicketAuditPage />);

    expect(screen.getByText("Flagged as Self harm")).toBeTruthy();
  });

  it("offers the requester who reopened their own ticket in the who filter", () => {
    /**
     * The list came from the assignee roster, which answers a different
     * question: who can be handed a ticket. A requester is never on it, and a
     * requester replying to a resolved ticket is what writes a reopen row, so
     * every reopen row named somebody the filter beside it could not select.
     */
    audit.data = page([
      row({ action: "reopen", actor: { id: 7, name: "Grace Okafor" },
            beforeState: { status: "resolved" }, afterState: { status: "open" } }),
    ]);
    render(<TicketAuditPage />);

    openSelect(/filter by who did it/i);

    expect(screen.getByRole("option", { name: "Grace Okafor" })).toBeTruthy();
    // Added to the roster, not swapped for it: an agent with no rows on this
    // page is still somebody worth filtering for.
    expect(screen.getByRole("option", { name: "Sam Reid" })).toBeTruthy();
  });

  it("asks the server for the person the reader picked, and for anyone again", () => {
    audit.data = page([
      row({ action: "reopen", actor: { id: 7, name: "Grace Okafor" } }),
    ]);
    render(<TicketAuditPage />);

    openSelect(/filter by who did it/i);
    fireEvent.click(screen.getByRole("option", { name: "Grace Okafor" }));
    expect(asked.filters).toEqual({ action: "", actor: "7" });

    openSelect(/filter by who did it/i);
    fireEvent.click(screen.getByRole("option", { name: "Anyone" }));
    expect(asked.filters).toEqual({ action: "", actor: "" });
  });

  it("keeps the person just picked on the list when nothing matches", () => {
    // Picking somebody leaves only their rows on screen, and picking them
    // with an action they never did leaves none at all. The list is built
    // from the rows, so the selection has to be held separately or the option
    // disappears out of the control it was picked in.
    audit.data = page([
      row({ action: "reopen", actor: { id: 7, name: "Grace Okafor" } }),
    ]);
    const view = render(<TicketAuditPage />);

    openSelect(/filter by who did it/i);
    fireEvent.click(screen.getByRole("option", { name: "Grace Okafor" }));

    audit.data = page([]);
    view.rerender(<TicketAuditPage />);
    openSelect(/filter by who did it/i);

    expect(screen.getByRole("option", { name: "Grace Okafor" })).toBeTruthy();
  });

  it("says why the Created filter is the empty one", () => {
    /**
     * Only the screening handoff writes a Created row. A ticket a requester
     * submits writes none, so this filter answers "nothing" on a platform
     * with a hundred tickets on it, and a bare empty table reads as a log
     * that has stopped recording.
     *
     * Both filters in one test: the sentence has to be about Created and not
     * about every empty result.
     */
    audit.data = page([]);
    render(<TicketAuditPage />);

    openSelect(/filter by action/i);
    fireEvent.click(screen.getByRole("option", { name: "Created" }));

    expect(
      screen.getByText(/Only the automated screening writes a Created row/),
    ).toBeTruthy();

    openSelect(/filter by action/i);
    fireEvent.click(screen.getByRole("option", { name: "Deleted" }));

    expect(screen.getByText("Nothing recorded for this filter.")).toBeTruthy();
  });

  it("tells the reader the record is about deletions surviving the ticket", () => {
    audit.data = page([]);
    render(<TicketAuditPage />);

    expect(
      screen.getByText(/A deleted ticket keeps its record here/),
    ).toBeTruthy();
  });

  it("tells a refused reader they lack access, not that something broke", () => {
    /**
     * The route only checks that somebody is signed in, so a student who
     * types this address reaches the page and the server answers 403.
     * "The audit log could not be loaded" sends them looking for a fault in a
     * product that is working exactly as intended.
     */
    audit.data = undefined;
    audit.isError = true;
    audit.error = { isAxiosError: true, response: { status: 403 } };
    render(<TicketAuditPage />);

    expect(screen.getByText(/You do not have access to the ticket audit/)).toBeTruthy();
    audit.isError = false;
    audit.error = undefined;
  });

  it("still reports a real fault as a fault", () => {
    audit.data = undefined;
    audit.isError = true;
    audit.error = { isAxiosError: true, response: { status: 500 } };
    render(<TicketAuditPage />);

    expect(screen.getByText("The audit log could not be loaded.")).toBeTruthy();
    audit.isError = false;
    audit.error = undefined;
  });
});

describe("the footer under the audit table", () => {
  /** A page of the log with more behind it than one page holds. */
  function bigLog(servedLimit: number) {
    return { items: [row()], total: 300, page: 1, limit: servedLimit,
             hasMore: true };
  }

  it("counts the pages on the size the server served, not the one asked for", () => {
    /**
     * views.py clamps limit to MAX_PAGE_SIZE, which is 100, and answers with
     * the size it actually used. The rows-per-page control offers 200 and a
     * custom box that reaches 500.
     *
     * Counting on the asked-for size called 300 rows two pages of 200 while
     * the server was sending three pages of 100, and the hundred rows past
     * the end of page 2 could be reached from nowhere in the footer.
     */
    audit.data = bigLog(100);
    const view = render(<TicketAuditPage />);

    openSelect(/rows per page/i);
    fireEvent.click(screen.getByRole("option", { name: "200 / page" }));
    view.rerender(<TicketAuditPage />);

    expect(screen.getByText("Page 1 of 3")).toBeTruthy();
  });

  it("shows the served size in the control, rather than the size refused", () => {
    // Left on 200 the control stands there naming a page size the server is
    // not honouring, on the same line as a page count that disagrees with it.
    audit.data = bigLog(100);
    const view = render(<TicketAuditPage />);

    openSelect(/rows per page/i);
    fireEvent.click(screen.getByRole("option", { name: "200 / page" }));
    view.rerender(<TicketAuditPage />);

    expect(
      screen.getByRole("combobox", { name: /rows per page/i }).textContent,
    ).toContain("100");
  });

  it("counts on the size asked for when the server has not answered yet", () => {
    // ⚠️ Load-bearing. There is no served size before the first response, and
    // a fallback of zero divides the total by nothing and offers Infinity
    // pages.
    audit.data = undefined;
    audit.isLoading = true;
    render(<TicketAuditPage />);

    expect(screen.getByText("Page 1 of 1")).toBeTruthy();
    audit.isLoading = false;
  });

  it("still gives a page to a log with nothing in it", () => {
    audit.data = { items: [], total: 0, page: 1, limit: 25, hasMore: false };
    render(<TicketAuditPage />);

    expect(screen.getByText("Page 1 of 1")).toBeTruthy();
  });
});

describe("the times the audit table prints", () => {
  it("names the time zone", () => {
    // Rendered in whatever zone the reader's machine is in, so the same row
    // reads 03:37 pm in Sydney and 02:37 am in Sao Paulo. This is the screen
    // people quote timestamps off when they compare notes about what
    // happened and when.
    const WHEN = "2026-09-01T09:00:00Z";
    audit.data = page([row({ createdAt: WHEN })]);
    render(<TicketAuditPage />);

    const stamp = {
      day: "numeric",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    } as const;
    // Built from the clock this machine is on rather than matched against a
    // list of zone spellings. The short name is "UTC" here, "AEST" in Sydney,
    // "GMT-3" in Sao Paulo and "GMT+5:30" in Kolkata, and a hand-written list
    // of those turns the suite red on whichever machine it happens to miss.
    const withoutZone = new Date(WHEN).toLocaleString("en-AU", stamp);
    const withZone = new Date(WHEN).toLocaleString("en-AU", {
      ...stamp,
      timeZoneName: "short",
    });

    const printed = screen.getAllByRole("cell")[0].textContent ?? "";
    expect(printed).toBe(withZone);
    // The zone name is an addition, not a replacement: the timestamp is still
    // in front of it, and there is something after it.
    expect(withZone.startsWith(withoutZone)).toBe(true);
    expect(printed).not.toBe(withoutZone);
  });
});
