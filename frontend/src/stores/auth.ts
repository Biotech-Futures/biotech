// Minimal Pinia auth store for router guard compatibility
import { defineStore } from 'pinia'
import { type MockUser, mockUsers } from '../data/mock'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    user: null as MockUser | null
  }),
  getters: {
    isAuthenticated: (s) => !!s.user,
    isAdmin: (s) => s.user?.role === 'admin',
    initials: (s) =>
      s.user ? s.user.name.split(' ').map(n => n[0]).join('').toUpperCase() : '—'
  },
  actions: {
    // Login by email (mock magic link)
    loginByEmail(email: string) {
      const u = mockUsers.find(
        x => x.email.toLowerCase() === String(email || '').toLowerCase()
      )
      if (!u) {
        throw new Error('No such user. Use one of mock emails (e.g. admin@btf.org).')
      }
      this.user = u
      try { localStorage.setItem('auth.user', JSON.stringify(u)) } catch {}
    },
    logout() {
      this.user = null
      try { localStorage.removeItem('auth.user') } catch {}
    },
    hydrate() {
      try {
        const raw = localStorage.getItem('auth.user')
        if (raw) this.user = JSON.parse(raw)
      } catch {}
    }
  }
})
