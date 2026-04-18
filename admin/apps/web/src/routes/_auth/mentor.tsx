import { createFileRoute } from "@tanstack/react-router";
import { useState, useMemo } from "react";
import { useQueryMentorDetail, useMutationSetMentorActive, type MentorDetail } from "@/query/mentor";
import {
  useQueryMatchedGroups,
  useQueryMentorList,
  useMutationConfirmMentorAssignments,
  useMutationUnassignMentors,
} from "@/query/mentorMatch";
import { BulkReplaceDialog } from "@/components/match/BulkReplaceDialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
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
  MessageSquareOffIcon,
  RefreshCwIcon,
} from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { AxiosError } from "axios";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/_auth/mentor")({
  component: MentorPage,
});

function daysSince(dateStr: string | null): number | null {
  if (!dateStr) return null;
  const diff = Date.now() - new Date(dateStr).getTime();
  return Math.floor(diff / (1000 * 60 * 60 * 24));
}

function isEffectivelyInactive(mentor: MentorDetail, inactiveDays: number): boolean {
  if (!mentor.isActive) return true;
  const days = daysSince(mentor.lastMessageAt);
  if (days === null) return true; // never sent a message
  return days >= inactiveDays;
}

function MentorPage() {
  const queryClient = useQueryClient();
  const [inactiveDays, setInactiveDays] = useState(30);
  const [expandedIds, setExpandedIds] = useState<Set<number>>(new Set());
  const [bulkDialogOpen, setBulkDialogOpen] = useState(false);

  const { data: mentorDetailData, isPending: isLoadingMentors } = useQueryMentorDetail();
  const setMentorActive = useMutationSetMentorActive();
  const { data: matchedData, refetch: refetchMatched } = useQueryMatchedGroups();
  const { data: mentorListData } = useQueryMentorList();
  const confirmAssignments = useMutationConfirmMentorAssignments();
  const unassignMentors = useMutationUnassignMentors();

  const mentors = mentorDetailData?.data ?? [];
  const matchedGroups = matchedData?.data ?? [];
  const mentorListItems = mentorListData?.data ?? [];

  // Groups assigned to an effectively-inactive mentor
  const inactiveGroups = useMemo(() => {
    const inactiveMentorIds = new Set(
      mentors
        .filter((m) => isEffectivelyInactive(m, inactiveDays))
        .map((m) => m.mentorId),
    );
    return matchedGroups.filter((g) => inactiveMentorIds.has(g.mentor.mentorId));
  }, [mentors, matchedGroups, inactiveDays]);

  function toggleExpand(mentorId: number) {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(mentorId)) next.delete(mentorId);
      else next.add(mentorId);
      return next;
    });
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
        refetchMatched(),
        queryClient.invalidateQueries({ queryKey: ["unmatchedGroups"] }),
        queryClient.invalidateQueries({ queryKey: ["mentorDetail"] }),
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

  if (isLoadingMentors) {
    return <p className="p-4 text-sm text-muted-foreground">Loading...</p>;
  }

  return (
    <div className="space-y-4 p-4">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">Mentors</h1>
          <p className="text-sm text-muted-foreground">
            {mentors.length} mentor{mentors.length === 1 ? "" : "s"} registered
          </p>
        </div>
        <div className="flex items-center gap-3">
          {/* Inactive days threshold */}
          <div className="flex items-center gap-2">
            <label className="text-sm text-muted-foreground whitespace-nowrap">
              Inactive after
            </label>
            <Input
              type="number"
              min={1}
              value={inactiveDays}
              onChange={(e) => setInactiveDays(Math.max(1, Number(e.target.value)))}
              className="h-8 w-20 text-sm"
            />
            <span className="text-sm text-muted-foreground">days</span>
          </div>
          {inactiveGroups.length > 0 && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => setBulkDialogOpen(true)}
            >
              <RefreshCwIcon className="mr-1.5 size-3.5" />
              Replace Inactive Mentors
              <Badge variant="destructive" className="ml-1.5">
                {inactiveGroups.length}
              </Badge>
            </Button>
          )}
        </div>
      </div>

      {/* Table */}
      {mentors.length === 0 ? (
        <div className="rounded-xl border border-dashed p-8 text-center text-sm text-muted-foreground">
          No mentors registered yet.
        </div>
      ) : (
        <div className="rounded-xl border bg-card">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-8" />
                <TableHead>Name</TableHead>
                <TableHead>Track</TableHead>
                <TableHead>Institution</TableHead>
                <TableHead>Capacity</TableHead>
                <TableHead>Last Message</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {mentors.map((mentor) => {
                const inactive = isEffectivelyInactive(mentor, inactiveDays);
                const days = daysSince(mentor.lastMessageAt);
                const isExpanded = expandedIds.has(mentor.mentorId);

                return [
                  <TableRow
                    key={mentor.mentorId}
                    className={cn("cursor-pointer", inactive && "bg-destructive/5")}
                    onClick={() => toggleExpand(mentor.mentorId)}
                  >
                    <TableCell>
                      <button onClick={(e) => { e.stopPropagation(); toggleExpand(mentor.mentorId); }}>
                        {isExpanded
                          ? <ChevronDownIcon className="size-4 text-muted-foreground" />
                          : <ChevronRightIcon className="size-4 text-muted-foreground" />}
                      </button>
                    </TableCell>
                    <TableCell>
                      <p className="font-medium">{mentor.name}</p>
                      <p className="text-xs text-muted-foreground">{mentor.email}</p>
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline">{mentor.trackCode}</Badge>
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {mentor.institution ?? "—"}
                    </TableCell>
                    <TableCell className="text-sm">
                      {mentor.currentAssignedCount}/{mentor.maxGroupCount}
                      <span className="ml-1 text-xs text-muted-foreground">
                        ({mentor.remainingCapacity} left)
                      </span>
                    </TableCell>
                    <TableCell className="text-sm">
                      {mentor.lastMessageAt ? (
                        <span className={cn(days !== null && days >= inactiveDays && "text-destructive")}>
                          {days === 0 ? "Today" : days === 1 ? "Yesterday" : `${days} days ago`}
                        </span>
                      ) : (
                        <span className="flex items-center gap-1 text-xs text-muted-foreground">
                          <MessageSquareOffIcon className="size-3.5" />
                          Never
                        </span>
                      )}
                    </TableCell>
                    <TableCell onClick={(e) => e.stopPropagation()}>
                      <div className="flex items-center gap-2">
                        {mentor.isActive ? (
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
                        <Button
                          variant="outline"
                          size="sm"
                          className="h-7 text-xs"
                          disabled={setMentorActive.isPending}
                          onClick={() =>
                            setMentorActive.mutate({
                              mentorId: mentor.mentorId,
                              isActive: !mentor.isActive,
                            })
                          }
                        >
                          {mentor.isActive ? "Deactivate" : "Activate"}
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>,

                  isExpanded && (
                    <TableRow key={`detail-${mentor.mentorId}`} className="hover:bg-transparent">
                      <TableCell colSpan={7} className="p-0">
                        <div className="border-t bg-muted/20 px-6 py-3">
                          <p className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                            Interests
                          </p>
                          {mentor.interests.length > 0 ? (
                            <div className="flex flex-wrap gap-1">
                              {mentor.interests.map((i) => (
                                <Badge key={i} variant="secondary" className="text-xs">
                                  {i}
                                </Badge>
                              ))}
                            </div>
                          ) : (
                            <p className="text-xs text-muted-foreground">No interests listed.</p>
                          )}
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
        mentors={mentorListItems}
        onConfirm={handleBulkConfirm}
        isPending={confirmAssignments.isPending}
      />
    </div>
  );
}
