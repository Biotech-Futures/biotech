// Splits chat text into plain-text and link segments so templates can render
// anchors from text nodes only — never v-html. Mirrors the backend URL
// detector (apps/chat/og_extractor.py): http(s) URLs or bare www. hosts, with
// trailing punctuation kept out of the link.
export interface LinkifySegment {
  type: 'text' | 'link'
  text: string
  href?: string
}

const URL_PATTERN = /https?:\/\/[^\s<>"']+|(?<![\w@.])www\.[^\s<>"']+/gi
const TRAILING_PUNCTUATION = /[.,!?;:)\]'"]+$/

const countChar = (haystack: string, needle: string): number =>
  haystack.split(needle).length - 1

// Trims trailing punctuation, but re-claims ')' that closes a '(' inside the
// URL so wiki-style links (…/Rust_(programming_language)) stay intact.
const trimTrailing = (raw: string): string => {
  let cleaned = raw.replace(TRAILING_PUNCTUATION, '')
  while (
    raw[cleaned.length] === ')' &&
    countChar(cleaned, '(') > countChar(cleaned, ')')
  ) {
    cleaned += ')'
  }
  return cleaned
}

const toHref = (candidate: string): string | null => {
  if (/^https?:\/\/\S{3,}$/i.test(candidate)) return candidate
  if (/^www\.\S{2,}$/i.test(candidate)) return `https://${candidate}`
  return null
}

export const splitTextIntoLinkSegments = (text: string | null | undefined): LinkifySegment[] => {
  const source = String(text ?? '')
  if (!source) return []

  const segments: LinkifySegment[] = []
  let cursor = 0
  URL_PATTERN.lastIndex = 0
  let match = URL_PATTERN.exec(source)

  while (match) {
    const cleaned = trimTrailing(match[0])
    const href = toHref(cleaned)
    if (match.index > cursor) {
      segments.push({ type: 'text', text: source.slice(cursor, match.index) })
    }
    if (href) {
      segments.push({ type: 'link', text: cleaned, href })
    } else {
      segments.push({ type: 'text', text: cleaned })
    }
    // Re-scan from the end of the cleaned match so stripped trailing
    // punctuation flows into the following text segment.
    cursor = match.index + cleaned.length
    URL_PATTERN.lastIndex = cursor
    match = URL_PATTERN.exec(source)
  }

  if (cursor < source.length) {
    segments.push({ type: 'text', text: source.slice(cursor) })
  }
  return segments
}

export const firstLinkHref = (text: string | null | undefined): string | null => {
  const link = splitTextIntoLinkSegments(text).find((segment) => segment.type === 'link')
  return link?.href ?? null
}
