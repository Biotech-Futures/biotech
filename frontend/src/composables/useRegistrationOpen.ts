/**
 * Management > Registration's switch, shared by the sign-in page (its Register
 * now), the registration page and the Management tab: whether registration is
 * open to the public. Taken as open until it's known to be closed, as it is by
 * default, so Register now doesn't flicker in.
 */
import { ref } from 'vue'

import { fetchRegistrationOpen } from '@/utils/managementAPI'

const open = ref(true)
let loading: Promise<boolean> | null = null

/** The switch, read from the server once and then kept; ``force`` reads it again. */
export function loadRegistrationOpen(force = false): Promise<boolean> {
  if (!loading || force) {
    loading = fetchRegistrationOpen()
      .then((setting) => (open.value = setting?.open !== false))
      .catch(() => {
        loading = null
        return open.value
      })
  }
  return loading
}

/** As saved (after an admin flips it), so this tab follows straight away. */
export function setRegistrationOpen(value: boolean): void {
  open.value = value
  loading = Promise.resolve(value)
}

export function useRegistrationOpen() {
  return { open }
}
