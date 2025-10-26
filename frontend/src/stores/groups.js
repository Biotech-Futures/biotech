import { defineStore } from 'pinia'
import { safeJson } from '@/utils/http'
import { useAuthStore } from '@/stores/auth'

export const useGroupStore = defineStore('groups', {
  state: () => ({
    myGroups: [],
    myGroupsLoaded: false,
    loadingMyGroups: false,
    allGroups: [],
    allGroupsLoaded: false,
    loadingAllGroups: false,
    loadingById: {},
    groupsById: {},
    errorMyGroups: null,
    errorAllGroups: null,
    errorById: {},
    activeUserId: null
  }),
  actions: {
    reset() {
      this.myGroups = []
      this.myGroupsLoaded = false
      this.loadingMyGroups = false
      this.allGroups = []
      this.allGroupsLoaded = false
      this.loadingAllGroups = false
      this.loadingById = {}
      this.groupsById = {}
      this.errorMyGroups = null
      this.errorAllGroups = null
      this.errorById = {}
      this.activeUserId = null
    },

    async fetchMyGroups({ forceRefresh = false } = {}) {
      if (this.loadingMyGroups) return this.myGroups

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

      if (this.myGroupsLoaded && !forceRefresh) return this.myGroups

      this.loadingMyGroups = true
      this.errorMyGroups = null

      try {
        const response = await auth.authenticatedFetch('/groups/my-groups/')
        const data = await safeJson(response)
        if (!response.ok) {
          throw new Error(data?.error || 'Failed to load groups')
        }

        this.myGroups = Array.isArray(data?.groups) ? data.groups : []
        this.myGroupsLoaded = true

        this.myGroups.forEach((group) => {
          const existing = this.groupsById[group.id]
          this.groupsById[group.id] = existing
            ? { ...existing, ...group }
            : { ...group }
        })

        return this.myGroups
      } catch (error) {
        this.errorMyGroups = error
        throw error
      } finally {
        this.loadingMyGroups = false
      }
    },

    async fetchAllGroups({ forceRefresh = false } = {}) {
      if (this.loadingAllGroups) return this.allGroups

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

      if (this.allGroupsLoaded && !forceRefresh) return this.allGroups

      this.loadingAllGroups = true
      this.errorAllGroups = null

      try {
        const response = await auth.authenticatedFetch('/groups/')
        const data = await safeJson(response)
        if (!response.ok) {
          throw new Error(data?.error || 'Failed to load all groups')
        }

        this.allGroups = Array.isArray(data?.groups) ? data.groups : []
        this.allGroupsLoaded = true

        this.allGroups.forEach((group) => {
          const existing = this.groupsById[group.id]
          this.groupsById[group.id] = existing
            ? { ...existing, ...group }
            : { ...group }
        })

        return this.allGroups
      } catch (error) {
        this.errorAllGroups = error
        throw error
      } finally {
        this.loadingAllGroups = false
      }
    },

    async fetchGroupDetail(groupId, { forceRefresh = false } = {}) {
      if (!groupId) return null

      const auth = useAuthStore()
      const userId = auth.user?.id ?? null
      if (!userId) {
        this.reset()
        return null
      }
      if (this.activeUserId !== userId) {
        this.reset()
        this.activeUserId = userId
      }

      const cached = this.groupsById[groupId]
      if (!forceRefresh && cached?.milestones) return cached
      if (this.loadingById[groupId]) return cached || null

      this.loadingById = { ...this.loadingById, [groupId]: true }
      this.errorById = { ...this.errorById, [groupId]: null }

      try {
        const response = await auth.authenticatedFetch(`/groups/${groupId}/`)
        const data = await safeJson(response)
        if (!response.ok) {
          throw new Error(data?.error || 'Failed to load group details')
        }

        this.groupsById[groupId] = data

        const index = this.myGroups.findIndex((group) => group.id === groupId)
        if (index !== -1) {
          const summary = this.myGroups[index]
          this.myGroups[index] = {
            ...summary,
            name: data.name,
            status: data.status,
            mentor: data.mentor,
            track: data.track,
            members: Array.isArray(data.members)
              ? data.members.length
              : summary.members
          }
        }

        return data
      } catch (error) {
        this.errorById = { ...this.errorById, [groupId]: error }
        throw error
      } finally {
        this.loadingById = { ...this.loadingById, [groupId]: false }
      }
    },

    async setTaskCompletion(groupId, taskId, completed) {
      if (!groupId || !taskId) return null

      const auth = useAuthStore()
      const response = await auth.authenticatedFetch(
        `/groups/${groupId}/tasks/${taskId}/`,
        {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ completed })
        }
      )

      const data = await safeJson(response)
      if (!response.ok) {
        throw new Error(data?.error || 'Failed to update task status')
      }

      const group = this.groupsById[groupId]
      if (group?.milestones) {
        group.milestones.forEach((milestone) => {
          const task = milestone.tasks?.find((t) => t.id === taskId)
          if (task) task.completed = completed
        })
      }

      return data.task
    },

    async addTask(groupId, milestoneId, name) {
      if (!groupId || !milestoneId) return null
      const trimmed = String(name || '').trim()
      if (!trimmed) {
        throw new Error('Task name cannot be empty')
      }

      const auth = useAuthStore()
      const response = await auth.authenticatedFetch(
        `/groups/${groupId}/milestones/${milestoneId}/tasks/`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name: trimmed })
        }
      )

      const data = await safeJson(response)
      if (!response.ok) {
        throw new Error(data?.error || 'Failed to create task')
      }

      const group = this.groupsById[groupId]
      if (group?.milestones) {
        const milestone = group.milestones.find(
          (m) => String(m.id) === String(milestoneId)
        )
        if (milestone) {
          if (!Array.isArray(milestone.tasks)) milestone.tasks = []
          milestone.tasks.push(data)
        }
      }

      return data
    },

    async createMilestone(groupId, { title, description = '' } = {}) {
      if (!groupId) return null
      const trimmed = String(title || '').trim()
      if (!trimmed) {
        throw new Error('Milestone title cannot be empty')
      }

      const auth = useAuthStore()
      const response = await auth.authenticatedFetch(
        `/groups/${groupId}/milestones/`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ title: trimmed, description })
        }
      )

      const data = await safeJson(response)
      if (!response.ok) {
        throw new Error(data?.error || 'Failed to create milestone')
      }

      const group = this.groupsById[groupId]
      if (group) {
        if (!Array.isArray(group.milestones)) group.milestones = []
        group.milestones.push({
          id: data.id,
          title: data.title,
          description: data.description || '',
          order_index: data.order_index ?? group.milestones.length,
          tasks: Array.isArray(data.tasks) ? data.tasks : []
        })
      }

      return data
    },

    async deleteMilestone(groupId, milestoneId) {
      if (!groupId || !milestoneId) return false
      const auth = useAuthStore()
      const response = await auth.authenticatedFetch(
        `/groups/${groupId}/milestones/${milestoneId}/`,
        { method: 'DELETE' }
      )

      if (!response.ok && response.status !== 204) {
        const data = await safeJson(response)
        throw new Error(data?.error || 'Failed to delete milestone')
      }

      const group = this.groupsById[groupId]
      if (group?.milestones) {
        group.milestones = group.milestones.filter(
          (milestone) => String(milestone.id) !== String(milestoneId)
        )
      }

      return true
    }
  }
})
