import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { routerKey } from 'vue-router'

import SetPasswordPage from '@/views/SetPasswordPage.vue'
import { heldRegistrationPassword, holdRegistrationPassword } from '@/registration/registrationPassword'
import { useAuthStore } from '@/stores/auth'

const router = { replace: vi.fn(), push: vi.fn(), resolve: vi.fn(() => ({ matched: [] })) }

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
    expect(wrapper.get('legend').text()).toBe('Parent or guardian')

    await choosePassword(wrapper)
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(wrapper.get('.error-message').text()).toBe("Enter your guardian's first name.")
    expect(calls(send).filter((call) => call.method !== 'GET')).toEqual([])

    await wrapper.get('#guardian-first-name').setValue('Taylor')
    await wrapper.get('#guardian-last-name').setValue('Pupil')
    await wrapper.get('#guardian-email').setValue('Taylor@Example.com')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    // Their guardian first (emailed the permission form), then the password.
    expect(calls(send).filter((call) => call.method !== 'GET')).toEqual([
      {
        url: expect.stringContaining('/api/v1/users/me/guardian/'),
        method: 'PUT',
        body: { first_name: 'Taylor', last_name: 'Pupil', email: 'taylor@example.com' },
      },
      {
        url: expect.stringContaining('/api/v1/set-password/'),
        method: 'POST',
        body: { password: 'a-good-password' },
      },
    ])
    expect(router.replace).toHaveBeenCalledWith('/dashboard')
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
    await choosePassword(wrapper)
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(wrapper.get('.error-message').text()).toBe("Enter your parent or guardian's email, not your own.")
    expect(calls(send).some((call) => call.url.includes('/set-password/'))).toBe(false)
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
