import { useState } from "react";
import {
  useQueryMatchedGroups,
  useQueryMentorList,
  useMutationReplaceMentor,
  useMutationConfirmMentorAssignments,
  useMutationUnassignMentors,
} from "@/query/mentorMatch";
import { useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "@tanstack/react-router";
import type { MatchedGroup } from "@/type/mentorMatch";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { BulkReplaceDialog } from "@/components/match/BulkReplaceDialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  AlertTriangleIcon,
  CheckCircle2Icon,
  ChevronDownIcon,
  ChevronRightIcon,
  RefreshCwIcon,
} from "lucide-react";
import { toast } from "sonner";
import { AxiosError } from "axios";

export function MatchedGroupsPanel() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const { data: matchedData, isPending: isLoadingMatched, refetch } = useQueryMatchedGroups();
  const { data: mentorListData, isPending: isLoadingMentors } = useQueryMentorList();
  const replaceMentor = useMutationReplaceMentor();
  const confirmAssignments = useMutationConfirmMentorAssignments();
  const unassignMentors = useMutationUnassignMentors();

  const [replacingId, setReplacingId] = useState<number | null>(null);
  const [selectedMentorId, setSelectedMentorId] = useState<string>("");
  const [expandedIds, setExpandedIds] = useState<Set<number>>(new Set());

  const [bulkDialogOpen, setBulkDialogOpen] = useState(false);

  const matchedGroups: MatchedGroup[] = matchedData?.data ?? [];
  const mentors = mentorListData?.data ?? [];
  const inactiveGroups = matchedGroups.filter((g) => !g.mentor.isActive);
  const inactiveCount = inactiveGroups.length;

  function toggleExpand(membershipId: number) {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(membershipId)) next.delete(membershipId);
      else next.add(membershipId);
      return next;
    });
  }

  function startReplace(membershipId: number) {
    setReplacingId(membershipId);
    setSelectedMentorId("");
  }

  function cancelReplace() {
    setReplacingId(null);
    setSelectedMentorId("");
  }

  async function confirmReplace(group: MatchedGroup) {
    if (!selectedMentorId) {
      toast.error("Please select an action.");
      return;
    }
    try {
      if (selectedMentorId === "unassign") {
        await unassignMentors.mutateAsync([group.groupId]);
        toast.success("Mentor unassigned — group is now unmatched.");
      } else {
        await replaceMentor.mutateAsync({
          membershipId: group.membershipId,
          groupId: group.groupId,
          newMentorUserId: Number(selectedMentorId),
        });
        toast.success("Mentor replaced successfully.");
      }
      setReplacingId(null);
      setSelectedMentorId("");
      await Promise.all([
        refetch(),
        queryClient.invalidateQueries({ queryKey: ["unmatchedGroups"] }),
      ]);
    } catch (error) {
      const msg =
        error instanceof AxiosError
          ? ((error.response?.data as { msg?: string } | undefined)?.msg ?? error.message)
          : "Action failed. Please try again.";
      toast.error(msg);
    }
  }

  async function handleBulkConfirm(
    assignments: Array<{ groupId: number; mentorUserId: number }>,
    unassigns: number[],
  ) {
    try {
      await Promise.all([
        assignments.length > 0 ? confirmAssignments.mutateAsync({ assignments }) : Promise.resolve(),
        unassigns.length > 0 ? unassignMentors.mutateAsync(unassigns) : Promise.resolve(),
      ]);
      setBulkDialogOpen(false);
      await Promise.all([
        refetch(),
        queryClient.invalidateQueries({ queryKey: ["unmatchedGroups"] }),
        queryClient.invalidateQueries({ queryKey: ["mentorList"] }),
      ]);
      const parts = [];
      if (assignments.length > 0) parts.push(`${assignments.length} replaced`);
      if (unassigns.length > 0) parts.push(`${unassigns.length} unassigned`);
      toast.success(parts.join(", ") + ".");
    } catch (error) {
      const msg =
        error instanceof AxiosError
          ? ((error.response?.data as { msg?: string } | undefined)?.msg ?? error.message)
          : "Bulk replace failed. Please try again.";
      toast.error(`Bulk replace failed: ${msg}`);
    }
  }

  if (isLoadingMatched || isLoadingMentors) {
    return <p className="text-sm text-muted-foreground">Loading matched assignments...</p>;
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h2 className="text-base font-semibold">Matched Groups</h2>
          <Badge variant="secondary">{matchedGroups.length}</Badge>
          {inactiveCount > 0 && (
            <Badge variant="destructive" className="gap-1">
              <AlertTriangleIcon className="size-3" />
              {inactiveCount} inactive
            </Badge>
          )}
        </div>
        {inactiveCount > 0 && (
          <Button variant="outline" size="sm" onClick={() => setBulkDialogOpen(true)}>
            <RefreshCwIcon className="size-3.5 mr-1.5" />
            Replace Inactive Mentors
          </Button>
        )}
      </div>

      {/* Table */}
      {matchedGroups.length === 0 ? (
        <div className="rounded-xl border border-dashed p-8 text-center text-sm text-muted-foreground">
          No confirmed mentor assignments yet.
        </div>
      ) : (
        <div className="rounded-xl border bg-card">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-8" />
                <TableHead>Group</TableHead>
                <TableHead>Track</TableHead>
                <TableHead>Students</TableHead>
                <TableHead>Mentor</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="w-64">Action</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {matchedGroups.flatMap((group) => {
                const isReplacing = replacingId === group.membershipId;
                const isExpanded = expandedIds.has(group.membershipId);

                return [
                  <TableRow key={group.membershipId} className="cursor-pointer" onClick={() => toggleExpand(group.membershipId)}>
                    <TableCell onClick={(e) => e.stopPropagation()} className="text-muted-foreground">
                      <button onClick={() => toggleExpand(group.membershipId)}>
                        {isExpanded
                          ? <ChevronDownIcon className="size-4" />
                          : <ChevronRightIcon className="size-4" />}
                      </button>
                    </TableCell>
                    <TableCell className="font-medium">{group.groupName}</TableCell>
                    <TableCell>
                      <Badge variant="outline">{group.trackCode}</Badge>
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {group.studentCount}
                    </TableCell>
                    <TableCell>
                      <div>
                        <p className="text-sm">{group.mentor.name}</p>
                        {group.mentor.institution && (
                          <p className="text-xs text-muted-foreground">{group.mentor.institution}</p>
                        )}
                      </div>
                    </TableCell>
                    <TableCell onClick={(e) => e.stopPropagation()}>
                      {group.mentor.isActive ? (
                        <span className="flex items-center gap-1 text-xs text-green-600">
                          <CheckCircle2Icon className="size-3.5" />
                          Active
                        </span>
                      ) : (
                        <span className="flex items-center gap-1 text-xs text-destructive">
                          <AlertTriangleIcon className="size-3.5" />
                          Inactive
                        </span>
                      )}
                    </TableCell>
                    <TableCell onClick={(e) => e.stopPropagation()}>
                      {isReplacing ? (
                        <div className="flex items-center gap-2">
                          <Select value={selectedMentorId} onValueChange={setSelectedMentorId}>
                            <SelectTrigger className="h-8 w-44 text-xs">
                              <SelectValue placeholder="Select action" />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="unassign" className="text-muted-foreground">
                                — Unassign (leave unmatched)
                              </SelectItem>
                              {mentors.map((m) => (
                                <SelectItem key={m.mentorId} value={String(m.mentorId)}>
                                  {m.name}
                                  {m.remainingCapacity === 0 && (
                                    <span className="ml-1 text-muted-foreground">(full)</span>
                                  )}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                          <Button
                            size="sm"
                            className="h-8 text-xs"
                            onClick={() => confirmReplace(group)}
                            disabled={!selectedMentorId || replaceMentor.isPending || unassignMentors.isPending}
                          >
                            Confirm
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-8 text-xs"
                            onClick={cancelReplace}
                            disabled={replaceMentor.isPending}
                          >
                            Cancel
                          </Button>
                        </div>
                      ) : (
                        <Button
                          variant="outline"
                          size="sm"
                          className="h-8 text-xs"
                          onClick={() => startReplace(group.membershipId)}
                        >
                          Replace Mentor
                        </Button>
                      )}
                    </TableCell>
                  </TableRow>,

                  isExpanded && (
                    <TableRow key={`detail-${group.membershipId}`} className="hover:bg-transparent">
                      <TableCell colSpan={7} className="p-0">
                        <div className="grid gap-3 px-6 py-3 md:grid-cols-2 bg-muted/20 border-t">
                          {/* Students */}
                          <div className="space-y-2">
                            <p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                              Students ({group.studentCount})
                            </p>
                            {group.students.length > 0 ? (
                              <div className="space-y-1.5">
                                {group.students.map((s) => (
                                  <div key={s.name} className="rounded border bg-background px-3 py-1.5">
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
                              <p className="text-xs text-muted-foreground">No student data available.</p>
                            )}
                          </div>
                          {/* Mentor detail */}
                          <div className="space-y-2">
                            <p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                              Assigned Mentor
                            </p>
                            <div className="rounded border bg-background px-3 py-2 space-y-1">
                              <p className="text-sm font-medium">{group.mentor.name}</p>
                              {group.mentor.institution && (
                                <p className="text-xs text-muted-foreground">{group.mentor.institution}</p>
                              )}
                              <div className="flex items-center gap-2">
                                <Badge variant="outline" className="text-xs">{group.mentor.trackCode}</Badge>
                                {group.mentor.isActive ? (
                                  <span className="text-xs text-green-600">Active</span>
                                ) : (
                                  <span className="text-xs text-destructive">Inactive</span>
                                )}
                              </div>
                            </div>
                          </div>
                        </div>
                      </TableCell>
                    </TableRow>
                  ),
                ].filter(Boolean);
              })}
            </TableBody>
          </Table>
        </div>
      )}
      <BulkReplaceDialog
        open={bulkDialogOpen}
        onOpenChange={setBulkDialogOpen}
        inactiveGroups={inactiveGroups}
        mentors={mentors}
        onConfirm={handleBulkConfirm}
        isPending={confirmAssignments.isPending}
      />
    </div>
  );
}
