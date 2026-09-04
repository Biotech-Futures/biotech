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
} from "lucide-react";

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
];

export function NavMain() {
  return (
    <>
      {NAV_SECTIONS.map((section) => (
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
