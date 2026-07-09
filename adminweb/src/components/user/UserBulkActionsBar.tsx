import { Button } from "@/components/ui/button";
import { BulkActionsBar } from "@/components/ui/bulk-actions-bar";
import { Trash2Icon, UserCheckIcon, UserXIcon } from "lucide-react";

interface UserBulkActionsBarProps {
  count: number;
  noun?: string;
  onActivate: () => void;
  onDeactivate: () => void;
  /** When provided, shows a permanent-delete action. Omit to hide it. */
  onDelete?: () => void;
  onClear: () => void;
  isPending?: boolean;
}

export function UserBulkActionsBar({
  count,
  noun = "user",
  onActivate,
  onDeactivate,
  onDelete,
  onClear,
  isPending,
}: UserBulkActionsBarProps) {
  return (
    <BulkActionsBar
      count={count}
      noun={noun}
      onClear={onClear}
      disabled={isPending}
    >
      <Button
        variant="outline"
        size="sm"
        onClick={onActivate}
        disabled={isPending}
      >
        <UserCheckIcon />
        Activate
      </Button>
      <Button
        variant="outline"
        size="sm"
        className="text-destructive hover:text-destructive"
        onClick={onDeactivate}
        disabled={isPending}
      >
        <UserXIcon />
        Deactivate
      </Button>
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
