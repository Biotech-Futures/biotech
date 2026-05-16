// Group Management Panel

import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useState, useEffect } from "react";
import {
  GroupFilters,
  GroupTable,
  GroupDetailModal,
  GroupMessagesDialog,
  createColumns,
} from "@/components/group";
import {
  useDeleteGroup,
  useQueryGroup,
  useQueryGroups,
  useRestoreGroup,
} from "@/query/group";
import { useQueryTracks } from "@/query/student";
import type { Group, MentorStatusFilter, Track } from "@/type/group";
import { toast } from "sonner";

export const Route = createFileRoute("/_auth/group")({
  validateSearch: (
    search,
  ): {
    groupId?: string;
    page: number;
    searchName?: string;
    searchGroup?: string;
    track?: Track;
    mentorStatus?: MentorStatusFilter;
  } => {
    const params: {
      groupId?: string;
      page: number;
      searchName?: string;
      searchGroup?: string;
      track?: Track;
      mentorStatus?: MentorStatusFilter;
    } = {
      page:
        typeof search.page === "number" && search.page >= 1
          ? search.page
          : typeof search.page === "string" && Number(search.page) >= 1
            ? Number(search.page)
            : 1,
    };

    if (typeof search.groupId === "string") params.groupId = search.groupId;
    if (typeof search.searchName === "string" && search.searchName.trim()) {
      params.searchName = search.searchName;
    }
    if (typeof search.searchGroup === "string" && search.searchGroup.trim()) {
      params.searchGroup = search.searchGroup;
    }
    if (typeof search.track === "string" && search.track.trim()) {
      params.track = search.track;
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
  const { groupId, page, searchName, searchGroup, track, mentorStatus } =
    Route.useSearch();

  // Detail modal state
  const [selectedGroup, setSelectedGroup] = useState<Group | null>(null);
  const [messageGroup, setMessageGroup] = useState<Group | null>(null);
  const [messagesOpen, setMessagesOpen] = useState(false);
  const [detailOpen, setDetailOpen] = useState(false);
  const [recoveryPage, setRecoveryPage] = useState(1);

  // Query with pagination and filters
  const { data, isPending } = useQueryGroups({
    page,
    searchName,
    searchGroup,
    track,
    mentorStatus,
  });
  const { data: recoveryData, isPending: isRecoveryPending } = useQueryGroups({
    page: recoveryPage,
    searchName,
    searchGroup,
    track,
    mentorStatus,
    deleted: true,
  });
  const { data: tracksData, isPending: isLoadingTracks } = useQueryTracks();
  const restoreGroup = useRestoreGroup();
  const deleteGroup = useDeleteGroup();

  const { data: groupById, isPending: isGroupByIdPending } = useQueryGroup(
    groupId ?? "",
  );

  const groups = data?.data.items ?? [];
  const totalPages = Math.ceil(
    (data?.data.total ?? 0) / (data?.data.limit ?? 10),
  );
  const recoveryGroups = recoveryData?.data.items ?? [];
  const recoveryTotalPages = Math.max(
    1,
    Math.ceil((recoveryData?.data.total ?? 0) / (recoveryData?.data.limit ?? 10)),
  );

  const updateFilters = (
    filters: Partial<{
      searchName: string;
      searchGroup: string;
      track: Track;
      mentorStatus: MentorStatusFilter;
    }>,
  ) => {
    void navigate({
      to: "/group",
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
      to: "/group",
      search: (prev) => ({ ...prev, page: nextPage }),
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
        to: "/group",
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

  const handleRestoreGroup = async (group: Group) => {
    try {
      await restoreGroup.mutateAsync(group.id);
      toast.success(`Restored group "${group.name}".`);
    } catch {
      toast.error("Failed to restore group.");
    }
  };

  const handleDeleteGroup = async (group: Group) => {
    if (!window.confirm(`Delete group "${group.name}"?`)) return;

    try {
      await deleteGroup.mutateAsync(group.id);
      toast.success(`Deleted group "${group.name}".`);
      if (selectedGroup?.id === group.id) {
        setSelectedGroup(null);
        setDetailOpen(false);
      }
      if (messageGroup?.id === group.id) {
        setMessageGroup(null);
        setMessagesOpen(false);
      }
    } catch {
      toast.error("Failed to delete group.");
    }
  };

  // Columns with handlers
  const columns = createColumns({
    onViewDetail: handleViewDetail,
    onViewMessages: handleViewMessages,
    onDelete: handleDeleteGroup,
  });
  const recoveryColumns = createColumns({
    onRestore: handleRestoreGroup,
    recoveryMode: true,
  });

  return (
    <div className="p-4 space-y-4">
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
        track={track}
        onTrackChange={(value) => {
          updateFilters({ track: value });
        }}
        mentorStatus={mentorStatus}
        onMentorStatusChange={(value) => {
          updateFilters({ mentorStatus: value });
        }}
        tracks={tracksData?.data ?? []}
        isLoadingTracks={isLoadingTracks}
      />

      {/* Table */}
      <GroupTable
        columns={columns}
        data={groups}
        page={page}
        totalPages={totalPages}
        onPageChange={handlePageChange}
        isPending={isPending || deleteGroup.isPending}
      />

      <section className="space-y-3 rounded-md border p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h2 className="text-base font-semibold">Deleted Group Recovery</h2>
            <p className="text-sm text-muted-foreground">
              Review deleted groups and restore them when their name is available on the same track.
            </p>
          </div>
          <p className="text-sm text-muted-foreground">
            {recoveryData?.data.total ?? 0} deleted groups
          </p>
        </div>
        <GroupTable
          columns={recoveryColumns}
          data={recoveryGroups}
          page={recoveryPage}
          totalPages={recoveryTotalPages}
          onPageChange={setRecoveryPage}
          isPending={isRecoveryPending || restoreGroup.isPending}
        />
      </section>

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
    </div>
  );
}
