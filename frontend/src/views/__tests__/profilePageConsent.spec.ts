import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'

import ProfilePage from '../ProfilePage.vue'
import { useAuthStore } from '@/stores/auth'

const baseUser = {
  id: 81,
  email: 'student@example.com',
  first_name: 'Oscar',
  last_name: 'Fischer',
  current_role_name: 'Student',
  school_name: 'Westlake Secondary',
  year_lvl: '12',
  interests: [],
}

async function mountAs(user: Record<string, unknown>) {
  const auth = useAuthStore()
  auth.user = user as typeof auth.user
  // The page refetches /users/me on mount; keep the user set above.
  vi.spyOn(auth, 'fetchUserData').mockResolvedValue(undefined as never)
  const wrapper = mount(ProfilePage)
  await flushPromises()
  return wrapper
}

describe('ProfilePage guardian consent', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('shows consent as received', async () => {
    const wrapper = await mountAs({ ...baseUser, join_perm: true })

    expect(wrapper.find('[data-test="guardian-consent"]').text()).toBe('Received')
    expect(wrapper.text()).not.toContain('needs to complete the consent form')
  })

  it('shows consent as outstanding, with what to do next', async () => {
    const wrapper = await mountAs({ ...baseUser, join_perm: false })

    expect(wrapper.find('[data-test="guardian-consent"]').text()).toBe('Not received yet')
    expect(wrapper.text()).toContain('needs to complete the consent form')
  })

  it('treats a missing flag as not received', async () => {
    const wrapper = await mountAs({ ...baseUser, join_perm: null })

    expect(wrapper.find('[data-test="guardian-consent"]').text()).toBe('Not received yet')
  })

  it('is not shown to other roles', async () => {
    const wrapper = await mountAs({ ...baseUser, current_role_name: 'Mentor', join_perm: null })

    expect(wrapper.find('[data-test="guardian-consent"]').exists()).toBe(false)
  })
})
