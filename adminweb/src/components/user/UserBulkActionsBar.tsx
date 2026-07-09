import { Button } from "@/components/ui/button";
import { BulkActionsBar } from "@/components/ui/bulk-actions-bar";
import { UserCheckIcon, UserXIcon } from "lucide-react";

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
    <BulkActionsBar
      count={count}
      noun="user"
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
    </BulkActionsBar>
  );
}
