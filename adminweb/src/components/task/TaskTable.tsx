import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import {
  ChevronLeftIcon,
  ChevronRightIcon,
  PencilIcon,
  RotateCcwIcon,
  Trash2Icon,
} from "lucide-react";
import type { Task } from "@/type/task";
import { TASK_STATUS_LABELS } from "@/type/task";
import type { UserAccount } from "@/type/user";

interface GroupOption {
  id: number;
  name: string;
}

interface TaskTableProps {
  data: Task[];
  page: number;
  totalPages: number;
  onPageChange: (page: number) => void;
  onEdit: (task: Task) => void;
  onDelete: (task: Task) => void;
  onToggle: (task: Task) => void;
  onRestore?: (task: Task) => void;
  isPending?: boolean;
  groups?: GroupOption[];
  users?: UserAccount[];
  recoveryMode?: boolean;
}

const STATUS_VARIANT: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  todo: "outline",
  in_progress: "secondary",
  done: "default",
  blocked: "destructive",
};

export function TaskTable({
  data,
  page,
  totalPages,
  onPageChange,
  onEdit,
  onDelete,
  onToggle,
  onRestore,
  isPending,
  groups = [],
  users = [],
  recoveryMode = false,
}: TaskTableProps) {
  const groupMap = new Map(groups.map((g) => [g.id, g.name]));
  const userMap = new Map(users.map((u) => [Number(u.id), u.name]));
  return (
    <div className="space-y-4">
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              {!recoveryMode ? (
                <TableHead className="w-10">Completed</TableHead>
              ) : null}
              <TableHead>Name</TableHead>
              <TableHead>Type</TableHead>
              <TableHead>Target</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Due</TableHead>
              {recoveryMode ? <TableHead>Deleted</TableHead> : null}
              <TableHead className="w-24">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isPending ? (
              <TableRow>
                <TableCell colSpan={recoveryMode ? 7 : 7} className="h-24 text-center text-muted-foreground">
                  Loading...
                </TableCell>
              </TableRow>
            ) : data.length === 0 ? (
              <TableRow>
                <TableCell colSpan={recoveryMode ? 7 : 7} className="h-24 text-center text-muted-foreground">
                  No tasks found.
                </TableCell>
              </TableRow>
            ) : (
              data.map((task) => (
                <TableRow key={task.id} className={task.completed ? "opacity-60" : ""}>
                  {!recoveryMode ? (
                    <TableCell>
                      <Checkbox
                        checked={task.completed}
                        onCheckedChange={() => onToggle(task)}
                      />
                    </TableCell>
                  ) : null}
                  <TableCell className="font-medium max-w-48 truncate">
                    {task.name}
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline" className="capitalize">
                      {task.task_type}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {task.task_type === "group"
                      ? (task.group != null ? (groupMap.get(task.group) ?? `Group #${task.group}`) : "—")
                      : (task.assigned_user != null ? (userMap.get(task.assigned_user) ?? `User #${task.assigned_user}`) : "—")}
                  </TableCell>
                  <TableCell>
                    <Badge variant={STATUS_VARIANT[task.status] ?? "outline"}>
                      {TASK_STATUS_LABELS[task.status] ?? task.status}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-sm">
                    {task.due_date
                      ? new Date(task.due_date).toLocaleDateString()
                      : "—"}
                  </TableCell>
                  {recoveryMode ? (
                    <TableCell className="text-sm">
                      {task.deleted_at
                        ? new Date(task.deleted_at).toLocaleString()
                        : "—"}
                    </TableCell>
                  ) : null}
                  <TableCell>
                    <div className="flex gap-1">
                      {recoveryMode ? (
                        task.task_type === "group" ? (
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => onRestore?.(task)}
                          >
                            <RotateCcwIcon className="size-4" />
                            Restore
                          </Button>
                        ) : (
                          <span className="text-sm text-muted-foreground">—</span>
                        )
                      ) : (
                        <>
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => onEdit(task)}
                          >
                            <PencilIcon className="size-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => onDelete(task)}
                          >
                            <Trash2Icon className="size-4 text-destructive" />
                          </Button>
                        </>
                      )}
                    </div>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          Page {page} of {totalPages}
        </p>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => onPageChange(page - 1)}
            disabled={page <= 1 || isPending}
          >
            <ChevronLeftIcon className="size-4" />
            Previous
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => onPageChange(page + 1)}
            disabled={page >= totalPages || isPending}
          >
            Next
            <ChevronRightIcon className="size-4" />
          </Button>
        </div>
      </div>
    </div>
  );
}
