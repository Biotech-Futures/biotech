// Rows per page on every table built with AppDataTable.
export const DATA_TABLE_PAGE_SIZES = [7, 15, 30]

// A cell's text: a list joined with commas, and a dash when there's nothing.
export const cellText = (row: Record<string, unknown>, key: string) => {
  const value = row[key]
  if (Array.isArray(value)) return value.map((item) => String(item ?? '').trim()).filter(Boolean).join(', ') || '—'
  const text = String(value ?? '').trim()
  return text || '—'
}
