import { defineStore } from 'pinia'

import { buildSessionHeaders, ensureCsrfCookie, resetCsrfToken, setCsrfToken } from '@/utils/csrf'
import { clearAuthTokens } from '@/utils/authTokens'
import { ApiError, normalizeApiErrorBody } from '@/utils/apiError'
import { normalizeTimeZone } from '@/utils/date'
import { BRAND_NAME } from '@/constants/brand'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

interface User {
  id: number
  email: string
  first_name: string
  last_name: string
  timezone?: string
  must_change_password?: boolean
  account_status?: string
  status?: boolean
  current_role_id?: number | null
  current_role_name?: string | null
  is_staff?: boolean
  is_superuser?: boolean
  country?: { id: number; countryName: string } | null
  state?: { id: number; stateName: string } | null
  pg_firstname?: string | null
  pg_lastname?: string | null
  year_lvl?: string | null
  school_name?: string | null
  join_perm?: boolean | null
  interests?: string[]
  supervisor_name?: string | null
  supervisor_email?: string | null
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
  // Sent by /users/me/ (MeSerializer), not by the login response; the store
  // always re-fetches /users/me/ after signing in, so they are here whenever
  // a user is. Two booleans rather than one because isSupport is true for
  // admins as well (backend serializers.py MeSerializer). isAdmin here is the
  // server's AdminScope, which is NOT what the isAdmin getter below reads.
  isAdmin?: boolean
  isSupport?: boolean
}

async function parseResponseJson(response: Response): Promise<any> {
  try {
    return await response.json()
  } catch {
    return null
  }
}

type NormalizedRole = 'admin' | 'mentor' | 'supervisor' | 'student' | 'support'

// Keyed by NormalizedRole, so a role added to the union without a label here
// fails the type check instead of being shown as somebody else's.
const ROLE_LABELS: Record<NormalizedRole, string> = {
  admin: 'Administrator',
  mentor: 'Mentor',
  supervisor: 'Supervisor',
  student: 'Student',
  support: 'Support',
}

function resolveNormalizedRole(user: User | null): NormalizedRole {
  const rawRole = String(user?.current_role_name || '').toLowerCase()

  if (
    user?.is_staff === true ||
    user?.is_superuser === true ||
    ['admin', 'administrator', 'local_admin', 'global_admin', 'local administrator', 'global administrator'].includes(rawRole)
  ) {
    return 'admin'
  }

  // A support agent's role name. It used to fall through to 'student' below,
  // so an agent signed in to a student dashboard. The role says who the
  // account is; whether it may work the queue is the separate isSupport flag.
  if (rawRole === 'support') {
    return 'support'
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

    // The ticket side reads the server's two flags, never the role name above.
    // The backend computes "SupportScope or AdminScope" once
    // (apps/tickets/permissions.py is_support) and says that OR must not be
    // written out anywhere else, so it is read here, not recomputed. It is
    // true for admins too, and for a mentor or student granted access on the
    // roster: queue access is not the role.
    canWorkTickets: (state) => state.user?.isSupport === true,

    // The server's AdminScope, which is what deleting a ticket and the
    // support roster are gated on (IsAdminScoped). The role-name isAdmin above
    // is Team 1's and can disagree with it: an account whose role says admin
    // but whose AdminScope row is gone sees admin menus that 403.
    isTicketAdmin: (state) => state.user?.isAdmin === true,

    // An account whose role is support and who is not an admin, with or
    // without queue access. They get the queue (or the page explaining why
    // they cannot have it) and nothing else. A mentor granted access is not
    // support-only: they keep their member pages and gain the queue.
    isSupportOnly: (state) =>
      resolveNormalizedRole(state.user) === 'support' && state.user?.isAdmin !== true,

    mustChangePassword: (state) => state.user?.must_change_password === true,

    timeZone: (state) => normalizeTimeZone(state.user?.timezone),

    displayName: (state) => {
      const fullName = `${state.user?.first_name || ''} ${state.user?.last_name || ''}`.trim()
      return fullName || state.user?.email || 'User'
    },

    displayRegion: (state) =>
      state.user?.state?.stateName || state.user?.country?.countryName || 'General',

    organizationLabel: (state) => state.user?.ment_inst || state.user?.school_name || BRAND_NAME,

    roleLabel: (state) => ROLE_LABELS[resolveNormalizedRole(state.user)]
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

      // Django rotates the CSRF token on login; cache the fresh value returned
      // by the backend so subsequent unsafe requests do not reuse the old one.
      if (!setCsrfToken(data?.csrfToken)) {
        resetCsrfToken()
      }

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

    async setInitialPassword(password: string) {
      const csrfReady = await ensureCsrfCookie(API_BASE_URL)
      if (!csrfReady) {
        throw new Error('Could not initialize a secure session. Please refresh and try again.')
      }

      // Non-admin first-password endpoint. The /admin/auth/ twin is IsAdminScoped
      // and 403s every student/mentor/supervisor on first login.
      const response = await fetch(`${API_BASE_URL}/api/v1/set-password/`, {
        method: 'POST',
        credentials: 'include',
        headers: buildSessionHeaders({
          includeCSRF: true
        }),
        body: JSON.stringify({
          password
        })
      })

      const data = await parseResponseJson(response)

      if (!response.ok) {
        throw new ApiError(
          normalizeApiErrorBody(
            data,
            data?.msg || 'Could not set your password. Please try again.',
            response.headers.get('X-Request-ID') || undefined,
            response.status
          ),
          response.status
        )
      }

      const user = await this.fetchUserData()
      if (!user) {
        throw new Error('Password was set, but the current user profile could not be loaded.')
      }

      return user
    },

    async updateTimeZone(timezone: string) {
      const csrfReady = await ensureCsrfCookie(API_BASE_URL)
      if (!csrfReady) {
        throw new Error('Could not initialize a secure session. Please refresh and try again.')
      }

      const response = await fetch(`${API_BASE_URL}/api/v1/users/me/`, {
        method: 'PATCH',
        credentials: 'include',
        headers: buildSessionHeaders({
          includeCSRF: true
        }),
        body: JSON.stringify({
          timezone
        })
      })

      const data = await parseResponseJson(response)

      if (!response.ok) {
        throw new ApiError(
          normalizeApiErrorBody(
            data,
            'Could not update your timezone. Please try again.',
            response.headers.get('X-Request-ID') || undefined,
            response.status
          ),
          response.status
        )
      }

      this.user = data
      localStorage.setItem('auth.user', JSON.stringify(data))
      return data
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
