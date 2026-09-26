import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent } from 'vue'
import { mount } from '@vue/test-utils'
import { FLASH_MESSAGE_MS, useFlashMessage } from '@/composables/useFlashMessage'

// The composable registers onBeforeUnmount, so drive it from inside a real
// component the way every page does.
const mountFlash = () => {
  let flash!: ReturnType<typeof useFlashMessage>
  const wrapper = mount(
    defineComponent({
      setup() {
        flash = useFlashMessage()
        return () => null
      }
    })
  )
  return { wrapper, flash }
}

beforeEach(() => {
  vi.useFakeTimers()
})

afterEach(() => {
  vi.useRealTimers()
})

describe('useFlashMessage', () => {
  it('stays for 3.5 seconds, then clears itself', () => {
    const { flash } = mountFlash()
    flash.show('Saved.')
    expect(flash.message.value).toBe('Saved.')

    vi.advanceTimersByTime(FLASH_MESSAGE_MS - 1)
    expect(flash.message.value).toBe('Saved.')
    vi.advanceTimersByTime(1)
    expect(flash.message.value).toBe('')
  })

  it('a second message restarts the countdown', () => {
    const { flash } = mountFlash()
    flash.show('First.')
    vi.advanceTimersByTime(3000)
    flash.show('Second.')

    vi.advanceTimersByTime(3000)
    expect(flash.message.value).toBe('Second.')
    vi.advanceTimersByTime(FLASH_MESSAGE_MS - 3000)
    expect(flash.message.value).toBe('')
  })

  it('leaves no timer running after unmount', () => {
    const { wrapper, flash } = mountFlash()
    flash.show('Saved.')
    wrapper.unmount()
    expect(vi.getTimerCount()).toBe(0)
  })
})
