import { mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import { describe, expect, it, vi } from 'vitest'

import { REGISTRATION_GATEWAY_KEY, type RegistrationGateway } from '@/registration/registrationGateway'
import {
  REGISTRATION_UI_TEST_PATH,
  registrationUiTestRoute,
  resolveRegistrationUiTestAccess,
} from '@/router/registrationUiTestRoute'
import RegistrationUiTestPage from '@/views/RegistrationUiTestPage.vue'

const expectedJourneys = [
  ['Individual student', 'Register as an individual student'],
  ['Student team', 'Create a student team'],
  ['One student', 'Register one student'],
  ['Pre-formed group', 'Register a student group'],
  ['CSV import', 'Upload students by CSV'],
  ['Mentor application', 'Register as a mentor'],
] as const

const mountPage = async () => {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: REGISTRATION_UI_TEST_PATH, component: RegistrationUiTestPage },
      { path: '/register', component: { template: '<div />' } },
    ],
  })
  await router.push(REGISTRATION_UI_TEST_PATH)
  await router.isReady()
  const liveGateway: RegistrationGateway = {
    submit: vi.fn(async () => {
      throw new Error('The UI test surface must not call an injected live gateway.')
    }),
  }
  const wrapper = mount(RegistrationUiTestPage, {
    global: {
      plugins: [router, createPinia()],
      provide: { [REGISTRATION_GATEWAY_KEY as symbol]: liveGateway },
    },
  })
  return { wrapper, liveGateway }
}

describe('registration UI test surface', () => {
  it('denies production access before the route can render', () => {
    expect(resolveRegistrationUiTestAccess(false)).toBe('/register')
    expect(resolveRegistrationUiTestAccess(true)).toBe(true)
    expect(registrationUiTestRoute.beforeEnter).toBeTypeOf('function')
  })

  it('directly launches every current intake journey', async () => {
    const { wrapper } = await mountPage()
    for (const [launcher, heading] of expectedJourneys) {
      const button = wrapper.findAll('button').find((item) => item.text().includes(launcher))
      expect(button).toBeDefined()
      await button!.trigger('click')
      await wrapper.vm.$nextTick()
      expect(wrapper.text()).toContain(heading)
    }
  })

  it('labels its in-memory behavior and synthetic supervisor context', async () => {
    const { wrapper, liveGateway } = await mountPage()
    expect(wrapper.text()).toContain('Development UI test surface')
    expect(wrapper.text()).toContain('No registration data is sent or persisted')

    const button = wrapper.findAll('button').find((item) => item.text().includes('One student'))
    await button!.trigger('click')
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('Synthetic Supervisor')
    expect(wrapper.text()).toContain('UI test context - no authorization')
    expect(wrapper.text()).toContain('display-only')
    expect(liveGateway.submit).not.toHaveBeenCalled()
  })
})
