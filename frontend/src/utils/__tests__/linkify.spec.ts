import { describe, expect, it } from 'vitest'

import { firstLinkHref, splitTextIntoLinkSegments } from '@/utils/linkify'

describe('splitTextIntoLinkSegments', () => {
  it('returns a single text segment when there is no URL', () => {
    expect(splitTextIntoLinkSegments('hello team')).toEqual([
      { type: 'text', text: 'hello team' },
    ])
  })

  it('returns empty for empty or nullish input', () => {
    expect(splitTextIntoLinkSegments('')).toEqual([])
    expect(splitTextIntoLinkSegments(null)).toEqual([])
    expect(splitTextIntoLinkSegments(undefined)).toEqual([])
  })

  it('extracts an http(s) URL with surrounding text', () => {
    expect(splitTextIntoLinkSegments('see https://example.com/foo for info')).toEqual([
      { type: 'text', text: 'see ' },
      { type: 'link', text: 'https://example.com/foo', href: 'https://example.com/foo' },
      { type: 'text', text: ' for info' },
    ])
  })

  it('keeps trailing punctuation out of the link', () => {
    expect(splitTextIntoLinkSegments('read https://example.com/foo, please.')).toEqual([
      { type: 'text', text: 'read ' },
      { type: 'link', text: 'https://example.com/foo', href: 'https://example.com/foo' },
      { type: 'text', text: ', please.' },
    ])
  })

  it('keeps a closing paren that balances one inside the URL', () => {
    expect(
      splitTextIntoLinkSegments('see https://en.wikipedia.org/wiki/Rust_(programming_language).'),
    ).toEqual([
      { type: 'text', text: 'see ' },
      {
        type: 'link',
        text: 'https://en.wikipedia.org/wiki/Rust_(programming_language)',
        href: 'https://en.wikipedia.org/wiki/Rust_(programming_language)',
      },
      { type: 'text', text: '.' },
    ])
  })

  it('still drops an unbalanced trailing paren', () => {
    expect(splitTextIntoLinkSegments('(see https://example.com/foo)')).toEqual([
      { type: 'text', text: '(see ' },
      { type: 'link', text: 'https://example.com/foo', href: 'https://example.com/foo' },
      { type: 'text', text: ')' },
    ])
  })

  it('prefixes bare www. hosts with https://', () => {
    expect(splitTextIntoLinkSegments('go to www.example.com now')).toEqual([
      { type: 'text', text: 'go to ' },
      { type: 'link', text: 'www.example.com', href: 'https://www.example.com' },
      { type: 'text', text: ' now' },
    ])
  })

  it('handles multiple URLs and newlines', () => {
    expect(
      splitTextIntoLinkSegments('a https://a.io\nb https://b.io'),
    ).toEqual([
      { type: 'text', text: 'a ' },
      { type: 'link', text: 'https://a.io', href: 'https://a.io' },
      { type: 'text', text: '\nb ' },
      { type: 'link', text: 'https://b.io', href: 'https://b.io' },
    ])
  })

  it('does not linkify non-http schemes or mid-word www', () => {
    expect(splitTextIntoLinkSegments('ftp://x javascript:alert(1)')).toEqual([
      { type: 'text', text: 'ftp://x javascript:alert(1)' },
    ])
    expect(splitTextIntoLinkSegments('awww.cute')).toEqual([
      { type: 'text', text: 'awww.cute' },
    ])
  })

  it('demotes degenerate matches to text without losing characters', () => {
    const segments = splitTextIntoLinkSegments('see www.. hm')
    expect(segments.every((segment) => segment.type === 'text')).toBe(true)
    expect(segments.map((segment) => segment.text).join('')).toBe('see www.. hm')
  })
})

describe('firstLinkHref', () => {
  it('returns the first resolvable href', () => {
    expect(firstLinkHref('x www.a.io then https://b.io')).toBe('https://www.a.io')
  })

  it('returns null when there is none', () => {
    expect(firstLinkHref('plain text')).toBeNull()
    expect(firstLinkHref(null)).toBeNull()
  })
})
