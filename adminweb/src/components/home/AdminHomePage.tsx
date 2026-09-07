// The admin landing page, in its own module rather than in the route file.
//
// It used to live in src/routes/_auth/index.tsx and was exported from there
// so its component test could render it. That export disabled TanStack
// Router's autoCodeSplitting for the route: the main chunk grew from 526 kB
// to 697 kB and twenty chunks were folded into it. Route files must export
// nothing but the Route; anything that needs importing from elsewhere —
// including by a test — belongs in a file like this one.
import { Link } from "@tanstack/react-router";
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
  LifeBuoyIcon,
  ScrollTextIcon,
  UserCogIcon,
  ChartColumnIcon,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useAuthContext } from "@/provider/AuthProvider";

// Mirrors components/layout/Nav.tsx. Two lists rather than one because the
// sidebar and this grid want different copy; what they must agree on is who
// sees what, so `support` is spelled the same way in both.
// Exported for the consistency test against the sidebar's list; see there.
export const NAV_SECTIONS = [
  {
    label: "People",
    cards: [
      { title: "Users", url: "/people", icon: UserIcon, desc: "Manage platform users" },
      { title: "Students", url: "/people/students", icon: GraduationCapIcon, desc: "Assign students to groups" },
      { title: "Mentors", url: "/people/mentors", icon: HandshakeIcon, desc: "Manage mentor accounts" },
      // In People, not Support: that section carries support: true, and a
      // support agent must not be offered the screen that grants the role.
      { title: "Support agents", url: "/people/support-agents", icon: UserCogIcon, desc: "Grant and revoke support queue access" },
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
  {
    label: "Support",
    support: true,
    cards: [
      { title: "Ticket queue", url: "/tickets", icon: LifeBuoyIcon, desc: "Work enquiries from across the platform" },
      { title: "Ticket audit", url: "/tickets/audit", icon: ScrollTextIcon, desc: "Every recorded action, deletions included" },
      { title: "Ticket analytics", url: "/tickets/analytics", icon: ChartColumnIcon, desc: "Demand, flow, service and quality" },
    ],
  },
];

export function AdminHomePage() {
  const { user } = useAuthContext();
  const isAdmin = Boolean(user?.isAdmin);
  const isSupport = Boolean(user?.isSupport);

  // Three branches, matching the sidebar's rule about *who sees what*. It
  // must not copy the sidebar's section list as well: Nav.tsx has an
  // "Overview" section holding the Dashboard link and this grid has no such
  // section, so filtering for that label here selects nothing and renders a
  // blank page. Every card in this file is an admin area, so the third
  // branch is legitimately empty and the empty state below is what says so.
  const sections = isAdmin
    ? NAV_SECTIONS
    : isSupport
      ? NAV_SECTIONS.filter((section) => section.support)
      : [];

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

      {/* Somebody with an account but no admin or support row can still sign
          in here — the route only checks that you are signed in. They get no
          cards, and a page with a name at the top and nothing under it reads
          as broken rather than as "this is not for you". */}
      {sections.length === 0 && (
        <p className="text-sm text-muted-foreground">
          This is the administration area, and your account does not have
          access to any of it. If you think it should, ask an administrator to
          grant you support access.
        </p>
      )}

      {sections.map((section) => (
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
