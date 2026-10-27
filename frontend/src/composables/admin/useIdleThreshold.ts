import { ref } from 'vue'
import { DEFAULT_IDLE_DAYS } from '@/utils/mentorFormat'

/**
 * How many quiet days make a mentor idle, shared by every screen that counts
 * them.
 *
 * The ref is module-level on purpose. The Mentors page and Matched Groups used
 * to hold their own copies, so an admin who changed it on one screen left the
 * other still counting by the default, and the two reported different numbers
 * of mentors needing replacement. One ref means they cannot drift apart again.
 *
 * It lives only for the session: a reload returns both screens to the default
 * together, which is consistent even though it is not remembered.
 */
const idleDays = ref(DEFAULT_IDLE_DAYS)

/**
 * Set the threshold, clamped to at least a day. Zero or a negative would make
 * every mentor idle the moment they stopped typing, and a non-number would
 * make the comparison meaningless.
 */
export const setIdleDays = (value: number) => {
  idleDays.value = Math.max(1, Number.isFinite(value) ? value : 1)
}

export const useIdleThreshold = () => ({ idleDays, setIdleDays })
