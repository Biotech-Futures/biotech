import { createFileRoute } from "@tanstack/react-router";
import { TicketAnalyticsPage } from "@/components/tickets/TicketAnalyticsPage";

// Nothing but the Route is exported: an extra export switches off
// autoCodeSplitting for this route. The component lives in components/
// and its test imports it from there.
export const Route = createFileRoute("/_auth/tickets/analytics")({
  component: TicketAnalyticsPage,
});
