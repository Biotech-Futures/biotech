import { createFileRoute, redirect } from "@tanstack/react-router";

// Merged into the People hub (Mentors tab). Kept as a redirect for old links.
export const Route = createFileRoute("/_auth/mentor")({
  beforeLoad: ({ location }) => {
    throw redirect({ to: "/people/mentors", search: location.search as never });
  },
});
