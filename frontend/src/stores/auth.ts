// Pinia auth store with JWT token support
import { defineStore } from 'pinia'

interface User {
  id: number
  email: string
  first_name: string
  last_name: string
  name: string
  current_role_id?: number | null
  current_role_name?: string | null
  is_staff?: boolean
  is_superuser?: boolean
}

export const useAuthStore = defineStore('auth', {
  state: () => ({
    user: null as User | null,
    accessToken: null as string | null,
    refreshToken: null as string | null
  }),
  getters: {
    isAuthenticated: (s) => !!s.user, // Session-based auth - user exists means authenticated
    isAdmin: (s) => {
      // Check role name OR Django's is_staff/is_superuser flags
      return s.user?.current_role_name === 'admin' ||
             s.user?.is_staff === true ||
             s.user?.is_superuser === true ||
             false
    },
    initials: (s) => {
      if (!s.user) return '—'
      const first = s.user.first_name?.[0] || ''
      const last = s.user.last_name?.[0] || ''
      return (first + last).toUpperCase() || s.user.email[0].toUpperCase()
    }
  },
  actions: {
    // Fetch full user data from backend including roles
    async fetchUserData() {
      try {
        const response = await fetch('http://localhost:8000/api/v1/users/me/', {
          credentials: 'include', // Include session cookie
        })

        if (response.ok) {
          const userData = await response.json()
          this.user = userData
          localStorage.setItem('auth.user', JSON.stringify(userData))
          return userData
        }
      } catch (error) {
        console.error('Failed to fetch user data:', error)
      }
      return null
    },
    // Login with session-based authentication (Django sessions)
    loginWithUser(userData: User) {
      this.user = userData
      try {
        localStorage.setItem('auth.user', JSON.stringify(userData))
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

        if (rawUser) {
          this.user = JSON.parse(rawUser)
          // Also restore tokens if they exist (for backward compatibility)
          const rawAccess = localStorage.getItem('auth.accessToken')
          const rawRefresh = localStorage.getItem('auth.refreshToken')
          if (rawAccess) {
            this.accessToken = rawAccess
            this.refreshToken = rawRefresh
          }
        }
      } catch {}
    }
  }
})
