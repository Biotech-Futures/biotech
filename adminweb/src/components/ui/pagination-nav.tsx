import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

type PageItem = number | "ellipsis";

// Sliding window of page numbers with the first and last page always pinned.
// A single otherwise-hidden page is shown inline instead of behind an ellipsis.
function getPageItems(current: number, total: number): PageItem[] {
  const maxButtons = 7;
  if (total <= maxButtons) {
    return Array.from({ length: total }, (_, i) => i + 1);
  }

  const windowSize = maxButtons - 4; // slots between the pinned first/last + 2 ellipses
  let start = Math.max(2, current - Math.floor(windowSize / 2));
  let end = start + windowSize - 1;
  if (end > total - 1) {
    end = total - 1;
    start = end - windowSize + 1;
  }

  const items: PageItem[] = [1];
  if (start > 3) items.push("ellipsis");
  else for (let p = 2; p < start; p++) items.push(p);
  for (let p = start; p <= end; p++) items.push(p);
  if (end < total - 2) items.push("ellipsis");
  else for (let p = end + 1; p < total; p++) items.push(p);
  items.push(total);
  return items;
}

interface PageNavProps {
  page: number;
  totalPages: number;
  onPageChange: (page: number) => void;
  disabled?: boolean;
}

/** Numbered page navigation with Previous/Next and first/last pinned. */
export function PageNav({
  page,
  totalPages,
  onPageChange,
  disabled,
}: PageNavProps) {
  const items = getPageItems(page, totalPages);

  return (
    <nav
      aria-label="Pagination"
      className="flex flex-wrap items-center justify-end gap-1"
    >
      <Button
        variant="outline"
        size="sm"
        onClick={() => onPageChange(page - 1)}
        disabled={page <= 1 || disabled}
      >
        Previous
      </Button>
      {items.map((item, index) =>
        item === "ellipsis" ? (
          <span
            key={`ellipsis-${index}`}
            className="px-1 text-sm text-muted-foreground select-none"
            aria-hidden
          >
            …
          </span>
        ) : (
          <Button
            key={item}
            variant={item === page ? "default" : "outline"}
            size="sm"
            className={cn("h-8 min-w-8 px-2 tabular-nums")}
            aria-label={`Go to page ${item}`}
            aria-current={item === page ? "page" : undefined}
            onClick={() => onPageChange(item)}
            disabled={disabled}
          >
            {item}
          </Button>
        ),
      )}
      <Button
        variant="outline"
        size="sm"
        onClick={() => onPageChange(page + 1)}
        disabled={page >= totalPages || disabled}
      >
        Next
      </Button>
    </nav>
  );
}
