// Minimal Pinia auth store for router guard compatibility
import { defineStore } from 'pinia'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    user: null as null | { id: string; name: string; isAdmin?: boolean },
    isAuthenticated: false
  }),
  getters: {
    initials(state) {
      if (!state.user || !state.user.name) return ''
      return state.user.name.split(' ').map((n: string) => n[0]).join('').toUpperCase()
    },
    isAdmin(state) {
      return !!(state.user && state.user.isAdmin)
    }
  },
  actions: {
    hydrate() {
      // Placeholder: load user from localStorage or API if needed
      this.user = null
      this.isAuthenticated = false
    },
    logout() {
      this.user = null
      this.isAuthenticated = false
    }
  }
})
