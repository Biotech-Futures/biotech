import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { createFileRoute } from '@tanstack/react-router'

export const Route = createFileRoute('/_auth/email')({
  component: RouteComponent,
})

function RouteComponent() {
  const campaigns = [
    {
      name: "Mentor Welcome Pack",
      audience: "New mentors",
      status: "Draft",
      sendWindow: "April 18, 2026",
    },
    {
      name: "Unmatched Student Follow-up",
      audience: "Students awaiting placement",
      status: "Ready",
      sendWindow: "April 15, 2026",
    },
    {
      name: "Weekly Admin Digest",
      audience: "Program coordinators",
      status: "Scheduled",
      sendWindow: "Every Monday 9:00 AM",
    },
  ];

  return (
    <div className="space-y-4">
      <div className="rounded-xl border bg-card p-5">
        <Badge variant="outline">Presentation Page</Badge>
        <h1 className="mt-3 text-2xl font-bold">Email Campaigns</h1>
        <p className="mt-2 text-muted-foreground">
          This screen is currently a mock presentation of the messaging workflow. It is ready for a real
          API once email templates and delivery ownership are confirmed.
        </p>
      </div>

      <div className="grid gap-4 xl:grid-cols-3">
        {campaigns.map((campaign) => (
          <div key={campaign.name} className="rounded-xl border bg-card p-5">
            <div className="flex items-center justify-between gap-2">
              <h2 className="text-base font-semibold">{campaign.name}</h2>
              <Badge variant="secondary">{campaign.status}</Badge>
            </div>
            <p className="mt-3 text-sm text-muted-foreground">Audience: {campaign.audience}</p>
            <p className="mt-1 text-sm text-muted-foreground">Send window: {campaign.sendWindow}</p>
            <div className="mt-4 flex gap-2">
              <Button size="sm">Preview</Button>
              <Button size="sm" variant="outline">Edit Copy</Button>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
