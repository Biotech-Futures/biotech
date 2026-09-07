import { getRouteApi } from "@tanstack/react-router";

// The typed handle a code-split component uses to reach its route's search
// params — the component cannot import the Route object itself without
// recreating the circular import this file exists to break.
const route = getRouteApi("/_auth/tickets/");
import { useEffect, useRef, useState } from "react";
import { TablePaginationBar } from "@/components/ui/table-pagination";
import { BulkAssignBar } from "@/components/tickets/BulkAssignBar";
import { CounterCards } from "@/components/tickets/CounterCards";
import { FilterBar } from "@/components/tickets/FilterBar";
import { QueueTable } from "@/components/tickets/QueueTable";
import { TicketDetailPanel } from "@/components/tickets/TicketDetailPanel";
import {
  useAssignees,
  useBulkAssign,
  useTicketRegions,
  useTicketSummary,
  useTicketsQuery,
} from "@/query/ticket";
import type { TicketFilters } from "@/schema/ticket";
import { useAuthContext } from "@/provider/AuthProvider";

// The response names a failure by internal id, and an agent has never seen
// one of those. The ticket number is what is on the row, in the search box and
// in the ticket itself, so that is what a failure has to be reported as.
function describeFailure(
  failure: { ticketId: number; error?: string },
  numbers: Map<number, string>,
) {
  const name = numbers.get(failure.ticketId) ?? `ticket ${failure.ticketId}`;
  // `||`, not `??`: the reason is an optional string, so an exception with no
  // message reaches us as "" rather than as nothing, and "SUP-2026-00001 ()"
  // reads as a bug in this page.
  return `${name} (${failure.error || "no reason given"})`;
}

// The queue page, out of the route file for the same reason as
// AdminHomePage next door: exporting a component from a route file turns off
// autoCodeSplitting for that route, and the two exports together cost the
// main chunk 170 kB. The test imports it from here.
export function TicketQueuePage() {
  const { user } = useAuthContext();
  const navigate = route.useNavigate();
  const { ticket: openTicketId } = route.useSearch();

  const [page, setPage] = useState(1);
  const [limit, setLimit] = useState(10);
  const [filters, setFilters] = useState<TicketFilters>({});
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  // Where each page of the current walk starts.
  //
  // The queue is ordered by last support activity, so its order moves while
  // somebody reads it. Paging by offset over that loses tickets — measured:
  // an internal note on three of two hundred, and those three appeared on no
  // page while the footer still said "20 of 20". So Next carries the snapshot
  // the walk began under plus the sort key of the last row served, and the
  // server returns the rows strictly after that place. Nothing in front of the
  // reader can push a row behind them.
  //
  // Held in a ref rather than state: writing it must not re-render, and it is
  // read during render for the page being requested.
  const walks = useRef(new Map<number, { asOf: string; after: string }>());

  // Page one has nothing in front of it, and a page reached by clicking its
  // number in the footer is the agent choosing to skip — neither continues a
  // walk, so both are answered live.
  const queue = useTicketsQuery(page, limit, filters, walks.current.get(page));

  // Each page hands the next one its starting place. In an effect rather than
  // derived, because the value has to outlive the response it arrived on.
  useEffect(() => {
    if (queue.data?.after) {
      walks.current.set(page + 1, {
        asOf: queue.data.asOf,
        after: queue.data.after,
      });
    }
  }, [page, queue.data?.asOf, queue.data?.after]);

  // Anything that changes what is being walked starts a new walk.
  const restartWalk = () => walks.current.clear();

  const goToPage = (next: number) => {
    // Only stepping one page forward continues the walk. Everything else,
    // Previous included, is a jump, and a jump reads from a fresh snapshot.
    // Keeping the old cursors across a jump would mix two walks and show
    // pages from different moments as if they were one.
    //
    // Previous therefore re-reads by offset, and a row worked while the
    // reader was ahead of it can come back a second time on the way down.
    // That is visible and harmless: no row is lost either way, which is the
    // property the snapshot exists to hold.
    //
    // Reaching page N-1 with the forward cursor page N-2 handed out was
    // tried and reverted. It does not remove the repeats, it moves them:
    // measured against the queue endpoint, 220 tickets ten to a page with
    // three worked behind the reader, the cursor route repeated six rows
    // across pages where the offset route repeated three. Rows leaving the
    // snapshot shrink it, so an old cursor pulls the following page's rows
    // up into the gap. Do not restore it without measuring both routes.
    if (next !== page + 1) restartWalk();
    setPage(next);
  };
  const summary = useTicketSummary();
  const assignees = useAssignees();
  const regions = useTicketRegions();
  const bulkAssign = useBulkAssign();

  const tickets = queue.data?.items ?? [];

  // Ticket numbers outlive the rows they came from. A partial bulk assign has
  // to name the tickets it could not do, and those are precisely the ones that
  // have just left the queue, so by then there is no row to read a number off.
  //
  // Filled during render rather than in an effect: a page that mounts with a
  // finished mutation already in the cache would otherwise read the map one
  // render before anything wrote to it. The write is a cache of what is on
  // screen, so repeating it costs nothing.
  const numbersSeen = useRef(new Map<number, string>());
  for (const ticket of tickets) {
    numbersSeen.current.set(ticket.id, ticket.ticketNumber);
  }

  const bulkFailures = (bulkAssign.data?.results ?? []).filter((r) => !r.ok);

  // Which list is down, in the order they are named. Saying both when only one
  // failed sends the agent hunting for a fault that is not there, and only the
  // assignee list feeds the assign controls.
  const listsDown = [
    assignees.isError && "assignee",
    regions.isError && "region",
  ].filter((name): name is string => Boolean(name));

  // hasMore is the floor, not the total. `total` counts the walk's frozen set,
  // and a ticket somebody works mid-walk leaves it — so the count can fall
  // below the page being read, and Next would go dead with rows still ahead.
  const totalPages = Math.max(
    1,
    Math.ceil((queue.data?.total ?? 0) / limit),
    queue.data?.hasMore ? page + 1 : page,
  );

  const openTicket = (id: number | null) =>
    navigate({ search: { ticket: id ?? undefined }, replace: true });

  const applyFilters = (next: TicketFilters) => {
    setFilters(next);
    // Page 3 of the old filter is rarely page 3 of the new one.
    restartWalk();
    setPage(1);
    setSelectedIds([]);
  };

  const toggle = (id: number) =>
    setSelectedIds((current) =>
      current.includes(id) ? current.filter((x) => x !== id) : [...current, id],
    );

  // Scoped to the rows on screen. The selection deliberately survives paging,
  // so comparing its total length against this page's row count made the
  // header checkbox answer a question nobody asked: with 10 selected on page
  // one it showed page two as fully selected, and clicking it cleared the
  // other page's selection instead of selecting this one.
  const toggleAll = () =>
    setSelectedIds((current) => {
      const pageIds = tickets.map((t) => t.id);
      const allOnPage =
        pageIds.length > 0 && pageIds.every((id) => current.includes(id));
      return allOnPage
        ? current.filter((id) => !pageIds.includes(id))
        : [...new Set([...current, ...pageIds])];
    });

  // null hands the batch back to the pool, which the endpoint has always
  // accepted and no control on this page could ask for.
  const assignSelected = (assigneeId: number | null) => {
    bulkAssign.mutate(
      { ticketIds: selectedIds, assigneeId },
      { onSuccess: () => setSelectedIds([]) },
    );
  };

  return (
    <div className="space-y-4 p-4">
      <div>
        <h1 className="text-2xl font-semibold">Ticket queue</h1>
        <p className="text-muted-foreground text-sm">
          Enquiries from across the platform, most recently active first.
        </p>
      </div>

      <CounterCards
        summary={summary.data}
        isLoading={summary.isLoading}
        isError={summary.isError}
        // Spread, not the card's filter on its own: applyFilters replaces the
        // whole filter state, so passing it alone would silently clear
        // whatever region or status the agent had already narrowed to.
        onShowFilter={(filter) => applyFilters({ ...filters, ...filter })}
      />

      {queue.isError && (
        <p className="text-destructive text-sm" role="alert">
          The queue could not be loaded, so this page is not showing the real
          state of it. Reload to try again.
        </p>
      )}

      <FilterBar
        filters={filters}
        onChange={applyFilters}
        regions={regions.data ?? []}
        assignees={assignees.data ?? []}
      />

      {/* The two option lists fail quietly on their own: an empty list looks
          exactly like a platform with nobody on it. The assignee query also
          feeds the assign controls further down this page, which is why this
          sits above them rather than inside the filter bar. */}
      {listsDown.length > 0 && (
        <p className="text-destructive text-sm" role="alert">
          The {listsDown.join(" and ")} list{listsDown.length > 1 ? "s" : ""}{" "}
          could not be loaded. The filters above are missing those choices
          {assignees.isError && ", and so are the assign controls on this page"}
          . Reload to try again.
        </p>
      )}

      {/* Two different failures, and the two belong in different places.
          A partial failure comes back as a 200, so onSuccess clears the
          selection and its message has to live *outside* this block to
          survive that. A rejected request (a 400 from an assignee the write
          path refuses, a dropped connection) never reaches onSuccess, so the
          selection is still there and the message belongs with it — rendered
          outside, it outlived the bar and left an agent reading a warning
          about a batch that was no longer selected. */}
      {selectedIds.length > 0 && (
        <>
          <BulkAssignBar
            count={selectedIds.length}
            assignees={assignees.data ?? []}
            // The banner above names the failure once for the whole page. The
            // bar says it again inside its own dropdown, which still offers
            // the pool and so no longer looks empty when the list is down.
            assigneesUnavailable={assignees.isError}
            isPending={bulkAssign.isPending}
            onClear={() => {
              setSelectedIds([]);
              // Or the next selection opens showing the last one's failure.
              bulkAssign.reset();
            }}
            onAssign={assignSelected}
          />
          {bulkAssign.isError && (
            <p className="text-destructive text-sm" role="alert">
              {/* Nobody was picked when the batch went back to the pool, so
                  the advice below is about a person who does not exist and
                  reads as a second, unrelated fault. */}
              {bulkAssign.variables?.assigneeId === null
                ? "Could not hand the selected tickets back to the pool. Nothing was changed. Try again."
                : "Could not assign the selected tickets. Nothing was changed — check that the person you picked can still work the queue, then try again."}
            </p>
          )}
        </>
      )}

      {bulkAssign.data && bulkFailures.length > 0 && (
        <p className="text-destructive text-sm" role="alert">
          {bulkFailures.length} of {bulkAssign.data.results.length} could not be
          assigned:{" "}
          {bulkFailures.map((f) => describeFailure(f, numbersSeen.current)).join("; ")}
          .
          {/* Only when every failure is the deleted-row branch. bulk_assign
              fails two ways: a row that is gone reads "not found", and
              anything the write itself throws comes back as the exception
              text. That second kind can come good on a second try, so this
              page must not tell the agent one is pointless. */}
          {bulkFailures.every((f) => f.error === "not found") &&
            " Tickets deleted while they sat in the selection come back as not found, and sending the batch again will not change that."}
        </p>
      )}

      <QueueTable
        tickets={tickets}
        isLoading={queue.isLoading}
        isError={queue.isError}
        selectedIds={selectedIds}
        onToggle={toggle}
        onToggleAll={toggleAll}
        onOpen={openTicket}
        // Not every page past the first continues the walk: clicking a page
        // number in the footer drops the cursors and reads a fresh snapshot,
        // and an empty page there says nothing about rows being worked ahead
        // of the reader.
        beyondFirstPage={page > 1 && walks.current.has(page)}
      />

      <TablePaginationBar
        page={page}
        totalPages={totalPages}
        onPageChange={goToPage}
        pageSize={limit}
        onPageSizeChange={(size) => {
          setLimit(size);
          restartWalk();
          setPage(1);
        }}
        disabled={queue.isLoading}
      />

      <TicketDetailPanel
        ticketId={openTicketId ?? null}
        assignees={assignees.data ?? []}
        onClose={() => openTicket(null)}
        canDelete={Boolean(user?.isAdmin)}
        onDeleted={(id) =>
          // Drop it from the selection too. The bulk bar counts selectedIds,
          // so leaving it there makes the bar offer to assign a ticket that
          // no longer exists.
          setSelectedIds((current) => current.filter((x) => x !== id))
        }
      />
    </div>
  );
}
