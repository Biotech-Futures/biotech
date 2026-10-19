import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import LiveTextPanel from '@/components/live/LiveTextPanel.vue'
import { SEND_TEXT_MS } from '@/composables/useLiveRoom'

let now = 0
let frames: FrameRequestCallback[] = []

/** Runs animation frames up to `ms` from now. */
function advance(ms: number) {
  const end = now + ms
  while (now < end) {
    now = Math.min(end, now + 16)
    const due = frames
    frames = []
    due.forEach((callback) => callback(now))
  }
}

beforeEach(() => {
  now = 0
  frames = []
  vi.spyOn(performance, 'now').mockImplementation(() => now)
  vi.stubGlobal('requestAnimationFrame', (callback: FrameRequestCallback) => frames.push(callback))
  vi.stubGlobal('cancelAnimationFrame', () => {
    frames = []
  })
})

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

const shownText = (wrapper: ReturnType<typeof mount>) => wrapper.find('[data-testid="live-text"]').text()

describe('LiveTextPanel', () => {
  it('shows the text with the cursor where the typist is', () => {
    const wrapper = mount(LiveTextPanel, { props: { text: 'Our idea', caret: 3 } })

    const box = wrapper.find('[data-testid="live-text"]').element
    expect(box.firstChild?.textContent).toBe('Our')
    expect(box.querySelector('.live-text__caret')).not.toBeNull()
    expect(box.lastChild?.textContent).toBe(' idea')
  })

  it('types out added text over the gap between updates', async () => {
    const wrapper = mount(LiveTextPanel, { props: { text: 'Our', caret: null } })

    await wrapper.setProps({ text: 'Our idea is' })
    advance(SEND_TEXT_MS / 2)
    await wrapper.vm.$nextTick()
    const midway = shownText(wrapper)
    expect(midway.length).toBeGreaterThan('Our'.length)
    expect(midway.length).toBeLessThan('Our idea is'.length)

    advance(SEND_TEXT_MS)
    await wrapper.vm.$nextTick()
    expect(shownText(wrapper)).toBe('Our idea is')
  })

  it('shows deletions and edits at once', async () => {
    const wrapper = mount(LiveTextPanel, { props: { text: 'Our idea', caret: null } })

    await wrapper.setProps({ text: 'Your idea' })

    expect(shownText(wrapper)).toBe('Your idea')
  })
})
