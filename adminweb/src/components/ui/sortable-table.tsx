import { ArrowDownIcon, ArrowUpDownIcon, ArrowUpIcon } from "lucide-react";
import { useMemo, useState } from "react";
import { cn } from "@/lib/utils";

export type SortDirection = "asc" | "desc";

export type SortState<TSortKey extends string> = {
  key: TSortKey;
  direction: SortDirection;
};

type SortableTableHeadProps<TSortKey extends string> = {
  label: string;
  sortKey: TSortKey;
  sortState: SortState<TSortKey>;
  onSortChange: (sortState: SortState<TSortKey>) => void;
  className?: string;
  align?: "left" | "right";
};

export function SortableTableHead<TSortKey extends string>({
  label,
  sortKey,
  sortState,
  onSortChange,
  className,
  align = "left",
}: SortableTableHeadProps<TSortKey>) {
  const active = sortState.key === sortKey;
  const nextDirection: SortDirection =
    active && sortState.direction === "asc" ? "desc" : "asc";
  const Icon = active
    ? sortState.direction === "asc"
      ? ArrowUpIcon
      : ArrowDownIcon
    : ArrowUpDownIcon;

  return (
    <button
      type="button"
      className={cn(
        "flex w-full items-center gap-1.5 rounded-sm py-1 text-left transition hover:text-foreground",
        align === "right" && "justify-end text-right",
        !active && "text-muted-foreground",
        className,
      )}
      onClick={() => onSortChange({ key: sortKey, direction: nextDirection })}
      aria-label={`Sort by ${label} ${nextDirection === "asc" ? "ascending" : "descending"}`}
      aria-sort={
        active
          ? sortState.direction === "asc"
            ? "ascending"
            : "descending"
          : "none"
      }
    >
      <span>{label}</span>
      <Icon className="size-3.5 shrink-0" />
    </button>
  );
}

function normalizeSortValue(value: unknown): string | number {
  if (value === null || value === undefined) return "";
  if (typeof value === "number") return value;
  if (typeof value === "boolean") return value ? 1 : 0;
  if (value instanceof Date) return value.getTime();

  const stringValue = String(value);
  const timestamp = Date.parse(stringValue);
  if (!Number.isNaN(timestamp) && /\d{4}-\d{2}-\d{2}/.test(stringValue)) {
    return timestamp;
  }

  return stringValue.toLocaleLowerCase();
}

export function sortRows<T>(
  rows: T[],
  direction: SortDirection,
  getValue: (row: T) => unknown,
) {
  const multiplier = direction === "asc" ? 1 : -1;

  return [...rows].sort((a, b) => {
    const aValue = normalizeSortValue(getValue(a));
    const bValue = normalizeSortValue(getValue(b));

    if (typeof aValue === "number" && typeof bValue === "number") {
      return (aValue - bValue) * multiplier;
    }

    return (
      String(aValue).localeCompare(String(bValue), undefined, {
        numeric: true,
        sensitivity: "base",
      }) * multiplier
    );
  });
}

export function useSortableRows<T, TSortKey extends string>(
  rows: T[],
  initialSort: SortState<TSortKey>,
  getValue: (row: T, key: TSortKey) => unknown,
) {
  const [sortState, setSortState] = useState<SortState<TSortKey>>(initialSort);
  const sortedRows = useMemo(
    () => sortRows(rows, sortState.direction, (row) => getValue(row, sortState.key)),
    [rows, sortState, getValue],
  );

  return { sortState, setSortState, sortedRows };
}
