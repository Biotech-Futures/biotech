import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'

import SupervisorStudentsPage from '@/views/SupervisorStudentsPage.vue'
import { downloadConsentDocuments, viewConsentDocuments } from '@/utils/consentDocument'
import {
  fetchConsentLinks,
  fetchDetailsLinks,
  fetchSupervisedStudents,
  saveGuardianDetails,
  sendSupervisedEmails,
  withConsentSignatures,
  type SupervisedStudent,
} from '@/utils/supervisedStudents'

// The roster's rules (who is pending what, how a row reads) stay real; only
// the calls to the server are replaced.
vi.mock('@/utils/supervisedStudents', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/utils/supervisedStudents')>()),
  fetchSupervisedStudents: vi.fn(),
  saveGuardianDetails: vi.fn(),
  sendSupervisedEmails: vi.fn(),
  fetchConsentLinks: vi.fn(),
  fetchDetailsLinks: vi.fn(),
  withConsentSignatures: vi.fn(),
}))

vi.mock('@/utils/consentDocument', () => ({
  downloadConsentDocuments: vi.fn(),
  viewConsentDocuments: vi.fn(),
}))

const student = (id: number, first: string, over: Partial<SupervisedStudent> = {}): SupervisedStudent => ({
  id,
  first_name: first,
  last_name: 'Lee',
  email: `${first.toLowerCase()}@example.com`,
  school_name: 'Eastwood College',
  year_lvl: '10',
  interests: [],
  pg_first_name: '',
  pg_last_name: '',
  pg_email: null,
  parent_guardian_flag: true,
  has_join_permission: false,
  joinperm_response_id: null,
  joinperm_granted_at: null,
  group_id: null,
  group_name: null,
  ...over,
})

const awaitingGuardian = (id: number, first: string, guardian: string, over: Partial<SupervisedStudent> = {}) =>
  student(id, first, { pg_first_name: guardian, pg_last_name: 'Lee', pg_email: `${guardian.toLowerCase()}@example.com`, ...over })

const registered = (id: number, first: string, grantedAt: string) =>
  awaitingGuardian(id, first, 'Robin', { has_join_permission: true, joinperm_granted_at: grantedAt })

const roster = () => [
  student(1, 'Ava', { interests: ['Space & Astrobiology', 'Water & Energy Tech'] }),
  student(2, 'Ben'),
  awaitingGuardian(3, 'Cara', 'Pat'),
  awaitingGuardian(4, 'Dan', 'Jo'),
  registered(5, 'Eve', '2026-05-01T10:00:00Z'),
  registered(6, 'Finn', '2026-06-01T10:00:00Z'),
]

const SheetStub = {
  name: 'SupervisorStudentSheet',
  props: ['student', 'editGuardian'],
  emits: ['close', 'saved', 'updated'],
  template: '<div class="sheet-stub" />',
}
const UploadStub = { name: 'GuardianUploadDialog', emits: ['applied'], template: '<button type="button">Upload</button>' }

let router: Router
const clipboard = { writeText: vi.fn() }

const mountPage = async (props: { admin?: boolean } = {}, query: Record<string, string> = {}) => {
  router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/students', component: { template: '<div />' } }],
  })
  await router.push({ path: '/students', query })
  const wrapper = mount(SupervisorStudentsPage, {
    props,
    global: {
      plugins: [router],
      stubs: { SupervisorStudentSheet: SheetStub, GuardianUploadDialog: UploadStub, SupervisorTableOptions: true },
    },
  })
  await flushPromises()
  return wrapper
}

type Wrapper = VueWrapper<InstanceType<typeof SupervisorStudentsPage>>

const tab = (wrapper: Wrapper, label: string) =>
  wrapper.findAll('[role="tab"]').find((t) => t.text() === label)!

const rowOf = (wrapper: Wrapper, name: string) =>
  wrapper.findAll('tbody tr').find((tr) => tr.find('.supervisor-name-btn').exists() && tr.text().includes(name))!

const buttonIn = (scope: Pick<Wrapper, 'findAll'>, label: string) =>
  scope.findAll('button').find((b) => b.text().trim() === label)!

const select = async (wrapper: Wrapper, ...names: string[]) => {
  for (const name of names) await wrapper.get(`input[aria-label="Select ${name} Lee"]`).setValue(true)
}

const bulkButton = (wrapper: Wrapper, label: string) => buttonIn(wrapper.get('.data-table-bulk'), label)

const sheet = (wrapper: Wrapper) => wrapper.findComponent({ name: 'SupervisorStudentSheet' })

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(fetchSupervisedStudents).mockResolvedValue(roster())
  vi.mocked(withConsentSignatures).mockImplementation(async (rows) => rows.map((row) => ({ ...row, signature: '' })))
  vi.mocked(downloadConsentDocuments).mockResolvedValue(undefined)
  vi.mocked(viewConsentDocuments).mockResolvedValue(undefined)
  clipboard.writeText.mockResolvedValue(undefined)
  vi.stubGlobal('navigator', { ...navigator, clipboard })
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('SupervisorStudentsPage', () => {
  it("lists a supervisor's students by where their registration is", async () => {
    const wrapper = await mountPage()
    expect(wrapper.get('.page-subtitle').text()).toBe('This is a list of all students registered under your supervision.')
    expect(tab(wrapper, 'Pending Details').attributes('aria-selected')).toBe('true')
    expect(wrapper.get('.subheading').text()).toBe('Pending Guardian Details')
    expect(wrapper.text()).toContain('Ava Lee')
    expect(wrapper.text()).toContain('Ben Lee')
    expect(wrapper.text()).not.toContain('Cara Lee')
    // A student's areas of interest sit on their own line under the row.
    expect(wrapper.get('.students-interests').text()).toBe(
      'Area(s) of Interest: Space & Astrobiology, Water & Energy Tech',
    )

    await tab(wrapper, 'Pending Permission').trigger('click')
    expect(wrapper.get('.subheading').text()).toBe('Pending Guardian Permission')
    expect(wrapper.text()).toContain('Cara Lee')
    expect(wrapper.text()).toContain('Pat Lee')
    expect(wrapper.text()).not.toContain('Ava Lee')

    await tab(wrapper, 'Fully Registered').trigger('click')
    expect(wrapper.get('.subheading').text()).toBe('Fully Registered with Guardian Permission')
    // Latest permission first.
    const names = wrapper.findAll('.supervisor-name-btn').map((b) => b.text())
    expect(names).toEqual(['Finn Lee', 'Eve Lee'])
  })

  it('describes every student to an admin', async () => {
    const wrapper = await mountPage({ admin: true })
    expect(wrapper.get('.page-subtitle').text()).toBe('This is a list of all students registered.')
  })

  it('says why the list could not be loaded', async () => {
    vi.mocked(fetchSupervisedStudents).mockRejectedValueOnce(new Error('Session expired.'))
    const wrapper = await mountPage()
    expect(wrapper.get('.supervisor-error').text()).toBe('Session expired.')
  })

  it('falls back to a plain message when loading fails without one', async () => {
    vi.mocked(fetchSupervisedStudents).mockRejectedValueOnce('offline')
    const wrapper = await mountPage()
    expect(wrapper.get('.supervisor-error').text()).toBe('Student list could not be loaded.')
  })

  describe('emails', () => {
    it('asks before emailing one student, then sends and reports', async () => {
      vi.mocked(sendSupervisedEmails).mockResolvedValue({ sent: 1, failed: 0, skipped: 0, msg: 'Sent 1 email.', messages: [] })
      const wrapper = await mountPage()
      await buttonIn(rowOf(wrapper, 'Ava Lee'), 'Send Email').trigger('click')
      const dialog = wrapper.get('[role="dialog"]')
      expect(dialog.get('h3').text()).toBe('Email student?')
      expect(dialog.text()).toContain('asking this student to add guardian details')
      expect(dialog.findAll('li').map((li) => li.text())).toEqual(['Ava Lee'])

      await buttonIn(dialog, 'Send Emails').trigger('click')
      await flushPromises()
      expect(sendSupervisedEmails).toHaveBeenCalledWith([1], 'guardian_details')
      expect(wrapper.find('[role="dialog"]').exists()).toBe(false)
      expect(wrapper.get('.supervisor-notice').text()).toBe('Sent 1 email.')
    })

    it('emails every student on the tab, or none when cancelled', async () => {
      const wrapper = await mountPage()
      await buttonIn(wrapper, 'Email All Students').trigger('click')
      const dialog = wrapper.get('[role="dialog"]')
      expect(dialog.get('h3').text()).toBe('Email all students?')
      expect(dialog.text()).toContain('asking these students to add guardian details')
      expect(dialog.findAll('li').map((li) => li.text())).toEqual(['Ava Lee', 'Ben Lee'])
      await buttonIn(dialog, 'Cancel').trigger('click')
      expect(wrapper.find('[role="dialog"]').exists()).toBe(false)
      expect(sendSupervisedEmails).not.toHaveBeenCalled()
    })

    it("names the guardians when emailing them, and says why a send failed", async () => {
      vi.mocked(sendSupervisedEmails).mockRejectedValueOnce(new Error('The mail server is down.'))
      const wrapper = await mountPage()
      await tab(wrapper, 'Pending Permission').trigger('click')
      await buttonIn(rowOf(wrapper, 'Cara Lee'), 'Email Guardian').trigger('click')
      let dialog = wrapper.get('[role="dialog"]')
      expect(dialog.get('h3').text()).toBe('Email guardian?')
      expect(dialog.findAll('li').map((li) => li.text())).toEqual(['Pat Lee'])
      await buttonIn(dialog, 'Send Emails').trigger('click')
      await flushPromises()
      expect(sendSupervisedEmails).toHaveBeenCalledWith([3], 'guardian_consent')
      expect(wrapper.get('.supervisor-error').text()).toBe('The mail server is down.')

      await buttonIn(wrapper, 'Email All Guardians').trigger('click')
      dialog = wrapper.get('[role="dialog"]')
      expect(dialog.get('h3').text()).toBe('Email all guardians?')
      expect(dialog.text()).toContain('to these guardians')
      // A click on the backdrop closes it too.
      await wrapper.get('.supervisor-modal-backdrop').trigger('click')
      expect(wrapper.find('[role="dialog"]').exists()).toBe(false)
    })

    it('emails the ticked students from the selection bar', async () => {
      vi.mocked(sendSupervisedEmails).mockRejectedValueOnce('down')
      const wrapper = await mountPage()
      await select(wrapper, 'Ava', 'Ben')
      expect(wrapper.get('.data-table-bulk').text()).toContain('2 selected')
      await bulkButton(wrapper, 'Send Email').trigger('click')
      await buttonIn(wrapper.get('[role="dialog"]'), 'Send Emails').trigger('click')
      await flushPromises()
      expect(sendSupervisedEmails).toHaveBeenCalledWith([1, 2], 'guardian_details')
      expect(wrapper.get('.supervisor-error').text()).toBe('Emails could not be sent.')
    })
  })

  describe('links', () => {
    it("copies one student's details link on its own", async () => {
      vi.mocked(fetchDetailsLinks).mockResolvedValue([{ studentId: 1, link: 'https://example.com/details/a', msg: '' }])
      const wrapper = await mountPage()
      await buttonIn(rowOf(wrapper, 'Ava Lee'), 'Copy link to provide guardian details').trigger('click')
      await flushPromises()
      expect(fetchDetailsLinks).toHaveBeenCalledWith([1])
      expect(clipboard.writeText).toHaveBeenCalledWith('https://example.com/details/a')
      expect(wrapper.get('.supervisor-notice').text()).toBe('Details link copied.')
    })

    it('copies a line per guardian, and says which links could not be made', async () => {
      vi.mocked(fetchConsentLinks).mockResolvedValue([
        { studentId: 3, link: 'https://example.com/consent/c', msg: '' },
        { studentId: 4, link: null, msg: 'Permission already given.' },
      ])
      const wrapper = await mountPage()
      await tab(wrapper, 'Pending Permission').trigger('click')
      await select(wrapper, 'Cara', 'Dan')
      await bulkButton(wrapper, 'Copy Consent Link').trigger('click')
      await flushPromises()
      expect(fetchConsentLinks).toHaveBeenCalledWith([3, 4])
      expect(clipboard.writeText).toHaveBeenCalledWith('https://example.com/consent/c')
      expect(wrapper.get('.supervisor-notice').text()).toBe(
        'Consent link copied. 1 could not be made: Permission already given.',
      )
    })

    it('copies several links as "Name: link" lines', async () => {
      vi.mocked(fetchConsentLinks).mockResolvedValue([
        { studentId: 3, link: 'https://example.com/consent/c', msg: '' },
        { studentId: 4, link: 'https://example.com/consent/d', msg: '' },
      ])
      const wrapper = await mountPage()
      await tab(wrapper, 'Pending Permission').trigger('click')
      await select(wrapper, 'Cara', 'Dan')
      await bulkButton(wrapper, 'Copy Consent Link').trigger('click')
      await flushPromises()
      expect(clipboard.writeText).toHaveBeenCalledWith(
        'Cara Lee: https://example.com/consent/c\nDan Lee: https://example.com/consent/d',
      )
      expect(wrapper.get('.supervisor-notice').text()).toBe('2 consent links copied.')
    })

    it('copies nothing when no link could be made, and says why links failed', async () => {
      vi.mocked(fetchDetailsLinks).mockResolvedValueOnce([{ studentId: 1, link: null, msg: 'No.' }])
      const wrapper = await mountPage()
      await buttonIn(rowOf(wrapper, 'Ava Lee'), 'Copy link to provide guardian details').trigger('click')
      await flushPromises()
      expect(clipboard.writeText).not.toHaveBeenCalled()
      expect(wrapper.get('.supervisor-notice').text()).toBe('Nothing to copy for the selected students.')

      vi.mocked(fetchDetailsLinks).mockRejectedValueOnce(new Error('Not your student.'))
      await buttonIn(rowOf(wrapper, 'Ava Lee'), 'Copy link to provide guardian details').trigger('click')
      await flushPromises()
      expect(wrapper.get('.supervisor-error').text()).toBe('Not your student.')

      vi.mocked(fetchDetailsLinks).mockRejectedValueOnce('offline')
      await buttonIn(rowOf(wrapper, 'Ava Lee'), 'Copy link to provide guardian details').trigger('click')
      await flushPromises()
      expect(wrapper.get('.supervisor-error').text()).toBe('The details links could not be made.')
    })
  })

  describe('guardian details', () => {
    it("opens one student's panel at the guardian form", async () => {
      const wrapper = await mountPage()
      await buttonIn(rowOf(wrapper, 'Ava Lee'), 'Enter Guardian Details').trigger('click')
      await flushPromises()
      expect(router.currentRoute.value.query).toEqual({ student: '1', show: 'edit-guardian' })
      expect(sheet(wrapper).props('student')).toMatchObject({ id: 1 })
      expect(sheet(wrapper).props('editGuardian')).toBe(true)
    })

    it('saves one guardian for several students from the popup', async () => {
      vi.mocked(saveGuardianDetails).mockResolvedValue(
        roster().map((s) => (s.id <= 2 ? { ...s, pg_first_name: 'Sam', pg_last_name: 'Park', pg_email: 'sam@example.com' } : s)),
      )
      const wrapper = await mountPage()
      await select(wrapper, 'Ava', 'Ben')
      await bulkButton(wrapper, 'Enter Guardian Details').trigger('click')
      const form = wrapper.get('form.supervisor-modal')
      expect(form.text()).toContain('Applies to 2 students.')
      const inputs = form.findAll('input')
      await inputs[0]!.setValue(' Sam ')
      await inputs[1]!.setValue('Park')
      await inputs[2]!.setValue('sam@example.com ')
      await form.trigger('submit')
      await flushPromises()
      expect(saveGuardianDetails).toHaveBeenCalledWith({
        student_ids: [1, 2],
        pg_first_name: 'Sam',
        pg_last_name: 'Park',
        pg_email: 'sam@example.com',
      })
      expect(wrapper.find('form.supervisor-modal').exists()).toBe(false)
      expect(wrapper.get('.supervisor-notice').text()).toBe('Guardian details saved.')
      // Both now have a guardian email, so they've moved to Pending Permission.
      expect(wrapper.text()).not.toContain('Ava Lee')
    })

    it('keeps the popup open with the reason when saving fails, and closes on Cancel', async () => {
      vi.mocked(saveGuardianDetails).mockRejectedValueOnce(new Error('That email is not valid.'))
      const wrapper = await mountPage()
      await select(wrapper, 'Ava', 'Ben')
      await bulkButton(wrapper, 'Enter Guardian Details').trigger('click')
      await wrapper.get('form.supervisor-modal').trigger('submit')
      await flushPromises()
      expect(wrapper.get('form.supervisor-modal .supervisor-error').text()).toBe('That email is not valid.')

      vi.mocked(saveGuardianDetails).mockRejectedValueOnce('offline')
      await wrapper.get('form.supervisor-modal').trigger('submit')
      await flushPromises()
      expect(wrapper.get('form.supervisor-modal .supervisor-error').text()).toBe('Guardian details could not be saved.')

      await buttonIn(wrapper.get('form.supervisor-modal'), 'Cancel').trigger('click')
      expect(wrapper.find('form.supervisor-modal').exists()).toBe(false)
    })

    it('reloads the list and says how many were saved after a guardian sheet is applied', async () => {
      const wrapper = await mountPage()
      wrapper.findComponent({ name: 'GuardianUploadDialog' }).vm.$emit('applied', 2)
      await flushPromises()
      expect(fetchSupervisedStudents).toHaveBeenCalledTimes(2)
      expect(wrapper.get('.supervisor-notice').text()).toBe('Guardian details saved for 2 students.')

      wrapper.findComponent({ name: 'GuardianUploadDialog' }).vm.$emit('applied', 1)
      await flushPromises()
      expect(wrapper.get('.supervisor-notice').text()).toBe('Guardian details saved for 1 student.')
    })
  })

  describe('consent forms', () => {
    it('views one form, and downloads one or all of them', async () => {
      const wrapper = await mountPage()
      await tab(wrapper, 'Fully Registered').trigger('click')
      await buttonIn(rowOf(wrapper, 'Eve Lee'), 'View').trigger('click')
      await flushPromises()
      expect(viewConsentDocuments).toHaveBeenCalledTimes(1)
      expect(withConsentSignatures).toHaveBeenCalledWith([expect.objectContaining({ id: 5 })])

      await buttonIn(rowOf(wrapper, 'Eve Lee'), 'Download').trigger('click')
      await flushPromises()
      expect(downloadConsentDocuments).toHaveBeenCalledWith([expect.objectContaining({ id: 5, signature: '' })])
      expect(wrapper.get('.supervisor-notice').text()).toBe('Downloaded BIOTech Futures consent PDF.')

      await buttonIn(wrapper, 'Download All Consent PDFs').trigger('click')
      await flushPromises()
      // Every fully registered student's form, in the roster's order.
      expect(downloadConsentDocuments).toHaveBeenLastCalledWith([
        expect.objectContaining({ id: 5 }),
        expect.objectContaining({ id: 6 }),
      ])
      expect(wrapper.get('.supervisor-notice').text()).toBe('Downloaded 2 BIOTech Futures consent PDFs.')
    })

    it('downloads the ticked forms from the selection bar', async () => {
      const wrapper = await mountPage()
      await tab(wrapper, 'Fully Registered').trigger('click')
      await select(wrapper, 'Finn')
      await bulkButton(wrapper, 'Download Selected PDFs').trigger('click')
      await flushPromises()
      expect(downloadConsentDocuments).toHaveBeenCalledWith([expect.objectContaining({ id: 6 })])
    })

    it('says when a consent PDF could not be made', async () => {
      vi.mocked(downloadConsentDocuments).mockRejectedValueOnce(new Error('pdf'))
      vi.mocked(viewConsentDocuments).mockRejectedValueOnce(new Error('pdf'))
      const wrapper = await mountPage()
      await tab(wrapper, 'Fully Registered').trigger('click')
      await buttonIn(rowOf(wrapper, 'Eve Lee'), 'Download').trigger('click')
      await flushPromises()
      expect(wrapper.get('.supervisor-error').text()).toBe('Consent PDF could not be generated.')

      await buttonIn(rowOf(wrapper, 'Eve Lee'), 'View').trigger('click')
      await flushPromises()
      expect(wrapper.get('.supervisor-error').text()).toBe('Consent PDF could not be generated.')
    })

    it('offers no Download All when nobody is fully registered', async () => {
      vi.mocked(fetchSupervisedStudents).mockResolvedValue(roster().filter((s) => !s.has_join_permission))
      const wrapper = await mountPage()
      await tab(wrapper, 'Fully Registered').trigger('click')
      expect(buttonIn(wrapper, 'Download All Consent PDFs')).toBeUndefined()
    })
  })

  describe("a student's panel", () => {
    it("opens from the student's name and closes again, keeping other query values", async () => {
      const wrapper = await mountPage({}, { tab: 'x' })
      await rowOf(wrapper, 'Ben Lee').get('.supervisor-name-btn').trigger('click')
      await flushPromises()
      expect(router.currentRoute.value.query).toEqual({ tab: 'x', student: '2' })
      expect(sheet(wrapper).props('student')).toMatchObject({ id: 2 })
      expect(sheet(wrapper).props('editGuardian')).toBe(false)

      sheet(wrapper).vm.$emit('close')
      await flushPromises()
      expect(router.currentRoute.value.query).toEqual({ tab: 'x' })
      expect(sheet(wrapper).props('student')).toBeNull()
    })

    it('opens from the address, so a refresh keeps it open', async () => {
      const wrapper = await mountPage({}, { student: '3', show: 'edit-guardian' })
      expect(sheet(wrapper).props('student')).toMatchObject({ id: 3 })
      expect(sheet(wrapper).props('editGuardian')).toBe(true)
    })

    it('puts what the panel saved back in the list', async () => {
      const wrapper = await mountPage({}, { student: '1' })
      sheet(wrapper).vm.$emit('updated', { ...roster()[0]!, first_name: 'Avery' })
      await flushPromises()
      expect(wrapper.text()).toContain('Avery Lee')

      sheet(wrapper).vm.$emit('saved', [student(9, 'Zoe')])
      await flushPromises()
      expect(wrapper.text()).toContain('Zoe Lee')
      expect(wrapper.text()).not.toContain('Ben Lee')
    })
  })
})
