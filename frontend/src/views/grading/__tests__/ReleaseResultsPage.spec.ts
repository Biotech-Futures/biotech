import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import ReleaseResultsPage from '@/views/grading/ReleaseResultsPage.vue'
import ReleasePage from '@/views/grading/ReleasePage.vue'
import {
  downloadResultsSampleSheet,
  fetchCertificatesRelease,
  fetchRelease,
  fetchResultsEmailDetails,
  previewResultsEmail,
  sendResultsEmailBatch,
  updateResultsEmailDetails
} from '@/utils/gradingAPI'

vi.mock('@/utils/gradingAPI', () => ({
  downloadResultsSampleSheet: vi.fn(),
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
  sendResultsEmailBatch: vi.fn()
}))
const detailsMock = vi.mocked(fetchResultsEmailDetails)
const saveMock = vi.mocked(updateResultsEmailDetails)
const previewMock = vi.mocked(previewResultsEmail)
const sendMock = vi.mocked(sendResultsEmailBatch)

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
          : ['2026_BTF_Student_Certificate_Amy_Chen.docx', '2026_BTF_Student_Marks.xlsx']
    }))
    const wrapper = await mountPage()
    await wrapper.find('input[type="url"]').setValue('https://survey.example.com/draft')
    await buttonNamed(wrapper, /^Preview Group Email$/).trigger('click')
    await flushPromises()
    expect(previewMock).toHaveBeenCalledWith('groups', {
      survey_url: 'https://survey.example.com/draft',
      survey_closes: '2026-11-30'
    })
    expect(wrapper.find('[aria-label="Email preview"]').text()).toContain('As BTF01 would get it.')
    const attachments = () => wrapper.findAll('.release-results__attachments li').map((li) => li.text())
    expect(attachments()).toEqual(groupFiles)

    await buttonNamed(wrapper, /^Close$/).trigger('click')
    expect(wrapper.find('[aria-label="Email preview"]').exists()).toBe(false)
    await buttonNamed(wrapper, /^Preview Supervisor Email$/).trigger('click')
    await flushPromises()
    expect(previewMock).toHaveBeenLastCalledWith('supervisors', expect.any(Object))
    expect(wrapper.find('[aria-label="Email preview"]').text()).toContain('As Sam Lee would get it.')
    expect(attachments()).toEqual(['2026_BTF_Student_Certificate_Amy_Chen.docx', '2026_BTF_Student_Marks.xlsx'])
  })
})

describe('sample spreadsheet', () => {
  it('can be downloaded from the bottom of the Release Results card, above Release Marks', async () => {
    const sampleMock = vi.mocked(downloadResultsSampleSheet)
    sampleMock.mockReset().mockResolvedValueOnce()
    const wrapper = await mountPage()
    const buttons = wrapper.findAll('.card')[0]!.findAll('button')
    expect(buttons[buttons.length - 1]!.text()).toBe('Download Sample Marks Spreadsheet')
    await buttons[buttons.length - 1]!.trigger('click')
    await flushPromises()
    expect(sampleMock).toHaveBeenCalledOnce()
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

  it('emails groups batch after batch until done, then supervisors on their own button', async () => {
    sendMock
      .mockResolvedValueOnce({
        emailed: 6, failed: 0, cursor: 9, done: false,
        groups: { total: 3, emailed: 2 }, supervisors: { total: 2, emailed: 0 }
      })
      .mockResolvedValueOnce({
        emailed: 3, failed: 0, cursor: 12, done: true,
        groups: { total: 3, emailed: 3 }, supervisors: { total: 2, emailed: 0 }
      })
    const wrapper = await mountPage()
    detailsMock.mockResolvedValue(details({ groups: { total: 3, emailed: 3 } }))

    await emailButton(wrapper, 'Groups').trigger('click')
    const dialog = wrapper.find('[aria-label="Send results emails"]')
    expect(dialog.text()).toContain('Email groups?')
    expect(dialog.text()).toContain(
      "This emails the students and mentors of the 3 groups that haven't had their results email yet."
    )
    await buttonNamed(wrapper, /^Send$/).trigger('click')
    await flushPromises()

    expect(sendMock.mock.calls).toEqual([['groups', null], ['groups', 9]])
    // People: every student and mentor emailed.
    expect(wrapper.text()).toContain('Emailed 9 people.')
    expect(wrapper.find('.release-results__counts').text()).toBe(
      'Groups: 3 of 3 emailed · Supervisors: 0 of 2 emailed'
    )
    // Groups are done; supervisors are still to go.
    expect(emailButton(wrapper, 'Groups').attributes('disabled')).toBeDefined()
    expect(emailButton(wrapper, 'Supervisors').attributes('disabled')).toBeUndefined()
    expect(wrapper.find('.release-results__status').text()).toBe(
      'Emails are not sent to every group and supervisor'
    )

    sendMock.mockResolvedValueOnce({
      emailed: 2, failed: 0, cursor: 7, done: true,
      groups: { total: 3, emailed: 3 }, supervisors: { total: 2, emailed: 2 }
    })
    detailsMock.mockResolvedValue(details({ groups: { total: 3, emailed: 3 }, supervisors: { total: 2, emailed: 2 } }))
    await emailButton(wrapper, 'Supervisors').trigger('click')
    await buttonNamed(wrapper, /^Send$/).trigger('click')
    await flushPromises()
    expect(sendMock).toHaveBeenLastCalledWith('supervisors', null)
    expect(wrapper.text()).toContain('Emailed 2 supervisors.')
    expect(wrapper.find('.release-results__status').text()).toBe(
      'Emails are sent to every group and supervisor'
    )
  })

  it('says how many groups were not emailed in full, for a retry', async () => {
    sendMock.mockResolvedValueOnce({
      emailed: 4, failed: 1, cursor: 12, done: true,
      groups: { total: 3, emailed: 2 }, supervisors: { total: 2, emailed: 0 }
    })
    const wrapper = await mountPage()
    await emailButton(wrapper, 'Groups').trigger('click')
    await buttonNamed(wrapper, /^Send$/).trigger('click')
    await flushPromises()
    expect(wrapper.find('.release-results__banner--error').text()).toBe(
      "Emailed 4 people. 1 group wasn't emailed in full; press Email Groups again to retry."
    )
  })

  it('rechecks once marks are released below', async () => {
    const wrapper = await mountPage()
    detailsMock.mockClear()
    wrapper.findComponent(ReleasePage).vm.$emit('changed')
    await flushPromises()
    expect(detailsMock).toHaveBeenCalledOnce()
  })
})
