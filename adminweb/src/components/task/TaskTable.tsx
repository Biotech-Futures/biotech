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
import {
  ChevronLeftIcon,
  ChevronRightIcon,
  PencilIcon,
  Trash2Icon,
} from "lucide-react";
import type { Task } from "@/type/task";
import { TASK_STATUS_LABELS } from "@/type/task";
import type { UserAccount } from "@/type/user";
import { useCallback, useMemo } from "react";

interface GroupOption {
  id: number;
  name: string;
}

interface TrackOption {
  id: number;
  trackName: string;
}

interface TaskTableProps {
  data: Task[];
  page: number;
  totalPages: number;
  onPageChange: (page: number) => void;
  onEdit: (task: Task) => void;
  onDelete: (task: Task) => void;
  onToggle: (task: Task) => void;
  isPending?: boolean;
  groups?: GroupOption[];
  users?: UserAccount[];
  tracks?: TrackOption[];
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
  onPageChange,
  onEdit,
  onDelete,
  onToggle,
  isPending,
  groups = [],
  users = [],
  tracks = [],
  sortState,
  onSortChange,
}: TaskTableProps) {
  const groupMap = useMemo(() => new Map(groups.map((g) => [g.id, g.name])), [groups]);
  const userMap = useMemo(() => new Map(users.map((u) => [Number(u.id), u.name])), [users]);
  const trackMap = useMemo(() => new Map(tracks.map((t) => [t.id, t.trackName])), [tracks]);
  const getTargetLabel = useCallback(
    (task: Task) => {
      if (task.task_type === "group") {
        return task.group != null
          ? (groupMap.get(task.group) ?? `Group #${task.group}`)
          : "—";
      }
      if (task.task_type === "track") {
        return task.track != null
          ? (trackMap.get(task.track) ?? `Track #${task.track}`)
          : "—";
      }
      return task.assigned_user != null
        ? (userMap.get(task.assigned_user) ?? `User #${task.assigned_user}`)
        : "—";
    },
    [groupMap, userMap, trackMap],
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
