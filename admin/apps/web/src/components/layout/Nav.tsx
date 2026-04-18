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
  MailIcon,
  CalendarIcon,
  UserIcon,
  Link2Icon,
  FileTextIcon,
  GraduationCapIcon,
} from "lucide-react";

const NAV_ITEMS = [
  {
    title: "Group",
    url: "/group",
    icon: <UsersIcon />,
  },
  {
    title: "Email",
    url: "/email",
    icon: <MailIcon />,
  },
  {
    title: "Event",
    url: "/event",
    icon: <CalendarIcon />,
  },
  {
    title: "User",
    url: "/student",
    icon: <UserIcon />,
  },
  {
    title: "Resource",
    url: "/resource",
    icon: <FileTextIcon />,
  },
  {
    title: "Matching",
    url: "/matching",
    icon: <Link2Icon />,
  },
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
];

export function NavMain() {
  return (
    <SidebarGroup>
      <SidebarGroupContent className="flex flex-col gap-2">
        <SidebarMenu>
          {NAV_ITEMS.map((item) => (
            <SidebarMenuItem key={item.title} className="p-2">
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
