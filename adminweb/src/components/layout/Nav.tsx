import {
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar";
import { Link } from "@tanstack/react-router";
import type { ReactNode } from "react";
import {
  UsersIcon,
  CalendarIcon,
  UserIcon,
  GraduationCapIcon,
  HandshakeIcon,
  Link2Icon,
  ShuffleIcon,
  FileTextIcon,
  MegaphoneIcon,
  CheckSquareIcon,
  LayoutDashboardIcon,
  LifeBuoyIcon,
  ChartColumnIcon,
  ScrollTextIcon,
  UserCogIcon,
  ClipboardListIcon,
  UnlockIcon,
  StarIcon,
  SettingsIcon,
} from "lucide-react";
import { useAuthContext } from "@/provider/AuthProvider";

type NavItem = {
  title: string;
  url: string;
  icon: ReactNode;
  /** Highlight only on an exact path match — use for hub index routes. */
  exact?: boolean;
};

type NavSection = {
  label: string;
  items: NavItem[];
  /** Visible to a support agent who is not an admin. Everything else is not. */
  support?: boolean;
};

// Exported for two tests: the sidebar's own visibility test, and the
// consistency check against the home page's copy of this list — the drift
// between the two copies is what shipped a blank home page once already.
export const NAV_SECTIONS: NavSection[] = [
  {
    label: "Overview",
    // Support-visible: "/" is where signing in lands you, so a filtered
    // sidebar without it leaves an agent no way back to their own start page.
    support: true,
    items: [
      { title: "Dashboard", url: "/", icon: <LayoutDashboardIcon />, exact: true },
    ],
  },
  {
    label: "People",
    items: [
      { title: "Users", url: "/people", icon: <UserIcon />, exact: true },
      { title: "Students", url: "/people/students", icon: <GraduationCapIcon /> },
      { title: "Mentors", url: "/people/mentors", icon: <HandshakeIcon /> },
      // In People, not Support: that section carries support: true, and a
      // support agent must not be offered the screen that grants the role.
      { title: "Support agents", url: "/people/support-agents", icon: <UserCogIcon /> },
    ],
  },
  {
    label: "Groups & Matching",
    items: [
      { title: "Groups", url: "/groups", icon: <UsersIcon />, exact: true },
      {
        title: "Student Matching",
        url: "/groups/student-matching",
        icon: <ShuffleIcon />,
      },
      {
        title: "Mentor Matching",
        url: "/groups/mentor-matching",
        icon: <Link2Icon />,
      },
    ],
  },
  {
    label: "Content",
    items: [
      { title: "Events", url: "/event", icon: <CalendarIcon /> },
      { title: "Resources", url: "/resource", icon: <FileTextIcon /> },
      { title: "Announcements", url: "/announcement", icon: <MegaphoneIcon /> },
      { title: "Tasks", url: "/task", icon: <CheckSquareIcon /> },
    ],
  },
  {
    // No `support` flag, so this section is gated on `isAdmin`. A support
    // agent is correctly excluded: SupportScope implies neither staff nor
    // AdminScope, so the link would only end in a 403.
    //
    // ⚠️ `isAdmin` is NOT equivalent to the backend gate. is_admin() is an
    // AdminScope row and nothing else (apps/common/rbac.py:81-86), while
    // IsGrader (apps/grading/permissions.py:11-17) is
    // `is_staff or is_superuser or AdminScope`. So an account that is staff
    // or superuser with no AdminScope row does not see this section even
    // though the grading API would serve it. Left as-is on purpose: /users/me/
    // ships only isAdmin and isSupport (apps/users/serializers.py:356-372),
    // so the sidebar cannot express the difference without a backend change.
    // That gap is main's to close and belongs in its own issue, not in a
    // merge resolution.
    label: "Grading",
    items: [
      { title: "Mark by Component", url: "/grading/by-component", icon: <ClipboardListIcon /> },
      { title: "Mark by Group", url: "/grading/by-group", icon: <UsersIcon /> },
      { title: "Certificate Setup", url: "/grading/settings", icon: <SettingsIcon /> },
      { title: "Release Marks", url: "/grading/release", icon: <UnlockIcon /> },
      { title: "Finalists", url: "/grading/finalists", icon: <StarIcon /> },
    ],
  },
  {
    label: "Support",
    support: true,
    items: [
      { title: "Ticket queue", url: "/tickets", icon: <LifeBuoyIcon />, exact: true },
      { title: "Ticket audit", url: "/tickets/audit", icon: <ScrollTextIcon /> },
      { title: "Ticket analytics", url: "/tickets/analytics", icon: <ChartColumnIcon /> },
    ],
  },
];

export function NavMain() {
  const { user } = useAuthContext();
  const isAdmin = Boolean(user?.isAdmin);
  const isSupport = Boolean(user?.isSupport);

  // Every admin can work the queue, so the two flags overlap and one of them
  // could not tell these cases apart. A support agent who is not an admin
  // gets the queue and nothing else — and hiding the rest is a courtesy, not
  // the control: the other endpoints refuse them at the server.
  //
  // Three cases, not two. Somebody who is neither an admin nor an agent can
  // still reach this app — the route only checks that you are signed in — so
  // a student who signs in here gets the dashboard and nothing else. Offering
  // them the ticket queue would be a link that ends in 403, which reads as a
  // broken page rather than as "this is not for you".
  const sections = isAdmin
    ? NAV_SECTIONS
    : isSupport
      ? NAV_SECTIONS.filter((section) => section.support)
      : NAV_SECTIONS.filter((section) => section.label === "Overview");

  return (
    <>
      {sections.map((section) => (
        <SidebarGroup key={section.label}>
          <SidebarGroupLabel>{section.label}</SidebarGroupLabel>
          <SidebarGroupContent className="flex flex-col gap-1">
            <SidebarMenu>
              {section.items.map((item) => (
                <SidebarMenuItem key={item.title}>
                  <SidebarMenuButton asChild tooltip={item.title}>
                    <Link
                      to={item.url}
                      className="flex items-center"
                      activeOptions={{ exact: item.exact ?? false }}
                      activeProps={{
                        className:
                          "rounded-md text-sm font-medium text-primary bg-primary/10",
                      }}
                    >
                      {item.icon}
                      <span>{item.title}</span>
                    </Link>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      ))}
    </>
  );
}
