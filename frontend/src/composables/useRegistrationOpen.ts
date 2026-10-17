/**
 * Whether registration is open, by the year's dates (Management > Registration
 * Visibility > Registration Dates), shared by the sign-in page (its Register
 * now) and the registration page: whether the public can register now
 * (``openNow``), and for a supervisor whether they can register students now
 * (``canRegisterStudents``). Taken as open until it's known to be closed, as
 * it is with no dates, so Register now doesn't flicker in.
 */
import { ref } from 'vue'

import { fetchRegistrationOpen, type RegistrationState } from '@/utils/managementAPI'

const openNow = ref(true)
const opensAt = ref<string | null>(null)
const closesAt = ref<string | null>(null)
const canRegisterStudents = ref(true)
let loading: Promise<boolean> | null = null

/** As the server gives it (after an admin changes the dates too, so this tab
 *  follows straight away). */
export function setRegistrationState(state: RegistrationState): void {
  openNow.value = state.open_now !== false
  opensAt.value = state.opens_at ?? null
  closesAt.value = state.closes_at ?? null
  canRegisterStudents.value = state.can_register_students !== false
  loading = Promise.resolve(openNow.value)
}

/** Read from the server once and then kept; ``force`` reads it again. */
export function loadRegistrationOpen(force = false): Promise<boolean> {
  if (!loading || force) {
    loading = fetchRegistrationOpen()
      .then((state) => {
        setRegistrationState(state)
        return openNow.value
      })
      .catch(() => {
        loading = null
        return openNow.value
      })
  }
  return loading
}

export function useRegistrationOpen() {
  return { openNow, opensAt, closesAt, canRegisterStudents }
}
