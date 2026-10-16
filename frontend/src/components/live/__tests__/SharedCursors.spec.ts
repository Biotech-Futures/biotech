import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount, type VueWrapper } from '@vue/test-utils'
import { nextTick, ref } from 'vue'
import SharedCursors, { LABEL_MS } from '@/components/live/SharedCursors.vue'
import type { PlacedCursor } from '@/composables/useCoeditedFields'

/** The test browser lays nothing out, so each element reports a size; markers sit at `top` by cursor id. */
const tops: Record<string, number> = {}
let shown = true

function fakeLayout() {
  const define = (name: string, get: (this: HTMLElement) => unknown) =>
    vi.spyOn(HTMLElement.prototype, name as 'offsetTop', 'get').mockImplementation(get as () => number)
  define('offsetParent', function () {
    return shown ? document.body : null
  })
  define('offsetTop', function () {
    return this.dataset.cursor ? (tops[this.dataset.cursor] ?? 10) : 0
  })
  define('offsetLeft', function () {
    return this.dataset.cursor ? 40 : 0
  })
  define('offsetHeight', () => 18)
  vi.spyOn(Element.prototype, 'clientWidth', 'get').mockImplementation(() => 300)
  vi.spyOn(Element.prototype, 'clientHeight', 'get').mockImplementation(() => 120)
}

let wrapper: VueWrapper | null = null
let box: HTMLTextAreaElement

function mountOver(text: string, cursors: PlacedCursor[]) {
  box = document.createElement('textarea')
  box.value = text
  document.body.appendChild(box)
  const source = { target: () => box, text: ref(text), cursors: ref(cursors) }
  wrapper = mount(SharedCursors, { props: { source }, attachTo: document.body })
  return source
}

const carets = () => wrapper!.findAll('[data-testid="shared-cursor"]')

beforeEach(() => {
  vi.useFakeTimers()
  vi.setSystemTime(10_000)
  shown = true
  Object.keys(tops).forEach((key) => delete tops[key])
  fakeLayout()
})

afterEach(() => {
  wrapper?.unmount()
  wrapper = null
  box?.remove()
  vi.restoreAllMocks()
  vi.useRealTimers()
})

describe('SharedCursors', () => {
  it("draws each teammate's cursor where it falls in the text", async () => {
    mountOver('Our idea is', [
      { id: 2, name: 'Ben', index: 3, startedAt: null },
      { id: 3, name: 'Cy', index: 8, startedAt: null }
    ])
    await vi.runOnlyPendingTimersAsync()
    await nextTick()

    expect(carets()).toHaveLength(2)
    expect(carets()[0]!.attributes('style')).toContain('left: 40px')
    expect(wrapper!.find('.shared-cursors__mirror').text()).toBe('Our idea is')
  })

  it('names a teammate as they start typing, and drops the name a couple of seconds after', async () => {
    mountOver('Our idea', [{ id: 2, name: 'Ben', index: 3, startedAt: 10_000 }])
    await vi.advanceTimersByTimeAsync(0)
    await nextTick()
    expect(wrapper!.find('.shared-cursors__name').classes()).toContain('is-shown')
    expect(wrapper!.find('.shared-cursors__name').text()).toBe('Ben')

    await vi.advanceTimersByTimeAsync(LABEL_MS)
    await nextTick()

    expect(carets()).toHaveLength(1)
    expect(wrapper!.find('.shared-cursors__name').classes()).not.toContain('is-shown')
  })

  it('shows no name for a cursor that only moved', async () => {
    mountOver('Our idea', [{ id: 2, name: 'Ben', index: 3, startedAt: null }])
    await vi.advanceTimersByTimeAsync(0)
    await nextTick()

    expect(wrapper!.find('.shared-cursors__name').classes()).not.toContain('is-shown')
  })

  it('leaves out a cursor scrolled out of the box', async () => {
    tops['3'] = 500
    mountOver('Our idea is long', [
      { id: 2, name: 'Ben', index: 3, startedAt: null },
      { id: 3, name: 'Cy', index: 12, startedAt: null }
    ])
    await vi.advanceTimersByTimeAsync(0)
    await nextTick()

    expect(carets()).toHaveLength(1)
  })

  it('moves with the text, and draws nothing over a hidden box or with nobody else in it', async () => {
    const source = mountOver('Our idea', [{ id: 2, name: 'Ben', index: 3, startedAt: null }])
    await vi.advanceTimersByTimeAsync(0)
    await nextTick()
    source.text.value = 'So, our idea'
    source.cursors.value = [{ id: 2, name: 'Ben', index: 7, startedAt: null }]
    await vi.advanceTimersByTimeAsync(0)
    await nextTick()
    expect(wrapper!.find('.shared-cursors__mirror').text()).toBe('So, our idea')

    source.cursors.value = []
    await nextTick()
    expect(wrapper!.find('.shared-cursors').exists()).toBe(false)

    shown = false
    source.cursors.value = [{ id: 2, name: 'Ben', index: 3, startedAt: null }]
    await vi.advanceTimersByTimeAsync(0)
    await nextTick()
    expect(wrapper!.find('.shared-cursors').exists()).toBe(false)
  })
})
