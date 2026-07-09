import { createFileRoute, Outlet } from "@tanstack/react-router";
import { PageHeader } from "@/components/layout/PageHeader";
import type { PageTab } from "@/components/layout/PageTabs";

const PEOPLE_TABS: PageTab[] = [
  { label: "Users", to: "/people", exact: true },
  { label: "Students", to: "/people/students" },
  { label: "Mentors", to: "/people/mentors" },
];

export const Route = createFileRoute("/_auth/people")({
  component: PeopleLayout,
});

function PeopleLayout() {
  return (
    <div className="p-4 space-y-4">
      <PageHeader title="People" tabs={PEOPLE_TABS} />
      <Outlet />
    </div>
  );
}
