/**
 * @file normalizeAuthRedirect.ts
 * @description Rewrites auth redirects that land outside the hash so the hash-based router can read them.
 *
 * Project: Group Based 5703 Capstone Project
 * Group: CS17-1
 * Team: Frontend
 *
 * File Type: Router Helper
 * Purpose: Recover backend auth redirects whose path or query was placed outside the URL fragment.
 */

const DIRECT_AUTH_PATHS = ['/auth/callback', '/auth/reset-password', '/auth/set-password']

export const normalizeDirectAuthRedirect = () => {
  const { pathname, search, hash } = window.location

  if (hash) {
    return
  }

  if (DIRECT_AUTH_PATHS.includes(pathname)) {
    window.history.replaceState(null, '', `/#${pathname}${search}`)
    return
  }

  // Magic-link error redirects are built from a fragment-stripped base, so ?error= strands in the real
  // query string where the hash router cannot see it. Recover it onto the callback route.
  if (new URLSearchParams(search).has('error')) {
    window.history.replaceState(null, '', `/#/auth/callback${search}`)
  }
}
