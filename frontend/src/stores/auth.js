import { defineStore } from 'pinia'
import { safeJson } from '@/utils/http'

const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api'
).replace(/\/$/, '')
const SESSION_STORAGE_KEY = 'auth.session'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    user: null,
    accessToken: null,
    refreshToken: null,
    pendingEmail: null
  }),
  getters: {
    isAuthenticated: (s) => !!s.user,
    isAdmin: (s) => s.user?.role === 'admin',
    initials: (s) =>
      s.user
        ? (s.user.name || s.user.email || '')
          .split(' ')
          .filter(Boolean)
          .map((n) => n[0])
          .join('')
          .toUpperCase()
        : '—'
  },
  actions: {
    async requestMagicLink(email) {
      const normalized = String(email || '').trim().toLowerCase()
      if (!normalized) {
        throw new Error('Please enter your email address')
      }

      const res = await fetch(`${API_BASE_URL}/auth/magic-link/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: normalized })
      })

      const data = await safeJson(res)
      if (!res.ok) {
        throw new Error(data?.error || data?.message || 'Failed to send login email, please try again later')
      }

      this.pendingEmail = normalized
      try {
        localStorage.setItem('auth.pendingEmail', normalized)
      } catch {}
      return data
    },

    async verifyOtp(code, email) {
      const targetEmail = String(email || this.pendingEmail || '').trim().toLowerCase()
      if (!targetEmail) {
        throw new Error('Enter your email and request a code first')
      }

      const trimmedCode = String(code || '').trim()
      if (trimmedCode.length !== 6) {
        throw new Error('Please enter the 6-digit code')
      }

      const res = await fetch(`${API_BASE_URL}/auth/verify-otp/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: targetEmail, code: trimmedCode })
      })

      const data = await safeJson(res)
      if (!res.ok) {
        throw new Error(data?.error || 'The verification code is invalid or has expired')
      }

      this.setSession({
        user: data.user,
        accessToken: data.token,
        refreshToken: data.refresh_token
      })
      this.pendingEmail = null
      try {
        localStorage.removeItem('auth.pendingEmail')
      } catch {}
      return data
    },

    async refreshSession() {
      if (!this.refreshToken) return null

      const res = await fetch(`${API_BASE_URL}/auth/refresh/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: this.refreshToken })
      })
      const data = await safeJson(res)
      if (!res.ok) {
        this.clearSession()
        throw new Error('Session expired, please sign in again')
      }

      this.setSession({
        user: this.user,
        accessToken: data.token,
        refreshToken: data.refresh_token
      })
      return data
    },

    async authenticatedFetch(path, options = {}, retry = true) {
      if (!this.accessToken) {
        throw new Error('Please sign in first')
      }

      const config = { ...options }
      config.headers = {
        ...(options.headers || {}),
        Authorization: `Bearer ${this.accessToken}`
      }

      const response = await fetch(`${API_BASE_URL}${path}`, config)
      if (response.status === 401 && retry) {
        try {
          await this.refreshSession()
        } catch (error) {
          throw error
        }
        if (!this.accessToken) {
          throw new Error('Session expired, please sign in again')
        }
        return this.authenticatedFetch(path, options, false)
      }
      return response
    },

    async fetchCurrentUser({ forceRefresh = false } = {}) {
      if (!this.accessToken) return null
      if (!forceRefresh && this.user) return this.user

      const res = await this.authenticatedFetch('/users/me/')
      const data = await safeJson(res)
      if (!res.ok) {
        throw new Error(data?.error || 'Failed to fetch user information')
      }

      this.setSession({
        user: data,
        accessToken: this.accessToken,
        refreshToken: this.refreshToken
      })
      return data
    },

    async updateCurrentUser(payload) {
      const res = await this.authenticatedFetch('/users/me/', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })

      const data = await safeJson(res)
      if (!res.ok) {
        throw new Error(data?.error || 'Update failed')
      }

      this.setSession({
        user: data,
        accessToken: this.accessToken,
        refreshToken: this.refreshToken
      })
      return data
    },

    setSession({ user, accessToken, refreshToken }) {
      const previousUserId = this.user?.id ?? null
      this.user = user || null
      this.accessToken = accessToken || null
      this.refreshToken = refreshToken || null

      try {
        if (this.user && this.accessToken && this.refreshToken) {
          localStorage.setItem(
            SESSION_STORAGE_KEY,
            JSON.stringify({
              user: this.user,
              accessToken: this.accessToken,
              refreshToken: this.refreshToken
            })
          )
        } else {
          localStorage.removeItem(SESSION_STORAGE_KEY)
        }
      } catch {}

      // 当检测到账号切换时，重置依赖于用户身份的缓存
      const currentUserId = this.user?.id ?? null
      if (previousUserId !== null && currentUserId !== null && previousUserId !== currentUserId) {
        try {
          const { useGroupStore } = require('@/stores/groups')
          const { useResourceStore } = require('@/stores/resources')
          const { useEventStore } = require('@/stores/events')
          const { useAnnouncementStore } = require('@/stores/announcements')
          const { useChatStore } = require('@/stores/chat')

          useGroupStore().reset()
          useResourceStore().reset()
          useEventStore().reset()
          useAnnouncementStore().reset()
          useChatStore().reset()
        } catch {
          // ignore require issues (e.g. during hydration in non-module context)
        }
      }
    },

    clearSession() {
      this.user = null
      this.accessToken = null
      this.refreshToken = null
      this.pendingEmail = null
      try {
        localStorage.removeItem(SESSION_STORAGE_KEY)
        localStorage.removeItem('auth.pendingEmail')
      } catch {}
    },

    logout() {
      this.clearSession()
    },

    hydrate() {
      try {
        const raw = localStorage.getItem(SESSION_STORAGE_KEY)
        if (raw) {
          const parsed = JSON.parse(raw)
          this.user = parsed.user || null
          this.accessToken = parsed.accessToken || null
          this.refreshToken = parsed.refreshToken || null
        }
        const pending = localStorage.getItem('auth.pendingEmail')
        if (pending) this.pendingEmail = pending
      } catch {}
    }
  }
})
