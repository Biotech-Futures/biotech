/**
 * Setting a password straight after registering. Someone registering
 * themselves (a student, mentor or supervisor) gets a token with their
 * receipt; the registration page keeps it in this tab and goes to the Set
 * password page, which sends it with the password they choose
 * (POST registration/password/). Students and supervisors are signed in by
 * it; a mentor's account waits for an admin to activate it.
 *
 * A student someone else registered (a teammate, their supervisor or an
 * admin) is emailed a link to that page with a token of their own
 * (?token=), which lasts 14 days. Registered without all their guardian's
 * details, they give those too (GET registration/password/ says so).
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

export interface RegistrationGuardian {
  first_name: string
  last_name: string
  email: string
}

export interface RegistrationPasswordCheck {
  /** A student registered without all their guardian's details. */
  needsGuardian: boolean
  /** What's on file of them, while some is missing. */
  guardian: RegistrationGuardian | null
  /** Registered by others: they agree to the BIOTech Futures policies here. */
  needsPolicies: boolean
}

/** Whether the token still works, and whether they give their guardian too. */
export async function checkRegistrationPassword(token: string): Promise<RegistrationPasswordCheck> {
  const response = await fetch(`${ENDPOINT}?${new URLSearchParams({ token })}`, { credentials: 'include' })
  if (!response.ok) throw await apiErrorFromResponse(response, 'This link to set your password could not be opened.')
  const data = (await response.json().catch(() => null)) as Partial<RegistrationPasswordCheck> | null
  return {
    needsGuardian: data?.needsGuardian === true,
    guardian: data?.guardian ?? null,
    needsPolicies: data?.needsPolicies === true,
  }
}

/** Set their password (with their guardian, and agreeing to the policies,
 *  when asked): whether they're signed in by it. */
export async function setRegistrationPassword(
  token: string,
  password: string,
  guardian?: RegistrationGuardian,
  policiesAgreed = false,
): Promise<boolean> {
  const response = await fetch(ENDPOINT, {
    method: 'POST',
    credentials: 'include',
    headers: buildSessionHeaders(),
    body: JSON.stringify({
      token,
      password,
      ...(guardian ? { guardian } : {}),
      ...(policiesAgreed ? { policiesAgreed } : {}),
    }),
  })
  if (!response.ok) throw await apiErrorFromResponse(response, 'Could not set your password. Please try again.')
  const data = (await response.json().catch(() => null)) as { signedIn?: unknown; csrfToken?: unknown } | null
  if (data?.signedIn !== true) return false
  // Signing in rotates the CSRF token: carry on with the new one.
  if (!setCsrfToken(data.csrfToken)) resetCsrfToken()
  return true
}
