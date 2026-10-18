import type { RouteRecordRaw } from 'vue-router'

export const SUPERVISOR_REGISTRATION_PATH = '/supervisor/registration'

export const supervisorRegistrationRoute: RouteRecordRaw = {
  path: SUPERVISOR_REGISTRATION_PATH,
  name: 'supervisor-registration',
  component: () => import('@/views/RegistrationPage.vue'),
  props: { mode: 'supervisor' },
  meta: { supervisorRegistration: true },
}
