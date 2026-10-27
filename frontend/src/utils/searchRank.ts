// Search that reads "BTF 7", "btf07" and "BTF-7" alike, and lists what it
// finds from the most relevant to the least.

/** Lower case, spaces collapsed, no space or dash between a word and its
 *  number ("btf 7" → "btf7") and no leading zeros ("btf07" → "btf7"). */
export function searchForm(text: string): string {
  return text
    .trim()
    .toLowerCase()
    .replace(/\s+/g, ' ')
    .replace(/(\p{L})[\s_-]+(?=\p{N})/gu, '$1')
    .replace(/(^|\D)0+(?=\d)/g, '$1')
}

type Score = [rank: number, extra: number]

// Best first: the whole text, its start, a word or number in it, the start of
// one, anywhere; then the fewer characters beyond the query, so BTF10 comes
// before BTF111. Null when the text doesn't contain the query.
function score(text: string, query: string): Score | null {
  const value = searchForm(text)
  const extra = value.length - query.length
  if (value === query) return [0, 0]
  if (value.startsWith(query)) return [1, extra]
  const parts: string[] = value.match(/\p{L}+|\p{N}+/gu) ?? []
  if (parts.includes(query)) return [2, extra]
  if (parts.some((part) => part.startsWith(query))) return [3, extra]
  return value.includes(query) ? [4, extra] : null
}

const better = (a: Score, b: Score) => a[0] - b[0] || a[1] - b[1]

/** The items whose texts contain the query, most relevant first; equally
 *  relevant ones keep the order they came in. All of them for no query. */
export function rankBySearch<T>(items: T[], query: string, textsOf: (item: T) => string[]): T[] {
  const wanted = searchForm(query)
  if (!wanted) return items
  return items
    .map((item, index) => {
      const scores = textsOf(item)
        .map((text) => score(text, wanted))
        .filter((found): found is Score => found !== null)
      return { item, index, best: scores.sort(better)[0] }
    })
    .filter((entry) => entry.best !== undefined)
    .sort((a, b) => better(a.best!, b.best!) || a.index - b.index)
    .map((entry) => entry.item)
}
