import { Checkbox } from "@/components/ui/checkbox";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { OverdueBadge, PriorityBadge, StatusBadge } from "./TicketBadges";
import type { TicketRow } from "@/schema/ticket";

type Props = {
  tickets: TicketRow[];
  isLoading: boolean;
  selectedIds: number[];
  onToggle: (id: number) => void;
  onToggleAll: () => void;
  onOpen: (id: number) => void;
};

function formatWhen(value: string) {
  return new Date(value).toLocaleString("en-AU", {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function QueueTable({
  tickets,
  isLoading,
  selectedIds,
  onToggle,
  onToggleAll,
  onOpen,
}: Props) {
  const allSelected = tickets.length > 0 && selectedIds.length === tickets.length;

  if (isLoading) {
    return <p className="text-muted-foreground py-8 text-sm">Loading the queue…</p>;
  }

  if (!tickets.length) {
    return (
      <p className="text-muted-foreground py-8 text-sm">
        No tickets match these filters.
      </p>
    );
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead className="w-10">
            <Checkbox
              checked={allSelected}
              onCheckedChange={onToggleAll}
              aria-label="Select every ticket on this page"
            />
          </TableHead>
          <TableHead>Ticket</TableHead>
          <TableHead>Requester</TableHead>
          <TableHead>Subject</TableHead>
          <TableHead>Status</TableHead>
          <TableHead>Priority</TableHead>
          <TableHead>Assignee</TableHead>
          <TableHead>Last activity</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {tickets.map((ticket) => (
          <TableRow
            key={ticket.id}
            className="cursor-pointer"
            onClick={() => onOpen(ticket.id)}
          >
            <TableCell onClick={(event) => event.stopPropagation()}>
              <Checkbox
                checked={selectedIds.includes(ticket.id)}
                onCheckedChange={() => onToggle(ticket.id)}
                aria-label={`Select ${ticket.ticketNumber}`}
              />
            </TableCell>
            <TableCell className="font-medium whitespace-nowrap">
              {ticket.ticketNumber}
            </TableCell>
            <TableCell className="whitespace-nowrap">
              {/* No requester at all on tickets the platform raised itself. */}
              {ticket.user.name ?? <span className="text-muted-foreground">—</span>}
              {ticket.user.region && (
                <span className="text-muted-foreground block text-xs">
                  {ticket.user.region}
                </span>
              )}
            </TableCell>
            <TableCell className="max-w-[22rem] truncate">{ticket.subject}</TableCell>
            <TableCell>
              <div className="flex items-center gap-1">
                <StatusBadge status={ticket.status} />
                {ticket.overdue && <OverdueBadge />}
              </div>
            </TableCell>
            <TableCell>
              <PriorityBadge priority={ticket.priority} />
            </TableCell>
            <TableCell className="whitespace-nowrap">
              {ticket.assignee?.name ?? (
                <span className="text-muted-foreground">Unassigned</span>
              )}
            </TableCell>
            <TableCell className="text-muted-foreground whitespace-nowrap text-sm">
              {/* The support clock: internal notes count as activity here,
                  which is why it is not the same column the requester sees. */}
              {formatWhen(ticket.supportUpdatedAt)}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
