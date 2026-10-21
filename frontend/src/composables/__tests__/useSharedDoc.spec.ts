import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h, nextTick, ref } from 'vue'
import { mount, type VueWrapper } from '@vue/test-utils'
import * as Y from 'yjs'
import { FLUSH_TIMEOUT_MS, SEND_DOC_MS, fromBase64, toBase64, useSharedDoc, type DocChannel } from '@/composables/useSharedDoc'

/** A stand-in for the live room: records what is sent, and lets the test play the server. */
function fakeChannel() {
  const sent: Array<Record<string, unknown>> = []
  const handlers: Array<(message: Record<string, unknown>) => void> = []
  const opens: Array<() => void> = []
  const closes: Array<() => void> = []
  const channel: DocChannel = {
    sendDoc: (message) => {
      if (!channel.isConnected.value) return false
      sent.push(message as Record<string, unknown>)
      return true
    },
    onDoc: (handler) => handlers.push(handler),
    onOpen: (handler) => opens.push(handler),
    onClose: (handler) => closes.push(handler),
    isConnected: ref(false)
  }
  return {
    channel,
    sent,
    open() {
      channel.isConnected.value = true
      opens.forEach((handler) => handler())
    },
    close() {
      channel.isConnected.value = false
      closes.forEach((handler) => handler())
    },
    receive(message: Record<string, unknown>) {
      handlers.forEach((handler) => handler(message))
    }
  }
}

/** The server's copy, answering a page's sync the way the backend does. */
function server(initial: Record<string, string> = {}, generation = 'build-1') {
  const doc = new Y.Doc()
  Object.entries(initial).forEach(([name, value]) => doc.getText(name).insert(0, value))
  doc.getMap('meta').set('generation', generation)
  return {
    doc,
    stateFor(vector: unknown, extra: Record<string, unknown> = {}) {
      const since = fromBase64(vector) ?? new Uint8Array()
      return {
        type: 'doc-state',
        update: toBase64(since.length ? Y.encodeStateAsUpdate(doc, since) : Y.encodeStateAsUpdate(doc)),
        vector: toBase64(Y.encodeStateVector(doc)),
        full: false,
        editable: true,
        ...extra
      }
    }
  }
}

let wrapper: VueWrapper | null = null
let shared: ReturnType<typeof useSharedDoc>
const enabled = ref(true)

function mountShared(channel: DocChannel) {
  wrapper = mount(
    defineComponent({
      setup() {
        shared = useSharedDoc(channel, enabled)
        return () => h('div')
      }
    })
  )
}

beforeEach(() => {
  vi.useFakeTimers()
  enabled.value = true
})

afterEach(() => {
  wrapper?.unmount()
  wrapper = null
  vi.useRealTimers()
})

describe('syncing', () => {
  it("asks for the server's copy on connecting, and is ready once it arrives", () => {
    const room = fakeChannel()
    const truth = server({ 'answer:q1': 'Saved answer.' })
    mountShared(room.channel)

    room.open()
    expect(room.sent[0]!.type).toBe('doc-sync')
    expect(shared.synced.value).toBe(false)
    room.receive(truth.stateFor(room.sent[0]!.vector))

    expect(shared.synced.value).toBe(true)
    expect(shared.editable.value).toBe(true)
    expect(shared.text('answer:q1').toString()).toBe('Saved answer.')
  })

  it('sends the server any edits it missed while disconnected', () => {
    const room = fakeChannel()
    const truth = server({ 'answer:q1': 'Saved.' })
    mountShared(room.channel)
    room.open()
    room.receive(truth.stateFor(room.sent[0]!.vector))
    room.close()

    shared.text('answer:q1').insert(6, ' More.')
    room.open()
    room.receive(truth.stateFor(room.sent.at(-1)!.vector))

    const resend = room.sent.at(-1)!
    expect(resend.type).toBe('doc-update')
    Y.applyUpdate(truth.doc, fromBase64(resend.update)!)
    expect(truth.doc.getText('answer:q1').toString()).toBe('Saved. More.')
  })

  it('drops edits the server will no longer take, and starts again from its copy', () => {
    const room = fakeChannel()
    const truth = server({ 'answer:q1': 'Saved.' })
    mountShared(room.channel)
    room.open()
    room.receive(truth.stateFor(room.sent[0]!.vector))
    room.close()
    shared.text('answer:q1').insert(0, 'Too late. ')

    room.open()
    room.receive(truth.stateFor(room.sent.at(-1)!.vector, { editable: false }))
    room.receive(truth.stateFor(room.sent.at(-1)!.vector, { editable: false }))

    expect(shared.text('answer:q1').toString()).toBe('Saved.')
    expect(shared.editable.value).toBe(false)
  })

  it('takes a full copy in place of its own when told to', () => {
    const room = fakeChannel()
    const truth = server({ 'answer:q1': 'Saved.' })
    mountShared(room.channel)
    room.open()
    shared.text('answer:q1').insert(0, 'Stray. ')
    const replaced = vi.fn()
    shared.onReplaced(replaced)

    room.receive(truth.stateFor('', { full: true }))

    expect(shared.text('answer:q1').toString()).toBe('Saved.')
    expect(replaced).toHaveBeenCalledOnce()
  })
})

describe('editing', () => {
  function ready() {
    const room = fakeChannel()
    const truth = server({ 'answer:q1': '' })
    mountShared(room.channel)
    room.open()
    room.receive(truth.stateFor(room.sent[0]!.vector))
    room.sent.length = 0
    return { room, truth }
  }

  it('sends edits merged, at most every 100ms', () => {
    const { room, truth } = ready()

    shared.text('answer:q1').insert(0, 'a')
    shared.text('answer:q1').insert(1, 'b')
    expect(room.sent).toHaveLength(0)
    vi.advanceTimersByTime(SEND_DOC_MS)

    expect(room.sent).toHaveLength(1)
    Y.applyUpdate(truth.doc, fromBase64(room.sent[0]!.update)!)
    expect(truth.doc.getText('answer:q1').toString()).toBe('ab')
  })

  it("shows a teammate's update without sending it back", () => {
    const { room, truth } = ready()
    const vector = Y.encodeStateVector(truth.doc)
    truth.doc.getText('answer:q1').insert(0, 'From Ben.')

    room.receive({ type: 'doc-update', update: toBase64(Y.encodeStateAsUpdate(truth.doc, vector)) })
    vi.advanceTimersByTime(SEND_DOC_MS)

    expect(shared.text('answer:q1').toString()).toBe('From Ben.')
    expect(room.sent).toHaveLength(0)
  })

  it('keeps its typing through a refused edit and offers it to the server again', () => {
    const { room, truth } = ready()
    shared.text('answer:q1').insert(0, 'Typed just now')
    const before = shared.doc.value

    room.receive({ type: 'doc-reject' })
    vi.advanceTimersByTime(0)

    expect(shared.doc.value).toBe(before)
    expect(shared.synced.value).toBe(false)
    const offer = room.sent.at(-1)!
    expect(offer.type).toBe('doc-sync')
    Y.applyUpdate(truth.doc, fromBase64(offer.update)!)
    expect(truth.doc.getText('answer:q1').toString()).toBe('Typed just now')
  })

  it('stops counting as ready when the connection drops', () => {
    const { room } = ready()

    room.close()

    expect(shared.synced.value).toBe(false)
  })
})

describe('saving now', () => {
  it('resolves once the server says it has saved, sending any held edits first', async () => {
    const room = fakeChannel()
    const truth = server({ 'answer:q1': '' })
    mountShared(room.channel)
    room.open()
    room.receive(truth.stateFor(room.sent[0]!.vector))
    shared.text('answer:q1').insert(0, 'Last words')

    const saving = shared.flush()
    const flushRequest = room.sent.at(-1)!
    expect(room.sent.at(-2)!.type).toBe('doc-update')
    room.receive({ type: 'doc-flushed', id: flushRequest.id, ok: true })

    await expect(saving).resolves.toBe(true)
  })

  it('fails when no answer comes in time, or the connection drops', async () => {
    const room = fakeChannel()
    const truth = server()
    mountShared(room.channel)
    room.open()
    room.receive(truth.stateFor(room.sent[0]!.vector))

    const timedOut = shared.flush()
    vi.advanceTimersByTime(FLUSH_TIMEOUT_MS)
    await expect(timedOut).resolves.toBe(false)

    const dropped = shared.flush()
    room.close()
    await expect(dropped).resolves.toBe(false)
  })

  it('fails at once before the document is ready', async () => {
    const room = fakeChannel()
    mountShared(room.channel)

    await expect(shared.flush()).resolves.toBe(false)
  })
})

describe('switching on', () => {
  it('syncs when co-editing is switched on while connected', async () => {
    enabled.value = false
    const room = fakeChannel()
    mountShared(room.channel)
    room.open()
    expect(room.sent).toHaveLength(0)

    enabled.value = true
    await nextTick()

    expect(room.sent[0]!.type).toBe('doc-sync')
  })
})


describe('faults', () => {
  function ready(initial: Record<string, string> = { 'answer:q1': 'Saved.' }) {
    const room = fakeChannel()
    const truth = server(initial)
    mountShared(room.channel)
    room.open()
    room.receive(truth.stateFor(room.sent[0]!.vector))
    room.sent.length = 0
    return { room, truth }
  }
  const syncsSent = (room: ReturnType<typeof fakeChannel>) => room.sent.filter((m) => m.type === 'doc-sync').length

  it('backs off while the server keeps refusing, instead of hammering it', () => {
    const { room } = ready()

    room.receive({ type: 'doc-reject' })
    vi.advanceTimersByTime(0)
    expect(syncsSent(room)).toBe(1)
    room.receive({ type: 'doc-reject' })
    vi.advanceTimersByTime(999)
    expect(syncsSent(room)).toBe(1)
    vi.advanceTimersByTime(1)
    expect(syncsSent(room)).toBe(2)
    room.receive({ type: 'doc-reject' })
    vi.advanceTimersByTime(1999)
    expect(syncsSent(room)).toBe(2)
    vi.advanceTimersByTime(1)

    expect(syncsSent(room)).toBe(3)
  })

  it("takes the server's copy when the offered edits are no longer allowed", () => {
    const { room, truth } = ready()
    shared.text('answer:q1').insert(0, 'Too late. ')

    room.receive({ type: 'doc-reject' })
    vi.advanceTimersByTime(0)
    room.receive(truth.stateFor('', { full: true, editable: false }))

    expect(shared.text('answer:q1').toString()).toBe('Saved.')
    expect(shared.editable.value).toBe(false)
  })

  it('counts as ready again once a retry gets through, and resets the back-off', () => {
    const { room, truth } = ready()

    room.receive({ type: 'doc-reject' })
    vi.advanceTimersByTime(0)
    room.receive(truth.stateFor(room.sent.at(-1)!.vector))
    room.receive({ type: 'doc-reject' })
    vi.advanceTimersByTime(0)

    expect(syncsSent(room)).toBe(2)
  })

  it("applies a teammate's update that arrives before the server's copy", () => {
    const room = fakeChannel()
    const truth = server({ 'answer:q1': 'Saved.' })
    mountShared(room.channel)
    room.open()
    const vector = Y.encodeStateVector(truth.doc)
    truth.doc.getText('answer:q1').insert(6, ' Ben.')

    room.receive({ type: 'doc-update', update: toBase64(Y.encodeStateAsUpdate(truth.doc, vector)) })
    room.receive(truth.stateFor(room.sent[0]!.vector))

    expect(shared.text('answer:q1').toString()).toBe('Saved. Ben.')
  })

  it('starts again on a malformed update or a server copy without its state vector', () => {
    const { room, truth } = ready()
    const first = shared.doc.value

    room.receive({ type: 'doc-update', update: '%%%' })
    expect(shared.doc.value).not.toBe(first)
    room.receive(truth.stateFor('', { vector: undefined }))

    expect(shared.synced.value).toBe(false)
  })

  it("replaces its copy when the server rebuilt the document", () => {
    const { room } = ready()
    shared.text('answer:q1').insert(0, 'Stale. ')
    const before = shared.doc.value

    room.receive({ type: 'doc-reset' })

    expect(shared.doc.value).not.toBe(before)
    expect(shared.text('answer:q1').toString()).toBe('')
    expect(room.sent.at(-1)!.type).toBe('doc-sync')
  })

  it('names the build its copy came from in everything it sends, so the server never merges another', () => {
    const { room } = ready()
    shared.text('answer:q1').insert(6, ' More.')
    vi.advanceTimersByTime(SEND_DOC_MS)
    room.receive({ type: 'doc-reject' })
    vi.advanceTimersByTime(0)
    room.close()
    room.open()

    expect(room.sent.map((m) => [m.type, m.generation])).toEqual([
      ['doc-update', 'build-1'],
      ['doc-sync', 'build-1'],
      ['doc-sync', 'build-1']
    ])
  })

  it("swaps in a rebuilt server copy instead of merging its own into it", () => {
    const { room } = ready()
    shared.text('answer:q1').insert(6, ' Unsaved.')
    const rebuilt = server({ 'answer:q1': 'Saved.' }, 'build-2')

    room.receive({ type: 'doc-reject' })
    vi.advanceTimersByTime(0)
    room.receive(rebuilt.stateFor('', { full: true }))
    vi.advanceTimersByTime(SEND_DOC_MS)

    expect(shared.text('answer:q1').toString()).toBe('Saved.')
    expect(room.sent.at(-1)!.type).toBe('doc-sync')
    shared.text('answer:q1').insert(6, '!')
    vi.advanceTimersByTime(SEND_DOC_MS)
    expect(room.sent.at(-1)!.generation).toBe('build-2')
  })

  it('asks again for what it missed when an update goes missing on the way, without pausing typing', () => {
    const { room, truth } = ready()
    truth.doc.getText('answer:q1').insert(6, ' A')
    // That update never arrives; the next one builds on it.
    const afterA = Y.encodeStateVector(truth.doc)
    truth.doc.getText('answer:q1').insert(8, ' B')

    room.receive({ type: 'doc-update', update: toBase64(Y.encodeStateAsUpdate(truth.doc, afterA)) })
    expect(shared.text('answer:q1').toString()).toBe('Saved.')
    expect(shared.synced.value).toBe(true)
    const ask = room.sent.at(-1)!
    expect(ask.type).toBe('doc-sync')
    room.receive(truth.stateFor(ask.vector))

    expect(shared.text('answer:q1').toString()).toBe('Saved. A B')
    expect(room.sent.filter((m) => m.type === 'doc-sync')).toHaveLength(1)
  })

  it('fails a save-now at once while recovering, so Submit can offer the last saved answers', async () => {
    const { room } = ready()

    room.receive({ type: 'doc-reject' })

    await expect(shared.flush()).resolves.toBe(false)
  })

  it('drops a pending retry when the connection drops, and syncs afresh on reconnecting', () => {
    const { room } = ready()
    room.receive({ type: 'doc-reject' })
    vi.advanceTimersByTime(0)
    room.receive({ type: 'doc-reject' })
    room.close()
    room.sent.length = 0

    vi.advanceTimersByTime(60_000)
    expect(room.sent).toHaveLength(0)
    room.open()

    expect(room.sent[0]!.type).toBe('doc-sync')
  })
})
