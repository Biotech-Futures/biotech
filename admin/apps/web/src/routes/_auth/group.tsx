// Group Management Panel

import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useState, useEffect } from "react";
import {
  GroupFilters,
  GroupTable,
  GroupDetailDrawer,
  createColumns,
  MatchedGroupsPanel,
  UnmatchedGroupsPanel,
} from "@/components/group";
import { useQueryGroup, useQueryGroups } from "@/query/group";
import { cn } from "@/lib/utils";
import type { Group, Track } from "@/type/group";

export const Route = createFileRoute("/_auth/group")({
  validateSearch: (search) => ({
    groupId: typeof search.groupId === "string" ? search.groupId : undefined,
  }),
  component: GroupPage,
});

function GroupPage() {
  const navigate = useNavigate();
  const { groupId } = Route.useSearch();

  // Tab state
  const [tab, setTab] = useState<"groups" | "matched" | "unmatched">("groups");

  // Filter state - separate search inputs
  const [searchName, setSearchName] = useState("");
  const [searchGroup, setSearchGroup] = useState("");
  const [track, setTrack] = useState<Track | undefined>();

  // Pagination state
  const [page, setPage] = useState(1);

  // Drawer state
  const [selectedGroup, setSelectedGroup] = useState<Group | null>(null);
  const [sheetOpen, setSheetOpen] = useState(false);
  const [sheetMode, setSheetMode] = useState<"view" | "edit">("view");

  // Query with pagination and filters
  const { data, isPending } = useQueryGroups({
    page,
    searchName,
    searchGroup,
    track,
  });

  const { data: groupById, isPending: isGroupByIdPending } = useQueryGroup(
    groupId ?? "",
  );

  // Reset to page 1 when filters change
  useEffect(() => {
    setPage(1);
  }, [searchName, searchGroup, track]);

  const groups = data?.data.items ?? [];
  const totalPages = Math.ceil(
    (data?.data.total ?? 0) / (data?.data.limit ?? 10),
  );

  useEffect(() => {
    if (!groupId) return;
    if (!groupById?.data) return;

    setSelectedGroup(groupById.data);
    setSheetMode("view");
    setSheetOpen(true);
  }, [groupId, groupById?.data]);

  const handleDrawerOpenChange = (open: boolean) => {
    setSheetOpen(open);

    if (!open && groupId) {
      navigate({
        to: "/group",
        search: () => ({ groupId: undefined }),
        replace: true,
      });
    }
  };

  const isGroupNotFound =
    Boolean(groupId) && !isGroupByIdPending && groupById?.data === null;

  // Handlers
  const handleViewDetail = (group: Group) => {
    setSelectedGroup(group);
    setSheetMode("view");
    setSheetOpen(true);
  };

  const handleEdit = (group: Group) => {
    setSelectedGroup(group);
    setSheetMode("edit");
    setSheetOpen(true);
  };

  // Columns with handlers
  const columns = createColumns({
    onViewDetail: handleViewDetail,
    onEdit: handleEdit,
  });

  return (
    <div className="p-4 space-y-4">
      {/* Tab switcher */}
      <div className="flex gap-1 rounded-lg border bg-muted p-1 w-fit">
        <button
          onClick={() => setTab("groups")}
          className={cn(
            "rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
            tab === "groups"
              ? "bg-background shadow-sm text-foreground"
              : "text-muted-foreground hover:text-foreground",
          )}
        >
          All Groups
        </button>
        <button
          onClick={() => setTab("matched")}
          className={cn(
            "rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
            tab === "matched"
              ? "bg-background shadow-sm text-foreground"
              : "text-muted-foreground hover:text-foreground",
          )}
        >
          Matched
        </button>
        <button
          onClick={() => setTab("unmatched")}
          className={cn(
            "rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
            tab === "unmatched"
              ? "bg-background shadow-sm text-foreground"
              : "text-muted-foreground hover:text-foreground",
          )}
        >
          Unmatched
        </button>
      </div>

      {tab === "groups" && (
        <>
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
            searchName={searchName}
            onSearchNameChange={setSearchName}
            searchGroup={searchGroup}
            onSearchGroupChange={setSearchGroup}
            track={track}
            onTrackChange={setTrack}
          />

          {/* Table */}
          <GroupTable
            columns={columns}
            data={groups}
            page={page}
            totalPages={totalPages}
            onPageChange={setPage}
            isPending={isPending}
          />
        </>
      )}

      {tab === "matched" && <MatchedGroupsPanel />}
      {tab === "unmatched" && <UnmatchedGroupsPanel />}

      {/* Detail/Edit Drawer (available on both tabs) */}
      <GroupDetailDrawer
        group={selectedGroup}
        open={sheetOpen}
        onOpenChange={handleDrawerOpenChange}
        mode={sheetMode}
      />
    </div>
  );
}
