import { beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import * as vueRouter from 'vue-router'
import GroupMarkingPage from '@/views/grading/GroupMarkingPage.vue'
import { markingFullWidth } from '@/composables/markingLayout'
import {
  downloadGroupZip,
  downloadSubmissionFile,
  fetchComponentRows,
  fetchGroupMarking,
  saveGradesBulk
} from '@/utils/gradingAPI'

vi.mock('@/utils/gradingAPI', () => ({
  downloadGroupZip: vi.fn(),
  downloadSubmissionFile: vi.fn(),
  fetchComponentRows: vi.fn(),
  fetchGroupMarking: vi.fn(),
  overallCommentLabel: (code: string) => (code === 'POSTER' ? 'Overall Poster Comment' : null),
  resolveApiFileUrl: (url: string | null) => url,
  saveGradesBulk: vi.fn()
}))
const zipMock = vi.mocked(downloadGroupZip)
const fileMock = vi.mocked(downloadSubmissionFile)
const rowsMock = vi.mocked(fetchComponentRows)
const markingMock = vi.mocked(fetchGroupMarking)
const saveMock = vi.mocked(saveGradesBulk)

const pushMock = vi.hoisted(() => vi.fn())
vi.mock('vue-router', async () => {
  const { reactive } = await import('vue')
  const route = reactive({
    name: 'grading-group' as string,
    params: { groupId: '3' } as Record<string, string>
  })
  return { useRoute: () => route, useRouter: () => ({ push: pushMock }), __route: route }
})
const routeState = (
  vueRouter as unknown as { __route: { name: string; params: Record<string, string> } }
).__route

// --- child stubs -----------------------------------------------------------
const resolveIdMock = vi.fn<() => number | null>()
const GroupSearchInputStub = defineComponent({
  name: 'GroupSearchInput',
  props: { modelValue: { type: String, default: '' } },
  emits: ['update:modelValue', 'select'],
  methods: {
    resolveId(): number | null {
      return resolveIdMock()
    }
  },
  template: '<input class="picker" :value="modelValue" />'
})

const formDirty = { value: false }
const RubricFormStub = defineComponent({
  name: 'RubricForm',
  props: ['submission', 'criteria', 'grades', 'overallCommentLabel', 'isSaving'],
  emits: ['save'],
  computed: {
    isDirty(): boolean {
      return formDirty.value
    }
  },
  template:
    '<div class="rubric-stub"><button class="save-stub" @click="$emit(\'save\', [{submission: 11, criterion: 2, mark: \'5\', comment: \'\'}], overallCommentLabel ? \'Great\' : null)">save</button><slot name="actions" /></div>'
})

const MarkingCategoriesStub = defineComponent({
  name: 'MarkingCategories',
  props: ['groupId'],
  emits: ['status'],
  template:
    '<button class="categories-stub" @click="$emit(\'status\', { text: \'Saved.\', error: false })"></button>'
})

const stubs = {
  GroupSearchInput: GroupSearchInputStub,
  RubricForm: RubricFormStub,
  MarkingCategories: MarkingCategoriesStub,
  ResizableSplit: {
    template: '<div class="split-stub"><slot name="left" /><slot name="right" /></div>'
  },
  SubmissionPreview: {
    props: ['submission', 'component', 'lastGraderName', 'criterionMarkers', 'graderNames', 'hideSubmitted'],
    template: '<div class="preview-stub">{{ component.code }}</div>'
  },
  RouterLink: { props: ['to'], template: '<a :href="to"><slot /></a>' }
}

// --- fixtures --------------------------------------------------------------
const submission = (over: Record<string, unknown> = {}) => ({
  id: 11,
  component: 1,
  file_url: null,
  text: 'Answers.',
  link: '',
  submitted_at: '2026-09-01T10:00:00Z',
  is_late: false,
  overall_comment: '',
  ...over
})

const block = (code: string, over: Record<string, unknown> = {}) => ({
  component: {
    id: 1, code, name: code === 'SAQ' ? 'Short Answer Questions' : code,
    is_optional: false, accepts_file: true, accepts_text: false, accepts_link: false, order: 1
  },
  submission: submission(),
  rubric_id: 1,
  criteria: [
    { id: 2, rubric: 1, name: 'Content', description: '', max_mark: '10.00', order: 10 }
  ],
  grades: [
    {
      id: 200, submission: 11, criterion: 2, mark: '7.00', comment: '',
      graded_by: 5, graded_by_name: 'Ada Grader', graded_at: '2026-09-02T00:00:00Z'
    }
  ],
  last_grader_name: 'Ada Grader',
  ...over
})

const markingPayload = (components: unknown[]) => ({
  group: { id: 3, group_name: 'Alpha Team' },
  year: 2026,
  components
})

const cohortRow = (group_id: number, over: Record<string, unknown> = {}) => ({
  group_id,
  group_name: `BTF-${group_id}`,
  submission_id: 10 + group_id,
  submitted_at: '2026-09-01T10:00:00Z',
  is_late: false,
  late_by: null,
  criteria_graded: 2,
  marks_total: null,
  last_grader_name: 'Ada Grader',
  grader_names: ['Ada Grader'],
  criterion_markers: [],
  ...over
})

const rowsPayload = (code: string, rows: unknown[]) => ({
  component: {
    id: 1, code, name: code, is_optional: false,
    accepts_file: true, accepts_text: false, accepts_link: false, order: 1
  },
  year: 2026,
  criteria_total: 2,
  rows
})

const mountPage = async () => {
  const wrapper = mount(GroupMarkingPage, { global: { stubs } })
  await flushPromises()
  return wrapper
}

beforeEach(() => {
  routeState.name = 'grading-group'
  routeState.params = { groupId: '3' }
  pushMock.mockReset()
  resolveIdMock.mockReset()
  formDirty.value = false
  zipMock.mockReset()
  fileMock.mockReset()
  saveMock.mockReset().mockResolvedValue([] as never)
  markingMock.mockReset().mockResolvedValue(
    markingPayload([
      block('SAQ'),
      block('POSTER', { submission: submission({ file_url: '/media/poster.pdf', file_name: 'poster.pdf' }), last_grader_name: 'Bob Marker' })
    ]) as never
  )
  // Cohort: 1 fully marked, 2 unsubmitted, 3 current, 5 unmarked.
  rowsMock.mockReset().mockImplementation(async (code: string) => {
    if (code === 'SAQ') {
      return rowsPayload('SAQ', [
        cohortRow(1),
        cohortRow(2, { submission_id: null, submitted_at: null, criteria_graded: 0 }),
        cohortRow(3, { criteria_graded: 1 }),
        cohortRow(5, { criteria_graded: 0 })
      ]) as never
    }
    throw new Error(`no rubric for ${code}`)
  })
})

describe('the combined SAQs & Poster view', () => {
  it('is the default when both sections exist, under the group heading', async () => {
    const wrapper = await mountPage()
    expect(wrapper.find('.group-marking__title').text()).toContain('Alpha Team')
    // The heading shows the group name alone — no id.
    expect(wrapper.find('.group-marking__title').text()).not.toContain('#')
    const active = wrapper.find('[role="tab"][aria-selected="true"]')
    expect(active.text()).toBe('SAQs & Poster')
    // Both previews and both rubric forms render.
    expect(wrapper.findAll('.preview-stub').map((p) => p.text())).toEqual(['SAQ', 'POSTER'])
    expect(wrapper.findAll('.rubric-stub')).toHaveLength(2)
  })

  it('hoists one shared stamp naming each section marker', async () => {
    const wrapper = await mountPage()
    const stamp = wrapper.find('.group-marking__pane-stamp')
    expect(stamp.text()).toContain('Submitted')
    expect(stamp.find('.group-marking__stamp-marker').text()).toBe('SAQ: Ada Grader · Poster: Bob Marker')
    expect(stamp.find('.group-marking__stamp-marker').attributes('title')).toContain('SAQ 1: Ada Grader')
    // The poster PDF gets its Open action on the stamp line.
    expect(stamp.find('a').attributes('href')).toBe('/media/poster.pdf')
  })

  it('collapses the marker to one name when the same person marked both', async () => {
    markingMock.mockResolvedValue(
      markingPayload([block('SAQ'), block('POSTER')]) as never
    )
    const wrapper = await mountPage()
    expect(wrapper.find('.group-marking__stamp-marker').text()).toBe('Ada Grader')
  })

  it('the categories status surfaces on the stamp line', async () => {
    const wrapper = await mountPage()
    await wrapper.find('.categories-stub').trigger('click')
    expect(wrapper.find('.group-marking__stamp-status').text()).toContain('Saved.')
  })

  it('widens the layout for marking, and releases it on unmount', async () => {
    const wrapper = await mountPage()
    expect(markingFullWidth.value).toBe(true)
    wrapper.unmount()
    expect(markingFullWidth.value).toBe(false)
  })
})

describe('saving marks', () => {
  it('a poster save carries its overall comment keyed by component', async () => {
    const wrapper = await mountPage()
    await wrapper.findAll('.save-stub')[1]!.trigger('click') // poster form
    await flushPromises()
    expect(saveMock).toHaveBeenCalledWith(
      [{ submission: 11, criterion: 2, mark: '5', comment: '' }],
      [{ submission: 11, component: 'POSTER', comment: 'Great' }]
    )
    expect(wrapper.find('.group-marking__banner--ok').text()).toBe('Marks saved.')
    expect(markingMock).toHaveBeenCalledTimes(2) // refetch after the upsert
  })

  it('an SAQ save sends no overall comment — SAQ has no box', async () => {
    const wrapper = await mountPage()
    await wrapper.findAll('.save-stub')[0]!.trigger('click')
    await flushPromises()
    expect(saveMock).toHaveBeenCalledWith(expect.any(Array), undefined)
  })

  it('a refused save is reported without claiming success', async () => {
    saveMock.mockRejectedValueOnce(new Error('mismatched criterion'))
    const wrapper = await mountPage()
    await wrapper.findAll('.save-stub')[0]!.trigger('click')
    await flushPromises()
    expect(wrapper.find('.group-marking__banner--error').text()).toContain('mismatched criterion')
    expect(wrapper.find('.group-marking__banner--ok').exists()).toBe(false)
  })
})

describe('switching sections in by-group mode', () => {
  it('switches locally without navigating', async () => {
    const wrapper = await mountPage()
    await wrapper.findAll('[role="tab"]').find((t) => t.text() === 'POSTER')!.trigger('click')
    expect(pushMock).not.toHaveBeenCalled()
    expect(wrapper.find('[role="tab"][aria-selected="true"]').text()).toBe('POSTER')
    expect(wrapper.findAll('.rubric-stub')).toHaveLength(1)
  })

  it('asks before discarding unsaved marks, and staying is honoured', async () => {
    formDirty.value = true
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false)
    const wrapper = await mountPage()
    await wrapper.findAll('[role="tab"]').find((t) => t.text() === 'POSTER')!.trigger('click')
    expect(confirm).toHaveBeenCalled()
    expect(wrapper.find('[role="tab"][aria-selected="true"]').text()).toBe('SAQs & Poster')
    confirm.mockRestore()
  })
})

describe('walking the cohort', () => {
  it('prev skips groups with no submission anywhere', async () => {
    const wrapper = await mountPage()
    await wrapper.findAll('button').find((b) => /Prev/.test(b.text()))!.trigger('click')
    expect(pushMock).toHaveBeenCalledWith('/grading/groups/1') // skipped #2
  })

  it('next unmarked finds the group whose current subtab still needs marks', async () => {
    const wrapper = await mountPage()
    await wrapper.findAll('button').find((b) => /Next Unmarked/.test(b.text()))!.trigger('click')
    expect(pushMock).toHaveBeenCalledWith('/grading/groups/5')
  })

  it('search opens the resolved group and refuses an unknown one', async () => {
    resolveIdMock.mockReturnValue(5)
    const wrapper = await mountPage()
    await wrapper.find('.group-marking__search-form').trigger('submit')
    expect(pushMock).toHaveBeenCalledWith('/grading/groups/5')

    pushMock.mockClear()
    resolveIdMock.mockReturnValue(null)
    await wrapper.find('.group-marking__search-form').trigger('submit')
    expect(wrapper.find('.group-marking__search-error').text()).toBe('No group matches that name.')
    expect(pushMock).not.toHaveBeenCalled()
  })
})

describe('component mode', () => {
  beforeEach(() => {
    routeState.name = 'grading-component-group'
    routeState.params = { code: 'POSTER', groupId: '3' }
  })

  it('tab switches navigate through the URL so guards can fire', async () => {
    const wrapper = await mountPage()
    await wrapper.findAll('[role="tab"]').find((t) => t.text() === 'Short Answer Questions')!.trigger('click')
    expect(pushMock).toHaveBeenCalledWith('/grading/components/SAQ/3')
  })

  it('an unknown component gets a message and a way back', async () => {
    routeState.params = { code: 'NOPE', groupId: '3' }
    const wrapper = await mountPage()
    expect(wrapper.text()).toContain('No such component "NOPE" for this group.')
    expect(wrapper.find('a').attributes('href')).toBe('/grading/components/NOPE')
  })
})

describe('downloads', () => {
  it('Download all zips the whole entry', async () => {
    zipMock.mockResolvedValueOnce()
    const wrapper = await mountPage()
    await wrapper.findAll('button').find((b) => /Download all/.test(b.text()))!.trigger('click')
    await flushPromises()
    expect(zipMock).toHaveBeenCalledWith(3)
  })

  it('a failed zip is reported', async () => {
    zipMock.mockRejectedValueOnce(new Error('storage down'))
    const wrapper = await mountPage()
    await wrapper.findAll('button').find((b) => /Download all/.test(b.text()))!.trigger('click')
    await flushPromises()
    expect(wrapper.find('.group-marking__banner--error').text()).toContain('storage down')
  })

  it('the stamp download falls back to opening the URL when the fetch is blocked', async () => {
    fileMock.mockRejectedValueOnce(new Error('CORS'))
    const open = vi.spyOn(window, 'open').mockImplementation(() => null)
    const wrapper = await mountPage()
    await wrapper.find('.group-marking__stamp-actions button').trigger('click')
    await flushPromises()
    expect(fileMock).toHaveBeenCalledWith('/media/poster.pdf', 'poster.pdf')
    expect(open).toHaveBeenCalledWith('/media/poster.pdf', '_blank', 'noopener')
    open.mockRestore()
  })
})

describe('failure to load', () => {
  it('offers retry and a way back', async () => {
    markingMock.mockRejectedValueOnce(new Error('backend down'))
    const wrapper = await mountPage()
    expect(wrapper.text()).toContain('Failed to load marking payload for group 3.')
    markingMock.mockResolvedValueOnce(markingPayload([block('SAQ'), block('POSTER')]) as never)
    await wrapper.findAll('button').find((b) => /Try again/.test(b.text()))!.trigger('click')
    await flushPromises()
    expect(wrapper.find('.group-marking__title').text()).toContain('Alpha Team')
  })
})
