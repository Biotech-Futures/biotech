import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/_auth/event")({
  component: RouteComponent,
});

function RouteComponent() {
  return <div>Hello "/_auth/event"!</div>;
}
