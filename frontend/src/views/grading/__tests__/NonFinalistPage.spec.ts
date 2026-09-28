import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import NonFinalistPage from '@/views/grading/NonFinalistPage.vue'
import {
  fetchNonFinalistEmail,
  previewNonFinalistEmail,
  sendNonFinalistEmailBatch,
  type NonFinalistEmailStatus
} from '@/utils/gradingAPI'

vi.mock('@/utils/gradingAPI', () => ({
  fetchNonFinalistEmail: vi.fn(),
  previewNonFinalistEmail: vi.fn(),
  sendNonFinalistEmailBatch: vi.fn()
}))
const statusMock = vi.mocked(fetchNonFinalistEmail)
const previewMock = vi.mocked(previewNonFinalistEmail)
const sendMock = vi.mocked(sendNonFinalistEmailBatch)

const status = (overrides: Partial<NonFinalistEmailStatus> = {}): NonFinalistEmailStatus => ({
  teams: { total: 3, emailed: 0 },
  students: { total: 6, emailed: 0 },
  blocked: '',
  ...overrides
})

const mountPage = async () => {
  const wrapper = mount(NonFinalistPage, {
    global: {
      stubs: {
        teleport: true,
        RouterLink: { props: ['to'], template: '<a :href="to"><slot /></a>' }
      }
    }
  })
  await flushPromises()
  return wrapper
}

const buttonNamed = (wrapper: Awaited<ReturnType<typeof mountPage>>, label: RegExp) =>
  wrapper.findAll('button').find((b) => label.test(b.text().trim()))!

beforeEach(() => {
  statusMock.mockReset()
  previewMock.mockReset()
  sendMock.mockReset()
  statusMock.mockResolvedValue(status())
})

describe('Email Nonfinalist', () => {
  it('has the page title, then the section heading, then says where the date and link come from', async () => {
    const wrapper = await mountPage()
    expect(wrapper.find('.card-title').text()).toBe('Email Nonfinalist')
    expect(wrapper.find('.non-finalist__section-title').text()).toBe('Email Nonfinalist')
    // The second sentence on its own line, spaced like the lines around it.
    expect(wrapper.findAll('.non-finalist__hint').map((p) => p.text())).toEqual([
      "For teams that submitted but weren't selected as finalists.",
      'The Symposium date and registration link come from Email Details on Notify Finalists.'
    ])
    expect(wrapper.find('.non-finalist__hint a').attributes('href')).toBe('/management/notify-finalists')
  })

  it('says the emails are not sent yet and how many students there are', async () => {
    const wrapper = await mountPage()
    const line = wrapper.find('.non-finalist__status')
    expect(line.text()).toBe('Emails are not sent to every group member')
    expect(line.classes()).toContain('non-finalist__status--warn')
    expect(wrapper.find('.non-finalist__counts').text()).toBe('Students: 0 of 6 emailed')
    expect(buttonNamed(wrapper, /^Email Nonfinalists$/).attributes('disabled')).toBeUndefined()
  })

  it('turns green and stops offering to send once every team is emailed', async () => {
    statusMock.mockResolvedValue(status({ teams: { total: 3, emailed: 3 }, students: { total: 6, emailed: 6 } }))
    const wrapper = await mountPage()
    expect(wrapper.find('.non-finalist__status').text()).toBe('Emails are sent to every group member')
    expect(buttonNamed(wrapper, /^Email Nonfinalists$/).attributes('disabled')).toBeDefined()
  })

  it('says why it cannot send, from the server', async () => {
    const reason = 'Set the Symposium date and registration link on Notify Finalists before sending.'
    statusMock.mockResolvedValue(status({ blocked: reason }))
    const wrapper = await mountPage()
    expect(wrapper.find('.non-finalist__blocked').text()).toBe(reason)
    expect(buttonNamed(wrapper, /^Email Nonfinalists$/).attributes('disabled')).toBeDefined()
  })

  it('shows no status or count when no team is due the email', async () => {
    statusMock.mockResolvedValue(status({ teams: { total: 0, emailed: 0 }, students: { total: 0, emailed: 0 } }))
    const wrapper = await mountPage()
    expect(wrapper.find('.non-finalist__status').exists()).toBe(false)
    expect(wrapper.find('.non-finalist__counts').exists()).toBe(false)
  })

  it('says when the teams could not be loaded', async () => {
    statusMock.mockRejectedValue(new Error('Server down'))
    const wrapper = await mountPage()
    expect(wrapper.find('.non-finalist__load-error').text()).toContain('Failed to load the teams.')
    expect(wrapper.find('.non-finalist__actions').exists()).toBe(false)
  })

  it('previews the email as the first team due would get it', async () => {
    previewMock.mockResolvedValue({
      subject: 'Thank you for your submission – Invitation to the Symposium',
      to: 'BTF07',
      html: '<p>email</p>'
    })
    const wrapper = await mountPage()
    await buttonNamed(wrapper, /^Preview Email$/).trigger('click')
    await flushPromises()
    const dialog = wrapper.find('[aria-label="Email preview"]')
    expect(dialog.text()).toContain('Thank you for your submission – Invitation to the Symposium')
    expect(dialog.text()).toContain('As BTF07 would get it. Nothing has been sent.')
  })

  it('asks first, then emails batch after batch until done', async () => {
    sendMock
      .mockResolvedValueOnce({
        emailed: 8, failed: 0, cursor: 5, done: false,
        teams: { total: 3, emailed: 2 }, students: { total: 6, emailed: 4 }
      })
      .mockResolvedValueOnce({
        emailed: 4, failed: 0, cursor: 9, done: true,
        teams: { total: 3, emailed: 3 }, students: { total: 6, emailed: 6 }
      })
    const wrapper = await mountPage()
    await buttonNamed(wrapper, /^Email Nonfinalists$/).trigger('click')
    expect(wrapper.find('[aria-label="Send the non-finalist email"]').text()).toContain(
      "This emails every member of the 3 teams that haven't had this email yet."
    )
    expect(sendMock).not.toHaveBeenCalled()

    statusMock.mockResolvedValue(status({ teams: { total: 3, emailed: 3 }, students: { total: 6, emailed: 6 } }))
    await buttonNamed(wrapper, /^Send$/).trigger('click')
    await flushPromises()
    expect(sendMock.mock.calls).toEqual([[null], [5]])
    expect(wrapper.find('.non-finalist__banner--ok').text()).toBe('Emailed 12 people.')
    expect(wrapper.find('.non-finalist__counts').text()).toBe('Students: 6 of 6 emailed')
  })

  it('says how many teams were not emailed in full, for a retry', async () => {
    sendMock.mockResolvedValue({
      emailed: 1, failed: 1, cursor: 5, done: true,
      teams: { total: 3, emailed: 2 }, students: { total: 6, emailed: 4 }
    })
    statusMock.mockResolvedValue(status({ teams: { total: 3, emailed: 2 } }))
    const wrapper = await mountPage()
    await buttonNamed(wrapper, /^Email Nonfinalists$/).trigger('click')
    expect(wrapper.find('[aria-label="Send the non-finalist email"]').text()).toContain(
      "This emails every member of the 1 team that hasn't had this email yet."
    )
    await buttonNamed(wrapper, /^Send$/).trigger('click')
    await flushPromises()
    expect(wrapper.find('.non-finalist__banner--error').text()).toBe(
      "Emailed 1 person. 1 team wasn't emailed in full; press Email Nonfinalists again to retry."
    )
  })
})
