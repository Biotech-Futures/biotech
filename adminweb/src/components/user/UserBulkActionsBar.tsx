import { Button } from "@/components/ui/button";
import { UserCheckIcon, UserXIcon, XIcon } from "lucide-react";

interface UserBulkActionsBarProps {
  count: number;
  onActivate: () => void;
  onDeactivate: () => void;
  onClear: () => void;
  isPending?: boolean;
}

export function UserBulkActionsBar({
  count,
  onActivate,
  onDeactivate,
  onClear,
  isPending,
}: UserBulkActionsBarProps) {
  return (
    <div
      role="toolbar"
      aria-label="Bulk actions"
      className="flex flex-wrap items-center justify-between gap-2 rounded-md border bg-muted/50 px-3 py-2"
    >
      <div className="flex items-center gap-1">
        <p className="text-sm font-medium" aria-live="polite">
          {count} {count === 1 ? "user" : "users"} selected
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
      </div>
    </div>
  );
}
