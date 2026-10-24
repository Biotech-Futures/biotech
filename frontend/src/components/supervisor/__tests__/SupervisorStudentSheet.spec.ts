import { describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import SupervisorStudentSheet from '../SupervisorStudentSheet.vue'
import { appSelectText, pickAppSelect } from '@/__tests__/appSelect'
import {
  saveGuardianDetails,
  updateSupervisedStudentProfile,
  uploadSupervisedStudentPhoto,
  type SupervisedStudent,
} from '@/utils/supervisedStudents'

vi.mock('@/utils/supervisedStudents', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/utils/supervisedStudents')>()),
  fetchStudentEditOptions: vi.fn(async () => ({ countries: [], regions: [], interests: ['Biomedical Innovations'] })),
  saveGuardianDetails: vi.fn(async () => [student()]),
  updateSupervisedStudentProfile: vi.fn(async (_id: number, payload: Record<string, unknown>) => ({
    ...student(),
    ...payload,
  })),
  uploadSupervisedStudentPhoto: vi.fn(async () => ({ ...student(), profile_image_url: 'https://files.example.com/new.png' })),
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

describe('supervisor student panel: photo and policies', () => {
  it('shows their photo first, and when they agreed to the policies above Account Status', () => {
    const wrapper = open({ profile_image_url: 'https://files.example.com/amy.png', policies_agreed_at: '2026-10-21T00:15:00Z' })
    expect(wrapper.findAll('h3')[0].text()).toBe('Profile Photo')
    expect(wrapper.get('[data-test="student-sheet-photo"] dd img').attributes('src')).toBe('https://files.example.com/amy.png')
    const terms = wrapper.findAll('dt').map((term) => term.text())
    expect(terms.indexOf('Policies')).toBe(terms.indexOf('Account Status') - 1)
    expect(wrapper.get('[data-test="student-sheet-policies"] dd').text()).toMatch(/^Agreed, /)

    const never = open({ profile_image_url: null, policies_agreed_at: null })
    expect(never.get('[data-test="student-sheet-photo"] dd').text()).toBe('—')
    expect(never.get('[data-test="student-sheet-policies"] dd').text()).toBe('—')
  })

  it('uploads a chosen photo on Save and passes the student up', async () => {
    vi.stubGlobal('URL', Object.assign(URL, { createObjectURL: () => 'blob:chosen', revokeObjectURL: () => {} }))
    const wrapper = open({ profile_image_url: null })
    const section = wrapper.get('[data-test="student-sheet-photo"]')
    await section.findAll('button').find((button) => button.text() === 'Edit')!.trigger('click')

    const file = new File(['png'], 'amy.png', { type: 'image/png' })
    const input = wrapper.get('[data-test="student-sheet-photo-input"]')
    Object.defineProperty(input.element, 'files', { value: [file] })
    await input.trigger('change')
    expect(wrapper.get('[data-test="student-sheet-photo-form"] img').attributes('src')).toBe('blob:chosen')

    await wrapper.get('[data-test="student-sheet-photo-form"]').trigger('submit')
    await flushPromises()
    expect(uploadSupervisedStudentPhoto).toHaveBeenCalledWith(4, file)
    expect(wrapper.emitted('updated')![0][0]).toMatchObject({ profile_image_url: 'https://files.example.com/new.png' })
    vi.unstubAllGlobals()
  })
})

describe('supervisor student panel: guardian', () => {
  const editGuardian = async (wrapper: ReturnType<typeof open>) => {
    const section = wrapper.findAll('section').find((part) => part.find('h3').text() === 'Guardian Details')!
    await section.findAll('button').find((button) => button.text() === 'Edit')!.trigger('click')
    await flushPromises()
  }

  it('warns before changing a guardian who has given permission, then clears it', async () => {
    const wrapper = open({ has_join_permission: true, joinperm_granted_at: '2026-10-01T00:00:00Z' })
    await editGuardian(wrapper)

    // The warning first, not the form.
    expect(wrapper.find('#student-sheet-guardian').exists()).toBe(false)
    expect(wrapper.get('.admin-modal__message').text()).toBe(
      "Pat Chen has given permission for Amy. Changing the guardian's details clears it, and the new " +
        "guardian will be sent the consent form. Until they complete it, Amy won't be fully registered."
    )
    await wrapper.findAll('button').find((button) => button.text() === 'Continue')!.trigger('click')
    await flushPromises()

    await wrapper.get('#student-sheet-guardian input').setValue('Jordan')
    await wrapper.get('#student-sheet-guardian').trigger('submit')
    await flushPromises()
    expect(vi.mocked(saveGuardianDetails).mock.lastCall![0]).toMatchObject({
      pg_first_name: 'Jordan',
      clear_permission: true,
    })
  })

  it('opens the form straight away while permission is still to come', async () => {
    const wrapper = open()
    await editGuardian(wrapper)

    expect(wrapper.find('.admin-modal__message').exists()).toBe(false)
    await wrapper.get('#student-sheet-guardian').trigger('submit')
    await flushPromises()
    expect(vi.mocked(saveGuardianDetails).mock.lastCall![0]).toMatchObject({ clear_permission: false })
  })
})
