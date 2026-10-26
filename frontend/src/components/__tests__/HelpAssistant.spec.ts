import { flushPromises, mount, RouterLinkStub } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import HelpAssistant from '../HelpAssistant.vue'
import { askAssistant } from '@/utils/assistantAPI'

vi.mock('@/utils/assistantAPI', () => ({ askAssistant: vi.fn() }))

const mountAssistant = () => mount(HelpAssistant, { global: { stubs: { RouterLink: RouterLinkStub } } })

describe('HelpAssistant', () => {
  beforeEach(() => {
    vi.mocked(askAssistant).mockReset()
  })

  it('asks a suggested question and shows the answer with its links', async () => {
    vi.mocked(askAssistant).mockResolvedValue({
      answer: 'Raise a ticket on the Support page.',
      links: [{ label: 'Support', to: '/support' }],
      matched: true,
    })
    const wrapper = mountAssistant()

    await wrapper.find('.help-assistant__suggestions button').trigger('click')
    await flushPromises()

    expect(askAssistant).toHaveBeenCalledWith('What should I do?')
    expect(wrapper.text()).toContain('Raise a ticket on the Support page.')
    expect(wrapper.findComponent(RouterLinkStub).props('to')).toBe('/support')
  })

  it('points to Support when the request fails', async () => {
    vi.mocked(askAssistant).mockImplementation(async () => {
      throw new Error('down')
    })
    const wrapper = mountAssistant()

    await wrapper.find('input').setValue('Where are resources?')
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(wrapper.text()).toContain('Where are resources?')
    expect(wrapper.text()).toContain('Sorry, I could not answer just now.')
    expect(wrapper.findComponent(RouterLinkStub).props('to')).toBe('/support')
  })
})
