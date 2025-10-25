import { defineStore } from 'pinia'
import { safeJson } from '@/utils/http'
import { useAuthStore } from '@/stores/auth'

const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api'
).replace(/\/$/, '')
const WS_BASE_URL = (import.meta.env.VITE_WS_BASE_URL || '').replace(/\/$/, '')
const DEFAULT_LIMIT = 50
const RECONNECT_DELAY_MS = 5000

const buildWebSocketUrl = (groupId, token) => {
  if (!groupId) throw new Error('Missing group identifier')
  if (!token) throw new Error('Missing access token')

  let base
  if (WS_BASE_URL) {
    base = new URL(WS_BASE_URL)
  } else {
    base = new URL(API_BASE_URL)
  }

  let protocol = base.protocol
  if (protocol === 'http:') protocol = 'ws:'
  if (protocol === 'https:') protocol = 'wss:'
  if (protocol !== 'ws:' && protocol !== 'wss:') {
    protocol = typeof window !== 'undefined' && window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  }

  let pathBase = base.pathname.replace(/\/$/, '')
  if (!WS_BASE_URL) {
    pathBase = pathBase.replace(/\/api$/, '').replace(/\/api\/$/, '').replace(/\/$/, '')
  }

  return `${protocol}//${base.host}${pathBase}/ws/chat/groups/${encodeURIComponent(groupId)}/?token=${encodeURIComponent(token)}`
}

const sortByTimestamp = (messages) =>
  [...messages].sort(
    (a, b) => new Date(a.timestamp || 0).getTime() - new Date(b.timestamp || 0).getTime()
  )

export const useChatStore = defineStore('chat', {
  state: () => ({
    messagesByGroup: {},
    loadingByGroup: {},
    hasMoreByGroup: {},
    errorByGroup: {},
    sendingByGroup: {},
    uploadingFiles: {},
    socketByGroup: {},
    socketStatusByGroup: {},
    socketRetryByGroup: {}
  }),
  actions: {
    reset() {
      Object.keys(this.socketByGroup || {}).forEach((groupId) => this.disconnectFromGroup(groupId))
      this.messagesByGroup = {}
      this.loadingByGroup = {}
      this.hasMoreByGroup = {}
      this.errorByGroup = {}
      this.sendingByGroup = {}
      this.uploadingFiles = {}
    },

    normaliseMessages(raw = []) {
      return [...raw]
        .map((item, index) => {
          const timestamp = item.timestamp || item.created_at || item.createdAt || new Date().toISOString()
          const attachments = Array.isArray(item.attachments)
            ? item.attachments.map((file, fileIndex) => ({
                id: file.id ?? `${item.id ?? index}-${fileIndex}`,
                url: file.file_url || file.url,
                filename: file.filename || `Attachment ${fileIndex + 1}`,
                size: file.file_size ?? file.size ?? null,
                mimeType: file.mime_type || file.mimeType || 'application/octet-stream'
              }))
            : []

          const moderationPayload = item.moderation || {}

          return {
            id: item.id,
            text: item.text || '',
            timestamp,
            author: {
              id: item.author?.id ?? null,
              name: item.author?.name || item.author || 'Unknown'
            },
            attachments,
            isDeleted: Boolean(item.isDeleted),
            deletedAt: item.deletedAt || null,
            deletedBy: item.deletedBy ?? null,
            moderation: {
              status: moderationPayload.status || 'approved',
              note: moderationPayload.note || null,
              moderatedAt: moderationPayload.moderatedAt || moderationPayload.moderated_at || null,
              moderatedBy: moderationPayload.moderatedBy ?? moderationPayload.moderated_by ?? null
            }
          }
        })
        .filter((item) => item.id !== undefined && item.id !== null)
        .reduce((acc, item) => {
          if (!item.timestamp) {
            item.timestamp = new Date().toISOString()
          }
          acc.push(item)
          return acc
        }, [])
    },

    _mergeMessages(groupId, incoming = [], { mode = 'append' } = {}) {
      const existing = this.messagesByGroup[groupId] || []
      let combined

      switch (mode) {
        case 'replace':
          combined = [...incoming]
          break
        case 'prepend':
          combined = [...incoming, ...existing]
          break
        default:
          combined = [...existing, ...incoming]
      }

      const dedupedMap = new Map()
      combined.forEach((message) => {
        if (!message || message.id === undefined) return
        const current = dedupedMap.get(message.id) || {}
        dedupedMap.set(message.id, { ...current, ...message })
      })

      const deduped = sortByTimestamp([...dedupedMap.values()])
      this.messagesByGroup = { ...this.messagesByGroup, [groupId]: deduped }
      return deduped
    },

    connectToGroup(groupId) {
      this.ensureSocket(groupId)
    },

    ensureSocket(groupId) {
      if (!groupId || typeof window === 'undefined' || !('WebSocket' in window)) {
        return null
      }

      const auth = useAuthStore()
      const token = auth.accessToken
      if (!token) return null

      const existing = this.socketByGroup[groupId]
      if (
        existing &&
        (existing.readyState === WebSocket.OPEN || existing.readyState === WebSocket.CONNECTING)
      ) {
        return existing
      }

      this._clearReconnect(groupId)
      return this._openSocket(groupId, token)
    },

    disconnectFromGroup(groupId) {
      const socket = this.socketByGroup[groupId]
      if (socket) {
        socket._manualClose = true
        try {
          socket.close()
        } catch {}
      }
      this._clearReconnect(groupId)
      const nextSockets = { ...this.socketByGroup }
      delete nextSockets[groupId]
      this.socketByGroup = nextSockets
      const nextStatus = { ...this.socketStatusByGroup }
      delete nextStatus[groupId]
      this.socketStatusByGroup = nextStatus
    },

    _openSocket(groupId, token) {
      let url
      try {
        url = buildWebSocketUrl(groupId, token)
      } catch (error) {
        console.error('Failed to build WebSocket URL', error)
        return null
      }

      let socket
      try {
        socket = new WebSocket(url)
      } catch (error) {
        console.error('Failed to open WebSocket', error)
        return null
      }

      socket._manualClose = false
      socket.addEventListener('open', () => {
        this.socketStatusByGroup = { ...this.socketStatusByGroup, [groupId]: 'open' }
      })
      socket.addEventListener('message', (event) => this._handleSocketMessage(groupId, event.data))
      socket.addEventListener('close', (event) => this._handleSocketClose(groupId, socket, event))
      socket.addEventListener('error', () => {
        this.socketStatusByGroup = { ...this.socketStatusByGroup, [groupId]: 'error' }
      })

      this.socketByGroup = { ...this.socketByGroup, [groupId]: socket }
      this.socketStatusByGroup = { ...this.socketStatusByGroup, [groupId]: 'connecting' }
      return socket
    },

    _handleSocketMessage(groupId, rawMessage) {
      let parsed
      try {
        parsed = JSON.parse(rawMessage)
      } catch (error) {
        console.warn('Failed to parse chat socket payload', error)
        return
      }

      const { type, payload } = parsed
      if (type === 'connection.established') {
        this.socketStatusByGroup = { ...this.socketStatusByGroup, [groupId]: 'open' }
        return
      }

      if (type === 'error') {
        this.errorByGroup = {
          ...this.errorByGroup,
          [groupId]: new Error(payload?.detail || 'WebSocket error')
        }
        return
      }

      if (['message.created', 'message.updated', 'message.deleted'].includes(type) && payload) {
        const normalised = this.normaliseMessages([payload])
        if (normalised.length) {
          this._mergeMessages(groupId, normalised, { mode: 'append' })
        }
      }
    },

    _handleSocketClose(groupId, socket, event) {
      const nextSockets = { ...this.socketByGroup }
      if (nextSockets[groupId] === socket) {
        delete nextSockets[groupId]
        this.socketByGroup = nextSockets
      }
      this.socketStatusByGroup = { ...this.socketStatusByGroup, [groupId]: 'closed' }

      if (!socket._manualClose) {
        this._scheduleReconnect(groupId)
      }
    },

    _scheduleReconnect(groupId) {
      this._clearReconnect(groupId)
      const timer = setTimeout(() => {
        const auth = useAuthStore()
        if (!auth.accessToken) {
          this._clearReconnect(groupId)
          return
        }
        this.ensureSocket(groupId)
      }, RECONNECT_DELAY_MS)

      this.socketRetryByGroup = { ...this.socketRetryByGroup, [groupId]: timer }
    },

    _clearReconnect(groupId) {
      const timer = this.socketRetryByGroup[groupId]
      if (timer) {
        clearTimeout(timer)
        const nextTimers = { ...this.socketRetryByGroup }
        delete nextTimers[groupId]
        this.socketRetryByGroup = nextTimers
      }
    },

    async fetchMessages(groupId, { before = null, limit = DEFAULT_LIMIT, append = false } = {}) {
      if (!groupId) return []
      this.ensureSocket(groupId)

      const auth = useAuthStore()

      if (this.loadingByGroup[groupId]) {
        return this.messagesByGroup[groupId] || []
      }

      this.loadingByGroup = { ...this.loadingByGroup, [groupId]: true }
      this.errorByGroup = { ...this.errorByGroup, [groupId]: null }

      const params = new URLSearchParams()
      if (limit) params.set('limit', limit)
      if (before) params.set('before', before)

      try {
        const response = await auth.authenticatedFetch(
          `/groups/${groupId}/messages${params.toString() ? `?${params}` : ''}`
        )
        const data = await safeJson(response)
        if (!response.ok) {
          throw new Error(data?.error || 'Failed to load messages')
        }

        const normalised = sortByTimestamp(this.normaliseMessages(data?.messages))
        this._mergeMessages(groupId, normalised, { mode: append ? 'prepend' : 'replace' })

        this.hasMoreByGroup = { ...this.hasMoreByGroup, [groupId]: Boolean(data?.hasMore) }
        return this.messagesByGroup[groupId]
      } catch (error) {
        this.errorByGroup = { ...this.errorByGroup, [groupId]: error }
        throw error
      } finally {
        this.loadingByGroup = { ...this.loadingByGroup, [groupId]: false }
      }
    },

    async sendMessage(groupId, { text = '', attachments = [] } = {}) {
      if (!groupId) throw new Error('Missing group ID')
      const auth = useAuthStore()

      if (this.sendingByGroup[groupId]) {
        throw new Error('Still sending the previous message, please wait')
      }

      this.sendingByGroup = { ...this.sendingByGroup, [groupId]: true }

      const payload = {
        text,
        attachments: attachments.map((item) => ({
          url: item.url,
          filename: item.filename,
          size: item.size,
          mimeType: item.mimeType || item.mime_type || 'application/octet-stream'
        }))
      }

      try {
        const response = await auth.authenticatedFetch(`/groups/${groupId}/messages`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        })
        const data = await safeJson(response)
        if (!response.ok) {
          throw new Error(data?.error || 'Failed to send message')
        }

        const normalised = this.normaliseMessages([data])
        if (normalised.length) {
          this._mergeMessages(groupId, normalised, { mode: 'append' })
        }
        return normalised[0]
      } finally {
        this.sendingByGroup = { ...this.sendingByGroup, [groupId]: false }
      }
    },

    async uploadAttachment(file) {
      if (!file) throw new Error('No file selected')
      const auth = useAuthStore()
      const tmpId = `${Date.now()}-${file.name}`
      this.uploadingFiles = {
        ...this.uploadingFiles,
        [tmpId]: { file, status: 'uploading' }
      }

      try {
        const formData = new FormData()
        formData.append('file', file)

        const response = await auth.authenticatedFetch('/uploads/', {
          method: 'POST',
          body: formData
        })
        const data = await safeJson(response)
        if (!response.ok || !data?.url) {
          throw new Error(data?.detail || data?.error || 'Failed to upload file')
        }

        this.uploadingFiles = {
          ...this.uploadingFiles,
          [tmpId]: { file, status: 'done', result: data }
        }
        return {
          url: data.url,
          filename: data.filename || file.name,
          size: data.size || file.size,
          mimeType: data.mimeType || file.type || 'application/octet-stream'
        }
      } catch (error) {
        this.uploadingFiles = {
          ...this.uploadingFiles,
          [tmpId]: { file, status: 'error', error }
        }
        throw error
      }
    }
  }
})
