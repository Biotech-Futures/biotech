import { describe, expect, it } from 'vitest'

import { detectPlace, matchCountry } from '@/registration/detectPlace'

const COUNTRIES = ['Australia', 'India', 'New Zealand', 'United States', 'Czechia (Czech Republic)', "Côte d'Ivoire"]
const STATES = ['ACT', 'NSW', 'NT', 'QLD', 'SA', 'TAS', 'VIC', 'WA']
const at = (timeZone: string, ...languages: string[]) => detectPlace(COUNTRIES, STATES, { timeZone, languages })

describe('where the computer says it is', () => {
  it("gives Australia's state from its time zone", () => {
    expect(at('Australia/Sydney')).toEqual({ country: 'Australia', state: 'NSW' })
    expect(at('Australia/Melbourne')).toEqual({ country: 'Australia', state: 'VIC' })
    expect(at('Australia/Brisbane')).toEqual({ country: 'Australia', state: 'QLD' })
    expect(at('Australia/Adelaide')).toEqual({ country: 'Australia', state: 'SA' })
    expect(at('Australia/Perth')).toEqual({ country: 'Australia', state: 'WA' })
    expect(at('Australia/Hobart')).toEqual({ country: 'Australia', state: 'TAS' })
    expect(at('Australia/Darwin')).toEqual({ country: 'Australia', state: 'NT' })
    expect(at('Australia/Canberra')).toEqual({ country: 'Australia', state: 'ACT' })
    expect(at('Australia/Broken_Hill')).toEqual({ country: 'Australia', state: 'NSW' })
  })

  it('gives the country of any time zone, older names too, and no state outside Australia', () => {
    expect(at('Pacific/Auckland')).toEqual({ country: 'New Zealand', state: '' })
    expect(at('Asia/Calcutta')).toEqual({ country: 'India', state: '' })
    expect(at('Asia/Kolkata')).toEqual({ country: 'India', state: '' })
    expect(at('Europe/Prague')).toEqual({ country: 'Czechia (Czech Republic)', state: '' })
    expect(at('Africa/Abidjan')).toEqual({ country: "Côte d'Ivoire", state: '' })
  })

  it("names a country as the page's list does", () => {
    // Our list may say United States, or United States of America.
    expect(at('America/New_York')).toEqual({ country: 'United States', state: '' })
    expect(matchCountry('United States of America', ['United States of America'])).toBe('United States of America')
    expect(matchCountry('Czechia (Czech Republic)', ['Czechia'])).toBe('Czechia')
    expect(matchCountry('Japan', COUNTRIES)).toBe('')
  })

  it("falls back on the browser's language region, then gives up", () => {
    expect(at('UTC', 'en-AU', 'en')).toEqual({ country: 'Australia', state: '' })
    expect(at('', 'en', 'fr-NZ')).toEqual({ country: 'New Zealand', state: '' })
    expect(at('UTC', 'en')).toBeNull()
    // A country not on the list: nothing chosen.
    expect(at('Asia/Tokyo', 'ja-JP')).toBeNull()
  })
})
