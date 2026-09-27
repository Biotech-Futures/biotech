import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import ReleaseCertificatesPage from '@/views/grading/ReleaseCertificatesPage.vue'
import {
  fetchCertificatesRelease,
  setCertificatesFinalistExclusion,
  toggleCertificatesRelease
} from '@/utils/gradingAPI'

vi.mock('@/utils/gradingAPI', () => ({
  fetchCertificatesRelease: vi.fn(),
  setCertificatesFinalistExclusion: vi.fn(),
  toggleCertificatesRelease: vi.fn()
}))
const fetchMock = vi.mocked(fetchCertificatesRelease)
const exclusionMock = vi.mocked(setCertificatesFinalistExclusion)
const toggleMock = vi.mocked(toggleCertificatesRelease)

const status = (over: Record<string, unknown> = {}) => ({
  released_at: null,
  released_by: null,
  exclude_finalists: true,
  submissions_open: false,
  ...over
})

const mountPage = async () => {
  const wrapper = mount(ReleaseCertificatesPage, { global: { stubs: { teleport: true } } })
  await flushPromises()
  return wrapper
}

const buttonNamed = (wrapper: Awaited<ReturnType<typeof mountPage>>, label: RegExp) =>
  wrapper.findAll('button').find((b) => label.test(b.text().trim()))!

beforeEach(() => {
  fetchMock.mockReset()
  exclusionMock.mockReset()
  toggleMock.mockReset()
})

describe('certificate release state', () => {
  it('has its own gate, worded for certificates', async () => {
    fetchMock.mockResolvedValueOnce(status())
    const wrapper = await mountPage()
    expect(wrapper.text()).toContain('Certificates are not released')
    expect(buttonNamed(wrapper, /^Release$/).attributes('disabled')).toBeUndefined()
  })

  it('holds the gate shut while submissions are open', async () => {
    fetchMock.mockResolvedValueOnce(status({ submissions_open: true }))
    const wrapper = await mountPage()
    expect(buttonNamed(wrapper, /^Release$/).attributes('disabled')).toBeDefined()
    expect(wrapper.text()).toContain('Submissions are still open')
  })

  it('shows the released stamp and offers Unrelease', async () => {
    fetchMock.mockResolvedValueOnce(
      status({ released_at: '2026-09-20T10:00:00Z', released_by: 'Ada Admin' })
    )
    const wrapper = await mountPage()
    expect(wrapper.text()).toContain('Certificates are released')
    expect(wrapper.text()).toContain('by Ada Admin')
    expect(buttonNamed(wrapper, /Unrelease/)).toBeTruthy()
  })

  it('retries a failed status load', async () => {
    fetchMock.mockRejectedValueOnce(new Error('backend down'))
    const wrapper = await mountPage()
    expect(wrapper.text()).toContain('Failed to load release status.')
    fetchMock.mockResolvedValueOnce(status())
    await wrapper.find('.release__load-error button').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('Certificates are not released')
  })
})

describe('the finalist exclusion', () => {
  it('reflects the stored exclusion, on by default', async () => {
    fetchMock.mockResolvedValueOnce(status({ exclude_finalists: true }))
    const wrapper = await mountPage()
    expect((wrapper.find('input[type="checkbox"]').element as HTMLInputElement).checked).toBe(true)
  })

  it('changing it saves only the exclusion, not the release stamp', async () => {
    fetchMock.mockResolvedValueOnce(status({ exclude_finalists: true }))
    exclusionMock.mockResolvedValueOnce(status({ exclude_finalists: false }))
    const wrapper = await mountPage()
    const box = wrapper.find('input[type="checkbox"]')
    ;(box.element as HTMLInputElement).checked = false
    await box.trigger('change')
    await flushPromises()
    expect(exclusionMock).toHaveBeenCalledWith(false)
    expect(toggleMock).not.toHaveBeenCalled()
  })

  it('a refused exclusion change is reported', async () => {
    fetchMock.mockResolvedValueOnce(status())
    exclusionMock.mockRejectedValueOnce(new Error('refused'))
    const wrapper = await mountPage()
    await wrapper.find('input[type="checkbox"]').trigger('change')
    await flushPromises()
    expect(wrapper.find('.release__banner--error').text()).toContain('refused')
  })
})

describe('the release flow', () => {
  it('confirms in-page, then releases', async () => {
    fetchMock.mockResolvedValueOnce(status())
    toggleMock.mockResolvedValueOnce(status({ released_at: '2026-09-23T12:00:00Z' }))
    const wrapper = await mountPage()
    await buttonNamed(wrapper, /^Release$/).trigger('click')
    expect(wrapper.find('[role="dialog"]').text()).toContain('Release certificates?')
    await wrapper.find('[role="dialog"] .btn-primary').trigger('click')
    await flushPromises()
    expect(toggleMock).toHaveBeenCalledWith(true)
    expect(wrapper.text()).toContain('Certificates are released')
  })

  it('unreleases directly and reports a refusal in place', async () => {
    fetchMock.mockResolvedValueOnce(status({ released_at: '2026-09-20T10:00:00Z' }))
    toggleMock.mockRejectedValueOnce(new Error('cannot unrelease'))
    const wrapper = await mountPage()
    await buttonNamed(wrapper, /Unrelease/).trigger('click')
    await flushPromises()
    expect(toggleMock).toHaveBeenCalledWith(false)
    expect(wrapper.find('.release__banner--error').text()).toContain('cannot unrelease')
  })
})
