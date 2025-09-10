import { defineStore } from 'pinia'
import { mockUsers } from '../data/mock.js'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    user: null // { id, name, email, role, ... } or null
  }),
  getters: {
    isAuthenticated: (s) => !!s.user,
    isAdmin: (s) => s.user?.role === 'admin',
    initials: (s) =>
      s.user ? s.user.name.split(' ').map(n => n[0]).join('').toUpperCase() : '—'
  },
  actions: {
    // 用邮箱“登录”（模拟 magic link 成功后）
    loginByEmail(email) {
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
