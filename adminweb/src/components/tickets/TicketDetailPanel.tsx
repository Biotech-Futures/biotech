import { useState } from "react";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { OverdueBadge, PriorityBadge, StatusBadge } from "./TicketBadges";
import { InternalNoteBox } from "./InternalNoteBox";
import { ReplyBox } from "./ReplyBox";
import {
  TICKET_PRIORITY_LABELS,
  TICKET_STATUS_LABELS,
  type AssigneeOption,
  type TicketMessage,
} from "@/schema/ticket";
import {
  ticketAttachmentUrl,
  useReplyTicket,
  useTicketDetail,
  useTicketHistory,
  useUpdateTicket,
} from "@/query/ticket";

type Props = {
  ticketId: number | null;
  assignees: AssigneeOption[];
  onClose: () => void;
};

function when(value: string) {
  return new Date(value).toLocaleString("en-AU", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function MessageRow({ message, ticketId }: { message: TicketMessage; ticketId: number }) {
  if (message.messageType === "system") {
    return (
      <li className="text-muted-foreground py-1 text-center text-xs">
        {message.body} · {when(message.createdAt)}
      </li>
    );
  }

  const isInternal = message.messageType === "internal_note";
  return (
    <li
      className={
        isInternal
          ? "rounded-md border-2 border-dashed border-amber-400 bg-amber-50 p-3"
          : "rounded-md border p-3"
      }
    >
      <p className="mb-1 flex flex-wrap items-baseline gap-2 text-xs">
        <span className="font-semibold">{message.author?.name ?? "Requester"}</span>
        {isInternal && (
          <span className="font-semibold text-amber-900">🔒 Internal note</span>
        )}
        <span className="text-muted-foreground">{when(message.createdAt)}</span>
      </p>
      <p className="text-sm whitespace-pre-wrap break-words">{message.body}</p>
      {message.attachments.length > 0 && (
        <ul className="mt-2 space-y-1">
          {message.attachments.map((file) => (
            <li key={file.id}>
              <a
                className="text-primary text-xs underline"
                href={ticketAttachmentUrl(ticketId, file.id)}
                target="_blank"
                rel="noopener"
              >
                {file.filename}
              </a>
            </li>
          ))}
        </ul>
      )}
    </li>
  );
}

export function TicketDetailPanel({ ticketId, assignees, onClose }: Props) {
  const [tab, setTab] = useState<"conversation" | "details">("conversation");
  const { data: ticket, isLoading } = useTicketDetail(ticketId);
  const { data: history } = useTicketHistory(tab === "details" ? ticketId : null);
  const update = useUpdateTicket();
  const reply = useReplyTicket();

  const send = (messageType: "support_reply" | "internal_note") =>
    (body: string, files: File[]) => {
      if (ticketId === null) return;
      reply.mutate({ id: ticketId, messageType, body, files });
    };

  return (
    <Sheet open={ticketId !== null} onOpenChange={(open) => !open && onClose()}>
      <SheetContent className="w-full overflow-y-auto sm:max-w-2xl">
        {isLoading || !ticket ? (
          <div className="p-6">
            <p className="text-muted-foreground text-sm">Loading…</p>
          </div>
        ) : (
          <>
            <SheetHeader>
              <SheetTitle className="flex flex-wrap items-center gap-2">
                <span>{ticket.ticketNumber}</span>
                <StatusBadge status={ticket.status} />
                <PriorityBadge priority={ticket.priority} />
                {ticket.overdue && <OverdueBadge />}
              </SheetTitle>
              <p className="text-left text-sm font-medium">{ticket.subject}</p>
            </SheetHeader>

            <div className="space-y-4 px-4 pb-6">
              {/* Status and assignee are two separate controls on purpose: the
                  backend refuses a request carrying both, because each drives a
                  different transition. */}
              <div className="flex flex-wrap gap-2">
                <Select
                  value={ticket.status}
                  onValueChange={(status) =>
                    update.mutate({ id: ticket.id, patch: { status } })
                  }
                >
                  <SelectTrigger className="w-[160px]" aria-label="Change status">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {Object.entries(TICKET_STATUS_LABELS).map(([value, label]) => (
                      <SelectItem key={value} value={value}>
                        {label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>

                <Select
                  value={ticket.priority}
                  onValueChange={(priority) =>
                    update.mutate({ id: ticket.id, patch: { priority } })
                  }
                >
                  <SelectTrigger className="w-[140px]" aria-label="Change priority">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {Object.entries(TICKET_PRIORITY_LABELS).map(([value, label]) => (
                      <SelectItem key={value} value={value}>
                        {label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>

                <Select
                  value={ticket.assignee ? String(ticket.assignee.id) : ""}
                  onValueChange={(assignee) =>
                    update.mutate({
                      id: ticket.id,
                      patch: { assignee: Number(assignee) },
                    })
                  }
                >
                  <SelectTrigger className="w-[190px]" aria-label="Change assignee">
                    <SelectValue placeholder="Unassigned" />
                  </SelectTrigger>
                  <SelectContent>
                    {assignees.map((person) => (
                      <SelectItem key={person.id} value={String(person.id)}>
                        {person.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="flex gap-1 border-b">
                {(["conversation", "details"] as const).map((name) => (
                  <button
                    key={name}
                    type="button"
                    onClick={() => setTab(name)}
                    className={
                      tab === name
                        ? "border-primary -mb-px border-b-2 px-3 py-2 text-sm font-medium capitalize"
                        : "text-muted-foreground -mb-px px-3 py-2 text-sm capitalize"
                    }
                  >
                    {name}
                  </button>
                ))}
              </div>

              {tab === "conversation" ? (
                <>
                  <ul className="space-y-2">
                    {ticket.messages.map((message) => (
                      <MessageRow
                        key={message.id}
                        message={message}
                        ticketId={ticket.id}
                      />
                    ))}
                  </ul>
                  <ReplyBox
                    isPending={reply.isPending}
                    onSend={send("support_reply")}
                  />
                  <InternalNoteBox
                    isPending={reply.isPending}
                    onSend={send("internal_note")}
                  />
                </>
              ) : (
                <div className="space-y-4 text-sm">
                  <dl className="grid grid-cols-2 gap-x-4 gap-y-2">
                    <dt className="text-muted-foreground">Requester</dt>
                    <dd>{ticket.requester?.name ?? "—"}</dd>
                    <dt className="text-muted-foreground">Email</dt>
                    <dd className="break-all">{ticket.requester?.email ?? "—"}</dd>
                    <dt className="text-muted-foreground">Region</dt>
                    <dd>{ticket.region || "Unknown"}</dd>
                    <dt className="text-muted-foreground">Category</dt>
                    <dd>{ticket.category || "—"}</dd>
                    <dt className="text-muted-foreground">Channel</dt>
                    <dd>{ticket.channel}</dd>
                    <dt className="text-muted-foreground">Raised</dt>
                    <dd>{when(ticket.createdAt)}</dd>
                    <dt className="text-muted-foreground">First reply</dt>
                    <dd>
                      {ticket.firstResponseAt ? when(ticket.firstResponseAt) : "Not yet"}
                    </dd>
                    <dt className="text-muted-foreground">Resolved</dt>
                    <dd>{ticket.resolvedAt ? when(ticket.resolvedAt) : "—"}</dd>
                  </dl>

                  <div>
                    <p className="mb-2 font-medium">History</p>
                    {history?.length ? (
                      <ul className="space-y-1">
                        {history.map((entry) => (
                          <li key={entry.id} className="text-muted-foreground text-xs">
                            <span className="font-medium">{entry.action}</span>
                            {" by "}
                            {entry.actor?.name ?? "system"} · {when(entry.createdAt)}
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="text-muted-foreground text-xs">
                        Nothing recorded yet.
                      </p>
                    )}
                  </div>
                </div>
              )}
            </div>
          </>
        )}
      </SheetContent>
    </Sheet>
  );
}
