import { createFileRoute } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PlusIcon } from "lucide-react";
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
  useQueryCountries,
  useQueryStates,
  useQueryUsers,
  useCreateUser,
  useUpdateUser,
  useUpdateUserStatus,
  useBulkUpdateUserStatus,
  useBulkDeleteUsers,
  type BulkStatusFilters,
} from "@/query/user";
import { UserTable, type UserSortKey } from "@/components/user/UserTable";
import { UserBulkActionsBar } from "@/components/user/UserBulkActionsBar";
import { UserEditorSheet } from "@/components/user/UserEditorSheet";
import { UserDetailSheet } from "@/components/user/UserDetailSheet";
import type { SortState } from "@/components/ui/sortable-table";
import type { UserAccount, UserFormValues } from "@/type/user";
import { toast } from "sonner";

const DEFAULT_PAGE_SIZE = 25;

export const Route = createFileRoute("/_auth/people/supervisors")({
  component: SupervisorsPage,
});

function SupervisorsPage() {
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE);
  const [sortState, setSortState] = useState<SortState<UserSortKey>>({
    key: "name",
    direction: "asc",
  });
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  // "Select all matching" mode: every supervisor matching the current search is
  // selected except the ids the admin explicitly unchecked (excludedIds).
  const [selectAllMatching, setSelectAllMatching] = useState(false);
  const [excludedIds, setExcludedIds] = useState<Set<string>>(new Set());
  const [editorOpen, setEditorOpen] = useState(false);
  const [detailOpen, setDetailOpen] = useState(false);
  const [editorMode, setEditorMode] = useState<"create" | "edit">("create");
  const [selectedUser, setSelectedUser] = useState<UserAccount | null>(null);
  const [bulkAction, setBulkAction] = useState<{
    action: "activate" | "deactivate";
    count: number;
  } | null>(null);
  const [bulkDelete, setBulkDelete] = useState<{
    count: number;
    selectAll: boolean;
  } | null>(null);
  // Mass "select all matching" delete requires typing DELETE to confirm.
  const [deleteConfirmText, setDeleteConfirmText] = useState("");
  // Force delete also purges records that PROTECT the user (chat messages,
  // resources, workshops, match runs) — needed to remove accounts with activity.
  const [forceDelete, setForceDelete] = useState(false);

  const { data, isPending } = useQueryUsers({
    page,
    limit: pageSize,
    role: "supervisor",
    search: search.trim() || undefined,
    sortBy: sortState.key,
    sortOrder: sortState.direction,
  });
  const { data: countriesData } = useQueryCountries();
  const { data: statesData } = useQueryStates();
  const createUser = useCreateUser();
  const updateUser = useUpdateUser();
  const updateUserStatus = useUpdateUserStatus();
  const bulkUpdateUserStatus = useBulkUpdateUserStatus();
  const bulkDeleteUsers = useBulkDeleteUsers();

  const pageItems = useMemo(() => data?.data?.items ?? [], [data?.data?.items]);
  const total = data?.data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  const countryNameById = useMemo(() => {
    const map = new Map<number, string>();
    for (const item of countriesData?.data ?? [])
      map.set(item.id, item.countryName);
    return map;
  }, [countriesData]);

  const stateNameById = useMemo(() => {
    const map = new Map<number, string>();
    for (const item of statesData?.data ?? []) map.set(item.id, item.stateName);
    return map;
  }, [statesData]);

  const clearSelection = () => {
    setSelectedIds(new Set());
    setSelectAllMatching(false);
    setExcludedIds(new Set());
  };

  // Filters shared by the list query and "select all matching" bulk actions.
  const currentFilters: BulkStatusFilters = {
    search: search.trim() || undefined,
    role: "supervisor",
  };

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
    const isAdmin = values.role === "admin";
    const countryName =
      isAdmin || values.countryId == null
        ? undefined
        : countryNameById.get(values.countryId);
    const stateName =
      isAdmin || values.stateId == null
        ? undefined
        : stateNameById.get(values.stateId);
    try {
      if (editorMode === "create") {
        const response = await createUser.mutateAsync({
          firstName: values.firstName,
          lastName: values.lastName,
          email: values.email,
          role: values.role,
          country: countryName,
          state: stateName,
          supervisorSchoolName:
            values.role === "supervisor" ? values.supervisorSchoolName : undefined,
          active: values.active,
        });
        if (!response.data) {
          toast.error(response.msg || "Unable to create supervisor.");
          return;
        }
        setEditorOpen(false);
        return;
      }

      if (!selectedUser) return;
      const response = await updateUser.mutateAsync({
        id: selectedUser.id,
        updates: {
          firstName: values.firstName,
          lastName: values.lastName,
          role: values.role,
          countryId: isAdmin ? null : values.countryId,
          stateId: isAdmin ? null : values.stateId,
          supervisorSchoolName:
            values.role === "supervisor" ? values.supervisorSchoolName : null,
        },
      });
      if (!response.data) {
        toast.error(response.msg || "Unable to update supervisor.");
        return;
      }
      if (selectedUser.active !== values.active) {
        await updateUserStatus.mutateAsync({
          id: selectedUser.id,
          updates: { isActive: values.active },
        });
      }
      setEditorOpen(false);
    } catch {
      toast.error("Unable to save the supervisor right now.");
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
    if (!selectAllMatching && selectedIds.size === 0) {
      setBulkDelete(null);
      return;
    }
    try {
      const response = await bulkDeleteUsers.mutateAsync(
        selectAllMatching
          ? {
              selectAll: true,
              filters: currentFilters,
              excludeIds: [...excludedIds],
              expectedCount: effectiveSelectedCount,
              force: forceDelete,
            }
          : { ids: [...selectedIds], force: forceDelete },
      );
      if (!response.data) {
        toast.error(response.msg || "Unable to delete supervisors.");
        return;
      }
      toast.success(response.msg);
      clearSelection();
    } catch {
      toast.error("Unable to delete supervisors right now.");
    } finally {
      setBulkDelete(null);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <Input
          placeholder="Search supervisors..."
          value={search}
          onChange={(event) => {
            setSearch(event.target.value);
            setPage(1);
            // Search redefines the matching set, so any selection (including
            // "all matching") no longer maps to what's on screen.
            clearSelection();
          }}
          className="max-w-sm"
        />
        <Button onClick={openCreate}>
          <PlusIcon />
          Add Supervisor
        </Button>
      </div>

      {effectiveSelectedCount > 0 && (
        <UserBulkActionsBar
          count={effectiveSelectedCount}
          noun="supervisor"
          onActivate={() =>
            setBulkAction({ action: "activate", count: effectiveSelectedCount })
          }
          onDeactivate={() =>
            setBulkAction({
              action: "deactivate",
              count: effectiveSelectedCount,
            })
          }
          onDelete={() => {
            setDeleteConfirmText("");
            setForceDelete(false);
            setBulkDelete({
              count: effectiveSelectedCount,
              selectAll: selectAllMatching,
            });
          }}
          onClear={clearSelection}
          isPending={bulkUpdateUserStatus.isPending || bulkDeleteUsers.isPending}
        />
      )}

      <UserTable
        data={pageItems}
        page={page}
        totalPages={totalPages}
        pageSize={pageSize}
        onPageChange={setPage}
        onPageSizeChange={(size) => {
          setPageSize(size);
          setPage(1);
        }}
        onView={openDetail}
        onEdit={openEdit}
        onToggleActive={handleToggleActive}
        sortState={sortState}
        onSortChange={(next) => {
          setSortState(next);
          setPage(1);
        }}
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
        isPending={isPending}
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
              {bulkAction?.count}{" "}
              {bulkAction?.count === 1 ? "supervisor" : "supervisors"}?
            </AlertDialogTitle>
            <AlertDialogDescription>
              {bulkAction?.action === "activate"
                ? "The selected supervisors will be able to sign in again."
                : "The selected supervisors will no longer be able to sign in. You can reactivate them at any time."}
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
              {bulkDelete?.count === 1 ? "supervisor" : "supervisors"}?
            </AlertDialogTitle>
            <AlertDialogDescription>
              This permanently removes the selected{" "}
              {bulkDelete?.count === 1 ? "account" : "accounts"} and all related
              data. This cannot be undone.
              {bulkDelete?.selectAll ? (
                <>
                  {" "}
                  Every supervisor matching the current search will be deleted;
                  admin accounts are protected and skipped.
                </>
              ) : null}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <div className="space-y-3">
            <label
              htmlFor="bulk-delete-supervisor-force"
              className="flex items-start gap-2 text-sm"
            >
              <input
                id="bulk-delete-supervisor-force"
                type="checkbox"
                className="mt-0.5 size-4"
                checked={forceDelete}
                onChange={(event) => setForceDelete(event.target.checked)}
              />
              <span>
                Force delete — also permanently delete each supervisor's chat
                messages, uploaded resources, workshops, and match runs. Required
                to remove accounts that have any activity.
              </span>
            </label>
            {forceDelete ? (
              <p className="text-sm font-medium text-destructive">
                This destroys their content for everyone, not just the account,
                and cannot be undone.
              </p>
            ) : null}
            {bulkDelete?.selectAll || forceDelete ? (
              <div className="space-y-1.5">
                <Label htmlFor="bulk-delete-supervisor-confirm">
                  Type <span className="font-semibold">DELETE</span> to confirm
                </Label>
                <Input
                  id="bulk-delete-supervisor-confirm"
                  autoComplete="off"
                  value={deleteConfirmText}
                  onChange={(event) => setDeleteConfirmText(event.target.value)}
                  placeholder="DELETE"
                />
              </div>
            ) : null}
          </div>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={bulkDeleteUsers.isPending}>
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              disabled={
                bulkDeleteUsers.isPending ||
                ((bulkDelete?.selectAll === true || forceDelete) &&
                  deleteConfirmText !== "DELETE")
              }
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
        countries={countriesData?.data ?? []}
        states={statesData?.data ?? []}
        defaultRole="supervisor"
        onSubmit={handleSaveUser}
        isPending={
          createUser.isPending ||
          updateUser.isPending ||
          updateUserStatus.isPending
        }
      />

      <UserDetailSheet
        open={detailOpen}
        onOpenChange={setDetailOpen}
        user={selectedUser}
      />
    </div>
  );
}
