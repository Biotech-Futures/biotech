// The registration page's email boxes, checked as each is left
// (registration/emailFieldCheck): a hard problem is the box's error and keeps
// its step from going on; a warning is shown under it, its tick Submit's.
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import RegistrationPage from '@/views/RegistrationPage.vue'
import { configuredRegistrationGateway } from '@/registration/httpRegistrationGateway'
import { REGISTRATION_GATEWAY_KEY } from '@/registration/registrationGateway'
import { resetCsrfToken } from '@/utils/csrf'

vi.mock('vue-router', async (importOriginal) => ({
  ...(await importOriginal<typeof import('vue-router')>()),
  useRouter: () => ({ push: vi.fn() }),
}))

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status })

// The field check's answers, by address (or a School box's school); anything else is fine.
let answers: Record<string, unknown> = {}
// Each check the page asked for, as sent.
interface CheckRequest {
  journey?: string
  fields: Array<{ field: string; email?: string; school?: string; overrides?: Record<string, boolean> }>
}
let checks: CheckRequest[] = []

beforeEach(() => {
  sessionStorage.clear()
  resetCsrfToken()
  answers = {}
  checks = []
  vi.stubGlobal('scrollTo', vi.fn())
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    const path = String(url)
    if (path.includes('/services/csrf/')) return json({ csrfToken: 'csrf' })
    if (path.includes('/registration/email-check/field/')) {
      const body = JSON.parse(String(init?.body)) as CheckRequest
      checks.push(body)
      const field = body.fields[0]!
      return json({ results: { [field.field]: answers[field.email || field.school || ''] ?? { ok: true } } })
    }
    if (path.includes('/registration/') && init?.method === 'POST') {
      return json({ error: 'Stop here.', code: 'invalid', request_id: 'x' }, 400)
    }
    return json({})
  }))
})

afterEach(() => vi.unstubAllGlobals())

const mountPage = () =>
  mount(RegistrationPage, {
    props: { mode: 'canonical' },
    global: {
      plugins: [createPinia()],
      // The page's own gateway, over the stubbed network.
      provide: { [REGISTRATION_GATEWAY_KEY as symbol]: configuredRegistrationGateway(undefined, 'http://localhost:8000') },
      stubs: { RouterLink: { props: ['to'], template: '<a :href="to"><slot /></a>' } },
    },
  })

const clickButton = async (wrapper: VueWrapper, label: string) => {
  const button = wrapper.findAll('button').find((candidate) => candidate.text().includes(label))
  expect(button, `button containing "${label}"`).toBeDefined()
  await button!.trigger('click')
  await flushPromises()
}

const leave = async (wrapper: VueWrapper, selector: string, value: string) => {
  await wrapper.get(selector).setValue(value)
  await wrapper.get(selector).trigger('blur')
  await flushPromises()
}

// Continue: the step's form, submitted.
const continueStep = async (wrapper: VueWrapper) => {
  await wrapper.get('form').trigger('submit')
  await flushPromises()
}

const step = (wrapper: VueWrapper) => (wrapper.vm as unknown as { currentStep: number }).currentStep

describe('a student registering on their own', () => {
  const start = async () => {
    const wrapper = mountPage()
    await clickButton(wrapper, 'Student')
    await clickButton(wrapper, "I don't have a group")
    await wrapper.get('#studentIndividual-student-firstName').setValue('Jo')
    await wrapper.get('#studentIndividual-student-lastName').setValue('Lee')
    return wrapper
  }

  it('shows a hard problem as the box leaves, and stays on the step until it is corrected', async () => {
    answers['taken@example.test'] = {
      ok: false, severity: 'hard', code: 'email_taken', message: 'An account with this email already exists.',
    }
    const wrapper = await start()

    await leave(wrapper, '#studentIndividual-student-email', 'taken@example.test')
    expect(checks[0]).toMatchObject({
      journey: 'student_individual',
      fields: [{
        field: 'studentIndividual.student.email', kind: 'student', email: 'taken@example.test', student: 0,
        firstName: 'Jo', lastName: 'Lee',
      }],
    })
    const field = () => wrapper.get('#studentIndividual-student-email').element.closest('.registration-field')!
    expect(field().textContent).toContain('An account with this email already exists.')

    await continueStep(wrapper)
    expect(step(wrapper)).toBe(0)

    await leave(wrapper, '#studentIndividual-student-email', 'jo.lee@example.test')
    expect(field().textContent).not.toContain('already exists')
    await continueStep(wrapper)
    expect(step(wrapper)).toBe(1)
  })

  it('shows a warning under the box, and its tick goes with the next check', async () => {
    const path = 'students.0.overrides.ConfirmEmailInvalidOverride'
    answers['jo@unsure.test'] = {
      ok: false, severity: 'soft',
      warnings: [{
        code: 'email_invalid', message: "This email address couldn't be verified.",
        field: 'students.0.email', override_field: path,
      }],
    }
    const wrapper = await start()

    await leave(wrapper, '#studentIndividual-student-email', 'jo@unsure.test')
    expect(wrapper.get('.email-check-note--warning').text()).toContain("couldn't be verified")
    // A warning doesn't hold the step up.
    await continueStep(wrapper)
    expect(step(wrapper)).toBe(1)

    ;(wrapper.vm as unknown as { currentStep: number }).currentStep = 0
    await flushPromises()
    answers['jo@unsure.test'] = { ok: true }
    await wrapper.get('[data-test="studentIndividual-student-email-confirm"]').setValue(true)
    await flushPromises()
    expect(checks.at(-1)!.fields[0]!.overrides).toEqual({ ConfirmEmailInvalidOverride: true })
    expect(wrapper.find('.email-check-note--warning').exists()).toBe(false)
  })
})

describe("a student's School", () => {
  it('warns about a university as the box leaves, and its tick goes with the next check', async () => {
    const message = 'This looks like a university, not a school. Please confirm if this is correct.'
    answers['University of Sydney'] = {
      ok: false, severity: 'soft',
      warnings: [{
        code: 'university_school', message, field: 'students.0.school',
        override_field: 'students.0.overrides.ConfirmSchoolOverride',
      }],
    }
    const wrapper = mountPage()
    await clickButton(wrapper, 'Student')
    await clickButton(wrapper, "I don't have a group")
    Object.assign(wrapper.vm as unknown as { currentStep: number; maxReachedStep: number }, {
      currentStep: 1, maxReachedStep: 1,
    })
    await flushPromises()

    await leave(wrapper, '#studentIndividual-student-school', 'University of Sydney')

    expect(checks.at(-1)).toMatchObject({
      journey: 'student_individual',
      fields: [{
        field: 'studentIndividual.student.school', kind: 'school', email: '', school: 'University of Sydney',
        student: 0,
      }],
    })
    const note = wrapper.get('.email-check-note--warning')
    expect(note.text()).toContain(message)
    expect(note.text()).toContain('Yes, this school is correct')

    answers['University of Sydney'] = { ok: true }
    await wrapper.get('[data-test="studentIndividual-student-school-confirm"]').setValue(true)
    await flushPromises()
    expect(checks.at(-1)!.fields[0]!.overrides).toEqual({ ConfirmSchoolOverride: true })
    expect(wrapper.find('.email-check-note--warning').exists()).toBe(false)
  })
})

describe('a supervisor registering themselves', () => {
  it('checks their own address as theirs', async () => {
    const wrapper = mountPage()
    await clickButton(wrapper, 'Supervisor')

    await leave(wrapper, '#supervisor-email', 'sam@example.test')

    expect(checks.at(-1)).toMatchObject({
      journey: 'supervisor',
      fields: [{ field: 'supervisor.email', kind: 'supervisor_self', email: 'sam@example.test' }],
    })
  })
})
