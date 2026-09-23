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
  expected_type: 'SAQs',
  found_type: 'SAQs',
  type_ok: true,
  bad_group_rows: [],
  bad_marks: [],
  ...over
})

const rowEntry = (row: number, groupId: number) => ({
  row,
  group_id: groupId,
  criterion_id: 1,
  submission_id: 1,
  mark: '5.00',
  comment: ''
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

const pickFile = async (wrapper: Wrapper, name = 'marks.csv') => {
  const input = wrapper.find('input[type="file"]')
  Object.defineProperty(input.element, 'files', {
    value: [new File(['group_id,type\n'], name, { type: 'text/csv' })],
    configurable: true
  })
  await input.trigger('change')
}

const runPreview = async (wrapper: Wrapper, body: BulkUploadResponse) => {
  uploadMock.mockResolvedValueOnce(body)
  await buttonNamed(wrapper, /Preview/).trigger('click')
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
    await pickFile(wrapper)
    expect(wrapper.text()).toContain('marks.csv')

    await buttonNamed(wrapper, /^×$/).trigger('click')
    await openDialog(wrapper)
    expect(wrapper.text()).toContain('No file selected.')
  })
})

describe('the two-step flow', () => {
  it('offers Preview only once a file is chosen, and Apply only after a preview', async () => {
    const wrapper = mountDialog()
    await openDialog(wrapper)
    expect(buttonNamed(wrapper, /Preview/).attributes('disabled')).toBeDefined()
    expect(buttonNamed(wrapper, /Apply/).attributes('disabled')).toBeDefined()

    await pickFile(wrapper)
    expect(buttonNamed(wrapper, /Preview/).attributes('disabled')).toBeUndefined()
    expect(buttonNamed(wrapper, /Apply/).attributes('disabled')).toBeDefined()
  })

  it('previews as a dry run, never a write', async () => {
    const wrapper = mountDialog('SAQ')
    await openDialog(wrapper)
    await pickFile(wrapper)
    await runPreview(wrapper, response())
    expect(uploadMock).toHaveBeenCalledWith('SAQ', expect.any(File), true)
  })

  it('choosing a different file discards the stale preview', async () => {
    const wrapper = mountDialog()
    await openDialog(wrapper)
    await pickFile(wrapper)
    await runPreview(wrapper, response({ summary: { creates: 3, updates: 0, unchanged: 0, errors: 0 } }))
    expect(wrapper.text()).toContain('Writing New Records')

    await pickFile(wrapper, 'other.csv')
    expect(wrapper.text()).not.toContain('Writing New Records')
    expect(buttonNamed(wrapper, /Apply/).attributes('disabled')).toBeDefined()
  })

  it('applies with a real write and reports how much was written', async () => {
    const wrapper = mountDialog('SAQ')
    await openDialog(wrapper)
    await pickFile(wrapper)
    await runPreview(wrapper, response({ summary: { creates: 2, updates: 0, unchanged: 0, errors: 0 } }))

    uploadMock.mockResolvedValueOnce(response({ applied: true, written: 3 }))
    await buttonNamed(wrapper, /Apply/).trigger('click')
    await flushPromises()

    expect(uploadMock).toHaveBeenLastCalledWith('SAQ', expect.any(File), false)
    expect(wrapper.emitted('applied')).toEqual([[3]])
    expect(wrapper.find('[role="dialog"]').exists()).toBe(false)
  })
})

describe('the preview report', () => {
  it('shows None for every check on a clean sheet, plus both record counts', async () => {
    const wrapper = mountDialog()
    await openDialog(wrapper)
    await pickFile(wrapper)
    await runPreview(
      wrapper,
      response({
        updates: [rowEntry(2, 7)],
        summary: { creates: 4, updates: 1, unchanged: 0, errors: 0 }
      })
    )
    const text = wrapper.text()
    expect(text).toContain('Missing Column Header(s): None')
    expect(text).toContain('Type: SAQs')
    expect(text).toContain('Incorrect group details: None')
    expect(text).toContain('Incorrect mark format: None')
    expect(text).toContain('Overwriting Existing Records: 1')
    expect(text).toContain('Writing New Records: 4')
  })

  it('names each overwritten sheet row with its group, once, in order', async () => {
    const wrapper = mountDialog()
    await openDialog(wrapper)
    await pickFile(wrapper)
    await runPreview(
      wrapper,
      response({
        // Two criteria on row 2 → one listing; rows arrive unsorted.
        updates: [rowEntry(3, 4), rowEntry(2, 7), rowEntry(2, 7)],
        summary: { creates: 0, updates: 3, unchanged: 0, errors: 0 }
      })
    )
    expect(wrapper.text()).toContain('(row 2 [group_id 7], row 3 [group_id 4])')
  })

  it('a missing header stops the report there, hiding checks that never ran', async () => {
    const wrapper = mountDialog()
    await openDialog(wrapper)
    await pickFile(wrapper)
    await runPreview(
      wrapper,
      response({
        checks: cleanChecks({ missing_headers: ['r1_comment'], type_ok: false, found_type: null }),
        errors: [{ row: 1, message: 'missing header r1_comment' }],
        summary: { creates: 0, updates: 0, unchanged: 0, errors: 1 }
      })
    )
    const text = wrapper.text()
    expect(text).toContain('Missing Column Header(s): r1_comment')
    expect(text).not.toContain('Type:')
    expect(text).not.toContain('Incorrect group details')
  })

  it('a wrong type names both what it found and what it expected', async () => {
    const wrapper = mountDialog()
    await openDialog(wrapper)
    await pickFile(wrapper)
    await runPreview(
      wrapper,
      response({
        checks: cleanChecks({ type_ok: false, found_type: 'SAQ' }),
        errors: [{ row: 2, message: 'wrong type' }],
        summary: { creates: 0, updates: 0, unchanged: 0, errors: 1 }
      })
    )
    const text = wrapper.text()
    expect(text).toContain('SAQ (should be SAQs)')
    expect(text).not.toContain('Incorrect group details')
  })

  it('bad group rows are named with their reason and hide the mark check', async () => {
    const wrapper = mountDialog()
    await openDialog(wrapper)
    await pickFile(wrapper)
    await runPreview(
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
    await pickFile(wrapper)
    await runPreview(
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
  it('a failed preview is reported in the dialog, which stays open', async () => {
    const wrapper = mountDialog()
    await openDialog(wrapper)
    await pickFile(wrapper)
    uploadMock.mockRejectedValueOnce(new Error('server unavailable'))
    await buttonNamed(wrapper, /Preview/).trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('Preview failed:')
    expect(wrapper.find('[role="dialog"]').exists()).toBe(true)
  })

  it('a failed apply keeps the dialog open with the preview intact', async () => {
    const wrapper = mountDialog()
    await openDialog(wrapper)
    await pickFile(wrapper)
    await runPreview(wrapper, response({ summary: { creates: 1, updates: 0, unchanged: 0, errors: 0 } }))

    uploadMock.mockRejectedValueOnce(new Error('write refused'))
    await buttonNamed(wrapper, /Apply/).trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('Apply failed:')
    expect(wrapper.find('[role="dialog"]').exists()).toBe(true)
    expect(wrapper.emitted('applied')).toBeUndefined()
  })
})
