import { onBeforeUnmount, reactive, ref, watch, type Ref } from 'vue'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

/** While typing continues, the signal is refreshed this often. */
export const RESEND_TYPING_MS = 3000
/** This long without a keystroke counts as stopped, and the field unlocks for others. */
export const STOP_TYPING_MS = 4000
/** A teammate's label and lock fade if nothing fresh arrives in time, e.g. after their wifi drops. */
export const TYPING_EXPIRES_MS = 6000
/** Typed text is sent at most this often per field; the last change is always sent. */
export const SEND_TEXT_MS = 200
/** Mirrors the server's cap; anything longer is left to the normal save. */
export const MAX_TEXT_LENGTH = 20_000
const RETRY_FIRST_MS = 1000
const RETRY_MAX_MS = 30000
const NO_ACCESS = 4403

type RemoteText = (field: string, text: string) => void
type Settled = () => void
/** Something about the item changed elsewhere, e.g. it was submitted; `by` is who did it. */
type Changed = (item: string, by: string | null) => void
type Timer = ReturnType<typeof setTimeout>

export function liveRoomUrl(kind: string, roomId: string): string {
  const path = `/ws/live/${kind}/${roomId}/`
  try {
    const api = new URL(API_BASE_URL)
    return `${api.protocol === 'https:' ? 'wss:' : 'ws:'}//${api.host}${path}`
  } catch {
    return `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}${path}`
  }
}

/** "Amy is typing…", "Amy and Ben are typing…", "3 teammates are typing…"; '' for nobody. */
export function typingLabel(names: string[]): string {
  if (names.length === 0) return ''
  if (names.length === 1) return `${names[0]} is typing…`
  if (names.length === 2) return `${names[0]} and ${names[1]} are typing…`
  return `${names.length} teammates are typing…`
}

/**
 * Who is typing in which field of one item, and what they have typed, live. A field someone
 * else is typing in is locked here, so two people never type over each other. Connects only
 * while `active` is true and the tab is visible; saving never depends on it.
 */
export function useLiveRoom(kind: string, roomId: Ref<string>, active: Ref<boolean>) {
  const typers = reactive<Record<string, Record<number, string>>>({})
  const expiry = new Map<string, Timer>()
  const lastSent = new Map<string, number>()
  const stopTimers = new Map<string, Timer>()
  const textTimers = new Map<string, Timer>()
  const pendingText = new Map<string, { text: string; caret: number }>()
  const carets = reactive<Record<string, number>>({})
  const remoteTextHandlers: RemoteText[] = []
  const settledHandlers: Settled[] = []
  const changedHandlers: Changed[] = []
  const isVisible = ref(document.visibilityState === 'visible')
  let myId: number | null = null
  let socket: WebSocket | null = null
  let socketRoom = ''
  let retryTimer: Timer | null = null
  let retries = 0
  let dropped = false

  const shouldConnect = () => active.value && isVisible.value && Boolean(roomId.value)
  const isTypingHere = (field: string) => stopTimers.has(field)

  function forget(field: string, userId: number) {
    const key = `${field}:${userId}`
    clearTimeout(expiry.get(key))
    expiry.delete(key)
    const rest = { ...(typers[field] ?? {}) }
    delete rest[userId]
    if (Object.keys(rest).length) {
      typers[field] = rest
    } else if (typers[field]) {
      delete typers[field]
      delete carets[field]
      notifySettled()
    }
  }

  /** A field was released or the connection came back, so live text may have been missed. */
  function notifySettled() {
    settledHandlers.forEach((handler) => handler())
  }

  function remember(field: string, userId: number, name: string) {
    typers[field] = { ...(typers[field] ?? {}), [userId]: name }
    const key = `${field}:${userId}`
    clearTimeout(expiry.get(key))
    expiry.set(key, setTimeout(() => forget(field, userId), TYPING_EXPIRES_MS))
  }

  function clearTypers() {
    expiry.forEach((timer) => clearTimeout(timer))
    expiry.clear()
    Object.keys(typers).forEach((field) => delete typers[field])
    Object.keys(carets).forEach((field) => delete carets[field])
  }

  function stopOwnTyping(field: string) {
    clearTimeout(stopTimers.get(field))
    stopTimers.delete(field)
    clearTimeout(textTimers.get(field))
    textTimers.delete(field)
    pendingText.delete(field)
    lastSent.delete(field)
    send({ type: 'typing', field, typing: false })
  }

  /** Two people starting on one field at once: the earlier account keeps it, on every screen. */
  function yieldsTo(userId: number, field: string): boolean {
    if (!isTypingHere(field)) return true
    if (myId === null || userId > myId) return false
    stopOwnTyping(field)
    return true
  }

  function onMessage(data: unknown) {
    let event: {
      type?: string
      field?: unknown
      typing?: unknown
      text?: unknown
      caret?: unknown
      user?: { id?: unknown; name?: unknown }
    }
    try {
      event = JSON.parse(String(data))
    } catch {
      return
    }
    const { field, user } = event
    if (event.type === 'hello' && typeof user?.id === 'number') {
      myId = user.id
      return
    }
    if (event.type === 'changed' && typeof (event as { item?: unknown }).item === 'string') {
      const item = (event as { item: string }).item
      const by = typeof user?.name === 'string' ? user.name : null
      changedHandlers.forEach((handler) => handler(item, by))
      return
    }
    if (typeof field !== 'string' || typeof user?.id !== 'number') return
    const userId = user.id
    const name = String(user.name ?? 'A teammate')

    if (event.type === 'typing') {
      if (!event.typing) forget(field, userId)
      else if (yieldsTo(userId, field)) remember(field, userId, name)
    } else if (event.type === 'text' && typeof event.text === 'string') {
      if (!yieldsTo(userId, field)) return
      remember(field, userId, name)
      const text = event.text
      carets[field] = typeof event.caret === 'number' ? Math.min(Math.max(event.caret, 0), text.length) : text.length
      remoteTextHandlers.forEach((handler) => handler(field, text))
    }
  }

  function connect() {
    if (socket || retryTimer || !shouldConnect() || typeof WebSocket === 'undefined') return
    const ws = new WebSocket(liveRoomUrl(kind, roomId.value))
    socket = ws
    socketRoom = roomId.value
    ws.onopen = () => {
      retries = 0
      if (dropped) notifySettled()
      dropped = false
    }
    ws.onmessage = (event) => onMessage(event.data)
    ws.onclose = (event) => {
      if (socket !== ws) return
      socket = null
      clearOwnTimers()
      clearTypers()
      if (event.code === NO_ACCESS || !shouldConnect()) return
      dropped = true
      notifySettled()
      // Spread out, so a whole cohort dropped by a restart does not reconnect at once.
      const delay = Math.min(RETRY_MAX_MS, RETRY_FIRST_MS * 2 ** retries) * (0.5 + Math.random() / 2)
      retries += 1
      retryTimer = setTimeout(() => {
        retryTimer = null
        connect()
      }, delay)
    }
  }

  function clearOwnTimers() {
    stopTimers.forEach((timer) => clearTimeout(timer))
    stopTimers.clear()
    textTimers.forEach((timer) => clearTimeout(timer))
    textTimers.clear()
    pendingText.clear()
    lastSent.clear()
  }

  function disconnect() {
    if (retryTimer) clearTimeout(retryTimer)
    retryTimer = null
    retries = 0
    clearOwnTimers()
    const ws = socket
    socket = null
    ws?.close(1000)
    clearTypers()
  }

  function send(message: object) {
    if (socket?.readyState === WebSocket.OPEN) socket.send(JSON.stringify(message))
  }

  /** Call on each keystroke in `field`; signals are throttled and a stop follows a pause. */
  function sendTyping(field: string) {
    // Silent until the server says who we are, so a clash can always be settled.
    if (socket?.readyState !== WebSocket.OPEN || myId === null || isLocked(field)) return
    const now = Date.now()
    if (now - (lastSent.get(field) ?? 0) >= RESEND_TYPING_MS) {
      send({ type: 'typing', field, typing: true })
      lastSent.set(field, now)
    }
    clearTimeout(stopTimers.get(field))
    stopTimers.set(field, setTimeout(() => stopOwnTyping(field), STOP_TYPING_MS))
  }

  /** Shares the field's whole text and cursor: at once, then at most every SEND_TEXT_MS, ending on the latest. */
  function sendText(field: string, text: string, caret = text.length) {
    if (socket?.readyState !== WebSocket.OPEN || !isTypingHere(field) || text.length > MAX_TEXT_LENGTH) return
    if (textTimers.has(field)) {
      pendingText.set(field, { text, caret })
      return
    }
    send({ type: 'text', field, text, caret })
    const flush = () => {
      const next = pendingText.get(field)
      pendingText.delete(field)
      if (next === undefined || !isTypingHere(field)) {
        textTimers.delete(field)
        return
      }
      send({ type: 'text', field, ...next })
      textTimers.set(field, setTimeout(flush, SEND_TEXT_MS))
    }
    textTimers.set(field, setTimeout(flush, SEND_TEXT_MS))
  }

  function typingIn(field: string): string[] {
    return Object.values(typers[field] ?? {})
  }

  /** Where the teammate typing in `field` has their cursor, or null when nobody is. */
  function caretIn(field: string): number | null {
    return carets[field] ?? null
  }

  /** Someone else is typing in `field`, so it should not be editable here. */
  function isLocked(field: string): boolean {
    return typingIn(field).length > 0 && !isTypingHere(field)
  }

  function onRemoteText(handler: RemoteText) {
    remoteTextHandlers.push(handler)
  }

  function onSettled(handler: Settled) {
    settledHandlers.push(handler)
  }

  function onChanged(handler: Changed) {
    changedHandlers.push(handler)
  }

  function onVisibilityChange() {
    isVisible.value = document.visibilityState === 'visible'
  }
  document.addEventListener('visibilitychange', onVisibilityChange)

  watch(
    [roomId, active, isVisible],
    () => {
      if (socketRoom !== roomId.value || !shouldConnect()) disconnect()
      connect()
    },
    { immediate: true },
  )

  onBeforeUnmount(() => {
    document.removeEventListener('visibilitychange', onVisibilityChange)
    disconnect()
  })

  return { sendTyping, sendText, typingIn, caretIn, isLocked, onRemoteText, onSettled, onChanged }
}
