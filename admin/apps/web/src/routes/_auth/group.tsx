// Group Management Panel

import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useState, useEffect } from "react";
import {
  GroupFilters,
  GroupTable,
  GroupDetailDrawer,
  GroupMessagesDialog,
  createColumns,
} from "@/components/group";
import { useQueryGroup, useQueryGroups } from "@/query/group";
import { useQueryTracks } from "@/query/student";
import type { Group, MentorStatusFilter, Track } from "@/type/group";

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

  // Drawer state
  const [selectedGroup, setSelectedGroup] = useState<Group | null>(null);
  const [messageGroup, setMessageGroup] = useState<Group | null>(null);
  const [messagesOpen, setMessagesOpen] = useState(false);
  const [sheetOpen, setSheetOpen] = useState(false);

  // Query with pagination and filters
  const { data, isPending } = useQueryGroups({
    page,
    searchName,
    searchGroup,
    track,
    mentorStatus,
  });
  const { data: tracksData, isPending: isLoadingTracks } = useQueryTracks();

  const { data: groupById, isPending: isGroupByIdPending } = useQueryGroup(
    groupId ?? "",
  );

  const groups = data?.data.items ?? [];
  const totalPages = Math.ceil(
    (data?.data.total ?? 0) / (data?.data.limit ?? 10),
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
    setSheetOpen(true);
  }, [groupId, groupById?.data]);

  const handleDrawerOpenChange = (open: boolean) => {
    setSheetOpen(open);

    if (!open && groupId) {
      navigate({
        to: "/group",
        search: (prev) => ({
          groupId: undefined,
          mentorStatus: prev.mentorStatus,
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
    setSheetOpen(true);
  };

  const handleViewMessages = (group: Group) => {
    setMessageGroup(group);
    setMessagesOpen(true);
  };

  // Columns with handlers
  const columns = createColumns({
    onViewDetail: handleViewDetail,
    onViewMessages: handleViewMessages,
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
        isPending={isPending}
      />

      {/* Detail Drawer */}
      <GroupDetailDrawer
        group={selectedGroup}
        open={sheetOpen}
        onOpenChange={handleDrawerOpenChange}
      />

      <GroupMessagesDialog
        group={messageGroup}
        open={messagesOpen}
        onOpenChange={setMessagesOpen}
      />
    </div>
  );
}
