import { Button } from "@/components/ui/button";
import { XIcon } from "lucide-react";
import type { ReactNode } from "react";

interface BulkActionsBarProps {
  count: number;
  /** Singular noun for the selected rows, e.g. "announcement". */
  noun: string;
  onClear: () => void;
  disabled?: boolean;
  /** Action buttons rendered on the right. */
  children: ReactNode;
}

/** Shared selection toolbar: "{n} {noun}s selected" + Clear + action buttons. */
export function BulkActionsBar({
  count,
  noun,
  onClear,
  disabled,
  children,
}: BulkActionsBarProps) {
  return (
    <div
      role="toolbar"
      aria-label="Bulk actions"
      className="flex flex-wrap items-center justify-between gap-2 rounded-md border bg-muted/50 px-3 py-2"
    >
      <div className="flex items-center gap-1">
        <p className="text-sm font-medium" aria-live="polite">
          {count} {count === 1 ? noun : `${noun}s`} selected
        </p>
        <Button
          variant="ghost"
          size="sm"
          onClick={onClear}
          disabled={disabled}
          aria-label="Clear selection"
        >
          <XIcon />
          Clear
        </Button>
      </div>
      <div className="flex items-center gap-2">{children}</div>
    </div>
  );
}
