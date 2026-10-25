import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { routerKey } from 'vue-router'

import SetPasswordPage from '@/views/SetPasswordPage.vue'
import { heldRegistrationPassword, holdRegistrationPassword } from '@/registration/registrationPassword'
import { useAuthStore } from '@/stores/auth'

const router = {
  replace: vi.fn(),
  push: vi.fn(),
  resolve: vi.fn(() => ({ matched: [] })),
  // ?token= when opened from a registration email.
  currentRoute: { value: { query: {} as Record<string, string> } },
}

const mountPage = (props: { registration?: boolean } = {}) =>
  mount(SetPasswordPage, {
    props,
    global: {
      provide: { [routerKey as symbol]: router },
      stubs: { RouterLink: { props: ['to'], template: '<a :href="to"><slot /></a>' } },
    },
  })

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status })

// The requests the page made: each one's address, method and body.
const calls = (send: ReturnType<typeof vi.fn>) =>
  send.mock.calls.map(([url, init]) => ({
    url: String(url),
    method: (init as RequestInit | undefined)?.method ?? 'GET',
    body: (init as RequestInit | undefined)?.body ? JSON.parse(String((init as RequestInit).body)) : null,
  }))

const choosePassword = async (wrapper: ReturnType<typeof mountPage>, password = 'a-good-password') => {
  await wrapper.get('#new-password').setValue(password)
  await wrapper.get('#confirm-password').setValue(password)
}

beforeEach(() => {
  setActivePinia(createPinia())
  sessionStorage.clear()
  router.replace.mockClear()
  router.currentRoute.value.query = {}
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('straight after registering', () => {
  it('needs the registration\'s token', async () => {
    mountPage({ registration: true })
    await flushPromises()
    expect(router.replace).toHaveBeenCalledWith('/login')
  })

  it('sets their password, signs them in and opens their profile', async () => {
    holdRegistrationPassword('signed-token', false)
    const send = vi.fn(async (url: string) =>
      String(url).includes('/registration/password/')
        ? json({ signedIn: true, csrfToken: 'rotated' })
        : json({ id: 7, email: 'jordan@example.com', current_role_name: 'student', must_change_password: false }),
    )
    vi.stubGlobal('fetch', send)
    const wrapper = mountPage({ registration: true })
    await flushPromises()
    expect(wrapper.text()).toContain('Create a password for your account.')
    // Not signed in yet: nothing to log out of.
    expect(wrapper.text()).not.toContain('Log out')

    await choosePassword(wrapper)
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(calls(send)[0]).toMatchObject({
      url: expect.stringContaining('/api/v1/registration/password/'),
      method: 'POST',
      body: { token: 'signed-token', password: 'a-good-password' },
    })
    expect(calls(send).some((call) => call.url.includes('/api/v1/users/me/'))).toBe(true)
    expect(router.replace).toHaveBeenCalledWith('/profile')
    // Used: let go.
    expect(heldRegistrationPassword()).toBeNull()
  })

  it('tells a mentor they sign in once activated', async () => {
    holdRegistrationPassword('signed-token', true)
    vi.stubGlobal('fetch', vi.fn(async () => json({ signedIn: false })))
    const wrapper = mountPage({ registration: true })
    await flushPromises()
    await choosePassword(wrapper)
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(wrapper.text()).toContain('Your password is set. You can sign in with it once your account is activated.')
    expect(wrapper.get('a.primary-action').attributes('href')).toBe('/login')
    expect(router.replace).not.toHaveBeenCalled()
  })

  it('checks the password, and shows what the server says', async () => {
    holdRegistrationPassword('signed-token', false)
    const send = vi.fn(async () =>
      json({ error: 'This link to set your password has expired.', code: 'invalid', request_id: 'x' }, 400),
    )
    vi.stubGlobal('fetch', send)
    const wrapper = mountPage({ registration: true })
    await flushPromises()
    await wrapper.get('#new-password').setValue('a-good-password')
    await wrapper.get('#confirm-password').setValue('another-password')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(wrapper.get('.error-message').text()).toBe('The two passwords do not match.')
    expect(send).not.toHaveBeenCalled()

    await choosePassword(wrapper)
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(wrapper.get('.error-message').text()).toBe('This link to set your password has expired.')
    expect(router.replace).not.toHaveBeenCalled()
  })
})

describe('from a registration email', () => {
  const EXPIRED = 'This link to set your password has expired. Sign in with your email to set one.'
  const opened = () => {
    router.currentRoute.value.query = { token: 'emailed-token' }
    const wrapper = mountPage({ registration: true })
    return wrapper
  }

  it('asks a student registered without their guardian for them, then their password, then opens their profile', async () => {
    const send = vi.fn(async (url: string, init?: RequestInit) => {
      if (String(url).includes('/registration/password/')) {
        return init?.method === 'POST'
          ? json({ signedIn: true, csrfToken: 'rotated' })
          : json({
              needsGuardian: true, guardian: { first_name: 'Taylor', last_name: '', email: '' }, needsPolicies: true,
            })
      }
      return json({ id: 7, email: 'pupil@example.com', current_role_name: 'student', must_change_password: false })
    })
    vi.stubGlobal('fetch', send)
    const wrapper = opened()
    await flushPromises()
    expect(calls(send)[0]).toMatchObject({ url: expect.stringContaining('token=emailed-token'), method: 'GET' })
    // Step 1: their guardian, what's on file already filled in.
    expect(wrapper.get('h1').text()).toBe('Complete your registration')
    expect(wrapper.get('.step-label').text()).toBe('Step 1 of 2')
    expect(wrapper.get('h2').text()).toBe('Guardian details')
    expect(wrapper.get('#guardian-first-name').element).toHaveProperty('value', 'Taylor')
    expect(wrapper.find('#new-password').exists()).toBe(false)

    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(wrapper.get('.error-message').text()).toBe("Enter your guardian's last name.")
    expect(wrapper.find('#new-password').exists()).toBe(false)

    await wrapper.get('#guardian-last-name').setValue('Pupil')
    await wrapper.get('#guardian-email').setValue('Taylor@Example.com')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    // Step 2: their password, and back to change the guardian, kept as given.
    expect(wrapper.get('.step-label').text()).toBe('Step 2 of 2')
    expect(wrapper.get('h2').text()).toBe('Password')
    expect(wrapper.find('#guardian-first-name').exists()).toBe(false)
    await wrapper.findAll('button').find((button) => button.text() === 'Back to guardian details')!.trigger('click')
    expect(wrapper.get('#guardian-last-name').element).toHaveProperty('value', 'Pupil')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    // The policies, agreed to before anything is sent.
    await choosePassword(wrapper)
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(wrapper.get('.policies-agree__error').text()).toBe('Agree to the BIOTech Futures policies to continue.')
    expect(calls(send).some((call) => call.method === 'POST')).toBe(false)

    await wrapper.get('[data-test="policies-agree"]').setValue(true)
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(calls(send).find((call) => call.method === 'POST')).toMatchObject({
      url: expect.stringContaining('/api/v1/registration/password/'),
      body: {
        token: 'emailed-token',
        password: 'a-good-password',
        guardian: { first_name: 'Taylor', last_name: 'Pupil', email: 'taylor@example.com' },
        policiesAgreed: true,
      },
    })
    expect(router.replace).toHaveBeenCalledWith('/profile')
  })

  it('takes them back to their guardian when the server refuses them', async () => {
    vi.stubGlobal('fetch', vi.fn(async (_url: string, init?: RequestInit) =>
      init?.method === 'POST'
        ? json({
            error: "Enter your parent or guardian's email, not your own.", code: 'invalid', request_id: 'x',
            fields: { email: ["Enter your parent or guardian's email, not your own."] },
          }, 400)
        : json({ needsGuardian: true, guardian: { first_name: '', last_name: '', email: '' }, needsPolicies: false }),
    ))
    const wrapper = opened()
    await flushPromises()
    await wrapper.get('#guardian-first-name').setValue('Taylor')
    await wrapper.get('#guardian-last-name').setValue('Pupil')
    await wrapper.get('#guardian-email').setValue('pupil@example.com')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    await choosePassword(wrapper)
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(wrapper.get('.step-label').text()).toBe('Step 1 of 2')
    expect(wrapper.get('.guardian-fields .error-message').text()).toBe(
      "Enter your parent or guardian's email, not your own.",
    )
    expect(wrapper.get('#guardian-email').classes()).toContain('is-error')
    expect(router.replace).not.toHaveBeenCalled()
  })

  it('just asks for a password when their guardian is on file and the policies agreed to', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => json({ needsGuardian: false, guardian: null, needsPolicies: false })))
    const wrapper = opened()
    await flushPromises()
    expect(wrapper.find('.step-label').exists()).toBe(false)
    expect(wrapper.find('.guardian-fields').exists()).toBe(false)
    expect(wrapper.find('[data-test="policies-agree"]').exists()).toBe(false)
    expect(wrapper.find('#new-password').exists()).toBe(true)
  })

  it('says so when the link has expired, and offers sign in', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => json({ error: EXPIRED, code: 'invalid', request_id: 'x' }, 400)))
    const wrapper = opened()
    await flushPromises()
    expect(wrapper.text()).toContain(EXPIRED)
    expect(wrapper.find('form').exists()).toBe(false)
    expect(wrapper.get('a.primary-action').attributes('href')).toBe('/login')
    expect(router.replace).not.toHaveBeenCalled()
  })
})

describe('first sign-in', () => {
  const signedIn = (user: Record<string, unknown>) => {
    useAuthStore().user = {
      id: 3, email: 'pupil@example.com', first_name: 'Pip', last_name: 'Pupil',
      must_change_password: true, ...user,
    } as never
  }

  it('asks a student registered without their guardian for them too', async () => {
    signedIn({ current_role_name: 'student', pg_firstname: '', pg_lastname: '', pg_email: null })
    const send = vi.fn(async (url: string) =>
      String(url).includes('/services/csrf/')
        ? json({ csrfToken: 'csrf' })
        : json({ id: 3, email: 'pupil@example.com', current_role_name: 'student', must_change_password: false }),
    )
    vi.stubGlobal('fetch', send)
    const wrapper = mountPage()
    await flushPromises()
    expect(wrapper.get('h1').text()).toBe('Complete your registration')
    expect(wrapper.get('h2').text()).toBe('Guardian details')

    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(wrapper.get('.error-message').text()).toBe("Enter your guardian's first name.")
    expect(calls(send).filter((call) => call.method !== 'GET')).toEqual([])

    await wrapper.get('#guardian-first-name').setValue('Taylor')
    await wrapper.get('#guardian-last-name').setValue('Pupil')
    await wrapper.get('#guardian-email').setValue('Taylor@Example.com')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    await choosePassword(wrapper)
    await wrapper.get('[data-test="policies-agree"]').setValue(true)
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    // Their guardian first (emailed the permission form), then the password,
    // agreeing to the policies.
    expect(calls(send).filter((call) => call.method !== 'GET')).toEqual([
      {
        url: expect.stringContaining('/api/v1/users/me/guardian/'),
        method: 'PUT',
        body: { first_name: 'Taylor', last_name: 'Pupil', email: 'taylor@example.com' },
      },
      {
        url: expect.stringContaining('/api/v1/set-password/'),
        method: 'POST',
        body: { password: 'a-good-password', policiesAgreed: true },
      },
    ])
    expect(router.replace).toHaveBeenCalledWith('/profile')
  })

  it("doesn't set the password when the guardian's details are refused", async () => {
    signedIn({ current_role_name: 'student', pg_firstname: 'Taylor', pg_lastname: '', pg_email: '' })
    const send = vi.fn(async (url: string) =>
      String(url).includes('/services/csrf/')
        ? json({ csrfToken: 'csrf' })
        : json({
            error: 'Enter your parent or guardian\'s email, not your own.', code: 'invalid', request_id: 'x',
            fields: { email: ["Enter your parent or guardian's email, not your own."] },
          }, 400),
    )
    vi.stubGlobal('fetch', send)
    const wrapper = mountPage()
    await flushPromises()
    // What's on file already is filled in.
    expect(wrapper.get('#guardian-first-name').element).toHaveProperty('value', 'Taylor')
    await wrapper.get('#guardian-last-name').setValue('Pupil')
    await wrapper.get('#guardian-email').setValue('pupil@example.com')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    await choosePassword(wrapper)
    await wrapper.get('[data-test="policies-agree"]').setValue(true)
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    // Back with their guardian, to change them.
    expect(wrapper.get('h2').text()).toBe('Guardian details')
    expect(wrapper.get('.error-message').text()).toBe("Enter your parent or guardian's email, not your own.")
    expect(calls(send).some((call) => call.url.includes('/set-password/'))).toBe(false)
  })

  it('asks for the policies only of someone registered by others who has not agreed', () => {
    for (const [user, asked] of [
      [{ current_role_name: 'student', pg_firstname: 'T', pg_lastname: 'P', pg_email: 't@example.com' }, true],
      [{ current_role_name: 'supervisor' }, true],
      [{ current_role_name: 'student', pg_firstname: 'T', pg_lastname: 'P', pg_email: 't@example.com',
        policies_agreed_at: '2026-10-20T00:00:00Z' }, false],
      [{ current_role_name: 'admin' }, false],
    ] as const) {
      setActivePinia(createPinia())
      signedIn(user)
      const wrapper = mountPage()
      expect(wrapper.find('[data-test="policies-agree"]').exists()).toBe(asked)
      // An admin is only setting a password; everyone else is completing their registration.
      expect(wrapper.get('h1').text()).toBe(user.current_role_name === 'admin' ? 'Set your password' : 'Complete your registration')
      wrapper.unmount()
    }
  })

  it('asks no one else for a guardian', () => {
    for (const user of [
      { current_role_name: 'student', pg_firstname: 'Taylor', pg_lastname: 'Pupil', pg_email: 't@example.com' },
      { current_role_name: 'supervisor' },
      { current_role_name: 'mentor' },
    ]) {
      setActivePinia(createPinia())
      signedIn(user)
      const wrapper = mountPage()
      expect(wrapper.find('.guardian-fields').exists()).toBe(false)
      expect(wrapper.text()).toContain('Log out')
      wrapper.unmount()
    }
  })
})
