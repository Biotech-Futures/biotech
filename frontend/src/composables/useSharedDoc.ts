import * as Y from 'yjs'
import { onBeforeUnmount, ref, shallowRef, watch, type Ref } from 'vue'

/** Local edits are sent at most this often, merged into one update. */
export const SEND_DOC_MS = 100
/** A save-now request that gets no answer in this time counts as failed. */
export const FLUSH_TIMEOUT_MS = 8000
/** After a refused edit, edits are offered again after 1s, 2s, 4s… up to this. */
export const RECOVER_MAX_MS = 30_000
/** An empty Yjs update encodes to this many bytes. */
const EMPTY_UPDATE_BYTES = 2
/** Marks updates that came from the server, so they are never sent back. */
const FROM_SERVER = Symbol('from-server')

/** The parts of a live room a shared document travels on. */
export interface DocChannel {
  sendDoc: (message: object) => boolean
  onDoc: (handler: (message: Record<string, unknown>) => void) => void
  onOpen: (handler: () => void) => void
  onClose: (handler: () => void) => void
  isConnected: Ref<boolean>
}

export function toBase64(bytes: Uint8Array): string {
  let binary = ''
  bytes.forEach((byte) => {
    binary += String.fromCharCode(byte)
  })
  return btoa(binary)
}

export function fromBase64(text: unknown): Uint8Array | null {
  if (typeof text !== 'string') return null
  try {
    return Uint8Array.from(atob(text), (char) => char.charCodeAt(0))
  } catch {
    return null
  }
}

/**
 * A document shared live with everyone in the room, merged by Yjs so simultaneous edits all keep.
 * `synced` is true once this copy matches the server's; `editable` is the server's word on whether
 * this person may change it. Until both are true, fields bound to it should stay read-only.
 */
export function useSharedDoc(channel: DocChannel, enabled: Ref<boolean>) {
  const doc = shallowRef(new Y.Doc())
  const synced = ref(false)
  const editable = ref(false)
  const replacedHandlers: Array<(doc: Y.Doc) => void> = []
  const flushes = new Map<number, { resolve: (ok: boolean) => void; timer: ReturnType<typeof setTimeout> }>()
  let pending: Uint8Array[] = []
  let sendTimer: ReturnType<typeof setTimeout> | null = null
  let recoverTimer: ReturnType<typeof setTimeout> | null = null
  let recoverAttempts = 0
  let flushCount = 0
  let detach = attach(doc.value)

  function attach(target: Y.Doc) {
    const onUpdate = (update: Uint8Array, origin: unknown) => {
      if (origin !== FROM_SERVER) queue(update)
    }
    target.on('update', onUpdate)
    return () => target.off('update', onUpdate)
  }

  function queue(update: Uint8Array) {
    pending.push(update)
    if (!sendTimer) sendTimer = setTimeout(sendPending, SEND_DOC_MS)
  }

  /** Unsent edits are not lost if this fails: the next sync sends whatever the server lacks. */
  function sendPending() {
    if (sendTimer) clearTimeout(sendTimer)
    sendTimer = null
    const updates = pending
    pending = []
    if (!updates.length || !synced.value) return
    channel.sendDoc({ type: 'doc-update', update: toBase64(Y.mergeUpdates(updates)), generation: generation() })
  }

  /** Which build of the server's document this copy came from; the server never merges another build's. */
  function generation(): string | null {
    const value = doc.value.getMap('meta').get('generation')
    return typeof value === 'string' ? value : null
  }

  function sync() {
    if (!enabled.value) return
    synced.value = false
    channel.sendDoc({
      type: 'doc-sync',
      vector: toBase64(Y.encodeStateVector(doc.value)),
      update: '',
      generation: generation()
    })
  }

  /** Drops this copy and starts again from the server's, e.g. once the server rebuilt its document. */
  function restart() {
    replaceDoc(new Y.Doc())
    sync()
  }

  /**
   * After a refused edit: this copy is offered again, whole, after a growing pause. The server keeps
   * what it may (so a passing fault loses no typing) and answers with its full copy otherwise.
   */
  function recover() {
    synced.value = false
    pending = []
    if (recoverTimer) return
    const delay = recoverAttempts === 0 ? 0 : Math.min(RECOVER_MAX_MS, 1000 * 2 ** (recoverAttempts - 1))
    recoverAttempts += 1
    recoverTimer = setTimeout(() => {
      recoverTimer = null
      if (!enabled.value) return
      channel.sendDoc({
        type: 'doc-sync',
        vector: toBase64(Y.encodeStateVector(doc.value)),
        update: toBase64(Y.encodeStateAsUpdate(doc.value)),
        generation: generation()
      })
    }, delay)
  }

  function replaceDoc(next: Y.Doc) {
    detach()
    pending = []
    const previous = doc.value
    doc.value = next
    detach = attach(next)
    replacedHandlers.forEach((handler) => handler(next))
    previous.destroy()
  }

  function onState(message: Record<string, unknown>) {
    const update = fromBase64(message.update)
    const serverVector = fromBase64(message.vector)
    if (!update || !serverVector) {
      restart()
      return
    }
    if (message.full) replaceDoc(new Y.Doc())
    Y.applyUpdate(doc.value, update, FROM_SERVER)
    editable.value = Boolean(message.editable)
    const missing = Y.encodeStateAsUpdate(doc.value, serverVector)
    if (missing.length > EMPTY_UPDATE_BYTES) {
      // Edits made here that the server never received: sent now, or dropped if no longer allowed.
      if (!editable.value) {
        restart()
        return
      }
      channel.sendDoc({ type: 'doc-update', update: toBase64(missing), generation: generation() })
    }
    recoverAttempts = 0
    synced.value = true
  }

  function settleFlush(id: unknown, ok: boolean) {
    const waiting = typeof id === 'number' ? flushes.get(id) : undefined
    if (!waiting) return
    clearTimeout(waiting.timer)
    flushes.delete(id as number)
    waiting.resolve(ok)
  }

  channel.onDoc((message) => {
    if (!enabled.value) return
    switch (message.type) {
      case 'doc-state':
        onState(message)
        break
      case 'doc-update': {
        const update = fromBase64(message.update)
        if (update) Y.applyUpdate(doc.value, update, FROM_SERVER)
        else restart()
        break
      }
      case 'doc-reject':
        recover()
        break
      case 'doc-reset':
        restart()
        break
      case 'doc-flushed':
        settleFlush(message.id, Boolean(message.ok))
        break
    }
  })

  channel.onOpen(() => sync())

  channel.onClose(() => {
    synced.value = false
    // A reconnect syncs from scratch, offering anything the server lacks.
    if (recoverTimer) clearTimeout(recoverTimer)
    recoverTimer = null
    flushes.forEach((_, id) => settleFlush(id, false))
  })

  watch(enabled, (on) => {
    if (on && channel.isConnected.value) sync()
    if (!on) synced.value = false
  })

  /** Asks the server to save everything sent so far; true once it has. */
  function flush(): Promise<boolean> {
    if (!enabled.value || !synced.value) return Promise.resolve(false)
    sendPending()
    flushCount += 1
    const id = flushCount
    if (!channel.sendDoc({ type: 'doc-flush', id })) return Promise.resolve(false)
    return new Promise((resolve) => {
      const timer = setTimeout(() => settleFlush(id, false), FLUSH_TIMEOUT_MS)
      flushes.set(id, { resolve, timer })
    })
  }

  function text(name: string): Y.Text {
    return doc.value.getText(name)
  }

  function onReplaced(handler: (doc: Y.Doc) => void) {
    replacedHandlers.push(handler)
  }

  onBeforeUnmount(() => {
    if (sendTimer) clearTimeout(sendTimer)
    if (recoverTimer) clearTimeout(recoverTimer)
    flushes.forEach((_, id) => settleFlush(id, false))
    detach()
    doc.value.destroy()
  })

  /** Asks again, e.g. once the entry is submitted or reopened and what may be edited has changed. */
  function resync() {
    if (channel.isConnected.value) sync()
  }

  return { doc, synced, editable, text, flush, onReplaced, resync }
}
