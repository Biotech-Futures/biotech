import type { RouteRecordRaw } from 'vue-router'

export const REGISTRATION_UI_TEST_PATH = '/registration-ui-test'

export const resolveRegistrationUiTestAccess = (
  isDevelopment: boolean,
): true | '/register' => (isDevelopment ? true : '/register')

export const registrationUiTestRoute: RouteRecordRaw = {
  path: REGISTRATION_UI_TEST_PATH,
  name: 'registration-ui-test',
  component: () => import('@/views/RegistrationUiTestPage.vue'),
  beforeEnter: () => resolveRegistrationUiTestAccess(import.meta.env.DEV),
}
