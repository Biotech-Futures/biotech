import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Link, createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/_auth/")({
  component: RouteComponent,
});

function RouteComponent() {
  const stats = [
    { label: "Active groups", value: "24", hint: "+3 this week" },
    { label: "Unassigned students", value: "11", hint: "Review matching board" },
    { label: "Mentor confirmations", value: "7", hint: "2 awaiting sign-off" },
    { label: "Resources published", value: "18", hint: "4 updated recently" },
  ];

  const quickActions = [
    {
      title: "Review student matching",
      body: "Open the drag-and-drop assignment board and confirm the current mock recommendations.",
      href: "/matching",
    },
    {
      title: "Check mentor allocations",
      body: "Run the mentor recommendation pass and spot groups that still have no suitable mentor.",
      href: "/mentor-matching",
    },
    {
      title: "Clean up admin resources",
      body: "Edit resource metadata, role visibility, and document descriptions for the showcase.",
      href: "/resource",
    },
  ];

  return (
    <div className="space-y-6">
      <section className="rounded-2xl border bg-card p-6">
        <Badge variant="outline">Mock Admin Console</Badge>
        <h1 className="mt-3 text-3xl font-bold">Operations Overview</h1>
        <p className="mt-2 max-w-2xl text-muted-foreground">
          This dashboard is wired for demo mode: page layouts, filters, and mutations all reflect the
          real admin flow, while the data currently comes from mock services.
        </p>
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {stats.map((item) => (
          <div key={item.label} className="rounded-xl border bg-card p-4">
            <p className="text-sm text-muted-foreground">{item.label}</p>
            <p className="mt-2 text-3xl font-semibold">{item.value}</p>
            <p className="mt-1 text-sm text-muted-foreground">{item.hint}</p>
          </div>
        ))}
      </section>

      <section className="grid gap-4 xl:grid-cols-[1.4fr_1fr]">
        <div className="rounded-xl border bg-card p-5">
          <h2 className="text-lg font-semibold">Launch Checklist</h2>
          <div className="mt-4 space-y-3 text-sm text-muted-foreground">
            <p>1. Install workspace dependencies with <code>pnpm install</code>.</p>
            <p>2. Start the mock API on port <code>3003</code> and the web app on port <code>3000</code>.</p>
            <p>3. Use the sidebar to review the user, group, matching, and resource flows.</p>
          </div>
        </div>
        <div className="rounded-xl border bg-card p-5">
          <h2 className="text-lg font-semibold">Recent Notes</h2>
          <div className="mt-4 space-y-3 text-sm text-muted-foreground">
            <p>The database-facing integration points are intentionally preserved behind mock services.</p>
            <p>User, resource, and matching pages are ready for visual review and later API replacement.</p>
            <p>Email and event pages currently serve as presentation placeholders for upcoming backend work.</p>
          </div>
        </div>
      </section>

      <section className="grid gap-4 xl:grid-cols-3">
        {quickActions.map((item) => (
          <div key={item.title} className="rounded-xl border bg-card p-5">
            <h3 className="text-base font-semibold">{item.title}</h3>
            <p className="mt-2 text-sm text-muted-foreground">{item.body}</p>
            <Button asChild className="mt-4">
              <Link to={item.href}>Open</Link>
            </Button>
          </div>
        ))}
      </section>
    </div>
  );
}
