import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
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

type TicketSearch = {
  // Deep link. A ticket the platform raised itself carries a link of this
  // shape in its first message, so support can go straight from the
  // notification to the ticket. Without this the panel has no way to open.
  ticket?: number;
};

export const Route = createFileRoute("/_auth/tickets/")({
  validateSearch: (search: Record<string, unknown>): TicketSearch => ({
    ticket: search.ticket ? Number(search.ticket) : undefined,
  }),
  component: TicketQueuePage,
});

function TicketQueuePage() {
  const navigate = useNavigate({ from: Route.fullPath });
  const { ticket: openTicketId } = Route.useSearch();

  const [page, setPage] = useState(1);
  const [limit, setLimit] = useState(10);
  const [filters, setFilters] = useState<TicketFilters>({});
  const [selectedIds, setSelectedIds] = useState<number[]>([]);

  const queue = useTicketsQuery(page, limit, filters);
  const summary = useTicketSummary();
  const assignees = useAssignees();
  const regions = useTicketRegions();
  const bulkAssign = useBulkAssign();

  const tickets = queue.data?.items ?? [];
  const totalPages = Math.max(1, Math.ceil((queue.data?.total ?? 0) / limit));

  const openTicket = (id: number | null) =>
    navigate({ search: { ticket: id ?? undefined }, replace: true });

  const applyFilters = (next: TicketFilters) => {
    setFilters(next);
    // Page 3 of the old filter is rarely page 3 of the new one.
    setPage(1);
    setSelectedIds([]);
  };

  const toggle = (id: number) =>
    setSelectedIds((current) =>
      current.includes(id) ? current.filter((x) => x !== id) : [...current, id],
    );

  const toggleAll = () =>
    setSelectedIds((current) =>
      current.length === tickets.length ? [] : tickets.map((t) => t.id),
    );

  const assignSelected = (assigneeId: number) => {
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

      <CounterCards summary={summary.data} isLoading={summary.isLoading} />

      <FilterBar
        filters={filters}
        onChange={applyFilters}
        regions={regions.data ?? []}
        assignees={assignees.data ?? []}
      />

      {selectedIds.length > 0 && (
        <BulkAssignBar
          count={selectedIds.length}
          assignees={assignees.data ?? []}
          isPending={bulkAssign.isPending}
          onClear={() => setSelectedIds([])}
          onAssign={assignSelected}
        />
      )}

      {bulkAssign.data && bulkAssign.data.results.some((r) => !r.ok) && (
        <p className="text-destructive text-sm">
          {bulkAssign.data.results.filter((r) => !r.ok).length} of{" "}
          {bulkAssign.data.results.length} could not be assigned.
        </p>
      )}

      <QueueTable
        tickets={tickets}
        isLoading={queue.isLoading}
        selectedIds={selectedIds}
        onToggle={toggle}
        onToggleAll={toggleAll}
        onOpen={openTicket}
      />

      <TablePaginationBar
        page={page}
        totalPages={totalPages}
        onPageChange={setPage}
        pageSize={limit}
        onPageSizeChange={(size) => {
          setLimit(size);
          setPage(1);
        }}
        disabled={queue.isLoading}
      />

      <TicketDetailPanel
        ticketId={openTicketId ?? null}
        assignees={assignees.data ?? []}
        onClose={() => openTicket(null)}
      />
    </div>
  );
}
