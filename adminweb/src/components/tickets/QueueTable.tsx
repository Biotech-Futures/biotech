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
  isError: boolean;
  selectedIds: number[];
  onToggle: (id: number) => void;
  onToggleAll: () => void;
  onOpen: (id: number) => void;
  /** True only on a page that continues the frozen walk. An empty page there
   *  is not the same claim as an empty queue, so it does not get the same
   *  sentence. A page reached by clicking its number is a fresh read, so it
   *  is not one of these. */
  beyondFirstPage?: boolean;
};

function formatWhen(value: string) {
  return new Date(value).toLocaleString("en-AU", {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    // Rendered in whatever zone the reader's machine is in, so the zone has
    // to be on screen. The same row reads 03:37 pm in Sydney and 02:37 am in
    // Sao Paulo, and agents compare these times with each other.
    timeZoneName: "short",
  });
}

export function QueueTable({
  tickets,
  isLoading,
  isError,
  selectedIds,
  onToggle,
  onToggleAll,
  onOpen,
  beyondFirstPage,
}: Props) {
  // Against the rows on screen, not against the whole selection, which
  // survives paging on purpose.
  const allSelected =
    tickets.length > 0 && tickets.every((t) => selectedIds.includes(t.id));

  if (isLoading) {
    return <p className="text-muted-foreground py-8 text-sm">Loading the queue…</p>;
  }

  if (isError && !tickets.length) {
    // Never the empty state: "no tickets match these filters" is a claim
    // about the queue, and a request that failed licenses no claim about it.
    //
    // Guarded on having nothing to show, because the queue now refetches when
    // the tab regains focus. One failed background refresh must not replace a
    // screen of real tickets with a single line of red text; the page-level
    // banner already says the data may be stale.
    return (
      <p className="text-destructive py-8 text-sm" role="alert">
        The queue could not be loaded.
      </p>
    );
  }

  if (!tickets.length) {
    // Same rule as the failed request above: "no tickets match these filters"
    // is a claim about the queue, and past page one this page cannot make it.
    // A walk is frozen at the moment it started, so every ticket somebody
    // works leaves the set the walk is reading. When the rows in front of the
    // reader are all worked, the next page arrives empty while the tickets on
    // it still match perfectly well.
    return (
      <p className="text-muted-foreground py-8 text-sm">
        {beyondFirstPage
          ? "Nothing left on this page. The tickets that were here have been worked on since you opened the queue, which moves them to the front of it. Go back to page 1 to see them."
          : "No tickets match these filters."}
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
            // A click handler on a <tr> is invisible to the keyboard, and
            // opening a ticket is the only thing this page is for. The rest
            // of the platform puts the action on a real control
            // (components/user/UserTable.tsx); this keeps the whole-row
            // target and adds the keyboard path it was missing.
            tabIndex={0}
            role="button"
            aria-label={`Open ${ticket.ticketNumber}`}
            onClick={() => onOpen(ticket.id)}
            onKeyDown={(event) => {
              // Only when the row itself has focus. Without this the checkbox
              // inside it never gets its own space key: the event bubbles up,
              // this handler opens the drawer and preventDefault cancels the
              // toggle, which puts bulk assign out of reach from a keyboard.
              if (event.target !== event.currentTarget) return;
              if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                onOpen(ticket.id);
              }
            }}
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
