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
        { name: 'Content', max_mark: '10', mark: '7.5', comment: 'Clear claim.' },
        { name: 'Clarity', max_mark: '5', mark: '', comment: '' }
      ],
      overall_comment: 'A thoughtful set of answers.',
      subtotal: '7.5',
      subtotal_max: '15'
    },
    {
      code: 'POSTER',
      name: 'A2 Poster',
      submitted: true,
      criteria: [{ name: 'Design', max_mark: '5', mark: '4', comment: 'Bold.' }],
      overall_comment: '',
      subtotal: '4',
      subtotal_max: '5'
    },
    // A part with no criteria has nothing to show.
    { code: 'REPORT', name: 'Scientific Report', submitted: true, criteria: [] }
  ],
  summary: {
    project_title: 'Plant Sensors',
    project_category_heading: 'Project Categories',
    project_category: 'Health and Medicine, Agriculture',
    solution_category: 'App',
    combined_total: '12',
    combined_max: '20'
  },
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
    expect(marks.find('h2').text()).toBe('Mark Summary')
    expect(marks.findAll('.group-results__component-name').map((h) => h.text())).toEqual([
      'Short Answer Questions',
      'A2 Poster'
    ])
    const rows = marks.findAll('tbody tr').map((r) => r.findAll('td').map((c) => c.text()))
    expect(rows.slice(0, 2)).toEqual([
      ['Content', '7.5 / 10', 'Clear claim.'],
      ['Clarity', '— / 5', '']
    ])
    // Each table ends with its marks added up.
    const subtotals = marks
      .findAll('[data-testid="results-subtotal"]')
      .map((r) => r.findAll('th, td').map((c) => c.text()))
    expect(subtotals).toEqual([
      ['Subtotal', '7.5 / 15', ''],
      ['Subtotal', '4 / 5', '']
    ])

    await marks.find('button').trigger('click')
    await flushPromises()
    expect(summaryMock).toHaveBeenCalledWith('7', '2026_BTF_Marks_BTF1.docx')
  })

  it('gives the project details, each overall comment, the combined mark and the note', () => {
    const marks = mountResults(results()).find('[data-testid="results-marks"]')
    const details = marks
      .findAll('[data-testid="results-details"] div')
      .map((d) => `${d.find('dt').text()} ${d.find('dd').text()}`)
    expect(details).toEqual([
      'Project Title: Plant Sensors',
      'Project Categories: Health and Medicine, Agriculture',
      'Solution Category: App'
    ])
    const overall = marks.findAll('[data-testid="results-overall"]').map((p) => p.text().replace(/\s+/g, ' '))
    expect(overall).toEqual(['Overall SAQ Comment: A thoughtful set of answers.', 'Overall Poster Comment: —'])
    expect(marks.find('[data-testid="results-combined"]').text()).toBe('Combined Mark: 12/20')
    expect(marks.text()).toContain(
      '*Please note that if you submitted a prototype or report, specific marks for these are not released.'
    )
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
    const certificatesOnly = mountResults(results({ marks_released: false, components: [], summary: null }))
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
    const wrapper = mountResults(results({ has_submission: false, components: [], summary: null, certificates: [] }))
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
