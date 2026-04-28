import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useMemo, useState } from "react";
import { StudentFilters } from "@/components/user/StudentFilters";
import { StudentTable } from "@/components/user/StudentTable";
import { studentColumns } from "@/components/user/columns";
import { Button } from "@/components/ui/button";
import { useQueryStudents, useQueryTracks } from "@/query/student";
import type { StudentTrack, StudentUser } from "@/type/user";
import { ShuffleIcon } from "lucide-react";
import type { ColumnDef } from "@tanstack/react-table";
import { useQueryGroups } from "@/query/group";
import { useMutationConfirmAssignments } from "@/query/match";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { AxiosError } from "axios";
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

const DEFAULT_GROUP_MAX_SIZE = 5;

export const Route = createFileRoute("/_auth/student")({
  component: StudentPage,
});

function ManualAssignDialog({
  student,
  groups,
  open,
  onOpenChange,
  onConfirm,
  isConfirming,
}: {
  student: StudentUser | null;
  groups: Array<{
    id: string;
    name: string;
    track: string;
    studentCount: number;
  }>;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: (groupId: number) => Promise<void>;
  isConfirming: boolean;
}) {
  const [selectedGroupId, setSelectedGroupId] = useState("");

  function handleOpenChange(nextOpen: boolean) {
    if (!nextOpen) {
      setSelectedGroupId("");
    }

    onOpenChange(nextOpen);
  }

  async function handleConfirm() {
    const groupId = Number(selectedGroupId);
    if (!student || !Number.isFinite(groupId)) return;

    await onConfirm(groupId);
    setSelectedGroupId("");
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Assign Student to Group</DialogTitle>
          <DialogDescription>
            Select a group for{" "}
            <span className="font-medium text-foreground">{student?.name}</span>
            {student?.track ? (
              <span className="ml-1 text-xs">({student.track})</span>
            ) : null}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-2">
          <Select value={selectedGroupId} onValueChange={setSelectedGroupId}>
            <SelectTrigger>
              <SelectValue placeholder="Select a group" />
            </SelectTrigger>
            <SelectContent>
              {groups.length === 0 ? (
                <SelectItem value="__empty" disabled>
                  No compatible groups found
                </SelectItem>
              ) : (
                groups.map((group) => (
                  <SelectItem key={group.id} value={group.id}>
                    {group.name} · {group.track} · {group.studentCount}/
                    {DEFAULT_GROUP_MAX_SIZE} students
                  </SelectItem>
                ))
              )}
            </SelectContent>
          </Select>
          <p className="text-xs text-muted-foreground">
            Only same-track groups are shown here for manual assignment.
          </p>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => handleOpenChange(false)}>
            Cancel
          </Button>
          <Button
            onClick={() => void handleConfirm()}
            disabled={!selectedGroupId || isConfirming || groups.length === 0}
          >
            {isConfirming ? "Assigning..." : "Confirm Assignment"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function StudentPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [yearLevel, setYearLevel] = useState("");
  const [track, setTrack] = useState<StudentTrack | undefined>();
  const [interest, setInterest] = useState("");
  const [inGroup, setInGroup] = useState<"yes" | "no" | "all">("all");
  const [page, setPage] = useState(1);
  const [assigningStudent, setAssigningStudent] = useState<StudentUser | null>(
    null,
  );

  const { data, isPending } = useQueryStudents({
    page,
    limit: 10,
    search: search || undefined,
    yearLevel: yearLevel ? Number(yearLevel) : undefined,
    track,
    interest: interest || undefined,
    inGroup: inGroup === "all" ? undefined : inGroup,
  });
  const { data: ungroupedStudentsData } = useQueryStudents({
    page: 1,
    limit: 1,
    inGroup: "no",
  });
  const { data: groupsData } = useQueryGroups({
    page: 1,
    limit: 100,
  });
  const { data: tracksData, isPending: isLoadingTracks } = useQueryTracks();
  const confirmAssignments = useMutationConfirmAssignments();

  useEffect(() => {
    setPage(1);
  }, [search, yearLevel, track, interest, inGroup]);

  const students = data?.data?.items ?? [];
  const total = data?.data?.total ?? 0;
  const hasUngroupedStudents = (ungroupedStudentsData?.data?.total ?? 0) > 0;
  const totalPages = useMemo(() => Math.max(1, Math.ceil(total / 10)), [total]);
  const assignableGroups = useMemo(() => {
    const currentTrack = assigningStudent?.track;
    const groups = groupsData?.data?.items ?? [];

    return groups
      .filter((group) => (currentTrack ? group.track === currentTrack : true))
      .map((group) => ({
        id: group.id,
        name: group.name,
        track: group.track,
        studentCount: group.members.filter((member) => member.role === "student")
          .length,
      }))
      .sort((a, b) => {
        const aHasSpace = a.studentCount < DEFAULT_GROUP_MAX_SIZE ? 0 : 1;
        const bHasSpace = b.studentCount < DEFAULT_GROUP_MAX_SIZE ? 0 : 1;

        if (aHasSpace !== bHasSpace) {
          return aHasSpace - bHasSpace;
        }

        if (a.studentCount !== b.studentCount) {
          return a.studentCount - b.studentCount;
        }

        return a.name.localeCompare(b.name);
      });
  }, [assigningStudent?.track, groupsData?.data?.items]);
  const columns = useMemo<ColumnDef<StudentUser>[]>(() => {
    const actionColumn: ColumnDef<StudentUser> = {
      id: "actions",
      header: "Action",
      cell: ({ row }) => {
        if (row.original.groupId) return null;

        return (
          <Button
            size="sm"
            variant="outline"
            onClick={(event) => {
              event.stopPropagation();
              setAssigningStudent(row.original);
            }}
          >
            Assign to Group
          </Button>
        );
      },
    };

    return [...studentColumns, actionColumn];
  }, []);

  const handleStudentClick = (student: { groupId: string | null }) => {
    if (!student.groupId) return;

    navigate({
      to: "/group",
      search: { page: 1, groupId: student.groupId },
    });
  };

  const handleMatchStudents = () => {
    navigate({
      to: "/matching",
      search: { run: true },
    });
  };

  async function handleConfirmAssignment(groupId: number) {
    if (!assigningStudent) return;

    try {
      await confirmAssignments.mutateAsync({
        assignments: [{ studentId: assigningStudent.id, groupId }],
      });
      toast.success("Student assigned successfully.");
      setAssigningStudent(null);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["students"] }),
        queryClient.invalidateQueries({ queryKey: ["groups"] }),
        queryClient.invalidateQueries({ queryKey: ["matchInfo"] }),
        queryClient.invalidateQueries({ queryKey: ["individualStudents"] }),
      ]);
    } catch (error) {
      if (error instanceof AxiosError) {
        const msg =
          (error.response?.data as { msg?: string } | undefined)?.msg ??
          error.message;
        toast.error(`Assignment failed: ${msg}`);
      } else {
        toast.error("Assignment failed. Please try again.");
      }
    }
  }

  return (
    <div className="p-4 space-y-4">
      {hasUngroupedStudents && (
        <div className="flex items-center justify-end">
          <Button onClick={handleMatchStudents}>
            <ShuffleIcon className="size-4" />
            Match Student
          </Button>
        </div>
      )}

      <StudentFilters
        search={search}
        onSearchChange={setSearch}
        yearLevel={yearLevel}
        onYearLevelChange={setYearLevel}
        track={track}
        onTrackChange={setTrack}
        tracks={tracksData?.data ?? []}
        isLoadingTracks={isLoadingTracks}
        interest={interest}
        onInterestChange={setInterest}
        inGroup={inGroup}
        onInGroupChange={setInGroup}
      />

      <StudentTable
        columns={columns}
        data={students}
        page={page}
        totalPages={totalPages}
        onPageChange={setPage}
        onRowClick={handleStudentClick}
        isPending={isPending}
      />

      <ManualAssignDialog
        student={assigningStudent}
        groups={assignableGroups}
        open={Boolean(assigningStudent)}
        onOpenChange={(open) => {
          if (!open) {
            setAssigningStudent(null);
          }
        }}
        onConfirm={handleConfirmAssignment}
        isConfirming={confirmAssignments.isPending}
      />
    </div>
  );
}
