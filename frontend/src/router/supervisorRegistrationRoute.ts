import type { RouteRecordRaw } from 'vue-router'

export const SUPERVISOR_REGISTRATION_PATH = '/supervisor/registration'
export const EMBEDDED_SUPERVISOR_REGISTRATION_PATH = '/supervisor/registration/embed'

export const supervisorRegistrationRoute: RouteRecordRaw = {
  path: SUPERVISOR_REGISTRATION_PATH,
  name: 'supervisor-registration',
  component: () => import('@/views/RegistrationDemoPage.vue'),
  props: { mode: 'supervisor' },
}

export const embeddedSupervisorRegistrationRoute: RouteRecordRaw = {
  path: EMBEDDED_SUPERVISOR_REGISTRATION_PATH,
  name: 'embedded-supervisor-registration',
  component: () => import('@/views/RegistrationDemoPage.vue'),
  props: { mode: 'embedded-supervisor' },
}

export const SUPERVISOR_REGISTRATION_PATHS = [
  SUPERVISOR_REGISTRATION_PATH,
  EMBEDDED_SUPERVISOR_REGISTRATION_PATH,
] as const
