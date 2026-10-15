// All rows on one page, as a rows-per-page choice.
export const DATA_TABLE_ALL = 0

// Rows per page on every table built with AppDataTable.
export const DATA_TABLE_PAGE_SIZES = [7, 15, 30, DATA_TABLE_ALL]

// The shared table's heading row and shortest row, in px, as its CSS sets them.
export const DATA_TABLE_HEAD_HEIGHT = 50
export const DATA_TABLE_ROW_HEIGHT = 56
// A row of two separate lines, like a name with an email under it.
export const DATA_TABLE_TWO_LINE_ROW_HEIGHT = 70
// The bar under the table: rows per page and the pager.
export const DATA_TABLE_BOTTOM_HEIGHT = 52
// The table's own sideways scrollbar and outline.
export const DATA_TABLE_EXTRA_HEIGHT = 20

// The site's green top bar, which stays at the top as the page scrolls.
export const siteHeaderHeight = () => document.querySelector<HTMLElement>('header.header')?.offsetHeight ?? 0

// The room on screen for a table's rows: the window under the site's top bar,
// less the table's headings, its bottom bar and its sideways scrollbar, so
// the whole table from headings to bottom bar fits on screen at once.
export const tableRowRoom = (
  headHeight = DATA_TABLE_HEAD_HEIGHT,
  bottomHeight = DATA_TABLE_BOTTOM_HEIGHT,
  extraHeight = DATA_TABLE_EXTRA_HEIGHT,
) => window.innerHeight - siteHeaderHeight() - headHeight - bottomHeight - extraHeight

// The most rows a table could fit on screen, were each as short as
// ``rowHeight``: what a table starts on, before counting its first rows'
// real heights (see AppDataTable). A table that always showed every row
// starts on All instead, by passing it as its page size.
export const fitPageSize = (rowHeight = DATA_TABLE_ROW_HEIGHT, headHeight = DATA_TABLE_HEAD_HEIGHT) =>
  Math.max(1, Math.floor(tableRowRoom(headHeight) / rowHeight))

// What to ask the server for: All is every row, and the server pages by
// count, so it gets more than any list will hold.
export const serverPageLimit = (size: number) => (size === DATA_TABLE_ALL ? 10000 : size)

// A cell's text: a list joined with commas, and a dash when there's nothing.
export const cellText = (row: Record<string, unknown>, key: string) => {
  const value = row[key]
  if (Array.isArray(value)) return value.map((item) => String(item ?? '').trim()).filter(Boolean).join(', ') || '—'
  const text = String(value ?? '').trim()
  return text || '—'
}
