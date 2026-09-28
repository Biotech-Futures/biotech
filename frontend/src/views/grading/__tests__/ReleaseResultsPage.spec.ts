import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import ReleaseResultsPage from '@/views/grading/ReleaseResultsPage.vue'
import { fetchCertificatesRelease, fetchRelease } from '@/utils/gradingAPI'

vi.mock('@/utils/gradingAPI', () => ({
  fetchRelease: vi.fn(),
  toggleRelease: vi.fn(),
  fetchCertificatesRelease: vi.fn(),
  setCertificatesFinalistExclusion: vi.fn(),
  toggleCertificatesRelease: vi.fn()
}))

const status = { released_at: null, released_by: null, submissions_open: false }

beforeEach(() => {
  vi.mocked(fetchRelease).mockReset().mockResolvedValue(status)
  vi.mocked(fetchCertificatesRelease)
    .mockReset()
    .mockResolvedValue({ ...status, exclude_finalists: true })
})

describe('Release Results', () => {
  it('is three cards: the title with the shared hint, then marks, then certificates', async () => {
    const wrapper = mount(ReleaseResultsPage, { global: { stubs: { teleport: true } } })
    await flushPromises()

    const cards = wrapper.findAll('.card')
    expect(cards).toHaveLength(3)
    expect(cards[0]!.find('.card-title').text()).toBe('Release Results')
    expect(cards[0]!.find('.release-results__hint').text()).toBe(
      'Releasing shows results only to students whose group made a submission.'
    )
    expect(cards[1]!.find('.release__section-title').text()).toBe('Release Marks')
    expect(cards[2]!.find('.release__section-title').text()).toBe('Release Certificates')
    expect(wrapper.text()).toContain('Marks are not released')
    expect(wrapper.text()).toContain('Certificates are not released')
    // Each card keeps its own line as well.
    expect(cards[1]!.text()).toContain(
      'Releasing shows marks only to students whose group made a submission.'
    )
    expect(cards[2]!.text()).toContain(
      'Releasing gives certificates only to students whose group made a submission.'
    )
    expect(wrapper.text().match(/still being built/g)).toHaveLength(1)
  })

  it('Preview Email, under the title card, says the results email is not set up yet', async () => {
    const wrapper = mount(ReleaseResultsPage, { global: { stubs: { teleport: true } } })
    await flushPromises()

    const preview = wrapper.findAll('.card')[0]!.findAll('button').find((b) => b.text() === 'Preview Email')!
    expect(wrapper.find('[role="dialog"]').exists()).toBe(false)
    await preview.trigger('click')
    expect(wrapper.find('[role="dialog"]').text()).toContain("hasn't been set up yet")

    const close = wrapper.find('[role="dialog"]').findAll('button').find((b) => b.text() === 'Close')!
    await close.trigger('click')
    expect(wrapper.find('[role="dialog"]').exists()).toBe(false)
  })
})
