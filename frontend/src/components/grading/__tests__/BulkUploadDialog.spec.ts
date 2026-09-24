import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount, flushPromises, type VueWrapper } from '@vue/test-utils'
import BulkUploadDialog from '@/components/grading/BulkUploadDialog.vue'
import { bulkUploadMarks, type BulkUploadResponse } from '@/utils/gradingAPI'

vi.mock('@/utils/gradingAPI', () => ({
  bulkUploadMarks: vi.fn()
}))
const uploadMock = vi.mocked(bulkUploadMarks)

const cleanChecks = (over: Partial<NonNullable<BulkUploadResponse['checks']>> = {}) => ({
  missing_headers: [],
  bad_group_rows: [],
  bad_marks: [],
  ...over
})

const rowEntry = (row: number, groupId: number, columns = ['mark'], criteriaNo = 1) => ({
  row,
  group_id: groupId,
  criterion_id: 1,
  criteria_no: criteriaNo,
  submission_id: 1,
  mark: '5.00',
  comment: '',
  group_name: `BTF-${groupId}`,
  columns
})

const response = (over: Partial<BulkUploadResponse> = {}): BulkUploadResponse => ({
  creates: [],
  updates: [],
  unchanged: [],
  errors: [],
  checks: cleanChecks(),
  summary: { creates: 0, updates: 0, unchanged: 0, errors: 0 },
  ...over
})

const mountDialog = (code = 'SAQ') =>
  mount(BulkUploadDialog, {
    props: { code },
    global: { stubs: { teleport: true } }
  })

type Wrapper = VueWrapper<InstanceType<typeof BulkUploadDialog>>

const buttonNamed = (wrapper: Wrapper, label: RegExp) =>
  wrapper.findAll('button').find((b) => label.test(b.text().trim()))!

const openDialog = async (wrapper: Wrapper) => {
  await buttonNamed(wrapper, /^Upload marks$/).trigger('click')
}

// Picking a file previews it automatically, so the preview response (when
// given) is queued before the change event fires.
const pickFile = async (wrapper: Wrapper, body?: BulkUploadResponse, name = 'marks.csv') => {
  if (body) uploadMock.mockResolvedValueOnce(body)
  const input = wrapper.find('input[type="file"]')
  Object.defineProperty(input.element, 'files', {
    value: [new File(['group_id,type\n'], name, { type: 'text/csv' })],
    configurable: true
  })
  await input.trigger('change')
  await flushPromises()
}

beforeEach(() => {
  uploadMock.mockReset()
})

describe('opening the dialog', () => {
  it('starts closed, showing only the trigger button', () => {
    const wrapper = mountDialog()
    expect(wrapper.find('[role="dialog"]').exists()).toBe(false)
  })

  it('names the component type in the title, not the raw code', async () => {
    const wrapper = mountDialog('SAQ')
    await openDialog(wrapper)
    expect(wrapper.text()).toContain('Upload marks for SAQs')
  })

  it('mentions the overall_comment column for every component, SAQ included', async () => {
    const saq = mountDialog('SAQ')
    await openDialog(saq)
    expect(saq.text()).toContain('overall_comment')

    const poster = mountDialog('POSTER')
    await openDialog(poster)
    expect(poster.text()).toContain('overall_comment')
  })

  it('reopens clean after closing, with the previous file forgotten', async () => {
    const wrapper = mountDialog()
    await openDialog(wrapper)
    await pickFile(wrapper, response())
    expect(wrapper.text()).toContain('marks.csv')

    await buttonNamed(wrapper, /^×$/).trigger('click')
    await openDialog(wrapper)
    expect(wrapper.text()).toContain('No file selected.')
  })
})

describe('the pick → auto-preview → apply flow', () => {
  it('disables Apply until a file has been previewed', async () => {
    const wrapper = mountDialog()
    await openDialog(wrapper)
    expect(buttonNamed(wrapper, /Apply/).attributes('disabled')).toBeDefined()
  })

  it('shows a Previewing… hint while the dry run is in flight', async () => {
    const wrapper = mountDialog()
    await openDialog(wrapper)
    let resolvePreview!: (body: BulkUploadResponse) => void
    uploadMock.mockImplementationOnce(() => new Promise((resolve) => (resolvePreview = resolve)))
    const input = wrapper.find('input[type="file"]')
    Object.defineProperty(input.element, 'files', {
      value: [new File(['group_id,type\n'], 'marks.csv', { type: 'text/csv' })],
      configurable: true
    })
    await input.trigger('change')
    expect(wrapper.text()).toContain('Previewing…')

    resolvePreview(response())
    await flushPromises()
    expect(wrapper.text()).not.toContain('Previewing…')
  })

  it('previews automatically on pick — one dry run, never a write', async () => {
    const wrapper = mountDialog('SAQ')
    await openDialog(wrapper)
    await pickFile(wrapper, response())
    expect(uploadMock).toHaveBeenCalledTimes(1)
    expect(uploadMock).toHaveBeenCalledWith('SAQ', expect.any(File), true)
    expect(buttonNamed(wrapper, /Apply/).attributes('disabled')).toBeUndefined()
  })

  it('choosing a different file re-previews it, replacing the stale report', async () => {
    const wrapper = mountDialog()
    await openDialog(wrapper)
    await pickFile(
      wrapper,
      response({
        creates: [rowEntry(4, 9), rowEntry(5, 10), rowEntry(6, 11)],
        summary: { creates: 3, updates: 0, unchanged: 0, errors: 0 }
      })
    )
    expect(wrapper.text()).toContain('Writing New Records: 3')

    await pickFile(
      wrapper,
      response({
        errors: [{ row: 2, message: 'non-numeric mark' }],
        summary: { creates: 0, updates: 0, unchanged: 0, errors: 1 }
      }),
      'other.csv'
    )
    expect(wrapper.text()).toContain('other.csv')
    expect(wrapper.text()).not.toContain('Writing New Records: 3')
    expect(buttonNamed(wrapper, /Apply/).attributes('disabled')).toBeDefined()
  })

  it('applies with a real write and reports how much was written', async () => {
    const wrapper = mountDialog('SAQ')
    await openDialog(wrapper)
    await pickFile(
      wrapper,
      response({ summary: { creates: 2, updates: 0, unchanged: 0, errors: 0 } })
    )

    uploadMock.mockResolvedValueOnce(response({ applied: true, written: 3 }))
    await buttonNamed(wrapper, /Apply/).trigger('click')
    await flushPromises()

    expect(uploadMock).toHaveBeenLastCalledWith('SAQ', expect.any(File), false)
    expect(wrapper.emitted('applied')).toEqual([[3]])
    expect(wrapper.find('[role="dialog"]').exists()).toBe(false)
  })
})

describe('the preview report', () => {
  it('shows None for every check on a clean sheet, plus group-based record counts', async () => {
    const wrapper = mountDialog()
    await openDialog(wrapper)
    await pickFile(
      wrapper,
      response({
        // Group 7 overwrites; groups 9 and 10 are new (group 9 spans two
        // criteria rows yet still counts once — groups, not rows).
        creates: [rowEntry(4, 9, ['mark'], 1), rowEntry(5, 9, ['mark'], 2), rowEntry(6, 10)],
        updates: [rowEntry(2, 7)],
        summary: { creates: 3, updates: 1, unchanged: 0, errors: 0 }
      })
    )
    const text = wrapper.text()
    expect(text).toContain('Missing Column Header(s): None')
    expect(text).toContain('Incorrect group details: None')
    expect(text).toContain('Incorrect mark format: None')
    expect(text).toContain('Overwriting Existing Records: 1')
    expect(text).toContain('Writing New Records: 2')
  })

  it('counts overwritten groups and folds their cells into one listing each', async () => {
    const wrapper = mountDialog()
    await openDialog(wrapper)
    await pickFile(
      wrapper,
      response({
        // BTF-7 overwrites cells on two criteria -> one listing; the
        // count says 2 because two groups are touched.
        updates: [
          rowEntry(4, 7, ['mark'], 3),
          rowEntry(5, 7, ['mark', 'comment'], 4),
          rowEntry(8, 9, ['mark'], 1)
        ],
        summary: { creates: 0, updates: 3, unchanged: 0, errors: 0 }
      })
    )
    expect(wrapper.text()).toContain(
      'Overwriting Existing Records: 2 (BTF-7 [3_mark, 4_mark, 4_comment], BTF-9 [1_mark])'
    )
  })

  it('a missing header stops the report there, hiding checks that never ran', async () => {
    const wrapper = mountDialog()
    await openDialog(wrapper)
    await pickFile(
      wrapper,
      response({
        checks: cleanChecks({ missing_headers: ['comment'] }),
        errors: [{ row: 1, message: 'missing header comment' }],
        summary: { creates: 0, updates: 0, unchanged: 0, errors: 1 }
      })
    )
    const text = wrapper.text()
    expect(text).toContain('Missing Column Header(s): comment')
    expect(text).not.toContain('Incorrect group details')
  })

  it('wide-shape sheets (non SAQ) keep the Type check line', async () => {
    const wrapper = mountDialog('POSTER')
    await openDialog(wrapper)
    await pickFile(
      wrapper,
      response({
        checks: cleanChecks({ expected_type: 'Poster', found_type: 'SAQs', type_ok: false }),
        errors: [{ row: 2, message: 'wrong type' }],
        summary: { creates: 0, updates: 0, unchanged: 0, errors: 1 }
      })
    )
    const text = wrapper.text()
    expect(text).toContain('SAQs (should be Poster)')
    expect(text).not.toContain('Incorrect group details')
  })

  it('bad group rows are named with their reason and hide the mark check', async () => {
    const wrapper = mountDialog()
    await openDialog(wrapper)
    await pickFile(
      wrapper,
      response({
        checks: cleanChecks({ bad_group_rows: [{ row: 2, reason: 'name should be BTF-1' }] }),
        errors: [{ row: 2, message: 'bad group' }],
        summary: { creates: 0, updates: 0, unchanged: 0, errors: 1 }
      })
    )
    const text = wrapper.text()
    expect(text).toContain('row 2 (name should be BTF-1)')
    expect(text).not.toContain('Incorrect mark format')
  })

  it('any error keeps Apply disabled, so a broken sheet cannot be committed', async () => {
    const wrapper = mountDialog()
    await openDialog(wrapper)
    await pickFile(
      wrapper,
      response({
        errors: [{ row: 2, message: 'non-numeric mark' }],
        summary: { creates: 0, updates: 0, unchanged: 0, errors: 1 }
      })
    )
    expect(buttonNamed(wrapper, /Apply/).attributes('disabled')).toBeDefined()
  })
})

describe('request failures', () => {
  it('a failed auto-preview is reported in the dialog, which stays open', async () => {
    const wrapper = mountDialog()
    await openDialog(wrapper)
    uploadMock.mockRejectedValueOnce(new Error('server unavailable'))
    await pickFile(wrapper)
    expect(wrapper.text()).toContain('Preview failed:')
    expect(wrapper.find('[role="dialog"]').exists()).toBe(true)
  })

  it('re-picking a file after a failure previews again', async () => {
    const wrapper = mountDialog()
    await openDialog(wrapper)
    uploadMock.mockRejectedValueOnce(new Error('server unavailable'))
    await pickFile(wrapper)
    expect(wrapper.text()).toContain('Preview failed:')

    await pickFile(wrapper, response())
    expect(wrapper.text()).not.toContain('Preview failed:')
    expect(buttonNamed(wrapper, /Apply/).attributes('disabled')).toBeUndefined()
  })

  it('a failed apply keeps the dialog open with the preview intact', async () => {
    const wrapper = mountDialog()
    await openDialog(wrapper)
    await pickFile(
      wrapper,
      response({ summary: { creates: 1, updates: 0, unchanged: 0, errors: 0 } })
    )

    uploadMock.mockRejectedValueOnce(new Error('write refused'))
    await buttonNamed(wrapper, /Apply/).trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('Apply failed:')
    expect(wrapper.find('[role="dialog"]').exists()).toBe(true)
    expect(wrapper.emitted('applied')).toBeUndefined()
  })
})
