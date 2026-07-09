import { createFileRoute, Link } from "@tanstack/react-router";
import {
  UserIcon,
  UsersIcon,
  CalendarIcon,
  GraduationCapIcon,
  HandshakeIcon,
  Link2Icon,
  ShuffleIcon,
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

const NAV_SECTIONS = [
  {
    label: "People",
    cards: [
      { title: "Users", url: "/people", icon: UserIcon, desc: "Manage platform users" },
      { title: "Students", url: "/people/students", icon: GraduationCapIcon, desc: "Assign students to groups" },
      { title: "Mentors", url: "/people/mentors", icon: HandshakeIcon, desc: "Manage mentor accounts" },
    ],
  },
  {
    label: "Groups & Matching",
    cards: [
      { title: "Groups", url: "/groups", icon: UsersIcon, desc: "View and manage groups" },
      { title: "Student Matching", url: "/groups/student-matching", icon: ShuffleIcon, desc: "Match students into groups" },
      { title: "Mentor Matching", url: "/groups/mentor-matching", icon: Link2Icon, desc: "Match mentors to groups" },
    ],
  },
  {
    label: "Content",
    cards: [
      { title: "Events", url: "/event", icon: CalendarIcon, desc: "Schedule and track events" },
      { title: "Resources", url: "/resource", icon: FileTextIcon, desc: "Upload and manage resources" },
      { title: "Announcements", url: "/announcement", icon: MegaphoneIcon, desc: "Publish announcements" },
      { title: "Tasks", url: "/task", icon: CheckSquareIcon, desc: "Assign and track tasks" },
    ],
  },
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

      {NAV_SECTIONS.map((section) => (
        <div key={section.label}>
          <h2 className="text-sm font-medium text-muted-foreground uppercase tracking-wide mb-3">
            {section.label}
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {section.cards.map(({ title, url, icon: Icon, desc }) => (
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
      ))}
    </div>
  );
}
