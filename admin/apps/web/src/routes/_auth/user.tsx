import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PlusIcon, UploadIcon } from "lucide-react";
import {
  useQueryTracks,
  useBulkCreateUsers,
  useCreateUser,
  useDeleteUser,
  useQueryUsers,
  useUpdateUser,
  useUpdateUserStatus,
} from "@/query/user";
import {
  USER_ROLES,
  type CsvUserRow,
  type UserAccount,
  type UserFormValues,
  type UserRole,
  type UserTrack,
} from "@/type/user";
import { UserFilters } from "@/components/user/UserFilters";
import { UserTable } from "@/components/user/UserTable";
import { UserEditorSheet } from "@/components/user/UserEditorSheet";
import { UserBulkUploadSheet } from "@/components/user/UserBulkUploadSheet";
import { UserDetailSheet } from "@/components/user/UserDetailSheet";

const PAGE_SIZE = 10;
type UserStatusFilter = "all" | "active" | "inactive";
type UserSearchParams = {
  page: number;
  search?: string;
  role?: UserRole;
  track?: UserTrack;
  status?: UserStatusFilter;
};
type EditableUserSearchParams = Omit<
  Partial<UserSearchParams>,
  "role" | "track"
> & {
  role?: UserRole | "all";
  track?: UserTrack | "all";
};

export const Route = createFileRoute("/_auth/user")({
  validateSearch: (search): UserSearchParams => {
    const params: UserSearchParams = {
      page:
        typeof search.page === "number" && search.page >= 1
          ? search.page
          : typeof search.page === "string" && Number(search.page) >= 1
            ? Number(search.page)
            : 1,
    };

    if (typeof search.search === "string" && search.search.trim()) {
      params.search = search.search;
    }

    if (
      typeof search.role === "string" &&
      USER_ROLES.includes(search.role as UserRole)
    ) {
      params.role = search.role as UserRole;
    }

    if (typeof search.track === "string" && search.track.trim()) {
      params.track = search.track;
    }

    if (
      search.status === "active" ||
      search.status === "inactive" ||
      search.status === "all"
    ) {
      params.status = search.status;
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
  const track = searchParams.track ?? "all";
  const status = searchParams.status ?? "all";
  const page = searchParams.page;
  const [editorOpen, setEditorOpen] = useState(false);
  const [bulkOpen, setBulkOpen] = useState(false);
  const [detailOpen, setDetailOpen] = useState(false);
  const [editorMode, setEditorMode] = useState<"create" | "edit">("create");
  const [selectedUser, setSelectedUser] = useState<UserAccount | null>(null);

  const { data, isPending } = useQueryUsers({
    page,
    limit: PAGE_SIZE,
    search: search.trim() || undefined,
    role: role === "all" ? undefined : role,
    track: track === "all" ? undefined : track,
    active: status === "all" ? undefined : status === "active",
  });
  const { data: tracksData } = useQueryTracks();
  const createUser = useCreateUser();
  const updateUser = useUpdateUser();
  const updateUserStatus = useUpdateUserStatus();
  const deleteUser = useDeleteUser();
  const bulkCreateUsers = useBulkCreateUsers();

  const updateFilters = (
    filters: Partial<{
      search: string;
      role: UserRole | "all";
      track: UserTrack | "all";
      status: UserStatusFilter;
    }>,
  ) => {
    void navigate({
      to: "/user",
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
      to: "/user",
      search: () => cleanSearchParams({ ...searchParams, page: nextPage }),
      replace: true,
    });
  };

  const pageItems = useMemo(() => data?.data?.items ?? [], [data?.data?.items]);

  const total = data?.data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

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
          track: values.track ?? undefined,
          schoolName: values.role === "student" ? values.schoolName : undefined,
          yearLevel:
            values.role === "student"
              ? (values.yearLevel ?? undefined)
              : undefined,
          interests:
            values.role === "student" || values.role === "mentor"
              ? values.interests
              : undefined,
          joinPermissionReceived:
            values.role === "student"
              ? values.joinPermissionReceived
              : undefined,
          active: values.active,
        });

        if (!response.data) {
          window.alert(response.msg || "Unable to create user.");
          return;
        }

        setEditorOpen(false);
      } catch {
        window.alert("Unable to create the user right now.");
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
          email: values.email,
          role: values.role,
          track: values.track,
          schoolName: values.role === "student" ? values.schoolName : null,
          yearLevel: values.role === "student" ? values.yearLevel : null,
          interests:
            values.role === "student" || values.role === "mentor"
              ? values.interests
              : [],
          joinPermissionReceived:
            values.role === "student" ? values.joinPermissionReceived : false,
        },
      });

      if (!response.data) {
        window.alert(response.msg || "Unable to update user.");
        return;
      }

      if (selectedUser.active !== values.active) {
        const statusResponse = await updateUserStatus.mutateAsync({
          id: selectedUser.id,
          updates: { isActive: values.active },
        });

        if (!statusResponse.data) {
          window.alert(
            statusResponse.msg || "Unable to update the account status.",
          );
          return;
        }
      }

      setEditorOpen(false);
    } catch {
      window.alert("Unable to update the user right now.");
    }
  };

  const handleToggleActive = async (user: UserAccount) => {
    try {
      const response = await updateUserStatus.mutateAsync({
        id: user.id,
        updates: { isActive: !user.active },
      });

      if (!response.data) {
        window.alert(response.msg || "Unable to update the account status.");
      }
    } catch {
      window.alert("Unable to update the account status right now.");
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
        window.alert(response.msg || "Unable to delete user.");
        return;
      }

      if (selectedUser?.id === user.id) {
        setDetailOpen(false);
        setEditorOpen(false);
        setSelectedUser(null);
      }
    } catch {
      window.alert("Unable to delete the user right now.");
    }
  };

  const handleImportUsers = async (rows: CsvUserRow[]) => {
    try {
      const response = await bulkCreateUsers.mutateAsync({
        users: rows.map((row) => ({
          firstName: row.firstName,
          lastName: row.lastName,
          email: row.email,
          role: row.role,
          track: row.track ?? undefined,
          schoolName: row.role === "student" ? row.schoolName : undefined,
          yearLevel:
            row.role === "student" ? (row.yearLevel ?? undefined) : undefined,
          interests:
            row.role === "student" || row.role === "mentor"
              ? row.interests
              : undefined,
          joinPermissionReceived:
            row.role === "student" ? row.joinPermissionReceived : undefined,
          active: row.active,
        })),
      });

      const createdCount = response.data?.created?.length ?? 0;
      const skippedCount = response.data?.skipped?.length ?? 0;

      if (!createdCount && skippedCount) {
        window.alert(response.msg || "No users were imported.");
        return;
      }

      window.alert(response.msg || `Imported ${createdCount} users.`);
      setBulkOpen(false);
    } catch {
      window.alert("Bulk upload failed.");
    }
  };

  return (
    <div className="p-4 space-y-6">
      <div className="flex flex-wrap gap-2 justify-end w-full">
        <Button variant="outline" onClick={() => setBulkOpen(true)}>
          <UploadIcon />
          Bulk Upload CSV
        </Button>
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
          track={track}
          onTrackChange={(value) => updateFilters({ track: value })}
          tracks={tracksData?.data ?? []}
          status={status}
          onStatusChange={(value) => updateFilters({ status: value })}
        />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>User Directory</CardTitle>
        </CardHeader>
        <CardContent>
          <UserTable
            data={pageItems}
            page={page}
            totalPages={totalPages}
            onPageChange={updatePage}
            onView={openDetail}
            onEdit={openEdit}
            onToggleActive={handleToggleActive}
            isPending={
              isPending ||
              createUser.isPending ||
              updateUser.isPending ||
              updateUserStatus.isPending ||
              deleteUser.isPending ||
              bulkCreateUsers.isPending
            }
          />
        </CardContent>
      </Card>

      <UserEditorSheet
        open={editorOpen}
        onOpenChange={setEditorOpen}
        mode={editorMode}
        user={selectedUser}
        tracks={tracksData?.data ?? []}
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

      <UserBulkUploadSheet
        open={bulkOpen}
        onOpenChange={setBulkOpen}
        onImport={handleImportUsers}
        isPending={bulkCreateUsers.isPending}
      />
    </div>
  );
}

function cleanSearchParams(params: EditableUserSearchParams): UserSearchParams {
  const next: UserSearchParams = {
    page: params.page && params.page > 1 ? params.page : 1,
  };
  const search = params.search?.trim();

  if (search) next.search = search;
  if (params.role && params.role !== "all") next.role = params.role;
  if (params.track && params.track !== "all") next.track = params.track;
  if (params.status && params.status !== "all") next.status = params.status;

  return next;
}
