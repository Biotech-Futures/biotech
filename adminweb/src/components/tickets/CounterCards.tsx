import { Card, CardContent } from "@/components/ui/card";
import { UNASSIGNED, type TicketFilters, type TicketSummary } from "@/schema/ticket";

type Props = {
  summary?: TicketSummary;
  isLoading: boolean;
  isError: boolean;
  /** Cards a single filter reproduces exactly lead there. Overdue is the one
   *  that does not: it is worked out from the SLA clock as the queue is read,
   *  and the queue endpoint has no parameter for it. */
  onShowFilter?: (filter: TicketFilters) => void;
};

const CARDS: {
  key: keyof TicketSummary;
  label: string;
  hint: string;
  /** The filter that lists what this card counts, where one exists. */
  filter?: TicketFilters;
}[] = [
  {
    key: "unassigned",
    label: "Unassigned",
    // Resolved tickets have no owner either, but nobody has to pick them up.
    hint: "Still needs somebody to pick it up",
    filter: { assignee: UNASSIGNED },
  },
  {
    key: "open",
    label: "Open",
    // Not "received, not started": a reply does not claim a ticket, and a
    // reopened one comes back here with its history intact, so this bucket
    // legitimately holds answered work too. What is true of all of them is
    // that nobody owns it.
    hint: "Nobody has picked it up yet",
    filter: { status: "open" },
  },
  {
    key: "pendingUser",
    label: "Pending user",
    hint: "Waiting on the requester",
    filter: { status: "pending_user" },
  },
  {
    key: "overdue",
    label: "Overdue",
    // Not "no first reply": that is the rule the client replaced on
    // 2026-09-04. The clock restarts every time the requester writes back, so
    // a ticket support has already answered lands here again once it sits.
    hint: "Waiting on support for longer than its priority allows",
  },
];

export function CounterCards({
  summary,
  isLoading,
  isError,
  onShowFilter,
}: Props) {
  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      {CARDS.map((card) => {
        const filter = card.filter;
        const show =
          filter && onShowFilter ? () => onShowFilter(filter) : undefined;
        return (
        <Card
          key={card.key}
          className={show ? "hover:border-primary cursor-pointer" : undefined}
          // A button rather than a click handler on the card: this has to be
          // reachable from the keyboard, and a div with onClick is not.
          onClick={show}
        >
          <CardContent className="p-4">
            {show ? (
              <button
                type="button"
                onClick={show}
                className="text-muted-foreground hover:text-foreground text-xs font-medium uppercase tracking-wide underline-offset-2 hover:underline"
              >
                {card.label}
              </button>
            ) : (
              <p className="text-muted-foreground text-xs font-medium uppercase tracking-wide">
                {card.label}
              </p>
            )}
            <p
              className={
                card.key === "overdue" && (summary?.overdue ?? 0) > 0
                  ? "text-destructive mt-1 text-2xl font-semibold"
                  : "mt-1 text-2xl font-semibold"
              }
            >
              {/* No number at all when we do not have one. A failed request
                  is not the same as a count of zero, and "Overdue 0" is the
                  one thing on this page an agent might act on by walking
                  away. Nothing in this app retries on its own. */}
              {isLoading || isError || summary === undefined
                ? "—"
                : summary[card.key]}
            </p>
            <p className="text-muted-foreground mt-1 text-xs">{card.hint}</p>
          </CardContent>
        </Card>
        );
      })}
    </div>
  );
}
