/**
 * The registration form's Country and State or region dropdowns: the
 * countries, and Australia's states and territories, as the database holds
 * them (GET registration/countries/ and registration/states/), each loaded
 * once and shared by every form on the page. Empty until they come (or if
 * they can't), when the form shows a text box instead. Also the universities
 * a mentor's University or institution suggests (registration/universities/).
 */
import { ref, watch } from 'vue'

import { isAustralia } from './registration'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

export type LocationOption = { value: string; label: string }

/** A list from ``path``'s ``key``, loaded once; asked again if none came. */
const loader = (path: string, key: string) => {
  let names: Promise<string[]> | null = null
  return () =>
    (names ??= fetch(`${API_BASE_URL}/api/v1/registration/${path}`)
      .then((response) => (response.ok ? response.json() : null))
      .then((body) => (Array.isArray(body?.[key]) ? (body[key] as string[]) : []))
      .catch(() => [])
      .then((list) => {
        if (!list.length) names = null
        return list
      }))
}

const loadCountries = loader('countries/', 'countries')
const loadAustralianStates = loader('states/?country=Australia', 'states')
const loadUniversities = loader('universities/', 'universities')

/** The universities admins keep on Management > Known Universities, offered
 *  as a mentor types theirs; none until they come. */
export function useUniversityNames() {
  const names = ref<string[]>([])
  void loadUniversities().then((universities) => {
    names.value = universities
  })
  return names
}

/** Every country's name, and Australia's states' (none if they can't come). */
export const countryNames = () => loadCountries()
export const australianStateNames = () => loadAustralianStates()

const asOptions = (names: string[]): LocationOption[] => names.map((name) => ({ value: name, label: name }))

/** Every country, as dropdown options. */
export function useCountryOptions() {
  const options = ref<LocationOption[]>([])
  void loadCountries().then((countries) => {
    options.value = asOptions(countries)
  })
  return options
}

/** ``country()``'s states as dropdown options while it's Australia, else none. */
export function useStateOptions(country: () => string) {
  const options = ref<LocationOption[]>([])
  watch(
    () => isAustralia(country()),
    async (australia) => {
      if (!australia) {
        options.value = []
        return
      }
      const states = await loadAustralianStates()
      if (isAustralia(country())) options.value = asOptions(states)
    },
    { immediate: true },
  )
  return options
}
