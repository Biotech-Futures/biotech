import type { ColumnDef } from "@tanstack/react-table";
import {
  flexRender,
  getCoreRowModel,
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
import { Input } from "@/components/ui/input";
import { ChevronLeftIcon, ChevronRightIcon } from "lucide-react";
import type { Resource } from "@/type/resource";
import { useEffect, useMemo, useRef, useState } from "react";

interface ResourceTableProps {
  columns: ColumnDef<Resource>[];
  data: Resource[];
  page: number;
  totalPages: number;
  onPageChange: (page: number) => void;
  bulkMode: boolean;
  selectedIds: number[];
  onSelectedIdsChange: (ids: number[]) => void;
  isPending?: boolean;
}

export function ResourceTable({
  columns,
  data,
  page,
  totalPages,
  onPageChange,
  bulkMode,
  selectedIds,
  onSelectedIdsChange,
  isPending,
}: ResourceTableProps) {
  const [pageInput, setPageInput] = useState(String(page));
  const selectAllRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    setPageInput(String(page));
  }, [page]);

  const handleJumpPage = () => {
    const parsed = Number.parseInt(pageInput, 10);
    if (Number.isNaN(parsed)) {
      setPageInput(String(page));
      return;
    }

    const nextPage = Math.min(totalPages, Math.max(1, parsed));
    onPageChange(nextPage);
  };

  const table = useReactTable({
    data,
    columns,
    getCoreRowModel: getCoreRowModel(),
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
    <div className="space-y-4">
      <div className="rounded-md border">
        <Table>
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
                  <TableHead key={header.id}>
                    {header.isPlaceholder
                      ? null
                      : flexRender(header.column.columnDef.header, header.getContext())}
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
                        aria-label={`Select resource ${row.original.resource_name}`}
                      />
                    </TableCell>
                  ) : null}
                  {row.getVisibleCells().map((cell) => (
                    <TableCell key={cell.id}>
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

      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          Page {page} of {totalPages}
        </p>
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-2">
            <Input
              value={pageInput}
              onChange={(event) => setPageInput(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  handleJumpPage();
                }
              }}
              className="w-18"
              inputMode="numeric"
              pattern="[0-9]*"
              aria-label="Go to page"
            />
            <Button
              variant="outline"
              size="sm"
              onClick={handleJumpPage}
              disabled={isPending}
            >
              Go
            </Button>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => onPageChange(page - 1)}
            disabled={page <= 1 || isPending}
          >
            <ChevronLeftIcon className="size-4" />
            Previous
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => onPageChange(page + 1)}
            disabled={page >= totalPages || isPending}
          >
            Next
            <ChevronRightIcon className="size-4" />
          </Button>
        </div>
      </div>
    </div>
  );
}
