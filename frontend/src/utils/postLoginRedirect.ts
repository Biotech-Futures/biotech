import type { Router } from 'vue-router'

interface AdminAwareAuth {
  isAdmin: boolean
}

const ADMIN_FRONTEND_URL = import.meta.env.VITE_ADMIN_FRONTEND_URL || 'https://mentoringadmin.biotechfutures.org'

export const redirectAfterLogin = async (auth: AdminAwareAuth, router: Router) => {
  if (auth.isAdmin) {
    window.location.assign(ADMIN_FRONTEND_URL)
    return
  }

  try {
    await router.replace('/dashboard')
  } catch {
    window.location.href = '/#/dashboard'
  }
}
