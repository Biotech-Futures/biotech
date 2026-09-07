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
import { UNASSIGNED, type AssigneeOption } from "@/schema/ticket";

type Props = {
  count: number;
  assignees: AssigneeOption[];
  /** Whether the list above is empty because its endpoint failed. Without it
   *  a dead endpoint and a platform with nobody on it look identical in here,
   *  and the pool line below makes the short list look complete. */
  assigneesUnavailable?: boolean;
  isPending: boolean;
  onClear: () => void;
  onAssign: (assigneeId: number | null) => void;
};

export function BulkAssignBar({
  count,
  assignees,
  assigneesUnavailable,
  isPending,
  onClear,
  onAssign,
}: Props) {
  const [assigneeId, setAssigneeId] = useState<string>("");
  const toThePool = assigneeId === UNASSIGNED;
  // "Assign" is the wrong word for handing a batch back, and the button is
  // the last thing an agent reads before pressing it.
  const label = toThePool ? "Unassign" : "Assign";
  const workingLabel = toThePool ? "Unassigning…" : "Assigning…";

  return (
    <BulkActionsBar count={count} noun="ticket" onClear={onClear} disabled={isPending}>
      <Select value={assigneeId} onValueChange={setAssigneeId}>
        <SelectTrigger className="w-[200px]" aria-label="Assign to">
          <SelectValue placeholder="Assign to…" />
        </SelectTrigger>
        <SelectContent>
          {/* The pool, under the name the filter bar already calls it by. The
              batch endpoint has always taken a null assignee, the way the
              single-ticket PATCH does, but nothing here could say it: an
              agent who swept twenty tickets onto themselves by mistake had
              twenty separate visits to the detail panel to undo it. Above the
              names rather than below, again matching the filter bar. */}
          <SelectItem value={UNASSIGNED}>Unassigned</SelectItem>
          {/* Same filter as the detail panel's assign dropdown. The endpoint
              returns one list for two consumers: the filter dropdown wants
              every past owner, this one wants only people the write path will
              accept. Without the filter a deactivated or revoked agent was
              offered here and the whole batch came back 400. */}
          {assignees
            .filter((person) => person.assignable)
            .map((person) => (
              <SelectItem key={person.id} value={String(person.id)}>
                {person.name}
              </SelectItem>
            ))}
          {/* Said here as well as in the page's banner, because this list is
              not empty any more: the pool line above it is always offered, so
              a failed endpoint leaves a dropdown that opens on one plausible
              option and reads as the whole platform. A disabled item rather
              than loose text, which is the shape the group dialogs already
              use for a list with nothing to offer. */}
          {assigneesUnavailable && (
            <SelectItem value="__unavailable" disabled>
              The assignee list could not be loaded, so there is nobody to pick
              here. Reload to try again.
            </SelectItem>
          )}
        </SelectContent>
      </Select>
      <Button
        size="sm"
        disabled={!assigneeId || isPending}
        // null is what sends a ticket back to the pool. The mutation keeps a
        // JSON null intact, so it arrives as null rather than being dropped.
        onClick={() => onAssign(toThePool ? null : Number(assigneeId))}
      >
        {isPending ? workingLabel : label}
      </Button>
    </BulkActionsBar>
  );
}
