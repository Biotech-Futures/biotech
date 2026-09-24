import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import GradingSettingsPage from '@/views/grading/GradingSettingsPage.vue'
import {
  downloadCandidateTestRender,
  downloadTemplateTestRender,
  fetchGradingSettings,
  fetchTemplateScan,
  scanTemplateCandidate,
  updateGradingSettings
} from '@/utils/gradingAPI'

const guards = vi.hoisted(() => ({ leave: [] as Array<() => boolean | undefined>[] }))
vi.mock('vue-router', () => ({
  onBeforeRouteLeave: (fn: never) => (guards.leave as unknown as unknown[]).push(fn)
}))

vi.mock('@/utils/gradingAPI', () => ({
  downloadCandidateTestRender: vi.fn(),
  downloadTemplateTestRender: vi.fn(),
  fetchGradingSettings: vi.fn(),
  fetchTemplateScan: vi.fn(),
  scanTemplateCandidate: vi.fn(),
  updateGradingSettings: vi.fn()
}))
const settingsMock = vi.mocked(fetchGradingSettings)
const scanMock = vi.mocked(fetchTemplateScan)
const candidateScanMock = vi.mocked(scanTemplateCandidate)
const updateMock = vi.mocked(updateGradingSettings)
const testStoredMock = vi.mocked(downloadTemplateTestRender)
const testCandidateMock = vi.mocked(downloadCandidateTestRender)

const detail = (over: Record<string, unknown> = {}) => ({
  director_1_name: 'Prof. Alice Adams',
  director_1_signature: '/media/grading/sig1.png',
  director_2_name: '',
  director_2_signature: null,
  marks_summary_template: '/media/grading/marks%20summary.docx',
  certificate_template: null,
  component_weights: {},
  ...over
})

const scan = (present: string[] = [], unknown: string[] = []) => ({
  uploaded: true,
  dialect: 'tokens' as const,
  present,
  unknown
})

const mountPage = async () => {
  const wrapper = mount(GradingSettingsPage)
  await flushPromises()
  return wrapper
}

const buttonNamed = (wrapper: Awaited<ReturnType<typeof mountPage>>, label: RegExp) =>
  wrapper.findAll('button').find((b) => label.test(b.text().trim()))!

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
})

describe('loading', () => {
  it('shows the stored names and file basenames, decoded', async () => {
    const wrapper = await mountPage()
    expect((wrapper.find('input[type="text"]').element as HTMLInputElement).value).toBe(
      'Prof. Alice Adams'
    )
    expect(wrapper.text()).toContain('sig1.png')
    expect(wrapper.text()).toContain('marks summary.docx') // %20 decoded
    expect(wrapper.text()).toContain('No file selected.') // cert template empty
  })

  it('colours the placeholder chips the saved template actually uses', async () => {
    const wrapper = await mountPage()
    const found = wrapper.findAll('code.is-found').map((c) => c.text())
    expect(found).toContain('{{TeamCode}}')
    expect(found).not.toContain('{{SAQTotal}}')
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
    await wrapper.findAll('input[type="text"]')[1]!.setValue('Dr. Bob Brown')
    await buttonNamed(wrapper, /^Update$/).trigger('click')
    await flushPromises()
    expect(updateMock).toHaveBeenCalledWith({
      director_1_name: 'Prof. Alice Adams',
      director_2_name: 'Dr. Bob Brown'
    })
    expect(wrapper.find('.grading-settings__banner--ok').text()).toBe('Settings updated.')
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
    candidateScanMock.mockResolvedValueOnce(scan(['TeamCode', 'SAQTotal']))
    const wrapper = await mountPage()
    await pickFile(wrapper, '.docx', 'draft.docx', 0)
    expect(candidateScanMock).toHaveBeenCalledWith('marks-summary', expect.any(File))
    const found = wrapper.findAll('code.is-found').map((c) => c.text())
    expect(found).toContain('{{SAQTotal}}')
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
    candidateScanMock.mockResolvedValueOnce(scan(['firstName']))
    testStoredMock.mockResolvedValueOnce()
    testCandidateMock.mockResolvedValueOnce()
    const wrapper = await mountPage()

    await buttonNamed(wrapper, /^Test$/).trigger('click')
    await flushPromises()
    expect(testStoredMock).toHaveBeenCalledWith('marks-summary')

    await pickFile(wrapper, '.docx', 'candidate.docx', 1) // certificate slot
    const testButtons = wrapper.findAll('button').filter((b) => /^Test$/.test(b.text().trim()))
    await testButtons[1]!.trigger('click')
    await flushPromises()
    expect(testCandidateMock).toHaveBeenCalledWith('certificate', expect.any(File))
  })

  it('the certificate Test stays off while no template exists at all', async () => {
    const wrapper = await mountPage()
    const testButtons = wrapper.findAll('button').filter((b) => /^Test$/.test(b.text().trim()))
    expect(testButtons[0]!.attributes('disabled')).toBeUndefined() // summary stored
    expect(testButtons[1]!.attributes('disabled')).toBeDefined() // no certificate
  })

  it('Reset drops picked files and re-describes the saved templates', async () => {
    candidateScanMock.mockResolvedValueOnce(scan(['SAQTotal']))
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
