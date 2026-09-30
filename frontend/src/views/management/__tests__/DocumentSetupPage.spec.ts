import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import DocumentSetupPage from '@/views/management/DocumentSetupPage.vue'
import {
  downloadCandidateTestRender,
  downloadSavedTemplate,
  downloadTemplateTestRender,
  fetchGradingSettings,
  fetchTemplateScan,
  fetchTemplateTestPeople,
  scanTemplateCandidate,
  updateGradingSettings
} from '@/utils/managementAPI'

const guards = vi.hoisted(() => ({ leave: [] as Array<() => boolean | undefined>[] }))
vi.mock('vue-router', () => ({
  onBeforeRouteLeave: (fn: never) => (guards.leave as unknown as unknown[]).push(fn)
}))

vi.mock('@/utils/managementAPI', () => ({
  downloadCandidateTestRender: vi.fn(),
  downloadSavedTemplate: vi.fn(),
  downloadTemplateTestRender: vi.fn(),
  fetchGradingSettings: vi.fn(),
  fetchTemplateScan: vi.fn(),
  fetchTemplateTestPeople: vi.fn(),
  scanTemplateCandidate: vi.fn(),
  updateGradingSettings: vi.fn()
}))
const settingsMock = vi.mocked(fetchGradingSettings)
const scanMock = vi.mocked(fetchTemplateScan)
const candidateScanMock = vi.mocked(scanTemplateCandidate)
const updateMock = vi.mocked(updateGradingSettings)
const testStoredMock = vi.mocked(downloadTemplateTestRender)
const testCandidateMock = vi.mocked(downloadCandidateTestRender)
const savedTemplateMock = vi.mocked(downloadSavedTemplate)
const peopleMock = vi.mocked(fetchTemplateTestPeople)

// This year's students, or mentors for the mentor certificate.
const PEOPLE = {
  'marks-summary': [
    { value: '1:11', label: '(BTF1) Amy Chen' },
    { value: '2:12', label: '(BTF2) Ben Lee' }
  ],
  certificate: [
    { value: '1:11', label: '(BTF1) Amy Chen' },
    { value: '2:12', label: '(BTF2) Ben Lee' }
  ],
  'mentor-certificate': [{ value: '1:21', label: '(BTF1) Mo Mentor' }]
}

const detail = (over: Record<string, unknown> = {}) => ({
  director_1_name: 'Prof. Alice Adams',
  director_1_position: 'Chair',
  director_1_signature: '/media/grading/sig1.png',
  director_2_name: '',
  director_2_position: '',
  director_2_signature: null,
  marks_summary_template: '/media/grading/marks%20summary.docx',
  certificate_template: null,
  mentor_certificate_template: null,
  component_weights: {},
  ...over
})

const scan = (present: string[] = [], unknown: string[] = []) => ({
  uploaded: true,
  present,
  unknown
})

const mountPage = async () => {
  const wrapper = mount(DocumentSetupPage)
  await flushPromises()
  return wrapper
}

const buttonNamed = (wrapper: Awaited<ReturnType<typeof mountPage>>, label: RegExp) =>
  wrapper.findAll('button').find((b) => label.test(b.text().trim()))!

// The text box under a field label such as "Director 2 Name".
const fieldNamed = (wrapper: Awaited<ReturnType<typeof mountPage>>, label: string) =>
  wrapper
    .findAll('label.grading-settings__field')
    .find((l) => l.find('span').text() === label)!
    .find('input')

const pickFile = async (
  wrapper: Awaited<ReturnType<typeof mountPage>>,
  accept: string,
  name: string,
  index = 0
) => {
  const input = wrapper.findAll(`input[type="file"][accept="${accept}"]`)[index]!
  Object.defineProperty(input.element, 'files', {
    value: [new File(['x'], name)],
    configurable: true
  })
  await input.trigger('change')
  await flushPromises()
}

beforeEach(() => {
  ;(guards.leave as unknown as unknown[]).length = 0
  settingsMock.mockReset().mockResolvedValue(detail())
  scanMock.mockReset().mockResolvedValue(scan(['TeamCode']))
  candidateScanMock.mockReset()
  updateMock.mockReset()
  testStoredMock.mockReset()
  testCandidateMock.mockReset()
  savedTemplateMock.mockReset()
  peopleMock.mockReset().mockImplementation(async (kind) => ({ options: PEOPLE[kind] }))
})

describe('loading', () => {
  it('shows the stored names, positions and file basenames, decoded', async () => {
    const wrapper = await mountPage()
    expect((fieldNamed(wrapper, 'Director 1 Name').element as HTMLInputElement).value).toBe(
      'Prof. Alice Adams'
    )
    expect((fieldNamed(wrapper, 'Director 1 Position').element as HTMLInputElement).value).toBe(
      'Chair'
    )
    expect(wrapper.text()).toContain('sig1.png')
    expect(wrapper.text()).toContain('marks summary.docx') // %20 decoded
    expect(wrapper.text()).toContain('No file selected.') // cert template empty
  })

  it('colours the placeholder chips the saved template actually uses', async () => {
    const wrapper = await mountPage()
    const found = wrapper.findAll('code.is-found').map((c) => c.text())
    expect(found).toContain('{{TeamCode}}')
    expect(found).not.toContain('{{SMTotal}}')
  })

  it('lists stray placeholders that would render blank', async () => {
    scanMock.mockResolvedValue(scan(['TeamCode'], ['Typoed']))
    const wrapper = await mountPage()
    expect(wrapper.find('.grading-settings__unknown').text()).toContain('Typoed')
  })

  it('offers a retry when settings fail to load', async () => {
    settingsMock.mockRejectedValueOnce(new Error('backend down'))
    const wrapper = await mountPage()
    expect(wrapper.text()).toContain('Failed to load settings.')
    settingsMock.mockResolvedValueOnce(detail())
    await buttonNamed(wrapper, /Try again/).trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('Document Setup')
  })
})

describe('saving', () => {
  it('stays disabled until something actually differs', async () => {
    const wrapper = await mountPage()
    expect(buttonNamed(wrapper, /^Update$/).attributes('disabled')).toBeDefined()
    await wrapper.find('input[type="text"]').setValue('Prof. Alicia Adams')
    expect(buttonNamed(wrapper, /^Update$/).attributes('disabled')).toBeUndefined()
    // Retyping the stored value counts as clean again.
    await wrapper.find('input[type="text"]').setValue('Prof. Alice Adams')
    expect(buttonNamed(wrapper, /^Update$/).attributes('disabled')).toBeDefined()
  })

  it('name-only edits go as plain JSON', async () => {
    updateMock.mockResolvedValueOnce(detail({ director_2_name: 'Dr. Bob Brown' }))
    const wrapper = await mountPage()
    await fieldNamed(wrapper, 'Director 2 Name').setValue('Dr. Bob Brown')
    await buttonNamed(wrapper, /^Update$/).trigger('click')
    await flushPromises()
    expect(updateMock).toHaveBeenCalledWith({
      director_1_name: 'Prof. Alice Adams',
      director_1_position: 'Chair',
      director_2_name: 'Dr. Bob Brown',
      director_2_position: ''
    })
    expect(wrapper.find('.grading-settings__banner--ok').text()).toBe('Files updated.')
  })

  it("a changed detail shows that director's save hint, and only theirs", async () => {
    const wrapper = await mountPage()
    // The hint sits under the director's signature row, at the end of their fields.
    const hintUnder = (director: 1 | 2) =>
      wrapper
        .findAll('div.grading-settings__field')
        .find((f) => f.find('span').text() === `Director ${director} Signature`)!
        .find('.grading-settings__save-hint')
    const detailsHint = 'Click Update to save details'
    expect(hintUnder(1).exists()).toBe(false)
    expect(hintUnder(2).exists()).toBe(false)

    await fieldNamed(wrapper, 'Director 2 Name').setValue('Dr. Bob Brown')
    expect(hintUnder(2).text()).toBe(detailsHint)
    expect(hintUnder(1).exists()).toBe(false)

    await fieldNamed(wrapper, 'Director 2 Name').setValue('') // back to the saved value
    expect(hintUnder(2).exists()).toBe(false)

    await fieldNamed(wrapper, 'Director 1 Position').setValue('Co-Chair')
    expect(hintUnder(1).text()).toBe(detailsHint)
    await fieldNamed(wrapper, 'Director 1 Position').setValue('Chair')
    expect(hintUnder(1).exists()).toBe(false)

    await pickFile(wrapper, 'image/*', 'new-sig.png', 1)
    expect(hintUnder(2).text()).toBe(detailsHint)
    expect(hintUnder(1).exists()).toBe(false)
  })

  it('a position edit enables Update and is saved', async () => {
    updateMock.mockResolvedValueOnce(detail({ director_2_position: 'Co-Chair' }))
    const wrapper = await mountPage()
    expect(buttonNamed(wrapper, /^Update$/).attributes('disabled')).toBeDefined()
    await fieldNamed(wrapper, 'Director 2 Position').setValue('Co-Chair')
    expect(buttonNamed(wrapper, /^Update$/).attributes('disabled')).toBeUndefined()
    await buttonNamed(wrapper, /^Update$/).trigger('click')
    await flushPromises()
    expect(updateMock).toHaveBeenCalledWith(
      expect.objectContaining({ director_2_position: 'Co-Chair' })
    )
    // Saved and shown back: nothing left to update.
    expect(buttonNamed(wrapper, /^Update$/).attributes('disabled')).toBeDefined()
  })

  it('any picked file switches the save to multipart with every field aboard', async () => {
    candidateScanMock.mockResolvedValueOnce(scan(['TeamCode']))
    updateMock.mockResolvedValueOnce(detail())
    const wrapper = await mountPage()
    await pickFile(wrapper, '.docx', 'new-summary.docx', 0)
    await buttonNamed(wrapper, /^Update$/).trigger('click')
    await flushPromises()
    const body = updateMock.mock.calls[0]![0] as FormData
    expect(body).toBeInstanceOf(FormData)
    expect((body.get('marks_summary_template') as File).name).toBe('new-summary.docx')
    expect(body.get('director_1_name')).toBe('Prof. Alice Adams')
    expect(body.get('director_1_position')).toBe('Chair')
    // Save clears the picker and re-describes the saved template.
    expect(wrapper.text()).not.toContain('new-summary.docx')
  })

  it('a refused save is reported', async () => {
    updateMock.mockRejectedValueOnce(new Error('not a valid docx'))
    const wrapper = await mountPage()
    await wrapper.find('input[type="text"]').setValue('Changed')
    await buttonNamed(wrapper, /^Update$/).trigger('click')
    await flushPromises()
    expect(wrapper.find('.grading-settings__banner--error').text()).toContain('not a valid docx')
  })
})

describe('template picking and testing', () => {
  it('scanning a picked file recolours the chips without saving anything', async () => {
    candidateScanMock.mockResolvedValueOnce(scan(['TeamCode', 'SMTotal']))
    const wrapper = await mountPage()
    await pickFile(wrapper, '.docx', 'draft.docx', 0)
    expect(candidateScanMock).toHaveBeenCalledWith('marks-summary', expect.any(File))
    const found = wrapper.findAll('code.is-found').map((c) => c.text())
    expect(found).toContain('{{SMTotal}}')
    expect(wrapper.text()).toContain('selected file')
    expect(updateMock).not.toHaveBeenCalled()
  })

  it('an unreadable pick is dropped so Save can never send it', async () => {
    candidateScanMock.mockRejectedValueOnce(new Error('cannot open file'))
    const wrapper = await mountPage()
    await pickFile(wrapper, '.docx', 'broken.docx', 0)
    expect(wrapper.find('.grading-settings__banner--error').text()).toContain(
      'Marks summary template: cannot open file'
    )
    expect(wrapper.text()).not.toContain('broken.docx')
  })

  it('Test renders the picked candidate when one is selected, else the saved template', async () => {
    candidateScanMock.mockResolvedValueOnce(scan(['FirstName']))
    testStoredMock.mockResolvedValueOnce()
    testCandidateMock.mockResolvedValueOnce()
    const wrapper = await mountPage()

    await buttonNamed(wrapper, /^Test$/).trigger('click')
    await flushPromises()
    expect(testStoredMock).toHaveBeenCalledWith('marks-summary', undefined)

    await pickFile(wrapper, '.docx', 'candidate.docx', 1) // certificate slot
    const testButtons = wrapper.findAll('button').filter((b) => /^Test$/.test(b.text().trim()))
    await testButtons[1]!.trigger('click')
    await flushPromises()
    expect(testCandidateMock).toHaveBeenCalledWith('certificate', expect.any(File), undefined)
  })

  it('each Test is followed by Test Student or Test Mentor and its dropdown', async () => {
    const wrapper = await mountPage()
    const rows = wrapper.findAll('.grading-settings__test-row')
    expect(rows.map((r) => r.findAll('button').map((b) => b.text().trim()))).toEqual([
      ['Test', 'Test Student'],
      ['Test', 'Test Student'],
      ['Test', 'Test Mentor']
    ])
    const options = (i: number) => rows[i]!.findAll('option').map((o) => o.text())
    expect(options(0)).toEqual(['(BTF1) Amy Chen', '(BTF2) Ben Lee'])
    expect(options(1)).toEqual(['(BTF1) Amy Chen', '(BTF2) Ben Lee'])
    expect(options(2)).toEqual(['(BTF1) Mo Mentor'])
    expect(peopleMock).toHaveBeenCalledWith('mentor-certificate')
  })

  it('Test Student renders the chosen student with the saved template', async () => {
    testStoredMock.mockResolvedValueOnce()
    const wrapper = await mountPage()
    const row = wrapper.findAll('.grading-settings__test-row')[0]!
    await row.find('select').setValue('2:12')
    await buttonNamed(wrapper, /^Test Student$/).trigger('click')
    await flushPromises()
    expect(testStoredMock).toHaveBeenCalledWith('marks-summary', '2:12')
  })

  it('Test Mentor renders a picked file with the chosen mentor', async () => {
    candidateScanMock.mockResolvedValueOnce(scan(['Name']))
    testCandidateMock.mockResolvedValueOnce()
    const wrapper = await mountPage()
    await pickFile(wrapper, '.docx', 'BTF_Mentor.docx', 2)
    await buttonNamed(wrapper, /^Test Mentor$/).trigger('click')
    await flushPromises()
    expect(testCandidateMock).toHaveBeenCalledWith('mentor-certificate', expect.any(File), '1:21')
  })

  it('Test Student stays off while nobody is on the list or no template exists', async () => {
    peopleMock.mockImplementation(async (kind) => ({
      options: kind === 'marks-summary' ? [] : PEOPLE[kind]
    }))
    const wrapper = await mountPage()
    const rows = wrapper.findAll('.grading-settings__test-row')
    // Nobody yet: the dropdown says so and both it and the button are off.
    expect(rows[0]!.find('select').text()).toBe('Nobody yet')
    expect(rows[0]!.find('select').attributes('disabled')).toBeDefined()
    expect(rows[0]!.findAll('button')[1]!.attributes('disabled')).toBeDefined()
    // People, but no certificate template saved or picked.
    expect(rows[1]!.findAll('button')[1]!.attributes('disabled')).toBeDefined()
  })

  it('Download Current Template sits above Browse and fetches the saved file', async () => {
    savedTemplateMock.mockResolvedValueOnce()
    const wrapper = await mountPage()
    const field = wrapper.findAll('.grading-settings__template .grading-settings__field')[0]!
    const order = field.findAll('button').map((b) => b.text().trim())
    expect(order).toEqual(['Download Current Template', 'Browse…'])

    // Even with a new file picked, it's the saved one that downloads.
    candidateScanMock.mockResolvedValueOnce(scan([]))
    await pickFile(wrapper, '.docx', 'draft.docx', 0)
    await field.find('.grading-settings__download').trigger('click')
    await flushPromises()
    expect(savedTemplateMock).toHaveBeenCalledWith('marks-summary')
  })

  it('names the three templates', async () => {
    const wrapper = await mountPage()
    const labels = wrapper
      .findAll('.grading-settings__template .grading-settings__field > span')
      .map((s) => s.text())
    expect(labels).toEqual([
      'Marks summary template (.docx)',
      'Student Certificate template (.docx)',
      'Mentor Certificate template (.docx)'
    ])
  })

  it('the Student Certificate template names the student with {{Name}}', async () => {
    const wrapper = await mountPage()
    const student = wrapper.findAll('.grading-settings__template')[1]!
    const chips = student.findAll('.grading-settings__tokens code').map((c) => c.text())
    expect(chips.slice(0, 3)).toEqual(['{{Year}}', '{{Name}}', '{{ProjectTitle}}'])
    expect(chips).not.toContain('{{FirstName}}')
    expect(chips).not.toContain('{{LastName}}')
  })

  it('the Mentor Certificate template lists its variables, addressed by {{Name}}', async () => {
    scanMock.mockImplementation(async (kind) =>
      kind === 'mentor-certificate' ? scan(['Name', 'Year'], ['FirstName']) : scan([])
    )
    const wrapper = await mountPage()
    expect(scanMock).toHaveBeenCalledWith('mentor-certificate')
    const mentor = wrapper.findAll('.grading-settings__template')[2]!
    const chips = mentor.findAll('.grading-settings__tokens code')
    expect(chips.map((c) => c.text())).toEqual([
      '{{Year}}',
      '{{Name}}',
      '{{ProjectTitle}}',
      '{{Date}}',
      '{{Director1Signature}}',
      '{{Director2Signature}}',
      '{{Director1Name}}',
      '{{Director2Name}}',
      '{{Director1Position}}',
      '{{Director2Position}}'
    ])
    expect(chips.filter((c) => c.classes('is-found')).map((c) => c.text())).toEqual(['{{Year}}', '{{Name}}'])
    expect(mentor.find('.grading-settings__unknown').text()).toContain('FirstName')
  })

  it('a picked Mentor Certificate template is checked, tested and saved like the others', async () => {
    candidateScanMock.mockResolvedValueOnce(scan(['Name']))
    testCandidateMock.mockResolvedValueOnce()
    updateMock.mockResolvedValueOnce(detail({ mentor_certificate_template: 'grading/templates/ab12/BTF_Mentor.docx' }))
    const wrapper = await mountPage()
    await pickFile(wrapper, '.docx', 'BTF_Mentor.docx', 2)
    expect(candidateScanMock).toHaveBeenCalledWith('mentor-certificate', expect.any(File))
    const mentor = wrapper.findAll('.grading-settings__template')[2]!
    expect(mentor.find('.grading-settings__file-name').text()).toBe('BTF_Mentor.docx')

    await mentor.findAll('button').find((b) => b.text().trim() === 'Test')!.trigger('click')
    await flushPromises()
    expect(testCandidateMock).toHaveBeenCalledWith('mentor-certificate', expect.any(File), undefined)

    await buttonNamed(wrapper, /^Update$/).trigger('click')
    await flushPromises()
    const body = updateMock.mock.calls[0]![0] as FormData
    expect((body.get('mentor_certificate_template') as File).name).toBe('BTF_Mentor.docx')
    // Saved: its name shows beside Browse, and the current one can be downloaded.
    expect(mentor.find('.grading-settings__file-name').text()).toBe('BTF_Mentor.docx')
    savedTemplateMock.mockResolvedValueOnce()
    await mentor.find('.grading-settings__download').trigger('click')
    await flushPromises()
    expect(savedTemplateMock).toHaveBeenCalledWith('mentor-certificate')
  })

  it('Download Current Template stays off while nothing is saved', async () => {
    const wrapper = await mountPage()
    const buttons = wrapper.findAll('.grading-settings__download')
    expect(buttons[0]!.attributes('disabled')).toBeUndefined() // summary saved
    expect(buttons[1]!.attributes('disabled')).toBeDefined() // no certificate
  })

  it('a failed download is reported', async () => {
    savedTemplateMock.mockRejectedValueOnce(new Error('No template uploaded yet.'))
    const wrapper = await mountPage()
    await wrapper.findAll('.grading-settings__download')[0]!.trigger('click')
    await flushPromises()
    expect(wrapper.find('.grading-settings__banner--error').text()).toContain('No template uploaded yet.')
  })

  it('the certificate Test stays off while no template exists at all', async () => {
    const wrapper = await mountPage()
    const testButtons = wrapper.findAll('button').filter((b) => /^Test$/.test(b.text().trim()))
    expect(testButtons[0]!.attributes('disabled')).toBeUndefined() // summary stored
    expect(testButtons[1]!.attributes('disabled')).toBeDefined() // no certificate
  })

  it('Reset drops picked files and re-describes the saved templates', async () => {
    candidateScanMock.mockResolvedValueOnce(scan(['SMTotal']))
    const wrapper = await mountPage()
    await pickFile(wrapper, '.docx', 'draft.docx', 0)
    expect(wrapper.text()).toContain('draft.docx')

    scanMock.mockClear()
    await buttonNamed(wrapper, /^Reset$/).trigger('click')
    await flushPromises()
    expect(wrapper.text()).not.toContain('draft.docx')
    expect(scanMock).toHaveBeenCalled() // chips describe the stored template again
  })
})

describe('leaving with unsaved changes', () => {
  it('asks only when something differs', async () => {
    const wrapper = await mountPage()
    const guard = (guards.leave as unknown as Array<() => boolean>)[0]!
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false)
    expect(guard()).toBe(true)
    expect(confirm).not.toHaveBeenCalled()

    await wrapper.find('input[type="text"]').setValue('Changed')
    expect(guard()).toBe(false)
    expect(confirm).toHaveBeenCalledOnce()
    confirm.mockRestore()
    wrapper.unmount()
  })
})
