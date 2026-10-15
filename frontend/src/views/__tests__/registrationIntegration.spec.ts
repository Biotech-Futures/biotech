import { mount, type VueWrapper } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  REGISTRATION_GATEWAY_KEY,
  type RegistrationGateway,
  type RegistrationGatewayResult,
} from '@/registration/registrationGateway'
import { createHttpRegistrationGateway } from '@/registration/httpRegistrationGateway'
import RegistrationPage from '@/views/RegistrationPage.vue'
import {
  createRegistrationForms,
  parseRegistrationCsv,
  registrationCsvTemplate,
  revalidateRegistrationCsvRows,
  type RegistrationForms,
  type StudentDetails,
} from '@/registration/registration'
import { resetCsrfToken, setCsrfToken } from '@/utils/csrf'

const studentCsv = () =>
  `${registrationCsvTemplate()}Alex,Morgan,alex@example.test,High School,10,Australia,NSW,Biomedical Innovations,Taylor,Morgan,taylor@example.test,Parent,,\r\n`

type PageSetup = {
  currentStep: number
  maxReachedStep: number
  journey: string
  forms: RegistrationForms
  clientErrors: Record<string, string>
  serverFieldErrors: Record<string, string>
  removeStudentTeammate: (index: number) => void
  removeSupervisorGroupStudent: (index: number) => void
  goToStep: (index: number) => void
  goBack: () => void
  changeJourney: () => void
  submitRegistration: () => Promise<void>
  handlePhoto: (student: StudentDetails, prefix: string, file: File) => void
}

const mountWithGateway = (gateway: RegistrationGateway) =>
  mount(RegistrationPage, {
    props: { mode: 'canonical' },
    attachTo: document.body,
    global: {
      plugins: [createPinia()],
      provide: { [REGISTRATION_GATEWAY_KEY as symbol]: gateway },
      stubs: {
        RouterLink: {
          props: ['to'],
          template: '<a :href="to"><slot /></a>',
        },
      },
    },
  })

const mountWithoutGateway = () =>
  mount(RegistrationPage, {
    props: { mode: 'canonical' },
    attachTo: document.body,
    global: {
      plugins: [createPinia()],
      stubs: {
        RouterLink: {
          props: ['to'],
          template: '<a :href="to"><slot /></a>',
        },
      },
    },
  })

const mountSupervisorWithGateway = (gateway: RegistrationGateway) =>
  mount(RegistrationPage, {
    props: { mode: 'supervisor' },
    attachTo: document.body,
    global: {
      plugins: [createPinia()],
      provide: { [REGISTRATION_GATEWAY_KEY as symbol]: gateway },
      stubs: {
        RouterLink: {
          props: ['to'],
          template: '<a :href="to"><slot /></a>',
        },
      },
    },
  })

const setupOf = (wrapper: VueWrapper) => wrapper.vm as unknown as PageSetup

const prepareStudent = async (wrapper: VueWrapper) => {
  const setup = setupOf(wrapper)
  setup.journey = 'student_individual'
  setup.currentStep = 3
  Object.assign(setup.forms.studentIndividual.student, {
    firstName: 'Alex',
    lastName: 'Morgan',
    email: 'alex@example.com',
    emailConfirm: 'alex@example.com',
    school: 'Example Secondary College',
    yearLevel: '10',
    country: 'Australia',
    state: 'NSW',
    interests: ['Biomedical Innovations'],
  })
  Object.assign(setup.forms.studentIndividual.student.guardian, {
    firstName: 'Taylor',
    lastName: 'Morgan',
    email: 'taylor@example.com',
    relationship: 'Parent',
  })
  Object.assign(setup.forms.studentIndividual.supervisor, {
    firstName: 'Sam',
    lastName: 'Teacher',
    email: 'sam@example.edu.au',
    school: 'Example Secondary College',
  })
  await wrapper.vm.$nextTick()
}

const prepareMentor = async (wrapper: VueWrapper) => {
  const setup = setupOf(wrapper)
  setup.journey = 'mentor'
  setup.currentStep = 4
  Object.assign(setup.forms.mentor, {
    firstName: 'Riley',
    lastName: 'Chen',
    email: 'riley@example.com',
    country: 'Australia',
    state: 'VIC',
    affiliation: 'industry',
    company: 'Bio Labs',
    interests: ['Biomedical Innovations'],
    capacity: '2',
    background: 'Biotechnology product development.',
    motivation: 'Support the next generation of researchers.',
    safeguardingJurisdiction: 'Victoria, Australia',
    complianceDeclaration: true,
    attestation: true,
  })
  await wrapper.vm.$nextTick()
}

const prepareSupervisorStudent = async (wrapper: VueWrapper) => {
  const setup = setupOf(wrapper)
  setup.journey = 'supervisor_individual'
  setup.currentStep = 1
  Object.assign(setup.forms.supervisorIndividual.student, {
    firstName: 'Alex',
    lastName: 'Morgan',
    email: 'alex@example.com',
    emailConfirm: 'alex@example.com',
    school: 'Example Secondary College',
    yearLevel: '10',
    country: 'Australia',
    interests: ['Biomedical Innovations'],
    state: 'NSW',
    guardianDeferred: true,
  })
  await wrapper.vm.$nextTick()
}

const submit = async (wrapper: VueWrapper) => {
  await wrapper.get('form').trigger('submit')
  await wrapper.vm.$nextTick()
}

const successfulGateway = (journey: 'student_individual' | 'mentor'): RegistrationGateway => ({
  async submit() {
    return {
      ok: true,
      receipt: {
        referenceCode: 'REG-1001',
        journey,
        studentCount: journey === 'mentor' ? 0 : 1,
        submittedAt: '2026-09-02T06:00:00.000Z',
      },
    }
  },
})

beforeEach(() => {
  vi.stubGlobal('scrollTo', vi.fn())
  resetCsrfToken()
})

afterEach(() => {
  document.body.innerHTML = ''
  vi.unstubAllGlobals()
})

describe('registration gateway UI integration', () => {
  it('submits a selected image through the real HTTP adapter with CSRF, invitation and actual file bytes', async () => {
    vi.stubGlobal(
      'URL',
      class extends URL {
        static createObjectURL() {
          return 'blob:selected-photo'
        }
        static revokeObjectURL() {}
      },
    )
    const endpoint = '/api/v1/registration'
    setCsrfToken('registration-csrf', window.location.origin)
    const send = vi.fn<typeof fetch>(
      async () =>
        new Response(
          JSON.stringify({
            reference_code: 'REG-HTTP',
            journey: 'student_individual',
            student_count: 1,
            created_at: '2026-10-11T05:00:00Z',
          }),
          { status: 201, headers: { 'Content-Type': 'application/json' } },
        ),
    )
    const gateway = createHttpRegistrationGateway({
      endpoint,
      fetchImpl: send,
      ensureCsrf: vi.fn(async () => true),
    })
    const wrapper = mountWithGateway(gateway)
    await wrapper.setProps({ invitationToken: 'signed-invitation' })
    await prepareStudent(wrapper)
    const setup = setupOf(wrapper)
    const photo = new File(['actual image bytes'], 'profile.png', { type: 'image/png' })
    setup.handlePhoto(setup.forms.studentIndividual.student, 'studentIndividual.student', photo)
    await wrapper.vm.$nextTick()
    await submit(wrapper)
    await vi.waitFor(() => expect(wrapper.text()).toContain('REG-HTTP'))
    const [url, init] = send.mock.calls[0]!
    expect(url).toBe(endpoint)
    expect(init?.credentials).toBe('include')
    const headers = init?.headers as Headers
    expect(headers.get('X-CSRFToken')).toBe('registration-csrf')
    expect(headers.get('X-Registration-Invitation')).toBe('signed-invitation')
    expect(headers.get('Content-Type')).toBeNull()
    expect(headers.get('Idempotency-Key')).toMatch(/^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i)
    const body = init?.body
    if (!(body instanceof FormData)) throw new Error('Expected registration multipart data')
    const serialized = body.get('request')
    if (typeof serialized !== 'string') throw new Error('Expected JSON request part')
    expect(JSON.parse(serialized)).toMatchObject({
      journey: 'student_individual',
      payload: {
        students: [{ email: 'alex@example.com' }],
        source: { method: 'student_individual' },
      },
    })
    expect(body.get('students.0')).toBeInstanceOf(File)
    wrapper.unmount()
  })

  it('requires the group creator guardian but permits deferred contacts for other members', async () => {
    const send = vi.fn<RegistrationGateway['submit']>().mockResolvedValue({
      ok: true,
      receipt: {
        referenceCode: 'REG-GROUP',
        journey: 'student_team',
        studentCount: 2,
        submittedAt: '2026-10-11T05:00:00Z',
      },
    })
    const wrapper = mountWithGateway({ submit: send })
    await prepareStudent(wrapper)
    const setup = setupOf(wrapper)
    setup.journey = 'student_team'
    setup.currentStep = 3
    setup.forms.studentTeam.creator = {
      ...createRegistrationForms().studentTeam.creator,
      ...setup.forms.studentIndividual.student,
      guardianDeferred: true,
      guardian: createRegistrationForms().studentTeam.creator.guardian,
    }
    setup.forms.studentTeam.supervisor = { ...setup.forms.studentIndividual.supervisor }
    setup.forms.studentTeam.interests = ['Water & Energy Tech']
    Object.assign(setup.forms.studentTeam.teammates[0]!, {
      firstName: 'Jamie',
      lastName: 'Student',
      email: 'jamie@example.test',
      emailConfirm: 'jamie@example.test',
    })
    await wrapper.vm.$nextTick()
    await submit(wrapper)
    expect(send).not.toHaveBeenCalled()
    expect(setup.currentStep).toBe(1)
    expect(wrapper.text()).toContain('Enter the guardian first name.')
    setup.forms.studentTeam.creator.guardianDeferred = false
    setup.forms.studentTeam.creator.guardian = { ...setup.forms.studentIndividual.student.guardian }
    setup.currentStep = 3
    await wrapper.vm.$nextTick()
    await submit(wrapper)
    await vi.waitFor(() => expect(send).toHaveBeenCalledOnce())
    expect(send.mock.calls[0]![0]).toMatchObject({
      journey: 'student_team',
      payload: { interests: ['Water & Energy Tech'], teammates: [{ guardianDeferred: true }] },
    })
    expect(wrapper.text()).toContain('REG-GROUP')
    wrapper.unmount()
  })

  it('requires a separate acknowledgement for each warning', async () => {
    const send = vi.fn<RegistrationGateway['submit']>().mockResolvedValue({
      ok: false,
      message: 'Check both details.',
      warnings: [
        {
          code: 'school_requires_confirmation',
          field: 'studentIndividual.student.school',
          overrideField: 'students.0.overrides.ConfirmSchoolOverride',
          message: 'Confirm this school.',
        },
        {
          code: 'name_email_requires_confirmation',
          field: 'studentIndividual.student.email',
          overrideField: 'students.0.overrides.ConfirmNameEmailOverride',
          message: 'Confirm this address.',
        },
      ],
    })
    const wrapper = mountWithGateway({ submit: send })
    await prepareStudent(wrapper)
    await submit(wrapper)
    const checkboxes = wrapper.findAll('.registration-warnings input')
    expect(checkboxes).toHaveLength(2)
    await checkboxes[0]!.setValue(true)
    await submit(wrapper)
    expect(send).toHaveBeenCalledOnce()
    await checkboxes[1]!.setValue(true)
    await submit(wrapper)
    expect(send).toHaveBeenCalledTimes(2)
    expect(send.mock.calls[1]![1]?.overrides).toEqual({
      'students.0.overrides.ConfirmSchoolOverride': true,
      'students.0.overrides.ConfirmNameEmailOverride': true,
    })
    wrapper.unmount()
  })

  it('requires explicit warning acknowledgment and resubmits with a new key', async () => {
    const send = vi
      .fn<RegistrationGateway['submit']>()
      .mockResolvedValueOnce({
        ok: false,
        message: 'Please check.',
        warnings: [
          {
            code: 'school_requires_confirmation',
            field: 'studentIndividual.student.school',
            overrideField: 'students.0.overrides.ConfirmSchoolOverride',
            message: 'Confirm this school.',
          },
        ],
      })
      .mockResolvedValueOnce({
        ok: true,
        receipt: {
          referenceCode: 'REG-WARN',
          journey: 'student_individual',
          studentCount: 1,
          submittedAt: '2026-10-11T05:00:00Z',
        },
      })
    const wrapper = mountWithGateway({ submit: send })
    await prepareStudent(wrapper)
    await submit(wrapper)
    expect(wrapper.find('.registration-warnings').exists()).toBe(true)
    expect(wrapper.find('.success-panel').exists()).toBe(false)
    await submit(wrapper)
    expect(send).toHaveBeenCalledTimes(1)
    await wrapper.get('.registration-warnings input').setValue(true)
    await submit(wrapper)
    expect(send).toHaveBeenCalledTimes(2)
    expect(send.mock.calls[1]![1]?.overrides).toEqual({
      'students.0.overrides.ConfirmSchoolOverride': true,
    })
    expect(send.mock.calls[1]![1]?.idempotencyKey).not.toBe(send.mock.calls[0]![1]?.idempotencyKey)
    expect(wrapper.find('.success-panel').exists()).toBe(true)
    wrapper.unmount()
  })

  it('clears acknowledged warnings when registration data changes', async () => {
    const send = vi.fn<RegistrationGateway['submit']>().mockResolvedValue({
      ok: false,
      message: 'Please check.',
      warnings: [
        {
          code: 'school_requires_confirmation',
          field: 'studentIndividual.student.school',
          overrideField: 'students.0.overrides.ConfirmSchoolOverride',
          message: 'Confirm this school.',
        },
      ],
    })
    const wrapper = mountWithGateway({ submit: send })
    await prepareStudent(wrapper)
    await submit(wrapper)
    await wrapper.get('.registration-warnings input').setValue(true)
    setupOf(wrapper).forms.studentIndividual.student.school = 'Corrected High School'
    await wrapper.vm.$nextTick()
    expect(wrapper.find('.registration-warnings').exists()).toBe(false)
    await submit(wrapper)
    expect(send.mock.calls[1]![1]?.overrides).toEqual({})
    wrapper.unmount()
  })

  it('edits an invalid uploaded row and submits only the corrected, included values', async () => {
    const send = vi.fn<RegistrationGateway['submit']>().mockResolvedValue({
      ok: true,
      receipt: {
        referenceCode: 'CSV-1001',
        journey: 'supervisor_csv',
        studentCount: 1,
        submittedAt: '2026-10-07T06:00:00Z',
      },
    })
    const wrapper = mountSupervisorWithGateway({ submit: send })
    const setup = setupOf(wrapper)
    setup.journey = 'supervisor_csv'
    setup.currentStep = 1
    setup.forms.supervisorCsv.fileName = 'students.csv'
    const uploadedRows = parseRegistrationCsv(studentCsv()).rows
    uploadedRows[0].values.email = 'invalid'
    setup.forms.supervisorCsv.rows = revalidateRegistrationCsvRows(uploadedRows)
    await wrapper.vm.$nextTick()
    await wrapper.get('form').trigger('submit')
    expect(setup.currentStep).toBe(1)
    expect(send).not.toHaveBeenCalled()
    await wrapper.get('button[aria-label="Edit row 2"]').trigger('click')
    await wrapper.get('#csv-row-2-email').setValue('corrected@example.test')
    await wrapper.get('#csv-row-2-year_level').setValue('11')
    await wrapper.get('#csv-row-2-first_name').setValue('Corrected Alex')
    expect(setup.forms.supervisorCsv.rows[0].category).toBe('valid')
    expect(wrapper.text()).not.toContain('Student email format is invalid.')
    const excluded = {
      ...setup.forms.supervisorCsv.rows[0],
      rowNumber: 3,
      values: { ...setup.forms.supervisorCsv.rows[0].values, email: 'still-invalid' },
    }
    setup.forms.supervisorCsv.rows.push(excluded)
    setup.forms.supervisorCsv.excludedRowNumbers = [3]
    await wrapper.vm.$nextTick()
    expect(wrapper.get('.form-footer button[type="submit"]').attributes('disabled')).toBeDefined()
    await wrapper.get('form').trigger('submit')
    expect(setup.currentStep).toBe(1)
    expect(send).not.toHaveBeenCalled()
    await wrapper.get('.csv-editor-footer button').trigger('click')
    await wrapper.get('form').trigger('submit')
    expect(setup.currentStep).toBe(2)
    await wrapper.get('form').trigger('submit')
    await vi.waitFor(() => expect(send).toHaveBeenCalledOnce())
    expect(send.mock.calls[0]![0]).toMatchObject({
      journey: 'supervisor_csv',
      payload: {
        fileName: 'students.csv',
        rows: [
          {
            rowNumber: 2,
            values: {
              first_name: 'Corrected Alex',
              email: 'corrected@example.test',
              year_level: '11',
            },
          },
        ],
      },
    })
    expect(wrapper.text()).toContain('CSV-1001')
    wrapper.unmount()
  })

  it('puts row confirmation after the fields and prevents all submission and step bypasses while editing', async () => {
    const send = vi.fn<RegistrationGateway['submit']>().mockResolvedValue({
      ok: true,
      receipt: {
        referenceCode: 'CSV-CONFIRMED',
        journey: 'supervisor_csv',
        studentCount: 1,
        submittedAt: '2026-10-07T06:00:00Z',
      },
    })
    const wrapper = mountSupervisorWithGateway({ submit: send })
    const setup = setupOf(wrapper)
    setup.journey = 'supervisor_csv'
    setup.currentStep = 1
    setup.maxReachedStep = 2
    setup.forms.supervisorCsv.fileName = 'students.csv'
    setup.forms.supervisorCsv.rows = parseRegistrationCsv(studentCsv()).rows
    await wrapper.vm.$nextTick()
    await wrapper.get('#csv-edit-2').trigger('click')
    const editor = wrapper.get('#csv-row-editor')
    const confirmation = editor.get('.csv-editor-footer button')
    expect(confirmation.text()).toBe('Done editing')
    expect(confirmation.attributes('type')).toBe('button')
    expect(
      editor.get('.csv-fields').element.compareDocumentPosition(confirmation.element) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy()
    expect(wrapper.get('.form-footer button[type="submit"]').attributes('disabled')).toBeDefined()
    expect(
      wrapper
        .findAll('.step-navigation button')
        .every((button) => button.attributes('disabled') !== undefined),
    ).toBe(true)
    expect(wrapper.get('.change-journey').attributes('disabled')).toBeDefined()
    setup.goToStep(2)
    setup.goBack()
    setup.changeJourney()
    expect(setup.currentStep).toBe(1)
    expect(setup.journey).toBe('supervisor_csv')
    setup.currentStep = 2
    await setup.submitRegistration()
    expect(send).not.toHaveBeenCalled()
    expect(setup.currentStep).toBe(1)
    await confirmation.trigger('click')
    expect(wrapper.get('.form-footer button[type="submit"]').attributes('disabled')).toBeUndefined()
    await wrapper.get('form').trigger('submit')
    await wrapper.get('form').trigger('submit')
    await vi.waitFor(() => expect(send).toHaveBeenCalledOnce())
    expect(wrapper.text()).toContain('CSV-CONFIRMED')
    wrapper.unmount()
  })

  it('allows duplicate uploads into preview and updates both rows when corrected', async () => {
    const wrapper = mountSupervisorWithGateway({ submit: vi.fn() })
    const setup = setupOf(wrapper)
    setup.journey = 'supervisor_csv'
    const row = parseRegistrationCsv(studentCsv()).rows[0]
    setup.forms.supervisorCsv.fileName = 'duplicates.csv'
    setup.forms.supervisorCsv.rows = [row, { ...row, rowNumber: 3, values: { ...row.values } }]
    await wrapper.vm.$nextTick()
    await wrapper.get('form').trigger('submit')
    expect(setup.currentStep).toBe(1)
    await wrapper.get('button[aria-label="Edit row 3"]').trigger('click')
    await wrapper.get('#csv-row-3-email').setValue('second@example.test')
    expect(setup.forms.supervisorCsv.rows.map((entry) => entry.category)).toEqual([
      'valid',
      'valid',
    ])
    await wrapper.get('#csv-row-3-email').setValue(row.values.email)
    expect(setup.forms.supervisorCsv.rows.map((entry) => entry.category)).toEqual([
      'invalid',
      'invalid',
    ])
    await wrapper.get('#csv-row-3-email').setValue('second@example.test')
    await wrapper
      .findAll('button')
      .find((button) => button.text() === 'Done editing')!
      .trigger('click')
    await wrapper.get('form').trigger('submit')
    expect(setup.currentStep).toBe(2)
    wrapper.unmount()
  })

  it('shows backend CSV errors on the original row after exclusions and supports retrying edits', async () => {
    const send = vi.fn<RegistrationGateway['submit']>().mockResolvedValue({
      ok: false,
      message: 'Registration needs corrections.',
      fieldErrors: {
        'supervisorCsv.rows.0.email': 'Choose a different email.',
        'supervisorCsv.rows.1.school': 'Use the full school name.',
      },
    })
    const wrapper = mountSupervisorWithGateway({ submit: send })
    const setup = setupOf(wrapper)
    const row = parseRegistrationCsv(studentCsv()).rows[0]
    setup.journey = 'supervisor_csv'
    setup.currentStep = 2
    setup.forms.supervisorCsv.fileName = 'students.csv'
    setup.forms.supervisorCsv.rows = [
      { ...row, values: { ...row.values, email: 'excluded@example.test' } },
      { ...row, rowNumber: 3, values: { ...row.values } },
      { ...row, rowNumber: 4, values: { ...row.values, email: 'another@example.test' } },
    ]
    setup.forms.supervisorCsv.excludedRowNumbers = [2]
    await wrapper.vm.$nextTick()
    await wrapper.get('form').trigger('submit')
    await vi.waitFor(() => expect(wrapper.find('#csv-row-3-email').exists()).toBe(true))
    expect(wrapper.get('#csv-row-3-email').attributes('aria-invalid')).toBe('true')
    expect(wrapper.text()).toContain('Choose a different email.')
    await wrapper.get('#csv-row-3-email').setValue('retry@example.test')
    expect(wrapper.text()).not.toContain('Choose a different email.')
    expect(wrapper.text()).toContain('Use the full school name.')
    expect(setup.forms.supervisorCsv.excludedRowNumbers).toEqual([2])
    await wrapper.findAll('tbody tr')[1].get('input[type="checkbox"]').setValue(true)
    expect(setup.serverFieldErrors).toEqual({
      'supervisorCsv.rows.0.school': 'Use the full school name.',
    })
    await wrapper.get('#csv-edit-4').trigger('click')
    expect(wrapper.get('#csv-row-4-school').attributes('aria-invalid')).toBe('true')
    wrapper.unmount()
  })

  it('keeps repaired excluded rows excluded and restores duplicate checks on inclusion', async () => {
    const wrapper = mountSupervisorWithGateway({ submit: vi.fn() })
    const setup = setupOf(wrapper)
    const row = parseRegistrationCsv(studentCsv()).rows[0]
    setup.journey = 'supervisor_csv'
    setup.currentStep = 1
    setup.forms.supervisorCsv.rows = revalidateRegistrationCsvRows([
      row,
      { ...row, rowNumber: 3, values: { ...row.values } },
    ])
    await wrapper.vm.$nextTick()
    await wrapper.findAll('tbody tr')[1].get('input[type="checkbox"]').setValue(true)
    expect(setup.forms.supervisorCsv.rows[0].category).toBe('valid')
    await wrapper.get('#csv-edit-3').trigger('click')
    await wrapper.get('#csv-row-3-first_name').setValue('Repaired student')
    expect(setup.forms.supervisorCsv.excludedRowNumbers).toEqual([3])
    expect(wrapper.get('#csv-row-3-email').attributes('type')).toBe('text')
    await wrapper.findAll('tbody tr')[1].get('input[type="checkbox"]').setValue(false)
    expect(setup.forms.supervisorCsv.rows.map((entry) => entry.category)).toEqual([
      'invalid',
      'invalid',
    ])
    expect(setup.forms.supervisorCsv.excludedRowNumbers).toEqual([])
    wrapper.unmount()
  })

  it('opens a fresh individual student form directly after supervisor registration', async () => {
    const send = vi.fn<RegistrationGateway['submit']>().mockResolvedValue({
      ok: true,
      receipt: {
        referenceCode: 'REG-2001',
        journey: 'supervisor_individual',
        studentCount: 1,
        submittedAt: '2026-10-07T06:00:00Z',
      },
    })
    const wrapper = mountSupervisorWithGateway({ submit: send })
    await prepareSupervisorStudent(wrapper)
    await submit(wrapper)
    await vi.waitFor(() => expect(wrapper.text()).toContain('REG-2001'))
    await wrapper
      .findAll('button')
      .find((button) => button.text() === 'Register another student')!
      .trigger('click')
    expect(setupOf(wrapper).journey).toBe('supervisor_individual')
    expect(setupOf(wrapper).currentStep).toBe(0)
    expect(wrapper.get('#supervisorIndividual-student-email').element).toHaveProperty('value', '')
    expect(wrapper.text()).not.toContain('REG-2001')
    expect(wrapper.find('.pathway-choices').exists()).toBe(false)
    await prepareSupervisorStudent(wrapper)
    setupOf(wrapper).forms.supervisorIndividual.student.email = 'second@example.com'
    setupOf(wrapper).forms.supervisorIndividual.student.emailConfirm = 'second@example.com'
    await submit(wrapper)
    await vi.waitFor(() => expect(send).toHaveBeenCalledTimes(2))
    expect(send.mock.calls[0]![1]!.idempotencyKey).not.toBe(send.mock.calls[1]![1]!.idempotencyKey)
    wrapper.unmount()
  })
  it('reports unavailable submission when no gateway is configured', async () => {
    const wrapper = mountWithoutGateway()
    await prepareStudent(wrapper)
    await submit(wrapper)

    await vi.waitFor(() =>
      expect(wrapper.text()).toContain(
        'Registration submission is not configured in this environment.',
      ),
    )
    expect(wrapper.text()).not.toContain('Registration details received')
  })

  it('shows loading and then the guardian-consent-required student outcome', async () => {
    let resolveResult!: (result: RegistrationGatewayResult) => void
    const gateway: RegistrationGateway = {
      submit: () =>
        new Promise((resolve) => {
          resolveResult = resolve
        }),
    }
    const wrapper = mountWithGateway(gateway)
    await prepareStudent(wrapper)
    await submit(wrapper)

    expect(wrapper.text()).toContain('Submitting…')
    resolveResult({
      ok: true,
      receipt: {
        referenceCode: 'REG-1001',
        journey: 'student_individual',
        studentCount: 1,
        submittedAt: '2026-09-02T06:00:00.000Z',
      },
    })
    await vi.waitFor(() => expect(wrapper.text()).toContain('Registration details received'))
    expect(wrapper.text()).toContain('Guardian consent is still required before full registration')
  })

  it('returns student email errors to the rendered first-step field and focuses it', async () => {
    const gateway: RegistrationGateway = {
      async submit() {
        return {
          ok: false,
          message: 'Review the highlighted information.',
          fieldErrors: { 'studentIndividual.student.email': 'This address is already registered.' },
        }
      },
    }
    const wrapper = mountWithGateway(gateway)
    await prepareStudent(wrapper)
    await submit(wrapper)

    await vi.waitFor(() => expect(setupOf(wrapper).currentStep).toBe(0))
    const email = wrapper.get('#studentIndividual-student-email')
    expect(email.attributes('aria-invalid')).toBe('true')
    expect(document.activeElement).toBe(email.element)
    expect(wrapper.text()).toContain('This address is already registered.')
    expect(wrapper.text()).toContain('Review the highlighted information.')
    expect(wrapper.text()).not.toContain('Registration details received')
  })

  it('preserves later server errors while an earlier step is corrected', async () => {
    const gateway: RegistrationGateway = {
      async submit() {
        return {
          ok: false,
          message: 'Review the highlighted information.',
          fieldErrors: {
            'studentIndividual.student.email': 'Choose another student email.',
            'studentIndividual.supervisor.school': 'Choose a recognized school.',
          },
        }
      },
    }
    const wrapper = mountWithGateway(gateway)
    await prepareStudent(wrapper)
    await submit(wrapper)
    await vi.waitFor(() => expect(setupOf(wrapper).currentStep).toBe(0))

    setupOf(wrapper).forms.studentIndividual.student.email = 'alex.new@example.com'
    setupOf(wrapper).forms.studentIndividual.student.emailConfirm = 'alex.new@example.com'
    await submit(wrapper)
    expect(setupOf(wrapper).currentStep).toBe(1)

    setupOf(wrapper).currentStep = 2
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).toContain('Choose a recognized school.')
    expect(wrapper.get('#student-individual-supervisor-school').attributes('aria-invalid')).toBe(
      'true',
    )
    expect(setupOf(wrapper).serverFieldErrors['studentIndividual.student.email']).toBeUndefined()
  })

  it('returns later-step mentor errors to their rendered contribution field', async () => {
    const gateway: RegistrationGateway = {
      async submit() {
        return {
          ok: false,
          message: 'Review the highlighted information.',
          fieldErrors: { 'mentor.background': 'Add more detail about your experience.' },
        }
      },
    }
    const wrapper = mountWithGateway(gateway)
    await prepareMentor(wrapper)
    await submit(wrapper)

    await vi.waitFor(() => expect(setupOf(wrapper).currentStep).toBe(2))
    const background = wrapper.get('#mentor-background')
    expect(background.attributes('aria-invalid')).toBe('true')
    expect(document.activeElement).toBe(background.element)
    expect(wrapper.text()).toContain('Add more detail about your experience.')
  })

  it('returns supervisor server errors to the visible reindexed student step', async () => {
    const gateway: RegistrationGateway = {
      async submit() {
        return {
          ok: false,
          message: 'Review the highlighted information.',
          fieldErrors: {
            'supervisorIndividual.student.email': 'This student address is already registered.',
          },
        }
      },
    }
    const wrapper = mountSupervisorWithGateway(gateway)
    await prepareSupervisorStudent(wrapper)
    await submit(wrapper)

    await vi.waitFor(() => expect(setupOf(wrapper).currentStep).toBe(0))
    const email = wrapper.get('#supervisorIndividual-student-email')
    expect(email.attributes('aria-invalid')).toBe('true')
    expect(document.activeElement).toBe(email.element)
    expect(wrapper.text()).toContain('This student address is already registered.')
  })

  it('summarizes unknown server fields without blocking an authoritative retry', async () => {
    const submitMock = vi
      .fn<RegistrationGateway['submit']>()
      .mockResolvedValueOnce({
        ok: false,
        message: 'Review the registration response.',
        fieldErrors: { 'registration.unmapped': 'The server could not map this field.' },
      })
      .mockResolvedValueOnce(
        await successfulGateway('student_individual').submit({
          journey: 'student_individual',
          payload: {},
        } as never),
      )
    const gateway: RegistrationGateway = { submit: submitMock }
    const wrapper = mountWithGateway(gateway)
    await prepareStudent(wrapper)
    await submit(wrapper)

    await vi.waitFor(() => expect(wrapper.text()).toContain('The server could not map this field.'))
    expect(setupOf(wrapper).currentStep).toBe(3)
    expect(document.activeElement).toBe(wrapper.get('.error-summary').element)

    await submit(wrapper)
    await vi.waitFor(() => expect(wrapper.text()).toContain('Registration details received'))
    expect(submitMock).toHaveBeenCalledTimes(2)
    expect(submitMock.mock.calls[1]![1]?.idempotencyKey).toBe(
      submitMock.mock.calls[0]![1]?.idempotencyKey,
    )
  })

  it('uses a new UUID retry key after correcting the submitted payload', async () => {
    const send = vi.fn<RegistrationGateway['submit']>().mockResolvedValue({
      ok: false,
      message: 'The service is temporarily unavailable.',
    })
    const wrapper = mountWithGateway({ submit: send })
    await prepareStudent(wrapper)
    await submit(wrapper)
    await vi.waitFor(() => expect(send).toHaveBeenCalledOnce())
    setupOf(wrapper).forms.studentIndividual.student.school = 'Corrected School'
    await wrapper.vm.$nextTick()
    await submit(wrapper)
    await vi.waitFor(() => expect(send).toHaveBeenCalledTimes(2))
    for (const [, options] of send.mock.calls) {
      expect(options?.idempotencyKey).toMatch(/^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i)
    }
    expect(send.mock.calls[1]![1]?.idempotencyKey).not.toBe(send.mock.calls[0]![1]?.idempotencyKey)
    wrapper.unmount()
  })

  it('reindexes client and server errors when dynamic students are removed', async () => {
    const wrapper = mountWithGateway(successfulGateway('student_individual'))
    const setup = setupOf(wrapper)
    setup.forms.studentTeam.teammates.push({
      ...setup.forms.studentTeam.teammates[0],
    })
    setup.clientErrors['studentTeam.teammates.0.email'] = 'Removed client error.'
    setup.clientErrors['studentTeam.teammates.1.email'] = 'Remaining client error.'
    setup.serverFieldErrors['studentTeam.teammates.0.email'] = 'Removed server error.'
    setup.serverFieldErrors['studentTeam.teammates.1.email'] = 'Remaining server error.'

    setup.removeStudentTeammate(0)

    expect(setup.clientErrors['studentTeam.teammates.0.email']).toBe('Remaining client error.')
    expect(setup.serverFieldErrors['studentTeam.teammates.0.email']).toBe('Remaining server error.')
    expect(setup.clientErrors['studentTeam.teammates.1.email']).toBeUndefined()
    expect(setup.serverFieldErrors['studentTeam.teammates.1.email']).toBeUndefined()

    setup.forms.supervisorGroup.students.push({
      ...setup.forms.supervisorGroup.students[0],
    })
    setup.clientErrors['supervisorGroup.students.2.email'] = 'Remaining group client error.'
    setup.serverFieldErrors['supervisorGroup.students.2.email'] = 'Remaining group server error.'

    setup.removeSupervisorGroupStudent(0)

    expect(setup.clientErrors['supervisorGroup.students.1.email']).toBe(
      'Remaining group client error.',
    )
    expect(setup.serverFieldErrors['supervisorGroup.students.1.email']).toBe(
      'Remaining group server error.',
    )
    expect(setup.clientErrors['supervisorGroup.students.2.email']).toBeUndefined()
    expect(setup.serverFieldErrors['supervisorGroup.students.2.email']).toBeUndefined()
  })

  it('recovers from a failed submission without losing entered data', async () => {
    const submitMock = vi
      .fn<RegistrationGateway['submit']>()
      .mockResolvedValueOnce({ ok: false, message: 'The service is temporarily unavailable.' })
      .mockResolvedValueOnce(
        await successfulGateway('student_individual').submit({
          journey: 'student_individual',
          payload: {},
        } as never),
      )
    const wrapper = mountWithGateway({ submit: submitMock })
    await prepareStudent(wrapper)
    await submit(wrapper)
    await vi.waitFor(() => expect(wrapper.text()).toContain('temporarily unavailable'))
    expect(setupOf(wrapper).forms.studentIndividual.student.email).toBe('alex@example.com')

    await submit(wrapper)
    await vi.waitFor(() => expect(wrapper.text()).toContain('Registration details received'))
    expect(submitMock).toHaveBeenCalledTimes(2)
  })

  it('shows the mentor Pending Review outcome', async () => {
    const wrapper = mountWithGateway(successfulGateway('mentor'))
    await prepareMentor(wrapper)
    await submit(wrapper)

    await vi.waitFor(() => expect(wrapper.text()).toContain('Application received'))
    expect(wrapper.text()).toContain('pending safeguarding and administrator review')
  })
})
