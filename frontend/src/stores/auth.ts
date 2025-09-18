// Pinia auth store with JWT token support
import { defineStore } from 'pinia'

interface User {
  id: number
  email: string
  first_name: string
  last_name: string
  name: string
}

export const useAuthStore = defineStore('auth', {
  state: () => ({
    user: null as User | null,
    accessToken: null as string | null,
    refreshToken: null as string | null
  }),
  getters: {
    isAuthenticated: (s) => !!s.user && !!s.accessToken,
    isAdmin: (s) => s.user?.email?.includes('admin') || false, // Simple admin check based on email
    initials: (s) => {
      if (!s.user) return '—'
      const first = s.user.first_name?.[0] || ''
      const last = s.user.last_name?.[0] || ''
      return (first + last).toUpperCase() || s.user.email[0].toUpperCase()
    }
  },
  actions: {
    // Login with JWT tokens from backend
    loginWithTokens(userData: User, accessToken: string, refreshToken: string) {
      this.user = userData
      this.accessToken = accessToken
      this.refreshToken = refreshToken
      try {
        localStorage.setItem('auth.user', JSON.stringify(userData))
        localStorage.setItem('auth.accessToken', accessToken)
        localStorage.setItem('auth.refreshToken', refreshToken)
      } catch {}
    },
    logout() {
      this.user = null
      this.accessToken = null
      this.refreshToken = null
      try {
        localStorage.removeItem('auth.user')
        localStorage.removeItem('auth.accessToken')
        localStorage.removeItem('auth.refreshToken')
      } catch {}
    },
    hydrate() {
      try {
        const rawUser = localStorage.getItem('auth.user')
        const rawAccess = localStorage.getItem('auth.accessToken')
        const rawRefresh = localStorage.getItem('auth.refreshToken')

        if (rawUser && rawAccess) {
          this.user = JSON.parse(rawUser)
          this.accessToken = rawAccess
          this.refreshToken = rawRefresh
        }
      } catch {}
    }
  }
})
