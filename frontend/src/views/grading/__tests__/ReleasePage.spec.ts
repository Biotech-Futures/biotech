import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import ReleasePage from '@/views/grading/ReleasePage.vue'
import { fetchRelease, toggleRelease } from '@/utils/gradingAPI'

vi.mock('@/utils/gradingAPI', () => ({
  fetchRelease: vi.fn(),
  toggleRelease: vi.fn()
}))
const fetchMock = vi.mocked(fetchRelease)
const toggleMock = vi.mocked(toggleRelease)

const status = (over: Record<string, unknown> = {}) => ({
  released_at: null,
  released_by: null,
  submissions_open: false,
  ...over
})

const mountPage = async () => {
  const wrapper = mount(ReleasePage, { global: { stubs: { teleport: true } } })
  await flushPromises()
  return wrapper
}

const buttonNamed = (wrapper: Awaited<ReturnType<typeof mountPage>>, label: RegExp) =>
  wrapper.findAll('button').find((b) => label.test(b.text().trim()))!

beforeEach(() => {
  fetchMock.mockReset()
  toggleMock.mockReset()
})

describe('release state', () => {
  it('shows the unreleased state with the release action armed once closed', async () => {
    fetchMock.mockResolvedValueOnce(status())
    const wrapper = await mountPage()
    expect(wrapper.text()).toContain('Marks are not released')
    expect(buttonNamed(wrapper, /^Release$/).attributes('disabled')).toBeUndefined()
    expect(wrapper.findAll('button').some((b) => /Unrelease/.test(b.text()))).toBe(false)
  })

  it('disables releasing while any team can still submit, and says why', async () => {
    fetchMock.mockResolvedValueOnce(status({ submissions_open: true }))
    const wrapper = await mountPage()
    expect(buttonNamed(wrapper, /^Release$/).attributes('disabled')).toBeDefined()
    expect(wrapper.text()).toContain('Submissions are still open')
  })

  it('shows when and by whom marks were released, with Unrelease on offer', async () => {
    fetchMock.mockResolvedValueOnce(
      status({ released_at: '2026-09-20T10:00:00Z', released_by: 'Ada Admin' })
    )
    const wrapper = await mountPage()
    expect(wrapper.text()).toContain('Marks are released')
    expect(wrapper.text()).toContain('by Ada Admin')
    expect(buttonNamed(wrapper, /^Release$/).attributes('disabled')).toBeDefined()
    expect(buttonNamed(wrapper, /Unrelease/)).toBeTruthy()
  })

  it('offers a retry when the status fails to load', async () => {
    fetchMock.mockRejectedValueOnce(new Error('backend down'))
    const wrapper = await mountPage()
    expect(wrapper.text()).toContain('Failed to load release status.')
    fetchMock.mockResolvedValueOnce(status())
    await wrapper.find('.release__load-error button').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('Marks are not released')
  })
})

describe('the release flow', () => {
  it('asks in-page first, and cancelling releases nothing', async () => {
    fetchMock.mockResolvedValueOnce(status())
    const wrapper = await mountPage()
    await buttonNamed(wrapper, /^Release$/).trigger('click')
    const dialog = wrapper.find('[role="dialog"]')
    expect(dialog.text()).toContain('Release marks?')
    await buttonNamed(wrapper, /^Cancel$/).trigger('click')
    expect(wrapper.find('[role="dialog"]').exists()).toBe(false)
    expect(toggleMock).not.toHaveBeenCalled()
  })

  it('confirming releases and shows the new state', async () => {
    fetchMock.mockResolvedValueOnce(status())
    toggleMock.mockResolvedValueOnce(
      status({ released_at: '2026-09-23T12:00:00Z', released_by: 'Ada Admin' })
    )
    const wrapper = await mountPage()
    await buttonNamed(wrapper, /^Release$/).trigger('click')
    await wrapper.find('[role="dialog"] .btn-primary').trigger('click')
    await flushPromises()
    expect(toggleMock).toHaveBeenCalledWith(true)
    expect(wrapper.find('[role="dialog"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('Marks are released')
  })

  it('a refused release closes the dialog and reports the reason', async () => {
    fetchMock.mockResolvedValueOnce(status())
    toggleMock.mockRejectedValueOnce(new Error('submissions are still open'))
    const wrapper = await mountPage()
    await buttonNamed(wrapper, /^Release$/).trigger('click')
    await wrapper.find('[role="dialog"] .btn-primary').trigger('click')
    await flushPromises()
    expect(wrapper.find('[role="dialog"]').exists()).toBe(false)
    expect(wrapper.find('.release__banner--error').text()).toContain('submissions are still open')
  })

  it('unreleasing needs no dialog — it is the emergency path', async () => {
    fetchMock.mockResolvedValueOnce(status({ released_at: '2026-09-20T10:00:00Z' }))
    toggleMock.mockResolvedValueOnce(status())
    const wrapper = await mountPage()
    await buttonNamed(wrapper, /Unrelease/).trigger('click')
    await flushPromises()
    expect(toggleMock).toHaveBeenCalledWith(false)
    expect(wrapper.text()).toContain('Marks are not released')
  })

  it('a failed unrelease is reported in place', async () => {
    fetchMock.mockResolvedValueOnce(status({ released_at: '2026-09-20T10:00:00Z' }))
    toggleMock.mockRejectedValueOnce(new Error('refused'))
    const wrapper = await mountPage()
    await buttonNamed(wrapper, /Unrelease/).trigger('click')
    await flushPromises()
    expect(wrapper.find('.release__banner--error').text()).toContain('refused')
  })
})
