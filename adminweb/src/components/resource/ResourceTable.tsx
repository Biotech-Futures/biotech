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
import { TablePaginationBar } from "@/components/ui/table-pagination";
import { ArrowDownIcon, ArrowUpDownIcon, ArrowUpIcon } from "lucide-react";
import type { Resource } from "@/type/resource";
import { useEffect, useMemo, useRef, useState } from "react";

type ResourceColumnMeta = {
  headClassName?: string;
  cellClassName?: string;
};

interface ResourceTableProps {
  columns: ColumnDef<Resource>[];
  data: Resource[];
  page: number;
  totalPages: number;
  onPageChange: (page: number) => void;
  pageSize?: number;
  onPageSizeChange?: (size: number) => void;
  bulkMode: boolean;
  selectedIds: number[];
  onSelectedIdsChange: (ids: number[]) => void;
  sorting?: SortingState;
  onSortingChange?: (sorting: SortingState) => void;
  manualSorting?: boolean;
  isPending?: boolean;
}

export function ResourceTable({
  columns,
  data,
  page,
  totalPages,
  onPageChange,
  pageSize,
  onPageSizeChange,
  bulkMode,
  selectedIds,
  onSelectedIdsChange,
  sorting: controlledSorting,
  onSortingChange,
  manualSorting,
  isPending,
}: ResourceTableProps) {
  const [internalSorting, setInternalSorting] = useState<SortingState>([]);
  const sorting = controlledSorting ?? internalSorting;
  const selectAllRef = useRef<HTMLInputElement | null>(null);

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

  const pageIds = useMemo(() => data.map((item) => item.id), [data]);
  const selectedSet = useMemo(() => new Set(selectedIds), [selectedIds]);
  const selectedCountInPage = useMemo(
    () => pageIds.filter((id) => selectedSet.has(id)).length,
    [pageIds, selectedSet],
  );
  const isAllSelectedInPage = pageIds.length > 0 && selectedCountInPage === pageIds.length;
  const isSomeSelectedInPage = selectedCountInPage > 0 && !isAllSelectedInPage;

  useEffect(() => {
    if (!selectAllRef.current) return;
    selectAllRef.current.indeterminate = isSomeSelectedInPage;
  }, [isSomeSelectedInPage]);

  const toggleAllInPage = (checked: boolean) => {
    if (checked) {
      const merged = Array.from(new Set([...selectedIds, ...pageIds]));
      onSelectedIdsChange(merged);
      return;
    }
    onSelectedIdsChange(selectedIds.filter((id) => !pageIds.includes(id)));
  };

  const toggleOne = (id: number, checked: boolean) => {
    if (checked) {
      onSelectedIdsChange(Array.from(new Set([...selectedIds, id])));
      return;
    }
    onSelectedIdsChange(selectedIds.filter((item) => item !== id));
  };

  const selectionColumnCount = bulkMode ? 1 : 0;

  return (
    <div className="min-w-0 space-y-4">
      <div className="rounded-md border overflow-x-auto">
        <Table className="table-fixed">
          <TableHeader>
            {table.getHeaderGroups().map((headerGroup) => (
              <TableRow key={headerGroup.id}>
                {bulkMode ? (
                  <TableHead className="w-10">
                    <input
                      ref={selectAllRef}
                      type="checkbox"
                      checked={isAllSelectedInPage}
                      onChange={(event) => toggleAllInPage(event.target.checked)}
                      aria-label="Select all rows on current page"
                    />
                  </TableHead>
                ) : null}
                {headerGroup.headers.map((header) => (
                  <TableHead
                    key={header.id}
                    className={
                      (header.column.columnDef.meta as ResourceColumnMeta | undefined)
                        ?.headClassName
                    }
                  >
                    {header.isPlaceholder ? null : header.column.getCanSort() ? (
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="-ml-3 h-8 min-w-0 px-2"
                        onClick={header.column.getToggleSortingHandler()}
                      >
                        <span className="truncate">
                          {flexRender(header.column.columnDef.header, header.getContext())}
                        </span>
                        {header.column.getIsSorted() === "asc" ? (
                          <ArrowUpIcon className="ml-1.5 size-3.5 shrink-0" />
                        ) : header.column.getIsSorted() === "desc" ? (
                          <ArrowDownIcon className="ml-1.5 size-3.5 shrink-0" />
                        ) : (
                          <ArrowUpDownIcon className="ml-1.5 size-3.5 shrink-0" />
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
                <TableCell colSpan={columns.length + selectionColumnCount} className="h-24 text-center">
                  Loading...
                </TableCell>
              </TableRow>
            ) : table.getRowModel().rows?.length ? (
              table.getRowModel().rows.map((row) => (
                <TableRow key={row.id}>
                  {bulkMode ? (
                    <TableCell className="w-10">
                      <input
                        type="checkbox"
                        checked={selectedSet.has(row.original.id)}
                        onChange={(event) => toggleOne(row.original.id, event.target.checked)}
                        aria-label={`Select resource ${row.original.name}`}
                      />
                    </TableCell>
                  ) : null}
                  {row.getVisibleCells().map((cell) => (
                    <TableCell
                      key={cell.id}
                      className={
                        (cell.column.columnDef.meta as ResourceColumnMeta | undefined)
                          ?.cellClassName
                      }
                    >
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </TableCell>
                  ))}
                </TableRow>
              ))
            ) : (
              <TableRow>
                <TableCell colSpan={columns.length + selectionColumnCount} className="h-24 text-center">
                  No resources found.
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
