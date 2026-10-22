import { mount, type VueWrapper } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { EmailCheckOutcome, EmailCheckProgress } from '@/registration/emailPrecheck'
import { REGISTRATION_GATEWAY_KEY, type RegistrationGateway } from '@/registration/registrationGateway'
import type { RegistrationForms } from '@/registration/registration'
import { resetCsrfToken } from '@/utils/csrf'
import RegistrationPage from '@/views/RegistrationPage.vue'

// Submitting: the BIOTech Futures policies agreed to first, as anyone
// registering must tick them on the last step.
const submitForm = async (page: { vm: unknown; get: (selector: string) => { trigger: (event: string) => Promise<unknown> } }) => {
  ;(page.vm as { policiesAgreed: boolean }).policiesAgreed = true
  await page.get('form').trigger('submit')
}

type PageSetup = { currentStep: number; journey: string; forms: RegistrationForms }

const receipt = {
  ok: true as const,
  receipt: {
    referenceCode: 'REG-1001',
    journey: 'student_individual' as const,
    studentCount: 1,
    submittedAt: '2026-10-18T06:00:00.000Z',
  },
}

const mountWithGateway = (gateway: RegistrationGateway, props: Record<string, unknown> = {}) =>
  mount(RegistrationPage, {
    props: { mode: 'canonical', ...props },
    attachTo: document.body,
    global: {
      plugins: [createPinia()],
      provide: { [REGISTRATION_GATEWAY_KEY as symbol]: gateway },
      stubs: { RouterLink: { props: ['to'], template: '<a :href="to"><slot /></a>' } },
    },
  })

const prepareStudent = async (wrapper: VueWrapper) => {
  const setup = wrapper.vm as unknown as PageSetup
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
  await wrapper.vm.$nextTick()
}

const submit = async (wrapper: VueWrapper) => {
  await submitForm(wrapper)
  await wrapper.vm.$nextTick()
}

/** A check the test drives: report progress, then finish it. */
const controllableCheck = () => {
  let report: (progress: EmailCheckProgress) => void = () => {}
  let finish: (outcome: EmailCheckOutcome) => void = () => {}
  const checkEmails = vi.fn<NonNullable<RegistrationGateway['checkEmails']>>(
    (_request, _options, onProgress) =>
      new Promise((resolve) => {
        report = onProgress
        finish = resolve
      }),
  )
  return {
    checkEmails,
    report: (progress: EmailCheckProgress) => report(progress),
    finish: (outcome: EmailCheckOutcome) => finish(outcome),
  }
}

beforeEach(() => {
  sessionStorage.clear()
  vi.stubGlobal('scrollTo', vi.fn())
  resetCsrfToken()
})

afterEach(() => {
  document.body.innerHTML = ''
  vi.unstubAllGlobals()
})

describe('checking email addresses before submitting', () => {
  it('shows the wait for earlier checks, then a bar and countdown, then submits', async () => {
    const check = controllableCheck()
    const send = vi.fn<RegistrationGateway['submit']>().mockResolvedValue(receipt)
    const wrapper = mountWithGateway({ submit: send, checkEmails: check.checkEmails })
    await prepareStudent(wrapper)

    await submit(wrapper)
    await vi.waitFor(() => expect(check.checkEmails).toHaveBeenCalledOnce())
    expect(send).not.toHaveBeenCalled()

    check.report({ phase: 'queued', done: 0, total: 2 })
    await wrapper.vm.$nextTick()
    expect(wrapper.get('.email-check').text()).toContain('Waiting for earlier checks')
    expect(wrapper.get('.email-check progress').attributes('value')).toBeUndefined()

    check.report({ phase: 'running', done: 1, total: 2, secondsRemaining: 75 })
    await wrapper.vm.$nextTick()
    expect(wrapper.get('.email-check').text()).toContain('1 of 2 checked')
    expect(wrapper.get('.email-check').text()).toContain('About 1 min 15 s left')
    const bar = wrapper.get('.email-check progress')
    expect([bar.attributes('value'), bar.attributes('max')]).toEqual(['1', '2'])

    check.finish('checked')
    await vi.waitFor(() => expect(send).toHaveBeenCalledOnce())
    await vi.waitFor(() => expect(wrapper.find('.email-check').exists()).toBe(false))
    wrapper.unmount()
  })

  it('sends the check the registration, its late link and the warnings already confirmed', async () => {
    const checkEmails = vi.fn<NonNullable<RegistrationGateway['checkEmails']>>(async () => 'checked')
    const send = vi.fn<RegistrationGateway['submit']>().mockResolvedValue(receipt)
    const wrapper = mountWithGateway({ submit: send, checkEmails }, { invitationToken: 'signed-link' })
    await prepareStudent(wrapper)

    await submit(wrapper)
    await vi.waitFor(() => expect(send).toHaveBeenCalledOnce())

    const [request, options] = checkEmails.mock.calls[0]!
    expect(request).toEqual(send.mock.calls[0]![0])
    expect(options).toMatchObject({ invitationToken: 'signed-link', overrides: {} })
    expect(checkEmails.mock.invocationCallOrder[0]!).toBeLessThan(send.mock.invocationCallOrder[0]!)
    wrapper.unmount()
  })

  it.each([
    ['skipped', async () => 'skipped' as const],
    [
      'throws',
      async (): Promise<EmailCheckOutcome> => {
        throw new Error('network down')
      },
    ],
  ])('submits as usual when the check is %s', async (_, outcome) => {
    const checkEmails = vi.fn<NonNullable<RegistrationGateway['checkEmails']>>(outcome)
    const send = vi.fn<RegistrationGateway['submit']>().mockResolvedValue(receipt)
    const wrapper = mountWithGateway({ submit: send, checkEmails })
    await prepareStudent(wrapper)

    await submit(wrapper)

    await vi.waitFor(() => expect(send).toHaveBeenCalledOnce())
    expect(wrapper.find('.email-check').exists()).toBe(false)
    wrapper.unmount()
  })

  it('submits exactly as before with a gateway that doesn’t check', async () => {
    const send = vi.fn<RegistrationGateway['submit']>().mockResolvedValue(receipt)
    const wrapper = mountWithGateway({ submit: send })
    await prepareStudent(wrapper)

    await submit(wrapper)

    await vi.waitFor(() => expect(send).toHaveBeenCalledOnce())
    expect(wrapper.find('.email-check').exists()).toBe(false)
    wrapper.unmount()
  })

  it('labels a guardian’s address that doesn’t exist, and checks again before resubmitting', async () => {
    const checkEmails = vi.fn<NonNullable<RegistrationGateway['checkEmails']>>(async () => 'checked')
    const send = vi
      .fn<RegistrationGateway['submit']>()
      .mockResolvedValueOnce({
        ok: false,
        message: 'Please check these registration warnings.',
        warnings: [
          {
            code: 'guardian_email_invalid',
            field: 'studentIndividual.student.guardian.email',
            overrideField: 'students.0.overrides.ConfirmGuardianEmailInvalidOverride',
            message: "The guardian's email address doesn't appear to exist.",
          },
        ],
      })
      .mockResolvedValueOnce(receipt)
    const wrapper = mountWithGateway({ submit: send, checkEmails })
    await prepareStudent(wrapper)

    await submit(wrapper)
    await vi.waitFor(() => expect(wrapper.find('.registration-warnings').exists()).toBe(true))
    expect(wrapper.get('.registration-warnings').text()).toContain('Guardian email:')
    expect(wrapper.get('.registration-warnings').text()).toContain("doesn't appear to exist")

    // The user corrects the address (or confirms it), then submits again.
    const setup = wrapper.vm as unknown as PageSetup
    setup.forms.studentIndividual.student.guardian.email = 'taylor.morgan@example.com'
    await wrapper.vm.$nextTick()
    if (wrapper.find('.registration-warnings input').exists())
      await wrapper.get('.registration-warnings input').setValue(true)
    await submit(wrapper)

    await vi.waitFor(() => expect(send).toHaveBeenCalledTimes(2))
    expect(checkEmails).toHaveBeenCalledTimes(2)
    expect(checkEmails.mock.invocationCallOrder[1]!).toBeLessThan(send.mock.invocationCallOrder[1]!)
    expect(send.mock.calls[1]![0]).toMatchObject({
      payload: { student: { guardian: { email: 'taylor.morgan@example.com' } } },
    })
    wrapper.unmount()
  })
})
