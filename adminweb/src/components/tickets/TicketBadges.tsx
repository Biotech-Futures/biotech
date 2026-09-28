import { Badge } from "@/components/ui/badge";
import {
  TICKET_PRIORITY_LABELS,
  TICKET_STATUS_LABELS,
  type TicketPriority,
  type TicketStatus,
} from "@/schema/ticket";

// Same reading as the student-facing app: green while it is ours to move,
// amber while it is theirs, grey once it is done. The colours are not shared
// with it — each app clears 4.5:1 against its own ground, and the grounds
// differ.
//
// The grey is neutral-100/neutral-600 rather than muted/muted-foreground.
// Those two tokens are oklch(0.97 0 0) and oklch(0.556 0 0), which render as
// #f5f5f5 and #737373 — 4.35:1, just under AA, on the three badges that use
// them (resolved, normal, low). neutral-100 is the same #f5f5f5, so no
// background pixel changes; neutral-600 is one step darker at 7.17:1, which
// sits inside the range the coloured badges already occupy (emerald 6.68,
// sky 6.54, amber 8.17, red 6.86) instead of making the quietest badge the
// loudest thing in the row.
//
// Changing --muted-foreground globally was the alternative and is worse: it
// is used 332 times across 71 files and only fails when paired with bg-muted.
//
// The hover: half has to move with it. tailwind-merge does not merge across
// the prefix, so a leftover hover:bg-muted would survive alongside
// bg-neutral-100 — identical today, and a badge that changes colour only
// under the pointer the day somebody retunes --muted.
const STATUS_CLASS: Record<TicketStatus, string> = {
  open: "bg-emerald-100 text-emerald-800 hover:bg-emerald-100",
  in_progress: "bg-sky-100 text-sky-800 hover:bg-sky-100",
  pending_user: "bg-amber-100 text-amber-900 hover:bg-amber-100",
  resolved: "bg-neutral-100 text-neutral-600 hover:bg-neutral-100",
};

const PRIORITY_CLASS: Record<TicketPriority, string> = {
  high: "bg-red-100 text-red-800 hover:bg-red-100",
  normal: "bg-neutral-100 text-neutral-600 hover:bg-neutral-100",
  low: "bg-neutral-100 text-neutral-600 hover:bg-neutral-100",
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
