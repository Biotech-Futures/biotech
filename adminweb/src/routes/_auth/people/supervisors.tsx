import { createFileRoute } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
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
  useQueryStates,
  useQueryUsers,
  useCreateUser,
  useUpdateUser,
  useUpdateUserStatus,
  useBulkUpdateUserStatus,
  useBulkDeleteUsers,
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
  const [editorOpen, setEditorOpen] = useState(false);
  const [detailOpen, setDetailOpen] = useState(false);
  const [editorMode, setEditorMode] = useState<"create" | "edit">("create");
  const [selectedUser, setSelectedUser] = useState<UserAccount | null>(null);
  const [bulkAction, setBulkAction] = useState<{
    action: "activate" | "deactivate";
    count: number;
  } | null>(null);
  const [bulkDelete, setBulkDelete] = useState<{ count: number } | null>(null);

  const { data, isPending } = useQueryUsers({
    page,
    limit: pageSize,
    role: "supervisor",
    search: search.trim() || undefined,
    sortBy: sortState.key,
    sortOrder: sortState.direction,
  });
  const { data: statesData } = useQueryStates();
  const createUser = useCreateUser();
  const updateUser = useUpdateUser();
  const updateUserStatus = useUpdateUserStatus();
  const bulkUpdateUserStatus = useBulkUpdateUserStatus();
  const bulkDeleteUsers = useBulkDeleteUsers();

  const pageItems = useMemo(() => data?.data?.items ?? [], [data?.data?.items]);
  const total = data?.data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  const stateNameById = useMemo(() => {
    const map = new Map<number, string>();
    for (const item of statesData?.data ?? []) map.set(item.id, item.stateName);
    return map;
  }, [statesData]);

  const clearSelection = () => setSelectedIds(new Set());

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
    const stateName =
      values.role === "admin"
        ? undefined
        : values.stateId != null
          ? stateNameById.get(values.stateId)
          : undefined;
    try {
      if (editorMode === "create") {
        const response = await createUser.mutateAsync({
          firstName: values.firstName,
          lastName: values.lastName,
          email: values.email,
          role: values.role,
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
          stateId: values.role === "admin" ? null : values.stateId,
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
    const ids = [...selectedIds];
    if (ids.length === 0) {
      setBulkAction(null);
      return;
    }
    try {
      const response = await bulkUpdateUserStatus.mutateAsync({
        ids,
        isActive: bulkAction.action === "activate",
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
          }}
          className="max-w-sm"
        />
        <Button onClick={openCreate}>
          <PlusIcon />
          Add Supervisor
        </Button>
      </div>

      {selectedIds.size > 0 && (
        <UserBulkActionsBar
          count={selectedIds.size}
          noun="supervisor"
          onActivate={() =>
            setBulkAction({ action: "activate", count: selectedIds.size })
          }
          onDeactivate={() =>
            setBulkAction({ action: "deactivate", count: selectedIds.size })
          }
          onDelete={() => setBulkDelete({ count: selectedIds.size })}
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
          // The Supervisors tab uses explicit selection only (no "select all matching").
          selectAllMatching: false,
          excludedIds: new Set(),
          total: pageItems.length,
          onSelectionChange: setSelectedIds,
          onExcludedChange: () => {},
          onSelectAllMatching: () => {},
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
          if (!open) setBulkDelete(null);
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
