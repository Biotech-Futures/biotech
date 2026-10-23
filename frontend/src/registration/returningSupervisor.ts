/**
 * A supervisor back for a new year (POST registration/returning-supervisor/):
 * Start new year deactivated their account, and supervisors don't register
 * themselves, so they confirm their email with a sign-in code instead. That
 * brings the account back and signs them in, to register their students as
 * before. Only while registration is open.
 */
import { apiErrorFromResponse } from '@/utils/apiError'
import { buildSessionHeaders, ensureCsrfCookie, resetCsrfToken, setCsrfToken } from '@/utils/csrf'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
const ENDPOINT = `${API_BASE_URL}/api/v1/registration/returning-supervisor/`

async function post(url: string, body: Record<string, string>, fallback: string): Promise<unknown> {
  await ensureCsrfCookie(API_BASE_URL)
  const response = await fetch(url, {
    method: 'POST',
    credentials: 'include',
    headers: buildSessionHeaders({ includeCSRF: true }),
    body: JSON.stringify(body),
  })
  if (!response.ok) throw await apiErrorFromResponse(response, fallback)
  return response.json().catch(() => null)
}

/** Email the code: the same answer whether or not it's a supervisor's address. */
export async function sendReturningSupervisorCode(email: string): Promise<void> {
  await post(ENDPOINT, { email }, "Couldn't send the code. Try again.")
}

/** Check the code: the supervisor is reactivated and signed in. */
export async function confirmReturningSupervisor(email: string, code: string): Promise<void> {
  const data = (await post(`${ENDPOINT}confirm/`, { email, code }, "That code didn't work. Check it and try again.")) as {
    csrfToken?: unknown
  } | null
  // Signing in rotates the CSRF token: carry on with the new one.
  if (!setCsrfToken(data?.csrfToken)) resetCsrfToken()
}
