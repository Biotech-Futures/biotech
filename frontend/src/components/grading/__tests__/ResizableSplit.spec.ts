import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import ResizableSplit from '@/components/grading/ResizableSplit.vue'

const mountSplit = (props: Record<string, unknown> = {}) =>
  mount(ResizableSplit, {
    props,
    slots: { left: '<div class="l">L</div>', right: '<div class="r">R</div>' }
  })

const cols = (wrapper: ReturnType<typeof mountSplit>) =>
  (wrapper.element as HTMLElement).style.getPropertyValue('--split-cols')

beforeEach(() => {
  // jsdom has no pointer-capture; the drag handlers call it unconditionally.
  Element.prototype.setPointerCapture = vi.fn()
})

describe('untouched layout', () => {
  it('caps the right pane at its content limit when one is given', () => {
    expect(cols(mountSplit({ rightMax: '28rem' }))).toBe(
      'minmax(0, 1fr) auto fit-content(28rem)'
    )
  })

  it('splits evenly-ish when no cap is given', () => {
    expect(cols(mountSplit())).toBe('minmax(0, 1fr) auto minmax(0, 1fr)')
  })

  it('renders both slots around an accessible separator', () => {
    const wrapper = mountSplit()
    expect(wrapper.find('.l').text()).toBe('L')
    expect(wrapper.find('.r').text()).toBe('R')
    const divider = wrapper.find('[role="separator"]')
    expect(divider.attributes('aria-orientation')).toBe('vertical')
    expect(divider.attributes('tabindex')).toBe('0')
  })
})

describe('keyboard resizing', () => {
  it('arrow keys nudge the split from the measured midpoint', async () => {
    const wrapper = mountSplit()
    const divider = wrapper.find('[role="separator"]')
    // jsdom measures nothing, so the first nudge starts from the 50% fallback.
    await divider.trigger('keydown', { key: 'ArrowRight' })
    expect(cols(wrapper)).toBe('52% auto minmax(0, 1fr)')
    await divider.trigger('keydown', { key: 'ArrowLeft' })
    await divider.trigger('keydown', { key: 'ArrowLeft' })
    expect(cols(wrapper)).toBe('48% auto minmax(0, 1fr)')
  })

  it('clamps between 25 and 75 percent', async () => {
    const wrapper = mountSplit()
    const divider = wrapper.find('[role="separator"]')
    for (let i = 0; i < 30; i++) await divider.trigger('keydown', { key: 'ArrowLeft' })
    expect(cols(wrapper)).toBe('25% auto minmax(0, 1fr)')
    for (let i = 0; i < 60; i++) await divider.trigger('keydown', { key: 'ArrowRight' })
    expect(cols(wrapper)).toBe('75% auto minmax(0, 1fr)')
  })

  it('ignores keys that are not arrows', async () => {
    const wrapper = mountSplit()
    await wrapper.find('[role="separator"]').trigger('keydown', { key: 'Enter' })
    expect(cols(wrapper)).toBe('minmax(0, 1fr) auto minmax(0, 1fr)')
  })
})

describe('pointer dragging', () => {
  it('tracks the pointer as a clamped percentage and stops on release', async () => {
    const wrapper = mountSplit()
    vi.spyOn(wrapper.element as HTMLElement, 'getBoundingClientRect').mockReturnValue({
      left: 0, width: 1000, top: 0, height: 100, right: 1000, bottom: 100, x: 0, y: 0,
      toJSON: () => ({})
    } as DOMRect)

    const divider = wrapper.find('[role="separator"]')
    await divider.trigger('pointerdown', { pointerId: 1 })
    expect(wrapper.classes()).toContain('split--dragging')

    divider.element.dispatchEvent(new MouseEvent('pointermove', { clientX: 400 }))
    await wrapper.vm.$nextTick()
    expect(cols(wrapper)).toBe('40% auto minmax(0, 1fr)')

    // Beyond the rails the split pins to the clamp.
    divider.element.dispatchEvent(new MouseEvent('pointermove', { clientX: 990 }))
    await wrapper.vm.$nextTick()
    expect(cols(wrapper)).toBe('75% auto minmax(0, 1fr)')

    divider.element.dispatchEvent(new MouseEvent('pointerup'))
    await wrapper.vm.$nextTick()
    expect(wrapper.classes()).not.toContain('split--dragging')

    // Listeners are removed: a stray move after release changes nothing.
    divider.element.dispatchEvent(new MouseEvent('pointermove', { clientX: 300 }))
    await wrapper.vm.$nextTick()
    expect(cols(wrapper)).toBe('75% auto minmax(0, 1fr)')
  })
})
