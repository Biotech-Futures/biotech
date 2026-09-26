// Integration: the real category boxes and rubric form inside the marking
// page, so the Save button's wiring to unsaved category edits is exercised
// end to end (GroupMarkingPage.spec stubs both children).
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import * as vueRouter from 'vue-router'
import GroupMarkingPage from '@/views/grading/GroupMarkingPage.vue'
import {
  fetchComponentRows,
  fetchGroupCategories,
  fetchGroupMarking,
  saveGradesBulk,
  saveGroupCategories
} from '@/utils/gradingAPI'

vi.mock('@/utils/gradingAPI', () => ({
  downloadGroupZip: vi.fn(),
  downloadSubmissionFile: vi.fn(),
  fetchComponentRows: vi.fn(),
  fetchGroupCategories: vi.fn(),
  fetchGroupMarking: vi.fn(),
  overallCommentLabel: (code: string) => (code === 'POSTER' ? 'Overall Poster Comment' : null),
  resolveApiFileUrl: (url: string | null) => url,
  saveGradesBulk: vi.fn(),
  saveGroupCategories: vi.fn()
}))
const rowsMock = vi.mocked(fetchComponentRows)
const categoriesMock = vi.mocked(fetchGroupCategories)
const markingMock = vi.mocked(fetchGroupMarking)
const saveGradesMock = vi.mocked(saveGradesBulk)
const saveCategoriesMock = vi.mocked(saveGroupCategories)

vi.mock('vue-router', async () => {
  const { reactive } = await import('vue')
  const route = reactive({
    name: 'grading-group' as string,
    params: { groupId: '3' } as Record<string, string>
  })
  return {
    useRoute: () => route,
    useRouter: () => ({ push: vi.fn() }),
    onBeforeRouteLeave: vi.fn(),
    onBeforeRouteUpdate: vi.fn(),
    __route: route
  }
})
const routeState = (
  vueRouter as unknown as { __route: { name: string; params: Record<string, string> } }
).__route

const block = (code: string, criterionId: number) => ({
  component: {
    id: criterionId, code, name: code === 'SAQ' ? 'Short Answer Questions' : code,
    is_optional: false, accepts_file: true, accepts_text: false, accepts_link: false, order: 1
  },
  submission: {
    id: 11, component: criterionId, file_url: null, text: 'Answers.', link: '',
    submitted_at: '2026-09-01T10:00:00Z', is_late: false, overall_comment: ''
  },
  rubric_id: criterionId,
  criteria: [
    { id: criterionId, rubric: criterionId, name: 'Content', description: '', max_mark: '5.00', order: 1 }
  ],
  grades: [],
  last_grader_name: null
})

const stubs = {
  GroupSearchInput: { props: ['modelValue'], template: '<input />' },
  ResizableSplit: {
    template: '<div class="split-stub"><slot name="left" /><slot name="right" /></div>'
  },
  SubmissionPreview: { props: ['submission', 'component'], template: '<div />' },
  RouterLink: { props: ['to'], template: '<a :href="to"><slot /></a>' }
}

const mountPage = async () => {
  const wrapper = mount(GroupMarkingPage, { global: { stubs } })
  await flushPromises()
  return wrapper
}

// The SAQ form is the first rubric form in the combined SAQ & Poster column.
const saqSaveButton = (wrapper: Awaited<ReturnType<typeof mountPage>>) =>
  wrapper.findAll('.rubric-form')[0]!.find('button[type="submit"]')

beforeEach(() => {
  routeState.name = 'grading-group'
  routeState.params = { groupId: '3' }
  markingMock.mockReset().mockResolvedValue({
    group: { id: 3, group_name: 'Alpha Team' },
    year: 2026,
    components: [block('SAQ', 1), block('POSTER', 2)]
  } as never)
  rowsMock.mockReset().mockRejectedValue(new Error('no rows'))
  categoriesMock.mockReset().mockResolvedValue({
    product_categories: [],
    product_category_other: '',
    solution_category: '',
    solution_category_other: ''
  })
  saveGradesMock.mockReset().mockResolvedValue([] as never)
  saveCategoriesMock.mockReset().mockImplementation(async (_id, data) => ({ ...data }))
})

describe('category boxes and the SAQ Save button', () => {
  it('ticking a category enables Save, and Save stores it', async () => {
    const wrapper = await mountPage()
    expect(saqSaveButton(wrapper).attributes('disabled')).toBeDefined()

    await wrapper.find('.marking-categories input[type="checkbox"]').trigger('change')
    await flushPromises()
    expect(saqSaveButton(wrapper).attributes('disabled')).toBeUndefined()

    await wrapper.findAll('.rubric-form')[0]!.trigger('submit')
    await flushPromises()
    expect(saveCategoriesMock).toHaveBeenCalledWith(
      3,
      expect.objectContaining({ product_categories: ['Health and Medicine'] })
    )
    expect(saqSaveButton(wrapper).attributes('disabled')).toBeDefined()
  })

  it('the SAQ-only view (By Component) enables its Save the same way', async () => {
    routeState.name = 'grading-component-group'
    routeState.params = { code: 'SAQ', groupId: '3' }
    const wrapper = await mountPage()
    expect(wrapper.findAll('.rubric-form')).toHaveLength(1)
    expect(saqSaveButton(wrapper).attributes('disabled')).toBeDefined()

    await wrapper.find('.marking-categories input[type="checkbox"]').trigger('change')
    await flushPromises()
    expect(saqSaveButton(wrapper).attributes('disabled')).toBeUndefined()
  })

  it('picking a solution enables Save too', async () => {
    const wrapper = await mountPage()
    await wrapper.find('.marking-categories input[type="radio"]').trigger('change')
    await flushPromises()
    expect(saqSaveButton(wrapper).attributes('disabled')).toBeUndefined()
  })
})
