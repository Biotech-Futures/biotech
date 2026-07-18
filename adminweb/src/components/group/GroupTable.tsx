// Group table component with pagination

import type { ColumnDef, SortingState } from "@tanstack/react-table";
import {
  flexRender,
  getCoreRowModel,
  useReactTable,
  getSortedRowModel,
} from "@tanstack/react-table";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { TablePaginationBar } from "@/components/ui/table-pagination";
import type { Group } from "@/type/group";
import {
  ArrowDownIcon,
  ArrowUpDownIcon,
  ArrowUpIcon,
  CheckCheckIcon,
  InfoIcon,
} from "lucide-react";
import { useState } from "react";

export interface GroupTableSelection {
  /** Explicitly checked row ids (used when selectAllMatching is false). */
  selectedIds: Set<string>;
  /** True once the admin has expanded selection to the whole filtered set. */
  selectAllMatching: boolean;
  /** Rows unchecked while in selectAllMatching mode. */
  excludedIds: Set<string>;
  /** Total groups matching the current filters (across all pages). */
  total: number;
  onSelectionChange: (ids: Set<string>) => void;
  onExcludedChange: (ids: Set<string>) => void;
  onSelectAllMatching: () => void;
  onClear: () => void;
}

interface GroupTableProps {
  columns: ColumnDef<Group>[];
  data: Group[];
  // Pagination
  page: number;
  totalPages: number;
  onPageChange: (page: number) => void;
  pageSize: number;
  onPageSizeChange: (size: number) => void;
  sorting?: SortingState;
  onSortingChange?: (sorting: SortingState) => void;
  manualSorting?: boolean;
  isPending?: boolean;
  selection?: GroupTableSelection;
}

export function GroupTable({
  columns,
  data,
  page,
  totalPages,
  onPageChange,
  pageSize,
  onPageSizeChange,
  sorting: controlledSorting,
  onSortingChange,
  manualSorting,
  isPending,
  selection,
}: GroupTableProps) {
  const [internalSorting, setInternalSorting] = useState<SortingState>([]);
  const sorting = controlledSorting ?? internalSorting;
  const table = useReactTable({
    data,
    columns,
    state: { sorting },
    onSortingChange: (updater) => {
      const next = typeof updater === "function" ? updater(sorting) : updater;
      if (onSortingChange) onSortingChange(next);
      else setInternalSorting(next);
    },
    manualSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  const spanCount = columns.length + (selection ? 1 : 0);

  const pageIds = data.map((group) => group.id);
  const isRowSelected = (id: string) =>
    selection
      ? selection.selectAllMatching
        ? !selection.excludedIds.has(id)
        : selection.selectedIds.has(id)
      : false;
  const selectedOnPage = pageIds.filter(isRowSelected);
  const headerChecked: boolean | "indeterminate" =
    selectedOnPage.length === 0
      ? false
      : selectedOnPage.length === pageIds.length
        ? true
        : "indeterminate";

  const toggleAllOnPage = () => {
    if (!selection) return;
    const wholePageSelected =
      pageIds.length > 0 && selectedOnPage.length === pageIds.length;
    if (selection.selectAllMatching) {
      const next = new Set(selection.excludedIds);
      // Whole page currently selected -> exclude it; otherwise re-include it.
      if (wholePageSelected) pageIds.forEach((id) => next.add(id));
      else pageIds.forEach((id) => next.delete(id));
      selection.onExcludedChange(next);
      return;
    }
    const next = new Set(selection.selectedIds);
    if (wholePageSelected) pageIds.forEach((id) => next.delete(id));
    else pageIds.forEach((id) => next.add(id));
    selection.onSelectionChange(next);
  };

  const toggleOne = (id: string) => {
    if (!selection) return;
    if (selection.selectAllMatching) {
      const next = new Set(selection.excludedIds);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      selection.onExcludedChange(next);
      return;
    }
    const next = new Set(selection.selectedIds);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    selection.onSelectionChange(next);
  };

  const excludedCount = selection?.excludedIds.size ?? 0;
  const total = selection?.total ?? 0;
  const effectiveAllCount = Math.max(0, total - excludedCount);
  const showExpandOffer =
    !!selection &&
    !selection.selectAllMatching &&
    pageIds.length > 0 &&
    selectedOnPage.length === pageIds.length &&
    total > pageIds.length;
  const showSelectionBanner =
    !isPending && (showExpandOffer || !!selection?.selectAllMatching);

  return (
    <div className="space-y-4">
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            {table.getHeaderGroups().map((headerGroup) => (
              <TableRow key={headerGroup.id}>
                {selection && (
                  <TableHead className="w-10">
                    <Checkbox
                      checked={headerChecked}
                      onCheckedChange={toggleAllOnPage}
                      disabled={isPending || data.length === 0}
                      aria-label="Select all groups on this page"
                    />
                  </TableHead>
                )}
                {headerGroup.headers.map((header) => (
                  <TableHead key={header.id}>
                    {header.isPlaceholder ? null : header.column.getCanSort() ? (
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="-ml-3 h-8 px-2"
                        onClick={header.column.getToggleSortingHandler()}
                      >
                        {flexRender(
                          header.column.columnDef.header,
                          header.getContext()
                        )}
                        {header.column.getIsSorted() === "asc" ? (
                          <ArrowUpIcon className="ml-1.5 size-3.5" />
                        ) : header.column.getIsSorted() === "desc" ? (
                          <ArrowDownIcon className="ml-1.5 size-3.5" />
                        ) : (
                          <ArrowUpDownIcon className="ml-1.5 size-3.5" />
                        )}
                      </Button>
                    ) : (
                      flexRender(
                        header.column.columnDef.header,
                        header.getContext()
                      )
                    )}
                  </TableHead>
                ))}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {selection && showSelectionBanner && (
              <TableRow className="border-primary/20 bg-primary/10 hover:bg-primary/10">
                <TableCell
                  colSpan={spanCount}
                  className="py-3 text-center text-sm"
                >
                  {selection.selectAllMatching ? (
                    <span className="inline-flex flex-wrap items-center justify-center gap-2">
                      <CheckCheckIcon
                        className="size-4 text-primary"
                        aria-hidden
                      />
                      <span aria-live="polite" className="font-medium">
                        {excludedCount > 0
                          ? `${effectiveAllCount} of ${total} groups selected.`
                          : `All ${total} groups matching these filters are selected.`}
                      </span>
                      <Button
                        variant="link"
                        size="sm"
                        className="h-auto p-0 font-semibold underline"
                        onClick={selection.onClear}
                      >
                        Clear selection
                      </Button>
                    </span>
                  ) : (
                    <span className="inline-flex flex-wrap items-center justify-center gap-2">
                      <InfoIcon className="size-4 text-primary" aria-hidden />
                      <span className="font-medium">
                        All {pageIds.length} groups on this page are selected.
                      </span>
                      <Button
                        variant="link"
                        size="sm"
                        className="h-auto p-0 font-semibold underline"
                        onClick={selection.onSelectAllMatching}
                      >
                        Select all {total} groups matching these filters
                      </Button>
                    </span>
                  )}
                </TableCell>
              </TableRow>
            )}
            {isPending ? (
              <TableRow>
                <TableCell colSpan={spanCount} className="h-24 text-center">
                  Loading...
                </TableCell>
              </TableRow>
            ) : table.getRowModel().rows?.length ? (
              table.getRowModel().rows.map((row) => (
                <TableRow
                  key={row.id}
                  data-state={
                    isRowSelected(row.original.id) ? "selected" : undefined
                  }
                >
                  {selection && (
                    <TableCell
                      className="w-10"
                      onClick={(event) => event.stopPropagation()}
                    >
                      <Checkbox
                        checked={isRowSelected(row.original.id)}
                        onCheckedChange={() => toggleOne(row.original.id)}
                        aria-label={`Select ${row.original.name}`}
                      />
                    </TableCell>
                  )}
                  {row.getVisibleCells().map((cell) => (
                    <TableCell key={cell.id}>
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </TableCell>
                  ))}
                </TableRow>
              ))
            ) : (
              <TableRow>
                <TableCell colSpan={spanCount} className="h-24 text-center">
                  No groups found.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      <TablePaginationBar
        page={page}
        totalPages={totalPages}
        onPageChange={onPageChange}
        pageSize={pageSize}
        onPageSizeChange={onPageSizeChange}
        disabled={isPending}
      />
    </div>
  );
}
