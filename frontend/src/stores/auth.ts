import { defineStore } from 'pinia'

import { buildSessionHeaders, ensureCsrfCookie, resetCsrfToken } from '@/utils/csrf'
import { clearAuthTokens } from '@/utils/authTokens'
import { ApiError, normalizeApiErrorBody } from '@/utils/apiError'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

interface User {
  id: number
  email: string
  first_name: string
  last_name: string
  status?: boolean
  current_role_id?: number | null
  current_role_name?: string | null
  is_staff?: boolean
  is_superuser?: boolean
  track?: number | null
  state?: number | null
  pg_firstname?: string | null
  pg_lastname?: string | null
  year_lvl?: string | null
  school_name?: string | null
  join_perm?: boolean | null
  ment_bg?: string | null
  ment_inst?: string | null
  ment_reason?: string | null
  ment_max_groups?: number | null
  supervisor_school_name?: string | null
  supervised_students?: Array<{
    id: number
    first_name: string
    last_name: string
    email: string
    relationship_type: string
  }>
}

async function parseResponseJson(response: Response): Promise<any> {
  try {
    return await response.json()
  } catch {
    return null
  }
}

type NormalizedRole = 'admin' | 'mentor' | 'supervisor' | 'student'

function resolveNormalizedRole(user: User | null): NormalizedRole {
  const rawRole = String(user?.current_role_name || '').toLowerCase()

  if (
    user?.is_staff === true ||
    user?.is_superuser === true ||
    ['admin', 'administrator', 'local_admin', 'global_admin', 'local administrator', 'global administrator'].includes(rawRole)
  ) {
    return 'admin'
  }

  if (['teacher', 'mentor'].includes(rawRole)) {
    return 'mentor'
  }

  if (rawRole === 'supervisor') {
    return 'supervisor'
  }

  return 'student'
}

async function postPasswordLogin(email: string, password: string): Promise<Response> {
  const endpoints = ['/api/v1/auth/login/', '/api/v1/login/']
  let lastResponse: Response | null = null

  for (const path of endpoints) {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      method: 'POST',
      credentials: 'include',
      headers: buildSessionHeaders({
        includeCSRF: true
      }),
      body: JSON.stringify({
        email,
        password
      })
    })

    lastResponse = response

    if (response.status !== 404) {
      return response
    }
  }

  if (!lastResponse) {
    throw new Error('Login service is unavailable right now.')
  }

  return lastResponse
}

export const useAuthStore = defineStore('auth', {
  state: () => ({
    user: null as User | null,
    initialized: false
  }),

  getters: {
    isAuthenticated: (state) => state.initialized && !!state.user,

    initials: (state) => {
      if (!state.user) return '--'

      const first = state.user.first_name?.[0] || ''
      const last = state.user.last_name?.[0] || ''
      return (first + last).toUpperCase() || state.user.email[0].toUpperCase()
    },

    normalizedRole: (state) => resolveNormalizedRole(state.user),

    isAdmin: (state) => resolveNormalizedRole(state.user) === 'admin',

    isMentor: (state) => resolveNormalizedRole(state.user) === 'mentor',

    isSupervisor: (state) => resolveNormalizedRole(state.user) === 'supervisor',

    isStudent: (state) => resolveNormalizedRole(state.user) === 'student',

    isTeacher: (state) => ['mentor', 'supervisor'].includes(resolveNormalizedRole(state.user)),

    displayName: (state) => {
      const fullName = `${state.user?.first_name || ''} ${state.user?.last_name || ''}`.trim()
      return fullName || state.user?.email || 'User'
    },

    displayTrack: (state) => String(state.user?.track ?? state.user?.state ?? 'General'),

    organizationLabel: (state) => state.user?.ment_inst || state.user?.school_name || 'BIOTech Futures',

    roleLabel: (state) => {
      const role = resolveNormalizedRole(state.user)

      if (role === 'admin') return 'Administrator'
      if (role === 'mentor') return 'Mentor'
      if (role === 'supervisor') return 'Supervisor'
      return 'Student'
    }
  },

  actions: {
    async fetchUserData() {
      try {
        const response = await fetch(`${API_BASE_URL}/api/v1/users/me/`, {
          credentials: 'include',
          headers: buildSessionHeaders()
        })

        const parsedData = await parseResponseJson(response)

        if (response.ok) {
          this.user = parsedData
          localStorage.setItem('auth.user', JSON.stringify(parsedData))
          return parsedData
        }

        if (response.status === 401) {
          clearAuthTokens()
        }

        this.user = null
        localStorage.removeItem('auth.user')
      } catch (error) {
        console.error('Failed to fetch user data:', error)
        this.user = null
        localStorage.removeItem('auth.user')
      }

      return null
    },

    async initializeAuth() {
      try {
        clearAuthTokens()
        this.hydrate()
        await this.fetchUserData()
      } finally {
        this.initialized = true
      }
    },

    async loginWithPassword(email: string, password: string) {
      clearAuthTokens()

      const csrfReady = await ensureCsrfCookie(API_BASE_URL)
      if (!csrfReady) {
        throw new Error('Could not initialize a secure session. Please refresh and try again.')
      }

      const response = await postPasswordLogin(email, password)
      const data = await parseResponseJson(response)

      if (!response.ok) {
        throw new ApiError(
          normalizeApiErrorBody(
            data,
            'Email or password is incorrect.',
            response.headers.get('X-Request-ID') || undefined,
            response.status
          ),
          response.status
        )
      }

      // Django rotates the CSRF token on login; refresh the cached value before
      // any immediate unsafe request can build headers from an empty cache.
      resetCsrfToken()
      await ensureCsrfCookie(API_BASE_URL)

      const user = await this.fetchUserData()
      if (!user) {
        throw new Error('Login succeeded, but the current user profile could not be loaded.')
      }

      this.initialized = true
      return user
    },

    loginWithUser(userData: User) {
      this.user = userData
      this.initialized = true

      try {
        localStorage.setItem('auth.user', JSON.stringify(userData))
      } catch {}
    },

    async logout() {
      try {
        await ensureCsrfCookie(API_BASE_URL)

        await fetch(`${API_BASE_URL}/services/logout/`, {
          method: 'POST',
          credentials: 'include',
          headers: buildSessionHeaders({
            includeCSRF: true
          })
        })
      } catch (error) {
        console.error('Failed to log out from backend session:', error)
      } finally {
        this.user = null
        this.initialized = true
        clearAuthTokens()
        resetCsrfToken()

        try {
          localStorage.removeItem('auth.user')
        } catch {}
      }
    },

    hydrate() {
      try {
        const rawUser = localStorage.getItem('auth.user')
        if (rawUser) {
          this.user = JSON.parse(rawUser)
        }
      } catch {}
    },
  },
})
