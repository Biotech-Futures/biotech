import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

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
  vi.stubGlobal('scrollTo', vi.fn())
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

    // Not one of the list: asked to choose one.
    Object.assign(setup.forms.supervisorIndividual.student, {
      firstName: 'Alex', lastName: 'Morgan', email: 'alex@example.com', emailConfirm: 'alex@example.com',
      school: 'Example High', yearLevel: '10', country: 'Australia', state: 'NSW', guardianDeferred: true,
    })
    await search.setValue('someone@else.test')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(send).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('Choose a supervisor from the list.')

    await search.setValue('sam@school.test')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(send).toHaveBeenCalledOnce()
    expect(send.mock.calls[0]![1]!.supervisorEmail).toBe('sam@school.test')
    wrapper.unmount()
  })
})
