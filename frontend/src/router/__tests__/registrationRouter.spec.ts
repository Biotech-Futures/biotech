import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useAuthStore } from '@/stores/auth'
import router from '@/router'

describe('registration in the current application router', () => {
  beforeEach(async () => {
    localStorage.clear()
    setActivePinia(createPinia())
    await router.push('/login')
  })
  afterEach(() => localStorage.clear())

  it('allows anonymous registration while protecting supervisor intake', async () => {
    await router.push('/register?invite=signed-token')
    expect(router.currentRoute.value.name).toBe('register')
    expect(router.currentRoute.value.meta.public).toBe(true)
    expect(router.currentRoute.value.query.invite).toBe('signed-token')
    await router.push('/supervisor/registration')
    expect(router.currentRoute.value.path).toBe('/login')
  })

  it.each(['student', 'mentor'])('denies supervisor intake to %s accounts', async (role) => {
    useAuthStore().loginWithUser({
      id: 1, email: `${role}@example.test`, first_name: 'Member',
      last_name: 'User', current_role_name: role,
    })
    await router.push('/supervisor/registration')
    expect(router.currentRoute.value.path).toBe('/dashboard')
  })

  it.each(['supervisor', 'admin'])('allows %s accounts without replacing their other routes', async (role) => {
    useAuthStore().loginWithUser({
      id: 1, email: `${role}@example.test`, first_name: 'Member',
      last_name: 'User', current_role_name: role,
    })
    await router.push('/supervisor/registration')
    expect(router.currentRoute.value.name).toBe('supervisor-registration')
    expect(router.resolve('/my-students').name).toBe('my-students')
    expect(router.resolve('/admin/users').name).toBe('admin-users')
    expect(router.resolve('/analytics/registration').name).toBe('registration-analytics')
    await router.push('/register')
    expect(router.currentRoute.value.name).toBe('register')
  })

  it('preserves the first-password gate for protected supervisor intake', async () => {
    useAuthStore().loginWithUser({
      id: 1, email: 'supervisor@example.test', first_name: 'New',
      last_name: 'Supervisor', current_role_name: 'supervisor', must_change_password: true,
    })
    await router.push('/supervisor/registration')
    expect(router.currentRoute.value.path).toBe('/auth/set-password')
    await router.push('/register')
    expect(router.currentRoute.value.name).toBe('register')
  })
})
