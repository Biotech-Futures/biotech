import {
  SidebarGroup,
  SidebarGroupContent,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar";
import { Link } from "@tanstack/react-router";
import {
  UsersIcon,
  CalendarIcon,
  UserIcon,
  GraduationCapIcon,
  Link2Icon,
  FileTextIcon,
  MegaphoneIcon,
  CheckSquareIcon,
  LayoutDashboardIcon,
} from "lucide-react";

const NAV_ITEMS = [
  {
    title: "Dashboard",
    url: "/",
    icon: <LayoutDashboardIcon />,
  },
  {
    title: "User",
    url: "/user",
    icon: <UserIcon />,
  },
  {
    title: "Group",
    url: "/group",
    icon: <UsersIcon />,
  },
  {
    title: "Event",
    url: "/event",
    icon: <CalendarIcon />,
  },
  {
    title: "Students",
    url: "/student",
    icon: <GraduationCapIcon />,
  },
  {
    title: "Resource",
    url: "/resource",
    icon: <FileTextIcon />,
  },
  // {
  //   title: "Matching",
  //   url: "/matching",
  //   icon: <Link2Icon />,
  // },
  {
    title: "Mentor Matching",
    url: "/mentorMatching",
    icon: <Link2Icon />,
  },
  {
    title: "Mentor",
    url: "/mentor",
    icon: <GraduationCapIcon />,
  },
  {
    title: "Announcement",
    url: "/announcement",
    icon: <MegaphoneIcon />,
  },
  {
    title: "Task",
    url: "/task",
    icon: <CheckSquareIcon />,
  },
];

export function NavMain() {
  const items = NAV_ITEMS;
  return (
    <SidebarGroup>
      <SidebarGroupContent className="flex flex-col gap-2">
        <SidebarMenu>
          {items.map((item) => (
            <SidebarMenuItem key={item.title} className="">
              <SidebarMenuButton asChild tooltip={item.title}>
                <Link
                  to={item.url}
                  className="flex items-center"
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
  );
}
