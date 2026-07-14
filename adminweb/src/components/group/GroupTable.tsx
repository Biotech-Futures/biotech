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
import { ArrowDownIcon, ArrowUpDownIcon, ArrowUpIcon } from "lucide-react";
import { useState } from "react";

export interface GroupTableSelection {
  isSelected: (id: string) => boolean;
  onToggleRow: (id: string) => void;
  headerState: boolean | "indeterminate";
  onToggleAll: () => void;
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
                      checked={selection.headerState}
                      onCheckedChange={selection.onToggleAll}
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
                    selection?.isSelected(row.original.id) ? "selected" : undefined
                  }
                >
                  {selection && (
                    <TableCell
                      className="w-10"
                      onClick={(event) => event.stopPropagation()}
                    >
                      <Checkbox
                        checked={selection.isSelected(row.original.id)}
                        onCheckedChange={() =>
                          selection.onToggleRow(row.original.id)
                        }
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
