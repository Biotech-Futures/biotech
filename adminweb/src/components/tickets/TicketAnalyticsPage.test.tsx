import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ticketAnalyticsSchema } from "@/schema/ticket";

// recharts measures its container and renders nothing at zero width, which is
// what jsdom reports for everything. Stubbed to a marker so these tests are
// about the page's own decisions — what it labels, and what it refuses to
// claim — rather than about whether a chart library draws in a headless DOM.
vi.mock("@/components/tickets/MeasureBars", () => ({
  // The page draws four of these. The breakdown chart is the only one given a
  // unit, which is what the tests below read it back by.
  MeasureBars: ({
    rows,
    unit,
  }: {
    rows: { label: string; value: number }[];
    unit?: string;
  }) => (
    <div data-testid={unit ? "segment-bars" : "bars"}>
      {rows.map((r) => `${r.label}:${r.value}`).join(" ")}
    </div>
  ),
}));

const analytics = { data: undefined as unknown, isLoading: false, isError: false,
  error: undefined as unknown };

// The roster the assignee breakdown reads names out of. Sana Reid is id 11
// because that is the id the assignee chart was labelling its bars with.
const roster = [{ id: 11, name: "Sana Reid", assignable: true }];

// Shaped like the query result rather than like its data, because this request
// can fail on its own while the numbers arrive fine, and that is a state the
// page has something to say about.
const people = { data: roster as unknown, isError: false };

vi.mock("@/query/ticket", () => ({
  useTicketAnalytics: () => analytics,
  useAssignees: () => people,
}));

import { TicketAnalyticsPage } from "./TicketAnalyticsPage";

/**
 * Every fixture goes through the real schema.
 *
 * The first version of this file hand-wrote the payload and got five keys
 * wrong — `demand.total` for `demand.volume`, `flow.unassigned` for
 * `flow.unassignedBacklog`, no `answeredCount` or `resolvedCount` at all. The
 * page rendered the literal string "undefined" in four places and all five
 * tests passed, because they only asserted the four section headings and
 * never a number.
 *
 * Parsing here is what makes that impossible: a fixture that does not match
 * what the endpoint actually returns now fails in the fixture, not silently
 * in the assertions.
 */
/**
 * What `GET /admin/tickets/analytics/` advertises, in its order.
 *
 * This list used to be written out inline and stopped at six, one short of
 * what the endpoint sends, so `priority` was never in a fixture and the
 * dropdown shipped showing it as its own database key. A longer hand-written
 * list is not the fix, because the next dimension is not on it either. What
 * the fix is rests on is that the page derives every label rather than
 * looking it up, which the first test below pins by asking it for a
 * dimension nobody has written yet.
 */
const DIMENSIONS = [
  "region",
  "userType",
  "category",
  "status",
  "assignee",
  "channel",
  "priority",
];

const breakdown = () =>
  screen.getByRole("combobox", { name: /break down by/i });

const chooseDimension = (name: string) => {
  fireEvent.keyDown(breakdown(), { key: "ArrowDown" });
  fireEvent.click(screen.getByRole("option", { name }));
};

function payload(overrides: Record<string, unknown> = {}) {
  return ticketAnalyticsSchema.parse({
    window: { from: null, to: null },
    demand: {
      volume: 7,
      categoryMix: [{ value: "account_access", count: 4 }],
      channelMix: [{ value: "portal", count: 7 }],
    },
    flow: {
      unassignedBacklog: 2,
      ageByStatus: [{ status: "open", averageSeconds: 3600 }],
      reopens: 11,
      handOffs: 12,
    },
    service: {
      firstResponseSeconds: 1800,
      answeredCount: 5,
      resolutionSeconds: 7200,
      resolvedCount: 3,
      overdue: 13,
    },
    quality: {
      resolutionRate: 0.5,
      resolvedCount: 4,
      totalCount: 8,
      repeatContacts: 9,
      satisfaction: null,
      satisfactionAvailable: false,
    },
    segment: { dimension: "region", buckets: [{ value: "Australia", count: 5 }] },
    dimensions: DIMENSIONS,
    ...overrides,
  });
}

describe("TicketAnalyticsPage", () => {
  it("names the four questions the client wrote on p52", () => {
    analytics.data = payload();
    render(<TicketAnalyticsPage />);

    // The page is organised by the client's own four groups, and each carries
    // the question they wrote above it. Losing the questions would leave a
    // wall of numbers that answers nothing in particular.
    expect(screen.getByText(/Demand · what help is being requested/)).toBeTruthy();
    expect(screen.getByText(/Flow · where does work slow down/)).toBeTruthy();
    expect(screen.getByText(/Service · how quickly do we respond/)).toBeTruthy();
    expect(screen.getByText(/Quality · did the support help/)).toBeTruthy();
  });

  it("renders the numbers, not the string undefined", () => {
    // The assertion the first version of this file was missing entirely.
    analytics.data = payload();
    const { container } = render(<TicketAnalyticsPage />);

    // Every number in the fixture is distinct, so each of these picks out
    // exactly one tile.
    expect(container.textContent).not.toContain("undefined");
    expect(screen.getByText("7")).toBeTruthy();  // demand.volume
    expect(screen.getByText("2")).toBeTruthy();  // flow.unassignedBacklog
    expect(screen.getByText("11")).toBeTruthy(); // flow.reopens
    expect(screen.getByText("12")).toBeTruthy(); // flow.handOffs
    expect(screen.getByText("13")).toBeTruthy(); // service.overdue
    expect(screen.getByText("9")).toBeTruthy();  // quality.repeatContacts
  });

  it("says satisfaction was never collected rather than showing a zero", () => {
    // The tile that matters most for honesty. No survey has been sent, so a
    // number here would be invented — and "0" reads as "people are unhappy"
    // rather than "nobody was asked".
    analytics.data = payload();
    render(<TicketAnalyticsPage />);

    expect(screen.getByText("Not collected yet")).toBeTruthy();
  });

  it("reports the resolution rate against the number it was taken from", () => {
    analytics.data = payload();
    render(<TicketAnalyticsPage />);

    expect(screen.getByText("50%")).toBeTruthy();
    // "50%" from six tickets is a different claim from "50%" from six hundred.
    expect(screen.getByText("4 of 8")).toBeTruthy();
  });

  it("shows a dash, not a zero, when the window holds no tickets at all", () => {
    analytics.data = payload({
      quality: {
        resolutionRate: null,
        resolvedCount: 0,
        totalCount: 0,
        repeatContacts: 0,
        satisfaction: null,
        satisfactionAvailable: false,
      },
    });
    render(<TicketAnalyticsPage />);

    // A resolution rate of 0% for an empty window is a claim about nothing.
    expect(screen.queryByText("0%")).toBeNull();
  });

  it("says so when the figures could not be loaded", () => {
    // Never a blank page dressed as data: an agent reading zeros they think
    // are real is worse than an agent who knows the request failed.
    analytics.data = undefined;
    analytics.isError = true;
    render(<TicketAnalyticsPage />);

    expect(screen.getByRole("alert")).toBeTruthy();
    analytics.isError = false;
  });

  it("tells a refused reader they lack access, not that something broke", () => {
    analytics.data = undefined;
    analytics.isError = true;
    analytics.error = { isAxiosError: true, response: { status: 403 } };
    render(<TicketAnalyticsPage />);

    expect(
      screen.getByText(/You do not have access to the ticket dashboard/),
    ).toBeTruthy();
    analytics.isError = false;
    analytics.error = undefined;
  });

  it("echoes the window back in a form with no date ambiguity in it", () => {
    /**
     * The native date input renders in the browser's locale: "mm/dd/yyyy" on
     * a machine set to US English, while the platform's users are Australian.
     * 03/09 is two different days depending on which you assume, and the
     * control cannot be told which to use.
     *
     * It also has to say "inclusive", because the closing date now counts the
     * whole day named — the correction that stopped "1st to today" reporting
     * zero.
     */
    analytics.data = payload();
    render(<TicketAnalyticsPage />);

    fireEvent.change(screen.getByLabelText("From"), { target: { value: "2026-08-26" } });
    fireEvent.change(screen.getByLabelText("To"), { target: { value: "2026-09-03" } });

    expect(
      screen.getByText("Covering 26 Aug 2026 to 3 Sept 2026 inclusive, in UTC."),
    ).toBeTruthy();
  });

  it("names every dimension in English, including one nobody has written yet", () => {
    // Neither "programStage" nor "first_response" is a dimension the backend
    // has. They stand in for whichever one it adds next, and they are here
    // because a label table that has to be extended by hand is how `priority`
    // came to sit in this list as its own lower-case database key beside six
    // English labels. Two spellings, because the backend writes some names in
    // camelCase and the database writes most of its own in snake_case, and a
    // key in the second shape used to keep its underscore.
    analytics.data = payload({
      dimensions: [...DIMENSIONS, "programStage", "first_response"],
    });
    render(<TicketAnalyticsPage />);
    fireEvent.keyDown(breakdown(), { key: "ArrowDown" });

    expect(screen.getAllByRole("option").map((o) => o.textContent)).toEqual([
      "Region",
      "User type",
      "Category",
      "Status",
      "Assignee",
      "Channel",
      "Priority",
      "Program stage",
      "First response",
    ]);
  });

  it("labels the assignee breakdown with names, never with user ids", () => {
    // The chart the client asked for by name. A bar labelled "11" answers
    // "who is carrying the load?" with a number nobody can read.
    analytics.data = payload({
      segment: {
        dimension: "assignee",
        buckets: [
          { value: "", count: 9 },
          { value: "11", count: 4 },
          { value: "77", count: 1 },
        ],
      },
    });
    render(<TicketAnalyticsPage />);
    chooseDimension("Assignee");

    // 77 is nobody on the roster, which is what a deleted account looks like.
    // An id is a poor label; a blank one would be worse.
    expect(screen.getByTestId("segment-bars").textContent).toBe(
      "Not recorded:9 Sana Reid:4 #77:1",
    );
  });

  it("tells the reader why the bars are ids when the roster did not load", () => {
    // The failure mode of the fix above is the defect it fixed: no roster, and
    // every bar reads "#11" again. Silence there leaves the reader to decide
    // whether the chart is broken or the data is.
    analytics.data = payload({
      segment: { dimension: "assignee", buckets: [{ value: "11", count: 4 }] },
    });
    people.data = undefined;
    people.isError = true;
    render(<TicketAnalyticsPage />);

    // Region is on screen first, and it does not read the roster at all.
    // Warning about labels nobody is looking at is noise.
    expect(screen.queryByRole("alert")).toBeNull();

    chooseDimension("Assignee");

    expect(screen.getByRole("alert").textContent).toBe(
      "The assignee list could not be loaded, so the bars below are labelled " +
        "with user ids instead of names. Reload to try again.",
    );
    expect(screen.getByTestId("segment-bars").textContent).toBe("#11:4");

    people.data = roster;
    people.isError = false;
  });

  it("keeps two agents apart when they share a display name", () => {
    // The backend builds this name from the account's first and last name, so
    // two of them can match. Before the names went in, the labels were ids and
    // were distinct by construction; a name on its own puts two bars on the
    // chart with one caption between them.
    analytics.data = payload({
      segment: {
        dimension: "assignee",
        buckets: [
          { value: "3", count: 5 },
          { value: "4", count: 2 },
          { value: "11", count: 1 },
        ],
      },
    });
    people.data = [
      { id: 3, name: "Sam Reid", assignable: true },
      { id: 4, name: "Sam Reid", assignable: true },
      { id: 11, name: "Sana Reid", assignable: true },
    ];
    render(<TicketAnalyticsPage />);
    chooseDimension("Assignee");

    // Sana Reid is nobody else, so her bar keeps a name and nothing else.
    expect(screen.getByTestId("segment-bars").textContent).toBe(
      "Sam Reid #3:5 Sam Reid #4:2 Sana Reid:1",
    );

    people.data = roster;
  });

  it("writes priorities the way every other screen writes them", () => {
    analytics.data = payload({
      segment: {
        dimension: "priority",
        buckets: [
          { value: "normal", count: 6 },
          { value: "high", count: 2 },
          { value: "low", count: 1 },
        ],
      },
    });
    render(<TicketAnalyticsPage />);
    chooseDimension("Priority");

    expect(screen.getByTestId("segment-bars").textContent).toBe(
      "Normal:6 High:2 Low:1",
    );
  });

  it("describes Overdue by the rule the number is actually counted with", () => {
    // The client replaced "no first reply inside its window" on 2026-09-04:
    // the clock restarts every time the requester writes and stops every time
    // support answers. A ticket answered once can be overdue again, so the
    // old wording called this number something it is not, two tiles along
    // from the one that does measure first replies.
    analytics.data = payload();
    render(<TicketAnalyticsPage />);

    // Word for word the sentence the queue's Overdue counter carries, so the
    // same number does not get described two ways in one product.
    expect(
      screen.getByText("Waiting on support for longer than its priority allows"),
    ).toBeTruthy();
    expect(screen.queryByText(/no first reply/i)).toBeNull();
  });

  it("repeats the server's reason when the window itself is the problem", () => {
    // A range typed back to front is the reader's to fix, and the server has
    // already said so. "Those numbers could not be loaded" sends them looking
    // for a fault instead.
    analytics.data = undefined;
    analytics.isError = true;
    analytics.error = {
      isAxiosError: true,
      response: {
        status: 400,
        data: { error: "from must be earlier than to.", code: "invalid" },
      },
    };
    render(<TicketAnalyticsPage />);

    expect(screen.getByRole("alert").textContent).toBe(
      "from must be earlier than to.",
    );
    analytics.isError = false;
    analytics.error = undefined;
  });

  it("does not repeat a server fault back as if the reader could fix it", () => {
    // The 500 envelope carries an `error` too, and it says "Internal server
    // error". Passing that on would be a worse sentence than the generic one.
    analytics.data = undefined;
    analytics.isError = true;
    analytics.error = {
      isAxiosError: true,
      response: { status: 500, data: { error: "Internal server error" } },
    };
    render(<TicketAnalyticsPage />);

    expect(screen.getByRole("alert").textContent).toBe(
      "Those numbers could not be loaded.",
    );
    analytics.isError = false;
    analytics.error = undefined;
  });

  it("keeps naming the chosen breakdown while the window is refused", () => {
    // The options come from the payload, and a refused window has none. The
    // control went blank, so the one thing the reader had just chosen stopped
    // being on screen at the moment they were being told something is wrong.
    analytics.data = payload();
    const { rerender } = render(<TicketAnalyticsPage />);
    chooseDimension("Priority");

    analytics.data = undefined;
    analytics.isError = true;
    analytics.error = {
      isAxiosError: true,
      response: { status: 400, data: { error: "from must be earlier than to." } },
    };
    rerender(<TicketAnalyticsPage />);

    expect(breakdown().textContent).toBe("Priority");
    analytics.isError = false;
    analytics.error = undefined;
  });
});
