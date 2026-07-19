import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useState, useMemo, useCallback, useEffect } from "react";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
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
import { BulkActionsBar } from "@/components/ui/bulk-actions-bar";
import { PlusIcon } from "lucide-react";
import {
  useQueryTasks,
  useCreateTask,
  useUpdateTask,
  useDeleteTask,
} from "@/query/task";
import { useQueryUsers } from "@/query/user";
import { useQuery } from "@tanstack/react-query";
import { myFetch } from "@/lib/myFetch";
import { TaskTable, type TaskSortKey } from "@/components/task/TaskTable";
import { TaskEditorSheet } from "@/components/task/TaskEditorSheet";
import type {
  Task,
  TaskCreateValues,
  TaskStatus,
  TaskUpdateValues,
} from "@/type/task";
import { TASK_STATUSES, TASK_STATUS_LABELS } from "@/type/task";
import { toast } from "sonner";
import type { SortState } from "@/components/ui/sortable-table";

type TaskTypeFilter = "all" | "group" | "individual";
type SearchParams = { page: number; task_type?: TaskTypeFilter };

export const Route = createFileRoute("/_auth/task")({
  validateSearch: (search): SearchParams => ({
    page: typeof search.page === "number" && search.page >= 1 ? search.page : 1,
    task_type:
      search.task_type === "group" || search.task_type === "individual"
        ? search.task_type
        : "all",
  }),
  component: TaskManagementPage,
});

const DEFAULT_PAGE_SIZE = 25;

function TaskManagementPage() {
  const navigate = useNavigate();
  const { page, task_type } = Route.useSearch();
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE);
  const [editorOpen, setEditorOpen] = useState(false);
  const [editorMode, setEditorMode] = useState<"create" | "edit">("create");
  const [selectedTask, setSelectedTask] = useState<Task | null>(null);
  const [sortState, setSortState] = useState<SortState<TaskSortKey>>({
    key: "due",
    direction: "asc",
  });
  // Selected tasks, keyed by id, so the selection persists across pages and we
  // keep each task snapshot for the bulk status/delete actions.
  const [selected, setSelected] = useState<Map<number, Task>>(new Map());
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);

  const typeFilter: TaskTypeFilter = task_type ?? "all";

  const { data: taskData, isPending } = useQueryTasks({
    page,
    limit: pageSize,
    task_type: typeFilter === "all" ? undefined : typeFilter,
    sortBy: sortState.key,
    sortOrder: sortState.direction,
  });

  const { data: usersData } = useQueryUsers({ page: 1, limit: 200 });
  const { data: groupsData } = useQuery({
    queryKey: ["admin-groups-dropdown"],
    queryFn: async () => {
      const res = await myFetch.get<{
        data: { items: { id: number; name: string }[] };
      }>("/group/", { params: { page: 1, limit: 200 } });
      return res.data;
    },
    refetchOnMount: false,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  });

  const createTask = useCreateTask();
  const updateTask = useUpdateTask();
  const deleteTask = useDeleteTask();

  const tasks = useMemo(
    () => taskData?.data?.items ?? [],
    [taskData?.data?.items],
  );
  const total = taskData?.data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  // Keep selected snapshots in sync with refetched page data so a single-row
  // edit/status change is reflected in the bulk-action payloads.
  useEffect(() => {
    setSelected((prev) => {
      if (prev.size === 0) return prev;
      let changed = false;
      const next = new Map(prev);
      for (const task of tasks) {
        if (next.has(task.id) && next.get(task.id) !== task) {
          next.set(task.id, task);
          changed = true;
        }
      }
      return changed ? next : prev;
    });
  }, [tasks]);

  const clearSelection = useCallback(() => setSelected(new Map()), []);

  const toggleRow = useCallback((task: Task) => {
    setSelected((prev) => {
      const next = new Map(prev);
      if (next.has(task.id)) next.delete(task.id);
      else next.set(task.id, task);
      return next;
    });
  }, []);

  const toggleAllOnPage = useCallback(() => {
    setSelected((prev) => {
      const next = new Map(prev);
      const allSelected =
        tasks.length > 0 && tasks.every((t) => next.has(t.id));
      if (allSelected) tasks.forEach((t) => next.delete(t.id));
      else tasks.forEach((t) => next.set(t.id, t));
      return next;
    });
  }, [tasks]);

  const selectedOnPage = tasks.filter((t) => selected.has(t.id));
  const headerState: boolean | "indeterminate" =
    tasks.length > 0 && selectedOnPage.length === tasks.length
      ? true
      : selectedOnPage.length > 0
        ? "indeterminate"
        : false;

  const groups = useMemo(
    () => groupsData?.data?.items ?? [],
    [groupsData?.data?.items],
  );
  const users = useMemo(
    () => usersData?.data?.items ?? [],
    [usersData?.data?.items],
  );

  const updateFilters = (filters: Partial<{ task_type: TaskTypeFilter }>) => {
    // Filters change the matching set, so drop the current selection with them.
    setSelected(new Map());
    void navigate({
      to: "/task",
      search: { page: 1, ...filters },
      replace: true,
    });
  };

  const updatePage = (nextPage: number) => {
    void navigate({
      to: "/task",
      search: { page: nextPage, task_type: typeFilter },
      replace: true,
    });
  };

  const handlePageSizeChange = (size: number) => {
    setPageSize(size);
    updatePage(1);
  };

  const openCreate = () => {
    setSelectedTask(null);
    setEditorMode("create");
    setEditorOpen(true);
  };

  const openEdit = (task: Task) => {
    setSelectedTask(task);
    setEditorMode("edit");
    setEditorOpen(true);
  };

  const handleSubmit = async (values: TaskCreateValues | TaskUpdateValues) => {
    try {
      if (editorMode === "create") {
        const created = values as TaskCreateValues;
        const result = await createTask.mutateAsync(created);
        // Fan-out creates N rows from one submit — say so, or the task list
        // suddenly growing by a dozen entries looks like a bug.
        if (created.assigned_role) toast.success(result.msg);
      } else if (selectedTask) {
        await updateTask.mutateAsync({
          id: selectedTask.id,
          updates: values as TaskUpdateValues,
        });
      }
      setEditorOpen(false);
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { msg?: string } } })?.response?.data
          ?.msg ?? "Failed to save task.";
      toast.error(msg);
    }
  };

  const handleDelete = async (task: Task) => {
    if (!window.confirm(`Delete task "${task.name}"? This cannot be undone.`))
      return;
    try {
      await deleteTask.mutateAsync(task.id);
    } catch {
      toast.error("Failed to delete task.");
    }
  };

  const isMutating =
    createTask.isPending || updateTask.isPending || deleteTask.isPending;

  const handleBulkStatus = async (status: TaskStatus) => {
    const targets = [...selected.values()];
    if (!targets.length) return;
    // Settle every update independently so one failure doesn't strand the rest.
    const outcomes = await Promise.allSettled(
      targets.map((task) =>
        updateTask
          .mutateAsync({
            id: task.id,
            updates: {
              name: task.name,
              description: task.description,
              due_date: task.due_date,
              status,
              parent: task.parent,
            },
          })
          .then(() => task.id),
      ),
    );
    const doneIds = outcomes
      .filter(
        (o): o is PromiseFulfilledResult<number> => o.status === "fulfilled",
      )
      .map((o) => o.value);
    const failed = targets.length - doneIds.length;

    if (doneIds.length) {
      // Drop only the tasks we actually updated; keep other selections.
      setSelected((prev) => {
        const next = new Map(prev);
        doneIds.forEach((id) => next.delete(id));
        return next;
      });
    }

    if (failed === 0) {
      toast.success(
        `Updated ${doneIds.length} task${doneIds.length === 1 ? "" : "s"}.`,
      );
    } else if (doneIds.length) {
      toast.error(`Updated ${doneIds.length}, but ${failed} could not be updated.`);
    } else {
      toast.error("Unable to update the selected tasks.");
    }
  };

  const handleBulkDelete = async () => {
    const targets = [...selected.values()];
    if (!targets.length) {
      setDeleteConfirmOpen(false);
      return;
    }
    const outcomes = await Promise.allSettled(
      targets.map((task) => deleteTask.mutateAsync(task.id).then(() => task.id)),
    );
    const doneIds = outcomes
      .filter(
        (o): o is PromiseFulfilledResult<number> => o.status === "fulfilled",
      )
      .map((o) => o.value);
    const failed = targets.length - doneIds.length;

    if (doneIds.length) {
      setSelected((prev) => {
        const next = new Map(prev);
        doneIds.forEach((id) => next.delete(id));
        return next;
      });
    }

    if (failed === 0) {
      toast.success(
        `Deleted ${doneIds.length} task${doneIds.length === 1 ? "" : "s"}.`,
      );
    } else if (doneIds.length) {
      toast.error(`Deleted ${doneIds.length}, but ${failed} could not be deleted.`);
    } else {
      toast.error("Unable to delete the selected tasks.");
    }
    setDeleteConfirmOpen(false);
  };

  return (
    <div className="p-4 space-y-6">
      <div className="flex flex-wrap gap-2 justify-between items-center w-full">
        <div className="flex gap-2 items-center">
          <Select
            value={typeFilter}
            onValueChange={(v) =>
              updateFilters({ task_type: v as TaskTypeFilter })
            }
          >
            <SelectTrigger className="w-40">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Types</SelectItem>
              <SelectItem value="group">Group Tasks</SelectItem>
              <SelectItem value="individual">Individual Tasks</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <Button onClick={openCreate}>
          <PlusIcon />
          Add Task
        </Button>
      </div>

      {selected.size > 0 && (
        <BulkActionsBar
          count={selected.size}
          noun="task"
          onClear={clearSelection}
          disabled={isMutating}
        >
          <Select
            value=""
            onValueChange={(v) => void handleBulkStatus(v as TaskStatus)}
          >
            <SelectTrigger className="w-36" disabled={isMutating}>
              <SelectValue placeholder="Set status" />
            </SelectTrigger>
            <SelectContent>
              {TASK_STATUSES.map((s) => (
                <SelectItem key={s} value={s}>
                  {TASK_STATUS_LABELS[s]}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button
            variant="destructive"
            size="sm"
            disabled={isMutating}
            onClick={() => setDeleteConfirmOpen(true)}
          >
            Delete
          </Button>
        </BulkActionsBar>
      )}

      <TaskTable
        data={tasks}
        page={page}
        totalPages={totalPages}
        pageSize={pageSize}
        onPageChange={updatePage}
        onPageSizeChange={handlePageSizeChange}
        onEdit={openEdit}
        onDelete={handleDelete}
        sortState={sortState}
        onSortChange={(nextSort) => {
          setSortState(nextSort);
          updatePage(1);
        }}
        isPending={isPending || isMutating}
        groups={groups}
        users={users}
        selection={{
          isSelected: (id) => selected.has(id),
          onToggleRow: toggleRow,
          headerState,
          onToggleAll: toggleAllOnPage,
        }}
      />

      <TaskEditorSheet
        open={editorOpen}
        onOpenChange={setEditorOpen}
        mode={editorMode}
        task={selectedTask}
        groups={groups}
        users={users}
        onSubmit={handleSubmit}
        isPending={isMutating}
      />

      <AlertDialog open={deleteConfirmOpen} onOpenChange={setDeleteConfirmOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              Delete {selected.size} {selected.size === 1 ? "task" : "tasks"}?
            </AlertDialogTitle>
            <AlertDialogDescription>
              This cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isMutating}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              disabled={isMutating}
              onClick={(event) => {
                event.preventDefault();
                void handleBulkDelete();
              }}
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
