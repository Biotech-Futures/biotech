/**
 * Management's Pages Visibility (on Challenge Start), shared by the menu, the
 * router guard and its card: when students, mentors and supervisors start
 * seeing Home, Groups, Events, Announcements and Resources. Hidden until its
 * date and time (and until that's known), and while none is set. Admins
 * always see them.
 */
import { computed, ref } from 'vue'

import { fetchSupervisorPages, type SupervisorPagesState } from '@/utils/managementAPI'

// When they're shown from (an instant), as the server has it; null for none.
const shownFrom = ref<string | null>(null)
// When this year's challenge starts (Challenge Start), which the menu says
// while the pages are hidden; null while it isn't set.
const challengeStartsAt = ref<string | null>(null)
// The time, kept for the menu so the pages appear when the date comes.
const now = ref(Date.now())
let clock: ReturnType<typeof setInterval> | undefined
let loading: Promise<void> | null = null

const isShownAt = (time: number) => shownFrom.value !== null && time >= Date.parse(shownFrom.value)

/** Whether they're shown now, following the time. */
const shown = computed(() => isShownAt(now.value))

// Keeps the time while the date is still to come, then stops.
const followTime = () => {
  now.value = Date.now()
  const waiting = shownFrom.value !== null && !isShownAt(now.value)
  if (waiting && !clock) {
    clock = setInterval(followTime, 30_000)
  } else if (!waiting && clock) {
    clearInterval(clock)
    clock = undefined
  }
}

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

/** When they're shown from, read from the server once and then kept:
 *  whether they're shown now. */
export function loadSupervisorPages(force = false): Promise<boolean> {
  return load(force).then(() => isShownAt(Date.now()))
}

/** As saved (after an admin sets the date), so this tab's menu follows straight away. */
export function setSupervisorPages(state: SupervisorPagesState): void {
  shownFrom.value = state.shown_from ?? null
  challengeStartsAt.value = state.challenge_starts_at ?? null
  loading = Promise.resolve()
  followTime()
}

/** The pages a student, mentor or supervisor loses while they're hidden. */
export const SUPERVISOR_HIDDEN_PATHS = ['/dashboard', '/groups', '/events', '/announcements', '/resources']

export const isSupervisorHiddenPath = (path: string) =>
  SUPERVISOR_HIDDEN_PATHS.some((hidden) => path === hidden || path.startsWith(`${hidden}/`))

export function useSupervisorPages() {
  return { shown, shownFrom, challengeStartsAt, now }
}
