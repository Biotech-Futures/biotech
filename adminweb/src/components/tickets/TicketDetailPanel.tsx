import { useEffect, useState } from "react";
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
  TICKET_CATEGORY_OPTIONS,
  TICKET_PRIORITY_LABELS,
  TICKET_STATUS_LABELS,
  UNASSIGNED,
  auditActionLabel,
  auditActorName,
  categoryLabel,
  type AssigneeOption,
  type TicketMessage,
} from "@/schema/ticket";
import {
  ticketAttachmentUrl,
  useDeleteTicket,
  useReplyTicket,
  useTicketDetail,
  useTicketHistory,
  useUpdateTicket,
} from "@/query/ticket";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { ticketRefusalReason } from "@/lib/ticketError";

type Props = {
  ticketId: number | null;
  assignees: AssigneeOption[];
  onClose: () => void;
  /** Only admins may delete (DEC-024), so the control is not rendered at all
   *  for a support agent. The server refuses them either way. */
  canDelete: boolean;
  /** Told which ticket went, so the queue can drop it from the selection. */
  onDeleted: (id: number) => void;
};

function whenDate(value: string) {
  // Date only. "Member since 26 Aug 2026, 09:14" reads like an event; the
  // field is there to answer "new account or long-standing participant".
  return new Date(value).toLocaleDateString("en-AU", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

function when(value: string) {
  return new Date(value).toLocaleString("en-AU", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    // Rendered in whatever zone the reader's machine is in, so the zone has
    // to be on screen. Same rule as the queue's last activity column: the
    // same message reads 03:37 pm in Sydney and 02:37 am in Sao Paulo, and
    // agents in two places read this timeline to each other.
    timeZoneName: "short",
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
        {/* Only a user_message with no author is the requester. Support rows
            lose their author when an agent's account is deleted, and calling
            that "Requester" attributes an internal note to the student it was
            written about.

            The label says what is known and no more. A support row with no
            author has three possible origins and the payload tells them
            apart in none of them: an agent whose account was deleted,
            screening's evidence note, and the note recording an email that
            could not be delivered. The last two were never written by a
            person, so naming a removed account states something that never
            happened on two rows out of three.

            Not the wording the audit page and the History list below use,
            and deliberately so. Those two read AuditLog rows, where the
            screening handoff is the only writer that leaves the actor empty
            and its rows carry `channel` in their own snapshot to prove it, so
            they can name both cases. A message carries no such evidence, and
            copying their sentence here would be this row claiming a certainty
            it does not have. */}
        <span className="font-semibold">
          {message.author?.name ??
            (message.messageType === "user_message"
              ? "Requester"
              : "Support (author not recorded)")}
        </span>
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

export function TicketDetailPanel({
  ticketId,
  assignees,
  onClose,
  canDelete,
  onDeleted,
}: Props) {
  const [tab, setTab] = useState<"conversation" | "details">("conversation");
  const { data: ticket, isLoading, isError } = useTicketDetail(ticketId);
  const { data: history } = useTicketHistory(tab === "details" ? ticketId : null);
  const update = useUpdateTicket();
  const reply = useReplyTicket();
  const remove = useDeleteTicket();

  // Reset the mutations that render a warning when the panel moves to a
  // different ticket: otherwise a failure on one ticket keeps its red text on
  // screen while the agent is looking at the next one, which reads as a
  // problem with the ticket they are now looking at.
  //
  // `reply` is deliberately not reset — its boxes keep what was typed when a
  // send fails, and that state belongs to the composer, not to this panel.
  useEffect(() => {
    remove.reset();
    update.reset();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ticketId]);

  // The server's own words when it refused, for the same reason the two
  // message boxes read them: a refusal an agent can act on is worth more than
  // a sentence written months ago that guesses at what went wrong.
  const updateReason = ticketRefusalReason(update.error);
  const removeReason = ticketRefusalReason(remove.error);

  // mutateAsync, not mutate: the boxes below keep what was typed when a send
  // fails, and they can only know it failed if the promise reaches them.
  // moveToPending is optional so the internal-note box, which must never move
  // the ticket, can keep passing two arguments.
  const send = (messageType: "support_reply" | "internal_note") =>
    (body: string, files: File[], moveToPending?: boolean) => {
      if (ticketId === null) return Promise.resolve();
      return reply.mutateAsync({
        id: ticketId, messageType, body, files, moveToPending,
      });
    };

  return (
    <Sheet open={ticketId !== null} onOpenChange={(open) => !open && onClose()}>
      <SheetContent className="w-full overflow-y-auto sm:max-w-2xl">
        {isLoading ? (
          <div className="p-6">
            <p className="text-muted-foreground text-sm">Loading…</p>
          </div>
        ) : isError || !ticket ? (
          // Never a permanent spinner. The commonest way to land here is a
          // link to a ticket that has since been deleted, and "Loading…"
          // forever reads as a broken page rather than an answer.
          <div className="p-6">
            <p className="text-destructive text-sm" role="alert">
              That ticket could not be opened. It may have been deleted.
            </p>
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
              {/* All four selects below are controlled by `ticket`, so a
                  rejected PATCH leaves them showing the old value with no
                  other sign. The agent watches the dropdown snap back and has
                  no way to tell that from having misclicked. A 404 here is the
                  ordinary case, not an exotic one: somebody else deleting the
                  ticket while this panel is open produces exactly that, and
                  ticketRefusalReason leaves that one to the sentence below
                  because the sentence below says what to do about it. */}
              {update.isError && (
                <p className="text-destructive text-sm" role="alert">
                  That change was not saved.{" "}
                  {updateReason ??
                    "The ticket may have been deleted or changed by someone else — close the panel and reopen it to see where it stands."}
                </p>
              )}

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

                {/* Re-filing. With three categories a wrong one was
                    tolerable; the client's eight include two near-synonyms
                    ("General Question" and "Other") and two that overlap in
                    practice (Registration and Account and access), so an agent
                    will routinely know a ticket is filed wrong. Without this
                    the category breakdown the client asked for on p52 fills
                    with noise nobody can correct.

                    Full option list, screening's own category included: a
                    ticket message screening filed under Flagged content needs
                    a way out, and a genuine child-safety report that came in
                    through the form needs a way in. */}
                <Select
                  value={ticket.category}
                  onValueChange={(category) =>
                    update.mutate({ id: ticket.id, patch: { category } })
                  }
                >
                  <SelectTrigger
                    className="w-[220px]"
                    aria-label="Change category"
                  >
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {TICKET_CATEGORY_OPTIONS.map((option) => (
                      <SelectItem key={option.value} value={option.value}>
                        {option.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>

                <Select
                  value={
                    ticket.assignee ? String(ticket.assignee.id) : UNASSIGNED
                  }
                  onValueChange={(assignee) =>
                    update.mutate({
                      id: ticket.id,
                      // The sentinel travels as a real JSON null, which is
                      // what the backend reads as "back to the pool".
                      patch: {
                        assignee:
                          assignee === UNASSIGNED ? null : Number(assignee),
                      },
                    })
                  }
                >
                  <SelectTrigger className="w-[190px]" aria-label="Change assignee">
                    <SelectValue placeholder="Unassigned" />
                  </SelectTrigger>
                  <SelectContent>
                    {/* Handing a ticket back. Without this the owner control
                        was one-way: a ticket picked up by mistake stayed in
                        that person's name for good. */}
                    <SelectItem value={UNASSIGNED}>Unassigned</SelectItem>
                    {/* The current owner, even when they are no longer on the
                        assignable list. Without this row the trigger falls
                        back to its placeholder and the panel reads
                        "Unassigned" for a ticket the queue still shows as
                        theirs.

                        The row says the person no longer works the queue
                        rather than that they are inactive. Two different
                        things drop somebody off the assignable list: their
                        account being deactivated, and their queue access
                        being revoked from the support agents page. The second
                        leaves the account fully active, and People says so on
                        the same screen, so "(inactive)" sent an admin to
                        reactivate an account that was never switched off.

                        The test has to be "are they missing from the rows we
                        are about to render", not "are they missing from
                        `assignees`". They are never missing from `assignees`:
                        the endpoint returns one list for two consumers and
                        deliberately keeps past owners in it, marking them
                        assignable: false. Asking the wider question made this
                        row unreachable and produced the exact placeholder
                        fallback the comment above describes. */}
                    {ticket.assignee &&
                      !assignees.some(
                        (p) => p.id === ticket.assignee!.id && p.assignable,
                      ) && (
                        <SelectItem value={String(ticket.assignee.id)}>
                          {ticket.assignee.name} (no longer on the queue)
                        </SelectItem>
                      )}
                    {assignees
                      .filter((person) => person.assignable)
                      .map((person) => (
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
                    <dt className="text-muted-foreground">Member since</dt>
                    <dd>
                      {ticket.requester
                        ? whenDate(ticket.requester.registeredAt)
                        : "—"}
                    </dd>
                    <dt className="text-muted-foreground">Region</dt>
                    <dd>{ticket.region || "Unknown"}</dd>
                    <dt className="text-muted-foreground">Category</dt>
                    <dd>{categoryLabel(ticket.category)}</dd>
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
                    {/* p49 lists Category, Created and Updated as the panel's
                        read-only fields. This was the missing one: the value
                        was already in the payload and parsed by the schema,
                        it just had nowhere to render. Shows the support-side
                        clock, which is the one this panel is about — the
                        requester-facing clock deliberately ignores internal
                        notes and hand-offs, so an agent reading "Updated"
                        here wants to know when anything last happened. */}
                    <dt className="text-muted-foreground">Updated</dt>
                    <dd>{when(ticket.supportUpdatedAt)}</dd>
                  </dl>

                  <div>
                    <p className="mb-2 font-medium">History</p>
                    {history?.length ? (
                      <ul className="space-y-1">
                        {/* The same AuditLog rows the audit page lists, for
                            one ticket instead of all of them, so they are
                            named the same way. This list printed the stored
                            action and called every empty actor "system": one
                            screen said "Status changed by Sam Reid" while
                            this one said "status by system" about the row
                            underneath it, and "system" is plainly wrong for
                            the case an actor goes empty most often, which is
                            the person's account having been deleted.

                            Separated rather than joined with "by", which is
                            what the line used to read. The two names this can
                            print are not people — "Automated screening" and
                            "Account removed" — and "by Account removed" reads
                            as nonsense. Action, who, when, in the audit
                            table's own column order. */}
                        {history.map((entry) => (
                          <li key={entry.id} className="text-muted-foreground text-xs">
                            <span className="font-medium">
                              {auditActionLabel(entry.action)}
                            </span>
                            {" · "}
                            {auditActorName(entry.actor, entry.afterState)}
                            {" · "}
                            {when(entry.createdAt)}
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="text-muted-foreground text-xs">
                        Nothing recorded yet.
                      </p>
                    )}
                  </div>

                  {canDelete && (
                    <div className="border-destructive/30 rounded-md border border-dashed p-3">
                      <p className="mb-1 text-sm font-medium">Delete this ticket</p>
                      <p className="text-muted-foreground mb-3 text-xs">
                        For a duplicate, a test submission or spam. It leaves the
                        queue and the requester's own list, and there is no undo.
                        To close a real enquiry, mark it Resolved instead.
                      </p>
                      <AlertDialog>
                        <AlertDialogTrigger asChild>
                          <Button
                            variant="destructive"
                            size="sm"
                            disabled={remove.isPending}
                          >
                            {remove.isPending ? "Deleting…" : "Delete ticket"}
                          </Button>
                        </AlertDialogTrigger>
                        <AlertDialogContent>
                          <AlertDialogHeader>
                            <AlertDialogTitle>
                              Delete {ticket.ticketNumber}?
                            </AlertDialogTitle>
                            <AlertDialogDescription>
                              This removes it from the queue and from
                              {ticket.requester
                                ? ` ${ticket.requester.name}'s`
                                : " the requester's"}{" "}
                              own list of enquiries. It cannot be undone from the
                              app. A record of the deletion is kept in the history.
                            </AlertDialogDescription>
                          </AlertDialogHeader>
                          <AlertDialogFooter>
                            <AlertDialogCancel>Keep it</AlertDialogCancel>
                            <AlertDialogAction
                              onClick={() =>
                                remove.mutate(ticket.id, {
                                  onSuccess: () => {
                                    onDeleted(ticket.id);
                                    onClose();
                                  },
                                })
                              }
                            >
                              Delete
                            </AlertDialogAction>
                          </AlertDialogFooter>
                        </AlertDialogContent>
                      </AlertDialog>
                      {/* Reached most often by an admin whose admin access
                          was taken away while this panel was open, since
                          canDelete came from a cached session: the server
                          answers "You do not have admin privileges." and
                          "Nothing has changed" on its own leaves them
                          pressing the button again. */}
                      {remove.isError && (
                        <p className="text-destructive mt-2 text-xs" role="alert">
                          That did not delete. Nothing has changed.
                          {removeReason && ` ${removeReason}`}
                        </p>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          </>
        )}
      </SheetContent>
    </Sheet>
  );
}
