/**
 * Management's Supervisor Visibility switch, shared by the menu, the router guard
 * and the Management tab: whether supervisors see Home, Groups, Events,
 * Announcements and Resources. Hidden until it's known to be on.
 */
import { ref } from 'vue'

import { fetchSupervisorPages } from '@/utils/managementAPI'

const shown = ref(false)
let loading: Promise<boolean> | null = null

/** The switch, read from the server once and then kept. */
export function loadSupervisorPages(force = false): Promise<boolean> {
  if (!loading || force) {
    loading = fetchSupervisorPages()
      .then((setting) => (shown.value = setting.shown))
      .catch(() => {
        loading = null
        return shown.value
      })
  }
  return loading
}

/** After an admin flips it, so this tab's menu follows straight away. */
export function setSupervisorPagesShown(value: boolean): void {
  shown.value = value
  loading = Promise.resolve(value)
}

/** The pages a supervisor loses while the switch is off. */
export const SUPERVISOR_HIDDEN_PATHS = ['/dashboard', '/groups', '/events', '/announcements', '/resources']

export const isSupervisorHiddenPath = (path: string) =>
  SUPERVISOR_HIDDEN_PATHS.some((hidden) => path === hidden || path.startsWith(`${hidden}/`))

export function useSupervisorPages() {
  return { shown }
}
