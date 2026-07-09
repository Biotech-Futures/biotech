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
import { useCreateGroup, useQueryGroup, useQueryGroups } from "@/query/group";
import {
  MAX_PAGE_SIZE,
  MIN_PAGE_SIZE,
} from "@/components/user/PageSizeSelect";
import type { Group, MentorStatusFilter } from "@/type/group";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { PlusIcon } from "lucide-react";
import { toast } from "sonner";

const DEFAULT_PAGE_SIZE = 25;

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
  const createGroup = useCreateGroup();

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
  const totalPages = Math.max(1, Math.ceil((data?.data.total ?? 0) / pageSize));

  const updateFilters = (
    filters: Partial<{
      searchName: string;
      searchGroup: string;
      mentorStatus: MentorStatusFilter;
    }>,
  ) => {
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
