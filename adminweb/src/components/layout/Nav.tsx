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

const NAV_SECTIONS: NavSection[] = [
  {
    label: "Overview",
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
    label: "Support",
    support: true,
    items: [
      { title: "Ticket queue", url: "/tickets", icon: <LifeBuoyIcon /> },
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
  const sections = isAdmin
    ? NAV_SECTIONS
    : isSupport
      ? NAV_SECTIONS.filter((section) => section.support)
      : NAV_SECTIONS;

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
