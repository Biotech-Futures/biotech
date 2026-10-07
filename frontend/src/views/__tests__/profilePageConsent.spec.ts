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

  it('shows the guardian name and email', async () => {
    const wrapper = await mountAs({
      ...baseUser,
      pg_firstname: 'Pat',
      pg_lastname: 'Fischer',
      pg_email: 'pat@example.com',
      join_perm: false,
    })

    expect(wrapper.find('[data-test="guardian-details"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="guardian-name"]').text()).toBe('Pat Fischer')
    expect(wrapper.find('[data-test="guardian-email"] a').attributes('href')).toBe('mailto:pat@example.com')
  })

  it('shows when consent was received', async () => {
    const wrapper = await mountAs({
      ...baseUser,
      join_perm: true,
      join_perm_granted_at: '2026-09-14T03:00:00Z',
    })

    expect(wrapper.find('[data-test="guardian-consent-date"]').text()).toBe('Received on 14 September 2026')
  })

  it('treats the student\'s own name as no guardian on file', async () => {
    const wrapper = await mountAs({
      ...baseUser,
      pg_firstname: 'Oscar',
      pg_lastname: 'Fischer',
      pg_email: null,
      join_perm: false,
    })

    expect(wrapper.find('[data-test="guardian-name"]').text()).toBe('Not set')
    expect(wrapper.find('[data-test="guardian-email"]').text()).toBe('Not set')
    expect(wrapper.find('[data-test="guardian-consent-date"]').exists()).toBe(false)
  })

  it('hides guardian details from other roles', async () => {
    const wrapper = await mountAs({ ...baseUser, current_role_name: 'Mentor' })

    expect(wrapper.find('[data-test="guardian-details"]').exists()).toBe(false)
  })

  it('saves edited guardian details', async () => {
    const wrapper = await mountAs({ ...baseUser, pg_firstname: 'Pat', pg_lastname: 'Fischer', pg_email: 'pat@example.com', join_perm: false })
    const auth = useAuthStore()
    const update = vi.spyOn(auth, 'updateGuardian').mockResolvedValue(undefined as never)

    await wrapper.find('[data-test="guardian-edit"]').trigger('click')
    await wrapper.find('#guardian-first-name').setValue('Robin')
    await wrapper.find('#guardian-email').setValue('robin@example.com')
    await wrapper.find('[data-test="guardian-form"]').trigger('submit')
    await flushPromises()

    expect(update).toHaveBeenCalledWith({ first_name: 'Robin', last_name: 'Fischer', email: 'robin@example.com' })
    expect(wrapper.find('[data-test="guardian-form"]').exists()).toBe(false)
  })

  it('does not submit the student\'s own email', async () => {
    const wrapper = await mountAs({ ...baseUser, join_perm: false })
    const auth = useAuthStore()
    const update = vi.spyOn(auth, 'updateGuardian').mockResolvedValue(undefined as never)

    await wrapper.find('[data-test="guardian-edit"]').trigger('click')
    await wrapper.find('#guardian-first-name').setValue('Robin')
    await wrapper.find('#guardian-last-name').setValue('Carer')
    await wrapper.find('#guardian-email').setValue('Student@example.com')
    await wrapper.find('[data-test="guardian-form"]').trigger('submit')
    await flushPromises()

    expect(update).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('not your own')
  })

  it('shows a pending change alongside the consenting guardian', async () => {
    const wrapper = await mountAs({
      ...baseUser,
      pg_firstname: 'Pat',
      pg_lastname: 'Fischer',
      pg_email: 'pat@example.com',
      join_perm: true,
      pending_guardian: { first_name: 'Robin', last_name: 'Carer', email: 'robin@example.com', requested_at: '2026-10-01T00:00:00Z' },
    })

    expect(wrapper.find('[data-test="guardian-name"]').text()).toBe('Pat Fischer')
    const pending = wrapper.find('[data-test="guardian-pending"]').text()
    expect(pending).toContain('Robin Carer (robin@example.com)')
    expect(pending).toContain('Pat Fischer stays on file')
  })

  it('withdraws a pending change', async () => {
    const wrapper = await mountAs({
      ...baseUser,
      join_perm: true,
      pending_guardian: { first_name: 'Robin', last_name: 'Carer', email: 'robin@example.com', requested_at: '2026-10-01T00:00:00Z' },
    })
    const auth = useAuthStore()
    const withdraw = vi.spyOn(auth, 'withdrawGuardianChange').mockResolvedValue(undefined as never)

    await wrapper.find('[data-test="guardian-withdraw"]').trigger('click')
    await flushPromises()

    expect(withdraw).toHaveBeenCalled()
  })
})
