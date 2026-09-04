import { createFileRoute, Outlet } from "@tanstack/react-router";
import { PageHeader } from "@/components/layout/PageHeader";
import { PEOPLE_TABS } from "./-peopleTabs";

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
