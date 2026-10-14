import type { RouteRecordRaw } from 'vue-router'

export const PUBLIC_REGISTRATION_PATH = '/register'

export const publicRegistrationRoute: RouteRecordRaw = {
  path: PUBLIC_REGISTRATION_PATH,
  name: 'register',
  component: () => import('@/views/RegistrationPage.vue'),
  props: (route) => ({
    mode: 'canonical',
    invitationToken: typeof route.query.invite === 'string' ? route.query.invite : null,
  }),
  meta: { public: true, shellFree: true },
}
