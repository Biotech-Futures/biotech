import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import MissedPerson from '@/views/management/MissedPerson.vue'

describe('MissedPerson', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('shows the address with a copy button right after it', async () => {
    const writeText = vi.fn(async () => {})
    vi.stubGlobal('navigator', { clipboard: { writeText } })
    const wrapper = mount(MissedPerson, { props: { who: 'amy@example.com (BTF07, Amy Chen)' } })
    expect(wrapper.text()).toBe('amy@example.com (BTF07, Amy Chen)')
    const button = wrapper.find('button')
    expect(button.attributes('aria-label')).toBe('Copy amy@example.com')

    await button.trigger('click')
    await flushPromises()
    expect(writeText).toHaveBeenCalledWith('amy@example.com')
    expect(button.attributes('aria-label')).toBe('Copied')
  })

  it('has no copy button for an entry without an address', () => {
    const wrapper = mount(MissedPerson, { props: { who: '(BTF07) Amy Chen' } })
    expect(wrapper.text()).toBe('(BTF07) Amy Chen')
    expect(wrapper.find('button').exists()).toBe(false)
  })
})
