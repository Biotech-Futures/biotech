// Group Management Panel

import { createFileRoute } from "@tanstack/react-router";
import { useState, useEffect } from "react";
import {
  GroupFilters,
  GroupTable,
  GroupDetailDrawer,
  createColumns,
} from "@/components/group";
import { useQueryGroups } from "@/query/group";
import type { Group, Track } from "@/type/group";

export const Route = createFileRoute("/_auth/group")({
  component: GroupPage,
});

function GroupPage() {
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

  // Reset to page 1 when filters change
  useEffect(() => {
    setPage(1);
  }, [searchName, searchGroup, track]);

  const groups = data?.data.items ?? [];
  const totalPages = Math.ceil(
    (data?.data.total ?? 0) / (data?.data.limit ?? 10),
  );

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
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Group Management</h1>
          <p className="text-muted-foreground">
            View all groups, members, and assigned mentors
          </p>
        </div>
      </div>

      {/* Filters - separate search for name and group */}
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

      {/* Detail/Edit Drawer */}
      <GroupDetailDrawer
        group={selectedGroup}
        open={sheetOpen}
        onOpenChange={setSheetOpen}
        mode={sheetMode}
      />
    </div>
  );
}
