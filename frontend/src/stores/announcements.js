import { defineStore } from 'pinia'
import { safeJson } from '@/utils/http'
import { useAuthStore } from '@/stores/auth'

const mapAnnouncement = (payload = {}) => {
  const createdAt = payload.createdAt || payload.created_at || payload.date || null
  return {
    id: payload.id,
    title: payload.title || '',
    summary: payload.summary || '',
    content: payload.content || '',
    author: payload.author || 'Program Team',
    audience: payload.audience || 'all',
    link: payload.link || '',
    route: payload.route || null,
    createdAt,
    updatedAt: payload.updatedAt || payload.updated_at || null,
    date: createdAt, // legacy alias used by some views
  }
}

export const useAnnouncementStore = defineStore('announcements', {
  state: () => ({
    items: [],
    count: 0,
    loadingList: false,
    creating: false,
    listLoaded: false,
    listError: null,
    activeUserId: null,
  }),
  actions: {
    reset() {
      this.items = []
      this.count = 0
      this.loadingList = false
      this.creating = false
      this.listLoaded = false
      this.listError = null
      this.activeUserId = null
    },

    async fetchAnnouncements({ forceRefresh = false } = {}) {
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
        const response = await auth.authenticatedFetch('/announcements/')
        const data = await safeJson(response)

        if (!response.ok) {
          throw new Error(data?.error || 'Failed to load announcements')
        }

        const results = Array.isArray(data?.results)
          ? data.results
          : Array.isArray(data)
            ? data
            : []

        this.items = results.map(mapAnnouncement)
        this.count = data?.count ?? this.items.length
        this.listLoaded = true
        return this.items
      } catch (error) {
        this.listError = error
        throw error
      } finally {
        this.loadingList = false
      }
    },

    async refreshAnnouncements() {
      return this.fetchAnnouncements({ forceRefresh: true })
    },

    async createAnnouncement(payload) {
      if (this.creating) {
        throw new Error('Another announcement is currently being created, please wait')
      }

      this.creating = true

      try {
        const auth = useAuthStore()
        const response = await auth.authenticatedFetch('/announcements/', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        })

        const data = await safeJson(response)
        if (!response.ok) {
          throw new Error(data?.error || data?.detail || 'Failed to create announcement')
        }

        const mapped = mapAnnouncement(data)
        this.items = [mapped, ...this.items]
        this.count += 1
        this.listLoaded = true
        return mapped
      } finally {
        this.creating = false
      }
    },
  },
})
