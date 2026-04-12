import { createFileRoute } from "@tanstack/react-router";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

export const Route = createFileRoute("/_auth/event")({
  component: RouteComponent,
});

function RouteComponent() {
  const events = [
    {
      title: "Program Kick-off",
      date: "April 22, 2026",
      location: "Sydney + livestream",
      attendees: 64,
    },
    {
      title: "Mentor Office Hour",
      date: "April 29, 2026",
      location: "Online",
      attendees: 18,
    },
    {
      title: "Showcase Rehearsal",
      date: "May 14, 2026",
      location: "Melbourne Hub",
      attendees: 27,
    },
  ];

  return (
    <div className="space-y-4">
      <div className="rounded-xl border bg-card p-5">
        <Badge variant="outline">Presentation Page</Badge>
        <h1 className="mt-3 text-2xl font-bold">Event Planning</h1>
        <p className="mt-2 text-muted-foreground">
          This page currently showcases the intended event operations flow with mock schedule cards.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {events.map((event) => (
          <div key={event.title} className="rounded-xl border bg-card p-5">
            <h2 className="text-base font-semibold">{event.title}</h2>
            <p className="mt-3 text-sm text-muted-foreground">{event.date}</p>
            <p className="text-sm text-muted-foreground">{event.location}</p>
            <p className="mt-3 text-sm">
              <span className="font-medium">{event.attendees}</span> registered attendees
            </p>
            <div className="mt-4 flex gap-2">
              <Button size="sm">View Agenda</Button>
              <Button size="sm" variant="outline">Manage RSVP</Button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
