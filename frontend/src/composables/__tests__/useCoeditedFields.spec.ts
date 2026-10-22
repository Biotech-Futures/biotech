import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h, nextTick, ref } from 'vue'
import { mount, type VueWrapper } from '@vue/test-utils'
import * as Y from 'yjs'
import { FALLBACK_CATCH_UP_MS, LIVE_FALLBACK_MS, useCoeditedFields } from '@/composables/useCoeditedFields'
import { toBase64 } from '@/composables/useSharedDoc'
import type { useLiveRoom } from '@/composables/useLiveRoom'

/** The parts of a live room the boxes use, played by the test. */
function fakeLive() {
  const handlers: Array<(message: Record<string, unknown>) => void> = []
  const opens: Array<() => void> = []
  const sent: Array<Record<string, unknown>> = []
  const live = {
    isConnected: ref(false),
    sendDoc: (message: object) => {
      if (!live.isConnected.value) return false
      sent.push(message as Record<string, unknown>)
      return true
    },
    onDoc: (handler: (message: Record<string, unknown>) => void) => handlers.push(handler),
    onOpen: (handler: () => void) => opens.push(handler),
    onClose: () => {},
    cursorsIn: () => [],
    sendCursor: vi.fn(),
    sendTyping: vi.fn()
  }
  return {
    live: live as unknown as ReturnType<typeof useLiveRoom>,
    sent,
    /** The connection opens and the server sends its copy with "Saved." in the answer. */
    connect() {
      live.isConnected.value = true
      opens.forEach((handler) => handler())
      const doc = new Y.Doc()
      doc.getText('answer:q1').insert(0, 'Saved.')
      handlers.forEach((handler) =>
        handler({
          type: 'doc-state',
          update: toBase64(Y.encodeStateAsUpdate(doc)),
          vector: toBase64(Y.encodeStateVector(doc)),
          full: false,
          editable: true
        })
      )
    }
  }
}

let wrapper: VueWrapper | null = null

function mountBoxes(overrides: { adminAccess?: boolean; mayShow?: () => boolean; saveTyping?: () => Promise<boolean> } = {}) {
  const room = fakeLive()
  const shown: Array<[string, string]> = []
  const hooks = {
    keepSaved: vi.fn((change: () => void) => change()),
    saveTyping: vi.fn(overrides.saveTyping ?? (async () => true)),
    catchUp: vi.fn(async () => {})
  }
  let fields!: ReturnType<typeof useCoeditedFields>
  wrapper = mount(
    defineComponent({
      setup() {
        fields = useCoeditedFields({
          live: room.live,
          coediting: ref(true),
          adminAccess: ref(overrides.adminAccess ?? false),
          isEditable: ref(true),
          boxes: ref(['q1']),
          sharedName: (box) => `answer:${box}`,
          mayShow: overrides.mayShow ?? (() => true),
          showSaved: (box, value) => shown.push([box, value]),
          fallback: hooks
        })
        return () => h('textarea', { id: 'q1' })
      }
    }),
    { attachTo: document.body }
  )
  return { room, shown, hooks, fields }
}

let visibility: DocumentVisibilityState = 'visible'

beforeEach(() => {
  vi.useFakeTimers()
  visibility = 'visible'
  vi.spyOn(document, 'visibilityState', 'get').mockImplementation(() => visibility)
})

afterEach(() => {
  wrapper?.unmount()
  wrapper = null
  vi.restoreAllMocks()
  vi.useRealTimers()
})

describe('useCoeditedFields', () => {
  it('shows the shared text as saved once it arrives, unless the page says not to', async () => {
    const { room, shown } = mountBoxes()
    await nextTick()
    room.connect()
    await nextTick()
    expect(shown).toContainEqual(['q1', 'Saved.'])

    wrapper!.unmount()
    const blocked = mountBoxes({ mayShow: () => false })
    await nextTick()
    blocked.room.connect()
    await nextTick()
    expect(blocked.shown).toEqual([])
  })

  it('saves without the live connection after ten seconds, keeping the page saved and catching up', async () => {
    const { fields, hooks } = mountBoxes()
    await nextTick()

    vi.advanceTimersByTime(LIVE_FALLBACK_MS)
    await nextTick()

    expect(fields.savingWithoutLive.value).toBe(true)
    expect(fields.typingShared.value).toBe(false)
    expect(hooks.keepSaved).toHaveBeenCalledOnce()
    expect(hooks.catchUp).toHaveBeenCalledOnce()
    vi.advanceTimersByTime(FALLBACK_CATCH_UP_MS)
    expect(hooks.catchUp).toHaveBeenCalledTimes(2)
  })

  it('waits while the tab is hidden, since nothing can be typed then', async () => {
    visibility = 'hidden'
    const { fields } = mountBoxes()
    await nextTick()

    vi.advanceTimersByTime(LIVE_FALLBACK_MS * 3)

    expect(fields.savingWithoutLive.value).toBe(false)
  })

  it('goes back to live editing only once what was typed is saved', async () => {
    let saved = false
    const { room, fields, hooks } = mountBoxes({ saveTyping: async () => saved })
    await nextTick()
    vi.advanceTimersByTime(LIVE_FALLBACK_MS)
    await nextTick()

    room.connect()
    await vi.advanceTimersByTimeAsync(0)
    expect(hooks.saveTyping).toHaveBeenCalled()
    expect(fields.savingWithoutLive.value).toBe(true)

    saved = true
    await vi.advanceTimersByTimeAsync(FALLBACK_CATCH_UP_MS)
    expect(fields.savingWithoutLive.value).toBe(false)
    expect(room.sent.at(-1)).toMatchObject({ type: 'doc-sync' })
  })

  it('never switches an admin, who edits privately anyway', async () => {
    const { fields } = mountBoxes({ adminAccess: true })
    await nextTick()

    vi.advanceTimersByTime(LIVE_FALLBACK_MS * 2)

    expect(fields.savingWithoutLive.value).toBe(false)
    expect(fields.note.value).toBe('')
  })
})
