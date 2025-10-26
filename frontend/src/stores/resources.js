import { defineStore } from 'pinia'
import { safeJson } from '@/utils/http'
import { useAuthStore } from '@/stores/auth'

const mapResource = (payload = {}) => ({
  id: payload.id,
  title: payload.title || '',
  description: payload.description || '',
  type: payload.type || 'document',
  role: payload.role || 'all',
  url: payload.url || payload.file_url || '',
  coverImage: payload.coverImage || payload.cover_image || null,
  downloadCount: payload.download_count ?? payload.downloadCount ?? 0,
  createdAt: payload.created_at || payload.createdAt || null,
  updatedAt: payload.updated_at || payload.updatedAt || null
})

export const useResourceStore = defineStore('resources', {
  state: () => ({
    items: [],
    loadingList: false,
    listLoaded: false,
    listError: null,
    uploading: false,
    uploadingCoverIds: {},
    deletingIds: {},
    activeUserId: null
  }),
  actions: {
    reset() {
      this.items = []
      this.loadingList = false
      this.listLoaded = false
      this.listError = null
      this.uploading = false
      this.uploadingCoverIds = {}
      this.deletingIds = {}
      this.activeUserId = null
    },

    async fetchResources({ forceRefresh = false } = {}) {
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
        const response = await auth.authenticatedFetch('/resources/')
        const data = await safeJson(response)

        if (!response.ok) {
          throw new Error(data?.error || 'Failed to load resources')
        }

        const results = Array.isArray(data?.results) ? data.results : Array.isArray(data) ? data : []
        this.items = results.map(mapResource)
        this.listLoaded = true
        return this.items
      } catch (error) {
        this.listError = error
        throw error
      } finally {
        this.loadingList = false
      }
    },

    async refreshResources() {
      return this.fetchResources({ forceRefresh: true })
    },

    async createResource({ title, description, type, role, file }) {
      if (this.uploading) {
        throw new Error('Another upload is in progress, please wait')
      }
      if (!file) {
        throw new Error('Please choose a file to upload')
      }

      this.uploading = true

      try {
        const auth = useAuthStore()
        const form = new FormData()
        form.append('title', title)
        if (description) form.append('description', description)
        form.append('type', type)
        form.append('role', role)
        form.append('file', file)

        const response = await auth.authenticatedFetch('/resources/', {
          method: 'POST',
          body: form
        })

        const data = await safeJson(response)
        if (!response.ok) {
          throw new Error(data?.error || data?.detail || 'Failed to upload resource')
        }

        const mapped = mapResource(data)
        this.items = [mapped, ...this.items]
        return mapped
      } finally {
        this.uploading = false
      }
    },

    async updateCover(resourceId, file) {
      if (!resourceId || !file) {
        throw new Error('Missing information, cannot update cover')
      }

      this.uploadingCoverIds = { ...this.uploadingCoverIds, [resourceId]: true }

      try {
        const auth = useAuthStore()
        const form = new FormData()
        form.append('coverImage', file)

        const response = await auth.authenticatedFetch(`/resources/${resourceId}/cover/`, {
          method: 'PUT',
          body: form
        })

        const data = await safeJson(response)
        if (!response.ok) {
          throw new Error(data?.error || 'Failed to update cover image')
        }

        const coverUrl = data.coverImage || null
        this.items = this.items.map((item) =>
          item.id === resourceId ? { ...item, coverImage: coverUrl } : item
        )

        return coverUrl
      } finally {
        const { [resourceId]: _discard, ...rest } = this.uploadingCoverIds
        this.uploadingCoverIds = rest
      }
    },

    async deleteResource(resourceId) {
      if (!resourceId) return false
      this.deletingIds = { ...this.deletingIds, [resourceId]: true }

      try {
        const auth = useAuthStore()
        const response = await auth.authenticatedFetch(`/resources/${resourceId}/`, {
          method: 'DELETE'
        })

        if (!response.ok && response.status !== 204) {
          const data = await safeJson(response)
          throw new Error(data?.error || 'Failed to delete resource')
        }

        this.items = this.items.filter((item) => item.id !== resourceId)
        return true
      } finally {
        const { [resourceId]: _discard, ...rest } = this.deletingIds
        this.deletingIds = rest
      }
    }
  }
})
