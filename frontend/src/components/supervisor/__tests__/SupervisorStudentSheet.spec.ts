import { describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import SupervisorStudentSheet from '../SupervisorStudentSheet.vue'
import { appSelectText, pickAppSelect } from '@/__tests__/appSelect'
import { updateSupervisedStudentProfile, type SupervisedStudent } from '@/utils/supervisedStudents'

vi.mock('@/utils/supervisedStudents', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/utils/supervisedStudents')>()),
  fetchStudentEditOptions: vi.fn(async () => ({ countries: [], regions: [], interests: ['Biomedical Innovations'] })),
  updateSupervisedStudentProfile: vi.fn(async (_id: number, payload: Record<string, unknown>) => ({
    ...student(),
    ...payload,
  })),
}))

const student = (overrides: Partial<SupervisedStudent> = {}): SupervisedStudent => ({
  id: 4,
  first_name: 'Amy',
  last_name: 'Chen',
  pronouns: 'Xe/xem',
  email: 'amy@example.com',
  school_name: 'Test High',
  year_lvl: '10',
  interests: ['Biomedical Innovations'],
  pg_first_name: 'Pat',
  pg_last_name: 'Chen',
  pg_email: 'pat@example.com',
  parent_guardian_flag: true,
  has_join_permission: false,
  joinperm_response_id: null,
  joinperm_granted_at: null,
  group_id: null,
  group_name: null,
  ...overrides,
})

const open = (overrides: Partial<SupervisedStudent> = {}) =>
  mount(SupervisorStudentSheet, {
    props: { student: student(overrides) },
    global: { stubs: { teleport: true } },
  })

const detailsForm = (wrapper: ReturnType<typeof open>) =>
  wrapper.findAll('form').find((form) => form.find('[data-test="student-sheet-pronouns"]').exists())!

describe('supervisor student panel: pronouns', () => {
  it('shows them after Interests, and edits them as registering offers them', async () => {
    const wrapper = open()
    expect(wrapper.find('[data-test="student-sheet-pronouns-view"] dd').text()).toBe('Xe/xem')

    const section = wrapper.findAll('section').find((part) => part.find('h3').text() === 'Student Details')!
    await section.findAll('button').find((button) => button.text() === 'Edit')!.trigger('click')
    await flushPromises()
    // Their own words come back under Other.
    expect(appSelectText(wrapper, '[data-test="student-sheet-pronouns"]')).toBe('Other')
    expect((wrapper.find('[data-test="student-sheet-pronouns-other"]').element as HTMLInputElement).value).toBe('Xe/xem')

    await wrapper.find('[data-test="student-sheet-pronouns-other"]').setValue('')
    await detailsForm(wrapper).trigger('submit')
    expect(wrapper.text()).toContain('Enter their pronouns.')
    expect(updateSupervisedStudentProfile).not.toHaveBeenCalled()

    await pickAppSelect(wrapper, '[data-test="student-sheet-pronouns"]', 'They/them')
    await detailsForm(wrapper).trigger('submit')
    await flushPromises()
    expect(vi.mocked(updateSupervisedStudentProfile).mock.calls[0][1]).toMatchObject({ pronouns: 'They/them' })
  })

  it('shows a dash when they are unsaid', () => {
    const wrapper = open({ pronouns: '' })
    expect(wrapper.find('[data-test="student-sheet-pronouns-view"] dd').text()).toBe('—')
  })
})
