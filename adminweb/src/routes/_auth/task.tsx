import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useState, useMemo } from "react";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { PlusIcon } from "lucide-react";
import {
  useQueryTasks,
  useCreateTask,
  useUpdateTask,
  useDeleteTask,
  useToggleTask,
} from "@/query/task";
import { useQueryUsers } from "@/query/user";
import { useQuery } from "@tanstack/react-query";
import { myFetch } from "@/lib/myFetch";
import { TaskTable, type TaskSortKey } from "@/components/task/TaskTable";
import { TaskEditorSheet } from "@/components/task/TaskEditorSheet";
import type { Task, TaskCreateValues, TaskUpdateValues } from "@/type/task";
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

const PAGE_SIZE = 10;

function TaskManagementPage() {
  const navigate = useNavigate();
  const { page, task_type } = Route.useSearch();
  const [editorOpen, setEditorOpen] = useState(false);
  const [editorMode, setEditorMode] = useState<"create" | "edit">("create");
  const [selectedTask, setSelectedTask] = useState<Task | null>(null);
  const [sortState, setSortState] = useState<SortState<TaskSortKey>>({
    key: "due",
    direction: "asc",
  });

  const typeFilter: TaskTypeFilter = task_type ?? "all";

  const { data: taskData, isPending } = useQueryTasks({
    page,
    limit: PAGE_SIZE,
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
  const toggleTask = useToggleTask();

  const tasks = taskData?.data?.items ?? [];
  const total = taskData?.data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const groups = useMemo(
    () => groupsData?.data?.items ?? [],
    [groupsData?.data?.items],
  );
  const users = useMemo(
    () => usersData?.data?.items ?? [],
    [usersData?.data?.items],
  );

  const updateFilters = (filters: Partial<{ task_type: TaskTypeFilter }>) => {
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
        await createTask.mutateAsync(values as TaskCreateValues);
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

  const handleToggle = async (task: Task) => {
    try {
      await toggleTask.mutateAsync({ id: task.id, completed: !task.completed });
    } catch {
      toast.error("Failed to update task.");
    }
  };

  const isMutating =
    createTask.isPending ||
    updateTask.isPending ||
    deleteTask.isPending ||
    toggleTask.isPending;

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

      <TaskTable
        data={tasks}
        page={page}
        totalPages={totalPages}
        onPageChange={updatePage}
        onEdit={openEdit}
        onDelete={handleDelete}
        onToggle={handleToggle}
        sortState={sortState}
        onSortChange={(nextSort) => {
          setSortState(nextSort);
          updatePage(1);
        }}
        isPending={isPending || isMutating}
        groups={groups}
        users={users}
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
    </div>
  );
}
