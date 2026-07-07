export const TASK_TYPES = ["group", "individual"] as const;
export type TaskType = (typeof TASK_TYPES)[number];

export const TASK_STATUSES = ["todo", "in_progress", "done", "blocked"] as const;
export type TaskStatus = (typeof TASK_STATUSES)[number];

export const TASK_STATUS_LABELS: Record<TaskStatus, string> = {
  todo: "To Do",
  in_progress: "In Progress",
  done: "Done",
  blocked: "Blocked",
};

export type Task = {
  id: number;
  name: string;
  description: string;
  due_date: string | null;
  status: TaskStatus;
  completed: boolean;
  parent: number | null;
  task_type: TaskType;
  group: number | null;
  assigned_user: number | null;
  created_by: { id: number; name: string | null } | null;
  creator_role: string;
  deleted_at: string | null;
  created_at: string;
  updated_at: string;
};

export type AdminTaskListResponse = {
  msg: string;
  data: {
    items: Task[];
    total: number;
    page: number;
    limit: number;
    has_more: boolean;
  };
};

export type TaskCreateValues = {
  task_type: TaskType;
  group: number | null;
  assigned_user: number | null;
  name: string;
  description: string;
  due_date: string | null;
  status: TaskStatus;
  parent: number | null;
};

export type TaskUpdateValues = {
  name: string;
  description: string;
  due_date: string | null;
  status: TaskStatus;
  parent: number | null;
};
