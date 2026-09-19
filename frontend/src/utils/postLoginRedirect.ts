import type { Router } from 'vue-router'
import { formatTimeZoneLabel, getBrowserTimeZone, normalizeTimeZone } from '@/utils/date'

interface AdminAwareAuth {
  isAdmin: boolean
  mustChangePassword: boolean
  timeZone?: string
  user?: {
    id?: number | string
    timezone?: string | null
  } | null
}

const TIMEZONE_PROMPT_SESSION_PREFIX = 'timezone-mismatch-prompted'

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

export const redirectAfterLogin = async (auth: AdminAwareAuth, router: Router) => {
  if (auth.mustChangePassword) {
    await router.replace('/auth/set-password')
    return
  }

  if (auth.isAdmin) {
    await router.replace('/admin')
    return
  }

  if (shouldPromptForTimezoneMismatch(auth)) {
    await router.replace('/profile')
    return
  }

  try {
    await router.replace('/dashboard')
  } catch {
    window.location.href = '/#/dashboard'
  }
}
