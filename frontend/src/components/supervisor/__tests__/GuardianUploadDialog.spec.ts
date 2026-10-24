import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import GuardianUploadDialog from '@/components/supervisor/GuardianUploadDialog.vue'
import { uploadGuardianDetails, type GuardianUploadResult } from '@/utils/supervisedStudents'

vi.mock('@/utils/supervisedStudents', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/utils/supervisedStudents')>()),
  uploadGuardianDetails: vi.fn(),
}))
const uploadMock = vi.mocked(uploadGuardianDetails)

const entry = (row: number, name: string) => ({
  row,
  student_id: row,
  student_name: name,
  guardian_first_name: 'Pat',
  guardian_last_name: 'Lee',
  guardian_email: 'pat@example.com',
})

const result = (over: Partial<GuardianUploadResult> = {}): GuardianUploadResult => ({
  checks: { missing_headers: [], header_order: '', unknown_students: [], bad_rows: [], consented: [] },
  creates: [],
  updates: [],
  unchanged: [],
  summary: { creates: 0, updates: 0, unchanged: 0, errors: 0 },
  ...over,
})

type Wrapper = VueWrapper<InstanceType<typeof GuardianUploadDialog>>

const mountDialog = () => mount(GuardianUploadDialog, { global: { stubs: { teleport: true } } })

const button = (wrapper: Wrapper, label: RegExp) =>
  wrapper.findAll('button').find((b) => label.test(b.text().trim()))!

const openDialog = async (wrapper: Wrapper) => {
  await button(wrapper, /Upload Guardian Details/).trigger('click')
}

// Picking a file previews it straight away, so its reply is queued first.
const pickFile = async (wrapper: Wrapper, reply?: GuardianUploadResult | Error) => {
  if (reply instanceof Error) uploadMock.mockRejectedValueOnce(reply)
  else if (reply) uploadMock.mockResolvedValueOnce(reply)
  const input = wrapper.get('input[type="file"]')
  Object.defineProperty(input.element, 'files', {
    value: [new File(['student_email\n'], 'guardians.csv', { type: 'text/csv' })],
    configurable: true,
  })
  await input.trigger('change')
  await flushPromises()
}

const checks = (wrapper: Wrapper) => wrapper.findAll('.bulk-upload__checks li').map((li) => li.text())
const apply = (wrapper: Wrapper) => button(wrapper, /^Apply/)

beforeEach(() => {
  uploadMock.mockReset()
})

describe('GuardianUploadDialog', () => {
  it('opens on its button with nothing picked, and Apply off', async () => {
    const wrapper = mountDialog()
    expect(wrapper.find('[role="dialog"]').exists()).toBe(false)
    await openDialog(wrapper)
    expect(wrapper.get('[role="dialog"]').text()).toContain('No file selected.')
    expect(apply(wrapper).attributes('disabled')).toBeDefined()
  })

  it('previews a picked file and names whose guardians it replaces', async () => {
    const wrapper = mountDialog()
    await openDialog(wrapper)
    await pickFile(
      wrapper,
      result({
        updates: [entry(2, 'Aarav Gupta'), entry(3, 'Mia Chen')],
        creates: [entry(4, 'Sam Ho')],
        summary: { creates: 1, updates: 2, unchanged: 0, errors: 0 },
      }),
    )
    expect(uploadMock).toHaveBeenCalledWith(expect.any(File), true)
    expect(wrapper.text()).toContain('guardians.csv')
    expect(checks(wrapper)).toEqual([
      'Missing Column Header(s): None',
      'Students not on your list: None',
      'Incorrect guardian details: None',
      'Overwriting Existing Records: 2 (Aarav Gupta, Mia Chen)',
      'Writing New Records: 1',
    ])
    expect(apply(wrapper).attributes('disabled')).toBeUndefined()
  })

  it('stops at missing or misordered headers, as the rest was never read', async () => {
    const wrapper = mountDialog()
    await openDialog(wrapper)
    await pickFile(
      wrapper,
      result({
        checks: { missing_headers: ['guardian_email'], header_order: '', unknown_students: [], bad_rows: [], consented: [] },
        summary: { creates: 0, updates: 0, unchanged: 0, errors: 1 },
      }),
    )
    expect(checks(wrapper)).toEqual(['Missing Column Header(s): guardian_email'])
    expect(apply(wrapper).attributes('disabled')).toBeDefined()

    await pickFile(
      wrapper,
      result({
        checks: { missing_headers: [], header_order: 'Columns are out of order.', unknown_students: [], bad_rows: [], consented: [] },
        summary: { creates: 0, updates: 0, unchanged: 0, errors: 1 },
      }),
    )
    expect(checks(wrapper)).toEqual(['Missing Column Header(s): Columns are out of order.'])
  })

  it('lists rows it cannot use, and keeps Apply off while any are wrong', async () => {
    const wrapper = mountDialog()
    await openDialog(wrapper)
    await pickFile(
      wrapper,
      result({
        checks: {
          missing_headers: [],
          header_order: '',
          unknown_students: [{ row: 2, email: 'who@example.com' }],
          bad_rows: [{ row: 3, reason: 'guardian email is not valid' }],
          consented: [{ row: 4, email: 'done@example.com' }],
        },
        summary: { creates: 0, updates: 0, unchanged: 0, errors: 3 },
      }),
    )
    expect(checks(wrapper)).toEqual([
      'Missing Column Header(s): None',
      'Students not on your list: row 2 (who@example.com)',
      'Incorrect guardian details: row 3 (guardian email is not valid)',
      'Permission already given: row 4 (done@example.com)',
    ])
    expect(apply(wrapper).attributes('disabled')).toBeDefined()
  })

  it('says why a preview failed', async () => {
    const wrapper = mountDialog()
    await openDialog(wrapper)
    await pickFile(wrapper, new Error('The file could not be read.'))
    expect(wrapper.get('.bulk-upload__request-error').text()).toBe('Preview failed: The file could not be read.')
    expect(apply(wrapper).attributes('disabled')).toBeDefined()
  })

  it('applies a clean sheet, closes, and says how many it saved', async () => {
    const wrapper = mountDialog()
    await openDialog(wrapper)
    await pickFile(wrapper, result({ creates: [entry(2, 'Sam Ho')], summary: { creates: 1, updates: 0, unchanged: 0, errors: 0 } }))
    uploadMock.mockResolvedValueOnce(result({ saved: 1 }))
    await apply(wrapper).trigger('click')
    await flushPromises()
    expect(uploadMock).toHaveBeenLastCalledWith(expect.any(File), false)
    expect(wrapper.emitted('applied')).toEqual([[1]])
    expect(wrapper.find('[role="dialog"]').exists()).toBe(false)
  })

  it('counts nothing saved when the reply leaves the number out', async () => {
    const wrapper = mountDialog()
    await openDialog(wrapper)
    await pickFile(wrapper, result({ creates: [entry(2, 'Sam Ho')], summary: { creates: 1, updates: 0, unchanged: 0, errors: 0 } }))
    uploadMock.mockResolvedValueOnce(result())
    await apply(wrapper).trigger('click')
    await flushPromises()
    expect(wrapper.emitted('applied')).toEqual([[0]])
  })

  it('stays open and says why when applying fails', async () => {
    const wrapper = mountDialog()
    await openDialog(wrapper)
    await pickFile(wrapper, result({ creates: [entry(2, 'Sam Ho')], summary: { creates: 1, updates: 0, unchanged: 0, errors: 0 } }))
    uploadMock.mockRejectedValueOnce(new Error('A student was removed meanwhile.'))
    await apply(wrapper).trigger('click')
    await flushPromises()
    expect(wrapper.get('.bulk-upload__request-error').text()).toBe('Apply failed: A student was removed meanwhile.')
    expect(wrapper.find('[role="dialog"]').exists()).toBe(true)
    expect(wrapper.emitted('applied')).toBeUndefined()
  })

  it('closes from its close button or the backdrop, and starts afresh next time', async () => {
    const wrapper = mountDialog()
    await openDialog(wrapper)
    await pickFile(wrapper, result())
    await wrapper.get('button[aria-label="Close"]').trigger('click')
    expect(wrapper.find('[role="dialog"]').exists()).toBe(false)

    await openDialog(wrapper)
    expect(wrapper.find('.bulk-upload__checks').exists()).toBe(false)
    await wrapper.get('.bulk-upload__overlay').trigger('click')
    expect(wrapper.find('[role="dialog"]').exists()).toBe(false)
  })

  it('cannot be closed while a preview is running', async () => {
    const wrapper = mountDialog()
    await openDialog(wrapper)
    let finish!: (value: GuardianUploadResult) => void
    uploadMock.mockReturnValueOnce(new Promise((resolve) => (finish = resolve)))
    await pickFile(wrapper)
    expect(wrapper.text()).toContain('Previewing…')
    await wrapper.get('button[aria-label="Close"]').trigger('click')
    expect(wrapper.find('[role="dialog"]').exists()).toBe(true)
    finish(result())
    await flushPromises()
    expect(wrapper.text()).not.toContain('Previewing…')
  })

  it('opens the file picker from Browse, and ignores a change with no file', async () => {
    const wrapper = mountDialog()
    await openDialog(wrapper)
    const input = wrapper.get('input[type="file"]').element as HTMLInputElement
    const click = vi.spyOn(input, 'click')
    await button(wrapper, /^Browse/).trigger('click')
    expect(click).toHaveBeenCalled()

    Object.defineProperty(input, 'files', { value: [], configurable: true })
    await wrapper.get('input[type="file"]').trigger('change')
    expect(uploadMock).not.toHaveBeenCalled()
  })
})
