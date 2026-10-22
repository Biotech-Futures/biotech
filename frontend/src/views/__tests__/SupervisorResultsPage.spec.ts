import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'

import SupervisorResultsPage from '@/views/SupervisorResultsPage.vue'
import {
  downloadAllResultsCertificate,
  downloadAllResultsCertificates,
  downloadAllResultsSheet,
  downloadSupervisorResultsCertificate,
  downloadSupervisorResultsCertificates,
  downloadSupervisorResultsSheet,
  fetchAllResults,
  fetchSupervisorResults,
  type SupervisorResults,
  type SupervisorResultsPerson
} from '@/utils/managementAPI'

vi.mock('@/utils/managementAPI', () => ({
  fetchSupervisorResults: vi.fn(),
  downloadSupervisorResultsSheet: vi.fn(),
  downloadSupervisorResultsCertificate: vi.fn(),
  downloadSupervisorResultsCertificates: vi.fn(),
  fetchAllResults: vi.fn(),
  downloadAllResultsSheet: vi.fn(),
  downloadAllResultsCertificate: vi.fn(),
  downloadAllResultsCertificates: vi.fn()
}))

const fetchMock = vi.mocked(fetchSupervisorResults)
const fetchAllMock = vi.mocked(fetchAllResults)

const person = (over: Partial<SupervisorResultsPerson>): SupervisorResultsPerson => ({
  user_id: 1,
  name: 'Amy Chen',
  kind: 'student',
  group_id: 10,
  group_name: 'BTF01',
  withheld: false,
  file_name: '2026_BTF_Student_Certificate_Amy_Chen.docx',
  ...over
})

const results = (over: Partial<SupervisorResults> = {}): SupervisorResults => ({
  year: 2026,
  marks_released: true,
  certificates_released: true,
  columns: [
    { key: 'TeamCode', label: 'Group', title: '', mark: false },
    { key: 'Students', label: 'Students', title: '', mark: false },
    { key: 'Mentor', label: 'Mentor', title: '', mark: false },
    { key: 'PM1', label: 'PM1', title: 'Visual clarity', mark: true },
    { key: 'PosterComment1', label: 'Poster Comment 1', title: '', mark: false },
    { key: 'MTotal', label: 'MTotal', title: '', mark: true }
  ],
  groups: [
    { group_id: 10, TeamCode: 'BTF01', Students: 'Amy Chen', Mentor: 'Mo Mentor', PM1: '8', MTotal: '40' },
    { group_id: 11, TeamCode: 'BTF02', Students: 'Fin Al', Mentor: '', PM1: '9', MTotal: '55' }
  ],
  sheet_file_name: '2026_BTF_Student_Marks_Sam_Lee.xlsx',
  people: [
    person({}),
    person({ user_id: 2, name: 'Mo Mentor', kind: 'mentor' }),
    person({ user_id: 3, name: 'Fin Al', group_id: 11, group_name: 'BTF02', withheld: true })
  ],
  zip_file_name: '2026_BTF_Certificates_Sam_Lee.zip',
  ...over
})

const mountPage = async (body: SupervisorResults) => {
  fetchMock.mockResolvedValue(body)
  const wrapper = mount(SupervisorResultsPage)
  await flushPromises()
  return wrapper
}

const tabNames = (wrapper: VueWrapper) => wrapper.findAll('[role="tab"]').map((tab) => tab.text())
const button = (wrapper: VueWrapper, text: string) =>
  wrapper.findAll('button').find((b) => b.text() === text)
const rowTexts = (wrapper: VueWrapper) => wrapper.findAll('tr.data-table-row').map((row) => row.text())

beforeEach(() => {
  vi.clearAllMocks()
})

describe('SupervisorResultsPage', () => {
  it('shows only what is released', async () => {
    let wrapper = await mountPage(results({ certificates_released: false, people: [] }))
    expect(tabNames(wrapper)).toEqual(['Marks'])
    expect(wrapper.text()).toContain('Download Marks Spreadsheet')
    wrapper.unmount()

    wrapper = await mountPage(results({ marks_released: false, columns: [], groups: [] }))
    expect(tabNames(wrapper)).toEqual(['Certificates'])
    expect(wrapper.text()).toContain('Will be Released Separately')
  })

  it("shows admins every group's, released or not, from Management's own endpoints", async () => {
    fetchAllMock.mockResolvedValue(
      results({
        marks_released: false,
        certificates_released: false,
        sheet_file_name: '2026_BTF_Student_Marks_All_Groups.xlsx',
        zip_file_name: '2026_BTF_Certificates_All_Groups.zip',
        people: [person({}), person({ user_id: 3, name: 'Fin Al', group_id: 11, group_name: 'BTF02' })],
      }),
    )
    const wrapper = mount(SupervisorResultsPage, { props: { admin: true } })
    await flushPromises()

    expect(fetchMock).not.toHaveBeenCalled()
    expect(wrapper.find('.card-title').text()).toBe('Results')
    // Both, though neither is released, each saying so.
    expect(tabNames(wrapper)).toEqual(['Marks', 'Certificates'])
    expect(wrapper.find('[data-test="marks-unreleased"]').exists()).toBe(true)
    await button(wrapper, 'Download Marks Spreadsheet')!.trigger('click')
    expect(downloadAllResultsSheet).toHaveBeenCalledWith('2026_BTF_Student_Marks_All_Groups.xlsx')

    await wrapper.findAll('[role="tab"]')[1]!.trigger('click')
    expect(wrapper.find('[data-test="certificates-unreleased"]').exists()).toBe(true)
    await button(wrapper, 'Download All Certificates')!.trigger('click')
    expect(downloadAllResultsCertificates).toHaveBeenCalledWith('2026_BTF_Certificates_All_Groups.zip')
    await button(wrapper, 'Download')!.trigger('click')
    expect(downloadAllResultsCertificate).toHaveBeenCalledWith(expect.objectContaining({ name: 'Amy Chen' }))
    expect(downloadSupervisorResultsCertificate).not.toHaveBeenCalled()
  })

  it('shows the marks spreadsheet highest total first, and downloads it', async () => {
    const wrapper = await mountPage(results())

    const headings = wrapper.findAll('th.data-table-head').map((th) => th.text())
    // As the spreadsheet heads them.
    expect(headings).toEqual(['Group', 'Students', 'Mentor', 'PM1', 'Poster Comment 1', 'MTotal'])
    // The criterion a mark is for, on hover.
    expect(wrapper.findAll('th.data-table-head')[3]!.attributes('title')).toBe('Visual clarity')
    expect(rowTexts(wrapper)[0]).toContain('BTF02')

    await button(wrapper, 'Download Marks Spreadsheet')!.trigger('click')
    expect(downloadSupervisorResultsSheet).toHaveBeenCalledWith('2026_BTF_Student_Marks_Sam_Lee.xlsx')
  })

  it('shows only Group and the marks, then every column again, still searching them all', async () => {
    const wrapper = await mountPage(results())
    const headings = () => wrapper.findAll('th.data-table-head').map((th) => th.text())

    await button(wrapper, 'Show marks only')!.trigger('click')
    expect(headings()).toEqual(['Group', 'PM1', 'MTotal'])
    // A hidden column's text is still found.
    await wrapper.find('input[type="search"]').setValue('Mo Mentor')
    expect(rowTexts(wrapper)).toHaveLength(1)
    expect(rowTexts(wrapper)[0]).toContain('BTF01')

    await button(wrapper, 'Show all columns')!.trigger('click')
    expect(headings()).toEqual(['Group', 'Students', 'Mentor', 'PM1', 'Poster Comment 1', 'MTotal'])
  })

  it("colours each criterion's mark from red (0) to green (5) with Show marks only, but not the total", async () => {
    const wrapper = await mountPage(results({
      groups: [
        { group_id: 10, TeamCode: 'BTF01', Students: 'Amy Chen', Mentor: '', PM1: '0', MTotal: '40' },
        { group_id: 11, TeamCode: 'BTF02', Students: 'Fin Al', Mentor: '', PM1: '5', MTotal: '55' },
        { group_id: 12, TeamCode: 'BTF03', Students: 'Cara Ng', Mentor: '', PM1: '', MTotal: '30' },
      ],
    }))
    // Every column showing: no colour.
    expect(wrapper.find('tbody [class*="mark-score-"]').exists()).toBe(false)
    await button(wrapper, 'Show marks only')!.trigger('click')
    // Group, PM1, MTotal: highest total first.
    const cells = wrapper.findAll('tbody tr.data-table-row').map((row) => row.findAll('td'))
    expect(cells[0]![1]!.classes()).toContain('mark-score-5')
    expect(cells[1]![1]!.classes()).toContain('mark-score-0')
    // No mark, no colour; nor the total.
    expect(cells[2]![1]!.classes().some((name) => name.startsWith('mark-score-'))).toBe(false)
    expect(cells[0]![2]!.classes().some((name) => name.startsWith('mark-score-'))).toBe(false)
  })

  it("lists students' and mentors' certificates, a finalist's released separately", async () => {
    const wrapper = await mountPage(results())
    await wrapper.findAll('[role="tab"]')[1]!.trigger('click')

    const finalist = wrapper.findAll('tr.data-table-row').find((row) => row.text().includes('Fin Al'))!
    expect(finalist.text()).toContain('Will be Released Separately')
    expect(finalist.findAll('button')).toHaveLength(0)

    const amy = wrapper.findAll('tr.data-table-row').find((row) => row.text().includes('Amy Chen'))!
    await amy.find('button').trigger('click')
    expect(downloadSupervisorResultsCertificate).toHaveBeenCalledWith(expect.objectContaining({ user_id: 1 }))

    await button(wrapper, 'Download All Certificates')!.trigger('click')
    expect(downloadSupervisorResultsCertificates).toHaveBeenCalledWith('2026_BTF_Certificates_Sam_Lee.zip')
  })

  it('lists certificates by group, then role, then name, with headings that do not sort', async () => {
    const wrapper = await mountPage(
      results({
        marks_released: false,
        columns: [],
        groups: [],
        people: [
          person({ user_id: 5, name: 'Zed Mentor', kind: 'mentor', group_name: 'BTF2', group_id: 2 }),
          person({ user_id: 6, name: 'Bo Student', group_name: 'BTF10', group_id: 10 }),
          person({ user_id: 7, name: 'Al Student', group_name: 'BTF2', group_id: 2 }),
          person({ user_id: 8, name: 'Cy Student', group_name: 'BTF2', group_id: 2 })
        ]
      })
    )

    expect(wrapper.findAll('th.data-table-head').map((th) => th.text())).toEqual([
      'Group',
      'Role',
      'Name',
      'Certificate'
    ])
    expect(wrapper.findAll('.data-table-sort-btn')).toHaveLength(0)
    expect(rowTexts(wrapper).map((text) => text.replace('Download', '').trim())).toEqual([
      'BTF2StudentAl Student',
      'BTF2StudentCy Student',
      'BTF2MentorZed Mentor',
      'BTF10StudentBo Student'
    ])
  })
})
