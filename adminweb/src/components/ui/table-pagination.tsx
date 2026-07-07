import { PageNav } from "@/components/ui/pagination-nav";
import { PageSizeSelect } from "@/components/user/PageSizeSelect";

interface TablePaginationBarProps {
  page: number;
  totalPages: number;
  onPageChange: (page: number) => void;
  /** Provide both to show the rows-per-page selector. */
  pageSize?: number;
  onPageSizeChange?: (size: number) => void;
  disabled?: boolean;
}

/** Shared table footer: rows-per-page (optional) + page indicator + numbered nav. */
export function TablePaginationBar({
  page,
  totalPages,
  onPageChange,
  pageSize,
  onPageSizeChange,
  disabled,
}: TablePaginationBarProps) {
  const showPageSize = pageSize != null && onPageSizeChange != null;

  return (
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div className="flex flex-wrap items-center gap-4">
        {showPageSize && (
          <PageSizeSelect
            value={pageSize}
            onChange={onPageSizeChange}
            disabled={disabled}
          />
        )}
        <p className="text-sm text-muted-foreground">
          Page {page} of {totalPages}
        </p>
      </div>
      <PageNav
        page={page}
        totalPages={totalPages}
        onPageChange={onPageChange}
        disabled={disabled}
      />
    </div>
  );
}
