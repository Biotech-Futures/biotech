import { createFileRoute, redirect } from "@tanstack/react-router";

// Merged into the People hub. Kept as a redirect so existing links/bookmarks
// (and any forwarded search params) keep working.
export const Route = createFileRoute("/_auth/user")({
  beforeLoad: ({ location }) => {
    throw redirect({ to: "/people", search: location.search as never });
  },
});
