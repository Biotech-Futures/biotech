import { createFileRoute } from "@tanstack/react-router";
import { useCallback, useState, useMemo } from "react";
import {
  useQueryMentorDetail,
  useMutationSetMentorActive,
  type MentorDetail,
} from "@/query/mentor";
import {
  useQueryMatchedGroups,
  useQueryMentorList,
  useMutationConfirmMentorAssignments,
  useMutationUnassignMentors,
} from "@/query/mentorMatch";
import { BulkReplaceDialog } from "@/components/match/BulkReplaceDialog";
import { MentorImportSheet } from "@/components/user/MentorImportSheet";
import { UserBulkActionsBar } from "@/components/user/UserBulkActionsBar";
import { useBulkUpdateUserStatus } from "@/query/user";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  SortableTableHead,
  useSortableRows,
  type SortState,
} from "@/components/ui/sortable-table";
import {
  AlertTriangleIcon,
  CheckCircle2Icon,
  ChevronDownIcon,
  ChevronRightIcon,
  MessageSquareOffIcon,
  RefreshCwIcon,
  ShieldCheckIcon,
  ClockIcon,
  UploadIcon,
} from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { AxiosError } from "axios";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/_auth/people/mentors")({
  component: MentorPage,
});

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

type MentorSortKey =
  | "name"
  | "country"
  | "institution"
  | "capacity"
  | "lastMessage"
  | "status";

const initialMentorSort: SortState<MentorSortKey> = {
  key: "name",
  direction: "asc",
};

function daysSince(dateStr: string | null): number | null {
  if (!dateStr) return null;
  const diff = Date.now() - new Date(dateStr).getTime();
  return Math.floor(diff / (1000 * 60 * 60 * 24));
}

function isEffectivelyInactive(
  mentor: MentorDetail,
  inactiveDays: number,
): boolean {
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
  const [bulkImportOpen, setBulkImportOpen] = useState(false);
  // Selected mentor account ids (mentorId is the user id). The tab loads every
  // mentor at once (no pagination), so "select all" naturally covers them all.
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [bulkAction, setBulkAction] = useState<{
    action: "activate" | "deactivate";
    count: number;
  } | null>(null);

  const { data: mentorDetailData, isPending: isLoadingMentors } =
    useQueryMentorDetail();
  const setMentorActive = useMutationSetMentorActive();
  const bulkUpdateUserStatus = useBulkUpdateUserStatus();
  const { data: matchedData, refetch: refetchMatched } =
    useQueryMatchedGroups();
  const { data: mentorListData } = useQueryMentorList();
  const confirmAssignments = useMutationConfirmMentorAssignments();
  const unassignMentors = useMutationUnassignMentors();

  const mentors = mentorDetailData?.data ?? [];
  const matchedGroups = matchedData?.data ?? [];
  const mentorListItems = mentorListData?.data ?? [];

  const clearSelection = () => setSelectedIds(new Set());
  const allMentorIds = mentors.map((m) => m.mentorId);
  const headerChecked: boolean | "indeterminate" =
    selectedIds.size === 0
      ? false
      : allMentorIds.length > 0 && allMentorIds.every((id) => selectedIds.has(id))
        ? true
        : "indeterminate";

  const toggleAll = () => {
    setSelectedIds((prev) =>
      allMentorIds.length > 0 && allMentorIds.every((id) => prev.has(id))
        ? new Set()
        : new Set(allMentorIds),
    );
  };

  const toggleOne = (mentorId: number) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(mentorId)) next.delete(mentorId);
      else next.add(mentorId);
      return next;
    });
  };

  const handleBulkStatusConfirm = async () => {
    if (!bulkAction || selectedIds.size === 0) {
      setBulkAction(null);
      return;
    }
    try {
      const response = await bulkUpdateUserStatus.mutateAsync({
        ids: [...selectedIds].map(String),
        isActive: bulkAction.action === "activate",
      });
      if (!response.data) {
        toast.error(response.msg || "Unable to update mentor statuses.");
        return;
      }
      toast.success(response.msg);
      void queryClient.invalidateQueries({ queryKey: ["mentorDetail"] });
      clearSelection();
    } catch {
      toast.error("Unable to update mentor statuses right now.");
    } finally {
      setBulkAction(null);
    }
  };
  const getMentorSortValue = useCallback(
    (mentor: MentorDetail, key: MentorSortKey) => {
      switch (key) {
        case "name":
          return `${mentor.name} ${mentor.email}`;
        case "country":
          return mentor.countryName;
        case "institution":
          return mentor.institution ?? "";
        case "capacity":
          return mentor.remainingCapacity;
        case "lastMessage":
          return mentor.lastMessageAt ?? "";
        case "status":
          return isEffectivelyInactive(mentor, inactiveDays) ? "Inactive" : "Active";
      }
    },
    [inactiveDays],
  );
  const { sortState, setSortState, sortedRows: sortedMentors } = useSortableRows(
    mentors,
    initialMentorSort,
    getMentorSortValue,
  );

  // Groups assigned to an effectively-inactive mentor
  const inactiveGroups = useMemo(() => {
    const inactiveMentorIds = new Set(
      mentors
        .filter((m) => isEffectivelyInactive(m, inactiveDays))
        .map((m) => m.mentorId),
    );
    return matchedGroups.filter((g) =>
      inactiveMentorIds.has(g.mentor.mentorId),
    );
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
        assignments.length > 0
          ? confirmAssignments.mutateAsync({ assignments })
          : Promise.resolve(),
        unassigns.length > 0
          ? unassignMentors.mutateAsync(unassigns)
          : Promise.resolve(),
      ]);
      setBulkDialogOpen(false);
      await Promise.all([
        refetchMatched(),
        queryClient.refetchQueries({ queryKey: ["groups"] }),
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
          ? ((error.response?.data as { msg?: string } | undefined)?.msg ??
            error.message)
          : "Bulk replace failed. Please try again.";
      toast.error(`Bulk replace failed: ${msg}`);
    }
  }

  if (isLoadingMentors) {
    return <p className="text-sm text-muted-foreground">Loading...</p>;
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-sm text-muted-foreground">
            {mentors.length} mentor{mentors.length === 1 ? "" : "s"} registered
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setBulkImportOpen(true)}
          >
            <UploadIcon className="mr-1.5 size-3.5" />
            Import Mentors CSV
          </Button>
          {/* Inactive days threshold */}
          <div className="flex items-center gap-2">
            <label className="text-sm text-muted-foreground whitespace-nowrap">
              Inactive after
            </label>
            <Input
              type="number"
              min={1}
              value={inactiveDays}
              onChange={(e) =>
                setInactiveDays(Math.max(1, Number(e.target.value)))
              }
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

      {selectedIds.size > 0 && (
        <UserBulkActionsBar
          count={selectedIds.size}
          noun="mentor"
          onActivate={() =>
            setBulkAction({ action: "activate", count: selectedIds.size })
          }
          onDeactivate={() =>
            setBulkAction({ action: "deactivate", count: selectedIds.size })
          }
          onClear={clearSelection}
          isPending={bulkUpdateUserStatus.isPending}
        />
      )}

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
                <TableHead className="w-10">
                  <Checkbox
                    checked={headerChecked}
                    onCheckedChange={toggleAll}
                    disabled={isLoadingMentors || mentors.length === 0}
                    aria-label="Select all mentors"
                  />
                </TableHead>
                <TableHead className="w-8" />
                <TableHead>
                  <SortableTableHead
                    label="Name"
                    sortKey="name"
                    sortState={sortState}
                    onSortChange={setSortState}
                  />
                </TableHead>
                <TableHead>
                  <SortableTableHead
                    label="Country"
                    sortKey="country"
                    sortState={sortState}
                    onSortChange={setSortState}
                  />
                </TableHead>
                <TableHead>
                  <SortableTableHead
                    label="Institution"
                    sortKey="institution"
                    sortState={sortState}
                    onSortChange={setSortState}
                  />
                </TableHead>
                <TableHead>
                  <SortableTableHead
                    label="Capacity"
                    sortKey="capacity"
                    sortState={sortState}
                    onSortChange={setSortState}
                  />
                </TableHead>
                <TableHead>
                  <SortableTableHead
                    label="Last Message"
                    sortKey="lastMessage"
                    sortState={sortState}
                    onSortChange={setSortState}
                  />
                </TableHead>
                <TableHead>
                  <SortableTableHead
                    label="Status"
                    sortKey="status"
                    sortState={sortState}
                    onSortChange={setSortState}
                  />
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {sortedMentors.map((mentor) => {
                const inactive = isEffectivelyInactive(mentor, inactiveDays);
                const days = daysSince(mentor.lastMessageAt);
                const isExpanded = expandedIds.has(mentor.mentorId);

                return [
                  <TableRow
                    key={mentor.mentorId}
                    data-state={
                      selectedIds.has(mentor.mentorId) ? "selected" : undefined
                    }
                    className={cn(
                      "cursor-pointer",
                      inactive && "bg-destructive/5",
                    )}
                    onClick={() => toggleExpand(mentor.mentorId)}
                  >
                    <TableCell onClick={(e) => e.stopPropagation()}>
                      <Checkbox
                        checked={selectedIds.has(mentor.mentorId)}
                        onCheckedChange={() => toggleOne(mentor.mentorId)}
                        aria-label={`Select ${mentor.name}`}
                      />
                    </TableCell>
                    <TableCell>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          toggleExpand(mentor.mentorId);
                        }}
                      >
                        {isExpanded ? (
                          <ChevronDownIcon className="size-4 text-muted-foreground" />
                        ) : (
                          <ChevronRightIcon className="size-4 text-muted-foreground" />
                        )}
                      </button>
                    </TableCell>
                    <TableCell>
                      <p className="font-medium">{mentor.name}</p>
                      <p className="text-xs text-muted-foreground">
                        {mentor.email}
                      </p>
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline">{mentor.countryName}</Badge>
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
                        <span
                          className={cn(
                            days !== null &&
                              days >= inactiveDays &&
                              "text-destructive",
                          )}
                        >
                          {days === 0
                            ? "Today"
                            : days === 1
                              ? "Yesterday"
                              : `${days} days ago`}
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
                    <TableRow
                      key={`detail-${mentor.mentorId}`}
                      className="hover:bg-transparent"
                    >
                      <TableCell colSpan={8} className="p-0">
                        <div className="border-t bg-muted/20 px-6 py-4 space-y-4">
                          {/* Basic Info */}
                          <div>
                            <p className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                              Account Info
                            </p>
                            <div className="grid grid-cols-2 gap-x-8 gap-y-1 text-xs">
                              <div className="flex gap-2">
                                <span className="text-muted-foreground">
                                  User ID:
                                </span>
                                <span className="font-mono">
                                  {mentor.mentorId}
                                </span>
                              </div>
                              <div className="flex gap-2">
                                <span className="text-muted-foreground">
                                  Email:
                                </span>
                                <span>{mentor.email}</span>
                              </div>
                              <div className="flex gap-2">
                                <span className="text-muted-foreground">
                                  Institution:
                                </span>
                                <span>{mentor.institution ?? "—"}</span>
                              </div>
                              <div className="flex gap-2">
                                <span className="text-muted-foreground">
                                  Max Groups:
                                </span>
                                <span>{mentor.maxGroupCount}</span>
                              </div>
                            </div>
                          </div>

                          {/* Interests */}
                          <div>
                            <p className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                              Interests
                            </p>
                            {mentor.interests.length > 0 ? (
                              <div className="flex flex-wrap gap-1">
                                {mentor.interests.map((i) => (
                                  <Badge
                                    key={i}
                                    variant="secondary"
                                    className="text-xs"
                                  >
                                    {i}
                                  </Badge>
                                ))}
                              </div>
                            ) : (
                              <p className="text-xs text-muted-foreground">
                                No interests listed.
                              </p>
                            )}
                          </div>

                          {/* Availability */}
                          <div>
                            <p className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground flex items-center gap-1">
                              <ClockIcon className="size-3" /> Availability
                            </p>
                            {mentor.availability.length > 0 ? (
                              <div className="flex flex-wrap gap-2">
                                {[...mentor.availability]
                                  .sort((a, b) => a.weekday - b.weekday)
                                  .map((slot, idx) => (
                                    <div
                                      key={idx}
                                      className="rounded-md border bg-background px-2 py-1 text-xs"
                                    >
                                      <span className="font-medium">
                                        {WEEKDAYS[slot.weekday]}
                                      </span>
                                      <span className="ml-1 text-muted-foreground">
                                        {slot.startTime.slice(0, 5)}–
                                        {slot.endTime.slice(0, 5)}
                                      </span>
                                    </div>
                                  ))}
                              </div>
                            ) : (
                              <p className="text-xs text-muted-foreground">
                                No availability set.
                              </p>
                            )}
                          </div>

                          {/* Certificates */}
                          <div>
                            <p className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground flex items-center gap-1">
                              <ShieldCheckIcon className="size-3" />{" "}
                              Certificates
                            </p>
                            {mentor.certificates.length > 0 ? (
                              <div className="space-y-2">
                                {mentor.certificates.map((cert, idx) => (
                                  <div
                                    key={idx}
                                    className="rounded-md border bg-background px-3 py-2 text-xs space-y-0.5"
                                  >
                                    <div className="flex items-center gap-2">
                                      <span className="font-medium">
                                        {cert.certificateTypeName}
                                      </span>
                                      {cert.verifiedAt ? (
                                        <span className="flex items-center gap-0.5 text-green-600">
                                          <ShieldCheckIcon className="size-3" />{" "}
                                          Verified
                                        </span>
                                      ) : (
                                        <span className="text-muted-foreground">
                                          Unverified
                                        </span>
                                      )}
                                    </div>
                                    <div className="flex flex-wrap gap-x-4 text-muted-foreground">
                                      {cert.certificateNumber && (
                                        <span>
                                          No. {cert.certificateNumber}
                                        </span>
                                      )}
                                      {cert.issuedBy && (
                                        <span>Issued by: {cert.issuedBy}</span>
                                      )}
                                      <span>Issued: {cert.issuedAt}</span>
                                      {cert.expiresAt && (
                                        <span>Expires: {cert.expiresAt}</span>
                                      )}
                                    </div>
                                    {cert.fileUrl && (
                                      <a
                                        href={cert.fileUrl}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="text-primary underline-offset-2 hover:underline"
                                        onClick={(e) => e.stopPropagation()}
                                      >
                                        View file
                                      </a>
                                    )}
                                  </div>
                                ))}
                              </div>
                            ) : (
                              <p className="text-xs text-muted-foreground">
                                No certificates on file.
                              </p>
                            )}
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

      <AlertDialog
        open={bulkAction !== null}
        onOpenChange={(open) => {
          if (!open) setBulkAction(null);
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {bulkAction?.action === "activate" ? "Activate" : "Deactivate"}{" "}
              {bulkAction?.count}{" "}
              {bulkAction?.count === 1 ? "mentor" : "mentors"}?
            </AlertDialogTitle>
            <AlertDialogDescription>
              {bulkAction?.action === "activate"
                ? "The selected mentors will be able to sign in again."
                : "The selected mentors will no longer be able to sign in. You can reactivate them at any time."}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={bulkUpdateUserStatus.isPending}>
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              variant={
                bulkAction?.action === "activate" ? "default" : "destructive"
              }
              disabled={bulkUpdateUserStatus.isPending}
              onClick={(event) => {
                event.preventDefault();
                void handleBulkStatusConfirm();
              }}
            >
              {bulkAction?.action === "activate" ? "Activate" : "Deactivate"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <BulkReplaceDialog
        open={bulkDialogOpen}
        onOpenChange={setBulkDialogOpen}
        inactiveGroups={inactiveGroups}
        mentors={mentorListItems}
        onConfirm={handleBulkConfirm}
        isPending={confirmAssignments.isPending}
      />

      <MentorImportSheet
        open={bulkImportOpen}
        onOpenChange={setBulkImportOpen}
      />
    </div>
  );
}
