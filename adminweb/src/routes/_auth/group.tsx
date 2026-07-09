import { createFileRoute, redirect } from "@tanstack/react-router";

// Merged into the Groups & Matching hub (Groups tab). Kept as a redirect so
// deep links like /group?groupId=<id> still open the group detail modal.
export const Route = createFileRoute("/_auth/group")({
  beforeLoad: ({ location }) => {
    throw redirect({ to: "/groups", search: location.search as never });
  },
});
