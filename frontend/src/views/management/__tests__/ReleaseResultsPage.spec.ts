import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import ReleaseResultsPage from '@/views/management/ReleaseResultsPage.vue'
import ReleasePage from '@/views/management/ReleasePage.vue'
import {
  downloadResultsSampleSheet,
  downloadSupervisorMarksSheet,
  fetchCertificatesRelease,
  fetchTestEmailRecipients,
  fetchRelease,
  fetchResultsEmailDetails,
  previewResultsEmail,
  startResultsEmail,
  updateResultsEmailDetails
} from '@/utils/managementAPI'

vi.mock('@/utils/managementAPI', () => ({
  downloadResultsSampleSheet: vi.fn(),
  downloadSupervisorMarksSheet: vi.fn(),
  fetchTestEmailRecipients: vi.fn(async () => ({ recipients: [] })),
  sendTestEmail: vi.fn(),
  fetchRelease: vi.fn(),
  toggleRelease: vi.fn(),
  fetchCertificatesRelease: vi.fn(),
  setCertificatesFinalistExclusion: vi.fn(),
  toggleCertificatesRelease: vi.fn(),
  fetchResultsEmailDetails: vi.fn(),
  updateResultsEmailDetails: vi.fn(),
  previewResultsEmail: vi.fn(),
  startResultsEmail: vi.fn()
}))
const detailsMock = vi.mocked(fetchResultsEmailDetails)
const saveMock = vi.mocked(updateResultsEmailDetails)
const previewMock = vi.mocked(previewResultsEmail)
const sendMock = vi.mocked(startResultsEmail)

// A run's progress, as the server reports it.
const run = (over: Record<string, unknown> = {}) => ({
  due: 9,
  emailed: 0,
  failed: 0,
  error: '',
  missed: [] as { who: string; reason: string }[],
  started_at: '2026-10-20T00:00:00Z',
  finished_at: null as string | null,
  ...over
})
const sendingRun = (over: Record<string, unknown> = {}) => ({ sending: true, queued: 0, ahead: [], run: run(over) })
const finishedRun = (over: Record<string, unknown> = {}) => ({
  sending: false,
  queued: 0,
  ahead: [] as string[],
  run: run({ finished_at: '2026-10-20T00:01:00Z', ...over })
})
const IDLE = { sending: false, queued: 0, ahead: [] as string[], run: null }

const status = { released_at: null, released_by: null, submissions_open: false }

const details = (over: Record<string, unknown> = {}) => ({
  survey_url: 'https://survey.example.com/s',
  survey_closes: '2026-11-30',
  complete: true,
  today: '2026-09-28',
  closes_in_past: false,
  year: 2026,
  marks_released: true,
  certificates_released: true,
  emails_on: { groups: true, supervisors: true },
  templates_ready: { groups: true, supervisors: true },
  submissions_open: '',
  runs: { groups: IDLE, supervisors: IDLE },
  groups: { total: 3, emailed: 0 },
  supervisors: { total: 2, emailed: 0 },
  ...over
})

const mountPage = async () => {
  const wrapper = mount(ReleaseResultsPage, { global: { stubs: { teleport: true } } })
  await flushPromises()
  return wrapper
}

const buttonNamed = (wrapper: Awaited<ReturnType<typeof mountPage>>, label: RegExp) =>
  wrapper.findAll('button').find((b) => label.test(b.text().trim()))!

beforeEach(() => {
  vi.mocked(fetchRelease).mockReset().mockResolvedValue(status)
  vi.mocked(fetchCertificatesRelease).mockReset().mockResolvedValue({ ...status, exclude_finalists: true })
  detailsMock.mockReset().mockResolvedValue(details())
  saveMock.mockReset()
  previewMock.mockReset()
  sendMock.mockReset()
})

describe('layout', () => {
  it('is the title card, marks, certificates, then sending the results emails', async () => {
    const wrapper = await mountPage()
    const cards = wrapper.findAll('.card')
    expect(cards).toHaveLength(4)
    expect(cards[0]!.find('.card-title').text()).toBe('Release Results')
    expect(cards[0]!.text()).toContain('Releasing shows results only to students whose group made a submission.')
    expect(cards[0]!.text()).toContain('Email Details')
    expect(cards[1]!.find('.release__section-title').text()).toBe('Release Marks')
    expect(cards[2]!.find('.release__section-title').text()).toBe('Release Certificates')
    expect(cards[3]!.text()).toContain('Send Results Emails')
    expect(cards[3]!.text()).toContain('Groups: 0 of 3 emailed · Supervisors: 0 of 2 emailed')
    expect(wrapper.text()).not.toContain('still being built')
  })

  it('says the group email goes to its students and mentors, with all their certificates', async () => {
    const wrapper = await mountPage()
    const hints = wrapper.findAll('.release-results__send .release-results__hint').map((p) => p.text())
    expect(hints).toEqual([
      "Emails every group that submitted, and its students' supervisors, that their results are out. Each is emailed once.",
      "Group emails go to the group's students and mentors with every certificate in the group attached, so " +
        "students get each other's and their mentor's certificates. Anyone in multiple groups gets multiple emails, " +
        'one for each group.'
    ])
  })
})

describe('email details', () => {
  it('saves the survey link and close date', async () => {
    saveMock.mockResolvedValueOnce(details({ survey_url: 'https://survey.example.com/new' }))
    const wrapper = await mountPage()
    await wrapper.find('input[type="url"]').setValue('https://survey.example.com/new')
    await buttonNamed(wrapper, /^Save$/).trigger('click')
    await flushPromises()
    expect(saveMock).toHaveBeenCalledWith({
      survey_url: 'https://survey.example.com/new',
      survey_closes: '2026-11-30'
    })
    expect(wrapper.text()).toContain('Email details saved.')
  })

  it('Save can be pressed without changes, saving the details as they are', async () => {
    saveMock.mockResolvedValueOnce(details())
    const wrapper = await mountPage()
    const save = buttonNamed(wrapper, /^Save$/)
    expect(save.attributes('disabled')).toBeUndefined()
    await save.trigger('click')
    await flushPromises()
    expect(saveMock).toHaveBeenCalledWith({
      survey_url: 'https://survey.example.com/s',
      survey_closes: '2026-11-30'
    })
  })

  it('a saved close date that has passed is pointed out when Save is pressed', async () => {
    detailsMock.mockResolvedValue(details({ survey_closes: '2026-09-01', closes_in_past: true }))
    const wrapper = await mountPage()
    expect(wrapper.find('.release-results__field-error').exists()).toBe(false)
    await buttonNamed(wrapper, /^Save$/).trigger('click')
    await flushPromises()
    expect(saveMock).not.toHaveBeenCalled()
    expect(wrapper.find('.release-results__field-error').text()).toBe("Survey Closes can't be before today.")
  })

  it('a close date before today is only pointed out, above Save, once Save is pressed', async () => {
    const wrapper = await mountPage()
    const date = wrapper.find('input[type="date"]')
    await date.setValue('2026-09-01')
    expect(wrapper.find('.release-results__field-error').exists()).toBe(false)
    await buttonNamed(wrapper, /^Save$/).trigger('click')
    await flushPromises()
    expect(saveMock).not.toHaveBeenCalled()
    expect(wrapper.find('.release-results__field-error').text()).toBe("Survey Closes can't be before today.")
    expect(date.classes()).toContain('is-invalid')
  })
})

describe('preview', () => {
  it('has a button for the group email and one for the supervisor email', async () => {
    const groupFiles = [
      '2026_BTF_Student_Certificate_Amy_Chen.docx',
      '2026_BTF_Mentor_Certificate_Mo_Mentor.docx',
      '2026_BTF_Marks_BTF01.docx'
    ]
    previewMock.mockImplementation(async (audience) => ({
      subject: audience === 'groups' ? 'Your 2026 results' : 'Your students’ 2026 results',
      to: audience === 'groups' ? 'BTF01' : 'Sam Lee',
      html: '<p>email</p>',
      attachments:
        audience === 'groups'
          ? groupFiles
          : ['2026_BTF_Student_Certificate_Amy_Chen.docx', '2026_BTF_Student_Marks_Sam_Lee.xlsx']
    }))
    const wrapper = await mountPage()
    await wrapper.find('input[type="url"]').setValue('https://survey.example.com/draft')
    await buttonNamed(wrapper, /^Preview Group Email$/).trigger('click')
    await flushPromises()
    expect(previewMock).toHaveBeenCalledWith('groups', {
      survey_url: 'https://survey.example.com/draft',
      survey_closes: '2026-11-30'
    }, '')
    expect(wrapper.find('[aria-label="Email preview"]').text()).toContain('As BTF01 would get it.')
    const attachments = () => wrapper.findAll('.release-results__attachments li').map((li) => li.text())
    expect(attachments()).toEqual(groupFiles)

    await buttonNamed(wrapper, /^Close$/).trigger('click')
    expect(wrapper.find('[aria-label="Email preview"]').exists()).toBe(false)
    await buttonNamed(wrapper, /^Preview Supervisor Email$/).trigger('click')
    await flushPromises()
    expect(previewMock).toHaveBeenLastCalledWith('supervisors', expect.any(Object), '')
    expect(wrapper.find('[aria-label="Email preview"]').text()).toContain('As Sam Lee would get it.')
    expect(attachments()).toEqual(['2026_BTF_Student_Certificate_Amy_Chen.docx', '2026_BTF_Student_Marks_Sam_Lee.xlsx'])
  })
})

describe('preview of the person picked', () => {
  it('each preview is the email the person picked beside it gets', async () => {
    vi.mocked(fetchTestEmailRecipients).mockImplementation(async (kind) => ({
      recipients: kind === 'results-supervisors'
        ? [{ value: '7', label: 'Sam Lee' }, { value: '9', label: 'Ann Wu' }]
        : [{ value: '1:11', label: '(BTF01) Amy Chen' }, { value: '2:12', label: '(BTF02) Ben Lee' }]
    }))
    previewMock.mockResolvedValue({ subject: 'Results', to: 'Ann Wu', html: '<p>email</p>', attachments: [] })
    const wrapper = await mountPage()
    const [groupSelect, supervisorSelect] = wrapper.findAll('.test-email__select')
    await groupSelect!.setValue('2:12')
    await supervisorSelect!.setValue('9')
    await buttonNamed(wrapper, /^Preview Group Email$/).trigger('click')
    await flushPromises()
    expect(previewMock).toHaveBeenLastCalledWith('groups', expect.any(Object), '2:12')
    await buttonNamed(wrapper, /^Close$/).trigger('click')
    await buttonNamed(wrapper, /^Preview Supervisor Email$/).trigger('click')
    await flushPromises()
    expect(previewMock).toHaveBeenLastCalledWith('supervisors', expect.any(Object), '9')
    vi.mocked(fetchTestEmailRecipients).mockImplementation(async () => ({ recipients: [] }))
  })
})

describe('sample spreadsheet', () => {
  it('can be downloaded from the bottom of the Release Results card, above Release Marks', async () => {
    const sampleMock = vi.mocked(downloadResultsSampleSheet)
    sampleMock.mockReset().mockResolvedValueOnce()
    const wrapper = await mountPage()
    const buttons = wrapper.findAll('.card')[0]!.findAll('button').map((b) => b.text())
    expect(buttons.slice(-2)).toEqual(['Download Sample Marks Spreadsheet', 'Download Supervisor Marks'])
    await buttonNamed(wrapper, /^Download Sample Marks Spreadsheet$/).trigger('click')
    await flushPromises()
    expect(sampleMock).toHaveBeenCalledOnce()
  })

  it("Download Supervisor Marks downloads the chosen supervisor's real spreadsheet", async () => {
    vi.mocked(fetchTestEmailRecipients).mockImplementation(async (kind) => ({
      recipients: kind === 'results-supervisors'
        ? [{ value: '7', label: 'Sam Lee' }, { value: '9', label: 'Ann Wu' }]
        : []
    }))
    const sheetMock = vi.mocked(downloadSupervisorMarksSheet)
    sheetMock.mockReset().mockResolvedValueOnce()
    const wrapper = await mountPage()
    const select = wrapper.find('.release-results__supervisor-select')
    expect(select.findAll('option').map((o) => o.text())).toEqual(['Sam Lee', 'Ann Wu'])
    await select.setValue('9')
    await buttonNamed(wrapper, /^Download Supervisor Marks$/).trigger('click')
    await flushPromises()
    expect(sheetMock).toHaveBeenCalledWith('9')
    vi.mocked(fetchTestEmailRecipients).mockImplementation(async () => ({ recipients: [] }))
  })

  it('Download Supervisor Marks is off while no supervisor is due the email', async () => {
    const wrapper = await mountPage()
    expect(wrapper.find('.release-results__supervisor-select option').text()).toBe('Nobody yet')
    expect(buttonNamed(wrapper, /^Download Supervisor Marks$/).attributes('disabled')).toBeDefined()
  })

  it('says why a download failed', async () => {
    vi.mocked(downloadResultsSampleSheet).mockReset().mockRejectedValueOnce(new Error('Server down'))
    const wrapper = await mountPage()
    await buttonNamed(wrapper, /^Download Sample Marks Spreadsheet$/).trigger('click')
    await flushPromises()
    expect(wrapper.find('.release-results__banner--error').text()).toContain('Server down')
  })
})

describe('sending', () => {
  const emailButton = (wrapper: Awaited<ReturnType<typeof mountPage>>, who: 'Groups' | 'Supervisors') =>
    buttonNamed(wrapper, new RegExp(`^Email ${who}$`))

  it('waits until marks and certificates are both released', async () => {
    detailsMock.mockResolvedValue(details({ certificates_released: false }))
    const wrapper = await mountPage()
    expect(wrapper.find('.release-results__blocked').text()).toBe(
      'Release both marks and certificates before sending the results emails.'
    )
    expect(emailButton(wrapper, 'Groups').attributes('disabled')).toBeDefined()
    expect(emailButton(wrapper, 'Supervisors').attributes('disabled')).toBeDefined()
  })

  it('only emailing groups waits for the survey details', async () => {
    detailsMock.mockResolvedValue(details({ survey_closes: null, complete: false }))
    const wrapper = await mountPage()
    expect(wrapper.find('.release-results__blocked').text()).toBe(
      'Set the feedback survey link and close date above before emailing groups.'
    )
    expect(emailButton(wrapper, 'Groups').attributes('disabled')).toBeDefined()
    expect(emailButton(wrapper, 'Supervisors').attributes('disabled')).toBeUndefined()
  })

  it('waits for the Document Setup templates the attached files need', async () => {
    detailsMock.mockResolvedValue(details({ templates_ready: { groups: false, supervisors: true } }))
    const wrapper = await mountPage()
    expect(wrapper.find('.release-results__blocked').text()).toBe(
      'Upload the marks summary, student certificate and mentor certificate templates in Document Setup before emailing groups.'
    )
    expect(emailButton(wrapper, 'Groups').attributes('disabled')).toBeDefined()
    expect(emailButton(wrapper, 'Supervisors').attributes('disabled')).toBeUndefined()
  })

  it('supervisors wait for the student and mentor certificate templates', async () => {
    detailsMock.mockResolvedValue(details({ templates_ready: { groups: true, supervisors: false } }))
    const wrapper = await mountPage()
    expect(wrapper.find('.release-results__blocked').text()).toBe(
      'Upload the student certificate and mentor certificate templates in Document Setup before emailing supervisors.'
    )
    expect(emailButton(wrapper, 'Supervisors').attributes('disabled')).toBeDefined()
  })

  it('waits for an extension granted since the release, saying until when', async () => {
    const reason =
      "A team's extension is open until Friday, 17 October 2026, 11:59 PM (Sydney time). Send this once every extension has ended."
    detailsMock.mockResolvedValue(details({ submissions_open: reason }))
    const wrapper = await mountPage()
    expect(wrapper.find('.release-results__blocked').text()).toBe(reason)
    expect(emailButton(wrapper, 'Groups').attributes('disabled')).toBeDefined()
    expect(emailButton(wrapper, 'Supervisors').attributes('disabled')).toBeDefined()
  })

  it('asks first, then starts a run on the server and shows its progress until it is done', async () => {
    vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval'] })
    try {
      sendMock.mockResolvedValueOnce(details({ runs: { groups: sendingRun(), supervisors: IDLE } }))
      const wrapper = await mountPage()
      await emailButton(wrapper, 'Groups').trigger('click')
      const dialog = wrapper.find('[aria-label="Send results emails"]')
      expect(dialog.text()).toContain(
        "This emails the students and mentors of the 3 groups that haven't had their results email yet."
      )
      await buttonNamed(wrapper, /^Send$/).trigger('click')
      await flushPromises()

      // The dialog closes; the run sends on the server, its progress beside the buttons.
      expect(sendMock).toHaveBeenCalledWith('groups')
      expect(wrapper.find('[aria-label="Send results emails"]').exists()).toBe(false)
      expect(wrapper.find('.release-results__progress').text()).toBe('Emailed 0 of 9 people so far…')
      expect(emailButton(wrapper, 'Supervisors').attributes('disabled')).toBeUndefined()

      detailsMock.mockResolvedValue(details({ runs: { groups: sendingRun({ emailed: 6 }), supervisors: IDLE } }))
      vi.advanceTimersByTime(2000)
      await flushPromises()
      expect(wrapper.find('.release-results__progress').text()).toBe('Emailed 6 of 9 people so far…')

      detailsMock.mockResolvedValue(details({
        runs: { groups: finishedRun({ emailed: 9 }), supervisors: IDLE },
        groups: { total: 3, emailed: 3 }
      }))
      vi.advanceTimersByTime(2000)
      await flushPromises()
      expect(wrapper.find('.release-results__progress').exists()).toBe(false)
      expect(wrapper.text()).toContain('Emailed 9 people.')
      expect(wrapper.find('.release-results__counts').text()).toBe(
        'Groups: 3 of 3 emailed · Supervisors: 0 of 2 emailed'
      )
    } finally {
      vi.useRealTimers()
    }
  })

  it('a page opened mid-run shows its progress, and more sends can be queued', async () => {
    detailsMock.mockResolvedValue(details({ runs: { groups: IDLE, supervisors: sendingRun({ due: 2, emailed: 1 }) } }))
    const wrapper = await mountPage()
    expect(wrapper.find('.release-results__progress').text()).toBe('Emailed 1 of 2 supervisors so far…')
    expect(emailButton(wrapper, 'Supervisors').attributes('disabled')).toBeUndefined()
    expect(emailButton(wrapper, 'Groups').attributes('disabled')).toBeUndefined()
  })

  it('a send pressed while another is going says it is queued', async () => {
    sendMock.mockResolvedValueOnce(details({ runs: { groups: { ...IDLE, queued: 1 }, supervisors: IDLE } }))
    // Nothing ahead: it waits only the few seconds after the last send.
    const wrapper = await mountPage()
    await emailButton(wrapper, 'Groups').trigger('click')
    await buttonNamed(wrapper, /^Send$/).trigger('click')
    await flushPromises()
    expect(wrapper.find('.release-results__banner--ok').text()).toBe('Queued. It starts in a few seconds.')
    expect(wrapper.find('.release-results__queued').text()).toBe('Groups: Queued, starts in a few seconds.')
  })

  it('says how many groups were not emailed in full, for a retry', async () => {
    sendMock.mockResolvedValueOnce(details({ runs: { groups: finishedRun({ emailed: 4, failed: 1 }), supervisors: IDLE } }))
    const wrapper = await mountPage()
    await emailButton(wrapper, 'Groups').trigger('click')
    await buttonNamed(wrapper, /^Send$/).trigger('click')
    await flushPromises()
    expect(wrapper.find('.release-results__banner--error').text()).toBe(
      "Emailed 4 people. 1 group wasn't emailed in full; press Email Groups to email only those it missed."
    )
  })

  it("lists, under the buttons, who each email couldn't reach", async () => {
    detailsMock.mockResolvedValue(details({
      runs: {
        groups: finishedRun({ failed: 1, missed: [{ who: '(BTF07) Amy Chen', reason: 'address refused' }, { who: '(BTF07) Ben Lee', reason: 'address refused' }] }),
        supervisors: finishedRun({ due: 2, emailed: 1, failed: 1, missed: [{ who: '(BTF07, BTF12) Sam Lee', reason: 'sending limit reached' }] })
      }
    }))
    const wrapper = await mountPage()
    const listed = (audience: string) =>
      wrapper.find(`[data-testid="missed-${audience}"]`).findAll('li').map((li) => li.text())
    expect(wrapper.find('[data-testid="missed-groups"]').text()).toContain("The group email couldn't reach:")
    expect(listed('groups')).toEqual(['(BTF07) Amy Chen · address refused', '(BTF07) Ben Lee · address refused'])
    expect(wrapper.find('[data-testid="missed-supervisors"]').text()).toContain("The supervisor email couldn't reach:")
    expect(listed('supervisors')).toEqual(['(BTF07, BTF12) Sam Lee · sending limit reached'])
  })

  it('shows no list when everyone was reached', async () => {
    detailsMock.mockResolvedValue(details({ runs: { groups: finishedRun({ emailed: 9 }), supervisors: IDLE } }))
    const wrapper = await mountPage()
    expect(wrapper.find('.release-results__missed').exists()).toBe(false)
  })

  it('says when the mail server could not be reached', async () => {
    const error = "Couldn't reach the mail server. Press Send again to email the rest."
    sendMock.mockResolvedValueOnce(details({ runs: { groups: IDLE, supervisors: finishedRun({ due: 2, failed: 2, error }) } }))
    const wrapper = await mountPage()
    await emailButton(wrapper, 'Supervisors').trigger('click')
    await buttonNamed(wrapper, /^Send$/).trigger('click')
    await flushPromises()
    expect(wrapper.find('.release-results__banner--error').text()).toBe(`Emailed 0 supervisors. ${error}`)
  })

  it('rechecks once marks are released below', async () => {
    const wrapper = await mountPage()
    detailsMock.mockClear()
    wrapper.findComponent(ReleasePage).vm.$emit('changed')
    await flushPromises()
    expect(detailsMock).toHaveBeenCalledOnce()
  })
})
