import { createFileRoute, Outlet } from "@tanstack/react-router";
import { PageHeader } from "@/components/layout/PageHeader";
import type { PageTab } from "@/components/layout/PageTabs";

const GROUPS_TABS: PageTab[] = [
  { label: "Groups", to: "/groups", exact: true },
  { label: "Student Matching", to: "/groups/student-matching" },
  { label: "Mentor Matching", to: "/groups/mentor-matching" },
];

export const Route = createFileRoute("/_auth/groups")({
  component: GroupsLayout,
});

function GroupsLayout() {
  return (
    <div className="p-4 space-y-4">
      <PageHeader title="Groups & Matching" tabs={GROUPS_TABS} />
      <Outlet />
    </div>
  );
}
