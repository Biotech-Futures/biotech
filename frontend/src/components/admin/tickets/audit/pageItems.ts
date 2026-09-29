/**
 * Which page buttons the audit footer shows. Ported from
 * adminweb/src/components/ui/pagination-nav.tsx (getPageItems), the shared
 * footer the React audit page used. The portal's AdminDataTable has Previous
 * and Next only, which would leave page 40 of a long log forty clicks away.
 */
export type PageItem = number | 'ellipsis'

const MAX_BUTTONS = 7

// Sliding window of page numbers with the first and last page always pinned.
// A single otherwise-hidden page is shown inline instead of behind an ellipsis.
export function pageItems(current: number, total: number): PageItem[] {
  if (total <= MAX_BUTTONS) {
    return Array.from({ length: total }, (_, i) => i + 1)
  }

  const windowSize = MAX_BUTTONS - 4 // slots between the pinned first/last + 2 ellipses
  let start = Math.max(2, current - Math.floor(windowSize / 2))
  let end = start + windowSize - 1
  if (end > total - 1) {
    end = total - 1
    start = end - windowSize + 1
  }

  const items: PageItem[] = [1]
  if (start > 3) items.push('ellipsis')
  else for (let p = 2; p < start; p++) items.push(p)
  for (let p = start; p <= end; p++) items.push(p)
  if (end < total - 2) items.push('ellipsis')
  else for (let p = end + 1; p < total; p++) items.push(p)
  items.push(total)
  return items
}
