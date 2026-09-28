import { createFileRoute } from "@tanstack/react-router";
import { TicketQueuePage } from "@/components/tickets/TicketQueuePage";

// Nothing but the Route is exported: an extra export switches off
// autoCodeSplitting for the route (measured at 170 kB on the main chunk for
// this file and the home page together). The component lives in
// components/tickets/ and its test imports it from there.
type TicketSearch = {
  // Deep link. A ticket the platform raised itself carries a link of this
  // shape in its first message, so support can go straight from the
  // notification to the ticket. Without this the panel has no way to open.
  ticket?: number;
};

export const Route = createFileRoute("/_auth/tickets/")({
  validateSearch: (search: Record<string, unknown>): TicketSearch => ({
    // Guarded rather than coerced. `Number("abc")` is NaN, which is neither
    // null nor undefined, so the panel opens on a ticket that cannot exist
    // and sits on "Loading…" forever. The router has already parsed numeric
    // params, so the type check is what does the work here.
    ticket:
      typeof search.ticket === "number" &&
      Number.isInteger(search.ticket) &&
      search.ticket > 0
        ? search.ticket
        : undefined,
  }),
  component: TicketQueuePage,
});
