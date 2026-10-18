/**
 * Whether a supervisor's Results page is open, shared by the menu and the
 * router guard: once marks or certificates are released on Release Results.
 * Hidden until it's known to be open.
 */
import { ref } from 'vue'

import { fetchSupervisorResultsState } from '@/utils/managementAPI'

const shown = ref(false)
let loading: Promise<boolean> | null = null

/** Whether anything is released, read from the server once and then kept;
 *  ``force`` reads it again, e.g. when the page is opened. */
export function loadSupervisorResults(force = false): Promise<boolean> {
  if (!loading || force) {
    loading = fetchSupervisorResultsState()
      .then((state) => (shown.value = state.marks_released || state.certificates_released))
      .catch(() => {
        loading = null
        return shown.value
      })
  }
  return loading
}

export function useSupervisorResults() {
  return { shown }
}
