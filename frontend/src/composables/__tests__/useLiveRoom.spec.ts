import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h, nextTick, ref } from 'vue'
import { mount, type VueWrapper } from '@vue/test-utils'
import {
  MAX_TEXT_LENGTH,
  RESEND_TYPING_MS,
  SEND_TEXT_MS,
  STOP_TYPING_MS,
  TYPING_EXPIRES_MS,
  typingLabel,
  useLiveRoom,
} from '@/composables/useLiveRoom'

/** A stand-in socket the test opens, feeds and drops by hand. */
class FakeSocket {
  static OPEN = 1
  static instances: FakeSocket[] = []
  readyState = 0
  sent: Array<{ type: string; field: string; typing?: boolean; text?: string }> = []
  onopen: (() => void) | null = null
  onmessage: ((event: { data: string }) => void) | null = null
  onclose: ((event: { code: number }) => void) | null = null

  constructor(public url: string) {
    FakeSocket.instances.push(this)
  }

  send(data: string) {
    this.sent.push(JSON.parse(data))
  }

  close(code = 1000) {
    this.readyState = 3
    this.onclose?.({ code })
  }

  /** Opens, then says who we are, as the server does. */
  open() {
    this.readyState = FakeSocket.OPEN
    this.onopen?.()
    this.receive({ type: 'hello', user: { id: 1, name: 'Me' } })
  }

  receive(event: object) {
    this.onmessage?.({ data: JSON.stringify(event) })
  }
}

const latest = () => FakeSocket.instances[FakeSocket.instances.length - 1]!
const typing = (id: number, name: string, field: string, on = true) => ({
  type: 'typing',
  user: { id, name },
  field,
  typing: on,
})

let wrapper: VueWrapper | null = null
let live: ReturnType<typeof useLiveRoom>
const roomId = ref('1')
const active = ref(true)

function mountRoom() {
  wrapper = mount(
    defineComponent({
      setup() {
        live = useLiveRoom('submission', roomId, active)
        return () => h('div')
      },
    }),
  )
}

beforeEach(() => {
  vi.useFakeTimers()
  FakeSocket.instances = []
  vi.stubGlobal('WebSocket', FakeSocket)
  roomId.value = '1'
  active.value = true
})

afterEach(() => {
  wrapper?.unmount()
  wrapper = null
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

describe('typingLabel', () => {
  it('names one or two people and counts more', () => {
    expect(typingLabel([])).toBe('')
    expect(typingLabel(['Amy'])).toBe('Amy is typing…')
    expect(typingLabel(['Amy', 'Ben'])).toBe('Amy and Ben are typing…')
    expect(typingLabel(['Amy', 'Ben', 'Cy'])).toBe('3 teammates are typing…')
  })
})

describe('connecting', () => {
  it('joins the room for the item while active', () => {
    mountRoom()

    expect(FakeSocket.instances).toHaveLength(1)
    expect(latest().url).toBe('ws://localhost:8000/ws/live/submission/1/')
  })

  it('stays disconnected while inactive and leaves when made inactive', async () => {
    active.value = false
    mountRoom()
    expect(FakeSocket.instances).toHaveLength(0)

    active.value = true
    await nextTick()
    latest().open()
    latest().receive(typing(2, 'Ben', 'q1'))
    active.value = false
    await nextTick()

    expect(latest().readyState).toBe(3)
    expect(live.typingIn('q1')).toEqual([])
  })

  it('leaves while the tab is hidden and rejoins when it is shown', async () => {
    mountRoom()
    const visibility = vi.spyOn(document, 'visibilityState', 'get')

    visibility.mockReturnValue('hidden')
    document.dispatchEvent(new Event('visibilitychange'))
    await nextTick()
    expect(FakeSocket.instances[0]!.readyState).toBe(3)

    visibility.mockReturnValue('visible')
    document.dispatchEvent(new Event('visibilitychange'))
    await nextTick()
    expect(FakeSocket.instances).toHaveLength(2)
  })

  it('reconnects by itself after a dropped connection', () => {
    mountRoom()
    latest().open()

    latest().close(1006)
    expect(FakeSocket.instances).toHaveLength(1)

    vi.advanceTimersByTime(1000)
    expect(FakeSocket.instances).toHaveLength(2)
  })

  it('does not retry when refused entry', () => {
    mountRoom()

    latest().close(4403)
    vi.advanceTimersByTime(60_000)

    expect(FakeSocket.instances).toHaveLength(1)
  })

  it('switches rooms when the item changes', async () => {
    mountRoom()

    roomId.value = '2'
    await nextTick()

    expect(FakeSocket.instances[0]!.readyState).toBe(3)
    expect(latest().url).toContain('/ws/live/submission/2/')
  })
})

describe('sending', () => {
  it('signals typing at most every few seconds and stops after a pause', () => {
    mountRoom()
    latest().open()

    live.sendTyping('q1')
    live.sendTyping('q1')
    vi.advanceTimersByTime(RESEND_TYPING_MS)
    live.sendTyping('q1')
    vi.advanceTimersByTime(STOP_TYPING_MS)

    expect(latest().sent).toEqual([
      { type: 'typing', field: 'q1', typing: true },
      { type: 'typing', field: 'q1', typing: true },
      { type: 'typing', field: 'q1', typing: false },
    ])
  })

  it('sends nothing before the connection is open', () => {
    mountRoom()

    live.sendTyping('q1')
    vi.advanceTimersByTime(STOP_TYPING_MS)

    expect(latest().sent).toEqual([])
  })
})

describe('receiving', () => {
  it('shows teammates typing in a field until they stop', () => {
    mountRoom()
    latest().open()

    latest().receive(typing(2, 'Ben', 'q1'))
    latest().receive(typing(3, 'Cy', 'q1'))
    expect(live.typingIn('q1')).toEqual(['Ben', 'Cy'])
    expect(live.typingIn('q2')).toEqual([])

    latest().receive(typing(2, 'Ben', 'q1', false))
    expect(live.typingIn('q1')).toEqual(['Cy'])
  })

  it('counts someone with two tabs once', () => {
    mountRoom()
    latest().open()

    latest().receive(typing(2, 'Ben', 'q1'))
    latest().receive(typing(2, 'Ben', 'q1'))

    expect(live.typingIn('q1')).toEqual(['Ben'])
  })

  it('lets a label fade when no fresh signal arrives', () => {
    mountRoom()
    latest().open()
    latest().receive(typing(2, 'Ben', 'q1'))

    vi.advanceTimersByTime(TYPING_EXPIRES_MS - 1)
    latest().receive(typing(2, 'Ben', 'q1'))
    vi.advanceTimersByTime(TYPING_EXPIRES_MS - 1)
    expect(live.typingIn('q1')).toEqual(['Ben'])

    vi.advanceTimersByTime(1)
    expect(live.typingIn('q1')).toEqual([])
  })

  it('ignores anything it does not understand', () => {
    mountRoom()
    latest().open()

    latest().onmessage?.({ data: 'not json' })
    latest().receive({ type: 'changed', item: 'notes' })
    latest().receive({ type: 'typing', field: 'q1', typing: true, user: { name: 'No id' } })

    expect(live.typingIn('q1')).toEqual([])
  })
})

describe('live text', () => {
  const text = (id: number, name: string, field: string, value: string) => ({
    type: 'text',
    user: { id, name },
    field,
    text: value,
  })

  const typeIn = (field: string, value: string) => {
    live.sendTyping(field)
    live.sendText(field, value)
  }

  it('sends the field at once, then at most every quarter second, ending on the latest', () => {
    mountRoom()
    latest().open()

    typeIn('q1', 'a')
    typeIn('q1', 'ab')
    typeIn('q1', 'abc')
    vi.advanceTimersByTime(SEND_TEXT_MS)
    vi.advanceTimersByTime(SEND_TEXT_MS)

    const texts = latest().sent.filter((m) => m.type === 'text').map((m) => m.text)
    expect(texts).toEqual(['a', 'abc'])
  })

  it('sends nothing for a paste over the size cap', () => {
    mountRoom()
    latest().open()

    typeIn('q1', 'x'.repeat(MAX_TEXT_LENGTH + 1))

    expect(latest().sent.filter((m) => m.type === 'text')).toEqual([])
  })

  it('hands a teammate’s text over and locks the field until they stop', () => {
    const received: Array<[string, string]> = []
    mountRoom()
    live.onRemoteText((field, value) => received.push([field, value]))
    latest().open()

    latest().receive(typing(2, 'Ben', 'q1'))
    latest().receive(text(2, 'Ben', 'q1', 'Our idea'))

    expect(received).toEqual([['q1', 'Our idea']])
    expect(live.isLocked('q1')).toBe(true)
    expect(live.isLocked('q2')).toBe(false)

    latest().receive(typing(2, 'Ben', 'q1', false))
    expect(live.isLocked('q1')).toBe(false)
  })

  it('unlocks by itself if the typist vanishes', () => {
    mountRoom()
    latest().open()
    latest().receive(text(2, 'Ben', 'q1', 'Our idea'))

    vi.advanceTimersByTime(TYPING_EXPIRES_MS)

    expect(live.isLocked('q1')).toBe(false)
  })

  it('settles two people starting together: the earlier account keeps the field', () => {
    const received: string[] = []
    mountRoom()
    live.onRemoteText((_, value) => received.push(value))
    latest().open()
    latest().receive({ type: 'hello', user: { id: 5, name: 'Me' } })
    typeIn('q1', 'mine')

    latest().receive(text(9, 'Later', 'q1', 'theirs'))
    expect(received).toEqual([])
    expect(live.isLocked('q1')).toBe(false)

    latest().receive(text(3, 'Earlier', 'q1', 'first'))
    expect(received).toEqual(['first'])
    expect(live.isLocked('q1')).toBe(true)
    expect(latest().sent).toContainEqual({ type: 'typing', field: 'q1', typing: false })
  })
})

describe('settling', () => {
  it('signals when a field is released and when a dropped connection comes back', () => {
    const settled = vi.fn()
    mountRoom()
    live.onSettled(settled)
    latest().open()

    latest().receive(typing(2, 'Ben', 'q1'))
    latest().receive(typing(2, 'Ben', 'q1', false))
    expect(settled).toHaveBeenCalledTimes(1)

    latest().close(1006)
    vi.advanceTimersByTime(1000)
    latest().open()
    expect(settled).toHaveBeenCalledTimes(3)
  })

  it('stays quiet when leaving on purpose', async () => {
    const settled = vi.fn()
    mountRoom()
    live.onSettled(settled)
    latest().open()

    active.value = false
    await nextTick()

    expect(settled).not.toHaveBeenCalled()
  })
})

describe('identity and cursor', () => {
  it('stays silent until the server says who we are', () => {
    mountRoom()
    latest().readyState = FakeSocket.OPEN
    latest().onopen?.()

    live.sendTyping('q1')
    live.sendText('q1', 'early')

    expect(latest().sent).toEqual([])
  })

  it('knows where a teammate’s cursor is, and forgets it when they stop', () => {
    mountRoom()
    latest().open()

    latest().receive({ type: 'text', user: { id: 2, name: 'Ben' }, field: 'q1', text: 'abcdef', caret: 3 })
    expect(live.caretIn('q1')).toBe(3)

    latest().receive({ type: 'text', user: { id: 2, name: 'Ben' }, field: 'q1', text: 'abc', caret: 99 })
    expect(live.caretIn('q1')).toBe(3)

    latest().receive({ type: 'typing', user: { id: 2, name: 'Ben' }, field: 'q1', typing: false })
    expect(live.caretIn('q1')).toBeNull()
  })

  it('sends where your own cursor is', () => {
    mountRoom()
    latest().open()

    live.sendTyping('q1')
    live.sendText('q1', 'abcdef', 2)

    expect(latest().sent).toContainEqual({ type: 'text', field: 'q1', text: 'abcdef', caret: 2 })
  })
})
