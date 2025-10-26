import { defineStore } from 'pinia'
import { safeJson } from '@/utils/http'
import { useAuthStore } from '@/stores/auth'

const DEFAULT_FILTERS = {
  track: 'Global',
  role: '',
  status: '',
  search: '',
  page: 1
}

const DEFAULT_FILTER_OPTIONS = {
  tracks: [],
  roles: ['student', 'mentor', 'supervisor', 'admin'],
  statuses: ['active', 'pending', 'inactive']
}

const mapAdminUser = (payload = {}) => ({
  id: payload.id,
  name: payload.name || payload.email || '',
  email: payload.email || '',
  role: payload.role || 'student',
  track: payload.track || '',
  status: payload.status || 'pending'
})

export const useAdminStore = defineStore('admin', {
  state: () => ({
    stats: null,
    statsLoading: false,
    statsError: null,
    users: [],
    usersLoading: false,
    usersError: null,
    pagination: {
      count: 0,
      next: null,
      previous: null,
      pageSize: 0
    },
    filters: { ...DEFAULT_FILTERS },
    updatingStatus: {},
    filterOptions: { ...DEFAULT_FILTER_OPTIONS },
    filterOptionsLoading: false,
    filterOptionsError: null,
    detailCache: {},
    detailLoading: {},
    creatingUser: false,
    savingUser: {},
    exporting: false,
    deletingUser: {}
  }),
  actions: {
    reset() {
      this.stats = null
      this.statsLoading = false
      this.statsError = null
      this.users = []
      this.usersLoading = false
      this.usersError = null
      this.pagination = {
        count: 0,
        next: null,
        previous: null,
        pageSize: 0
      }
      this.filters = { ...DEFAULT_FILTERS }
      this.updatingStatus = {}
      this.filterOptions = { ...DEFAULT_FILTER_OPTIONS }
      this.filterOptionsLoading = false
      this.filterOptionsError = null
      this.detailCache = {}
      this.detailLoading = {}
      this.creatingUser = false
      this.savingUser = {}
      this.exporting = false
      this.deletingUser = {}
    },

    _mergeFilters(overrides = {}) {
      return {
        track: overrides.track ?? this.filters.track,
        role: overrides.role ?? this.filters.role,
        status: overrides.status ?? this.filters.status,
        search: overrides.search ?? this.filters.search,
        page: overrides.page ?? this.filters.page ?? DEFAULT_FILTERS.page
      }
    },

    _buildQueryParams(filters) {
      const params = new URLSearchParams()
      if (filters.track && filters.track.toLowerCase() !== 'global') {
        params.append('track', filters.track)
      }
      if (filters.search) params.append('search', filters.search)
      if (filters.role) params.append('role', filters.role)
      if (filters.status) params.append('status', filters.status)
      if (filters.page && filters.page > 1) {
        params.append('page', String(filters.page))
      }
      return params
    },

    async fetchStats({ track } = {}) {
      const auth = useAuthStore()
      const targetTrack = track ?? this.filters.track

      this.statsLoading = true
      this.statsError = null

      try {
        const params = new URLSearchParams()
        if (targetTrack && targetTrack.toLowerCase() !== 'global') {
          params.append('track', targetTrack)
        }

        const response = await auth.authenticatedFetch(
          `/admin/stats/${params.toString() ? `?${params.toString()}` : ''}`
        )
        const data = await safeJson(response)

        if (!response.ok) {
          throw new Error(data?.error || 'Failed to load admin statistics')
        }

        this.stats = data
        this.filters.track = targetTrack || DEFAULT_FILTERS.track
        return data
      } catch (error) {
        this.statsError = error
        throw error
      } finally {
        this.statsLoading = false
      }
    },

    async fetchUsers({ track, search, role, status, page } = {}) {
      const auth = useAuthStore()
      const nextFilters = this._mergeFilters({ track, search, role, status, page })

      this.usersLoading = true
      this.usersError = null

      try {
        const params = this._buildQueryParams(nextFilters)
        const response = await auth.authenticatedFetch(
          `/admin/users/${params.toString() ? `?${params.toString()}` : ''}`
        )
        const data = await safeJson(response)
        if (!response.ok) {
          throw new Error(data?.error || 'Failed to load users')
        }

        const results = Array.isArray(data?.results)
          ? data.results
          : Array.isArray(data)
            ? data
            : []

        this.users = results.map(mapAdminUser)
        this.pagination = {
          count: data?.count ?? results.length,
          next: data?.next ?? null,
          previous: data?.previous ?? null,
          pageSize: results.length
        }
        this.filters = nextFilters
        return this.users
      } catch (error) {
        this.usersError = error
        throw error
      } finally {
        this.usersLoading = false
      }
    },

    async fetchFilterOptions({ forceRefresh = false } = {}) {
      if (this.filterOptionsLoading) return this.filterOptions
      if (!forceRefresh && this.filterOptions.tracks.length) return this.filterOptions

      this.filterOptionsLoading = true
      this.filterOptionsError = null

      try {
        const auth = useAuthStore()
        const response = await auth.authenticatedFetch('/admin/users/filters/')
        const data = await safeJson(response)

        if (!response.ok) {
          throw new Error(data?.error || 'Failed to load filter options')
        }

        this.filterOptions = {
          tracks: Array.from(new Set(['Global', ...(data?.tracks || [])])),
          roles: data?.roles?.length ? data.roles : [...DEFAULT_FILTER_OPTIONS.roles],
          statuses: data?.statuses?.length
            ? data.statuses
            : [...DEFAULT_FILTER_OPTIONS.statuses]
        }

        return this.filterOptions
      } catch (error) {
        this.filterOptionsError = error
        throw error
      } finally {
        this.filterOptionsLoading = false
      }
    },

    async fetchUserDetail(userId, { forceRefresh = false } = {}) {
      if (!userId) return null
      if (!forceRefresh && this.detailCache[userId]) {
        return this.detailCache[userId]
      }

      this.detailLoading = { ...this.detailLoading, [userId]: true }
      try {
        const auth = useAuthStore()
        const response = await auth.authenticatedFetch(`/admin/users/${userId}/`)
        const data = await safeJson(response)
        if (!response.ok) {
          throw new Error(data?.error || 'Failed to load user details')
        }
        this.detailCache = { ...this.detailCache, [userId]: data }
        return data
      } finally {
        const { [userId]: _discard, ...rest } = this.detailLoading
        this.detailLoading = rest
      }
    },

    async createUser(payload) {
      const auth = useAuthStore()
      this.creatingUser = true

      try {
        const response = await auth.authenticatedFetch('/admin/users/', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        })

        const data = await safeJson(response)
        if (!response.ok) {
          throw new Error(data?.error || 'Failed to create user')
        }

        await this.fetchStats({ track: this.filters.track })
        await this.fetchUsers(this.filters)

        return mapAdminUser(data)
      } finally {
        this.creatingUser = false
      }
    },

    async updateUser(userId, payload) {
      if (!userId) {
        throw new Error('User ID is required')
      }

      const auth = useAuthStore()
      this.savingUser = { ...this.savingUser, [userId]: true }

      try {
        const response = await auth.authenticatedFetch(`/admin/users/${userId}/`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        })
        const data = await safeJson(response)
        if (!response.ok) {
          throw new Error(data?.error || 'Failed to update user')
        }

        const mapped = mapAdminUser(data)
        this.users = this.users.map((user) => (user.id === userId ? mapped : user))
        this.detailCache = { ...this.detailCache, [userId]: data }

        await this.fetchStats({ track: this.filters.track })
        return data
      } finally {
        const { [userId]: _discard, ...rest } = this.savingUser
        this.savingUser = rest
      }
    },

    async updateUserStatus({ userId, status }) {
      if (!userId || !status) {
        throw new Error('User ID and status are required to update a user')
      }

      const auth = useAuthStore()
      this.updatingStatus = { ...this.updatingStatus, [userId]: true }

      try {
        const response = await auth.authenticatedFetch(
          `/admin/users/${userId}/status/`,
          {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status })
          }
        )

        const data = await safeJson(response)
        if (!response.ok) {
          throw new Error(data?.error || 'Failed to update user status')
        }

        const mapped = mapAdminUser(data?.user || {})
        this.users = this.users.map((user) =>
          user.id === userId ? mapped : user
        )

        if (this.detailCache[userId]) {
          this.detailCache = {
            ...this.detailCache,
            [userId]: {
              ...this.detailCache[userId],
              status: mapped.status
            }
          }
        }

        try {
          await this.fetchStats({ track: this.filters.track })
        } catch {
          // ignore stats refresh errors to avoid interrupting the flow
        }

        return mapped
      } finally {
        const { [userId]: _discard, ...rest } = this.updatingStatus
        this.updatingStatus = rest
      }
    },

    async exportUsers() {
      const auth = useAuthStore()
      this.exporting = true

      try {
        const params = this._buildQueryParams(this.filters)
        const response = await auth.authenticatedFetch(
          `/admin/users/export/${params.toString() ? `?${params.toString()}` : ''}`
        )

        if (!response.ok) {
          const data = await safeJson(response)
          throw new Error(data?.error || 'Failed to export users')
        }

        const blob = await response.blob()
        const disposition = response.headers.get('Content-Disposition') || ''
        const match = disposition.match(/filename="?([^"]+)"?/)
        const filename = match?.[1] || 'users-export.csv'

        return { blob, filename }
      } finally {
        this.exporting = false
      }
    },

    async deleteUser(userId) {
      if (!userId) {
        throw new Error('User ID is required')
      }

      const auth = useAuthStore()
      this.deletingUser = { ...this.deletingUser, [userId]: true }

      try {
        const response = await auth.authenticatedFetch(`/admin/users/${userId}/`, {
          method: 'DELETE'
        })

        if (!response.ok && response.status !== 204) {
          const data = await safeJson(response)
          throw new Error(data?.error || 'Failed to delete user')
        }

        this.users = this.users.filter((user) => user.id !== userId)
        const { [userId]: _discard, ...rest } = this.detailCache
        this.detailCache = rest

        await this.fetchStats({ track: this.filters.track })
        await this.fetchUsers(this.filters)
      } finally {
        const { [userId]: _discard, ...rest } = this.deletingUser
        this.deletingUser = rest
      }
    }
  }
})
