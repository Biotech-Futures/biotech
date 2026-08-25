import { Card, CardContent } from "@/components/ui/card";
import type { TicketSummary } from "@/schema/ticket";

type Props = {
  summary?: TicketSummary;
  isLoading: boolean;
};

const CARDS: { key: keyof TicketSummary; label: string; hint: string }[] = [
  {
    key: "unassigned",
    label: "Unassigned",
    // Resolved tickets have no owner either, but nobody has to pick them up.
    hint: "Still needs somebody to pick it up",
  },
  { key: "open", label: "Open", hint: "Received, not started" },
  { key: "pendingUser", label: "Pending user", hint: "Waiting on the requester" },
  {
    key: "overdue",
    label: "Overdue",
    hint: "No first reply within its priority's window",
  },
];

export function CounterCards({ summary, isLoading }: Props) {
  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      {CARDS.map((card) => (
        <Card key={card.key}>
          <CardContent className="p-4">
            <p className="text-muted-foreground text-xs font-medium uppercase tracking-wide">
              {card.label}
            </p>
            <p
              className={
                card.key === "overdue" && (summary?.overdue ?? 0) > 0
                  ? "text-destructive mt-1 text-2xl font-semibold"
                  : "mt-1 text-2xl font-semibold"
              }
            >
              {isLoading ? "—" : (summary?.[card.key] ?? 0)}
            </p>
            <p className="text-muted-foreground mt-1 text-xs">{card.hint}</p>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
