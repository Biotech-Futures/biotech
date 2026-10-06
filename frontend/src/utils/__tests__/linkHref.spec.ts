import { describe, expect, it } from 'vitest'
import { linkHref } from '@/utils/linkHref'

describe('linkHref', () => {
  it('accepts placeholders, web and email addresses, filling in what a bare one lacks', () => {
    expect(linkHref('  {{ registration_url }} ')).toBe('{{ registration_url }}')
    expect(linkHref('{{ platform_url }}/groups')).toBe('{{ platform_url }}/groups')
    expect(linkHref('https://biotechfutures.org/symposium')).toBe('https://biotechfutures.org/symposium')
    expect(linkHref('mailto:support@biotechfutures.org')).toBe('mailto:support@biotechfutures.org')
    expect(linkHref('biotechfutures.org/apply')).toBe('https://biotechfutures.org/apply')
    expect(linkHref('support@biotechfutures.org')).toBe('mailto:support@biotechfutures.org')
  })

  it('refuses what cannot be a link', () => {
    for (const value of ['', '   ', 'register here', 'javascript:alert(1)', '/relative/path', '{{ half']) {
      expect(linkHref(value)).toBeNull()
    }
  })

  it('accepts site paths only where they work', () => {
    expect(linkHref('/events/12')).toBeNull()
    expect(linkHref('/events/12', { allowRelative: true })).toBe('/events/12')
  })
})
