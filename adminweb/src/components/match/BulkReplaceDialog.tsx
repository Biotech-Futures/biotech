import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useNavigate } from "@tanstack/react-router";
import { useQueryMentorReplaceSuggestions } from "@/query/mentorMatch";
import { ShowFullMentorsToggle } from "@/components/mentor/ShowFullMentorsToggle";
import { isMentorSelectable, useMentorPrefs } from "@/store/mentorPrefs";
import type { MatchedGroup, MentorListItem } from "@/type/mentorMatch";

const UNASSIGN_VALUE = "__unassign__";

type BulkReplaceDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  inactiveGroups: MatchedGroup[];
  mentors: MentorListItem[];
  onConfirm: (
    assignments: Array<{ groupId: number; mentorUserId: number }>,
    unassigns: number[],
  ) => Promise<void>;
  isPending: boolean;
};

/**
 * One group's replacement row. Fetches scored mentor suggestions for the group,
 * defaults the selection to the best match, and lists mentors best-first with a
 * score; falls back to the flat mentor list for anyone the matcher didn't score.
 */
function BulkReplaceRow({
  group,
  mentors,
  open,
  value,
  onSelect,
}: {
  group: MatchedGroup;
  mentors: MentorListItem[];
  open: boolean;
  value: string | undefined;
  onSelect: (value: string) => void;
}) {
  const showFullMentors = useMentorPrefs((s) => s.showFullMentors);
  const { data, isLoading } = useQueryMentorReplaceSuggestions(
    group.groupId,
    open,
  );
  const allSuggestions = data?.data.suggestions ?? [];
  // Never auto-select or offer a mentor with no room, unless the admin opted in.
  // The admin's own current pick always stays listed so the Select keeps its value.
  const suggestions = allSuggestions.filter(
    (s) => showFullMentors || !s.atCapacity || value === String(s.mentorUserId),
  );
  const top = suggestions[0];

  // Pre-select the best match once suggestions load, unless the admin already chose.
  useEffect(() => {
    if (value === undefined && top) onSelect(String(top.mentorUserId));
  }, [top, value, onSelect]);

  const scoredIds = new Set(allSuggestions.map((s) => s.mentorUserId));
  const extraMentors = mentors.filter(
    (m) =>
      !scoredIds.has(m.mentorId) &&
      isMentorSelectable(m, showFullMentors, value ? Number(value) : null),
  );

  return (
    <div className="flex items-center justify-between gap-3 rounded-lg border p-3">
      <div className="min-w-0">
        <p className="truncate text-sm font-medium">{group.groupName}</p>
        <p className="text-xs text-muted-foreground">
          Current:{" "}
          <span className="text-destructive">
            {group.mentor.name} (inactive)
          </span>
        </p>
        {top ? (
          <p className="truncate text-xs text-primary">
            ★ Suggested: {top.name} (score {Math.round(top.score)})
          </p>
        ) : isLoading ? (
          <p className="text-xs text-muted-foreground">Scoring mentors…</p>
        ) : allSuggestions.length > 0 ? (
          // Every scored mentor was filtered out, so nothing pre-selects — say why
          // rather than silently leaving Confirm disabled.
          <p className="text-xs text-muted-foreground">
            Every suggested mentor is at capacity — turn on “Show mentors at
            capacity” to pick one.
          </p>
        ) : null}
      </div>
      <Select value={value ?? ""} onValueChange={onSelect}>
        <SelectTrigger className="h-8 w-48 shrink-0 text-xs">
          <SelectValue placeholder="Select action" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={UNASSIGN_VALUE} className="text-muted-foreground">
            — Unassign (leave unmatched)
          </SelectItem>
          {suggestions.map((s, index) => (
            <SelectItem key={s.mentorUserId} value={String(s.mentorUserId)}>
              {index === 0 ? "★ " : ""}
              {s.name} · {Math.round(s.score)}
              {s.atCapacity ? (
                <span className="ml-1 text-muted-foreground">(full)</span>
              ) : null}
            </SelectItem>
          ))}
          {extraMentors.map((m) => (
            <SelectItem key={m.mentorId} value={String(m.mentorId)}>
              {m.name}
              {m.remainingCapacity === 0 ? (
                <span className="ml-1 text-muted-foreground">(full)</span>
              ) : null}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}

export function BulkReplaceDialog({
  open,
  onOpenChange,
  inactiveGroups,
  mentors,
  onConfirm,
  isPending,
}: BulkReplaceDialogProps) {
  const navigate = useNavigate();
  const [selections, setSelections] = useState<Record<number, string>>({});

  function handleOpenChange(nextOpen: boolean) {
    if (!nextOpen) setSelections({});
    onOpenChange(nextOpen);
  }

  async function handleConfirm() {
    const assignments: Array<{ groupId: number; mentorUserId: number }> = [];
    const unassigns: number[] = [];

    for (const g of inactiveGroups) {
      const val = selections[g.groupId];
      if (!val) continue;
      if (val === UNASSIGN_VALUE) {
        unassigns.push(g.groupId);
      } else {
        assignments.push({ groupId: g.groupId, mentorUserId: Number(val) });
      }
    }

    await onConfirm(assignments, unassigns);
    setSelections({});
  }

  const actionCount = inactiveGroups.filter((g) => selections[g.groupId]).length;

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Replace Inactive Mentors</DialogTitle>
          <DialogDescription>
            {inactiveGroups.length} group{inactiveGroups.length === 1 ? "" : "s"}{" "}
            {inactiveGroups.length === 1 ? "has" : "have"} an inactive mentor. The
            best match from the matcher is pre-selected — adjust any, or choose
            "Unassign" to leave a group unmatched.
          </DialogDescription>
        </DialogHeader>

        <div className="flex justify-end border-b pb-2">
          <ShowFullMentorsToggle />
        </div>

        <div className="max-h-72 space-y-3 overflow-y-auto py-1">
          {inactiveGroups.map((g) => (
            <BulkReplaceRow
              key={g.groupId}
              group={g}
              mentors={mentors}
              open={open}
              value={selections[g.groupId]}
              onSelect={(val) =>
                setSelections((prev) => ({ ...prev, [g.groupId]: val }))
              }
            />
          ))}
        </div>

        <DialogFooter className="flex-col gap-2 sm:flex-col">
          <Button
            className="w-full"
            onClick={handleConfirm}
            disabled={isPending || actionCount === 0}
          >
            {isPending
              ? "Confirming..."
              : `Confirm${actionCount > 0 ? ` (${actionCount})` : ""}`}
          </Button>
          <Button
            variant="outline"
            className="w-full"
            disabled={isPending}
            onClick={() => {
              onOpenChange(false);
              void navigate({ to: "/groups/mentor-matching" });
            }}
          >
            Go to Mentor Matching
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
