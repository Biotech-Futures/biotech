import { mount, type VueWrapper } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  REGISTRATION_GATEWAY_KEY,
  type RegistrationGateway,
  type RegistrationGatewayResult,
} from '@/registration/registrationGateway'
import RegistrationDemoPage from '@/views/RegistrationDemoPage.vue'

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
  }
}

const mountWithGateway = (gateway: RegistrationGateway) =>
  mount(RegistrationDemoPage, {
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

  it('keeps unknown server field errors summarized on the review step', async () => {
    const gateway: RegistrationGateway = {
      async submit() {
        return {
          ok: false,
          message: 'Review the registration response.',
          fieldErrors: { 'registration.unmapped': 'The server could not map this field.' },
        }
      },
    }
    const wrapper = mountWithGateway(gateway)
    await prepareStudent(wrapper)
    await submit(wrapper)

    await vi.waitFor(() => expect(wrapper.text()).toContain('The server could not map this field.'))
    expect(setupOf(wrapper).currentStep).toBe(3)
    expect(document.activeElement).toBe(wrapper.get('.error-summary').element)
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
