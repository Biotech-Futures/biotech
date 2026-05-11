import { createFileRoute, Link } from "@tanstack/react-router";
import {
  UserIcon,
  UsersIcon,
  CalendarIcon,
  GraduationCapIcon,
  Link2Icon,
  FileTextIcon,
  MegaphoneIcon,
  CheckSquareIcon,
  ShieldCheckIcon,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useAuthContext } from "@/provider/AuthProvider";

export const Route = createFileRoute("/_auth/")({
  component: AdminHomePage,
});

const NAV_CARDS = [
  { title: "Users", url: "/user", icon: UserIcon, desc: "Manage platform users" },
  { title: "Groups", url: "/group", icon: UsersIcon, desc: "View and manage groups" },
  { title: "Events", url: "/event", icon: CalendarIcon, desc: "Schedule and track events" },
  { title: "Students", url: "/student", icon: GraduationCapIcon, desc: "Student management" },
  { title: "Resources", url: "/resource", icon: FileTextIcon, desc: "Upload and manage resources" },
  { title: "Mentor Matching", url: "/mentorMatching", icon: Link2Icon, desc: "Run mentor matching" },
  { title: "Mentors", url: "/mentor", icon: GraduationCapIcon, desc: "Manage mentor accounts" },
  { title: "Announcements", url: "/announcement", icon: MegaphoneIcon, desc: "Publish announcements" },
  { title: "Tasks", url: "/task", icon: CheckSquareIcon, desc: "Assign and track tasks" },
];

function AdminHomePage() {
  const { user } = useAuthContext();

  const displayName =
    user?.name ||
    (user?.email ? user.email.split("@")[0] : "Admin");

  return (
    <div className="p-6 space-y-8">
      <div className="flex items-center gap-4">
        <div className="flex size-14 items-center justify-center rounded-full bg-primary/10">
          <ShieldCheckIcon className="size-7 text-primary" />
        </div>
        <div>
          <h1 className="text-2xl font-semibold">{displayName}</h1>
          <p className="text-sm text-muted-foreground">{user?.email}</p>
          {user?.role && (
            <p className="text-xs text-muted-foreground capitalize mt-0.5">
              {user.role}
            </p>
          )}
        </div>
      </div>

      <div>
        <h2 className="text-sm font-medium text-muted-foreground uppercase tracking-wide mb-3">
          Quick Navigation
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {NAV_CARDS.map(({ title, url, icon: Icon, desc }) => (
            <Link key={url} to={url}>
              <Card className="hover:bg-accent/50 transition-colors cursor-pointer h-full">
                <CardHeader className="pb-2 pt-4">
                  <CardTitle className="flex items-center gap-2 text-base font-medium">
                    <Icon className="size-4 text-primary" />
                    {title}
                  </CardTitle>
                </CardHeader>
                <CardContent className="pb-4">
                  <p className="text-xs text-muted-foreground">{desc}</p>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}
