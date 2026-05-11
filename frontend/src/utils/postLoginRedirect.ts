import type { Router } from 'vue-router'

interface AdminAwareAuth {
  isAdmin: boolean
  logout?: () => Promise<void>
}

export const ADMIN_FRONTEND_URL = import.meta.env.VITE_ADMIN_FRONTEND_URL || 'https://mentoringadmin.biotechfutures.org'

export const redirectAdminToAdminPortal = async (auth: AdminAwareAuth) => {
  if (auth.logout) {
    await auth.logout()
  }

  window.location.assign(ADMIN_FRONTEND_URL)
}

export const redirectAfterLogin = async (auth: AdminAwareAuth, router: Router) => {
  if (auth.isAdmin) {
    await redirectAdminToAdminPortal(auth)
    return
  }

  try {
    await router.replace('/dashboard')
  } catch {
    window.location.href = '/#/dashboard'
  }
}
