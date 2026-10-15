/**
 * The registration form's State or region dropdown: Australia's states and
 * territories as the database holds them (GET registration/states/), loaded
 * once and shared by every form on the page. Empty for any other country, or
 * until they come (or if they can't), when the form shows a text box instead.
 */
import { ref, watch } from 'vue'

import { isAustralia } from './registration'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

let australianStates: Promise<string[]> | null = null

const loadAustralianStates = () => {
  australianStates ??= fetch(`${API_BASE_URL}/api/v1/registration/states/?country=Australia`)
    .then((response) => (response.ok ? response.json() : null))
    .then((body) => (Array.isArray(body?.states) ? (body.states as string[]) : []))
    .catch(() => [])
    .then((states) => {
      // None came: asked again the next time, rather than never.
      if (!states.length) australianStates = null
      return states
    })
  return australianStates
}

export type StateOption = { value: string; label: string }

/** ``country()``'s states as dropdown options while it's Australia, else none. */
export function useStateOptions(country: () => string) {
  const options = ref<StateOption[]>([])
  watch(
    () => isAustralia(country()),
    async (australia) => {
      if (!australia) {
        options.value = []
        return
      }
      const states = await loadAustralianStates()
      if (isAustralia(country())) options.value = states.map((state) => ({ value: state, label: state }))
    },
    { immediate: true },
  )
  return options
}
