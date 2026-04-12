import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Drawer,
  DrawerContent,
  DrawerDescription,
  DrawerHeader,
  DrawerTitle,
} from "@/components/ui/drawer";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { createUserSchema, updateUserSchema } from "@/schema/user";
import { useCreateUser, useDeleteUser, useQueryUsers, useUpdateUser } from "@/query/user";
import { ROLES, TRACKS, type Role, type Track, type User } from "@/type/user";
import { toast } from "sonner";

export const Route = createFileRoute("/_auth/user")({
  component: UserPage,
});

type DrawerMode = "create" | "view" | "edit";

function emptyForm() {
  return {
    name: "",
    email: "",
    role: "student" as Role,
    track: "frontend" as Track | null,
    groupId: "",
  };
}

function SummaryCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-xl border bg-card p-4">
      <p className="text-sm text-muted-foreground">{label}</p>
      <p className="mt-2 text-2xl font-semibold">{value}</p>
    </div>
  );
}

function UserPage() {
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [role, setRole] = useState<Role | undefined>();
  const [track, setTrack] = useState<Track | undefined>();
  const [selectedUser, setSelectedUser] = useState<User | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [drawerMode, setDrawerMode] = useState<DrawerMode>("view");
  const [formState, setFormState] = useState(emptyForm);

  const { data, isPending } = useQueryUsers({ page, search, role, track });
  const createUser = useCreateUser();
  const updateUser = useUpdateUser();
  const deleteUser = useDeleteUser();

  useEffect(() => {
    setPage(1);
  }, [search, role, track]);

  const users = data?.data.items ?? [];
  const totalPages = Math.max(1, Math.ceil((data?.data.total ?? 0) / (data?.data.limit ?? 10)));
  const summary = useMemo(
    () => ({
      total: data?.data.total ?? 0,
      students: users.filter((user) => user.role === "student").length,
      mentors: users.filter((user) => user.role === "mentor").length,
      admins: users.filter((user) => user.role === "admin").length,
    }),
    [data?.data.total, users],
  );

  function syncForm(user: User | null, mode: DrawerMode) {
    setSelectedUser(user);
    setDrawerMode(mode);
    setFormState(
      user
        ? {
            name: user.name,
            email: user.email,
            role: user.role,
            track: user.track,
            groupId: user.groupId ?? "",
          }
        : emptyForm(),
    );
    setDrawerOpen(true);
  }

  function onSubmit() {
    const payload = {
      ...formState,
      groupId: formState.groupId.trim() || null,
      track: formState.role === "admin" ? null : formState.track,
    };

    const parser = drawerMode === "create" ? createUserSchema : updateUserSchema;
    const parsed = parser.safeParse(payload);
    if (!parsed.success) {
      toast.error(parsed.error.issues[0]?.message ?? "Please check the form.");
      return;
    }

    if (drawerMode === "create") {
      createUser.mutate(parsed.data, {
        onSuccess: (res) => {
          toast.success(res.msg);
          setDrawerOpen(false);
        },
      });
      return;
    }

    if (!selectedUser) {
      return;
    }

    updateUser.mutate(
      {
        id: selectedUser.id,
        updates: parsed.data,
      },
      {
        onSuccess: (res) => {
          toast.success(res.msg);
          setDrawerOpen(false);
        },
      },
    );
  }

  function onDelete(user: User) {
    if (!window.confirm(`Delete ${user.name}?`)) {
      return;
    }

    deleteUser.mutate(user.id, {
      onSuccess: (res) => {
        toast.success(res.msg);
        if (selectedUser?.id === user.id) {
          setDrawerOpen(false);
        }
      },
    });
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border bg-card p-4">
        <div>
          <h1 className="text-2xl font-bold">User Management</h1>
          <p className="text-muted-foreground">
            Review participants, filter by role, and demo create or edit flows.
          </p>
        </div>
        <Button onClick={() => syncForm(null, "create")}>Add Demo User</Button>
      </div>

      <div className="grid gap-3 md:grid-cols-4">
        <SummaryCard label="Total users" value={summary.total} />
        <SummaryCard label="Students on page" value={summary.students} />
        <SummaryCard label="Mentors on page" value={summary.mentors} />
        <SummaryCard label="Admins on page" value={summary.admins} />
      </div>

      <div className="flex flex-wrap gap-3 rounded-xl border bg-card p-4">
        <div className="min-w-[240px] flex-1 space-y-2">
          <Label htmlFor="user-search">Search</Label>
          <Input
            id="user-search"
            placeholder="Search by name or email"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
        </div>
        <div className="min-w-[180px] space-y-2">
          <Label>Role</Label>
          <Select
            value={role ?? "all"}
            onValueChange={(value) => setRole(value === "all" ? undefined : (value as Role))}
          >
            <SelectTrigger>
              <SelectValue placeholder="All roles" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All roles</SelectItem>
              {ROLES.map((item) => (
                <SelectItem key={item} value={item}>
                  {item}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="min-w-[180px] space-y-2">
          <Label>Track</Label>
          <Select
            value={track ?? "all"}
            onValueChange={(value) => setTrack(value === "all" ? undefined : (value as Track))}
          >
            <SelectTrigger>
              <SelectValue placeholder="All tracks" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All tracks</SelectItem>
              {TRACKS.map((item) => (
                <SelectItem key={item} value={item}>
                  {item}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      <div className="rounded-xl border bg-card">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Email</TableHead>
              <TableHead>Role</TableHead>
              <TableHead>Track</TableHead>
              <TableHead>Group</TableHead>
              <TableHead>Created</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isPending ? (
              <TableRow>
                <TableCell colSpan={7} className="h-24 text-center text-muted-foreground">
                  Loading demo users...
                </TableCell>
              </TableRow>
            ) : users.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} className="h-24 text-center text-muted-foreground">
                  No users match the current filters.
                </TableCell>
              </TableRow>
            ) : (
              users.map((user) => (
                <TableRow key={user.id}>
                  <TableCell>
                    <button className="font-medium hover:underline" onClick={() => syncForm(user, "view")}>
                      {user.name}
                    </button>
                  </TableCell>
                  <TableCell>{user.email}</TableCell>
                  <TableCell><Badge variant="outline">{user.role}</Badge></TableCell>
                  <TableCell>{user.track ?? "n/a"}</TableCell>
                  <TableCell>{user.groupName ?? "Unassigned"}</TableCell>
                  <TableCell>{new Date(user.createdAt).toLocaleDateString()}</TableCell>
                  <TableCell className="text-right">
                    <div className="flex justify-end gap-2">
                      <Button variant="outline" size="sm" onClick={() => syncForm(user, "edit")}>
                        Edit
                      </Button>
                      <Button variant="outline" size="sm" onClick={() => onDelete(user)}>
                        Delete
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>

        <div className="flex items-center justify-between border-t p-4">
          <p className="text-sm text-muted-foreground">
            Page {page} of {totalPages}
          </p>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={() => setPage((value) => value - 1)} disabled={page <= 1}>
              Previous
            </Button>
            <Button variant="outline" size="sm" onClick={() => setPage((value) => value + 1)} disabled={page >= totalPages}>
              Next
            </Button>
          </div>
        </div>
      </div>

      <Drawer open={drawerOpen} onOpenChange={setDrawerOpen} direction="right">
        <DrawerContent className="w-full sm:max-w-lg">
          <DrawerHeader>
            <DrawerTitle>
              {drawerMode === "create"
                ? "Add Demo User"
                : drawerMode === "edit"
                  ? "Edit User"
                  : selectedUser?.name ?? "User Details"}
            </DrawerTitle>
            <DrawerDescription>
              {drawerMode === "view"
                ? "Review profile details, role, and assigned group."
                : "This flow uses mock data now, but keeps the API shape for real integration later."}
            </DrawerDescription>
          </DrawerHeader>
          <div className="space-y-4 p-4">
            <div className="space-y-2">
              <Label htmlFor="drawer-name">Name</Label>
              <Input
                id="drawer-name"
                value={formState.name}
                disabled={drawerMode === "view"}
                onChange={(event) => setFormState((prev) => ({ ...prev, name: event.target.value }))}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="drawer-email">Email</Label>
              <Input
                id="drawer-email"
                value={formState.email}
                disabled={drawerMode === "view"}
                onChange={(event) => setFormState((prev) => ({ ...prev, email: event.target.value }))}
              />
            </div>
            <div className="space-y-2">
              <Label>Role</Label>
              <Select
                value={formState.role}
                disabled={drawerMode === "view"}
                onValueChange={(value) =>
                  setFormState((prev) => ({
                    ...prev,
                    role: value as Role,
                    track: value === "admin" ? null : prev.track ?? "frontend",
                  }))
                }
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {ROLES.map((item) => (
                    <SelectItem key={item} value={item}>
                      {item}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Track</Label>
              <Select
                value={formState.track ?? "none"}
                disabled={drawerMode === "view" || formState.role === "admin"}
                onValueChange={(value) =>
                  setFormState((prev) => ({
                    ...prev,
                    track: value === "none" ? null : (value as Track),
                  }))
                }
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">No track</SelectItem>
                  {TRACKS.map((item) => (
                    <SelectItem key={item} value={item}>
                      {item}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="drawer-group">Group ID</Label>
              <Input
                id="drawer-group"
                placeholder="e.g. g12"
                value={formState.groupId}
                disabled={drawerMode === "view"}
                onChange={(event) => setFormState((prev) => ({ ...prev, groupId: event.target.value }))}
              />
            </div>
            <div className="flex gap-2 pt-4">
              {drawerMode === "view" ? (
                <Button onClick={() => selectedUser && syncForm(selectedUser, "edit")}>Edit User</Button>
              ) : (
                <Button onClick={onSubmit} disabled={createUser.isPending || updateUser.isPending}>
                  {drawerMode === "create"
                    ? createUser.isPending
                      ? "Creating..."
                      : "Create User"
                    : updateUser.isPending
                      ? "Saving..."
                      : "Save Changes"}
                </Button>
              )}
              <Button variant="outline" onClick={() => setDrawerOpen(false)}>
                Close
              </Button>
            </div>
          </div>
        </DrawerContent>
      </Drawer>
    </div>
  );
}
