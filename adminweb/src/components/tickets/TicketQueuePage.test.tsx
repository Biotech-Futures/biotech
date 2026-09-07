import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// Same shape as the home page's test: the router is only here for navigation
// and Link rendering, neither of which this file is about.
vi.mock("@tanstack/react-router", () => ({
  getRouteApi: () => ({
    useSearch: () => ({ ticket: undefined }),
    useNavigate: () => vi.fn(),
  }),
  Link: ({ to, children }: { to: string; children: React.ReactNode }) => (
    <a href={to}>{children}</a>
  ),
}));

vi.mock("@/provider/AuthProvider", () => ({
  useAuthContext: () => ({ user: { name: "Ada", isAdmin: true, isSupport: true } }),
}));

const bulkAssign = {
  mutate: vi.fn(),
  reset: vi.fn(),
  isPending: false,
  isError: true,
  data: undefined as { results: { ticketId: number; ok: boolean; error?: string }[] } | undefined,
  // What the last batch asked for. react-query keeps it on the result, and it
  // is the only thing on this page that can tell a failed assign from a failed
  // hand-back once the bar has moved on.
  variables: undefined as { ticketIds: number[]; assigneeId: number | null } | undefined,
};

const idle = { data: undefined, isLoading: false, isError: false };

const ROW = {
  id: 1,
  ticketNumber: "SUP-2026-00001",
  user: { name: "Mia", region: "Australia", anonymous: false },
  subject: "Poster upload fails",
  status: "open",
  priority: "normal",
  category: "account_access",
  assignee: null,
  supportUpdatedAt: "2026-09-01T00:00:00Z",
  overdue: false,
};

const WALK = { asOf: "2026-09-06T05:00:00Z", after: "2026-09-01T00:00:00Z_1" };

const firstPage = {
  ...idle,
  data: { items: [ROW], total: 25, page: 1, limit: 10, hasMore: true, ...WALK },
};

// Page two after somebody worked every row in front of the reader: they left
// the frozen set the walk is reading, so the page comes back with nothing on
// it while the frozen total still counts them.
const emptySecondPage = {
  ...idle,
  data: {
    items: [] as (typeof ROW)[],
    total: 25,
    page: 2,
    limit: 10,
    hasMore: false,
    asOf: WALK.asOf,
    after: null,
  },
};

// What the queue was actually asked for, oldest first. A card shortcut is only
// worth something if its filter reaches the request.
const queueCalls: { page: number; filters: Record<string, string> }[] = [];

// The same calls with the paging cursor attached, kept apart so the four
// filter assertions above can go on comparing whole objects.
type Walk = { asOf: string; after: string } | undefined;
const walkCalls: { page: number; walk: Walk }[] = [];

// Per-page responses for the tests that walk further than page two. Empty by
// default, which leaves the two fixtures above answering everything.
type QueuePage = {
  items: (typeof ROW)[];
  total: number;
  page: number;
  limit: number;
  hasMore: boolean;
  asOf: string;
  after: string | null;
};
const responses: Record<
  number,
  { data: QueuePage; isLoading: boolean; isError: boolean }
> = {};

const SUPPORT_AGENTS = [{ id: 9, name: "Sam Reid", assignable: true }];
const assignees = {
  ...idle,
  data: SUPPORT_AGENTS as typeof SUPPORT_AGENTS | undefined,
};
const regions = { ...idle, data: [] as { value: string; label: string }[] };

vi.mock("@/query/ticket", () => ({
  useTicketsQuery: (
    page: number,
    _limit: number,
    filters: Record<string, string>,
    walk: Walk,
  ) => {
    queueCalls.push({ page, filters });
    walkCalls.push({ page, walk });
    return responses[page] ?? (page === 1 ? firstPage : emptySecondPage);
  },
  useTicketSummary: () => ({ ...idle, data: { unassigned: 1, open: 1, pendingUser: 0, overdue: 0 } }),
  useAssignees: () => assignees,
  useTicketRegions: () => regions,
  useBulkAssign: () => bulkAssign,
  useTicketDetail: () => ({ ...idle }),
  useTicketHistory: () => ({ ...idle }),
  useUpdateTicket: () => ({ mutate: vi.fn(), reset: vi.fn(), isPending: false, isError: false }),
  useDeleteTicket: () => ({ mutate: vi.fn(), reset: vi.fn(), isPending: false, isError: false }),
  useReplyTicket: () => ({ mutateAsync: vi.fn(), reset: vi.fn(), isPending: false, isError: false }),
}));

const { TicketQueuePage } = await import("./TicketQueuePage");

function selectTheOnlyRow() {
  // The row checkbox, not the header one: the header toggles the whole page
  // and this is about one batch.
  const boxes = screen.getAllByRole("checkbox");
  fireEvent.click(boxes[boxes.length - 1]);
}

const FAILURE = /Could not assign the selected tickets/;

afterEach(() => {
  // Shared by every test in the file, so a leftover value from one of them
  // would decide the next one.
  bulkAssign.data = undefined;
  bulkAssign.variables = undefined;
  assignees.isError = false;
  assignees.data = SUPPORT_AGENTS;
  regions.isError = false;
  queueCalls.length = 0;
  walkCalls.length = 0;
  for (const key of Object.keys(responses)) delete responses[Number(key)];
  firstPage.data.items = [ROW];
});

describe("the bulk assign failure message", () => {
  beforeEach(() => {
    bulkAssign.reset.mockClear();
  });

  it("appears while the batch it describes is still selected", () => {
    render(<TicketQueuePage />);
    selectTheOnlyRow();

    expect(screen.getByText(FAILURE)).toBeTruthy();
  });

  it("goes away with the selection rather than outliving it", () => {
    // It used to render outside the `selectedIds.length > 0` block, so an
    // agent who cleared the selection was left reading a warning about a
    // batch that was no longer there.
    render(<TicketQueuePage />);
    selectTheOnlyRow();

    fireEvent.click(screen.getByRole("button", { name: /clear/i }));

    expect(screen.queryByText(FAILURE)).toBeNull();
  });

  it("resets the mutation when the agent clears the selection", () => {
    // Hiding it is not enough on its own: the guard would bring the same
    // message straight back the moment a different batch is picked, reading
    // as though the new selection had failed too, before anything was sent.
    render(<TicketQueuePage />);
    selectTheOnlyRow();

    fireEvent.click(screen.getByRole("button", { name: /clear/i }));

    expect(bulkAssign.reset).toHaveBeenCalled();
  });
});

describe("the counter cards", () => {
  it("explains Overdue by the rule the counter actually uses", () => {
    // The client replaced the first-response test on 2026-09-04: the clock
    // restarts every time the requester writes back, so a ticket support has
    // already answered can be overdue. The card used to say the opposite of
    // the number printed above it.
    render(<TicketQueuePage />);

    expect(
      screen.getByText("Waiting on support for longer than its priority allows"),
    ).toBeTruthy();
    expect(screen.queryByText(/first reply/i)).toBeNull();
  });

  it("takes the agent to the tickets the Open card counts", () => {
    render(<TicketQueuePage />);

    fireEvent.click(screen.getByRole("button", { name: "Open" }));

    expect(queueCalls[queueCalls.length - 1]).toEqual({
      page: 1,
      filters: { status: "open" },
    });
  });

  it("takes the agent to the tickets the Pending user card counts", () => {
    render(<TicketQueuePage />);

    fireEvent.click(screen.getByRole("button", { name: "Pending user" }));

    expect(queueCalls[queueCalls.length - 1]).toEqual({
      page: 1,
      filters: { status: "pending_user" },
    });
  });

  it("takes the agent to the tickets the Unassigned card counts", () => {
    render(<TicketQueuePage />);

    fireEvent.click(screen.getByRole("button", { name: "Unassigned" }));

    expect(queueCalls[queueCalls.length - 1]).toEqual({
      page: 1,
      filters: { assignee: "__unassigned__" },
    });
  });

  it("leaves Overdue as a number, because no filter reproduces it", () => {
    // The queue endpoint has no overdue parameter: it is worked out per row
    // as the page is served. A card that navigated to a filter the server
    // ignores would list the whole queue and claim it was the overdue part.
    render(<TicketQueuePage />);

    expect(screen.queryByRole("button", { name: "Overdue" })).toBeNull();
  });
});

describe("an empty page", () => {
  it("does not claim nothing matches when the rows ahead were worked", () => {
    // The walk is frozen at the moment it began, and a ticket somebody works
    // leaves that frozen set. The rows this page was going to show still
    // match the filters perfectly well; they are just at the front now.
    render(<TicketQueuePage />);

    fireEvent.click(screen.getByRole("button", { name: "Next" }));

    expect(
      screen.getByText(
        "Nothing left on this page. The tickets that were here have been worked on since you opened the queue, which moves them to the front of it. Go back to page 1 to see them.",
      ),
    ).toBeTruthy();
    expect(screen.queryByText(/no tickets match these filters/i)).toBeNull();
  });

  it("still says nothing matches when the first page comes back empty", () => {
    firstPage.data.items = [];

    render(<TicketQueuePage />);

    expect(screen.getByText("No tickets match these filters.")).toBeTruthy();
  });

  it("says nothing matches when a page reached by its number is empty", () => {
    // Clicking a page number is not continuing the walk. The cursors are
    // dropped and the page is read from a fresh snapshot, so an empty one
    // there is no evidence that the rows ahead were worked, and telling the
    // agent to go back to page 1 to find them is a guess.
    render(<TicketQueuePage />);

    fireEvent.click(screen.getByRole("button", { name: "Go to page 3" }));

    expect(screen.getByText("No tickets match these filters.")).toBeTruthy();
    expect(screen.queryByText(/go back to page 1/i)).toBeNull();
  });
});

describe("paging backwards", () => {
  // Four pages of one row each, each handing out the cursor for the one after
  // it, all under one snapshot. Fixed strings rather than anything read off a
  // clock: what is asserted is which cursor was sent, not when. `total` is
  // four pages' worth so the footer offers all four numbers from the start.
  const fourPageWalk = () => {
    const last = 4;
    for (let n = 1; n <= last; n++) {
      responses[n] = {
        ...idle,
        data: {
          items: [{ ...ROW, id: n, ticketNumber: `SUP-2026-0000${n}` }],
          total: last * 10,
          page: n,
          limit: 10,
          hasMore: n < last,
          asOf: WALK.asOf,
          after: n < last ? `cursor-after-page-${n}` : null,
        },
      };
    }
  };

  const lastAsk = () => walkCalls[walkCalls.length - 1];

  // One entry per page the reader landed on. A render can ask the hook more
  // than once for the same page and the same cursor, and that is not what any
  // of this is about.
  const trace = () =>
    walkCalls.filter(
      (call, i) =>
        i === 0 || JSON.stringify(call) !== JSON.stringify(walkCalls[i - 1]),
    );

  it("reads backwards from a fresh snapshot, not from a held cursor", () => {
    // Only Next continues the walk. Previous is a jump, and a jump drops the
    // cursors and reads by offset out of a new snapshot.
    //
    // Reaching page N-1 with the cursor page N-2 handed out was tried and
    // reverted, so this pins the route rather than leaving it to whichever
    // reading of the module docstring the next person arrives with. It does
    // not remove the repeats, it moves them: measured against the queue
    // endpoint, 220 tickets ten to a page with three worked behind the
    // reader, the cursor route repeated six rows across pages where the
    // offset route repeated three. Rows leaving the snapshot shrink it, so an
    // old cursor pulls the following page's rows up into the gap.
    //
    // Neither route loses a row. That is the property the snapshot is for,
    // and it is the one to protect if this is ever revisited.
    fourPageWalk();
    render(<TicketQueuePage />);

    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    fireEvent.click(screen.getByRole("button", { name: "Previous" }));
    fireEvent.click(screen.getByRole("button", { name: "Next" }));

    const afterPage = (n: number) => ({
      asOf: WALK.asOf,
      after: `cursor-after-page-${n}`,
    });
    expect(trace()).toEqual([
      { page: 1, walk: undefined },
      { page: 2, walk: afterPage(1) },
      { page: 3, walk: afterPage(2) },
      { page: 2, walk: undefined },
      { page: 3, walk: afterPage(2) },
    ]);
  });

  it("reads page one live, because no cursor points at it", () => {
    // There is no cursor for the first page and there never will be. Sending
    // a stale one would serve page two under page one's number.
    fourPageWalk();
    render(<TicketQueuePage />);

    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    fireEvent.click(screen.getByRole("button", { name: "Previous" }));

    expect(lastAsk()).toEqual({ page: 1, walk: undefined });
  });

  it("does not carry the old cursors past a fresh read of page one", () => {
    // Page one is answered live, so the walk that reached page two is over
    // and its cursors describe a snapshot nothing on screen is reading any
    // more. They are normally overwritten by page one's own response, but a
    // page that hands out no cursor cannot overwrite anything: here every row
    // on page one was worked while the reader was on page two, so the reply
    // comes back empty and there is nothing to replace them with.
    fourPageWalk();
    render(<TicketQueuePage />);

    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    responses[1] = {
      ...idle,
      data: { ...responses[1].data, items: [], hasMore: false, after: null },
    };
    fireEvent.click(screen.getByRole("button", { name: "Previous" }));
    fireEvent.click(screen.getByRole("button", { name: "Next" }));

    expect(lastAsk()).toEqual({ page: 2, walk: undefined });
  });

  it("still reads a page chosen by its number from a fresh snapshot", () => {
    // Skipping pages is the reader saying they do not want the walk, and two
    // pages back is a jump the same way two pages forward is. The cursor for
    // page 2 is sitting in the map here, left by the walk out to page 4, so
    // "whichever pages we happen to hold a cursor for" would answer this one
    // out of a snapshot several minutes old.
    fourPageWalk();
    render(<TicketQueuePage />);

    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    fireEvent.click(screen.getByRole("button", { name: "Go to page 2" }));

    expect(lastAsk()).toEqual({ page: 2, walk: undefined });
  });
});

describe("the last activity column", () => {
  it("names the time zone it is printing", () => {
    // Rendered in the reader's own zone, so the same row is 03:37 pm in
    // Sydney and 02:37 am in Sao Paulo. Agents read these times to each other
    // and compare them against the overdue windows.
    render(<TicketQueuePage />);

    const cells = screen.getAllByRole("cell");
    const lastActivity = cells[cells.length - 1].textContent ?? "";

    // Built from the clock this machine is on rather than matched against a
    // list of zone spellings. The short name is "UTC" here, "AEST" in Sydney,
    // "GMT-3" in Sao Paulo and "GMT+5:30" in Kolkata, and a hand-written list
    // of those turns the suite red on whichever machine it happens to miss.
    const stamp = {
      day: "numeric",
      month: "short",
      hour: "2-digit",
      minute: "2-digit",
    } as const;
    const withoutZone = new Date(ROW.supportUpdatedAt).toLocaleString(
      "en-AU",
      stamp,
    );
    const withZone = new Date(ROW.supportUpdatedAt).toLocaleString("en-AU", {
      ...stamp,
      timeZoneName: "short",
    });

    expect(lastActivity).toBe(withZone);
    // The zone name is an addition, not a replacement: the timestamp is still
    // in front of it, and there is something after it.
    expect(withZone.startsWith(withoutZone)).toBe(true);
    expect(lastActivity).not.toBe(withoutZone);
  });
});

describe("the filter option lists", () => {
  it("says so when the assignee list could not be loaded", () => {
    // An empty dropdown is indistinguishable from a platform with nobody on
    // it, and the same query feeds the assign controls further down.
    assignees.isError = true;

    render(<TicketQueuePage />);

    expect(
      screen.getByText(
        "The assignee list could not be loaded. The filters above are missing those choices, and so are the assign controls on this page. Reload to try again.",
      ),
    ).toBeTruthy();
  });

  it("says so when the region list could not be loaded", () => {
    // The other half of the same hole. Regions fail on their own endpoint.
    regions.isError = true;

    render(<TicketQueuePage />);

    expect(
      screen.getByText(
        "The region list could not be loaded. The filters above are missing those choices. Reload to try again.",
      ),
    ).toBeTruthy();
    // The assignee list is fine, so its dropdowns are full. Naming them here
    // would send the agent looking for a fault that is not there.
    expect(screen.queryByText(/assign controls/i)).toBeNull();
  });

  it("names both lists when both endpoints are down", () => {
    assignees.isError = true;
    regions.isError = true;

    render(<TicketQueuePage />);

    expect(
      screen.getByText(
        "The assignee and region lists could not be loaded. The filters above are missing those choices, and so are the assign controls on this page. Reload to try again.",
      ),
    ).toBeTruthy();
  });

  it("says nothing while both lists are fine", () => {
    render(<TicketQueuePage />);

    expect(screen.queryByText(/could not be loaded/i)).toBeNull();
  });
});

describe("handing a batch back to the pool", () => {
  // Radix opens a Select on pointerdown, and jsdom gives its handler neither a
  // real PointerEvent nor pointer capture, so the trigger stays shut and every
  // assertion below would pass vacuously. ArrowDown is a documented way in.
  const openAssignTo = () =>
    fireEvent.keyDown(screen.getByRole("combobox", { name: /assign to/i }), {
      key: "ArrowDown",
    });

  it("sends a null assignee, which is what the endpoint reads as the pool", () => {
    // The whole point of the option: the serializer has taken null since it
    // was written and three backend tests pin it, but the only control that
    // could ask for it was the one-ticket panel.
    bulkAssign.mutate.mockClear();
    render(<TicketQueuePage />);
    selectTheOnlyRow();

    openAssignTo();
    fireEvent.click(screen.getByRole("option", { name: "Unassigned" }));
    fireEvent.click(screen.getByRole("button", { name: /^unassign$/i }));

    expect(bulkAssign.mutate.mock.calls[0][0]).toEqual({
      ticketIds: [1],
      assigneeId: null,
    });
  });

  it("does not blame the person nobody picked when it fails", () => {
    // The assign wording sends the agent checking whether somebody still has
    // the support role, and on a hand-back there is no somebody.
    bulkAssign.variables = { ticketIds: [1], assigneeId: null };

    render(<TicketQueuePage />);
    selectTheOnlyRow();

    expect(
      screen.getByText(
        "Could not hand the selected tickets back to the pool. Nothing was changed. Try again.",
      ),
    ).toBeTruthy();
    expect(screen.queryByText(FAILURE)).toBeNull();
  });

  it("keeps the assign wording when a person was picked", () => {
    bulkAssign.variables = { ticketIds: [1], assigneeId: 9 };

    render(<TicketQueuePage />);
    selectTheOnlyRow();

    expect(screen.getByText(FAILURE)).toBeTruthy();
  });

  it("says the assignee list is down inside the dropdown as well", () => {
    // The banner above says it once for the page. The dropdown needs it too
    // now: the pool line is always offered, so a dead endpoint leaves it
    // opening on one plausible option instead of on nothing at all.
    // A failed query has no data, so the list of people really is empty here.
    assignees.isError = true;
    assignees.data = undefined;

    render(<TicketQueuePage />);
    selectTheOnlyRow();
    openAssignTo();

    expect(
      screen.getByText(
        "The assignee list could not be loaded, so there is nobody to pick here. Reload to try again.",
      ),
    ).toBeTruthy();
  });
});

describe("a bulk assign that partly failed", () => {
  it("names the tickets it could not assign, by number and reason", () => {
    // The response identifies them by internal id, which appears nowhere an
    // agent can see. A bare "1 of 2 could not be assigned" leaves them
    // re-selecting the whole batch to work out which one.
    bulkAssign.data = {
      results: [
        { ticketId: 1, ok: false, error: "not found" },
        { ticketId: 2, ok: true },
      ],
    };

    render(<TicketQueuePage />);

    const message = screen.getByText(/could not be assigned/);
    expect(message.textContent?.replace(/\s+/g, " ")).toBe(
      "1 of 2 could not be assigned: SUP-2026-00001 (not found). Tickets " +
        "deleted while they sat in the selection come back as not found, and " +
        "sending the batch again will not change that.",
    );
  });

  it("does not call a second try pointless when a retry could work", () => {
    // bulk_assign fails two ways. A row that is gone comes back as "not
    // found" and no amount of retrying brings it back; anything the write
    // itself throws comes back as the exception text, and that one can come
    // good on a second try. One of each here, so the sentence about deleted
    // tickets is true of half the batch and must not be printed.
    firstPage.data.items = [
      ROW,
      { ...ROW, id: 2, ticketNumber: "SUP-2026-00002" },
    ];
    bulkAssign.data = {
      results: [
        { ticketId: 1, ok: false, error: "not found" },
        { ticketId: 2, ok: false, error: "deadlock detected" },
      ],
    };

    render(<TicketQueuePage />);

    const message = screen.getByText(/could not be assigned/);
    expect(message.textContent?.replace(/\s+/g, " ")).toBe(
      "2 of 2 could not be assigned: SUP-2026-00001 (not found); " +
        "SUP-2026-00002 (deadlock detected).",
    );
  });

  it("gives a reason even when the server sent an empty one", () => {
    // The reason is an optional string on the wire, and an exception with no
    // message serialises to "" rather than to nothing.
    bulkAssign.data = { results: [{ ticketId: 1, ok: false, error: "" }] };

    render(<TicketQueuePage />);

    const message = screen.getByText(/could not be assigned/);
    expect(message.textContent?.replace(/\s+/g, " ")).toBe(
      "1 of 1 could not be assigned: SUP-2026-00001 (no reason given).",
    );
  });

  it("says nothing when every ticket in the batch was assigned", () => {
    bulkAssign.data = { results: [{ ticketId: 1, ok: true }] };

    render(<TicketQueuePage />);

    expect(screen.queryByText(/could not be assigned/)).toBeNull();
  });
});
