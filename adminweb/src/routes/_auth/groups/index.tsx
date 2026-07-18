// Group Management Panel

import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useState, useEffect } from "react";
import type { SortingState } from "@tanstack/react-table";
import {
  GroupFilters,
  GroupTable,
  GroupDetailModal,
  GroupMessagesDialog,
  createColumns,
} from "@/components/group";
import {
  useBulkDeleteGroups,
  useCreateGroup,
  useDeleteGroup,
  useQueryGroup,
  useQueryGroups,
  type GroupListFilters,
} from "@/query/group";
import {
  MAX_PAGE_SIZE,
  MIN_PAGE_SIZE,
} from "@/components/user/PageSizeSelect";
import type { Group, MentorStatusFilter } from "@/type/group";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { BulkActionsBar } from "@/components/ui/bulk-actions-bar";
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
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { PlusIcon, Trash2Icon } from "lucide-react";
import { toast } from "sonner";

const DEFAULT_PAGE_SIZE = 25;
// A hard group delete cascades a lot (chat history, memberships, …), so large
// selections are deleted in batches across several requests rather than one
// long-running call that could time out.
const BULK_DELETE_BATCH_SIZE = 50;
const BULK_DELETE_TOAST_ID = "bulk-delete-groups";

function chunk<T>(items: T[], size: number): T[][] {
  const batches: T[][] = [];
  for (let i = 0; i < items.length; i += size) {
    batches.push(items.slice(i, i + size));
  }
  return batches;
}

type GroupSearchParams = {
  groupId?: string;
  page: number;
  limit?: number;
  searchName?: string;
  searchGroup?: string;
  mentorStatus?: MentorStatusFilter;
};

export const Route = createFileRoute("/_auth/groups/")({
  validateSearch: (search): GroupSearchParams => {
    const params: GroupSearchParams = {
      page:
        typeof search.page === "number" && search.page >= 1
          ? search.page
          : typeof search.page === "string" && Number(search.page) >= 1
            ? Number(search.page)
            : 1,
    };

    const rawLimit =
      typeof search.limit === "number"
        ? search.limit
        : typeof search.limit === "string"
          ? Number(search.limit)
          : NaN;
    if (Number.isFinite(rawLimit) && rawLimit >= MIN_PAGE_SIZE) {
      params.limit = Math.min(MAX_PAGE_SIZE, Math.floor(rawLimit));
    }

    if (typeof search.groupId === "string") params.groupId = search.groupId;
    if (typeof search.searchName === "string" && search.searchName.trim()) {
      params.searchName = search.searchName;
    }
    if (typeof search.searchGroup === "string" && search.searchGroup.trim()) {
      params.searchGroup = search.searchGroup;
    }
    if (
      search.mentorStatus === "matched" ||
      search.mentorStatus === "unmatched"
    ) {
      params.mentorStatus = search.mentorStatus;
    }

    return params;
  },
  component: GroupPage,
});

function GroupPage() {
  const navigate = useNavigate();
  const { groupId, page, limit, searchName, searchGroup, mentorStatus } =
    Route.useSearch();
  const pageSize = limit ?? DEFAULT_PAGE_SIZE;

  // Detail modal state
  const [selectedGroup, setSelectedGroup] = useState<Group | null>(null);
  const [messageGroup, setMessageGroup] = useState<Group | null>(null);
  const [messagesOpen, setMessagesOpen] = useState(false);
  const [detailOpen, setDetailOpen] = useState(false);
  const [sorting, setSorting] = useState<SortingState>([
    { id: "createdAt", desc: true },
  ]);
  const [createOpen, setCreateOpen] = useState(false);
  const [newGroupName, setNewGroupName] = useState("");
  // Page-level bulk selection, keyed by group id.
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  // "Select all matching" mode: every row in the filtered set is selected
  // except the ids the admin explicitly unchecked (excludedIds).
  const [selectAllMatching, setSelectAllMatching] = useState(false);
  const [excludedIds, setExcludedIds] = useState<Set<string>>(new Set());
  const [deletingGroup, setDeletingGroup] = useState<Group | null>(null);
  // Snapshot the count/mode when the dialog opens so its copy stays stable while
  // the selection is cleared and the dialog animates out.
  const [bulkDelete, setBulkDelete] = useState<{
    count: number;
    selectAll: boolean;
  } | null>(null);
  // Mass "select all matching" delete requires typing DELETE to confirm.
  const [deleteConfirmText, setDeleteConfirmText] = useState("");
  // Force delete also purges the hosted workshops that PROTECT a group —
  // required to delete a group that has any workshops scheduled.
  const [forceDelete, setForceDelete] = useState(false);
  // True for the whole batched delete loop (spans several requests).
  const [isBulkDeleting, setIsBulkDeleting] = useState(false);
  const createGroup = useCreateGroup();
  const deleteGroup = useDeleteGroup();
  const bulkDeleteGroups = useBulkDeleteGroups();

  // Query with pagination and filters
  const { data, isPending } = useQueryGroups({
    page,
    limit: pageSize,
    searchName,
    searchGroup,
    mentorStatus,
    sortBy:
      sorting[0]?.id === "name" ||
      sorting[0]?.id === "members" ||
      sorting[0]?.id === "mentor"
        ? sorting[0].id
        : "createdAt",
    sortOrder: sorting[0]?.desc ? "desc" : "asc",
  });

  const { data: groupById, isPending: isGroupByIdPending } = useQueryGroup(
    groupId ?? "",
  );

  const groups = data?.data.items ?? [];
  const total = data?.data.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  const clearSelection = () => {
    setSelectedIds(new Set());
    setSelectAllMatching(false);
    setExcludedIds(new Set());
  };

  // Filters shared by the list query and "select all matching" bulk delete.
  const currentFilters: GroupListFilters = {
    searchName,
    searchGroup,
    mentorStatus,
  };

  const effectiveSelectedCount = selectAllMatching
    ? Math.max(0, total - excludedIds.size)
    : selectedIds.size;

  // A resolved request means the soft-delete succeeded (404s reject).
  const handleDeleteGroup = async () => {
    if (!deletingGroup) return;
    const { id, name } = deletingGroup;
    try {
      await deleteGroup.mutateAsync(id);
      toast.success(`Deleted "${name}".`);
      setSelectedIds((prev) => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
    } catch (error) {
      // Surface the server reason (e.g. a group blocked by a scheduled
      // workshop) instead of a generic failure.
      const serverMsg = (
        error as { response?: { data?: { msg?: string } } }
      )?.response?.data?.msg;
      toast.error(serverMsg || "Unable to delete the group right now.");
    } finally {
      setDeletingGroup(null);
    }
  };

  const handleBulkDelete = async () => {
    if (!selectAllMatching && selectedIds.size === 0) {
      setBulkDelete(null);
      return;
    }

    setIsBulkDeleting(true);
    toast.loading("Deleting groups…", { id: BULK_DELETE_TOAST_ID });
    let deleted = 0;
    let failed = 0;

    try {
      if (selectAllMatching) {
        // Drain the matching set batch by batch. Rows that fail this call (e.g.
        // protected without force) are re-queued into excludeIds so each request
        // resolves fresh work and the loop terminates.
        const excluded = new Set(excludedIds);
        for (;;) {
          const res = await bulkDeleteGroups.mutateAsync({
            selectAll: true,
            filters: currentFilters,
            excludeIds: [...excluded],
            // The guard must shrink with each batch: we've already handled
            // `deleted + failed` of the reviewed set, so anything beyond the
            // remainder is a group created after review — refuse to sweep it in.
            expectedCount: effectiveSelectedCount - deleted - failed,
            force: forceDelete,
            limit: BULK_DELETE_BATCH_SIZE,
          });
          deleted += res.data?.deletedIds.length ?? 0;
          failed += res.data?.failedIds.length ?? 0;
          res.data?.failedIds.forEach((id) => excluded.add(String(id)));
          const attempted =
            (res.data?.deletedIds.length ?? 0) +
            (res.data?.failedIds.length ?? 0);
          toast.loading(`Deleting groups… ${deleted} done`, {
            id: BULK_DELETE_TOAST_ID,
          });
          if (attempted === 0) break;
        }
      } else {
        for (const batch of chunk([...selectedIds], BULK_DELETE_BATCH_SIZE)) {
          const res = await bulkDeleteGroups.mutateAsync({
            groupIds: batch,
            force: forceDelete,
          });
          deleted += res.data?.deletedIds.length ?? 0;
          failed += res.data?.failedIds.length ?? 0;
          toast.loading(`Deleting groups… ${deleted} done`, {
            id: BULK_DELETE_TOAST_ID,
          });
        }
      }

      if (failed > 0) {
        toast.warning(
          `Deleted ${deleted} group${deleted === 1 ? "" : "s"}; ${failed} could not be deleted (in use by a workshop — use Force delete).`,
          { id: BULK_DELETE_TOAST_ID },
        );
      } else {
        toast.success(`Deleted ${deleted} group${deleted === 1 ? "" : "s"}.`, {
          id: BULK_DELETE_TOAST_ID,
        });
      }
    } catch {
      // A 400 (e.g. the matching set grew past the reviewed count) or network
      // error rejects the request; earlier batches already committed.
      toast.error(
        deleted > 0
          ? `Deleted ${deleted} group${deleted === 1 ? "" : "s"}, then stopped. Refresh and retry.`
          : "Unable to delete groups right now.",
        { id: BULK_DELETE_TOAST_ID },
      );
    } finally {
      setIsBulkDeleting(false);
      setBulkDelete(null);
      clearSelection();
    }
  };

  const updateFilters = (
    filters: Partial<{
      searchName: string;
      searchGroup: string;
      mentorStatus: MentorStatusFilter;
    }>,
  ) => {
    // Filters change the matching set, so any selection (including
    // "all matching") no longer maps to what's on screen.
    clearSelection();
    void navigate({
      to: "/groups",
      search: (prev) => ({
        ...prev,
        ...filters,
        page: 1,
      }),
      replace: true,
    });
  };

  const handlePageChange = (nextPage: number) => {
    void navigate({
      to: "/groups",
      search: (prev) => ({ ...prev, page: nextPage }),
      replace: true,
    });
  };

  const handlePageSizeChange = (nextSize: number) => {
    void navigate({
      to: "/groups",
      search: (prev) => ({
        ...prev,
        limit: nextSize === DEFAULT_PAGE_SIZE ? undefined : nextSize,
        page: 1,
      }),
      replace: true,
    });
  };

  useEffect(() => {
    if (!groupId) return;
    if (!groupById?.data) return;

    setSelectedGroup(groupById.data);
    setDetailOpen(true);
  }, [groupId, groupById?.data]);

  const handleDetailOpenChange = (open: boolean) => {
    setDetailOpen(open);

    if (!open && groupId) {
      navigate({
        to: "/groups",
        search: (prev) => ({
          ...prev,
          page: prev.page ?? 1,
          groupId: undefined,
        }),
        replace: true,
      });
    }
  };

  const isGroupNotFound =
    Boolean(groupId) && !isGroupByIdPending && groupById?.data === null;

  // Handlers
  const handleViewDetail = (group: Group) => {
    setSelectedGroup(group);
    setDetailOpen(true);
  };

  const handleViewMessages = (group: Group) => {
    setMessageGroup(group);
    setMessagesOpen(true);
  };

  const handleCreateGroup = async () => {
    const name = newGroupName.trim();
    if (!name) return;
    try {
      const res = await createGroup.mutateAsync({ name });
      if (!res.data) {
        toast.error(res.msg || "Failed to create group.");
        return;
      }
      toast.success(res.msg || "Group created.");
      setNewGroupName("");
      setCreateOpen(false);
    } catch {
      toast.error("Failed to create group.");
    }
  };

  // Columns with handlers
  const columns = createColumns({
    onViewDetail: handleViewDetail,
    onViewMessages: handleViewMessages,
    onDelete: setDeletingGroup,
  });

  return (
    <div className="space-y-4">
      {groupId && !isGroupNotFound && (
        <div className="rounded-md border border-blue-200 bg-blue-50 px-3 py-2 text-sm text-blue-900">
          Group detail opened from student view for group id:{" "}
          <span className="font-medium">{groupId}</span>
        </div>
      )}

      {isGroupNotFound && (
        <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
          Group id <span className="font-medium">{groupId}</span> was not
          found.
        </div>
      )}

      <div className="flex items-center justify-end">
        <Button onClick={() => setCreateOpen(true)}>
          <PlusIcon className="size-4" />
          New Group
        </Button>
      </div>

      {/* Filters */}
      <GroupFilters
        searchName={searchName ?? ""}
        onSearchNameChange={(value) => {
          updateFilters({ searchName: value.trim() || undefined });
        }}
        searchGroup={searchGroup ?? ""}
        onSearchGroupChange={(value) => {
          updateFilters({ searchGroup: value.trim() || undefined });
        }}
        mentorStatus={mentorStatus}
        onMentorStatusChange={(value) => {
          updateFilters({ mentorStatus: value });
        }}
      />

      {effectiveSelectedCount > 0 && (
        <BulkActionsBar
          count={effectiveSelectedCount}
          noun="group"
          onClear={clearSelection}
          disabled={isBulkDeleting}
        >
          <Button
            variant="outline"
            size="sm"
            className="text-destructive hover:text-destructive"
            onClick={() => {
              setDeleteConfirmText("");
              setForceDelete(false);
              setBulkDelete({
                count: effectiveSelectedCount,
                selectAll: selectAllMatching,
              });
            }}
            disabled={isBulkDeleting}
          >
            <Trash2Icon />
            Delete
          </Button>
        </BulkActionsBar>
      )}

      {/* Table */}
      <GroupTable
        columns={columns}
        data={groups}
        page={page}
        totalPages={totalPages}
        onPageChange={handlePageChange}
        pageSize={pageSize}
        onPageSizeChange={handlePageSizeChange}
        sorting={sorting}
        onSortingChange={(nextSorting) => {
          setSorting(nextSorting);
          handlePageChange(1);
        }}
        manualSorting
        isPending={isPending}
        selection={{
          selectedIds,
          selectAllMatching,
          excludedIds,
          total,
          onSelectionChange: setSelectedIds,
          onExcludedChange: setExcludedIds,
          onSelectAllMatching: () => {
            setSelectedIds(new Set());
            setExcludedIds(new Set());
            setSelectAllMatching(true);
          },
          onClear: clearSelection,
        }}
      />

      <GroupDetailModal
        group={selectedGroup}
        open={detailOpen}
        onOpenChange={handleDetailOpenChange}
        onGroupChange={setSelectedGroup}
      />

      <GroupMessagesDialog
        group={messageGroup}
        open={messagesOpen}
        onOpenChange={setMessagesOpen}
      />

      <AlertDialog
        open={deletingGroup !== null}
        onOpenChange={(open) => {
          if (!open) setDeletingGroup(null);
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              Delete &ldquo;{deletingGroup?.name}&rdquo;?
            </AlertDialogTitle>
            <AlertDialogDescription>
              This permanently deletes the group and its chat history,
              memberships, and event links. Students become ungrouped and can be
              reassigned. This cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deleteGroup.isPending}>
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              disabled={deleteGroup.isPending}
              onClick={(event) => {
                event.preventDefault();
                void handleDeleteGroup();
              }}
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog
        open={bulkDelete !== null}
        onOpenChange={(open) => {
          if (!open) {
            setBulkDelete(null);
            setDeleteConfirmText("");
            setForceDelete(false);
          }
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              Delete {bulkDelete?.count}{" "}
              {bulkDelete?.count === 1 ? "group" : "groups"}?
            </AlertDialogTitle>
            <AlertDialogDescription>
              This permanently deletes the selected{" "}
              {bulkDelete?.count === 1 ? "group" : "groups"} and{" "}
              {bulkDelete?.count === 1 ? "its" : "their"} chat history,
              memberships, and event links. Students become ungrouped. This
              cannot be undone.
              {bulkDelete?.selectAll ? (
                <> Every group matching the current filters will be deleted.</>
              ) : null}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <div className="space-y-3">
            <label
              htmlFor="bulk-delete-force"
              className="flex items-start gap-2 text-sm"
            >
              <input
                id="bulk-delete-force"
                type="checkbox"
                className="mt-0.5 size-4"
                checked={forceDelete}
                onChange={(event) => setForceDelete(event.target.checked)}
              />
              <span>
                Force delete — also permanently delete any workshops scheduled
                for these groups. Required to delete a group that has workshops.
              </span>
            </label>
            {bulkDelete?.selectAll || forceDelete ? (
              <div className="space-y-1.5">
                <Label htmlFor="bulk-delete-confirm">
                  Type <span className="font-semibold">DELETE</span> to confirm
                </Label>
                <Input
                  id="bulk-delete-confirm"
                  autoComplete="off"
                  value={deleteConfirmText}
                  onChange={(event) => setDeleteConfirmText(event.target.value)}
                  placeholder="DELETE"
                />
              </div>
            ) : null}
          </div>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isBulkDeleting}>
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              disabled={
                isBulkDeleting ||
                ((bulkDelete?.selectAll === true || forceDelete) &&
                  deleteConfirmText !== "DELETE")
              }
              onClick={(event) => {
                event.preventDefault();
                void handleBulkDelete();
              }}
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <Dialog
        open={createOpen}
        onOpenChange={(open) => {
          setCreateOpen(open);
          if (!open) setNewGroupName("");
        }}
      >
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Create group</DialogTitle>
            <DialogDescription>
              Creates an empty group. Add students from the group's detail view,
              and a mentor from the matching tools.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-2">
            <Label htmlFor="new-group-name">Group name</Label>
            <Input
              id="new-group-name"
              value={newGroupName}
              onChange={(event) => setNewGroupName(event.target.value)}
              placeholder="e.g. Genomics Team A"
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  event.preventDefault();
                  void handleCreateGroup();
                }
              }}
            />
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              disabled={createGroup.isPending}
              onClick={() => setCreateOpen(false)}
            >
              Cancel
            </Button>
            <Button
              disabled={!newGroupName.trim() || createGroup.isPending}
              onClick={() => void handleCreateGroup()}
            >
              {createGroup.isPending ? "Creating..." : "Create group"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
