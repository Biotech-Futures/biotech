import type { RouteRecordRaw } from 'vue-router'

export const PUBLIC_REGISTRATION_PATH = '/register'

export const publicRegistrationRoute: RouteRecordRaw = {
  path: PUBLIC_REGISTRATION_PATH,
  name: 'register',
  component: () => import('@/views/RegistrationPage.vue'),
  props: { mode: 'canonical' },
  meta: { public: true, shellFree: true },
}
