// Member group-plan API (GP3 endpoints under /api/v1/plans/). Session/CSRF
// transport is the shared requestJson, as finalistAPI uses; not the admin helper.
import { requestJson } from './submissionsAPI'

/** Audiences match a viewer's role in the group, not their platform role. */
export type PlanAudienceRole = 'student' | 'mentor' | 'supervisor'

/** `per_person`: each person ticks their own; `per_group`: one tick for the whole group. */
export type PlanCompletionMode = 'per_person' | 'per_group'

export interface PlanStage {
  id: number
  name: string
  /** Stage introduction; '' when there is none. */
  description: string
  position: number
}

export interface GroupPlanTask {
  id: number
  stage_id: number
  position: number
  name: string
  /** Instructions, as plain text; '' when there are none. */
  description: string
  /** '' when the task has no resource link. */
  resource_url: string
  resource_label: string
  /** Date-only `YYYY-MM-DD`, or null when undated. */
  due_date: string | null
  audience_role: PlanAudienceRole
  completion_mode: PlanCompletionMode
  /**
   * The viewer's own tick for an individual task, or the group's tick for a
   * shared one. Null for an individual task outside the viewer's audience
   * (e.g. an admin viewing a student task): show "Each person ticks their own".
   */
  completed: boolean | null
  /** Server-decided: whether this viewer may tick it. Drive checkboxes from this alone. */
  can_toggle: boolean
}

export interface GroupPlanList {
  year: number
  /** Only stages with at least one visible task, in plan order. */
  stages: PlanStage[]
  /** Visible tasks in plan order. Both arrays are empty outside the current cohort. */
  items: GroupPlanTask[]
}

const groupTasksPath = (groupId: number | string) => `/api/v1/plans/groups/${groupId}/tasks/`

export function listGroupPlanTasks(groupId: number | string) {
  return requestJson<GroupPlanList>(groupTasksPath(groupId))
}

/**
 * Tick (`true`) or untick (`false`) a task for the signed-in viewer, or omit
 * `completed` to flip it. The server decides whose record changes; no user id
 * is ever sent. Resolves to the updated task.
 */
export function toggleGroupPlanTask(
  groupId: number | string,
  taskId: number | string,
  completed?: boolean
) {
  return requestJson<GroupPlanTask>(`${groupTasksPath(groupId)}${taskId}/check/`, {
    method: 'POST',
    body: JSON.stringify(completed === undefined ? {} : { completed })
  })
}
