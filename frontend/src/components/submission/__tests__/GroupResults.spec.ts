import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import GroupResults from '../GroupResults.vue'
import {
  downloadGroupCertificate,
  downloadGroupSummary,
  type GroupResults as GroupResultsData
} from '@/utils/gradingAPI'
import { ApiError } from '@/utils/apiError'

vi.mock('@/utils/gradingAPI', () => ({
  downloadGroupCertificate: vi.fn(),
  downloadGroupSummary: vi.fn()
}))
const summaryMock = vi.mocked(downloadGroupSummary)
const certificateMock = vi.mocked(downloadGroupCertificate)

const AMY = { user_id: 11, name: 'Amy Chen', kind: 'student' as const, file_name: '2026_BTF_Student_Certificate_Amy_Chen.docx' }
const MO = { user_id: 21, name: 'Mo Mentor', kind: 'mentor' as const, file_name: '2026_BTF_Mentor_Certificate_Mo_Mentor.docx' }

const results = (over: Partial<GroupResultsData> = {}): GroupResultsData => ({
  marks_released: true,
  certificates_released: true,
  certificates_withheld: false,
  has_submission: true,
  year: 2026,
  components: [
    {
      code: 'SAQ',
      name: 'Short Answer Questions',
      submitted: true,
      criteria: [
        { name: 'Content', max_mark: '10.00', mark: '8.00', comment: 'Clear claim.' },
        { name: 'Clarity', max_mark: '5.00', mark: '', comment: '' }
      ]
    },
    // A part with no criteria has nothing to show.
    { code: 'REPORT', name: 'Scientific Report', submitted: true, criteria: [] }
  ],
  summary_file_name: '2026_BTF_Marks_BTF1.docx',
  certificates: [AMY, MO],
  ...over
})

const mountResults = (data: GroupResultsData) =>
  mount(GroupResults, { props: { groupId: '7', results: data } })

beforeEach(() => {
  summaryMock.mockReset().mockResolvedValue()
  certificateMock.mockReset().mockResolvedValue()
})

describe('the Results section', () => {
  it("shows each part's marks and comments, with the marks summary", async () => {
    const wrapper = mountResults(results())
    const marks = wrapper.find('[data-testid="results-marks"]')
    expect(marks.findAll('.group-results__component-name').map((h) => h.text())).toEqual(['Short Answer Questions'])
    const rows = marks.findAll('tbody tr').map((r) => r.findAll('td').map((c) => c.text()))
    expect(rows).toEqual([
      ['Content', '8.00 / 10.00', 'Clear claim.'],
      ['Clarity', '— / 5.00', '']
    ])

    await marks.find('button').trigger('click')
    await flushPromises()
    expect(summaryMock).toHaveBeenCalledWith('7', '2026_BTF_Marks_BTF1.docx')
  })

  it("lists every student's and mentor's certificate to download", async () => {
    const wrapper = mountResults(results())
    const items = wrapper.findAll('[data-testid="results-certificates"] li')
    expect(items.map((li) => li.text().replace(/\s+/g, ' '))).toEqual([
      'Amy Chen · Student Certificate Download',
      'Mo Mentor · Mentor Certificate Download'
    ])
    await items[1]!.find('button').trigger('click')
    await flushPromises()
    expect(certificateMock).toHaveBeenCalledWith('7', MO)
  })

  it('says what is still to come when only one of them is released', () => {
    const marksOnly = mountResults(results({ certificates_released: false, certificates: [] }))
    expect(marksOnly.find('[data-testid="results-certificates"]').text()).toContain(
      "Certificates haven't been released yet."
    )
    const certificatesOnly = mountResults(results({ marks_released: false, components: [] }))
    expect(certificatesOnly.find('[data-testid="results-marks"]').text()).toContain(
      "Marks haven't been released yet."
    )
    expect(certificatesOnly.find('[data-testid="results-marks"] button').exists()).toBe(false)
  })

  it("tells a finalist team its certificates come at the Symposium", () => {
    const wrapper = mountResults(results({ certificates_withheld: true, certificates: [] }))
    expect(wrapper.find('[data-testid="results-certificates"]').text()).toContain(
      'your certificates are handed out at the Symposium'
    )
  })

  it("says there are no results for a group that didn't submit", () => {
    const wrapper = mountResults(results({ has_submission: false, components: [], certificates: [] }))
    expect(wrapper.text()).toContain("This group didn't make a submission, so there are no results to show.")
    expect(wrapper.find('[data-testid="results-marks"]').exists()).toBe(false)
  })

  it('says why a download failed', async () => {
    summaryMock.mockRejectedValue(
      new ApiError({ error: 'The document template has not been set up yet.', code: 'x', request_id: 'x' })
    )
    const wrapper = mountResults(results())
    await wrapper.find('[data-testid="results-marks"] button').trigger('click')
    await flushPromises()
    expect(wrapper.find('[role="alert"]').text()).toBe('The document template has not been set up yet.')
  })
})
