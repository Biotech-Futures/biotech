import { Button } from "@/components/ui/button";
import { UserMinusIcon, UsersIcon, XIcon } from "lucide-react";

interface StudentBulkActionsBarProps {
  count: number;
  /** How many of the selected students currently belong to a group. */
  groupedCount: number;
  onAssign: () => void;
  onRemove: () => void;
  onClear: () => void;
  isPending?: boolean;
}

export function StudentBulkActionsBar({
  count,
  groupedCount,
  onAssign,
  onRemove,
  onClear,
  isPending,
}: StudentBulkActionsBarProps) {
  return (
    <div
      role="toolbar"
      aria-label="Bulk actions"
      className="flex flex-wrap items-center justify-between gap-2 rounded-md border bg-muted/50 px-3 py-2"
    >
      <div className="flex items-center gap-1">
        <p className="text-sm font-medium" aria-live="polite">
          {count} {count === 1 ? "student" : "students"} selected
        </p>
        <Button
          variant="ghost"
          size="sm"
          onClick={onClear}
          disabled={isPending}
          aria-label="Clear selection"
        >
          <XIcon />
          Clear
        </Button>
      </div>
      <div className="flex items-center gap-2">
        <Button
          variant="outline"
          size="sm"
          onClick={onAssign}
          disabled={isPending}
        >
          <UsersIcon />
          Assign to group
        </Button>
        {/* Wrapper carries the tooltip: a disabled button has no pointer events. */}
        <span
          title={
            groupedCount === 0
              ? "None of the selected students are in a group"
              : undefined
          }
        >
          <Button
            variant="outline"
            size="sm"
            className="text-destructive hover:text-destructive"
            onClick={onRemove}
            disabled={isPending || groupedCount === 0}
          >
            <UserMinusIcon />
            Remove from group{groupedCount > 0 ? ` (${groupedCount})` : ""}
          </Button>
        </span>
      </div>
    </div>
  );
}
