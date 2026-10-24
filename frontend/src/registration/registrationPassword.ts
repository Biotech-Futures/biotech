/**
 * Setting a password straight after registering. Someone registering
 * themselves (a student, mentor or supervisor) gets a token with their
 * receipt; the registration page keeps it in this tab and goes to the Set
 * password page, which sends it with the password they choose
 * (POST registration/password/). Students and supervisors are signed in by
 * it; a mentor's account waits for an admin to activate it.
 */
import { apiErrorFromResponse } from '@/utils/apiError'
import { buildSessionHeaders, resetCsrfToken, setCsrfToken } from '@/utils/csrf'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
const ENDPOINT = `${API_BASE_URL}/api/v1/registration/password/`
const KEY = 'biotech.registration.password'

export const REGISTRATION_PASSWORD_PATH = '/register/password'

export interface HeldRegistrationPassword {
  token: string
  /** A mentor, whose account an admin activates before they can sign in. */
  mentor: boolean
}

/** Keep a new registration's token for the Set password page. */
export function holdRegistrationPassword(token: string, mentor: boolean) {
  try {
    sessionStorage.setItem(KEY, JSON.stringify({ token, mentor }))
  } catch {
    // No session storage: the page asks them to sign in instead.
  }
}

/** The token kept, if there is one. */
export function heldRegistrationPassword(): HeldRegistrationPassword | null {
  try {
    const held = JSON.parse(sessionStorage.getItem(KEY) || 'null') as HeldRegistrationPassword | null
    return held && typeof held.token === 'string' && held.token ? { token: held.token, mentor: Boolean(held.mentor) } : null
  } catch {
    return null
  }
}

/** Let it go, once it's used. */
export function releaseRegistrationPassword() {
  try {
    sessionStorage.removeItem(KEY)
  } catch {
    // Nothing kept.
  }
}

/** Set their password: whether they're signed in by it. */
export async function setRegistrationPassword(token: string, password: string): Promise<boolean> {
  const response = await fetch(ENDPOINT, {
    method: 'POST',
    credentials: 'include',
    headers: buildSessionHeaders(),
    body: JSON.stringify({ token, password }),
  })
  if (!response.ok) throw await apiErrorFromResponse(response, 'Could not set your password. Please try again.')
  const data = (await response.json().catch(() => null)) as { signedIn?: unknown; csrfToken?: unknown } | null
  if (data?.signedIn !== true) return false
  // Signing in rotates the CSRF token: carry on with the new one.
  if (!setCsrfToken(data.csrfToken)) resetCsrfToken()
  return true
}
