import { createFileRoute, redirect } from "@tanstack/react-router";

// Merged into the People hub (Students tab). Kept as a redirect for old links.
export const Route = createFileRoute("/_auth/student")({
  beforeLoad: ({ location }) => {
    throw redirect({ to: "/people/students", search: location.search as never });
  },
});
