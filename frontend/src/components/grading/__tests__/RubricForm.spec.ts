import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount, type VueWrapper } from '@vue/test-utils'
import RubricForm from '@/components/grading/RubricForm.vue'
import type { Grade, RubricCriterion, Submission } from '@/utils/gradingAPI'

// The form registers route-leave guards; capture them so the unsaved-changes
// behaviour can be exercised without mounting a real router.
const guards = vi.hoisted(() => ({
  leave: [] as Array<() => boolean>,
  update: [] as Array<() => boolean>
}))
vi.mock('vue-router', () => ({
  onBeforeRouteLeave: (fn: () => boolean) => guards.leave.push(fn),
  onBeforeRouteUpdate: (fn: () => boolean) => guards.update.push(fn)
}))

const criterion = (id: number, name = `Criterion ${id}`, max = '10.00'): RubricCriterion => ({
  id,
  rubric: 1,
  name,
  description: '',
  max_mark: max,
  order: id * 10
})

const grade = (criterionId: number, mark: string | null, comment = ''): Grade => ({
  id: criterionId * 100,
  submission: 1,
  criterion: criterionId,
  mark,
  comment,
  graded_by: 5,
  graded_by_name: 'Ada Grader',
  graded_at: '2026-09-01T00:00:00Z'
})

const submission = (id = 1, overallComment = ''): Submission => ({
  id,
  component: 1,
  file_url: null,
  text: 'Some answers.',
  link: '',
  submitted_at: '2026-08-01T00:00:00Z',
  is_late: false,
  overall_comment: overallComment
})

// Every mounted form registers a window beforeunload listener, so unmount
// them after each test — a leftover dirty form would arm the prompt for an
// unrelated test on the shared jsdom window.
const mounted: VueWrapper[] = []

const mountForm = (props: Partial<InstanceType<typeof RubricForm>['$props']> = {}) => {
  const wrapper = mount(RubricForm, {
    props: {
      submission: submission(),
      criteria: [criterion(1, 'Content'), criterion(2, 'Clarity', '5.00')],
      grades: [],
      isSaving: false,
      ...props
    }
  })
  mounted.push(wrapper)
  return wrapper
}

const markInputs = (wrapper: ReturnType<typeof mountForm>) => wrapper.findAll('.rubric-form__mark')
const saveButton = (wrapper: ReturnType<typeof mountForm>) => wrapper.find('button[type="submit"]')

beforeEach(() => {
  guards.leave.length = 0
  guards.update.length = 0
  vi.restoreAllMocks()
})

afterEach(() => {
  while (mounted.length) mounted.pop()!.unmount()
})

describe('what the form renders', () => {
  it('explains an empty rubric instead of showing a bare form', () => {
    const wrapper = mountForm({ criteria: [], overallCommentLabel: null })
    expect(wrapper.text()).toContain('No rubric defined for this component yet')
    expect(wrapper.find('form').exists()).toBe(false)
  })

  it('shows one row per criterion with its maximum mark', () => {
    const wrapper = mountForm()
    expect(markInputs(wrapper)).toHaveLength(2)
    expect(wrapper.text()).toContain('/ 10.00')
    expect(wrapper.text()).toContain('/ 5.00')
  })

  it('preloads stored grades into the inputs', () => {
    const wrapper = mountForm({ grades: [grade(1, '7.00', 'Solid')] })
    expect((markInputs(wrapper)[0]!.element as HTMLInputElement).value).toBe('7.00')
    expect((wrapper.findAll('.rubric-form__comment')[0]!.element as HTMLTextAreaElement).value).toBe('Solid')
  })

  it('offers the overall-comment box only when a label is given', () => {
    expect(mountForm().find('.rubric-form__overall').exists()).toBe(false)
    expect(
      mountForm({ overallCommentLabel: 'Overall comment on the poster' }).text()
    ).toContain('Overall comment on the poster')
  })

  it('calls the action Save, with criteria or with only the comment box', () => {
    const wrapper = mountForm({ criteria: [], overallCommentLabel: 'Overall comment' })
    expect(saveButton(wrapper).text()).toBe('Save')
    expect(mountForm().find('button[type="submit"]').text()).toBe('Save')
  })

  it('says Saving and stays disabled while a save is in flight', async () => {
    const wrapper = mountForm({ isSaving: true })
    await markInputs(wrapper)[0]!.setValue('6')
    expect(saveButton(wrapper).text()).toBe('Saving…')
    expect(saveButton(wrapper).attributes('disabled')).toBeDefined()
  })
})

describe('what counts as an unsaved edit', () => {
  it('starts clean, with the save button disabled', () => {
    expect(saveButton(mountForm()).attributes('disabled')).toBeDefined()
  })

  it('typing a mark makes it dirty', async () => {
    const wrapper = mountForm()
    await markInputs(wrapper)[0]!.setValue('6')
    expect(saveButton(wrapper).attributes('disabled')).toBeUndefined()
  })

  it('retyping the stored value counts as clean, not an edit', async () => {
    const wrapper = mountForm({ grades: [grade(1, '7.00')] })
    await markInputs(wrapper)[0]!.setValue('7.00')
    expect(saveButton(wrapper).attributes('disabled')).toBeDefined()
  })

  it('treats 7 and 7.00 as the same mark, matching the server normalisation', async () => {
    const wrapper = mountForm({ grades: [grade(1, '7.00')] })
    await markInputs(wrapper)[0]!.setValue('7')
    expect(saveButton(wrapper).attributes('disabled')).toBeDefined()
  })

  it('an edited overall comment is an unsaved edit too', async () => {
    const wrapper = mountForm({
      submission: submission(1, 'stored feedback'),
      overallCommentLabel: 'Overall comment'
    })
    expect(saveButton(wrapper).attributes('disabled')).toBeDefined()
    await wrapper.find('.rubric-form__overall-input').setValue('new feedback')
    expect(saveButton(wrapper).attributes('disabled')).toBeUndefined()
  })
})

describe('what a save sends', () => {
  it('sends every criterion, with empty marks as null so nothing reads as a zero', async () => {
    const wrapper = mountForm()
    await markInputs(wrapper)[0]!.setValue('8.5')
    await wrapper.find('form').trigger('submit')
    const [items, overall] = wrapper.emitted('save')![0]!
    expect(items).toEqual([
      { submission: 1, criterion: 1, mark: '8.5', comment: '' },
      { submission: 1, criterion: 2, mark: null, comment: '' }
    ])
    expect(overall).toBeNull()
  })

  it('sends the overall comment when its box is shown', async () => {
    const wrapper = mountForm({ overallCommentLabel: 'Overall comment' })
    await markInputs(wrapper)[0]!.setValue('8')
    await wrapper.find('.rubric-form__overall-input').setValue('Well argued.')
    await wrapper.find('form').trigger('submit')
    expect(wrapper.emitted('save')![0]![1]).toBe('Well argued.')
  })
})

describe('a refetch after saving', () => {
  it('keeps an edit in progress when the same entry refreshes', async () => {
    const wrapper = mountForm({ grades: [grade(1, '7.00')] })
    await markInputs(wrapper)[0]!.setValue('9')
    // The combined view saving the other section refetches the same entry.
    await wrapper.setProps({ grades: [grade(1, '7.00')] })
    expect((markInputs(wrapper)[0]!.element as HTMLInputElement).value).toBe('9')
  })

  it('adopts the saved value once the server confirms it', async () => {
    const wrapper = mountForm({ grades: [grade(1, '7.00')] })
    await markInputs(wrapper)[0]!.setValue('9')
    await wrapper.setProps({ grades: [grade(1, '9.00')] })
    expect((markInputs(wrapper)[0]!.element as HTMLInputElement).value).toBe('9.00')
    expect(saveButton(wrapper).attributes('disabled')).toBeDefined()
  })

  it('drops edits when a different entry loads', async () => {
    const wrapper = mountForm()
    await markInputs(wrapper)[0]!.setValue('9')
    await wrapper.setProps({ submission: submission(99), grades: [] })
    expect((markInputs(wrapper)[0]!.element as HTMLInputElement).value).toBe('')
  })
})

describe('leaving with unsaved edits', () => {
  it('lets a clean form leave without asking', () => {
    mountForm()
    const confirm = vi.spyOn(window, 'confirm')
    expect(guards.leave[0]!()).toBe(true)
    expect(confirm).not.toHaveBeenCalled()
  })

  it('asks before leaving a dirty form, and staying is honoured', async () => {
    const wrapper = mountForm()
    await markInputs(wrapper)[0]!.setValue('6')
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false)
    expect(guards.leave[0]!()).toBe(false)
    expect(confirm).toHaveBeenCalledOnce()
  })

  it('unsaved edits outside the form (the SAQ categories) enable Save and the guard', async () => {
    const wrapper = mountForm({ extraDirty: true })
    expect(saveButton(wrapper).attributes('disabled')).toBeUndefined()
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false)
    expect(guards.leave[0]!()).toBe(false)
    expect(confirm).toHaveBeenCalledOnce()

    await wrapper.setProps({ extraDirty: false })
    expect(saveButton(wrapper).attributes('disabled')).toBeDefined()
  })

  it('guards Prev/Next navigation the same way as leaving the page', async () => {
    const wrapper = mountForm()
    await markInputs(wrapper)[0]!.setValue('6')
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    expect(guards.update[0]!()).toBe(true)
  })

  it('arms the browser prompt for a tab close only while dirty', async () => {
    const wrapper = mountForm()
    const clean = new Event('beforeunload', { cancelable: true })
    window.dispatchEvent(clean)
    expect(clean.defaultPrevented).toBe(false)

    await markInputs(wrapper)[0]!.setValue('6')
    const dirty = new Event('beforeunload', { cancelable: true })
    window.dispatchEvent(dirty)
    expect(dirty.defaultPrevented).toBe(true)

    wrapper.unmount()
    const after = new Event('beforeunload', { cancelable: true })
    window.dispatchEvent(after)
    expect(after.defaultPrevented).toBe(false)
  })
})
