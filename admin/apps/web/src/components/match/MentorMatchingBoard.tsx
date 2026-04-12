import { useMemo, useState } from "react";
import type { MentorGroupRecommendation } from "@/type/mentorMatch";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { cn } from "@/lib/utils";
import { toast } from "sonner";
import { CheckIcon, InfoIcon } from "lucide-react";

type MentorMatchingBoardProps = {
  recommendations: MentorGroupRecommendation[];
  unmatchedGroupCount: number;
  onRunMatch: () => void;
  onConfirmAssignments: (
    assignments: Array<{ groupId: number; mentorUserId: number }>,
  ) => void | Promise<void>;
  isRunning: boolean;
  isConfirming: boolean;
};

function ScoreBreakdownTooltip({
  rec,
}: {
  rec: MentorGroupRecommendation;
}) {
  const { scoreBreakdown: bd } = rec;
  return (
    <TooltipContent
      side="left"
      className="w-[320px] max-w-[90vw] flex flex-col gap-2 rounded-lg border bg-card p-3 text-card-foreground shadow-lg"
    >
      <div className="rounded-md border bg-muted/20 p-2">
        <p className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
          Reason
        </p>
        <p className="mt-1 text-xs leading-relaxed">
          {rec.reason || "No reason provided"}
        </p>
      </div>

      <div className="rounded-md border bg-muted/20 p-2 text-xs">
        <div className="mb-2 flex items-center justify-between border-b pb-1.5">
          <span className="font-medium text-muted-foreground">Match score</span>
          <span className="text-sm font-semibold">{rec.score.toFixed(2)}</span>
        </div>
        <div className="space-y-1.5">
          <div className="flex items-center justify-between">
            <span className="text-muted-foreground">Base</span>
            <span>{bd.baseScore.toFixed(2)}</span>
          </div>
          {bd.trackPenalty > 0 && (
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">Track mismatch</span>
              <span className="text-red-500">-{bd.trackPenalty.toFixed(2)}</span>
            </div>
          )}
          {bd.interestBonus > 0 && (
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">Interest overlap</span>
              <span className="text-green-600">+{bd.interestBonus.toFixed(2)}</span>
            </div>
          )}
          {bd.timezonePenalty > 0 && (
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">Timezone penalty</span>
              <span className="text-red-500">-{bd.timezonePenalty.toFixed(2)}</span>
            </div>
          )}
          {bd.capacityBonus > 0 && (
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">Capacity bonus</span>
              <span className="text-green-600">+{bd.capacityBonus.toFixed(2)}</span>
            </div>
          )}
          <div className="flex items-center justify-between border-t pt-1.5 font-semibold">
            <span>Total</span>
            <span>{bd.objectiveScore.toFixed(2)}</span>
          </div>
        </div>
      </div>

      {rec.recommendedMentor && (
        <div className="rounded-md border bg-muted/20 p-2 text-xs">
          <p className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground mb-1">
            Mentor interests
          </p>
          <div className="flex flex-wrap gap-1">
            {rec.recommendedMentor.interests.length > 0 ? (
              rec.recommendedMentor.interests.map((interest) => (
                <Badge key={interest} variant="secondary" className="text-[10px]">
                  {interest}
                </Badge>
              ))
            ) : (
              <span className="text-muted-foreground">None listed</span>
            )}
          </div>
          <p className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground mt-2 mb-1">
            Group student interests
          </p>
          <div className="flex flex-wrap gap-1">
            {rec.group.studentInterests.length > 0 ? (
              [...new Set(rec.group.studentInterests)].map((interest) => (
                <Badge key={interest} variant="outline" className="text-[10px]">
                  {interest}
                </Badge>
              ))
            ) : (
              <span className="text-muted-foreground">None listed</span>
            )}
          </div>
        </div>
      )}
    </TooltipContent>
  );
}

export function MentorMatchingBoard({
  recommendations,
  unmatchedGroupCount,
  onRunMatch,
  onConfirmAssignments,
  isRunning,
  isConfirming,
}: MentorMatchingBoardProps) {
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [trackFilter, setTrackFilter] = useState("all");
  const [search, setSearch] = useState("");

  const availableTracks = useMemo(() => {
    return [
      "all",
      ...new Set(recommendations.map((r) => r.group.trackCode).filter(Boolean)),
    ];
  }, [recommendations]);

  const filtered = useMemo(() => {
    const query = search.trim().toLowerCase();
    return recommendations
      .filter((r) => (trackFilter === "all" ? true : r.group.trackCode === trackFilter))
      .filter((r) => {
        if (!query) return true;
        return (
          r.group.groupName.toLowerCase().includes(query) ||
          r.recommendedMentor?.name.toLowerCase().includes(query) ||
          r.group.trackCode.toLowerCase().includes(query)
        );
      });
  }, [recommendations, trackFilter, search]);

  const selectableIds = filtered
    .filter((r) => r.recommendedMentor !== null)
    .map((r) => r.group.groupId);

  const allSelected =
    selectableIds.length > 0 &&
    selectableIds.every((id) => selectedIds.has(id));

  function toggleAll() {
    if (allSelected) {
      setSelectedIds((prev) => {
        const next = new Set(prev);
        selectableIds.forEach((id) => next.delete(id));
        return next;
      });
    } else {
      setSelectedIds((prev) => {
        const next = new Set(prev);
        selectableIds.forEach((id) => next.add(id));
        return next;
      });
    }
  }

  function toggleRow(id: number) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }

  function onClickConfirm() {
    if (selectedIds.size === 0) {
      toast.error("Select at least one assignment to confirm.");
      return;
    }
    const assignments = Array.from(selectedIds).flatMap((groupId) => {
      const rec = recommendations.find((r) => r.group.groupId === groupId);
      if (!rec?.recommendedMentor) return [];
      return [{ groupId, mentorUserId: rec.recommendedMentor.mentorId }];
    });
    void onConfirmAssignments(assignments);
    setSelectedIds(new Set());
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="rounded-xl border bg-card p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold">Mentor Assignment</h2>
            <p className="text-sm text-muted-foreground">
              Run the algorithm, review recommendations, then confirm selected assignments.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button onClick={onRunMatch} disabled={isRunning}>
              {isRunning ? "Matching..." : "Run Match"}
            </Button>
            <Button
              onClick={onClickConfirm}
              disabled={
                recommendations.length === 0 ||
                selectedIds.size === 0 ||
                isConfirming
              }
            >
              {isConfirming
                ? "Confirming..."
                : `Confirm Selected (${selectedIds.size})`}
            </Button>
          </div>
        </div>

        <div className="mt-3 grid grid-cols-2 gap-2 md:grid-cols-4">
          <div className="rounded-md border bg-muted/30 p-2 text-xs">
            <p className="text-muted-foreground">Unmatched groups</p>
            <p className="text-sm font-semibold">{unmatchedGroupCount}</p>
          </div>
          <div className="rounded-md border bg-muted/30 p-2 text-xs">
            <p className="text-muted-foreground">Recommendations</p>
            <p className="text-sm font-semibold">{recommendations.length}</p>
          </div>
          <div className="rounded-md border bg-muted/30 p-2 text-xs">
            <p className="text-muted-foreground">No mentor found</p>
            <p className="text-sm font-semibold">
              {recommendations.filter((r) => r.recommendedMentor === null).length}
            </p>
          </div>
          <div className="rounded-md border bg-muted/30 p-2 text-xs">
            <p className="text-muted-foreground">Selected</p>
            <p className="text-sm font-semibold">{selectedIds.size}</p>
          </div>
        </div>
      </div>

      {/* Empty state */}
      {recommendations.length === 0 ? (
        <div className="rounded-xl border border-dashed p-8 text-center text-sm text-muted-foreground">
          Click <span className="font-semibold">Run Match</span> to load mentor
          recommendations.
        </div>
      ) : (
        <div className="rounded-xl border bg-card">
          {/* Filters */}
          <div className="flex flex-wrap items-center gap-2 border-b p-3">
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search by group, mentor, or track"
              className="h-9 min-w-[220px] flex-1 rounded-md border px-3 text-sm"
            />
            <select
              value={trackFilter}
              onChange={(e) => setTrackFilter(e.target.value)}
              className="h-9 rounded-md border bg-background px-3 text-sm"
            >
              {availableTracks.map((track) => (
                <option key={track} value={track}>
                  {track === "all" ? "All tracks" : track}
                </option>
              ))}
            </select>
          </div>

          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-10">
                  <button
                    onClick={toggleAll}
                    className={cn(
                      "flex h-5 w-5 items-center justify-center rounded border transition",
                      allSelected
                        ? "border-primary bg-primary text-primary-foreground"
                        : "border-input bg-background",
                    )}
                    title={allSelected ? "Deselect all" : "Select all"}
                  >
                    {allSelected && <CheckIcon className="size-3" />}
                  </button>
                </TableHead>
                <TableHead>Group</TableHead>
                <TableHead>Track</TableHead>
                <TableHead>Students</TableHead>
                <TableHead>Recommended Mentor</TableHead>
                <TableHead>Institution</TableHead>
                <TableHead>Capacity left</TableHead>
                <TableHead className="text-right">Score</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filtered.length === 0 ? (
                <TableRow>
                  <TableCell
                    colSpan={8}
                    className="h-24 text-center text-muted-foreground"
                  >
                    No results match current filters.
                  </TableCell>
                </TableRow>
              ) : (
                filtered.map((rec) => {
                  const groupId = rec.group.groupId;
                  const isSelected = selectedIds.has(groupId);
                  const hasMatch = rec.recommendedMentor !== null;

                  return (
                    <TableRow
                      key={`${groupId}`}
                      className={cn(
                        isSelected && "bg-primary/5",
                        !hasMatch && "opacity-60",
                      )}
                    >
                      <TableCell>
                        {hasMatch && (
                          <button
                            onClick={() => toggleRow(groupId)}
                            className={cn(
                              "flex h-5 w-5 items-center justify-center rounded border transition",
                              isSelected
                                ? "border-primary bg-primary text-primary-foreground"
                                : "border-input bg-background",
                            )}
                          >
                            {isSelected && <CheckIcon className="size-3" />}
                          </button>
                        )}
                      </TableCell>
                      <TableCell className="font-medium">
                        {rec.group.groupName}
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline">{rec.group.trackCode}</Badge>
                      </TableCell>
                      <TableCell>{rec.group.studentCount}</TableCell>
                      <TableCell>
                        {hasMatch ? (
                          <span>{rec.recommendedMentor!.name}</span>
                        ) : (
                          <span className="text-muted-foreground">
                            No suitable mentor
                          </span>
                        )}
                      </TableCell>
                      <TableCell>
                        {rec.recommendedMentor?.institution ?? (
                          <span className="text-muted-foreground">—</span>
                        )}
                      </TableCell>
                      <TableCell>
                        {hasMatch ? (
                          rec.recommendedMentor!.remainingCapacity
                        ) : (
                          <span className="text-muted-foreground">—</span>
                        )}
                      </TableCell>
                      <TableCell className="text-right">
                        {hasMatch ? (
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <button className="inline-flex items-center gap-1 rounded px-2 py-0.5 text-sm font-semibold hover:bg-muted/50">
                                {rec.score.toFixed(0)}
                                <InfoIcon className="size-3 text-muted-foreground" />
                              </button>
                            </TooltipTrigger>
                            <ScoreBreakdownTooltip rec={rec} />
                          </Tooltip>
                        ) : (
                          <span className="text-muted-foreground">—</span>
                        )}
                      </TableCell>
                    </TableRow>
                  );
                })
              )}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}
