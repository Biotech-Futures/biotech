/**
 * A student group's code (6 digits, apart from its name), held for it while the student registers
 * (POST registration/group-code/), so they can save it and share it with
 * their teammates. The group takes it when it's registered, by its token.
 */
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

export type HeldGroupCode = { code: string; token: string; expiresAt: string }

/** A group code is 6 digits. */
export const GROUP_CODE_PATTERN = /^\d{6}$/

/** Whether a registered group has this code, and has room (under 5). */
export type GroupCodeCheck =
  | { state: 'found'; members: number }
  | { state: 'full'; members: number }
  | { state: 'missing' }
  | { state: 'unavailable' }

/** Hold the next group code, or null if none could be held (the group then
 *  gets its code when it's registered). */
export async function holdGroupCode(): Promise<HeldGroupCode | null> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/v1/registration/group-code/`, {
      method: 'POST',
      headers: { Accept: 'application/json' },
    })
    if (!response.ok) return null
    const body = await response.json()
    return typeof body?.code === 'string' && typeof body?.token === 'string'
      ? { code: body.code, token: body.token, expiresAt: String(body.expires_at ?? '') }
      : null
  } catch {
    return null
  }
}

/** Check a group's code, to join it (GET registration/group-code/<code>/).
 *  "unavailable" if it couldn't be checked: registering then decides. */
export async function checkGroupCode(code: string): Promise<GroupCodeCheck> {
  try {
    const response = await fetch(
      `${API_BASE_URL}/api/v1/registration/group-code/${encodeURIComponent(code)}/`,
      { headers: { Accept: 'application/json' } },
    )
    if (response.status === 404) return { state: 'missing' }
    if (!response.ok) return { state: 'unavailable' }
    const body = await response.json()
    const members = Number(body?.members ?? 0)
    return body?.full ? { state: 'full', members } : { state: 'found', members }
  } catch {
    return { state: 'unavailable' }
  }
}
