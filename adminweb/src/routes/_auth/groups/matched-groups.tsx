import { createFileRoute } from "@tanstack/react-router";
import { MatchedGroupsPanel } from "@/components/group/MatchedGroupsPanel";

export const Route = createFileRoute("/_auth/groups/matched-groups")({
  component: MatchedGroupsRoute,
});

function MatchedGroupsRoute() {
  return <MatchedGroupsPanel />;
}
