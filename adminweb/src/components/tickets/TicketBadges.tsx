import { Badge } from "@/components/ui/badge";
import {
  TICKET_PRIORITY_LABELS,
  TICKET_STATUS_LABELS,
  type TicketPriority,
  type TicketStatus,
} from "@/schema/ticket";

// Same reading as the student-facing app: green while it is ours to move,
// amber while it is theirs, grey once it is done.
const STATUS_CLASS: Record<TicketStatus, string> = {
  open: "bg-emerald-100 text-emerald-800 hover:bg-emerald-100",
  in_progress: "bg-sky-100 text-sky-800 hover:bg-sky-100",
  pending_user: "bg-amber-100 text-amber-900 hover:bg-amber-100",
  resolved: "bg-muted text-muted-foreground hover:bg-muted",
};

const PRIORITY_CLASS: Record<TicketPriority, string> = {
  high: "bg-red-100 text-red-800 hover:bg-red-100",
  normal: "bg-muted text-muted-foreground hover:bg-muted",
  low: "bg-muted text-muted-foreground hover:bg-muted",
};

export function StatusBadge({ status }: { status: TicketStatus }) {
  return (
    <Badge variant="secondary" className={STATUS_CLASS[status]}>
      {TICKET_STATUS_LABELS[status]}
    </Badge>
  );
}

export function PriorityBadge({ priority }: { priority: TicketPriority }) {
  return (
    <Badge variant="secondary" className={PRIORITY_CLASS[priority]}>
      {TICKET_PRIORITY_LABELS[priority]}
    </Badge>
  );
}

export function OverdueBadge() {
  return (
    <Badge variant="secondary" className="bg-red-100 text-red-800 hover:bg-red-100">
      Overdue
    </Badge>
  );
}
