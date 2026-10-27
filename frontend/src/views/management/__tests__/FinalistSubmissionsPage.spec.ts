import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import FinalistSubmissionsPage from '@/views/management/FinalistSubmissionsPage.vue'
import {
  downloadPresentationSlidesZip,
  fetchFinalistSubmissionsClose,
  fetchPresentationSlides,
  saveFinalistSubmissionsClose
} from '@/utils/managementAPI'
import { setDateTimeFields } from '@/__tests__/appPicker'

vi.mock('@/utils/managementAPI', () => ({
  fetchFinalistSubmissionsClose: vi.fn(),
  saveFinalistSubmissionsClose: vi.fn(),
  fetchPresentationSlides: vi.fn(),
  downloadPresentationSlidesZip: vi.fn(),
  presentationSlidesUrl: (groupId: number) => `/slides/${groupId}/file/`,
  presentationSlidesDownloadUrl: (groupId: number) => `/slides/${groupId}/file/?download=1`
}))
const closeMock = vi.mocked(fetchFinalistSubmissionsClose)
const saveMock = vi.mocked(saveFinalistSubmissionsClose)
const slidesMock = vi.mocked(fetchPresentationSlides)
const zipMock = vi.mocked(downloadPresentationSlidesZip)

const mountPage = async () => {
  const wrapper = mount(FinalistSubmissionsPage, {
    global: { stubs: { RouterLink: { props: ['to'], template: '<a :href="to"><slot /></a>' } } }
  })
  await flushPromises()
  return wrapper
}

const buttonNamed = (wrapper: Awaited<ReturnType<typeof mountPage>>, label: string) =>
  wrapper.findAll('button').find((b) => b.text().trim() === label)!

beforeEach(() => {
  closeMock.mockReset().mockResolvedValue({ close: null })
  saveMock.mockReset()
  zipMock.mockReset().mockResolvedValue()
  slidesMock.mockReset().mockResolvedValue({
    slides_due: '2026-10-16',
    teams: [
      {
        group_id: 2,
        group_name: 'BTF2',
        submitted: true,
        file_name: 'BTF2 slides.pptx',
        submitted_by: 'Zoe Lee',
        submitted_at: '2026-10-10T03:05:00Z'
      },
      {
        group_id: 10,
        group_name: 'BTF10',
        submitted: false,
        file_name: '',
        submitted_by: null,
        submitted_at: null
      }
    ]
  })
})

describe('the closing time card', () => {
  it('says finalist teams can keep submitting until a time is set', async () => {
    const wrapper = await mountPage()
    const card = wrapper.find('.finalist-close')
    expect(card.find('.card-title').text()).toBe('Finalist Submissions')
    // Its subheading, as the other Symposium pages have one.
    expect(card.find('.finalist-presentation__section-title').text()).toBe('Close Submissions')
    expect(card.text()).toContain('No closing time set - finalist teams can keep submitting.')
    // Then the slides each team has handed in, below it.
    expect(wrapper.findAll('section.card').map((section) => section.find('h3').text())).toEqual([
      'Finalist Submissions',
      'Finalist Submissions'
    ])
  })

  it('shows the time in force, open or closed, and who set it', async () => {
    closeMock.mockResolvedValue({
      close: {
        closes_at: '2026-10-20T06:59:00Z', is_open: false, set_by: 'Amy Chen', created_at: '2026-10-18T01:00:00Z'
      }
    })
    const wrapper = await mountPage()
    const card = wrapper.find('.finalist-close')
    expect(card.find('.finalist-close__state--closed').text()).toBe('Finalist submissions closed')
    expect(card.text()).toContain('Closes:')
    expect(card.text()).toContain('Set by Amy Chen on')
  })

  it('sets a closing time once it is confirmed', async () => {
    const saved = {
      closes_at: '2026-10-20T12:59:00Z', is_open: true, set_by: 'Amy Chen', created_at: '2026-10-18T01:00:00Z'
    }
    saveMock.mockResolvedValue({ close: saved })
    const wrapper = await mountPage()
    await setDateTimeFields(wrapper, '.sydney-date-time', '2026-10-20T23:59')
    await wrapper.find('.finalist-close__form').trigger('submit')
    expect(wrapper.find('[role="dialog"]').text()).toContain('Close finalist submissions?')
    expect(saveMock).not.toHaveBeenCalled()
    await buttonNamed(wrapper, 'Confirm').trigger('click')
    await flushPromises()
    // 23:59 in Sydney (AEDT, UTC+11), whatever the computer's time zone.
    expect(saveMock).toHaveBeenCalledWith('2026-10-20T12:59:00.000Z')
    expect(wrapper.find('[role="dialog"]').exists()).toBe(false)
    expect(wrapper.find('.finalist-close__state--open').text()).toBe('Finalist submissions open')
  })

  it("says why a time wasn't set", async () => {
    saveMock.mockRejectedValue(new Error('Server down'))
    const wrapper = await mountPage()
    await wrapper.find('.finalist-close__form').trigger('submit')
    await buttonNamed(wrapper, 'Confirm').trigger('click')
    await flushPromises()
    expect(wrapper.find('.finalist-close__banner').text()).toBe('Server down')
  })
})

describe('Finalist Submissions', () => {
  it("Finalist Submissions lists each finalist team's slides and when they're due", async () => {
    const wrapper = await mountPage()
    const table = wrapper.find('.finalist-presentation__submissions')
    expect(table.find('h3').text()).toBe('Finalist Submissions')
    expect(table.text()).toContain("Each finalist team's presentation slides, due Friday, 16th October 2026")
    // How many have handed theirs in, as Grading's By Group counts them.
    expect(table.find('.data-table-stats').text()).toBe('1/2 Submitted')
    // Open and Download each have a column, both headed Actions for screen readers.
    expect(table.findAll('thead th').map((h) => h.text())).toEqual([
      'Group',
      'Submitted',
      'Type',
      'Actions',
      'Actions'
    ])
    const [btf2, btf10] = table.findAll('tbody tr')
    const cells = btf2!.findAll('td')
    expect(cells[0]!.text()).toBe('BTF2')
    expect(cells[1]!.text()).toMatch(/^10\/10\/26 \d{2}:05$/)
    expect(cells[2]!.text()).toBe('PPTX')
    // PowerPoint can't show in the browser: only Download, its name on hover.
    expect(cells[3]!.find('a').exists()).toBe(false)
    const links = btf2!.findAll('a')
    expect(links.map((a) => a.text())).toEqual(['Download'])
    expect(links[0]!.attributes('href')).toBe('/slides/2/file/?download=1')
    expect(links[0]!.attributes('title')).toBe('BTF2 slides.pptx')
    expect(btf10!.findAll('td').slice(0, 3).map((c) => c.text())).toEqual(['BTF10', 'Not submitted yet', '—'])
    expect(btf10!.find('a').exists()).toBe(false)
  })

  it('a PDF opens in a new tab, with Download to its right', async () => {
    slidesMock.mockResolvedValue({
      slides_due: '2026-10-16',
      teams: [
        {
          group_id: 2, group_name: 'BTF2', submitted: true, file_name: 'BTF2 slides.pdf',
          submitted_by: 'Amy Chen', submitted_at: '2026-10-10T00:05:00Z'
        }
      ]
    })
    const wrapper = await mountPage()
    const row = wrapper.find('.finalist-presentation__submissions tbody tr')
    expect(row.findAll('td')[2]!.text()).toBe('PDF')
    const [open, download] = row.findAll('a')
    expect([open!.text(), download!.text()]).toEqual(['Open', 'Download'])
    expect(open!.attributes('href')).toBe('/slides/2/file/')
    expect(open!.attributes('target')).toBe('_blank')
    expect(download!.attributes('href')).toBe('/slides/2/file/?download=1')
  })

  it('asks for the slides due date while it is not set', async () => {
    slidesMock.mockResolvedValue({ slides_due: null, teams: [] })
    const wrapper = await mountPage()
    const table = wrapper.find('.finalist-presentation__submissions')
    expect(table.text()).toContain("Set the date they're due on Notify Finalists.")
    expect(table.find('.data-table-empty').text()).toBe('No finalist teams yet.')
  })

  it("Download All saves every team's slides in one zip, Preparing until it's ready", async () => {
    let finish!: () => void
    zipMock.mockImplementation(() => new Promise<void>((resolve) => (finish = resolve)))
    const wrapper = await mountPage()
    await buttonNamed(wrapper, 'Download All').trigger('click')

    expect(zipMock).toHaveBeenCalledOnce()
    const preparing = buttonNamed(wrapper, 'Preparing…')
    expect(preparing.attributes('disabled')).toBeDefined()
    finish()
    await flushPromises()
    expect(buttonNamed(wrapper, 'Download All').attributes('disabled')).toBeUndefined()
    // The green button.
    expect(buttonNamed(wrapper, 'Download All').classes()).toContain('btn-primary')
  })

  it("says why the slides weren't saved", async () => {
    zipMock.mockRejectedValueOnce(new Error('Server down'))
    const wrapper = await mountPage()
    await buttonNamed(wrapper, 'Download All').trigger('click')
    await flushPromises()

    const section = wrapper.find('.finalist-presentation__submissions')
    expect(section.find('[role="alert"]').text()).toBe('Failed to download the slides. Server down')
  })

  it('Download All waits for slides to be in', async () => {
    slidesMock.mockResolvedValue({ slides_due: null, teams: [] })
    const wrapper = await mountPage()
    expect(buttonNamed(wrapper, 'Download All').attributes('disabled')).toBeDefined()
  })
})

describe('searching the finalist teams', () => {
  const team = (group_id: number, group_name: string, submitted_at: string) => ({
    group_id, group_name, submitted: true, file_name: `${group_name}.pdf`, submitted_by: null, submitted_at
  })

  it('finds a team however it is typed, the closest first, not the newest', async () => {
    // Newest first, as the page lists them: BTF111 handed in last.
    slidesMock.mockResolvedValue({
      slides_due: null,
      teams: [
        team(111, 'BTF111', '2026-10-12T00:00:00Z'),
        team(21, 'BTF21', '2026-10-11T00:00:00Z'),
        team(10, 'BTF10', '2026-10-10T00:00:00Z'),
        team(1, 'BTF01', '2026-10-09T00:00:00Z')
      ]
    })
    const wrapper = await mountPage()
    const table = wrapper.find('.finalist-presentation__submissions')
    const groups = () => table.findAll('tbody tr td:first-child').map((cell) => cell.text())

    for (const typed of ['btf 1', 'BTF1', 'btf-01']) {
      await table.find('input[type="search"]').setValue(typed)
      expect(groups()).toEqual(['BTF01', 'BTF10', 'BTF111'])
    }
    await table.find('input[type="search"]').setValue('BTF 21')
    expect(groups()).toEqual(['BTF21'])
    // Only the group is searched: every row's date has a 10 in it.
    await table.find('input[type="search"]').setValue('10')
    expect(groups()).toEqual(['BTF10'])
  })
})
