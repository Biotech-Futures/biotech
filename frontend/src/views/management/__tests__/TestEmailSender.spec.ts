import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import TestEmailSender from '@/views/management/TestEmailSender.vue'
import { fetchTestEmailRecipients, sendTestEmail } from '@/utils/managementAPI'

vi.mock('@/utils/managementAPI', () => ({
  fetchTestEmailRecipients: vi.fn(),
  sendTestEmail: vi.fn()
}))
const listMock = vi.mocked(fetchTestEmailRecipients)
const sendMock = vi.mocked(sendTestEmail)

const RECIPIENTS = [
  { value: '7:21', label: '(BTF07) Amy Chen' },
  { value: '7:22', label: '(BTF07, mentor) Mo Mentor' }
]

const mountSender = async (props: Record<string, unknown> = {}) => {
  const wrapper = mount(TestEmailSender, { props: { kind: 'nonfinalists', ...props } })
  await flushPromises()
  return wrapper
}
type Sender = Awaited<ReturnType<typeof mountSender>>
const sendButton = (wrapper: Sender) => wrapper.find('button')

beforeEach(() => {
  listMock.mockReset()
  sendMock.mockReset()
  listMock.mockResolvedValue({ recipients: RECIPIENTS })
})

describe('Send Test Email', () => {
  it('reads "Send Test Email of [who] to [address]", listing who the email can go to', async () => {
    const wrapper = await mountSender()
    expect(listMock).toHaveBeenCalledWith('nonfinalists')
    expect(sendButton(wrapper).text()).toBe('Send Test Email')
    expect(wrapper.findAll('.test-email__word').map((w) => w.text())).toEqual(['of', 'to'])
    expect(wrapper.findAll('option').map((o) => o.text())).toEqual([
      '(BTF07) Amy Chen',
      '(BTF07, mentor) Mo Mentor'
    ])
    // The first person is picked; the address starts empty and is left to password managers to ignore.
    expect((wrapper.find('select').element as HTMLSelectElement).value).toBe('7:21')
    const address = wrapper.find('input')
    expect((address.element as HTMLInputElement).value).toBe('')
    expect(address.attributes('autocomplete')).toBe('off')
    expect(address.attributes('data-bwignore')).toBeDefined()
    expect(sendButton(wrapper).attributes('disabled')).toBeDefined()
  })

  it('sends the chosen person\'s email to the typed address, with the page\'s unsaved details', async () => {
    sendMock.mockResolvedValue({ sent_to: 'me@example.com' })
    const fields = { survey_url: 'https://survey.example.com/draft' }
    const wrapper = await mountSender({ kind: 'results-students', fields: () => fields })
    await wrapper.find('select').setValue('7:22')
    await wrapper.find('input').setValue(' me@example.com ')
    await sendButton(wrapper).trigger('click')
    await flushPromises()
    expect(sendMock).toHaveBeenCalledWith('results-students', '7:22', 'me@example.com', fields)
    const result = wrapper.find('.test-email__result')
    expect(result.text()).toBe('Test sent to me@example.com.')
    expect(result.classes()).toContain('test-email__result--ok')
  })

  it('says what went wrong', async () => {
    sendMock.mockRejectedValue(new Error('Enter a valid email address.'))
    const wrapper = await mountSender()
    await wrapper.find('input').setValue('nope')
    await wrapper.find('input').trigger('keydown', { key: 'Enter' })
    await flushPromises()
    const result = wrapper.find('.test-email__result')
    expect(result.text()).toBe('Enter a valid email address.')
    expect(result.classes()).toContain('test-email__result--error')
  })

  it('can\'t send while nobody is due the email, or the list could not load', async () => {
    listMock.mockResolvedValue({ recipients: [] })
    let wrapper = await mountSender()
    expect(wrapper.find('option').text()).toBe('Nobody yet')
    await wrapper.find('input').setValue('me@example.com')
    expect(sendButton(wrapper).attributes('disabled')).toBeDefined()

    listMock.mockRejectedValue(new Error('Server down'))
    wrapper = await mountSender()
    expect(wrapper.find('option').text()).toBe("Couldn't load the list")
  })
})
