import { apiErrorFromResponse } from './apiError'
import { buildSessionHeaders, ensureCsrfCookie } from './csrf'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

export type RoleTaskStatus = 'todo' | 'in_progress' | 'done' | 'blocked'

export interface RoleTaskRow {
  id: number
  name: string
  description: string
  due_date: string | null
  role: string
  status: RoleTaskStatus
  completed: boolean
  created_at: string
  updated_at: string
}

async function requestJson<T>(pathOrUrl: string, options: RequestInit = {}): Promise<T> {
  const method = String(options.method || 'GET').toUpperCase()
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

// TK4: role tasks are defined once per role (see backend RoleTask) and picked
// up live by whoever currently holds that role — no per-user provisioning.
export function listMyRoleTasks() {
  return requestJson<RoleTaskRow[]>('/api/v1/tasks/role-tasks/mine/')
}

export function toggleRoleTaskCompletion(roleTaskId: number | string, completed?: boolean) {
  return requestJson<RoleTaskRow>(`/api/v1/tasks/role-tasks/${roleTaskId}/check/`, {
    method: 'POST',
    body: JSON.stringify(completed === undefined ? {} : { completed })
  })
}
