import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { PlusIcon } from "lucide-react";
import {
  useQueryStates,
  useBulkUpdateUserStatus,
  useBulkDeleteUsers,
  useCreateUser,
  useDeleteUser,
  useQueryUsers,
  useUpdateUser,
  useUpdateUserStatus,
  type BulkStatusFilters,
} from "@/query/user";
import {
  MAX_PAGE_SIZE,
  MIN_PAGE_SIZE,
} from "@/components/user/PageSizeSelect";
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
  USER_ROLES,
  type UserAccount,
  type UserFormValues,
  type UserRole,
} from "@/type/user";
import { UserFilters } from "@/components/user/UserFilters";
import { UserBulkActionsBar } from "@/components/user/UserBulkActionsBar";
import { UserTable, type UserSortKey } from "@/components/user/UserTable";
import { UserEditorSheet } from "@/components/user/UserEditorSheet";
import { UserDetailSheet } from "@/components/user/UserDetailSheet";
import type { SortState } from "@/components/ui/sortable-table";
import { toast } from "sonner";

const DEFAULT_PAGE_SIZE = 25;
type UserStatusFilter = "all" | "active" | "inactive";
const SORT_OPTIONS = [
  "createdAt_desc",
  "createdAt_asc",
  "name_asc",
  "name_desc",
  "email_asc",
  "email_desc",
  "role_asc",
  "role_desc",
  "state_asc",
  "state_desc",
  "status_asc",
  "status_desc",
] as const;
type SortOption = (typeof SORT_OPTIONS)[number];
type UserSearchParams = {
  page: number;
  limit?: number;
  search?: string;
  role?: UserRole;
  state?: string;
  status?: UserStatusFilter;
  sort?: SortOption;
};
type EditableUserSearchParams = Omit<
  Partial<UserSearchParams>,
  "role" | "state"
> & {
  role?: UserRole | "all";
  state?: string | "all";
};

export const Route = createFileRoute("/_auth/people/")({
  validateSearch: (search): UserSearchParams => {
    const params: UserSearchParams = {
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

    if (typeof search.search === "string" && search.search.trim()) {
      params.search = search.search;
    }

    if (
      typeof search.role === "string" &&
      USER_ROLES.includes(search.role as UserRole)
    ) {
      params.role = search.role as UserRole;
    }

    if (typeof search.state === "string" && search.state.trim()) {
      params.state = search.state;
    }

    if (
      search.status === "active" ||
      search.status === "inactive" ||
      search.status === "all"
    ) {
      params.status = search.status;
    }

    if (
      typeof search.sort === "string" &&
      (SORT_OPTIONS as readonly string[]).includes(search.sort)
    ) {
      params.sort = search.sort as SortOption;
    }

    return params;
  },
  component: UserManagementPage,
});

function UserManagementPage() {
  const navigate = useNavigate();
  const searchParams = Route.useSearch();
  const search = searchParams.search ?? "";
  const role = searchParams.role ?? "all";
  const stateFilter = searchParams.state ?? "all";
  const status = searchParams.status ?? "all";
  const sort = searchParams.sort ?? "createdAt_desc";
  const page = searchParams.page;
  const pageSize = searchParams.limit ?? DEFAULT_PAGE_SIZE;
  const [sortBy, sortOrder] = sort.split("_") as [
    "name" | "email" | "role" | "state" | "status" | "createdAt",
    "asc" | "desc",
  ];
  const tableSortState: SortState<UserSortKey> = {
    key: sortBy === "createdAt" ? "name" : sortBy,
    direction: sortOrder,
  };
  const [editorOpen, setEditorOpen] = useState(false);
  const [detailOpen, setDetailOpen] = useState(false);
  const [editorMode, setEditorMode] = useState<"create" | "edit">("create");
  const [selectedUser, setSelectedUser] = useState<UserAccount | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  // "Select all matching" mode: every row in the filtered set is selected
  // except the ids the admin explicitly unchecked (excludedIds).
  const [selectAllMatching, setSelectAllMatching] = useState(false);
  const [excludedIds, setExcludedIds] = useState<Set<string>>(new Set());
  // Snapshot the count when the dialog opens so its copy stays stable while
  // the selection is cleared and the dialog animates out.
  const [bulkAction, setBulkAction] = useState<{
    action: "activate" | "deactivate";
    count: number;
  } | null>(null);
  // Snapshot the count when the delete dialog opens so its copy stays stable.
  const [bulkDelete, setBulkDelete] = useState<{ count: number } | null>(null);

  const clearSelection = () => {
    setSelectedIds(new Set());
    setSelectAllMatching(false);
    setExcludedIds(new Set());
  };

  // Filters shared by the list query and "select all matching" bulk actions.
  const currentFilters: BulkStatusFilters = {
    search: search.trim() || undefined,
    role: role === "all" ? undefined : role,
    state: stateFilter === "all" ? undefined : stateFilter,
    active: status === "all" ? undefined : status === "active",
  };

  const { data, isPending } = useQueryUsers({
    page,
    limit: pageSize,
    ...currentFilters,
    sortBy,
    sortOrder,
  });
  const { data: statesData } = useQueryStates();
  const { data: supervisorsData } = useQueryUsers({
    page: 1,
    limit: 200,
    role: "supervisor",
  });
  const createUser = useCreateUser();
  const updateUser = useUpdateUser();
  const updateUserStatus = useUpdateUserStatus();
  const bulkUpdateUserStatus = useBulkUpdateUserStatus();
  const bulkDeleteUsers = useBulkDeleteUsers();
  const deleteUser = useDeleteUser();

  const updateFilters = (
    filters: Partial<{
      search: string;
      role: UserRole | "all";
      state: string | "all";
      status: UserStatusFilter;
      sort: SortOption;
    }>,
  ) => {
    // Filters change the matching set, so any selection (including
    // "all matching") no longer maps to what's on screen.
    clearSelection();
    void navigate({
      to: "/people",
      search: () =>
        cleanSearchParams({
          ...searchParams,
          ...filters,
          page: 1,
        }),
      replace: true,
    });
  };

  const updatePage = (nextPage: number) => {
    void navigate({
      to: "/people",
      search: () => cleanSearchParams({ ...searchParams, page: nextPage }),
      replace: true,
    });
  };

  const updatePageSize = (nextSize: number) => {
    void navigate({
      to: "/people",
      search: () =>
        cleanSearchParams({ ...searchParams, limit: nextSize, page: 1 }),
      replace: true,
    });
  };

  const pageItems = useMemo(() => data?.data?.items ?? [], [data?.data?.items]);

  // Create sends the state by name; map the selected stateId back to its name.
  const stateNameById = useMemo(() => {
    const map = new Map<number, string>();
    for (const item of statesData?.data ?? []) {
      map.set(item.id, item.stateName);
    }
    return map;
  }, [statesData]);

  const supervisorOptions = useMemo(
    () =>
      (supervisorsData?.data?.items ?? []).map((u) => ({
        id: u.id,
        name: u.name,
        email: u.email,
      })),
    [supervisorsData],
  );

  const total = data?.data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const effectiveSelectedCount = selectAllMatching
    ? Math.max(0, total - excludedIds.size)
    : selectedIds.size;

  const openCreate = () => {
    setSelectedUser(null);
    setEditorMode("create");
    setEditorOpen(true);
  };

  const openEdit = (user: UserAccount) => {
    setSelectedUser(user);
    setEditorMode("edit");
    setEditorOpen(true);
  };

  const openDetail = (user: UserAccount) => {
    setSelectedUser(user);
    setDetailOpen(true);
  };

  const handleSaveUser = async (values: UserFormValues) => {
    if (editorMode === "create") {
      try {
        const response = await createUser.mutateAsync({
          firstName: values.firstName,
          lastName: values.lastName,
          email: values.email,
          role: values.role,
          state:
            values.role === "admin"
              ? undefined
              : values.stateId != null
                ? stateNameById.get(values.stateId)
                : undefined,
          schoolName: values.role === "student" ? values.schoolName : undefined,
          supervisorSchoolName:
            values.role === "supervisor"
              ? values.supervisorSchoolName
              : undefined,
          mentorBackground:
            values.role === "mentor"
              ? values.mentorBackground || null
              : undefined,
          mentorInstitution:
            values.role === "mentor" ? values.mentorInstitution : undefined,
          mentorReason:
            values.role === "mentor" ? values.mentorReason : undefined,
          mentorMaxGroupCount:
            values.role === "mentor"
              ? (values.mentorMaxGroupCount ?? undefined)
              : undefined,
          yearLevel:
            values.role === "student"
              ? (values.yearLevel ?? undefined)
              : undefined,
          interests:
            values.role === "student" || values.role === "mentor"
              ? values.interests
              : undefined,
          supervisorEmail:
            values.role === "student" && values.supervisorEmail
              ? values.supervisorEmail
              : undefined,
          active: values.active,
        });

        if (!response.data) {
          toast.error(response.msg || "Unable to create user.");
          return;
        }

        setEditorOpen(false);
      } catch {
        toast.error("Unable to create the user right now.");
      }
      return;
    }

    if (!selectedUser) return;

    try {
      const response = await updateUser.mutateAsync({
        id: selectedUser.id,
        updates: {
          firstName: values.firstName,
          lastName: values.lastName,
          role: values.role,
          stateId: values.role === "admin" ? null : values.stateId,
          schoolName: values.role === "student" ? values.schoolName : null,
          supervisorSchoolName:
            values.role === "supervisor" ? values.supervisorSchoolName : null,
          mentorBackground:
            values.role === "mentor" ? values.mentorBackground || null : null,
          mentorInstitution:
            values.role === "mentor" ? values.mentorInstitution : null,
          mentorReason: values.role === "mentor" ? values.mentorReason : null,
          mentorMaxGroupCount:
            values.role === "mentor" ? values.mentorMaxGroupCount : null,
          yearLevel: values.role === "student" ? values.yearLevel : null,
          interests:
            values.role === "student" || values.role === "mentor"
              ? values.interests
              : [],
          supervisorEmail:
            values.role === "student" ? values.supervisorEmail : undefined,
        },
      });

      if (!response.data) {
        toast.error(response.msg || "Unable to update user.");
        return;
      }

      if (selectedUser.active !== values.active) {
        const statusResponse = await updateUserStatus.mutateAsync({
          id: selectedUser.id,
          updates: { isActive: values.active },
        });

        if (!statusResponse.data) {
          toast.error(
            statusResponse.msg || "Unable to update the account status.",
          );
          return;
        }
      }

      setEditorOpen(false);
    } catch {
      toast.error("Unable to update the user right now.");
    }
  };

  const handleToggleActive = async (user: UserAccount) => {
    try {
      const response = await updateUserStatus.mutateAsync({
        id: user.id,
        updates: { isActive: !user.active },
      });

      if (!response.data) {
        toast.error(response.msg || "Unable to update the account status.");
      }
    } catch {
      toast.error("Unable to update the account status right now.");
    }
  };

  const handleBulkStatusConfirm = async () => {
    if (!bulkAction) return;
    if (!selectAllMatching && selectedIds.size === 0) {
      setBulkAction(null);
      return;
    }

    const isActive = bulkAction.action === "activate";

    try {
      const response = selectAllMatching
        ? await bulkUpdateUserStatus.mutateAsync({
            selectAll: true,
            filters: currentFilters,
            excludeIds: [...excludedIds],
            isActive,
          })
        : await bulkUpdateUserStatus.mutateAsync({
            ids: [...selectedIds],
            isActive,
          });

      if (!response.data) {
        toast.error(response.msg || "Unable to update account statuses.");
        return;
      }

      toast.success(response.msg);
      clearSelection();
    } catch {
      toast.error("Unable to update account statuses right now.");
    } finally {
      setBulkAction(null);
    }
  };

  const handleBulkDeleteConfirm = async () => {
    const ids = [...selectedIds];
    if (ids.length === 0) {
      setBulkDelete(null);
      return;
    }
    try {
      const response = await bulkDeleteUsers.mutateAsync(ids);
      if (!response.data) {
        toast.error(response.msg || "Unable to delete users.");
        return;
      }
      toast.success(response.msg);
      clearSelection();
    } catch {
      toast.error("Unable to delete users right now.");
    } finally {
      setBulkDelete(null);
    }
  };

  const handleDeleteUser = async (user: UserAccount) => {
    const confirmed = window.confirm(
      `Delete user "${user.name}"? This cannot be undone.`,
    );
    if (!confirmed) return;

    try {
      const response = await deleteUser.mutateAsync(user.id);
      if (!response.data && response.msg !== "User deleted successfully") {
        toast.error(response.msg || "Unable to delete user.");
        return;
      }

      if (selectedUser?.id === user.id) {
        setDetailOpen(false);
        setEditorOpen(false);
        setSelectedUser(null);
      }
    } catch {
      toast.error("Unable to delete the user right now.");
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap gap-2 justify-end w-full">
        <Button onClick={openCreate}>
          <PlusIcon />
          Add User
        </Button>
      </div>

      <div>
        <UserFilters
          search={search}
          onSearchChange={(value) => updateFilters({ search: value })}
          role={role}
          onRoleChange={(value) => updateFilters({ role: value })}
          state={stateFilter}
          onStateChange={(value) => updateFilters({ state: value })}
          states={statesData?.data ?? []}
          status={status}
          onStatusChange={(value) => updateFilters({ status: value })}
        />
      </div>

      {effectiveSelectedCount > 0 && (
        <UserBulkActionsBar
          count={effectiveSelectedCount}
          onActivate={() =>
            setBulkAction({
              action: "activate",
              count: effectiveSelectedCount,
            })
          }
          onDeactivate={() =>
            setBulkAction({
              action: "deactivate",
              count: effectiveSelectedCount,
            })
          }
          // Permanent delete only for an explicit selection — never "all matching".
          onDelete={
            selectAllMatching
              ? undefined
              : () => setBulkDelete({ count: selectedIds.size })
          }
          onClear={clearSelection}
          isPending={bulkUpdateUserStatus.isPending || bulkDeleteUsers.isPending}
        />
      )}

      <UserTable
        data={pageItems}
        page={page}
        totalPages={totalPages}
        pageSize={pageSize}
        onPageChange={updatePage}
        onPageSizeChange={updatePageSize}
        sortState={tableSortState}
        onSortChange={(nextSort) =>
          updateFilters({
            sort: `${nextSort.key}_${nextSort.direction}` as SortOption,
          })
        }
        onView={openDetail}
        onEdit={openEdit}
        onToggleActive={handleToggleActive}
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
        isPending={
          isPending ||
          createUser.isPending ||
          updateUser.isPending ||
          updateUserStatus.isPending ||
          bulkUpdateUserStatus.isPending ||
          deleteUser.isPending
        }
      />

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
              {bulkAction?.count} {bulkAction?.count === 1 ? "user" : "users"}?
            </AlertDialogTitle>
            <AlertDialogDescription>
              {bulkAction?.action === "activate"
                ? "The selected users will be able to sign in again."
                : "The selected users will no longer be able to sign in. You can reactivate them at any time."}
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

      <AlertDialog
        open={bulkDelete !== null}
        onOpenChange={(open) => {
          if (!open) setBulkDelete(null);
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              Delete {bulkDelete?.count}{" "}
              {bulkDelete?.count === 1 ? "user" : "users"}?
            </AlertDialogTitle>
            <AlertDialogDescription>
              This permanently removes the selected{" "}
              {bulkDelete?.count === 1 ? "account" : "accounts"} and all related
              data. This cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={bulkDeleteUsers.isPending}>
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              disabled={bulkDeleteUsers.isPending}
              onClick={(event) => {
                event.preventDefault();
                void handleBulkDeleteConfirm();
              }}
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <UserEditorSheet
        open={editorOpen}
        onOpenChange={setEditorOpen}
        mode={editorMode}
        user={selectedUser}
        states={statesData?.data ?? []}
        supervisors={supervisorOptions}
        onSubmit={handleSaveUser}
        onDelete={handleDeleteUser}
        isPending={
          createUser.isPending ||
          updateUser.isPending ||
          updateUserStatus.isPending ||
          deleteUser.isPending
        }
        isDeleting={deleteUser.isPending}
      />

      <UserDetailSheet
        open={detailOpen}
        onOpenChange={setDetailOpen}
        user={selectedUser}
      />
    </div>
  );
}

function cleanSearchParams(params: EditableUserSearchParams): UserSearchParams {
  const next: UserSearchParams = {
    page: params.page && params.page > 1 ? params.page : 1,
  };
  const search = params.search?.trim();

  if (params.limit && params.limit !== DEFAULT_PAGE_SIZE) {
    next.limit = params.limit;
  }
  if (search) next.search = search;
  if (params.role && params.role !== "all") next.role = params.role;
  if (params.state && params.state !== "all") next.state = params.state;
  if (params.status && params.status !== "all") next.status = params.status;
  if (params.sort && params.sort !== "createdAt_desc") next.sort = params.sort;

  return next;
}
