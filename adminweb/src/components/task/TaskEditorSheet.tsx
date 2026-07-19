import { useEffect } from "react";
import { useForm, Controller } from "react-hook-form";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { TASK_STATUSES, TASK_STATUS_LABELS } from "@/type/task";
import type {
  AssignableRole,
  Task,
  TaskCreateValues,
  TaskUpdateValues,
} from "@/type/task";
import { useQueryRoles } from "@/query/event";
import { useRoleRecipientCount } from "@/query/task";
import type { UserAccount } from "@/type/user";

interface GroupOption {
  id: number;
  name: string;
}

interface TaskEditorSheetProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  mode: "create" | "edit";
  task: Task | null;
  groups: GroupOption[];
  users: UserAccount[];
  onSubmit: (values: TaskCreateValues | TaskUpdateValues) => void;
  isPending?: boolean;
}

type FormValues = {
  task_type: "group" | "individual";
  group: string;
  // "user" assigns one person; "role" fans out to every holder of the role.
  assign_mode: "user" | "role";
  assigned_user: string;
  assigned_role: string;
  name: string;
  description: string;
  due_date: string;
  status: string;
};

export function TaskEditorSheet({
  open,
  onOpenChange,
  mode,
  task,
  groups,
  users,
  onSubmit,
  isPending,
}: TaskEditorSheetProps) {
  const { control, handleSubmit, reset, watch } = useForm<FormValues>({
    defaultValues: {
      task_type: "group",
      group: "",
      assign_mode: "user",
      assigned_user: "",
      assigned_role: "",
      name: "",
      description: "",
      due_date: "",
      status: "todo",
    },
  });

  const taskType = watch("task_type");
  const assignMode = watch("assign_mode");
  const assignedRole = watch("assigned_role");

  // Same seeded Roles table the event/announcement/resource targeting reads.
  const { data: rolesData } = useQueryRoles();
  const roles = rolesData?.data ?? [];

  const { data: recipientData, isFetching: countLoading } =
    useRoleRecipientCount(assignMode === "role" ? assignedRole : "");
  const recipientCount = recipientData?.data?.count ?? null;

  useEffect(() => {
    if (!open) return;
    if (mode === "edit" && task) {
      reset({
        task_type: task.task_type,
        group: task.group != null ? String(task.group) : "",
        // Fan-out is a create-time expansion: an existing task is always a
        // single concrete assignee by the time it can be edited.
        assign_mode: "user",
        assigned_user:
          task.assigned_user != null ? String(task.assigned_user) : "",
        assigned_role: "",
        name: task.name,
        description: task.description,
        due_date: task.due_date
          ? task.due_date.substring(0, 10)
          : "",
        status: task.status,
      });
    } else {
      reset({
        task_type: "group",
        group: "",
        assign_mode: "user",
        assigned_user: "",
        assigned_role: "",
        name: "",
        description: "",
        due_date: "",
        status: "todo",
      });
    }
  }, [open, mode, task, reset]);

  const handleFormSubmit = (values: FormValues) => {
    if (mode === "create") {
      const byRole =
        values.task_type === "individual" && values.assign_mode === "role";
      // Fan-out has no bulk undo, so confirm against the resolved count rather
      // than the role label — a surprising number is the signal worth catching.
      if (byRole) {
        const count =
          recipientCount === null ? "an unknown number of" : recipientCount;
        if (
          !window.confirm(
            `Create ${count} task${recipientCount === 1 ? "" : "s"} — one for each ${values.assigned_role}? This cannot be undone in bulk.`,
          )
        ) {
          return;
        }
      }
      const payload: TaskCreateValues = {
        task_type: values.task_type,
        group: values.task_type === "group" && values.group ? Number(values.group) : null,
        // The backend rejects both being set, so only ever send one.
        assigned_user:
          values.task_type === "individual" &&
          !byRole &&
          values.assigned_user
            ? Number(values.assigned_user)
            : null,
        assigned_role:
          byRole && values.assigned_role
            ? (values.assigned_role as AssignableRole)
            : null,
        name: values.name.trim(),
        description: values.description.trim(),
        due_date: values.due_date ? `${values.due_date}T00:00:00Z` : null,
        status: values.status as TaskCreateValues["status"],
        parent: null,
      };
      onSubmit(payload);
    } else {
      const payload: TaskUpdateValues = {
        name: values.name.trim(),
        description: values.description.trim(),
        due_date: values.due_date ? `${values.due_date}T00:00:00Z` : null,
        status: values.status as TaskUpdateValues["status"],
        parent: null,
      };
      onSubmit(payload);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[92vh] overflow-y-auto sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>{mode === "create" ? "Create Task" : "Edit Task"}</DialogTitle>
        </DialogHeader>

        <form
          onSubmit={handleSubmit(handleFormSubmit)}
          className="mt-4 space-y-4 px-1"
        >
          {mode === "create" && (
            <>
              <div className="space-y-1">
                <Label>Task Type</Label>
                <Controller
                  control={control}
                  name="task_type"
                  render={({ field }) => (
                    <Select onValueChange={field.onChange} value={field.value}>
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="group">Group Task</SelectItem>
                        <SelectItem value="individual">Individual Task</SelectItem>
                      </SelectContent>
                    </Select>
                  )}
                />
              </div>

              {taskType === "group" && (
                <div className="space-y-1">
                  <Label>Group</Label>
                  <Controller
                    control={control}
                    name="group"
                    render={({ field }) => (
                      <Select onValueChange={field.onChange} value={field.value}>
                        <SelectTrigger>
                          <SelectValue placeholder="Select group" />
                        </SelectTrigger>
                        <SelectContent>
                          {groups.map((g) => (
                            <SelectItem key={g.id} value={String(g.id)}>
                              {g.name}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    )}
                  />
                </div>
              )}

              {taskType === "individual" && (
                <>
                  <div className="space-y-1">
                    <Label>Assign To</Label>
                    <Controller
                      control={control}
                      name="assign_mode"
                      render={({ field }) => (
                        <Select
                          onValueChange={field.onChange}
                          value={field.value}
                        >
                          <SelectTrigger>
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="user">A specific user</SelectItem>
                            <SelectItem value="role">
                              Everyone with a role
                            </SelectItem>
                          </SelectContent>
                        </Select>
                      )}
                    />
                  </div>

                  {assignMode === "user" ? (
                    <div className="space-y-1">
                      <Label>User</Label>
                      <Controller
                        control={control}
                        name="assigned_user"
                        render={({ field }) => (
                          <Select
                            onValueChange={field.onChange}
                            value={field.value}
                          >
                            <SelectTrigger>
                              <SelectValue placeholder="Select user" />
                            </SelectTrigger>
                            <SelectContent>
                              {users.map((u) => (
                                <SelectItem key={u.id} value={String(u.id)}>
                                  {u.name} ({u.email})
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        )}
                      />
                    </div>
                  ) : (
                    <div className="space-y-1">
                      <Label>Role</Label>
                      <Controller
                        control={control}
                        name="assigned_role"
                        // Without this the payload submits both targets null and
                        // the backend reports the misleading "requires an
                        // assigned user".
                        rules={{ required: true }}
                        render={({ field }) => (
                          <Select
                            onValueChange={field.onChange}
                            value={field.value}
                          >
                            <SelectTrigger>
                              <SelectValue placeholder="Select role" />
                            </SelectTrigger>
                            <SelectContent>
                              {roles.map((r) => (
                                <SelectItem key={r.id} value={r.roleName}>
                                  Everyone with the {r.roleName} role
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        )}
                      />
                      {assignedRole && (
                        <p className="text-sm text-muted-foreground">
                          {countLoading
                            ? "Resolving recipients..."
                            : recipientCount === null
                              ? `Creates a separate task for every ${assignedRole}.`
                              : `Creates ${recipientCount} separate task${
                                  recipientCount === 1 ? "" : "s"
                                } — one per ${assignedRole}.`}{" "}
                          People who gain the role later will not receive it,
                          and there is no bulk undo.
                        </p>
                      )}
                    </div>
                  )}
                </>
              )}
            </>
          )}

          <div className="space-y-1">
            <Label requiredMarker>Name</Label>
            <Controller
              control={control}
              name="name"
              rules={{ required: true }}
              render={({ field }) => (
                <Input {...field} placeholder="Task name" />
              )}
            />
          </div>

          <div className="space-y-1">
            <Label>Description</Label>
            <Controller
              control={control}
              name="description"
              render={({ field }) => (
                <Textarea {...field} placeholder="Optional description" rows={3} />
              )}
            />
          </div>

          <div className="space-y-1">
            <Label>Due Date</Label>
            <Controller
              control={control}
              name="due_date"
              render={({ field }) => (
                <Input {...field} type="date" />
              )}
            />
          </div>

          <div className="space-y-1">
            <Label>Status</Label>
            <Controller
              control={control}
              name="status"
              render={({ field }) => (
                <Select onValueChange={field.onChange} value={field.value}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {TASK_STATUSES.map((s) => (
                      <SelectItem key={s} value={s}>
                        {TASK_STATUS_LABELS[s]}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            />
          </div>

          <div className="pt-2 flex gap-2 justify-end">
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={isPending}>
              {isPending ? "Saving..." : "Save"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
