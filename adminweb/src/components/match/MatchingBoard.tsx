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
import type {
  MatchRecommendationGroup,
  MatchRecommendedStudent,
  NotFullGroup,
} from "@/schema/match";
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
  recommendations: MatchRecommendationGroup[];
  unmatchedStudents: MatchRecommendedStudent[];
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
  country: string;
  yearLevel: string;
  interests: string[];
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
  interests: string[];
};

type MatchingGroup = {
  id: string;
  name: string;
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
  recommendationStudent: MatchRecommendedStudent["student"],
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

function formatInterests(interests?: string[]): string[] {
  return (interests ?? []).map((interest) => interest.trim()).filter(Boolean);
}

function getSharedInterests(
  students: Array<{ id: string; interests: string[] }>,
): string[] {
  const uniqueStudents = new Map<string, { id: string; interests: string[] }>();

  for (const student of students) {
    if (!uniqueStudents.has(student.id)) {
      uniqueStudents.set(student.id, student);
    }
  }

  const studentList = [...uniqueStudents.values()];
  if (studentList.length === 0) {
    return [];
  }

  const commonInterests = new Map<
    string,
    {
      label: string;
    }
  >();

  for (const interest of studentList[0].interests) {
    const label = interest.trim();
    if (label) {
      commonInterests.set(label.toLowerCase(), { label });
    }
  }

  for (const student of studentList.slice(1)) {
    const studentInterests = new Set(
      student.interests
        .map((interest) => interest.trim().toLowerCase())
        .filter(Boolean),
    );

    for (const interest of commonInterests.keys()) {
      if (!studentInterests.has(interest)) {
        commonInterests.delete(interest);
      }
    }
  }

  return [...commonInterests.values()]
    .map((interest) => interest.label)
    .sort((a, b) => a.localeCompare(b));
}

function toContainerId(groupId: string): string {
  return `group-${groupId}`;
}

function toMatchingGroup(
  group: MatchRecommendationGroup | NotFullGroup,
): MatchingGroup | null {
  if (!group) {
    return null;
  }

  const groupStudents =
    "existingStudents" in group ? group.existingStudents : group.groupStudent;

  return {
    id: toStringId(group.id),
    name: group.groupName,
    tutor: group.tutor?.name || "Unassigned",
    maxSize: group.maxSize ?? DEFAULT_GROUP_MAX_SIZE,
    existingStudents: groupStudents.map((groupStudent) => ({
      id: toStringId(groupStudent.id),
      name:
        groupStudent.name?.trim() || `Student #${toStringId(groupStudent.id)}`,
      yearLevel: formatYearLevel(
        groupStudent.yearLevel ?? groupStudent.yearlevel,
      ),
      interests: formatInterests(groupStudent.interests),
    })),
  };
}

function buildBoardData(
  recommendations: MatchRecommendationGroup[],
  unmatchedStudents: MatchRecommendedStudent[],
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

  for (const group of recommendations) {
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

    const existingMemberIds = new Set(
      (groupsByContainerId[containerId]?.existingStudents ?? []).map(
        (member) => member.id,
      ),
    );

    for (const recommendation of group.recommendStudents) {
      const studentId = toStringId(recommendation.student.id);

      studentsById[studentId] = {
        id: studentId,
        name: buildDisplayName(recommendation.student),
        country: recommendation.student.country ?? "",
        yearLevel: formatYearLevel(
          recommendation.student.yearLevel ?? recommendation.student.yearlevel,
        ),
        interests: formatInterests(recommendation.student.interests),
        score: recommendation.score,
        reason: recommendation.reason,
        recommendedGroupId: toStringId(group.id),
        scoreBreakdown: recommendation.scoreBreakdown,
      };

      if (!existingMemberIds.has(studentId)) {
        containers[containerId].push(studentId);
      }
    }
  }

  for (const recommendation of unmatchedStudents) {
    const studentId = toStringId(recommendation.student.id);
    studentsById[studentId] = {
      id: studentId,
      name: buildDisplayName(recommendation.student),
      country: recommendation.student.country ?? "",
      yearLevel: formatYearLevel(
        recommendation.student.yearLevel ?? recommendation.student.yearlevel,
      ),
      interests: formatInterests(recommendation.student.interests),
      score: recommendation.score,
      reason: recommendation.reason,
      recommendedGroupId: null,
      scoreBreakdown: recommendation.scoreBreakdown,
    };
    containers[WAITING_CONTAINER_ID].push(studentId);
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

function normalizeInterestKey(interest: string): string {
  return interest.trim().toLowerCase();
}

function hasSharedInterest(
  student: MovableStudent,
  group: MatchingGroup,
  movedStudentIds: string[],
  studentsById: Record<string, MovableStudent>,
): boolean {
  const studentInterests = new Set(
    student.interests.map(normalizeInterestKey).filter(Boolean),
  );

  if (studentInterests.size === 0) {
    return false;
  }

  const groupInterests = new Set(
    [
      ...group.existingStudents.flatMap((member) => member.interests),
      ...movedStudentIds.flatMap(
        (studentId) => studentsById[studentId]?.interests ?? [],
      ),
    ]
      .map(normalizeInterestKey)
      .filter(Boolean),
  );

  for (const interest of studentInterests) {
    if (groupInterests.has(interest)) {
      return true;
    }
  }

  return false;
}

function StudentCard({
  student,
  isRecommendedInCurrentGroup,
  isDragging,
  suppressTooltip,
}: {
  student: MovableStudent;
  isRecommendedInCurrentGroup: boolean;
  isDragging?: boolean;
  suppressTooltip?: boolean;
}) {
  return (
    <Tooltip open={isDragging || suppressTooltip ? false : undefined}>
      <TooltipTrigger asChild>
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
            <Badge
              variant={isRecommendedInCurrentGroup ? "default" : "outline"}
            >
              {student.score.toFixed(0)}
            </Badge>
          </div>
        </div>
      </TooltipTrigger>
      <TooltipContent
        side="top"
        className="w-[340px] max-w-[90vw] !flex !flex-col !items-stretch gap-2 rounded-lg border bg-card p-3 text-card-foreground shadow-lg"
      >
        <div className="rounded-md border bg-muted/20 p-2 text-xs">
          <p className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
            Student
          </p>
          <div className="mt-1 grid grid-cols-2 gap-2">
            <div>
              <span className="text-muted-foreground">Country</span>
              <p className="font-medium">{student.country || "N/A"}</p>
            </div>
            <div>
              <span className="text-muted-foreground">Year level</span>
              <p className="font-medium">{student.yearLevel}</p>
            </div>
          </div>
          <div className="mt-2">
            <span className="text-muted-foreground">Interests</span>
            {student.interests.length > 0 ? (
              <div className="mt-1 flex flex-wrap gap-1">
                {student.interests.map((interest) => (
                  <Badge
                    key={interest}
                    variant="secondary"
                    className="text-[10px]"
                  >
                    {interest}
                  </Badge>
                ))}
              </div>
            ) : (
              <p className="mt-1 text-muted-foreground">No interests listed.</p>
            )}
          </div>
        </div>

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
              <span className="text-muted-foreground">Location penalty</span>
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
  );
}

function ExistingStudentCard({
  student,
  suppressTooltip,
}: {
  student: GroupMember;
  suppressTooltip?: boolean;
}) {
  return (
    <Tooltip open={suppressTooltip ? false : undefined}>
      <TooltipTrigger asChild>
        <div className="rounded-lg border bg-card/70 p-2 text-card-foreground">
          <p className="truncate text-xs font-semibold">{student.name}</p>
        </div>
      </TooltipTrigger>
      <TooltipContent
        side="top"
        className="w-[260px] max-w-[90vw] !flex !flex-col !items-stretch gap-2 rounded-lg border bg-card p-3 text-card-foreground shadow-lg"
      >
        <div className="rounded-md border bg-muted/20 p-2 text-xs">
          <p className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
            Student
          </p>
          <div className="mt-1">
            <span className="text-muted-foreground">Year level</span>
            <p className="font-medium">{student.yearLevel}</p>
          </div>
          <div className="mt-2">
            <span className="text-muted-foreground">Interests</span>
            {student.interests.length > 0 ? (
              <div className="mt-1 flex flex-wrap gap-1">
                {student.interests.map((interest) => (
                  <Badge
                    key={interest}
                    variant="secondary"
                    className="text-[10px]"
                  >
                    {interest}
                  </Badge>
                ))}
              </div>
            ) : (
              <p className="mt-1 text-muted-foreground">No interests listed.</p>
            )}
          </div>
        </div>
      </TooltipContent>
    </Tooltip>
  );
}

function SortableStudentCard({
  student,
  isRecommendedInCurrentGroup,
  suppressTooltip,
}: {
  student: MovableStudent;
  isRecommendedInCurrentGroup: boolean;
  suppressTooltip?: boolean;
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
        suppressTooltip={suppressTooltip}
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
  suppressTooltips,
}: {
  containerId: string;
  studentIds: string[];
  studentsById: Record<string, MovableStudent>;
  recommendedGroupId: string | null;
  emptyText: string;
  horizontal?: boolean;
  suppressTooltips?: boolean;
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
                <div key={studentId} className={cn(horizontal && "shrink-0")}>
                  <SortableStudentCard
                    student={student}
                    isRecommendedInCurrentGroup={
                      recommendedGroupId !== null &&
                      student.recommendedGroupId === recommendedGroupId
                    }
                    suppressTooltip={suppressTooltips}
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
  unmatchedStudents,
  notFullGroups,
  onRunMatch,
  onConfirmAssignments,
  isRunning,
  isConfirming,
}: MatchingBoardProps) {
  const boardData = useMemo(
    () => buildBoardData(recommendations, unmatchedStudents, notFullGroups),
    [notFullGroups, recommendations, unmatchedStudents],
  );
  const [containers, setContainers] = useState<Record<string, string[]>>({});
  const [activeStudentId, setActiveStudentId] = useState<string | null>(null);
  const [groupSearch, setGroupSearch] = useState("");
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
        const movedStudentDetails = movedStudents
          .map((studentId) => boardData.studentsById[studentId])
          .filter((student): student is MovableStudent => Boolean(student));
        const sharedInterests = getSharedInterests([
          ...group.existingStudents,
          ...movedStudentDetails,
        ]);

        return {
          containerId,
          group,
          movedStudents,
          sharedInterests,
          existingCount,
          recommendedCount,
          totalCount,
          remainingCapacity,
        };
      },
    );
  }, [
    boardData.groupsByContainerId,
    boardData.studentsById,
    effectiveContainers,
  ]);

  const filteredGroupSummaries = useMemo(() => {
    const query = groupSearch.trim().toLowerCase();

    return groupSummaries
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
          item.group.tutor.toLowerCase().includes(query)
        );
      })
      .sort((a, b) => a.group.name.localeCompare(b.group.name));
  }, [groupFilter, groupSearch, groupSummaries]);

  const waitingStudentIds = effectiveContainers[WAITING_CONTAINER_ID] ?? [];

  useEffect(() => {
    setContainers(boardData.containers);
  }, [boardData.containers]);

  function resetBoardFromRecommendations() {
    setContainers(boardData.containers);
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

    const currentContainers = effectiveContainers;

    const sourceContainerId = findContainerId(activeId, currentContainers);
    const targetContainerId = resolveDropContainer(overId, currentContainers);

    if (!sourceContainerId || !targetContainerId) {
      return;
    }

    if (sourceContainerId === targetContainerId) {
      const sourceItems = currentContainers[sourceContainerId];
      const activeIndex = sourceItems.indexOf(activeId);
      const overIndex = sourceItems.indexOf(overId);

      if (activeIndex < 0 || overIndex < 0 || activeIndex === overIndex) {
        return;
      }

      setContainers({
        ...currentContainers,
        [sourceContainerId]: arrayMove(sourceItems, activeIndex, overIndex),
      });
      return;
    }

    if (targetContainerId !== WAITING_CONTAINER_ID) {
      const targetGroup = boardData.groupsByContainerId[targetContainerId];
      const draggedStudent = boardData.studentsById[activeId];
      if (targetGroup) {
        if (
          !draggedStudent ||
          !hasSharedInterest(
            draggedStudent,
            targetGroup,
            currentContainers[targetContainerId] ?? [],
            boardData.studentsById,
          )
        ) {
          toast.error(
            `${draggedStudent?.name ?? "Student"} cannot be assigned to ${targetGroup.name}: no shared interest with the group.`,
          );
          return;
        }

        const existingCount = targetGroup.existingStudents.length;
        const currentMovedCount = currentContainers[targetContainerId].length;
        if (existingCount + currentMovedCount >= targetGroup.maxSize) {
          toast.error(
            `${targetGroup.name} is full (${targetGroup.maxSize}/${targetGroup.maxSize}).`,
          );
          return;
        }
      }
    }

    const sourceItems = [...currentContainers[sourceContainerId]];
    const sourceIndex = sourceItems.indexOf(activeId);
    if (sourceIndex === -1) {
      return;
    }
    sourceItems.splice(sourceIndex, 1);

    const targetItems = [...currentContainers[targetContainerId]];
    const targetIndex = currentContainers[targetContainerId].includes(overId)
      ? currentContainers[targetContainerId].indexOf(overId)
      : targetItems.length;
    targetItems.splice(targetIndex, 0, activeId);

    setContainers({
      ...currentContainers,
      [sourceContainerId]: sourceItems,
      [targetContainerId]: targetItems,
    });
  }

  const totalRemainingSeats = groupSummaries.reduce(
    (sum, item) => sum + item.remainingCapacity,
    0,
  );
  const recommendationStudentCount =
    recommendations.reduce(
      (sum, group) => sum + group.recommendStudents.length,
      0,
    ) + unmatchedStudents.length;
  const waitingStudentCount =
    effectiveContainers[WAITING_CONTAINER_ID]?.length ?? 0;

  function buildAssignmentsPayload() {
    const payload: Array<{ studentId: number; groupId: number | string }> = [];

    for (const [containerId, studentIds] of Object.entries(
      effectiveContainers,
    )) {
      if (containerId === WAITING_CONTAINER_ID) {
        continue;
      }

      const group = boardData.groupsByContainerId[containerId];
      if (!group) {
        continue;
      }

      const numericGroupId = Number(group.id);
      const groupId = Number.isFinite(numericGroupId)
        ? numericGroupId
        : group.id;

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
    const assignments = buildAssignmentsPayload();
    if (assignments.length === 0) {
      toast.error("No assignments to confirm.");
      return;
    }

    void onConfirmAssignments(assignments);
  }

  return (
    <div className="space-y-4">
      <div className="rounded-xl  bg-card">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-sm text-muted-foreground">
              Drag students to assign them to groups.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button onClick={onRunMatch} disabled={isRunning}>
              {isRunning ? "Matching..." : "Run Match"}
            </Button>
            <Button onClick={onClickConfirmAssignments} disabled={isConfirming}>
              {isConfirming ? "Confirming..." : "Confirm Assignments"}
            </Button>
            <Button
              variant="outline"
              onClick={resetBoardFromRecommendations}
              disabled={recommendationStudentCount === 0}
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
            <p className="text-sm font-semibold">{waitingStudentCount}</p>
          </div>
        </div>
      </div>

      {recommendationStudentCount === 0 ? (
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
          <section className="bg-card">
            <div className="mb-3 flex flex-wrap items-center gap-2">
              <input
                value={groupSearch}
                onChange={(event) => setGroupSearch(event.target.value)}
                placeholder="Search by group or tutor"
                className="h-9 flex-1 rounded-md border px-3 text-sm"
              />
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
                    {`${waitingStudentIds.length} students`}
                  </Badge>
                </div>
                <DroppableStudentList
                  containerId={WAITING_CONTAINER_ID}
                  studentIds={waitingStudentIds}
                  studentsById={boardData.studentsById}
                  recommendedGroupId={null}
                  emptyText="Drop students here to keep them waiting."
                  horizontal
                  suppressTooltips={activeStudentId !== null}
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
                              {item.group.tutor}
                            </p>
                          </div>
                          <Badge>
                            {item.totalCount}/{item.group.maxSize}
                          </Badge>
                        </div>
                        <div className="mt-2">
                          <p className="mb-1 text-xs text-muted-foreground">
                            Shared interests
                          </p>
                          {item.sharedInterests.length > 0 ? (
                            <div className="flex flex-wrap gap-1">
                              {item.sharedInterests.map((interest) => (
                                <Badge
                                  key={interest}
                                  variant="secondary"
                                  className="text-[10px]"
                                >
                                  {interest}
                                </Badge>
                              ))}
                            </div>
                          ) : (
                            <p className="text-xs text-muted-foreground">
                              No shared interests yet.
                            </p>
                          )}
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
                                    suppressTooltip={activeStudentId !== null}
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
                            suppressTooltips={activeStudentId !== null}
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
              <div className="">
                <StudentCard
                  student={activeStudent}
                  isRecommendedInCurrentGroup={false}
                  isDragging
                />
              </div>
            ) : null}
          </DragOverlay>
        </DndContext>
      )}
    </div>
  );
}
