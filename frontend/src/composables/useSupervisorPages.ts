/**
 * Management's Supervisor Pages Visibility switch, shared by the menu, the
 * router guard and the Management tab: whether supervisors see Home, Groups,
 * Events, Announcements and Resources. Hidden until it's known to be on.
 */
import { ref } from 'vue'

import { fetchSupervisorPages, type SupervisorPagesState } from '@/utils/managementAPI'

const shown = ref(false)
let loading: Promise<void> | null = null

const load = (force: boolean): Promise<void> => {
  if (!loading || force) {
    loading = fetchSupervisorPages()
      .then(setSupervisorPages)
      .catch(() => {
        loading = null
      })
  }
  return loading
}

/** The pages' switch, read from the server once and then kept. */
export function loadSupervisorPages(force = false): Promise<boolean> {
  return load(force).then(() => shown.value)
}

/** As saved (after an admin flips it), so this tab's menu follows straight away. */
export function setSupervisorPages(state: SupervisorPagesState): void {
  shown.value = state.shown
  loading = Promise.resolve()
}

/** The pages a supervisor loses while the switch is off. */
export const SUPERVISOR_HIDDEN_PATHS = ['/dashboard', '/groups', '/events', '/announcements', '/resources']

export const isSupervisorHiddenPath = (path: string) =>
  SUPERVISOR_HIDDEN_PATHS.some((hidden) => path === hidden || path.startsWith(`${hidden}/`))

export function useSupervisorPages() {
  return { shown }
}
