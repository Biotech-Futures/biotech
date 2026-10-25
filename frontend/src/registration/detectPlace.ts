/**
 * Where the computer says it is, for a sign-up's Country (and, in Australia,
 * its State) to start on: its time zone's country, else its language's region
 * (en-AU). Read from the browser alone: nothing is asked for or sent. Only a
 * country (and state) the page's own lists have is given.
 */
import { CODE_COUNTRIES, COUNTRY_TIME_ZONES } from './timeZoneCountries'
import { isAustralia } from './registration'

export interface DetectedPlace {
  country: string
  state: string
}

// Australia's time zones' states, as the database names them. Canberra's
// computers mostly say Sydney, so NSW.
const AUSTRALIAN_STATES: Record<string, string> = {
  'Australia/Sydney': 'NSW',
  'Australia/NSW': 'NSW',
  'Australia/Broken_Hill': 'NSW',
  'Australia/Yancowinna': 'NSW',
  'Australia/Lord_Howe': 'NSW',
  'Australia/LHI': 'NSW',
  'Australia/Canberra': 'ACT',
  'Australia/ACT': 'ACT',
  'Australia/Melbourne': 'VIC',
  'Australia/Victoria': 'VIC',
  'Australia/Brisbane': 'QLD',
  'Australia/Queensland': 'QLD',
  'Australia/Lindeman': 'QLD',
  'Australia/Adelaide': 'SA',
  'Australia/South': 'SA',
  'Australia/Perth': 'WA',
  'Australia/West': 'WA',
  'Australia/Eucla': 'WA',
  'Australia/Hobart': 'TAS',
  'Australia/Tasmania': 'TAS',
  'Australia/Currie': 'TAS',
  'Antarctica/Macquarie': 'TAS',
  'Australia/Darwin': 'NT',
  'Australia/North': 'NT',
}

// Other names a country may be under in a database (migration 0012's).
const ALSO_KNOWN_AS: Record<string, string[]> = {
  'United States of America': ['United States', 'USA', 'US'],
}

let zoneCountries: Map<string, string> | null = null
const countryOfZone = (zone: string) => {
  zoneCountries ??= new Map(
    Object.entries(COUNTRY_TIME_ZONES).flatMap(([country, zones]) =>
      zones.split(' ').map((name) => [name, country] as const),
    ),
  )
  return zoneCountries.get(zone) ?? ''
}

// A name to compare by: no accents, case, punctuation or "(…)".
const key = (name: string) =>
  name
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .split('(')[0]!
    .replace(/&/g, 'and')
    .replace(/[^a-z0-9]/g, '')

/** ``country`` as ``countries`` names it, or '' if it isn't there. */
export const matchCountry = (country: string, countries: string[]) => {
  if (!country) return ''
  for (const name of [country, ...(ALSO_KNOWN_AS[country] ?? [])]) {
    const found = countries.find((candidate) => candidate.toLowerCase() === name.toLowerCase())
    if (found) return found
  }
  return countries.find((candidate) => key(candidate) === key(country)) ?? ''
}

/** The browser's own: its time zone and languages. */
export const browserPlace = () => ({
  timeZone: (() => {
    try {
      return Intl.DateTimeFormat().resolvedOptions().timeZone || ''
    } catch {
      return ''
    }
  })(),
  languages: typeof navigator === 'undefined' ? [] : [...(navigator.languages ?? []), navigator.language ?? ''],
})

/** The country (and Australia's state) the computer is in, among
 *  ``countries`` and ``states`` (Australia's), or null if it can't be told. */
export function detectPlace(
  countries: string[],
  states: string[],
  browser: { timeZone: string; languages: readonly string[] } = browserPlace(),
): DetectedPlace | null {
  const region = browser.languages
    .map((language) => /^[a-z]{2,3}[-_]([A-Za-z]{2})\b/i.exec(language)?.[1]?.toUpperCase() ?? '')
    .find((code) => code && CODE_COUNTRIES[code])
  const country = matchCountry(
    countryOfZone(browser.timeZone) || (region ? CODE_COUNTRIES[region]! : ''),
    countries,
  )
  if (!country) return null
  const state = isAustralia(country) ? (AUSTRALIAN_STATES[browser.timeZone] ?? '') : ''
  return {
    country,
    state: states.find((name) => name.toUpperCase() === state) ?? '',
  }
}
