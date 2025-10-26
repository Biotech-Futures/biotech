import { defineStore } from 'pinia'
import { safeJson } from '@/utils/http'
import { useAuthStore } from '@/stores/auth'

const mapEvent = (payload = {}) => ({
  id: payload.id,
  title: payload.title || '',
  description: payload.description || '',
  longDescription: payload.longDescription || payload.long_description || '',
  date: payload.date || '',
  time: payload.time || '',
  location: payload.location || '',
  type: payload.type || 'in-person',
  coverImage: payload.coverImage || payload.cover_image || null,
  registerLink: payload.registerLink || payload.register_link || '',
  capacity: payload.capacity ?? null,
  createdAt: payload.createdAt || payload.created_at || null,
  updatedAt: payload.updatedAt || payload.updated_at || null,
  isRegistered: payload.isRegistered ?? payload.is_registered ?? false,
  registrationCount:
    payload.registrationCount ?? payload.registration_count ?? 0,
})

export const useEventStore = defineStore('events', {
  state: () => ({
    items: [],
    loadingList: false,
    listLoaded: false,
    listError: null,
    creating: false,
    uploadingCoverIds: {},
    registeringIds: {},
    deletingIds: {},
    activeUserId: null,
  }),
  actions: {
    reset() {
      this.items = []
      this.loadingList = false
      this.listLoaded = false
      this.listError = null
      this.creating = false
      this.uploadingCoverIds = {}
      this.registeringIds = {}
      this.deletingIds = {}
      this.activeUserId = null
    },

    async fetchEvents({ forceRefresh = false, upcoming = true } = {}) {
      if (this.loadingList) return this.items

      const auth = useAuthStore()
      const userId = auth.user?.id ?? null
      if (!userId) {
        this.reset()
        return []
      }
      if (this.activeUserId !== userId) {
        this.reset()
        this.activeUserId = userId
      }

      if (this.listLoaded && !forceRefresh) return this.items

      this.loadingList = true
      this.listError = null

      try {
        const params = new URLSearchParams()
        if (upcoming) params.set('upcoming', 'true')
        const response = await auth.authenticatedFetch(
          `/events/${params.toString() ? `?${params.toString()}` : ''}`
        )
        const data = await safeJson(response)

        if (!response.ok) {
          throw new Error(data?.error || 'Failed to load events')
        }

        const results = Array.isArray(data?.results)
          ? data.results
          : Array.isArray(data)
            ? data
            : []

        this.items = results.map(mapEvent)
        this.listLoaded = true
        return this.items
      } catch (error) {
        this.listError = error
        throw error
      } finally {
        this.loadingList = false
      }
    },

    async refreshEvents(options = {}) {
      return this.fetchEvents({ ...options, forceRefresh: true })
    },

    async createEvent(payload) {
      if (this.creating) {
        throw new Error('Another event is currently being created, please wait')
      }

      this.creating = true
      try {
        const auth = useAuthStore()
        const response = await auth.authenticatedFetch('/events/', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        })

        const data = await safeJson(response)
        if (!response.ok) {
          throw new Error(data?.error || 'Failed to create event')
        }

        const mapped = mapEvent(data)
        this.items = [mapped, ...this.items]
        return mapped
      } finally {
        this.creating = false
      }
    },

    async updateCover(eventId, file) {
      if (!eventId || !file) {
        throw new Error('Missing information, cannot update cover')
      }

      this.uploadingCoverIds = { ...this.uploadingCoverIds, [eventId]: true }

      try {
        const auth = useAuthStore()
        const form = new FormData()
        form.append('coverImage', file)

        const response = await auth.authenticatedFetch(`/events/${eventId}/cover/`, {
          method: 'PUT',
          body: form,
        })

        const data = await safeJson(response)
        if (!response.ok) {
          throw new Error(data?.error || 'Failed to update cover image')
        }

        const coverUrl = data.coverImage || null
        this.items = this.items.map((item) =>
          item.id === eventId ? { ...item, coverImage: coverUrl } : item
        )
        return coverUrl
      } finally {
        const { [eventId]: _removed, ...rest } = this.uploadingCoverIds
        this.uploadingCoverIds = rest
      }
    },

    async registerEvent(eventId) {
      if (!eventId) throw new Error('Unable to identify event')

      this.registeringIds = { ...this.registeringIds, [eventId]: true }
      try {
        const auth = useAuthStore()
        const response = await auth.authenticatedFetch(
          `/events/${eventId}/register/`,
          { method: 'POST' }
        )
        const data = await safeJson(response)
        if (!response.ok) {
          throw new Error(data?.message || data?.error || 'Failed to register for event')
        }

        this.items = this.items.map((item) =>
          item.id === eventId
            ? {
                ...item,
                isRegistered: true,
                registrationCount: (item.registrationCount || 0) + 1,
              }
            : item
        )
        return data
      } finally {
        const { [eventId]: _removed, ...rest } = this.registeringIds
        this.registeringIds = rest
      }
    },

    async deleteEvent(eventId) {
      if (!eventId) return false
      this.deletingIds = { ...this.deletingIds, [eventId]: true }
      try {
        const auth = useAuthStore()
        const response = await auth.authenticatedFetch(`/events/${eventId}/`, {
          method: 'DELETE',
        })
        if (!response.ok && response.status !== 204) {
          const data = await safeJson(response)
          throw new Error(data?.error || 'Failed to delete event')
        }
        this.items = this.items.filter((item) => item.id !== eventId)
        return true
      } catch (error) {
        throw error
      } finally {
        const { [eventId]: _removed, ...rest } = this.deletingIds
        this.deletingIds = rest
      }
    },
  },
})
