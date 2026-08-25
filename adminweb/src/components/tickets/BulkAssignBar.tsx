import { useState } from "react";
import { BulkActionsBar } from "@/components/ui/bulk-actions-bar";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { AssigneeOption } from "@/schema/ticket";

type Props = {
  count: number;
  assignees: AssigneeOption[];
  isPending: boolean;
  onClear: () => void;
  onAssign: (assigneeId: number) => void;
};

export function BulkAssignBar({
  count,
  assignees,
  isPending,
  onClear,
  onAssign,
}: Props) {
  const [assigneeId, setAssigneeId] = useState<string>("");

  return (
    <BulkActionsBar count={count} noun="ticket" onClear={onClear} disabled={isPending}>
      <Select value={assigneeId} onValueChange={setAssigneeId}>
        <SelectTrigger className="w-[200px]" aria-label="Assign to">
          <SelectValue placeholder="Assign to…" />
        </SelectTrigger>
        <SelectContent>
          {assignees.map((person) => (
            <SelectItem key={person.id} value={String(person.id)}>
              {person.name}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      <Button
        size="sm"
        disabled={!assigneeId || isPending}
        onClick={() => onAssign(Number(assigneeId))}
      >
        {isPending ? "Assigning…" : "Assign"}
      </Button>
    </BulkActionsBar>
  );
}
