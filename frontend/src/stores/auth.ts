// Minimal Pinia auth store for router guard compatibility
import { defineStore } from 'pinia'
import { mockUsers } from '@/data/mock.js'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    user: null as null | { id: string; name: string; email: string; role: string }
  }),
  getters: {
    isAuthenticated: (s) => !!s.user,
    isAdmin: (s) => s.user?.role === 'admin',
    initials: (s) =>
      s.user ? s.user.name.split(' ').map(n => n[0]).join('').toUpperCase() : '—'
  },
  actions: {
    // Login by email (simulate magic link success)
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
