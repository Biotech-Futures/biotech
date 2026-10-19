import type { Router } from 'vue-router'
import { formatTimeZoneLabel, getBrowserTimeZone, normalizeTimeZone } from '@/utils/date'

interface AdminAwareAuth {
  isAdmin: boolean
  isSupervisor?: boolean
  mustChangePassword: boolean
  timeZone?: string
  user?: {
    id?: number | string
    timezone?: string | null
  } | null
}

const TIMEZONE_PROMPT_SESSION_PREFIX = 'timezone-mismatch-prompted'

// The page a signed-out visitor asked for, e.g. an email's link to their
// profile, so signing in takes them there. Kept in localStorage, not the
// tab: the login code email's magic link opens a new tab.
const RETURN_TO_KEY = 'btf-return-to'
// Long enough to sign in with an emailed code; a stale one is ignored.
const RETURN_TO_MAX_AGE_MS = 60 * 60 * 1000

/** A page inside the app worth coming back to, not a sign-in page or another site. */
const isReturnable = (path: string) =>
  path.startsWith('/') &&
  !path.startsWith('//') &&
  !['/', '/login', '/dashboard', '/admin'].includes(path.split('?')[0]) &&
  !path.startsWith('/auth/')

/** Remember the page a signed-out visitor asked for (see RETURN_TO_KEY). */
export const rememberReturnTo = (path: string) => {
  if (!isReturnable(path)) return
  try {
    window.localStorage.setItem(RETURN_TO_KEY, JSON.stringify({ path, at: Date.now() }))
  } catch {
    // Storage blocked: they land on their usual page instead.
  }
}

/** The remembered page, once: it's forgotten as it's taken. Null when there's
 *  none, it's over an hour old, or the app has no such page. */
export const takeReturnTo = (router: Router): string | null => {
  let saved: { path?: unknown; at?: unknown } | null = null
  try {
    saved = JSON.parse(window.localStorage.getItem(RETURN_TO_KEY) || 'null')
    window.localStorage.removeItem(RETURN_TO_KEY)
  } catch {
    return null
  }
  const path = typeof saved?.path === 'string' ? saved.path : ''
  const at = typeof saved?.at === 'number' ? saved.at : 0
  if (!isReturnable(path) || Date.now() - at > RETURN_TO_MAX_AGE_MS) return null
  // An unknown page only falls through to the catch-all route.
  const matched = router.resolve(path).matched
  if (!matched.length || matched.some((record) => record.path.includes(':pathMatch'))) return null
  return path
}

const shouldPromptForTimezoneMismatch = (auth: AdminAwareAuth) => {
  if (typeof window === 'undefined' || auth.isAdmin || auth.mustChangePassword) return false

  const accountTimeZone = normalizeTimeZone(auth.timeZone || auth.user?.timezone)
  const browserTimeZone = getBrowserTimeZone()
  if (accountTimeZone === browserTimeZone) return false

  const userKey = auth.user?.id ?? 'current'
  const sessionKey = `${TIMEZONE_PROMPT_SESSION_PREFIX}:${userKey}`
  if (window.sessionStorage.getItem(sessionKey) === '1') return false

  window.sessionStorage.setItem(sessionKey, '1')
  return window.confirm(
    `Your account timezone is ${formatTimeZoneLabel(accountTimeZone)}, but this device is using ${formatTimeZoneLabel(browserTimeZone)}.\n\nPress OK to review your timezone in Profile, or Cancel to continue with your current account timezone.`
  )
}

/**
 * Where someone goes once signed in: setting their password first if they
 * must (the remembered page waits for after that), else the page they asked
 * for while signed out, else their usual home.
 */
export const redirectAfterLogin = async (auth: AdminAwareAuth, router: Router) => {
  if (auth.mustChangePassword) {
    await router.replace('/auth/set-password')
    return
  }

  const returnTo = takeReturnTo(router)

  if (auth.isAdmin) {
    await router.replace(returnTo || '/admin')
    return
  }

  if (auth.isSupervisor) {
    await router.replace(returnTo || '/profile')
    return
  }

  if (shouldPromptForTimezoneMismatch(auth)) {
    // A link to their profile already lands there, with whatever it opens.
    await router.replace(returnTo?.startsWith('/profile') ? returnTo : '/profile')
    return
  }

  const destination = returnTo || '/dashboard'
  try {
    await router.replace(destination)
  } catch {
    window.location.href = `/#${destination}`
  }
}
