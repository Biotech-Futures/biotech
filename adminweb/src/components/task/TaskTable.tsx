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
  SortableTableHead,
  type SortState,
} from "@/components/ui/sortable-table";
import { TablePaginationBar } from "@/components/ui/table-pagination";
import { PencilIcon, Trash2Icon } from "lucide-react";
import type { Task } from "@/type/task";
import { TASK_STATUS_LABELS } from "@/type/task";
import type { UserAccount } from "@/type/user";
import { useCallback, useMemo } from "react";

interface GroupOption {
  id: number;
  name: string;
}

interface TaskTableProps {
  data: Task[];
  page: number;
  totalPages: number;
  pageSize: number;
  onPageChange: (page: number) => void;
  onPageSizeChange: (size: number) => void;
  onEdit: (task: Task) => void;
  onDelete: (task: Task) => void;
  onToggle: (task: Task) => void;
  isPending?: boolean;
  groups?: GroupOption[];
  users?: UserAccount[];
  sortState: SortState<TaskSortKey>;
  onSortChange: (sortState: SortState<TaskSortKey>) => void;
}

const STATUS_VARIANT: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  todo: "outline",
  in_progress: "secondary",
  done: "default",
  blocked: "destructive",
};

export type TaskSortKey = "completed" | "name" | "type" | "target" | "status" | "due";

export function TaskTable({
  data,
  page,
  totalPages,
  pageSize,
  onPageChange,
  onPageSizeChange,
  onEdit,
  onDelete,
  onToggle,
  isPending,
  groups = [],
  users = [],
  sortState,
  onSortChange,
}: TaskTableProps) {
  const groupMap = useMemo(() => new Map(groups.map((g) => [g.id, g.name])), [groups]);
  const userMap = useMemo(() => new Map(users.map((u) => [Number(u.id), u.name])), [users]);
  const getTargetLabel = useCallback(
    (task: Task) => {
      if (task.task_type === "group") {
        return task.group != null
          ? (groupMap.get(task.group) ?? `Group #${task.group}`)
          : "—";
      }
      return task.assigned_user != null
        ? (userMap.get(task.assigned_user) ?? `User #${task.assigned_user}`)
        : "—";
    },
    [groupMap, userMap],
  );

  return (
    <div className="space-y-4">
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-10">
                <SortableTableHead
                  label="Completed"
                  sortKey="completed"
                  sortState={sortState}
                  onSortChange={onSortChange}
                />
              </TableHead>
              <TableHead>
                <SortableTableHead
                  label="Name"
                  sortKey="name"
                  sortState={sortState}
                  onSortChange={onSortChange}
                />
              </TableHead>
              <TableHead>
                <SortableTableHead
                  label="Type"
                  sortKey="type"
                  sortState={sortState}
                  onSortChange={onSortChange}
                />
              </TableHead>
              <TableHead>
                <SortableTableHead
                  label="Target"
                  sortKey="target"
                  sortState={sortState}
                  onSortChange={onSortChange}
                />
              </TableHead>
              <TableHead>
                <SortableTableHead
                  label="Status"
                  sortKey="status"
                  sortState={sortState}
                  onSortChange={onSortChange}
                />
              </TableHead>
              <TableHead>
                <SortableTableHead
                  label="Due"
                  sortKey="due"
                  sortState={sortState}
                  onSortChange={onSortChange}
                />
              </TableHead>
              <TableHead className="w-24">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isPending ? (
              <TableRow>
                <TableCell colSpan={7} className="h-24 text-center text-muted-foreground">
                  Loading...
                </TableCell>
              </TableRow>
            ) : data.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} className="h-24 text-center text-muted-foreground">
                  No tasks found.
                </TableCell>
              </TableRow>
            ) : (
              data.map((task) => (
                <TableRow key={task.id} className={task.completed ? "opacity-60" : ""}>
                  <TableCell>
                    <Checkbox
                      checked={task.completed}
                      onCheckedChange={() => onToggle(task)}
                    />
                  </TableCell>
                  <TableCell className="font-medium max-w-48 truncate">
                    {task.name}
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline" className="capitalize">
                      {task.task_type}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {getTargetLabel(task)}
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
                  <TableCell>
                    <div className="flex gap-1">
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
                    </div>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      <TablePaginationBar
        page={page}
        totalPages={totalPages}
        onPageChange={onPageChange}
        pageSize={pageSize}
        onPageSizeChange={onPageSizeChange}
        disabled={isPending}
      />
    </div>
  );
}
