import { Button } from "@/components/ui/button";
import { BulkActionsBar } from "@/components/ui/bulk-actions-bar";
import { Trash2Icon, UserMinusIcon, UsersIcon } from "lucide-react";

interface StudentBulkActionsBarProps {
  count: number;
  /** How many of the selected students currently belong to a group. */
  groupedCount: number;
  onAssign: () => void;
  onRemove: () => void;
  /** When provided, shows a permanent-delete action. Omit to hide it. */
  onDelete?: () => void;
  onClear: () => void;
  isPending?: boolean;
  /** True in "select all matching" mode: group actions need loaded rows, so
   *  only Delete (resolved server-side by filter) is available. */
  disableGroupActions?: boolean;
}

export function StudentBulkActionsBar({
  count,
  groupedCount,
  onAssign,
  onRemove,
  onDelete,
  onClear,
  isPending,
  disableGroupActions,
}: StudentBulkActionsBarProps) {
  const groupActionsHint = disableGroupActions
    ? "Select students individually to assign or remove from groups"
    : undefined;
  return (
    <BulkActionsBar
      count={count}
      noun="student"
      onClear={onClear}
      disabled={isPending}
    >
      {/* Wrapper carries the tooltip: a disabled button has no pointer events. */}
      <span title={groupActionsHint}>
        <Button
          variant="outline"
          size="sm"
          onClick={onAssign}
          disabled={isPending || disableGroupActions}
        >
          <UsersIcon />
          Assign to group
        </Button>
      </span>
      <span
        title={
          groupActionsHint ??
          (groupedCount === 0
            ? "None of the selected students are in a group"
            : undefined)
        }
      >
        <Button
          variant="outline"
          size="sm"
          className="text-destructive hover:text-destructive"
          onClick={onRemove}
          disabled={isPending || disableGroupActions || groupedCount === 0}
        >
          <UserMinusIcon />
          Remove from group{groupedCount > 0 ? ` (${groupedCount})` : ""}
        </Button>
      </span>
      {onDelete ? (
        <Button
          variant="outline"
          size="sm"
          className="text-destructive hover:text-destructive"
          onClick={onDelete}
          disabled={isPending}
        >
          <Trash2Icon />
          Delete
        </Button>
      ) : null}
    </BulkActionsBar>
  );
}
