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

const rowEntry = (row: number, groupId: number, columns = ['r1_mark']) => ({
  row,
  group_id: groupId,
  criterion_id: 1,
  submission_id: 1,
  mark: '5.00',
  comment: '',
  group_name: `BTF-${groupId}`,
  columns
})

const overallComment = (row: number, groupId: number, comment: string, oldComment: string) => ({
  row,
  group_id: groupId,
  group_name: `BTF-${groupId}`,
  component_id: 1,
  comment,
  old_comment: oldComment
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

  it('describes the one-row-per-group sheet, with answers and categories for SAQ only', async () => {
    const saq = mountDialog('SAQ')
    await openDialog(saq)
    const saqText = saq.text()
    expect(saqText).toContain('one row per group')
    expect(saqText).toContain('q1')
    expect(saqText).toContain('r1_mark')
    expect(saqText).toContain('product_category')
    expect(saqText).toContain('category_of_solution')
    expect(saqText).toContain('SAQs')
    expect(saqText).not.toContain('criteria_no')
    // The comma rule sits just before the closing "Extra columns" line.
    expect(saqText).toMatch(
      /Items in product_category are split on commas\s*Extra columns and rows are ignored\./
    )

    const poster = mountDialog('POSTER')
    await openDialog(poster)
    expect(poster.text()).not.toContain('q1')
    expect(poster.text()).not.toContain('product_category')
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

  it('applies with a real write and reports overwritten and new groups', async () => {
    const wrapper = mountDialog('SAQ')
    await openDialog(wrapper)
    await pickFile(
      wrapper,
      response({ summary: { creates: 2, updates: 0, unchanged: 0, errors: 0 } })
    )

    // Counted from the apply response, the diff re-parsed at commit time:
    // BTF-7 overwrites a grade, BTF-8 only replaces its overall comment,
    // BTF-9 is new.
    uploadMock.mockResolvedValueOnce(
      response({
        applied: true,
        written: 4,
        updates: [rowEntry(2, 7)],
        creates: [rowEntry(4, 9, ['r1_mark']), rowEntry(5, 9, ['r2_mark'])],
        overall_comments: [overallComment(3, 8, 'New', 'Old')]
      })
    )
    await buttonNamed(wrapper, /Apply/).trigger('click')
    await flushPromises()

    expect(uploadMock).toHaveBeenLastCalledWith('SAQ', expect.any(File), false)
    expect(wrapper.emitted('applied')).toEqual([[{ overwritten: 2, created: 1 }]])
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
        creates: [rowEntry(4, 9, ['r1_mark']), rowEntry(5, 9, ['r2_mark']), rowEntry(6, 10)],
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

  it('an untouched re-upload reports zero records of both kinds', async () => {
    const wrapper = mountDialog()
    await openDialog(wrapper)
    await pickFile(
      wrapper,
      response({
        unchanged: [rowEntry(2, 7), rowEntry(3, 8)],
        summary: { creates: 0, updates: 0, unchanged: 2, errors: 0 }
      })
    )
    const text = wrapper.text()
    expect(text).toContain('Overwriting Existing Records: 0')
    expect(text).toContain('Writing New Records: 0')
  })

  it('first-time categories count as writing a new record', async () => {
    const wrapper = mountDialog()
    await openDialog(wrapper)
    await pickFile(
      wrapper,
      response({
        marking_categories: [
          {
            row: 2,
            group_id: 7,
            group_name: 'BTF-7',
            columns: ['product_category', 'category_of_solution'],
            overwritten_columns: [],
            product_categories: ['Health and Medicine'],
            product_category_other: '',
            solution_category: 'Treatment',
            solution_category_other: ''
          }
        ],
        summary: { creates: 0, updates: 0, unchanged: 2, errors: 0 }
      })
    )
    const text = wrapper.text()
    expect(text).toContain('Overwriting Existing Records: 0')
    expect(text).toContain('Writing New Records: 1')
  })

  it('replacing stored categories is an overwrite, named in the listing', async () => {
    const wrapper = mountDialog()
    await openDialog(wrapper)
    await pickFile(
      wrapper,
      response({
        // BTF-7 overwrites a mark and its stored product category; BTF-8
        // only replaces its stored category of solution.
        updates: [rowEntry(2, 7, ['r3_mark'])],
        marking_categories: [
          {
            row: 2,
            group_id: 7,
            group_name: 'BTF-7',
            columns: ['product_category'],
            overwritten_columns: ['product_category'],
            product_categories: ['Health and Medicine'],
            product_category_other: '',
            solution_category: '',
            solution_category_other: ''
          },
          {
            row: 3,
            group_id: 8,
            group_name: 'BTF-8',
            columns: ['category_of_solution'],
            overwritten_columns: ['category_of_solution'],
            product_categories: [],
            product_category_other: '',
            solution_category: 'Treatment',
            solution_category_other: ''
          }
        ],
        summary: { creates: 0, updates: 1, unchanged: 0, errors: 0 }
      })
    )
    const text = wrapper.text()
    expect(text).toContain(
      'Overwriting Existing Records: 2 (BTF-7 [r3_mark, product_category], BTF-8 [category_of_solution])'
    )
    expect(text).toContain('Writing New Records: 0')
    expect(wrapper.find('.bulk-upload__count--overwrite').exists()).toBe(true)
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
          rowEntry(4, 7, ['r3_mark']),
          rowEntry(5, 7, ['r4_mark', 'r4_comment']),
          rowEntry(8, 9, ['r1_mark'])
        ],
        summary: { creates: 0, updates: 3, unchanged: 0, errors: 0 }
      })
    )
    expect(wrapper.text()).toContain(
      'Overwriting Existing Records: 2 (BTF-7 [r3_mark, r4_mark, r4_comment], BTF-9 [r1_mark])'
    )
  })

  it('a replaced or cleared overall comment is an overwrite, named in the listing', async () => {
    const wrapper = mountDialog()
    await openDialog(wrapper)
    await pickFile(
      wrapper,
      response({
        // BTF-7 overwrites a mark and replaces its comment; BTF-8 touches no
        // grade, but its blank cell clears the stored comment.
        updates: [rowEntry(2, 7, ['r3_mark'])],
        overall_comments: [
          overallComment(2, 7, 'Better now', 'Good work'),
          overallComment(6, 8, '', 'Strong poster')
        ],
        summary: { creates: 0, updates: 1, unchanged: 0, overall_comments: 2, errors: 0 }
      })
    )
    const text = wrapper.text()
    expect(text).toContain(
      'Overwriting Existing Records: 2 (BTF-7 [r3_mark, overall_comment], BTF-8 [overall_comment])'
    )
    expect(text).toContain('Writing New Records: 0')
    expect(wrapper.find('.bulk-upload__count--overwrite').exists()).toBe(true)
  })

  it('an overall comment where none was stored counts as a new record', async () => {
    const wrapper = mountDialog()
    await openDialog(wrapper)
    await pickFile(
      wrapper,
      response({
        overall_comments: [overallComment(2, 7, 'First comment', '')],
        summary: { creates: 0, updates: 0, unchanged: 1, overall_comments: 1, errors: 0 }
      })
    )
    const text = wrapper.text()
    expect(text).toContain('Overwriting Existing Records: 0')
    expect(text).toContain('Writing New Records: 1')
  })

  it('a missing header stops the report there, hiding checks that never ran', async () => {
    const wrapper = mountDialog()
    await openDialog(wrapper)
    await pickFile(
      wrapper,
      response({
        checks: cleanChecks({ missing_headers: ['r2_comment'] }),
        errors: [{ row: 1, message: 'missing column header(s): r2_comment' }],
        summary: { creates: 0, updates: 0, unchanged: 0, errors: 1 }
      })
    )
    const text = wrapper.text()
    expect(text).toContain('Missing Column Header(s): r2_comment')
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
