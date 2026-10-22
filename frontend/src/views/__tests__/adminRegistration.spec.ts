import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { fetchRegistrationSupervisors } from '@/utils/managementAPI'

import { REGISTRATION_GATEWAY_KEY, type RegistrationGateway } from '@/registration/registrationGateway'
import RegistrationPage from '@/views/RegistrationPage.vue'

vi.mock('@/utils/managementAPI', async (original) => ({
  ...(await original<typeof import('@/utils/managementAPI')>()),
  fetchRegistrationOpen: vi.fn(async () => ({ open_now: true, opens_at: null, closes_at: null, can_register_students: true })),
  fetchRegistrationSupervisors: vi.fn(async () => [
    { user_id: 7, name: 'Sam Lee', email: 'sam@school.test', school: 'Example High', students: 3, register_after_close: false },
  ]),
}))

// Management > Registration: an admin registers students as a supervisor does,
// choosing their supervisor by email first.
const mountAdmin = (gateway: RegistrationGateway) =>
  mount(RegistrationPage, {
    props: { mode: 'supervisor', embedded: true },
    attachTo: document.body,
    global: {
      plugins: [createPinia()],
      provide: { [REGISTRATION_GATEWAY_KEY as symbol]: gateway },
      stubs: { RouterLink: { props: ['to'], template: '<a :href="to"><slot /></a>' } },
    },
  })

type Setup = {
  journey: string | null
  forms: { supervisorIndividual: { student: Record<string, unknown> } }
}

beforeEach(() => {
  sessionStorage.clear()
  vi.stubGlobal('scrollTo', vi.fn())
  vi.mocked(fetchRegistrationSupervisors).mockReset().mockResolvedValue([
    { user_id: 7, name: 'Sam Lee', email: 'sam@school.test', school: 'Example High', students: 3, register_after_close: false },
  ])
})

afterEach(() => {
  document.body.innerHTML = ''
  vi.unstubAllGlobals()
})

describe('admin registration', () => {
  it('chooses the students’ supervisor by email, before Student 1, and sends it', async () => {
    const send = vi.fn<RegistrationGateway['submit']>().mockResolvedValue({
      ok: true,
      receipt: { referenceCode: 'R', journey: 'supervisor_individual', studentCount: 1, submittedAt: '2026-10-18T00:00:00Z' },
    })
    const wrapper = mountAdmin({ submit: send })
    await flushPromises()
    const setup = wrapper.vm as unknown as Setup
    setup.journey = 'supervisor_individual'
    await flushPromises()

    // The supervisor's email only (no names), then Student 1.
    expect(wrapper.find('#admin-supervisor-first').exists()).toBe(false)
    expect(wrapper.get('.student-entry__heading h3').text()).toBe('Student 1')
    const search = wrapper.get('#admin-supervisor-email')
    await search.setValue('sam@')
    await search.trigger('focus')
    const option = wrapper.get('.supervisor-search__option')
    expect(option.text()).toContain('Sam Lee')
    await option.trigger('mousedown')
    expect((search.element as HTMLInputElement).value).toBe('sam@school.test')

    // Missing or malformed supervisor emails are blocked locally.
    Object.assign(setup.forms.supervisorIndividual.student, {
      firstName: 'Alex', lastName: 'Morgan', email: 'alex@example.com', emailConfirm: 'alex@example.com',
      school: 'Example High', yearLevel: '10', country: 'Australia', state: 'NSW', guardianDeferred: true,
    })
    await search.setValue('')
    expect(search.attributes('required')).toBeDefined()
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(send).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('Enter the supervisor email.')

    await search.setValue('not-an-email')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(send).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('Enter a valid supervisor email.')

    await search.setValue('sam@school.test')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(send).toHaveBeenCalledOnce()
    expect(send.mock.calls[0]![1]!.supervisorEmail).toBe('sam@school.test')
    wrapper.unmount()
  })

  it.each(['failed', 'empty', 'loading', 'omitted'])('validates manually entered emails on the server when the list is %s', async (state) => {
    const fetchSupervisors = vi.mocked(fetchRegistrationSupervisors)
    if (state === 'failed') fetchSupervisors.mockRejectedValueOnce(new Error('Unavailable'))
    if (state === 'empty') fetchSupervisors.mockResolvedValueOnce([])
    if (state === 'loading') fetchSupervisors.mockImplementationOnce(() => new Promise(() => {}))
    // The populated list also omits valid profiles whose users are inactive.
    const send = vi.fn<RegistrationGateway['submit']>()
      .mockResolvedValueOnce({
        ok: false,
        message: 'Registration could not be saved.',
        fieldErrors: { supervisorEmail: 'No supervisor has this email.' },
      })
      .mockResolvedValueOnce({
        ok: true,
        receipt: { referenceCode: 'R', journey: 'supervisor_individual', studentCount: 1, submittedAt: '2026-10-18T00:00:00Z' },
      })
    const wrapper = mountAdmin({ submit: send })
    try {
      await flushPromises()
      const setup = wrapper.vm as unknown as Setup
      setup.journey = 'supervisor_individual'
      Object.assign(setup.forms.supervisorIndividual.student, {
        firstName: 'Alex', lastName: 'Morgan', email: 'alex@example.com',
        school: 'Example High', yearLevel: '10', country: 'Australia', state: 'NSW', guardianDeferred: true,
      })
      await flushPromises()
      const search = wrapper.get('#admin-supervisor-email')
      for (const email of ['', '   ', 'not-an-email']) {
        await search.setValue(email)
        await wrapper.get('form').trigger('submit')
        await flushPromises()
        expect(send).not.toHaveBeenCalled()
        expect(search.attributes('aria-invalid')).toBe('true')
      }
      await search.setValue('unknown@school.test')
      await wrapper.get('form').trigger('submit')
      await flushPromises()
      expect(send).toHaveBeenCalledOnce()
      expect(wrapper.text()).toContain('No supervisor has this email.')
      expect(search.attributes('aria-invalid')).toBe('true')

      await search.setValue('  OMITTED@school.test  ')
      await wrapper.get('form').trigger('submit')
      await flushPromises()
      expect(send).toHaveBeenCalledTimes(2)
      expect(send.mock.calls[1]![1]!.supervisorEmail).toBe('OMITTED@school.test')
    } finally {
      wrapper.unmount()
    }
  })

})
