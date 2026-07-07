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
import type { Task, TaskCreateValues, TaskUpdateValues } from "@/type/task";
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
  assigned_user: string;
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
      assigned_user: "",
      name: "",
      description: "",
      due_date: "",
      status: "todo",
    },
  });

  const taskType = watch("task_type");

  useEffect(() => {
    if (!open) return;
    if (mode === "edit" && task) {
      reset({
        task_type: task.task_type,
        group: task.group != null ? String(task.group) : "",
        assigned_user:
          task.assigned_user != null ? String(task.assigned_user) : "",
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
        assigned_user: "",
        name: "",
        description: "",
        due_date: "",
        status: "todo",
      });
    }
  }, [open, mode, task, reset]);

  const handleFormSubmit = (values: FormValues) => {
    if (mode === "create") {
      const payload: TaskCreateValues = {
        task_type: values.task_type,
        group: values.task_type === "group" && values.group ? Number(values.group) : null,
        assigned_user:
          values.task_type === "individual" && values.assigned_user
            ? Number(values.assigned_user)
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
                <div className="space-y-1">
                  <Label>Assign To</Label>
                  <Controller
                    control={control}
                    name="assigned_user"
                    render={({ field }) => (
                      <Select onValueChange={field.onChange} value={field.value}>
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
