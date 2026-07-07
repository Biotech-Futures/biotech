import type { ColumnDef, SortingState } from "@tanstack/react-table";
import {
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
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
import type { StudentUser } from "@/type/user";
import { ArrowDownIcon, ArrowUpDownIcon, ArrowUpIcon } from "lucide-react";
import { useState } from "react";

export type StudentSortKey =
  | "name"
  | "school"
  | "yearLevel"
  | "state"
  | "group"
  | "interests";

export interface StudentTableSelection {
  isSelected: (id: number) => boolean;
  onToggleRow: (student: StudentUser) => void;
  headerState: boolean | "indeterminate";
  onToggleAll: () => void;
}

interface StudentTableProps {
  data: StudentUser[];
  columns: ColumnDef<StudentUser>[];
  page: number;
  totalPages: number;
  onPageChange: (page: number) => void;
  pageSize?: number;
  onPageSizeChange?: (size: number) => void;
  onRowClick?: (student: StudentUser) => void;
  sorting?: SortingState;
  onSortingChange?: (sorting: SortingState) => void;
  manualSorting?: boolean;
  isPending?: boolean;
  selection?: StudentTableSelection;
}

export function StudentTable({
  data,
  columns,
  page,
  totalPages,
  onPageChange,
  pageSize,
  onPageSizeChange,
  onRowClick,
  sorting: controlledSorting,
  onSortingChange,
  manualSorting,
  isPending,
  selection,
}: StudentTableProps) {
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

  // Column span for the loading / empty rows, accounting for the select column.
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
                      aria-label="Select all students on this page"
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
                        {flexRender(header.column.columnDef.header, header.getContext())}
                        {header.column.getIsSorted() === "asc" ? (
                          <ArrowUpIcon className="ml-1.5 size-3.5" />
                        ) : header.column.getIsSorted() === "desc" ? (
                          <ArrowDownIcon className="ml-1.5 size-3.5" />
                        ) : (
                          <ArrowUpDownIcon className="ml-1.5 size-3.5" />
                        )}
                      </Button>
                    ) : (
                      flexRender(header.column.columnDef.header, header.getContext())
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
            ) : table.getRowModel().rows.length ? (
              table.getRowModel().rows.map((row) => (
                <TableRow
                  key={row.id}
                  onClick={() => onRowClick?.(row.original)}
                  data-state={
                    selection?.isSelected(row.original.id) ? "selected" : undefined
                  }
                  className={onRowClick && row.original.groupId ? "cursor-pointer hover:bg-muted/40" : undefined}
                >
                  {selection && (
                    <TableCell
                      className="w-10"
                      onClick={(event) => event.stopPropagation()}
                    >
                      <Checkbox
                        checked={selection.isSelected(row.original.id)}
                        onCheckedChange={() => selection.onToggleRow(row.original)}
                        aria-label={`Select ${row.original.firstName} ${row.original.lastName}`.trim()}
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
                  No students found.
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
