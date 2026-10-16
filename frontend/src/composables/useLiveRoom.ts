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
/** A cursor is sent at most this often per field; the latest position always goes. */
export const SEND_CURSOR_MS = 200
/** A cursor left still is sent again this often, so teammates know it is still there. */
export const RESEND_CURSOR_MS = 20_000
/** A teammate's cursor goes if nothing arrives for this long, e.g. after their wifi drops. */
export const CURSOR_EXPIRES_MS = 45_000
/** Typing again after a pause this long counts as starting afresh, so their name shows again. */
export const TYPING_RESTART_MS = 5000
const RETRY_FIRST_MS = 1000
const RETRY_MAX_MS = 30000
const NO_ACCESS = 4403

type RemoteText = (field: string, text: string) => void
/** 'released': a teammate let a field go or the connection dropped; 'rejoined': back after time away. */
type Settled = (reason: 'released' | 'rejoined') => void
/** Something about the item changed elsewhere, e.g. it was submitted; `by` is who did it. */
type Changed = (item: string, by: string | null) => void
/** A shared-document message ("doc-…"), for a room whose kind keeps one. */
type DocMessage = (message: Record<string, unknown>) => void
type Timer = ReturnType<typeof setTimeout>

/** Where a teammate's cursor is in a shared field, and when they last typed there. */
export interface TeammateCursor {
  id: number
  name: string
  /** An encoded shared-document position, so it stays put as text changes around it. */
  at: string
  typedAt: number | null
  /** When their current run of typing began; their name shows briefly from then. */
  startedAt: number | null
}

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
/**
 * With `coediting` on, a field is never locked: everyone types in it at once (the text itself
 * travels as shared-document messages), and every typist's name shows under it.
 */
export function useLiveRoom(kind: string, roomId: Ref<string>, active: Ref<boolean>, coediting?: Ref<boolean>) {
  const typers = reactive<Record<string, Record<number, string>>>({})
  const expiry = new Map<string, Timer>()
  const lastSent = new Map<string, number>()
  const stopTimers = new Map<string, Timer>()
  const textTimers = new Map<string, Timer>()
  const pendingText = new Map<string, { text: string; caret: number }>()
  const carets = reactive<Record<string, number>>({})
  const cursors = reactive<Record<string, Record<number, Omit<TeammateCursor, 'id'>>>>({})
  const cursorExpiry = new Map<string, Timer>()
  const cursorSends = new Map<string, { next: { at: string | null; typed: boolean } | null }>()
  const cursorTimers = new Map<string, Timer>()
  const remoteTextHandlers: RemoteText[] = []
  const settledHandlers: Settled[] = []
  const changedHandlers: Changed[] = []
  const docHandlers: DocMessage[] = []
  const openHandlers: Array<() => void> = []
  const closeHandlers: Array<() => void> = []
  const isConnected = ref(false)
  const isShared = () => Boolean(coediting?.value)
  const isVisible = ref(document.visibilityState === 'visible')
  let myId: number | null = null
  let socket: WebSocket | null = null
  let socketRoom = ''
  let retryTimer: Timer | null = null
  let retries = 0
  let dropped = false
  /** The room last joined, so coming back to it is told apart from the first join. */
  let joinedRoom = ''

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
      notifySettled('released')
    }
  }

  /** A field was released or the room was rejoined, so live text may have been missed. */
  function notifySettled(reason: 'released' | 'rejoined') {
    settledHandlers.forEach((handler) => handler(reason))
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
    cursorExpiry.forEach((timer) => clearTimeout(timer))
    cursorExpiry.clear()
    Object.keys(cursors).forEach((field) => delete cursors[field])
  }

  function keepCursor(field: string, userId: number, name: string, at: string, typed: boolean) {
    const previous = cursors[field]?.[userId]
    const now = Date.now()
    const typedAt = typed ? now : (previous?.typedAt ?? null)
    const restarted = typed && (previous?.typedAt == null || now - previous.typedAt >= TYPING_RESTART_MS)
    const startedAt = restarted ? now : (previous?.startedAt ?? null)
    cursors[field] = { ...(cursors[field] ?? {}), [userId]: { name, at, typedAt, startedAt } }
    const key = `${field}:${userId}`
    clearTimeout(cursorExpiry.get(key))
    cursorExpiry.set(key, setTimeout(() => dropCursor(field, userId), CURSOR_EXPIRES_MS))
  }

  function dropCursor(field: string, userId: number) {
    const key = `${field}:${userId}`
    clearTimeout(cursorExpiry.get(key))
    cursorExpiry.delete(key)
    const rest = { ...(cursors[field] ?? {}) }
    delete rest[userId]
    if (Object.keys(rest).length) cursors[field] = rest
    else delete cursors[field]
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
    if (isShared() || !isTypingHere(field)) return true
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
      at?: unknown
      typed?: unknown
      user?: { id?: unknown; name?: unknown }
    }
    try {
      event = JSON.parse(String(data))
    } catch {
      return
    }
    const { field, user } = event
    if (typeof event.type === 'string' && event.type.startsWith('doc-')) {
      const message = event as Record<string, unknown>
      docHandlers.forEach((handler) => handler(message))
      return
    }
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
    } else if (event.type === 'cursor') {
      if (typeof event.at === 'string' && event.at) keepCursor(field, userId, name, event.at, event.typed === true)
      else dropCursor(field, userId)
    }
  }

  function connect() {
    if (socket || retryTimer || !shouldConnect() || typeof WebSocket === 'undefined') return
    const room = roomId.value
    const ws = new WebSocket(liveRoomUrl(kind, room))
    socket = ws
    socketRoom = room
    ws.onopen = () => {
      retries = 0
      // Text typed while away was missed, whether the connection dropped or the tab was hidden.
      if (dropped || joinedRoom === room) notifySettled('rejoined')
      joinedRoom = room
      dropped = false
      isConnected.value = true
      openHandlers.forEach((handler) => handler())
    }
    ws.onmessage = (event) => onMessage(event.data)
    ws.onclose = (event) => {
      if (socket !== ws) return
      socket = null
      notifyClosed()
      clearOwnTimers()
      clearTypers()
      if (event.code === NO_ACCESS || !shouldConnect()) return
      dropped = true
      notifySettled('released')
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
    cursorTimers.forEach((timer) => clearTimeout(timer))
    cursorTimers.clear()
    cursorSends.clear()
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
    if (ws) notifyClosed()
    clearTypers()
  }

  function notifyClosed() {
    if (!isConnected.value) return
    isConnected.value = false
    closeHandlers.forEach((handler) => handler())
  }

  /** Sends a shared-document message; false when there is no open connection to send it on. */
  function sendDoc(message: object): boolean {
    if (socket?.readyState !== WebSocket.OPEN) return false
    socket.send(JSON.stringify(message))
    return true
  }

  function send(message: object) {
    if (socket?.readyState === WebSocket.OPEN) socket.send(JSON.stringify(message))
  }

  /** Call on each keystroke in `field`; signals are throttled and a stop follows a pause. */
  function sendTyping(field: string) {
    // Silent until the server says who we are, so a clash can always be settled.
    if (socket?.readyState !== WebSocket.OPEN || myId === null || (!isShared() && isLocked(field))) return
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

  /**
   * Shares where this person's cursor is in `field` (null once they leave it): at once, then at most
   * every SEND_CURSOR_MS, ending on the latest. `typed` marks a move made by typing.
   */
  function sendCursor(field: string, at: string | null, typed = false) {
    if (socket?.readyState !== WebSocket.OPEN || myId === null) return
    const waiting = cursorSends.get(field)
    if (waiting) {
      waiting.next = { at, typed: typed || Boolean(waiting.next?.typed) }
      return
    }
    emitCursor(field, at, typed)
  }

  function emitCursor(field: string, at: string | null, typed: boolean) {
    send({ type: 'cursor', field, at, typed })
    const entry: { next: { at: string | null; typed: boolean } | null } = { next: null }
    cursorSends.set(field, entry)
    clearTimeout(cursorTimers.get(field))
    cursorTimers.set(
      field,
      setTimeout(() => {
        cursorSends.delete(field)
        cursorTimers.delete(field)
        if (entry.next) emitCursor(field, entry.next.at, entry.next.typed)
        else if (at !== null) resendCursorLater(field, at)
      }, SEND_CURSOR_MS)
    )
  }

  function resendCursorLater(field: string, at: string) {
    cursorTimers.set(
      field,
      setTimeout(() => {
        cursorTimers.delete(field)
        emitCursor(field, at, false)
      }, RESEND_CURSOR_MS - SEND_CURSOR_MS)
    )
  }

  /** Teammates' cursors in `field`. */
  function cursorsIn(field: string): TeammateCursor[] {
    return Object.entries(cursors[field] ?? {}).map(([id, cursor]) => ({ id: Number(id), ...cursor }))
  }

  function typingIn(field: string): string[] {
    return Object.values(typers[field] ?? {})
  }

  /** Where the teammate typing in `field` has their cursor, or null when nobody is. */
  function caretIn(field: string): number | null {
    return carets[field] ?? null
  }

  /** Someone else is typing in `field`, so it should not be editable here; never while co-editing. */
  function isLocked(field: string): boolean {
    return !isShared() && typingIn(field).length > 0 && !isTypingHere(field)
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

  function onDoc(handler: DocMessage) {
    docHandlers.push(handler)
  }

  function onOpen(handler: () => void) {
    openHandlers.push(handler)
  }

  function onClose(handler: () => void) {
    closeHandlers.push(handler)
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

  return {
    sendTyping,
    sendText,
    sendCursor,
    cursorsIn,
    typingIn,
    caretIn,
    isLocked,
    onRemoteText,
    onSettled,
    onChanged,
    sendDoc,
    onDoc,
    onOpen,
    onClose,
    isConnected
  }
}
