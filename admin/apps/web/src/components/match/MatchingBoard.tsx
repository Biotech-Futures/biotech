import { useEffect, useMemo, useState } from "react";
import {
  DndContext,
  DragOverlay,
  KeyboardSensor,
  PointerSensor,
  pointerWithin,
  rectIntersection,
  useDroppable,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import {
  SortableContext,
  arrayMove,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import type { MatchRecommendation, NotFullGroup } from "@/schema/match";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import { toast } from "sonner";

type MatchingBoardProps = {
  recommendations: MatchRecommendation[];
  notFullGroups: NotFullGroup[];
  onRunMatch: () => void;
  onConfirmAssignments: (
    assignments: Array<{ studentId: number; groupId: number | string }>,
  ) => void | Promise<void>;
  isRunning: boolean;
  isConfirming: boolean;
};

type MovableStudent = {
  id: string;
  name: string;
  track: string;
  yearLevel: string;
  country: string;
  score: number;
  reason: string;
  recommendedGroupId: string | null;
  scoreBreakdown: {
    baseScore: number;
    yearPenalty: number;
    countryPenalty: number;
    timezonePenalty: number;
    sizeBonus: number;
    totalPenalty: number;
    objectiveScore: number;
  };
};

type GroupMember = {
  id: string;
  name: string;
  yearLevel: string;
  country: string;
};

type MatchingGroup = {
  id: string;
  name: string;
  track: string;
  tutor: string;
  maxSize: number;
  existingStudents: GroupMember[];
};

type BoardData = {
  studentsById: Record<string, MovableStudent>;
  groupsByContainerId: Record<string, MatchingGroup>;
  containers: Record<string, string[]>;
};

type GroupFilter = "all" | "needs_action" | "has_space" | "full";

const WAITING_CONTAINER_ID = "waiting";
const DEFAULT_GROUP_MAX_SIZE = 5;

function toStringId(id: string | number | undefined): string {
  if (id === undefined) {
    return "";
  }
  return String(id);
}

function buildDisplayName(
  recommendationStudent: MatchRecommendation["student"],
): string {
  if (recommendationStudent.name?.trim()) {
    return recommendationStudent.name.trim();
  }

  return `Student #${toStringId(recommendationStudent.id)}`;
}

function formatYearLevel(yearLevel?: number): string {
  if (yearLevel === undefined || yearLevel === null) {
    return "N/A";
  }
  return String(yearLevel);
}

function toContainerId(groupId: string): string {
  return `group-${groupId}`;
}

function toMatchingGroup(
  group: MatchRecommendation["recommendGroup"] | NotFullGroup,
): MatchingGroup | null {
  if (!group) {
    return null;
  }

  return {
    id: toStringId(group.id),
    name: group.groupName,
    track: toStringId(group.trackId),
    tutor: group.tutor?.name || "Unassigned",
    maxSize: group.maxSize ?? DEFAULT_GROUP_MAX_SIZE,
    existingStudents: group.groupStudent.map((groupStudent) => ({
      id: toStringId(groupStudent.id),
      name:
        groupStudent.name?.trim() ||
        `Student #${toStringId(groupStudent.id)}`,
      yearLevel: formatYearLevel(
        groupStudent.yearLevel ?? groupStudent.yearlevel,
      ),
      country: groupStudent.country ?? "N/A",
    })),
  };
}

function buildBoardData(
  recommendations: MatchRecommendation[],
  notFullGroups: NotFullGroup[],
): BoardData {
  const studentsById: Record<string, MovableStudent> = {};
  const groupsByContainerId: Record<string, MatchingGroup> = {};
  const containers: Record<string, string[]> = {
    [WAITING_CONTAINER_ID]: [],
  };

  for (const group of notFullGroups) {
    const containerId = toContainerId(toStringId(group.id));
    const matchingGroup = toMatchingGroup(group);

    if (matchingGroup) {
      groupsByContainerId[containerId] = matchingGroup;
      containers[containerId] = [];
    }
  }

  for (const recommendation of recommendations) {
    const studentId = toStringId(recommendation.student.id);
    const recommendGroupId = recommendation.recommendGroup
      ? toStringId(recommendation.recommendGroup.id)
      : null;

    studentsById[studentId] = {
      id: studentId,
      name: buildDisplayName(recommendation.student),
      track: toStringId(recommendation.student.trackId),
      yearLevel: formatYearLevel(
        recommendation.student.yearLevel ?? recommendation.student.yearlevel,
      ),
      country: recommendation.student.country ?? "N/A",
      score: recommendation.score,
      reason: recommendation.reason,
      recommendedGroupId: recommendGroupId,
      scoreBreakdown: recommendation.scoreBreakdown,
    };

    if (recommendation.recommendGroup) {
      const group = recommendation.recommendGroup;
      const containerId = toContainerId(toStringId(group.id));

      if (!groupsByContainerId[containerId]) {
        const matchingGroup = toMatchingGroup(group);
        if (matchingGroup) {
          groupsByContainerId[containerId] = matchingGroup;
        }
      }

      if (!containers[containerId]) {
        containers[containerId] = [];
      }

      containers[containerId].push(studentId);
    } else {
      containers[WAITING_CONTAINER_ID].push(studentId);
    }
  }

  return {
    studentsById,
    groupsByContainerId,
    containers,
  };
}

function findContainerId(
  studentId: string,
  containers: Record<string, string[]>,
): string | null {
  for (const [containerId, studentIds] of Object.entries(containers)) {
    if (studentIds.includes(studentId)) {
      return containerId;
    }
  }

  return null;
}

function resolveDropContainer(
  overId: string,
  containers: Record<string, string[]>,
): string | null {
  if (containers[overId]) {
    return overId;
  }

  return findContainerId(overId, containers);
}

function StudentCard({
  student,
  isRecommendedInCurrentGroup,
  isDragging,
}: {
  student: MovableStudent;
  isRecommendedInCurrentGroup: boolean;
  isDragging?: boolean;
}) {
  return (
    <div
      className={cn(
        "rounded-lg border bg-card p-2 text-card-foreground shadow-sm transition",
        isRecommendedInCurrentGroup &&
          "border-emerald-400 bg-emerald-50 text-emerald-950",
        isDragging && "opacity-40",
      )}
    >
      <div className="flex items-center justify-between gap-2">
        <p className="truncate text-xs font-semibold">{student.name}</p>
        <Tooltip>
          <TooltipTrigger asChild>
            <Badge
              variant={isRecommendedInCurrentGroup ? "default" : "outline"}
            >
              {student.score.toFixed(0)}
            </Badge>
          </TooltipTrigger>
          <TooltipContent
            side="top"
            className="w-[340px] max-w-[90vw] !flex !flex-col !items-stretch gap-2 rounded-lg border bg-card p-3 text-card-foreground shadow-lg"
          >
            <div className="rounded-md border bg-muted/20 p-2">
              <p className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
                Reason
              </p>
              <p className="mt-1 text-xs leading-relaxed">
                {student.reason || "No reason provided"}
              </p>
            </div>

            <div className="rounded-md border bg-muted/20 p-2 text-xs">
              <div className="mb-2 flex items-center justify-between border-b pb-1.5">
                <span className="font-medium text-muted-foreground">
                  Match score
                </span>
                <span className="text-sm font-semibold">
                  {student.score.toFixed(2)}
                </span>
              </div>
              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Base</span>
                  <span>{student.scoreBreakdown.baseScore.toFixed(2)}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Year penalty</span>
                  <span className="text-red-500">
                    -{student.scoreBreakdown.yearPenalty.toFixed(2)}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Country penalty</span>
                  <span className="text-red-500">
                    -{student.scoreBreakdown.countryPenalty.toFixed(2)}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Timezone penalty</span>
                  <span className="text-red-500">
                    -{student.scoreBreakdown.timezonePenalty.toFixed(2)}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Size bonus</span>
                  <span className="text-green-600">
                    +{student.scoreBreakdown.sizeBonus.toFixed(2)}
                  </span>
                </div>
                <div className="flex items-center justify-between border-t pt-1.5 font-semibold">
                  <span>Total</span>
                  <span>{student.scoreBreakdown.objectiveScore.toFixed(2)}</span>
                </div>
              </div>
            </div>
          </TooltipContent>
        </Tooltip>
      </div>
      <p className="mt-1 text-[11px] text-muted-foreground">
        Y{student.yearLevel} | {student.country}
      </p>
    </div>
  );
}

function ExistingStudentCard({ student }: { student: GroupMember }) {
  return (
    <div className="rounded-lg border bg-card/70 p-2 text-card-foreground">
      <p className="truncate text-xs font-semibold">{student.name}</p>
      <p className="mt-1 text-[11px] text-muted-foreground">
        Y{student.yearLevel} | {student.country}
      </p>
    </div>
  );
}

function SortableStudentCard({
  student,
  isRecommendedInCurrentGroup,
}: {
  student: MovableStudent;
  isRecommendedInCurrentGroup: boolean;
}) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: student.id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  };

  return (
    <div ref={setNodeRef} style={style} {...attributes} {...listeners}>
      <StudentCard
        student={student}
        isRecommendedInCurrentGroup={isRecommendedInCurrentGroup}
        isDragging={isDragging}
      />
    </div>
  );
}

function DroppableStudentList({
  containerId,
  studentIds,
  studentsById,
  recommendedGroupId,
  emptyText,
  horizontal = false,
}: {
  containerId: string;
  studentIds: string[];
  studentsById: Record<string, MovableStudent>;
  recommendedGroupId: string | null;
  emptyText: string;
  horizontal?: boolean;
}) {
  const { setNodeRef, isOver } = useDroppable({ id: containerId });

  return (
    <div
      ref={setNodeRef}
      className={cn(
        "rounded-lg border border-dashed p-2",
        horizontal ? "overflow-x-auto" : "space-y-2",
        isOver && "border-primary bg-primary/5",
      )}
    >
      <SortableContext
        items={studentIds}
        strategy={verticalListSortingStrategy}
      >
        {studentIds.length > 0 ? (
          <div
            className={cn(horizontal ? "flex min-w-max gap-2" : "space-y-2")}
          >
            {studentIds.map((studentId) => {
              const student = studentsById[studentId];
              if (!student) {
                return null;
              }

              return (
                <div
                  key={studentId}
                  className={cn(horizontal && "w-[220px] shrink-0")}
                >
                  <SortableStudentCard
                    student={student}
                    isRecommendedInCurrentGroup={
                      recommendedGroupId !== null &&
                      student.recommendedGroupId === recommendedGroupId
                    }
                  />
                </div>
              );
            })}
          </div>
        ) : (
          <div className="py-4 text-center text-xs text-muted-foreground">
            {emptyText}
          </div>
        )}
      </SortableContext>
    </div>
  );
}

export function MatchingBoard({
  recommendations,
  notFullGroups,
  onRunMatch,
  onConfirmAssignments,
  isRunning,
  isConfirming,
}: MatchingBoardProps) {
  const boardData = useMemo(
    () => buildBoardData(recommendations, notFullGroups),
    [notFullGroups, recommendations],
  );
  const [containers, setContainers] = useState<Record<string, string[]>>({});
  const [activeStudentId, setActiveStudentId] = useState<string | null>(null);
  const [dragError, setDragError] = useState<string | null>(null);
  const [groupSearch, setGroupSearch] = useState("");
  const [trackFilter, setTrackFilter] = useState("all");
  const [groupFilter, setGroupFilter] = useState<GroupFilter>("all");

  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    }),
  );

  const effectiveContainers =
    Object.keys(containers).length > 0 ? containers : boardData.containers;

  const activeStudent = activeStudentId
    ? boardData.studentsById[activeStudentId]
    : null;

  const groupSummaries = useMemo(() => {
    return Object.entries(boardData.groupsByContainerId).map(
      ([containerId, group]) => {
        const movedStudents = effectiveContainers[containerId] ?? [];
        const existingCount = group.existingStudents.length;
        const recommendedCount = movedStudents.length;
        const totalCount = existingCount + recommendedCount;
        const remainingCapacity = Math.max(0, group.maxSize - totalCount);

        return {
          containerId,
          group,
          movedStudents,
          existingCount,
          recommendedCount,
          totalCount,
          remainingCapacity,
        };
      },
    );
  }, [boardData.groupsByContainerId, effectiveContainers]);

  const availableTracks = useMemo(() => {
    return [
      "all",
      ...new Set(
        groupSummaries.map((item) => item.group.track).filter(Boolean),
      ),
    ];
  }, [groupSummaries]);

  const filteredGroupSummaries = useMemo(() => {
    const query = groupSearch.trim().toLowerCase();

    return groupSummaries
      .filter((item) =>
        trackFilter === "all" ? true : item.group.track === trackFilter,
      )
      .filter((item) => {
        if (groupFilter === "needs_action") {
          return item.recommendedCount > 0;
        }
        if (groupFilter === "has_space") {
          return item.remainingCapacity > 0;
        }
        if (groupFilter === "full") {
          return item.remainingCapacity === 0;
        }
        return true;
      })
      .filter((item) => {
        if (!query) {
          return true;
        }

        return (
          item.group.name.toLowerCase().includes(query) ||
          item.group.tutor.toLowerCase().includes(query) ||
          item.group.track.toLowerCase().includes(query)
        );
      })
      .sort((a, b) => a.group.name.localeCompare(b.group.name));
  }, [groupFilter, groupSearch, groupSummaries, trackFilter]);

  useEffect(() => {
    setContainers(boardData.containers);
    setDragError(null);
  }, [boardData.containers]);

  function resetBoardFromRecommendations() {
    setContainers(boardData.containers);
    setDragError(null);
  }

  function onDragEnd(event: DragEndEvent) {
    const activeId = toStringId(event.active.id as string | number);
    const overId = event.over
      ? toStringId(event.over.id as string | number)
      : null;

    setActiveStudentId(null);

    if (!overId) {
      return;
    }

    setContainers((previous) => {
      const currentContainers =
        Object.keys(previous).length > 0 ? previous : boardData.containers;

      const sourceContainerId = findContainerId(activeId, currentContainers);
      const targetContainerId = resolveDropContainer(overId, currentContainers);

      if (!sourceContainerId || !targetContainerId) {
        return currentContainers;
      }

      if (sourceContainerId === targetContainerId) {
        const sourceItems = currentContainers[sourceContainerId];
        const activeIndex = sourceItems.indexOf(activeId);
        const overIndex = sourceItems.indexOf(overId);

        if (activeIndex < 0 || overIndex < 0 || activeIndex === overIndex) {
          return currentContainers;
        }

        return {
          ...currentContainers,
          [sourceContainerId]: arrayMove(sourceItems, activeIndex, overIndex),
        };
      }

      if (targetContainerId !== WAITING_CONTAINER_ID) {
        const targetGroup = boardData.groupsByContainerId[targetContainerId];
        if (targetGroup) {
          const existingCount = targetGroup.existingStudents.length;
          const currentMovedCount = currentContainers[targetContainerId].length;
          if (existingCount + currentMovedCount >= targetGroup.maxSize) {
            setDragError(
              `${targetGroup.name} is full (${targetGroup.maxSize}/${targetGroup.maxSize}).`,
            );
            return currentContainers;
          }
        }
      }

      setDragError(null);

      const sourceItems = [...currentContainers[sourceContainerId]];
      const sourceIndex = sourceItems.indexOf(activeId);
      if (sourceIndex === -1) {
        return currentContainers;
      }
      sourceItems.splice(sourceIndex, 1);

      const targetItems = [...currentContainers[targetContainerId]];
      const targetIndex = currentContainers[targetContainerId].includes(overId)
        ? currentContainers[targetContainerId].indexOf(overId)
        : targetItems.length;
      targetItems.splice(targetIndex, 0, activeId);

      return {
        ...currentContainers,
        [sourceContainerId]: sourceItems,
        [targetContainerId]: targetItems,
      };
    });
  }

  const totalRemainingSeats = groupSummaries.reduce(
    (sum, item) => sum + item.remainingCapacity,
    0,
  );
  const assignedStudentCount =
    recommendations.length -
    (effectiveContainers[WAITING_CONTAINER_ID]?.length ?? 0);
  const waitingStudentCount = effectiveContainers[WAITING_CONTAINER_ID]?.length ?? 0;

  function buildAssignmentsPayload() {
    const payload: Array<{ studentId: number; groupId: number | string }> = [];

    for (const [containerId, studentIds] of Object.entries(effectiveContainers)) {
      if (containerId === WAITING_CONTAINER_ID) {
        continue;
      }

      const group = boardData.groupsByContainerId[containerId];
      if (!group) {
        continue;
      }

      const numericGroupId = Number(group.id);
      const groupId = Number.isFinite(numericGroupId) ? numericGroupId : group.id;

      for (const studentId of studentIds) {
        const parsedStudentId = Number(studentId);
        if (!Number.isFinite(parsedStudentId)) {
          continue;
        }

        payload.push({
          studentId: parsedStudentId,
          groupId,
        });
      }
    }

    return payload;
  }

  function onClickConfirmAssignments() {
    if (waitingStudentCount > 0) {
      toast.error(
        `Please assign all students first. ${waitingStudentCount} still in Waiting Area.`,
      );
      return;
    }

    const assignments = buildAssignmentsPayload();
    if (assignments.length === 0) {
      return;
    }

    void onConfirmAssignments(assignments);
  }

  return (
    <div className="space-y-4">
      <div className="rounded-xl border bg-card p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold">Group Assignment</h2>
            <p className="text-sm text-muted-foreground">
              Drag students to assign them to groups.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button onClick={onRunMatch} disabled={isRunning}>
              {isRunning ? "Matching..." : "Run Match"}
            </Button>
            <Button
              onClick={onClickConfirmAssignments}
              disabled={
                recommendations.length === 0 ||
                assignedStudentCount === 0 ||
                isConfirming
              }
            >
              {isConfirming ? "Confirming..." : "Confirm Assignments"}
            </Button>
            <Button
              variant="outline"
              onClick={resetBoardFromRecommendations}
              disabled={recommendations.length === 0}
            >
              Reset Board
            </Button>
          </div>
        </div>

        <div className="mt-3 grid grid-cols-2 gap-2 md:grid-cols-4">
          <div className="rounded-md border bg-muted/30 p-2 text-xs">
            <p className="text-muted-foreground">Total groups</p>
            <p className="text-sm font-semibold">{groupSummaries.length}</p>
          </div>
          <div className="rounded-md border bg-muted/30 p-2 text-xs">
            <p className="text-muted-foreground">Visible groups</p>
            <p className="text-sm font-semibold">
              {filteredGroupSummaries.length}
            </p>
          </div>
          <div className="rounded-md border bg-muted/30 p-2 text-xs">
            <p className="text-muted-foreground">Open seats</p>
            <p className="text-sm font-semibold">{totalRemainingSeats}</p>
          </div>
          <div className="rounded-md border bg-muted/30 p-2 text-xs">
            <p className="text-muted-foreground">Waiting students</p>
            <p className="text-sm font-semibold">
              {effectiveContainers[WAITING_CONTAINER_ID]?.length ?? 0}
            </p>
          </div>
        </div>

        {dragError ? (
          <p className="mt-3 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {dragError}
          </p>
        ) : null}
      </div>

      {recommendations.length === 0 ? (
        <div className="rounded-xl border border-dashed p-8 text-center text-sm text-muted-foreground">
          Click <span className="font-semibold">Run Match</span> to load
          recommended groups.
        </div>
      ) : (
        <DndContext
          sensors={sensors}
          collisionDetection={(args) => {
            const pointerHits = pointerWithin(args);
            if (pointerHits.length > 0) {
              return pointerHits;
            }

            return rectIntersection(args);
          }}
          onDragStart={(event) => {
            setActiveStudentId(toStringId(event.active.id as string | number));
          }}
          onDragCancel={() => setActiveStudentId(null)}
          onDragEnd={onDragEnd}
        >
          <section className="rounded-xl border bg-card p-4">
            <div className="mb-3 flex flex-wrap items-center gap-2">
              <input
                value={groupSearch}
                onChange={(event) => setGroupSearch(event.target.value)}
                placeholder="Search by group, tutor, or track"
                className="h-9 min-w-[220px] flex-1 rounded-md border px-3 text-sm"
              />
              <select
                value={trackFilter}
                onChange={(event) => setTrackFilter(event.target.value)}
                className="h-9 rounded-md border bg-background px-3 text-sm"
              >
                {availableTracks.map((track) => (
                  <option key={track} value={track}>
                    {track === "all" ? "All tracks" : track}
                  </option>
                ))}
              </select>
              <select
                value={groupFilter}
                onChange={(event) =>
                  setGroupFilter(event.target.value as GroupFilter)
                }
                className="h-9 rounded-md border bg-background px-3 text-sm"
              >
                <option value="all">All groups</option>
                <option value="needs_action">Has recommended students</option>
                <option value="has_space">Has space</option>
                <option value="full">Full groups</option>
              </select>
            </div>

            <div className="space-y-4">
              <div>
                <div className="mb-2 flex items-center justify-between">
                  <h3 className="text-base font-semibold">Waiting Area</h3>
                  <Badge variant="outline">
                    {effectiveContainers[WAITING_CONTAINER_ID]?.length ?? 0}{" "}
                    students
                  </Badge>
                </div>
                <DroppableStudentList
                  containerId={WAITING_CONTAINER_ID}
                  studentIds={effectiveContainers[WAITING_CONTAINER_ID] ?? []}
                  studentsById={boardData.studentsById}
                  recommendedGroupId={null}
                  emptyText="Drop students here to keep them waiting."
                  horizontal
                />
              </div>

              <div className="h-[70vh] overflow-auto rounded-lg border">
                {filteredGroupSummaries.length === 0 ? (
                  <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
                    No groups match current filters.
                  </div>
                ) : (
                  <div className="grid grid-cols-1 gap-4 p-4 md:grid-cols-2 xl:grid-cols-4">
                    {filteredGroupSummaries.map((item) => (
                      <section
                        key={item.containerId}
                        className="rounded-xl border bg-card p-3 shadow-sm"
                      >
                        <div className="flex items-center justify-between gap-2">
                          <div>
                            <h3 className="text-sm font-semibold">
                              {item.group.name}
                            </h3>
                            <p className="text-xs text-muted-foreground">
                              {item.group.track} | {item.group.tutor}
                            </p>
                          </div>
                          <Badge
                            variant={
                              item.remainingCapacity === 0
                                ? "destructive"
                                : "outline"
                            }
                          >
                            {item.totalCount}/{item.group.maxSize}
                          </Badge>
                        </div>
                        <div className="mt-2">
                          <p className="mb-1 text-xs text-muted-foreground">
                            Existing students
                          </p>
                          {item.group.existingStudents.length > 0 ? (
                            <div className="space-y-2 rounded-lg border border-dashed p-2">
                              {item.group.existingStudents.map(
                                (existingStudent) => (
                                  <ExistingStudentCard
                                    key={existingStudent.id}
                                    student={existingStudent}
                                  />
                                ),
                              )}
                            </div>
                          ) : (
                            <div className="rounded-lg border border-dashed py-4 text-center text-xs text-muted-foreground">
                              No existing students.
                            </div>
                          )}
                        </div>
                        <div className="mt-2">
                          <p className="mb-1 text-xs text-muted-foreground">
                            Recommended / moved
                          </p>
                          <DroppableStudentList
                            containerId={item.containerId}
                            studentIds={item.movedStudents}
                            studentsById={boardData.studentsById}
                            recommendedGroupId={item.group.id}
                            emptyText="Drop students here"
                          />
                        </div>
                      </section>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </section>

          <DragOverlay>
            {activeStudent ? (
              <div className="w-[300px]">
                <StudentCard
                  student={activeStudent}
                  isRecommendedInCurrentGroup={false}
                />
              </div>
            ) : null}
          </DragOverlay>
        </DndContext>
      )}
    </div>
  );
}
