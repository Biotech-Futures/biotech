// A sign-up starts in the country, and Australia's state, the computer says
// it's in (registration/detectPlace): chosen for them, never over theirs.
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import RegistrationPage from '@/views/RegistrationPage.vue'
import { REGISTRATION_GATEWAY_KEY } from '@/registration/registrationGateway'

vi.mock('vue-router', async (importOriginal) => ({
  ...(await importOriginal<typeof import('vue-router')>()),
  useRouter: () => ({ push: vi.fn() }),
}))

const json = (body: unknown) => new Response(JSON.stringify(body), { status: 200 })

type Place = { country: string; state: string }
type PageSetup = {
  forms: { studentIndividual: { student: Place }; mentor: Place; supervisor: Place }
}

beforeEach(() => {
  sessionStorage.clear()
  vi.stubGlobal('scrollTo', vi.fn())
  vi.stubGlobal('fetch', vi.fn(async (url: string) => {
    const path = String(url)
    if (path.includes('/registration/countries/')) return json({ countries: ['Australia', 'New Zealand'] })
    if (path.includes('/registration/states/')) return json({ states: ['ACT', 'NSW', 'QLD', 'VIC'] })
    return json({})
  }))
  // A computer set to Brisbane's time.
  const resolved = Intl.DateTimeFormat.prototype.resolvedOptions
  vi.spyOn(Intl.DateTimeFormat.prototype, 'resolvedOptions').mockImplementation(function (
    this: Intl.DateTimeFormat,
  ) {
    return { ...resolved.call(this), timeZone: 'Australia/Brisbane' }
  })
})

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

const mountPage = () =>
  mount(RegistrationPage, {
    props: { mode: 'canonical' },
    global: {
      plugins: [createPinia()],
      provide: { [REGISTRATION_GATEWAY_KEY as symbol]: { submit: vi.fn() } },
      stubs: { RouterLink: { props: ['to'], template: '<a :href="to"><slot /></a>' } },
    },
  })

const clickButton = async (wrapper: VueWrapper, label: string) => {
  const button = wrapper.findAll('button').find((candidate) => candidate.text().includes(label))
  expect(button, `button containing "${label}"`).toBeDefined()
  await button!.trigger('click')
  await flushPromises()
}

describe("a sign-up's Country and State", () => {
  it("start where the computer is, for a student and for a mentor", async () => {
    const wrapper = mountPage()
    const setup = wrapper.vm as unknown as PageSetup
    await clickButton(wrapper, 'Student')
    await clickButton(wrapper, "I don't have a group")

    await vi.waitFor(() =>
      expect(setup.forms.studentIndividual.student).toMatchObject({ country: 'Australia', state: 'QLD' }),
    )
    wrapper.unmount()

    const mentorPage = mountPage()
    await clickButton(mentorPage, 'Mentor')
    await vi.waitFor(() =>
      expect((mentorPage.vm as unknown as PageSetup).forms.mentor).toMatchObject({ country: 'Australia', state: 'QLD' }),
    )
    mentorPage.unmount()
  })

  it('leave a country already chosen as it is', async () => {
    const wrapper = mountPage()
    const setup = wrapper.vm as unknown as PageSetup
    setup.forms.supervisor.country = 'New Zealand'

    await clickButton(wrapper, 'Supervisor')
    await flushPromises()
    await new Promise((resolve) => setTimeout(resolve, 20))

    expect(setup.forms.supervisor).toMatchObject({ country: 'New Zealand', state: '' })
    wrapper.unmount()
  })
})
