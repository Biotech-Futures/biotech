import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import ResultsTab from '@/components/grading/ResultsTab.vue'
import {
  downloadMyCertificate,
  downloadMySummary,
  fetchMyGrades
} from '@/utils/gradingAPI'

vi.mock('@/utils/gradingAPI', () => ({
  fetchMyGrades: vi.fn(),
  downloadMySummary: vi.fn(),
  downloadMyCertificate: vi.fn()
}))
const gradesMock = vi.mocked(fetchMyGrades)
const summaryMock = vi.mocked(downloadMySummary)
const certMock = vi.mocked(downloadMyCertificate)

const payload = () => ({
  group: { id: 7, group_name: 'BTF-1' },
  year: 2026,
  components: [
    {
      code: 'SAQ',
      name: 'Short Answer Questions',
      submitted: true,
      criteria: [
        { name: 'Content', max_mark: '10.00', mark: '8.00', comment: 'Great' },
        { name: 'Clarity', max_mark: '5.00', mark: '', comment: '' }
      ]
    },
    { code: 'REPORT', name: 'Scientific Report', submitted: false, criteria: [] }
  ]
})

const mountTab = async () => {
  const wrapper = mount(ResultsTab)
  await flushPromises()
  return wrapper
}

beforeEach(() => {
  gradesMock.mockReset()
  summaryMock.mockReset()
  certMock.mockReset()
  gradesMock.mockResolvedValue(payload())
})

describe('loading', () => {
  it('renders the marks table with pending criteria shown as a dash', async () => {
    const wrapper = await mountTab()
    expect(wrapper.text()).toContain('BTF-1 · 2026')
    const rows = wrapper.findAll('tbody tr')
    expect(rows).toHaveLength(2)
    expect(rows[0]!.text()).toContain('8.00')
    expect(rows[0]!.text()).toContain('/ 10.00')
    expect(rows[1]!.find('.results-pending').text()).toBe('—')
  })

  it('says an unsubmitted component has no upload instead of an empty table', async () => {
    const wrapper = await mountTab()
    expect(wrapper.text()).toContain('No submission uploaded.')
  })

  it('translates the pre-release 403 into friendly copy', async () => {
    gradesMock.mockRejectedValueOnce(
      Object.assign(new Error('Forbidden'), { response: { status: 403 } })
    )
    const wrapper = await mountTab()
    expect(wrapper.find('[role="alert"]').text()).toBe('Marks have not been released yet.')
  })

  it('surfaces other failures by their message', async () => {
    gradesMock.mockRejectedValueOnce(new Error('server unavailable'))
    const wrapper = await mountTab()
    expect(wrapper.find('[role="alert"]').text()).toBe('server unavailable')
  })
})

describe('downloads', () => {
  const buttonNamed = (wrapper: Awaited<ReturnType<typeof mountTab>>, label: RegExp) =>
    wrapper.findAll('button').find((b) => label.test(b.text()))!

  it('downloads the summary named after the group', async () => {
    summaryMock.mockResolvedValueOnce()
    const wrapper = await mountTab()
    await buttonNamed(wrapper, /summary/i).trigger('click')
    await flushPromises()
    expect(summaryMock).toHaveBeenCalledWith('BTF-1')
  })

  it('downloads the certificate the same way', async () => {
    certMock.mockResolvedValueOnce()
    const wrapper = await mountTab()
    await buttonNamed(wrapper, /certificate/i).trigger('click')
    await flushPromises()
    expect(certMock).toHaveBeenCalledWith('BTF-1')
  })

  it('a failed download is reported without losing the marks table', async () => {
    summaryMock.mockRejectedValueOnce(new Error('render failed'))
    const wrapper = await mountTab()
    await buttonNamed(wrapper, /summary/i).trigger('click')
    await flushPromises()
    expect(wrapper.find('[role="alert"]').text()).toContain('Download failed: render failed')
  })
})
