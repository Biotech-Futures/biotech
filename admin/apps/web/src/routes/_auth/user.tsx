import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { PlusIcon, UploadIcon } from "lucide-react";
import {
  splitName,
  useQueryTracks,
  useBulkCreateUsers,
  useCreateUser,
  useDeleteUser,
  useQueryUsers,
  useUpdateUser,
  useUpdateUserStatus,
} from "@/query/user";
import {
  getUserStatus,
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

export const Route = createFileRoute("/_auth/user")({
  component: UserManagementPage,
});

function UserManagementPage() {
  const [search, setSearch] = useState("");
  const [role, setRole] = useState<UserRole | "all">("all");
  const [track, setTrack] = useState<UserTrack | "all">("all");
  const [status, setStatus] = useState<"all" | "active" | "inactive">("all");
  const [page, setPage] = useState(1);
  const [editorOpen, setEditorOpen] = useState(false);
  const [bulkOpen, setBulkOpen] = useState(false);
  const [detailOpen, setDetailOpen] = useState(false);
  const [editorMode, setEditorMode] = useState<"create" | "edit">("create");
  const [selectedUser, setSelectedUser] = useState<UserAccount | null>(null);

  const { data, isPending } = useQueryUsers();
  const { data: tracksData } = useQueryTracks();
  const createUser = useCreateUser();
  const updateUser = useUpdateUser();
  const updateUserStatus = useUpdateUserStatus();
  const deleteUser = useDeleteUser();
  const bulkCreateUsers = useBulkCreateUsers();

  useEffect(() => {
    setPage(1);
  }, [search, role, track, status]);

  const mergedUsers = useMemo(() => data?.data?.items ?? [], [data?.data?.items]);

  const filteredUsers = useMemo(() => {
    const query = search.trim().toLowerCase();

    return mergedUsers
      .filter((user) => {
        if (query) {
          const matches = [user.name ?? "", user.email ?? "", user.groupName ?? ""].some((value) =>
            value.toLowerCase().includes(query),
          );
          if (!matches) return false;
        }

        if (role !== "all" && user.role !== role) return false;
        if (track !== "all" && user.track !== track) return false;
        if (status !== "all" && getUserStatus(user) !== status) return false;

        return true;
      })
      .sort((left, right) => {
        if (left.active !== right.active) {
          return left.active ? -1 : 1;
        }
        return (left.name ?? "").localeCompare(right.name ?? "");
      });
  }, [mergedUsers, role, search, status, track]);

  const totalPages = Math.max(1, Math.ceil(filteredUsers.length / PAGE_SIZE));
  const pageItems = filteredUsers.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  const summary = useMemo(
    () => ({
      total: mergedUsers.length,
      active: mergedUsers.filter((user) => user.active).length,
      inactive: mergedUsers.filter((user) => !user.active).length,
      supervisors: mergedUsers.filter((user) => user.role === "supervisor").length,
    }),
    [mergedUsers],
  );

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
        const { firstName, lastName } = splitName(values.name);
        const response = await createUser.mutateAsync({
          firstName,
          lastName,
          email: values.email,
          role: values.role,
          track: values.track ?? undefined,
          schoolName: values.role === "student" ? values.schoolName : undefined,
          yearLevel: values.role === "student" ? values.yearLevel ?? undefined : undefined,
          interests: values.role === "student" ? values.interests : undefined,
          joinPermissionReceived:
            values.role === "student" ? values.joinPermissionReceived : undefined,
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
      const { firstName, lastName } = splitName(values.name);
      const response = await updateUser.mutateAsync({
        id: selectedUser.id,
        updates: {
          firstName,
          lastName,
          email: values.email,
          role: values.role,
          track: values.track,
          schoolName: values.role === "student" ? values.schoolName : null,
          yearLevel: values.role === "student" ? values.yearLevel : null,
          interests: values.role === "student" ? values.interests : [],
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
          window.alert(statusResponse.msg || "Unable to update the account status.");
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
    const confirmed = window.confirm(`Delete user "${user.name}"? This cannot be undone.`);
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
          ...splitName(row.name),
          email: row.email,
          role: row.role,
          track: row.track ?? undefined,
          schoolName: row.role === "student" ? row.schoolName : undefined,
          yearLevel: row.role === "student" ? row.yearLevel ?? undefined : undefined,
          interests: row.role === "student" ? row.interests : undefined,
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
    <div className="p-4 space-y-4">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" onClick={() => setBulkOpen(true)}>
            <UploadIcon />
            Bulk Upload CSV
          </Button>
          <Button onClick={openCreate}>
            <PlusIcon />
            Add User
          </Button>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <SummaryCard title="Total Users" value={summary.total} />
        <SummaryCard title="Active Accounts" value={summary.active} />
        <SummaryCard title="Inactive Accounts" value={summary.inactive} />
        <SummaryCard title="Supervisors" value={summary.supervisors} />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Filters</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <UserFilters
            search={search}
            onSearchChange={setSearch}
            role={role}
            onRoleChange={setRole}
            track={track}
            onTrackChange={setTrack}
            tracks={tracksData?.data ?? []}
            status={status}
            onStatusChange={setStatus}
          />

          <div className="flex flex-wrap gap-2">
            <Badge variant="outline">{filteredUsers.length} matched users</Badge>
            <Badge variant="outline">{summary.supervisors} supervisor records</Badge>
            <Badge variant="outline">{summary.inactive} inactive accounts</Badge>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>User Directory</CardTitle>
        </CardHeader>
        <CardContent>
          <UserTable
            data={pageItems}
            page={page}
            totalPages={totalPages}
            onPageChange={setPage}
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

function SummaryCard({
  title,
  value,
}: {
  title: string;
  value: number;
}) {
  return (
    <Card size="sm">
      <CardHeader>
        <p className="text-sm text-muted-foreground">{title}</p>
        <CardTitle>{value}</CardTitle>
      </CardHeader>
      <CardContent className="pt-0" />
    </Card>
  );
}
