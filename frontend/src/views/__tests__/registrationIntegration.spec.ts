import { mount, type VueWrapper } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  REGISTRATION_GATEWAY_KEY,
  type RegistrationGateway,
  type RegistrationGatewayResult,
} from '@/registration/registrationGateway'
import RegistrationPage from '@/views/RegistrationPage.vue'

type PageSetup = {
  currentStep: number
  journey: string
  forms: {
    studentIndividual: {
      student: {
        firstName: string
        lastName: string
        email: string
        emailConfirm: string
        school: string
        yearLevel: string
        country: string
        state: string
        interests: string[]
        guardian: {
          firstName: string
          lastName: string
          email: string
          relationship: string
        }
      }
      supervisor: {
        firstName: string
        lastName: string
        email: string
        school: string
      }
    }
    mentor: {
      firstName: string
      lastName: string
      email: string
      country: string
      state: string
      affiliation: string
      company: string
      interests: string[]
      capacity: string
      background: string
      motivation: string
      safeguardingJurisdiction: string
      complianceDeclaration: boolean
      attestation: boolean
    }
    supervisorIndividual: {
      student: {
        firstName: string
        lastName: string
        email: string
        emailConfirm: string
        school: string
        yearLevel: string
        country: string
        interests: string[]
        guardianDeferred: boolean
      }
    }
    studentTeam: {
      teammates: Array<Record<string, unknown>>
    }
    supervisorGroup: {
      students: Array<Record<string, unknown>>
    }
  }
  clientErrors: Record<string, string>
  serverFieldErrors: Record<string, string>
  removeStudentTeammate: (index: number) => void
  removeSupervisorGroupStudent: (index: number) => void
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
  setup.currentStep = 2
  Object.assign(setup.forms.supervisorIndividual.student, {
    firstName: 'Alex',
    lastName: 'Morgan',
    email: 'alex@example.com',
    emailConfirm: 'alex@example.com',
    school: 'Example Secondary College',
    yearLevel: '10',
    country: 'Australia',
    interests: ['Biomedical Innovations'],
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
})

afterEach(() => {
  document.body.innerHTML = ''
  vi.unstubAllGlobals()
})

describe('registration gateway UI integration', () => {
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
