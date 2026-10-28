/**
 * Upload student details, from an .xlsx: the browser can't read one itself,
 * so the server sends its first sheet back as CSV text
 * (POST registration/sheet/), to check as a CSV is checked. Nor write one: the
 * template to download is made there too (POST registration/sheet/template/).
 */
import { apiErrorFromResponse } from '@/utils/apiError'
import { buildSessionHeaders, ensureCsrfCookie } from '@/utils/csrf'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

/** An .xlsx, rather than a CSV. */
export const isXlsx = (file: File) => /\.xlsx$/i.test(file.name)

export async function sheetAsCsv(file: File): Promise<string> {
  await ensureCsrfCookie(API_BASE_URL)
  const form = new FormData()
  form.append('file', file)
  const response = await fetch(`${API_BASE_URL}/api/v1/registration/sheet/`, {
    method: 'POST',
    credentials: 'include',
    headers: buildSessionHeaders({ includeCSRF: true, isFormData: true, headers: { Accept: 'application/json' } }),
    body: form,
  })
  if (!response.ok) throw await apiErrorFromResponse(response)
  return ((await response.json()) as { csv: string }).csv
}

/** The template as an .xlsx: ``header``, then ``example`` with ``note``
 *  beside it. */
export async function templateSheet(header: string[], example: string[], note: string): Promise<Blob> {
  await ensureCsrfCookie(API_BASE_URL)
  const response = await fetch(`${API_BASE_URL}/api/v1/registration/sheet/template/`, {
    method: 'POST',
    credentials: 'include',
    headers: buildSessionHeaders({ includeCSRF: true }),
    body: JSON.stringify({ header, example, note }),
  })
  if (!response.ok) throw await apiErrorFromResponse(response)
  return response.blob()
}
