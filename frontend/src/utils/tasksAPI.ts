import { apiErrorFromResponse } from './apiError'
import { buildSessionHeaders, ensureCsrfCookie } from './csrf'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

export type TaskStatus = 'todo' | 'in_progress' | 'done' | 'blocked'
export type TaskType = 'group' | 'individual'
export type TaskOrdering = 'due_date' | '-due_date' | 'created_at' | '-created_at' | 'updated_at' | '-updated_at' | 'status' | '-status'

export interface TaskUserMini {
  id: number
  name: string | null
}

export interface TaskRow {
  id: number
  name: string
  description: string
  due_date: string | null
  status: TaskStatus
  completed: boolean
  parent: number | null
  task_type: TaskType
  group: number | null
  assigned_user: number | null
  created_by: TaskUserMini | null
  creator_role: string
  deleted_at: string | null
  created_at: string
  updated_at: string
}

export interface PaginatedTaskResponse {
  count: number
  next: string | null
  previous: string | null
  results: TaskRow[]
}

export interface ListTasksParams {
  page?: number
  page_size?: number
  deleted?: boolean
  task_type?: TaskType | ''
  status?: TaskStatus | ''
  completed?: boolean | ''
  group_id?: number | string | ''
  assigned_user?: number | string | ''
  parent_id?: number | string | ''
  due_date_after?: string
  due_date_before?: string
  search?: string
  ordering?: TaskOrdering | ''
}

export interface CreateTaskPayload {
  name: string
  description?: string
  due_date?: string | null
  status?: TaskStatus
  parent?: number | null
  task_type: TaskType
  group?: number | null
  assigned_user?: number | null
}

export interface UpdateTaskPayload {
  name?: string
  description?: string
  due_date?: string | null
  status?: TaskStatus
  parent?: number | null
}

export interface BulkToggleTasksResponse {
  updated: TaskRow[]
  not_found: number[]
  forbidden: number[]
}

function appendParam(params: URLSearchParams, key: string, value: unknown) {
  if (value === undefined || value === null || value === '') return
  params.set(key, String(value))
}

function buildTaskListUrl(params: ListTasksParams = {}) {
  const searchParams = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => appendParam(searchParams, key, value))
  const query = searchParams.toString()
  return `${API_BASE_URL}/api/v1/tasks/${query ? `?${query}` : ''}`
}

async function requestJson<T>(pathOrUrl: string, options: RequestInit = {}): Promise<T> {
  const method = String(options.method || 'GET').toUpperCase()
  const isFormData = options.body instanceof FormData
  const includeCSRF = !['GET', 'HEAD', 'OPTIONS'].includes(method)

  if (includeCSRF) {
    const csrfReady = await ensureCsrfCookie(API_BASE_URL)
    if (!csrfReady) {
      throw new Error('Could not initialize a secure session. Please refresh and try again.')
    }
  }

  const url = pathOrUrl.startsWith('http') ? pathOrUrl : `${API_BASE_URL}${pathOrUrl}`
  const response = await fetch(url, {
    credentials: 'include',
    ...options,
    headers: buildSessionHeaders({
      includeCSRF,
      isFormData,
      headers: {
        Accept: 'application/json',
        ...(options.headers || {})
      }
    })
  })

  if (!response.ok) {
    throw await apiErrorFromResponse(response)
  }

  const text = await response.text()
  return (text ? JSON.parse(text) : null) as T
}

export function listTasks(params: ListTasksParams = {}) {
  return requestJson<PaginatedTaskResponse>(buildTaskListUrl(params))
}

export function retrieveTask(taskId: number | string) {
  return requestJson<TaskRow>(`/api/v1/tasks/${taskId}/`)
}

export function createTask(payload: CreateTaskPayload) {
  return requestJson<TaskRow>('/api/v1/tasks/', {
    method: 'POST',
    body: JSON.stringify(payload)
  })
}

export function replaceTask(taskId: number | string, payload: UpdateTaskPayload) {
  return requestJson<TaskRow>(`/api/v1/tasks/${taskId}/`, {
    method: 'PUT',
    body: JSON.stringify(payload)
  })
}

export function updateTask(taskId: number | string, payload: UpdateTaskPayload) {
  return requestJson<TaskRow>(`/api/v1/tasks/${taskId}/`, {
    method: 'PATCH',
    body: JSON.stringify(payload)
  })
}

export function deleteTask(taskId: number | string) {
  return requestJson<TaskRow>(`/api/v1/tasks/${taskId}/`, {
    method: 'DELETE'
  })
}

export function toggleTaskCompletion(taskId: number | string, completed?: boolean) {
  return requestJson<TaskRow>(`/api/v1/tasks/${taskId}/check/`, {
    method: 'POST',
    body: JSON.stringify(completed === undefined ? {} : { completed })
  })
}

export function setTaskStatus(taskId: number | string, status: TaskStatus) {
  return requestJson<TaskRow>(`/api/v1/tasks/${taskId}/status/`, {
    method: 'POST',
    body: JSON.stringify({ status })
  })
}

export function bulkToggleTasks(taskIds: number[], completed?: boolean) {
  return requestJson<BulkToggleTasksResponse>('/api/v1/tasks/bulk/check/', {
    method: 'POST',
    body: JSON.stringify(completed === undefined ? { task_ids: taskIds } : { task_ids: taskIds, completed })
  })
}
