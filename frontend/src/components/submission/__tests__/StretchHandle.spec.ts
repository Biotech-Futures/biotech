import { afterEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h, ref } from 'vue'
import { mount, type VueWrapper } from '@vue/test-utils'
import StretchHandle from '@/components/submission/StretchHandle.vue'

// A seven-line box; one line is 24.8px, and padding and border add 24.4px.
const NATURAL = 198
const FIVE_LINES = 148
const TWENTY_LINES = 520
let wrapper: VueWrapper | null = null
const height = ref<number | null>(null)

/** The handle inside a box reporting its natural height, as the portal wraps it. */
function mountHandle() {
  height.value = null
  wrapper = mount(
    defineComponent({
      setup: () => () =>
        h('div', { class: 'box' }, [
          // The portal's line height, padding and border, which the handle measures.
          h('textarea', { style: 'line-height: 24.8px; padding: 11.2px 0; border: 1px solid' }),
          h(StretchHandle, { height: height.value, 'onUpdate:height': (v: number) => (height.value = v) }),
        ]),
    }),
    { attachTo: document.body },
  )
  const box = wrapper.find('.box').element as HTMLElement
  vi.spyOn(box, 'offsetHeight', 'get').mockImplementation(() => height.value ?? NATURAL)
  return wrapper.find('[data-testid="stretch-handle"]')
}

const pointer = (type: string, clientY: number) => {
  const event = new Event(type, { bubbles: true }) as Event & { clientY: number }
  Object.defineProperty(event, 'clientY', { value: clientY })
  return event
}

function drag(handle: ReturnType<typeof mountHandle>, by: number) {
  handle.element.dispatchEvent(pointer('pointerdown', 100))
  window.dispatchEvent(pointer('pointermove', 100 + by))
  window.dispatchEvent(pointer('pointerup', 100 + by))
}

afterEach(() => {
  wrapper?.unmount()
  wrapper = null
  vi.restoreAllMocks()
})

describe('StretchHandle', () => {
  it('stretches the box as the bottom border is dragged', () => {
    const handle = mountHandle()

    drag(handle, 120)

    expect(height.value).toBe(NATURAL + 120)
  })

  it('contracts to five lines and no further', () => {
    const handle = mountHandle()

    drag(handle, -30)
    expect(height.value).toBe(NATURAL - 30)

    drag(handle, -500)
    expect(height.value).toBe(FIVE_LINES)
  })

  it('stops at twenty lines', () => {
    const handle = mountHandle()

    drag(handle, 2000)

    expect(height.value).toBe(TWENTY_LINES)
  })

  it('can be resized a line at a time from the keyboard', async () => {
    const handle = mountHandle()

    await handle.trigger('keydown', { key: 'ArrowDown' })
    expect(height.value).toBe(Math.round(NATURAL + 24.8))

    await handle.trigger('keydown', { key: 'ArrowUp' })
    expect(height.value).toBe(NATURAL)
  })
})
