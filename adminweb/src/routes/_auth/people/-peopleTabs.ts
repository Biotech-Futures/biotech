import type { PageTab } from "@/components/layout/PageTabs";

export const PEOPLE_TABS: PageTab[] = [
  { label: "Users", to: "/people", exact: true },
  { label: "Students", to: "/people/students" },
  { label: "Mentors", to: "/people/mentors" },
  { label: "Supervisors", to: "/people/supervisors" },
  { label: "Registration", to: "/people/registration" },
];
