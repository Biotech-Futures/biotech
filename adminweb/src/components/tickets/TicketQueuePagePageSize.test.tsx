/**
 * The queue's page count and rows-per-page control, against the size the
 * server actually served rather than the one the agent asked for.
 *
 * The admin queue endpoint clamps `limit` to MAX_PAGE_SIZE and answers with
 * the value it used — pinned on the server side by
 * tests/apps/tickets/test_api_admin.py::test_the_queue_echoes_the_limit_it_used_not_the_one_asked_for,
 * which writes 100 out rather than importing the constant. The cap is written
 * out here for the same reason: this file is about the client honouring what
 * it was served, and importing the number from either side would make the
 * test agree with a change nobody meant to make.
 *
 * Kept out of TicketQueuePage.test.tsx because these tests need a fake server
 * that honours the requested size and clamps it, and that file's mock ignores
 * the argument for its own twenty-eight tests.
 */
import { fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { PAGE_SIZE_PRESETS } from "@/components/user/PageSizeSelect";

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

/** What apps/tickets/views.py clamps `limit` to. Measured, not imported. */
const SERVER_CAP = 100;

/** The fake server's whole contract, and the only model of it in this file. */
const serverServes = (asked: number) => Math.min(asked, SERVER_CAP);

/**
 * What the footer must read. Written from the served size, and deliberately
 * not from anything the component computes.
 */
const truePageCount = (total: number, asked: number) =>
  Math.max(1, Math.ceil(total / serverServes(asked)));

const idle = { isLoading: false, isError: false };

const row = (id: number) => ({
  id,
  ticketNumber: `SUP-2026-${String(id).padStart(5, "0")}`,
  user: { name: "Mia", region: "Australia", anonymous: false },
  subject: `Enquiry ${id}`,
  status: "open",
  priority: "normal",
  category: "account_access",
  assignee: null,
  supportUpdatedAt: "2026-09-01T00:00:00Z",
  overdue: false,
});

/**
 * The queue the fake server is holding.
 *
 * `rowCap` exists only to keep eighty-odd renders cheap: the footer count, the
 * numbered nav and the control are a function of total / served / hasMore /
 * page and of nothing else on the response, so the sweep serves two rows a
 * page. The walk and the last-page click below serve full pages instead, and
 * they are the tests that read row numbers.
 */
let queueState: { total: number; rowCap: number; forceHasMore?: boolean } = {
  total: 0,
  rowCap: Infinity,
};
/** Every (page, limit) the component asked the server for, oldest first. */
const asked: { page: number; limit: number }[] = [];

vi.mock("@/query/ticket", () => ({
  useTicketsQuery: (page: number, limit: number) => {
    asked.push({ page, limit });
    const served = serverServes(limit);
    const start = (page - 1) * served;
    const remaining = Math.max(0, Math.min(served, queueState.total - start));
    const shown = Math.min(remaining, queueState.rowCap);
    return {
      ...idle,
      data: {
        items: Array.from({ length: shown }, (_, i) => row(start + i + 1)),
        total: queueState.total,
        page,
        // The point of the whole file: the server answers with the size it
        // used, which is not the size it was asked for.
        limit: served,
        hasMore: queueState.forceHasMore ?? start + remaining < queueState.total,
        asOf: "2026-09-06T05:00:00Z",
        after: remaining ? `2026-09-01T00:00:00Z_${start + remaining}` : null,
      },
    };
  },
  useTicketSummary: () => ({
    ...idle,
    data: { unassigned: 0, open: 0, pendingUser: 0, overdue: 0 },
  }),
  useAssignees: () => ({ ...idle, data: [] }),
  useTicketRegions: () => ({ ...idle, data: [] }),
  useBulkAssign: () => ({
    mutate: vi.fn(), reset: vi.fn(), isPending: false, isError: false,
    data: undefined, variables: undefined,
  }),
  useTicketDetail: () => ({ ...idle, data: undefined }),
  useTicketHistory: () => ({ ...idle, data: undefined }),
  useUpdateTicket: () => ({ mutate: vi.fn(), reset: vi.fn(), isPending: false, isError: false }),
  useDeleteTicket: () => ({ mutate: vi.fn(), reset: vi.fn(), isPending: false, isError: false }),
  useReplyTicket: () => ({ mutateAsync: vi.fn(), reset: vi.fn(), isPending: false, isError: false }),
}));

const { TicketQueuePage } = await import("./TicketQueuePage");

afterEach(() => {
  queueState = { total: 0, rowCap: Infinity };
  asked.length = 0;
});

/**
 * Type a rows-per-page size into the control.
 *
 * The queue opens on 10, which is not a preset, so the control is the custom
 * number box and typing the size then pressing Enter is the path a support
 * agent takes to reach 200 or 500. One call per render: once the control has
 * snapped to the dropdown it is a different widget.
 */
function setRowsPerPage(size: number) {
  const box = screen.getByLabelText("Rows per page") as HTMLInputElement;
  fireEvent.change(box, { target: { value: String(size) } });
  fireEvent.keyDown(box, { key: "Enter" });
}

/** The exact footer sentence, so a wrong number cannot pass on a substring. */
function footer() {
  return screen.getByText(/^Page \d+ of \d+$/).textContent;
}

/** What the rows-per-page control is claiming, in either of its two shapes. */
function rowsPerPageReads() {
  const control = screen.getByLabelText("Rows per page");
  return control.tagName === "INPUT"
    ? (control as HTMLInputElement).value
    : (control.textContent ?? "").replace(/\s*\/\s*page$/, "").trim();
}

/** The numbered buttons in the footer nav, in order, as they read. */
function pageNumbers() {
  const nav = screen.getByRole("navigation", { name: "Pagination" });
  return Array.from(nav.querySelectorAll("button"))
    .map((b) => b.textContent ?? "")
    .filter((label) => /^\d+$/.test(label));
}

function ticketNumbersOnScreen() {
  return Array.from(document.body.textContent?.matchAll(/SUP-2026-\d{5}/g) ?? [])
    .map((m) => m[0]);
}

/**
 * The sizes and totals the sweep covers, generated rather than listed.
 *
 * Sizes: every preset the control offers, plus the top of the custom box, plus
 * two sizes under the cap that are not presets. Taking the presets from the
 * control means a preset added later is covered without anyone remembering to
 * come back here.
 *
 * Totals: built around each size's *served* page boundary — a page short of
 * one, exactly one, one over, and the same at two and four pages — because
 * that is where a page count is wrong by one and nobody notices.
 */
const SIZES = [...PAGE_SIZE_PRESETS, 500, 33, 7];
const CASES = SIZES.flatMap((size) =>
  [0, 1, 2, 4].flatMap((pages) =>
    [-1, 0, 1].map((delta) => pages * serverServes(size) + delta),
  )
    .filter((total) => total >= 1)
    .map((total) => ({ size, total })),
);

describe("the page count the queue prints", () => {
  it("covers every rows-per-page size the control offers", () => {
    // Guards the generator itself. Both expectations are written out by
    // hand, because deriving either from SIZES or PAGE_SIZE_PRESETS compared
    // the generator to itself: shrinking PAGE_SIZE_PRESETS to [25] deleted
    // thirty cases — every requested-200 case among them, which is the size
    // the defect was measured at — and this test stayed green.
    expect(SIZES).toEqual(expect.arrayContaining([25, 50, 100, 200, 500]));
    expect(CASES.length).toBeGreaterThanOrEqual(70);
    expect(CASES.some(({ size }) => size > SERVER_CAP)).toBe(true);
    expect(CASES.some(({ size }) => size < SERVER_CAP)).toBe(true);
  });

  it.each(CASES)(
    "counts $total tickets at a requested $size by the size the server served",
    ({ size, total }) => {
      queueState = { total, rowCap: 2 };
      render(<TicketQueuePage />);
      setRowsPerPage(size);

      const expected = truePageCount(total, size);
      expect(footer()).toBe(`Page 1 of ${expected}`);
      // The control reads the size that was ASKED for, which is the size the
      // server is not honouring. That is deliberate and it is the half of the
      // finding left unfixed: a control fed the served value cannot be set
      // back to the value it is displaying. Pinned here so the trade-off is a
      // decision on the record rather than a drift.
      expect(rowsPerPageReads()).toBe(String(size));
      // The pinned last-page button is the control an agent uses to reach the
      // end of a long queue, so it has to name the real last page.
      expect(pageNumbers().at(-1)).toBe(String(expected));
      // And the component must really have asked for the agent's size: a
      // client that quietly sent 100 would pass every line above.
      expect(asked.at(-1)).toEqual({ page: 1, limit: size });
    },
  );
});

describe("walking a queue deeper than the server's page cap", () => {
  it("never misstates the count on any page of the walk", () => {
    // 450 at a requested 200 is the case measured live: the footer read
    // "Page 1 of 3, 2 of 3, 3 of 4, 4 of 5, 5 of 5" — wrong on four of five.
    queueState = { total: 450, rowCap: Infinity };
    render(<TicketQueuePage />);
    setRowsPerPage(200);

    const expected = truePageCount(450, 200);
    const walk: string[] = [];
    for (let i = 1; i <= expected; i++) {
      walk.push(String(footer()));
      const next = screen.getByRole("button", { name: "Next" }) as HTMLButtonElement;
      if (i < expected) {
        expect(next.disabled).toBe(false);
        fireEvent.click(next);
      }
    }

    expect(walk).toEqual(
      Array.from({ length: expected }, (_, i) => `Page ${i + 1} of ${expected}`),
    );
    expect(
      (screen.getByRole("button", { name: "Next" }) as HTMLButtonElement).disabled,
    ).toBe(true);
  });

  it("sends the pinned last-page button to the last rows, not to the middle", () => {
    // Live at 450/200 the pinned button read "3"; clicking it moved the reader
    // to rows 201-300 of 450 while the footer re-labelled to "Page 3 of 4".
    queueState = { total: 450, rowCap: Infinity };
    render(<TicketQueuePage />);
    setRowsPerPage(200);

    const nav = screen.getByRole("navigation", { name: "Pagination" });
    const last = truePageCount(450, 200);
    const pinned = within(nav).getByRole("button", { name: `Go to page ${last}` });
    fireEvent.click(pinned);

    expect(footer()).toBe(`Page ${last} of ${last}`);
    // The last row of the queue, which is the row an agent clicks that button
    // to reach.
    expect(ticketNumbersOnScreen().at(-1)).toBe("SUP-2026-00450");
    expect(ticketNumbersOnScreen().at(0)).toBe("SUP-2026-00401");
  });
});

describe("the floor the walk's frozen total needs", () => {
  it("still counts a page past the end when the server says there is more", () => {
    // Unrelated to the clamp and easy to break while changing the divisor:
    // `total` counts the walk's frozen set, and a ticket somebody works
    // mid-walk leaves it, so the count can fall below the page being read.
    // hasMore is the floor that keeps Next alive with rows still ahead.
    queueState = { total: 25, rowCap: Infinity };
    render(<TicketQueuePage />);
    setRowsPerPage(10);
    expect(footer()).toBe("Page 1 of 3");

    // Somebody worked every row the walk had counted ahead of the reader, so
    // page two comes back with a total behind the page being read and hasMore
    // still true.
    queueState = { total: 5, rowCap: Infinity, forceHasMore: true };
    fireEvent.click(screen.getByRole("button", { name: "Next" }));

    // ceil(5/10) = 1, but the reader is standing on page 2 with more behind
    // it, so the floor has to carry the count to 3.
    expect(footer()).toBe("Page 2 of 3");
    expect(
      (screen.getByRole("button", { name: "Next" }) as HTMLButtonElement).disabled,
    ).toBe(false);
  });
});
