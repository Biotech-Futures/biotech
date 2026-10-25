import type { RouteRecordRaw } from 'vue-router'

export const PUBLIC_REGISTRATION_PATH = '/register'

/** Setting a password straight after registering (registrationPassword.ts). */
export const registrationPasswordRoute: RouteRecordRaw = {
  path: '/register/password',
  name: 'register-password',
  component: () => import('@/views/SetPasswordPage.vue'),
  props: { registration: true },
  // Under the site's top bar, as Guardian Details is.
  meta: { public: true, siteHeader: true },
}

export const publicRegistrationRoute: RouteRecordRaw = {
  path: PUBLIC_REGISTRATION_PATH,
  name: 'register',
  component: () => import('@/views/RegistrationPage.vue'),
  props: (route) => ({
    mode: 'canonical',
    invitationToken: typeof route.query.invite === 'string' ? route.query.invite : null,
  }),
  // The site's top bar (as other public pages), with Sign in on the right.
  meta: { public: true, shellFree: true, siteHeader: true, siteHeaderSignIn: true },
}
