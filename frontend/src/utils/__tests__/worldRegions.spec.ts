import { describe, expect, it } from 'vitest'
import { COUNTRY_TIME_ZONES } from '@/registration/timeZoneCountries'
import {
  MAP_COUNTRY_NAMES,
  WORLD_REGIONS,
  mapCountryName,
  worldRegionForCountry,
  type WorldRegion,
} from '@/utils/worldRegions'

// COUNTRY_TIME_ZONES is generated from the backend's country list, so its keys
// are every country name a user's profile can hold.
const countryList = Object.keys(COUNTRY_TIME_ZONES)
const countriesIn = (region: WorldRegion) =>
  countryList.filter((name) => worldRegionForCountry(name) === region)

describe('worldRegionForCountry', () => {
  it('places every country in the country list in a world region', () => {
    expect(countryList).toHaveLength(195)
    expect(countryList.filter((name) => worldRegionForCountry(name) === null)).toEqual([])
  })

  it('places each country in exactly one of the six world regions', () => {
    const counts = WORLD_REGIONS.map((region) => countriesIn(region).length)
    expect(counts.reduce((sum, count) => sum + count, 0)).toBe(countryList.length)
    expect(Object.fromEntries(WORLD_REGIONS.map((region, index) => [region, counts[index]]))).toEqual({
      'North America': 23,
      'South America': 12,
      Europe: 43,
      Africa: 54,
      Asia: 49,
      Oceania: 14,
    })
  })

  it('counts Nigeria and the rest of Africa, not only South Africa, as Africa', () => {
    const african = ['Nigeria', 'South Africa', 'Kenya', 'Egypt', 'Uganda', 'Cameroon', 'Côte d\'Ivoire', 'Eswatini (fmr. ""Swaziland"")']
    expect(african.filter((name) => worldRegionForCountry(name) !== 'Africa')).toEqual([])
  })

  it('uses the country, not its first time zone, for countries across regions', () => {
    // Spain's first zone is Africa/Ceuta, Australia's is Antarctica/Macquarie.
    expect(worldRegionForCountry('Spain')).toBe('Europe')
    expect(worldRegionForCountry('Portugal')).toBe('Europe')
    expect(worldRegionForCountry('Iceland')).toBe('Europe')
    expect(worldRegionForCountry('Australia')).toBe('Oceania')
    expect(worldRegionForCountry('New Zealand')).toBe('Oceania')
    expect(worldRegionForCountry('Cabo Verde')).toBe('Africa')
    expect(worldRegionForCountry('Madagascar')).toBe('Africa')
    expect(worldRegionForCountry('Maldives')).toBe('Asia')
    expect(worldRegionForCountry('Brazil')).toBe('South America')
    expect(worldRegionForCountry('Mexico')).toBe('North America')
    // As the map draws them.
    expect(worldRegionForCountry('Russia')).toBe('Asia')
    expect(worldRegionForCountry('Turkey')).toBe('Asia')
  })

  it('accepts the shorter names the map uses, and Greenland', () => {
    expect(worldRegionForCountry('United States of America')).toBe('North America')
    expect(worldRegionForCountry('United States')).toBe('North America')
    expect(worldRegionForCountry('Czechia')).toBe('Europe')
    expect(worldRegionForCountry('Myanmar')).toBe('Asia')
    expect(worldRegionForCountry('Greenland')).toBe('North America')
  })

  it('returns null for unknown or missing names', () => {
    expect(worldRegionForCountry('Atlantis')).toBeNull()
    expect(worldRegionForCountry('Unknown')).toBeNull()
    expect(worldRegionForCountry('NSW')).toBeNull()
    expect(worldRegionForCountry('')).toBeNull()
    expect(worldRegionForCountry(null)).toBeNull()
    expect(worldRegionForCountry(undefined)).toBeNull()
  })
})

describe('mapCountryName', () => {
  it('renames only the country-list names the map shortens', () => {
    expect(mapCountryName('United States of America')).toBe('United States')
    expect(mapCountryName('Czechia (Czech Republic)')).toBe('Czechia')
    expect(mapCountryName('Myanmar (formerly Burma)')).toBe('Myanmar')
    expect(mapCountryName('Nigeria')).toBe('Nigeria')
  })

  it('only renames names that are in the country list', () => {
    for (const listName of Object.keys(MAP_COUNTRY_NAMES)) {
      expect(countryList).toContain(listName)
    }
  })
})
