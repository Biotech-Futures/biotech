// Out of the route file for the same reason as TicketQueuePage and
// AdminHomePage: a route file that exports anything but its Route turns
// off autoCodeSplitting for that route, and the components that did it
// cost the main chunk 170 kB between them. Its test imports it from here.
import { useMemo, useState } from "react";
import { Link } from "@tanstack/react-router";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { TablePaginationBar } from "@/components/ui/table-pagination";
import { useAssignees, useTicketAudit } from "@/query/ticket";
import { wasRefused } from "@/lib/queryError";
import {
  TICKET_AUDIT_ACTIONS,
  TICKET_PRIORITY_LABELS,
  auditActionLabel,
  auditActorName,
  categoryLabel,
  TICKET_STATUS_LABELS,
  type AssigneeOption,
  type TicketAuditRow,
} from "@/schema/ticket";


const ANY = "__any__";

// The people on this screen, which is a wider set than the assignee roster:
// a requester who reopens their own ticket appears here and never there.
type Actor = NonNullable<TicketAuditRow["actor"]>;

function when(value: string) {
  return new Date(value).toLocaleString("en-AU", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    // Rendered in whatever zone the reader's machine is in, so the zone has
    // to be on screen. Same rule as the queue's last activity column: the
    // same row reads 03:37 pm in Sydney and 02:37 am in Sao Paulo, and this
    // is the screen people quote timestamps off when they compare notes.
    timeZoneName: "short",
  });
}

/** A stored value as the rest of the product writes it.
 *
 *  The audit page is the one screen whose entire job is being read, so it
 *  cannot be the one screen that prints database values. Every other place a
 *  status appears — the queue badge, the dashboard axis, all three emails —
 *  says "In progress", not "in_progress". */
function label(
  value: unknown,
  labels: Record<string, string>,
  missing = "—",
): string {
  if (typeof value !== "string" || value === "") return missing;
  return labels[value] ?? value;
}

/** A screening verdict's category as words.
 *
 *  The categories are decided by a module that is not in this repository, so
 *  there is no list here to look them up in. Underscores out and one capital
 *  is as far as this page can honestly go, and it beats printing self_harm at
 *  a reader. */
function humanise(value: string) {
  const words = value.replace(/_/g, " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}

/** Which ticket the row is about.
 *
 *  The id every time, deletions included, so that one ticket wears one name
 *  on the screen. Only a creation and a deletion carry the number in their
 *  snapshot, and naming those two by number printed the same ticket as
 *  SUP-2026-00250 on one row and #250 on the next.
 *
 *  An id is not a ticket number, and the two stop looking alike soon.
 *  numbering.py opens a fresh counter every year, while the ids carry on, so
 *  the first ticket of 2027 is SUP-2027-00001 on an id that follows the last
 *  one of 2026. Today's pairs line up only because the platform is in its
 *  first year of numbering.
 *
 *  The number is not lost. A deletion still prints it in What changed, that
 *  being the one row whose ticket cannot be opened to read it off. */
function ticketName(row: TicketAuditRow) {
  return `#${row.ticketId}`;
}

/** Who did it, when the row names nobody.
 *
 *  The wording and the reasoning live in schema/ticket.ts, because the
 *  History list on the detail panel prints the same AuditLog rows through the
 *  per-ticket endpoint and has to say the same thing about them. It used to
 *  say "system". */
function actorName(row: TicketAuditRow) {
  return auditActorName(row.actor, row.afterState);
}

/** What changed, in one line.
 *
 *  A deletion is the case this screen exists for, and it is also the only row
 *  whose ticket cannot be opened to read its number off. So the number goes
 *  here, out of the snapshot the delete wrote. */
function summarise(row: TicketAuditRow, people: AssigneeOption[]) {
  const before = row.beforeState ?? {};
  const after = row.afterState ?? {};

  if (row.action === "delete") {
    // Whatever the snapshot holds, in the order a person reads it. A delete
    // records both parts, so a row with only one of them is an old row or a
    // snapshot that half wrote, and half of it still beats none of it.
    const named = [before.ticket_number, before.subject].filter(
      (part) => typeof part === "string" && part !== "",
    );
    return named.length > 0 ? named.join(" · ") : "Ticket removed from the queue";
  }
  if (row.action === "create") {
    // Nothing changed: the ticket came into being. What is worth reading is
    // why the screener raised it, and this snapshot is the only place that
    // says so.
    const flagged = after.screening_category;
    return typeof flagged === "string" && flagged !== ""
      ? `Flagged as ${humanise(flagged)}`
      : "Ticket opened";
  }
  if (typeof before.status === "string" || typeof after.status === "string") {
    return `${label(before.status, TICKET_STATUS_LABELS)} → ${label(after.status, TICKET_STATUS_LABELS)}`;
  }
  if ("assignee_id" in before || "assignee_id" in after) {
    if (after.assignee_id === null) return "Handed back to the pool";
    // A name, not "#11". The Who column beside this one already prints
    // names, so an id here reads as a different kind of thing entirely.
    // Falls back to the id when the roster has not loaded or the person has
    // since been deleted — an id is poor, but blank would be worse.
    const owner = people.find((p) => p.id === after.assignee_id);
    return owner ? `Owner set to ${owner.name}` : `Owner set to #${after.assignee_id}`;
  }
  if (typeof before.priority === "string") {
    return `${label(before.priority, TICKET_PRIORITY_LABELS)} → ${label(after.priority, TICKET_PRIORITY_LABELS)}`;
  }
  // Re-filing, which support gained when the client replaced the three
  // categories with eight. Without this branch the row fell through to "—",
  // so the one screen whose job is being read said a change had happened and
  // refused to say what it was.
  if (typeof before.category === "string") {
    return `${categoryLabel(before.category)} → ${categoryLabel(after.category as string)}`;
  }
  return "—";
}

export function TicketAuditPage() {
  // Filters and paging live here and not on the URL, so following a ticket
  // link out of this page and pressing back lands on page 1 with no filter.
  // Putting them on the URL means a validateSearch in the route file
  // audit.tsx, the way routes/_auth/tickets/index.tsx does it, and that file
  // is not this component's to change.
  const [page, setPage] = useState(1);
  const [limit, setLimit] = useState(25);
  const [action, setAction] = useState("");
  const [actor, setActor] = useState<Actor | null>(null);

  const audit = useTicketAudit(page, limit, {
    action,
    actor: actor ? String(actor.id) : "",
  });
  const people = useAssignees();

  // Who did this is not the question the roster answers. The roster is who
  // can be handed a ticket; a requester who reopens their own is on this
  // screen and never on that list, so the rows themselves have to supply the
  // people it leaves out.
  const actorOptions = useMemo(() => {
    const byId = new Map<number, string>();
    for (const person of people.data ?? []) byId.set(person.id, person.name);
    for (const row of audit.data?.items ?? []) {
      if (row.actor) byId.set(row.actor.id, row.actor.name);
    }
    // Picking somebody leaves only their own rows on screen. Without this the
    // option just picked drops out of the list it was picked from as soon as
    // the two filters together match nothing.
    if (actor) byId.set(actor.id, actor.name);
    // Only the page in front of the reader. Somebody whose rows all sit on
    // another page is still not selectable from here, and the list changes as
    // the reader pages through. A complete one needs the server to name the
    // actors of the whole filtered log, which it does not do yet.
    return Array.from(byId, ([id, name]) => ({ id, name })).sort((a, b) =>
      a.name.localeCompare(b.name),
    );
  }, [people.data, audit.data, actor]);

  const change = (setter: (value: string) => void) => (value: string) => {
    setter(value === ANY ? "" : value);
    // Page 3 of the old filter is rarely page 3 of the new one.
    setPage(1);
  };

  const chooseActor = (value: string) => {
    setActor(
      value === ANY
        ? null
        : (actorOptions.find((person) => String(person.id) === value) ?? null),
    );
    setPage(1);
  };

  // The page size the server actually used, which is not always the one asked
  // for. views.py clamps limit to MAX_PAGE_SIZE, 100, and answers with what it
  // served; the rows-per-page control offers 200 and a custom box that reaches
  // 500. Dividing the total by the asked-for size called 300 rows two pages of
  // 200 while the server was sending three pages of 100, and the hundred rows
  // past the end of page 2 could be reached from nowhere in the footer.
  //
  // The control is fed the same number for the same reason: left on 200 it
  // stands there claiming a page size the server is not honouring.
  const served = audit.data?.limit ?? limit;

  return (
    <div className="space-y-4 p-6">
      <div>
        <h1 className="text-xl font-semibold">Ticket audit</h1>
        <p className="text-muted-foreground mt-1 text-sm">
          Every recorded action, including deletions. A deleted ticket keeps its
          record here after it has left the queue.
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <Select value={action || ANY} onValueChange={change(setAction)}>
          <SelectTrigger className="w-[190px]" aria-label="Filter by action">
            <SelectValue placeholder="Action" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ANY}>Any action</SelectItem>
            {TICKET_AUDIT_ACTIONS.map((option) => (
              <SelectItem key={option.value} value={option.value}>
                {option.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Select
          value={actor ? String(actor.id) : ANY}
          onValueChange={chooseActor}
        >
          <SelectTrigger className="w-[190px]" aria-label="Filter by who did it">
            <SelectValue placeholder="Anyone" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ANY}>Anyone</SelectItem>
            {actorOptions.map((person) => (
              <SelectItem key={person.id} value={String(person.id)}>
                {person.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {audit.isError ? (
        <p className="text-destructive text-sm" role="alert">
          {wasRefused(audit.error)
            ? "You do not have access to the ticket audit. It is open to the support team and to administrators."
            : "The audit log could not be loaded."}
        </p>
      ) : (
        <>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-[170px]">When</TableHead>
                <TableHead className="w-[150px]">Ticket</TableHead>
                <TableHead className="w-[140px]">Action</TableHead>
                <TableHead className="w-[170px]">Who</TableHead>
                <TableHead>What changed</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {audit.isLoading && (
                <TableRow>
                  <TableCell colSpan={5} className="text-muted-foreground">
                    Loading…
                  </TableCell>
                </TableRow>
              )}
              {audit.data?.items.length === 0 && (
                <TableRow>
                  <TableCell colSpan={5} className="text-muted-foreground">
                    {/* The screening handoff is the only writer of a
                        Created row. A ticket a requester submits records
                        none, so that filter answers nothing on a platform
                        with a hundred tickets on it, and a bare empty table
                        reads as a log that has stopped recording. */}
                    {action === "create"
                      ? "Nothing recorded for this filter. Only the automated screening writes a Created row. A ticket somebody submitted from the portal does not write one."
                      : "Nothing recorded for this filter."}
                  </TableCell>
                </TableRow>
              )}
              {(audit.data?.items ?? []).map((row) => (
                <TableRow key={row.id}>
                  <TableCell className="text-muted-foreground text-xs">
                    {when(row.createdAt)}
                  </TableCell>
                  <TableCell>
                    {row.action === "delete" ? (
                      // Nothing to open. This row is the record of the ticket
                      // going away, so a link would send the reader after the
                      // very thing the row says is gone.
                      <span className="text-muted-foreground">
                        {ticketName(row)}
                      </span>
                    ) : (
                      // These link even when that ticket has since been
                      // deleted, which nothing on the row can tell. The panel
                      // answers that case itself with "That ticket could not
                      // be opened. It may have been deleted." That is an
                      // answer, not a loose end to tidy up here.
                      <Link
                        to="/tickets"
                        search={{ ticket: row.ticketId }}
                        className="text-primary underline-offset-2 hover:underline"
                        title={`Open ticket ${ticketName(row)}`}
                      >
                        {ticketName(row)}
                      </Link>
                    )}
                  </TableCell>
                  <TableCell>{auditActionLabel(row.action)}</TableCell>
                  <TableCell>{actorName(row)}</TableCell>
                  <TableCell className="text-sm">{summarise(row, people.data ?? [])}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>

          <TablePaginationBar
            page={page}
            totalPages={Math.max(1, Math.ceil((audit.data?.total ?? 0) / served))}
            onPageChange={setPage}
            pageSize={served}
            onPageSizeChange={(next) => {
              setLimit(next);
              setPage(1);
            }}
            disabled={audit.isLoading}
          />
        </>
      )}
    </div>
  );
}
