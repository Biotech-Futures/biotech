import { useMemo, useState, useEffect } from "react";
import type { MentorGroupRecommendation, MentorListItem, UnmatchedGroup } from "@/type/mentorMatch";
import type { MatchMode } from "@/query/mentorMatch";
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
import { AlertTriangleIcon, CheckIcon, ChevronDownIcon, ChevronRightIcon } from "lucide-react";

const MATCH_MODES: {
  value: MatchMode;
  label: string;
  description: string;
}[] = [
  {
    value: "balanced",
    label: "Balanced",
    description:
      "Considers all available mentors for every group. Same-track mentors are preferred, but cross-track mentors can fill in when needed. Best overall coverage.",
  },
  {
    value: "strict",
    label: "Strict",
    description:
      "Only matches groups with mentors from the same track (or GLOBAL mentors). Groups with no compatible mentor in their track will be left unmatched.",
  },
  {
    value: "coverage",
    label: "Coverage",
    description:
      "Two-phase matching: first assigns same-track mentors, then uses remaining mentor capacity to cover still-unmatched groups across other tracks. Maximises the number of matched groups.",
  },
];

type MentorMatchingBoardProps = {
  recommendations: MentorGroupRecommendation[];
  unmatchedGroups: UnmatchedGroup[];
  mentors: MentorListItem[];
  mode: MatchMode;
  onModeChange: (mode: MatchMode) => void;
  onRunMatch: () => void;
  onConfirmAssignments: (
    assignments: Array<{ groupId: number; mentorUserId: number }>,
  ) => void | Promise<void>;
  isRunning: boolean;
  isConfirming: boolean;
};

// ─── Expanded detail panel ───────────────────────────────────────────────────

function ExpandedDetail({ rec }: { rec: MentorGroupRecommendation }) {
  const { group, recommendedMentor, reason, scoreBreakdown: bd } = rec;

  return (
    <div className="grid gap-3 px-4 py-3 md:grid-cols-3 bg-muted/20 border-t">
      {/* Group & students */}
      <div className="min-w-0 space-y-2">
        <p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
          Group
        </p>
        <div className="text-xs space-y-1">
          <p className="font-medium">{group.groupName}</p>
          <p className="text-muted-foreground">
            Track: <span className="text-foreground">{group.trackCode}</span>
          </p>
          <p className="text-muted-foreground">
            Students: <span className="text-foreground">{group.studentCount}</span>
          </p>
        </div>

        {group.students && group.students.length > 0 ? (
          <div className="space-y-1.5 pt-1">
            <p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
              Students
            </p>
            {group.students.map((s) => (
              <div key={s.name} className="rounded border bg-background px-2 py-1">
                <p className="text-xs font-medium">{s.name}</p>
                {s.interests.length > 0 && (
                  <div className="mt-0.5 flex flex-wrap gap-1">
                    {s.interests.map((i) => (
                      <Badge key={i} variant="outline" className="text-[10px] px-1 py-0">
                        {i}
                      </Badge>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        ) : (
          <div className="pt-1 space-y-1">
            <p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
              Student Interests
            </p>
            <div className="flex flex-wrap gap-1">
              {[...new Set(group.studentInterests)].map((i) => (
                <Badge key={i} variant="outline" className="text-[10px]">
                  {i}
                </Badge>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Score breakdown */}
      <div className="min-w-0 space-y-2">
        <p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
          Score Breakdown
        </p>
        <div className="rounded border bg-background p-2 text-xs space-y-1.5">
          <div className="flex items-center justify-between border-b pb-1.5 font-medium">
            <span className="text-muted-foreground">Match score</span>
            <span className="text-sm font-semibold">{rec.score.toFixed(0)}</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-muted-foreground">Base</span>
            <span>{bd.baseScore}</span>
          </div>
          {bd.trackPenalty > 0 && (
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">Track mismatch</span>
              <span className="text-red-500">−{bd.trackPenalty}</span>
            </div>
          )}
          {bd.interestBonus > 0 && (
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">Interest overlap</span>
              <span className="text-green-600">+{bd.interestBonus}</span>
            </div>
          )}
          {bd.timezonePenalty > 0 && (
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">Timezone penalty</span>
              <span className="text-red-500">−{bd.timezonePenalty}</span>
            </div>
          )}
          {bd.capacityBonus > 0 && (
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">Capacity bonus</span>
              <span className="text-green-600">+{bd.capacityBonus}</span>
            </div>
          )}
          <div className="flex items-center justify-between border-t pt-1.5 font-semibold">
            <span>Total</span>
            <span>{bd.objectiveScore}</span>
          </div>
        </div>

        <div className="rounded border bg-background p-2 text-xs">
          <p className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground mb-1">
            Reason
          </p>
          <div className="space-y-1">
            {(reason || "No reason provided.").split(". ").filter(Boolean).map((sentence, i) => (
              <p key={i} className="leading-relaxed text-foreground break-words">
                {sentence.endsWith(".") ? sentence : `${sentence}.`}
              </p>
            ))}
          </div>
        </div>
      </div>

      {/* Mentor details */}
      <div className="min-w-0 space-y-2">
        <p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
          Mentor
        </p>
        {recommendedMentor ? (
          <div className="rounded border bg-background p-2 text-xs space-y-1.5">
            <p className="font-medium">{recommendedMentor.name}</p>
            {recommendedMentor.institution && (
              <p className="text-muted-foreground">{recommendedMentor.institution}</p>
            )}
            <p className="text-muted-foreground">
              Track: <span className="text-foreground">{recommendedMentor.trackCode}</span>
            </p>
            <p className="text-muted-foreground">
              Remaining capacity:{" "}
              <span className="text-foreground">{recommendedMentor.remainingCapacity}</span>
            </p>
            <div className="pt-1 space-y-1">
              <p className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
                Mentor Interests
              </p>
              <div className="flex flex-wrap gap-1">
                {recommendedMentor.interests.length > 0 ? (
                  recommendedMentor.interests.map((i) => (
                    <Badge key={i} variant="secondary" className="text-[10px]">
                      {i}
                    </Badge>
                  ))
                ) : (
                  <span className="text-muted-foreground">None listed</span>
                )}
              </div>
            </div>
          </div>
        ) : (
          <div className="rounded border border-dashed bg-background p-3 text-xs text-muted-foreground">
            No mentor was found for this group under the current mode.
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Main board ───────────────────────────────────────────────────────────────

export function MentorMatchingBoard({
  recommendations,
  unmatchedGroups,
  mentors,
  mode,
  onModeChange,
  onRunMatch,
  onConfirmAssignments,
  isRunning,
  isConfirming,
}: MentorMatchingBoardProps) {
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [expandedIds, setExpandedIds] = useState<Set<number>>(new Set());
  const [expandedPreMatchIds, setExpandedPreMatchIds] = useState<Set<number>>(new Set());
  const [expandedMentorIds, setExpandedMentorIds] = useState<Set<number>>(new Set());
  const [trackFilter, setTrackFilter] = useState("all");
  const [search, setSearch] = useState("");
  const [overrides, setOverrides] = useState<Map<number, number>>(new Map());
  const [editingGroupId, setEditingGroupId] = useState<number | null>(null);

  // Reset overrides when a new match is run
  useEffect(() => {
    setOverrides(new Map());
    setEditingGroupId(null);
  }, [recommendations]);

  const capacityShortage = useMemo(() => {
    const totalCapacity = mentors.reduce((sum, m) => sum + m.remainingCapacity, 0);
    const shortage = unmatchedGroups.length - totalCapacity;
    return shortage > 0 ? { totalCapacity, shortage } : null;
  }, [mentors, unmatchedGroups]);

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
    .filter((r) => r.recommendedMentor !== null || overrides.has(r.group.groupId))
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
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function toggleExpand(id: number) {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function togglePreMatchExpand(id: number) {
    setExpandedPreMatchIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function toggleMentorExpand(id: number) {
    setExpandedMentorIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function onClickConfirm() {
    if (selectedIds.size === 0) {
      toast.error("Select at least one assignment to confirm.");
      return;
    }
    const assignments = Array.from(selectedIds).flatMap((groupId) => {
      const rec = recommendations.find((r) => r.group.groupId === groupId);
      if (!rec) return [];
      const mentorUserId = overrides.get(groupId) ?? rec.recommendedMentor?.mentorId;
      if (!mentorUserId) return [];
      return [{ groupId, mentorUserId }];
    });
    try {
      await onConfirmAssignments(assignments);
      setSelectedIds(new Set());
    } catch {
      // error is already handled and toasted in onConfirmAssignments
    }
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className=" bg-card p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold">Mentor Assignment</h2>
            <p className="text-sm text-muted-foreground">
              Run the algorithm, review recommendations, then confirm selected assignments.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {/* Mode selector */}
            <div className="flex rounded-md border overflow-hidden">
              {MATCH_MODES.map((m) => (
                <Tooltip key={m.value}>
                  <TooltipTrigger asChild>
                    <button
                      onClick={() => onModeChange(m.value)}
                      className={cn(
                        "px-3 py-1.5 text-sm font-medium transition-colors border-r last:border-r-0",
                        mode === m.value
                          ? "bg-primary text-primary-foreground"
                          : "bg-background text-muted-foreground hover:bg-muted",
                      )}
                    >
                      {m.label}
                    </button>
                  </TooltipTrigger>
                  <TooltipContent side="bottom" className="max-w-[260px] text-xs">
                    {m.description}
                  </TooltipContent>
                </Tooltip>
              ))}
            </div>
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
            <p className="text-sm font-semibold">{unmatchedGroups.length}</p>
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

      {/* Capacity shortage warning */}
      {capacityShortage && (
        <div className="flex items-start gap-3 rounded-xl border border-yellow-300 bg-yellow-50 p-4 text-sm dark:border-yellow-700 dark:bg-yellow-950">
          <AlertTriangleIcon className="mt-0.5 size-4 shrink-0 text-yellow-600 dark:text-yellow-400" />
          <div className="space-y-1">
            <p className="font-medium text-yellow-800 dark:text-yellow-300">
              Insufficient mentor capacity
            </p>
            <p className="text-yellow-700 dark:text-yellow-400">
              Total mentor capacity ({capacityShortage.totalCapacity} slot{capacityShortage.totalCapacity === 1 ? "" : "s"}) is less than the number of unmatched groups ({unmatchedGroups.length}).{" "}
              At least {capacityShortage.shortage} group{capacityShortage.shortage === 1 ? "" : "s"} will not be assigned a mentor.
            </p>
            <p className="text-yellow-700 dark:text-yellow-400">
              Consider using <strong>Balanced</strong> mode to prioritise match quality for the groups that can be assigned, and manually assign the remaining groups afterwards.
            </p>
          </div>
        </div>
      )}

      {/* Pre-match panels */}
      {recommendations.length === 0 && (
        <div className="grid gap-4 md:grid-cols-2">
          {/* Unmatched groups */}
          <div className="rounded-xl border bg-card">
            <div className="border-b px-4 py-3">
              <p className="text-sm font-semibold">
                Unmatched Groups
                <span className="ml-2 rounded-full bg-muted px-2 py-0.5 text-xs font-normal text-muted-foreground">
                  {unmatchedGroups.length}
                </span>
              </p>
            </div>
            <div className="divide-y max-h-96 overflow-y-auto">
              {unmatchedGroups.length === 0 ? (
                <p className="px-4 py-6 text-center text-xs text-muted-foreground">
                  All groups have a mentor assigned.
                </p>
              ) : (
                unmatchedGroups.map((g) => {
                  const isExpanded = expandedPreMatchIds.has(g.groupId);
                  return (
                    <div key={g.groupId} className="border-b last:border-b-0">
                      <button
                        className="w-full flex items-center justify-between px-4 py-2.5 hover:bg-muted/40 transition-colors text-left"
                        onClick={() => togglePreMatchExpand(g.groupId)}
                      >
                        <div className="flex items-center gap-2 min-w-0">
                          {isExpanded ? (
                            <ChevronDownIcon className="size-3.5 text-muted-foreground flex-shrink-0" />
                          ) : (
                            <ChevronRightIcon className="size-3.5 text-muted-foreground flex-shrink-0" />
                          )}
                          <span className="text-sm truncate">{g.groupName}</span>
                        </div>
                        <Badge variant="outline" className="text-xs flex-shrink-0 ml-2">{g.trackCode}</Badge>
                      </button>
                      {isExpanded && (
                        <div className="px-4 pb-3 pt-1 bg-muted/10 space-y-2">
                          <p className="text-xs text-muted-foreground">
                            Students: <span className="text-foreground">{g.studentCount}</span>
                          </p>
                          {g.students && g.students.length > 0 ? (
                            <div className="space-y-1.5">
                              {g.students.map((s) => (
                                <div key={s.name} className="rounded border bg-background px-2 py-1">
                                  <p className="text-xs font-medium">{s.name}</p>
                                  {s.interests.length > 0 && (
                                    <div className="mt-0.5 flex flex-wrap gap-1">
                                      {s.interests.map((i) => (
                                        <Badge key={i} variant="outline" className="text-[10px] px-1 py-0">
                                          {i}
                                        </Badge>
                                      ))}
                                    </div>
                                  )}
                                </div>
                              ))}
                            </div>
                          ) : (
                            <div className="space-y-1">
                              <p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                                Student Interests
                              </p>
                              <div className="flex flex-wrap gap-1">
                                {[...new Set(g.studentInterests)].map((i) => (
                                  <Badge key={i} variant="outline" className="text-[10px]">
                                    {i}
                                  </Badge>
                                ))}
                              </div>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })
              )}
            </div>
          </div>

          {/* Mentor list */}
          <div className="rounded-xl border bg-card">
            <div className="border-b px-4 py-3 flex items-center justify-between">
              <p className="text-sm font-semibold">
                Mentors
                <span className="ml-2 rounded-full bg-muted px-2 py-0.5 text-xs font-normal text-muted-foreground">
                  {mentors.length}
                </span>
              </p>
              <div className="flex gap-2 text-xs text-muted-foreground">
                <span className="flex items-center gap-1">
                  <span className="inline-block size-2 rounded-full bg-green-500" />
                  Available
                </span>
                <span className="flex items-center gap-1">
                  <span className="inline-block size-2 rounded-full bg-muted-foreground/40" />
                  At capacity
                </span>
              </div>
            </div>
            <div className="divide-y max-h-96 overflow-y-auto">
              {mentors.length === 0 ? (
                <p className="px-4 py-6 text-center text-xs text-muted-foreground">
                  No mentors found.
                </p>
              ) : (
                mentors.map((m) => {
                  const hasCapacity = m.remainingCapacity > 0;
                  const isExpanded = expandedMentorIds.has(m.mentorId);
                  return (
                    <div key={m.mentorId} className={cn("border-b last:border-b-0", !hasCapacity && "opacity-50")}>
                      <button
                        className="w-full flex items-center justify-between px-4 py-2.5 hover:bg-muted/40 transition-colors text-left"
                        onClick={() => toggleMentorExpand(m.mentorId)}
                      >
                        <div className="flex items-center gap-2 min-w-0">
                          <span className={cn("inline-block size-2 rounded-full flex-shrink-0", hasCapacity ? "bg-green-500" : "bg-muted-foreground/40")} />
                          {isExpanded ? (
                            <ChevronDownIcon className="size-3.5 text-muted-foreground flex-shrink-0" />
                          ) : (
                            <ChevronRightIcon className="size-3.5 text-muted-foreground flex-shrink-0" />
                          )}
                          <div className="min-w-0">
                            <p className="text-sm truncate">{m.name}</p>
                            {m.institution && (
                              <p className="text-xs text-muted-foreground truncate">{m.institution}</p>
                            )}
                          </div>
                        </div>
                        <div className="flex items-center gap-2 flex-shrink-0 ml-2">
                          <Badge variant="outline" className="text-xs">{m.trackCode}</Badge>
                          <span className="text-xs text-muted-foreground">{m.currentAssignedCount}/{m.maxGroupCount}</span>
                        </div>
                      </button>
                      {isExpanded && (
                        <div className="px-4 pb-3 pt-1 bg-muted/10 space-y-2">
                          <p className="text-xs text-muted-foreground">
                            Remaining capacity:{" "}
                            <span className="text-foreground font-medium">{m.remainingCapacity}</span>
                          </p>
                          {m.interests.length > 0 ? (
                            <div className="space-y-1">
                              <p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                                Interests
                              </p>
                              <div className="flex flex-wrap gap-1">
                                {m.interests.map((i) => (
                                  <Badge key={i} variant="secondary" className="text-[10px]">
                                    {i}
                                  </Badge>
                                ))}
                              </div>
                            </div>
                          ) : (
                            <p className="text-xs text-muted-foreground">No interests listed.</p>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })
              )}
            </div>
          </div>
        </div>
      )}

      {recommendations.length === 0 ? (
        <div className="rounded-xl border border-dashed p-6 text-center text-sm text-muted-foreground">
          Click <span className="font-semibold">Run Match</span> to generate recommendations.
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
                <TableHead className="w-8" />
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
                    colSpan={9}
                    className="h-24 text-center text-muted-foreground"
                  >
                    No results match current filters.
                  </TableCell>
                </TableRow>
              ) : (
                filtered.flatMap((rec) => {
                  const groupId = rec.group.groupId;
                  const isSelected = selectedIds.has(groupId);
                  const isExpanded = expandedIds.has(groupId);
                  const hasMatch = rec.recommendedMentor !== null;
                  const overrideMentorId = overrides.get(groupId);
                  const overrideMentor = overrideMentorId !== undefined
                    ? mentors.find((m) => m.mentorId === overrideMentorId)
                    : undefined;
                  const isEditing = editingGroupId === groupId;
                  const isSelectable = hasMatch || overrideMentorId !== undefined;

                  return [
                    <TableRow
                      key={`row-${groupId}`}
                      className={cn(
                        "cursor-pointer",
                        isSelected && "bg-primary/5",
                        !isSelectable && "opacity-60",
                      )}
                      onClick={() => toggleExpand(groupId)}
                    >
                      {/* Expand toggle */}
                      <TableCell
                        className="text-muted-foreground"
                        onClick={(e) => {
                          e.stopPropagation();
                          toggleExpand(groupId);
                        }}
                      >
                        {isExpanded ? (
                          <ChevronDownIcon className="size-4" />
                        ) : (
                          <ChevronRightIcon className="size-4" />
                        )}
                      </TableCell>

                      {/* Checkbox */}
                      <TableCell onClick={(e) => e.stopPropagation()}>
                        {isSelectable && (
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

                      {/* Recommended Mentor cell — with manual override */}
                      <TableCell onClick={(e) => e.stopPropagation()}>
                        {isEditing ? (
                          <div className="flex items-center gap-2">
                            <select
                              autoFocus
                              className="h-7 rounded border bg-background px-2 text-xs"
                              defaultValue={overrideMentorId ?? rec.recommendedMentor?.mentorId ?? ""}
                              onChange={(e) => {
                                const val = Number(e.target.value);
                                setOverrides((prev) => {
                                  const next = new Map(prev);
                                  if (val) next.set(groupId, val);
                                  else next.delete(groupId);
                                  return next;
                                });
                                setEditingGroupId(null);
                              }}
                            >
                              <option value="">— Select mentor —</option>
                              {mentors.map((m) => (
                                <option key={m.mentorId} value={m.mentorId}>
                                  {m.name} ({m.trackCode}, {m.remainingCapacity} left)
                                </option>
                              ))}
                            </select>
                            <button
                              className="text-xs text-muted-foreground hover:text-foreground"
                              onClick={() => setEditingGroupId(null)}
                            >
                              Cancel
                            </button>
                          </div>
                        ) : (
                          <div className="flex items-center gap-2">
                            <span className={cn(!isSelectable && "text-muted-foreground")}>
                              {overrideMentor
                                ? overrideMentor.name
                                : hasMatch
                                  ? rec.recommendedMentor!.name
                                  : "No suitable mentor"}
                            </span>
                            {overrideMentorId !== undefined && (
                              <Badge variant="secondary" className="text-[10px] px-1 py-0">
                                Manual
                              </Badge>
                            )}
                            <button
                              className="text-xs text-muted-foreground hover:text-foreground underline"
                              onClick={() => setEditingGroupId(groupId)}
                            >
                              {isSelectable ? "Change" : "Assign"}
                            </button>
                            {overrideMentorId !== undefined && (
                              <button
                                className="text-xs text-muted-foreground hover:text-foreground"
                                onClick={() => {
                                  setOverrides((prev) => {
                                    const next = new Map(prev);
                                    next.delete(groupId);
                                    return next;
                                  });
                                }}
                              >
                                ✕
                              </button>
                            )}
                          </div>
                        )}
                      </TableCell>

                      <TableCell>
                        {(overrideMentor ?? rec.recommendedMentor)?.institution ?? (
                          <span className="text-muted-foreground">—</span>
                        )}
                      </TableCell>
                      <TableCell>
                        {isSelectable ? (
                          (overrideMentor ?? rec.recommendedMentor)?.remainingCapacity ?? "—"
                        ) : (
                          <span className="text-muted-foreground">—</span>
                        )}
                      </TableCell>
                      <TableCell className="text-right font-semibold">
                        {overrideMentorId !== undefined ? (
                          <span className="text-muted-foreground text-xs">manual</span>
                        ) : hasMatch ? rec.score.toFixed(0) : (
                          <span className="text-muted-foreground">—</span>
                        )}
                      </TableCell>
                    </TableRow>,

                    isExpanded && (
                      <TableRow key={`detail-${groupId}`} className="hover:bg-transparent">
                        <TableCell colSpan={9} className="p-0">
                          <ExpandedDetail rec={rec} />
                        </TableCell>
                      </TableRow>
                    ),
                  ].filter(Boolean);
                })
              )}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}
