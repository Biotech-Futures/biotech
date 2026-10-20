import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import AdminUserFormSheet from '../AdminUserFormSheet.vue'
import AdminUserDetailSheet from '../AdminUserDetailSheet.vue'
import { createAdminUser, updateAdminUser } from '@/utils/adminAPI'
import type { AdminUser } from '@/utils/adminAPI'
import { mentorBackgroundLabel } from '@/utils/userFormat'
import { pickAppSelect } from '@/__tests__/appSelect'

vi.mock('@/utils/adminAPI', () => ({
  createAdminUser: vi.fn().mockResolvedValue({ msg: 'ok', data: null }),
  updateAdminUser: vi.fn().mockResolvedValue({ msg: 'ok', data: null }),
  setAdminUserActive: vi.fn(),
  sendGuardianConsentRequest: vi.fn(),
  fetchGuardianConsents: vi.fn(),
  downloadGuardianConsentRecord: vi.fn()
}))

const mentor = (overrides: Partial<AdminUser> = {}): AdminUser => ({
  id: 9,
  firstName: 'Mary',
  lastName: 'Somerville',
  email: 'mary@example.edu',
  role: 'mentor',
  country: { id: 1, countryName: 'Australia' },
  state: null,
  groupId: null,
  groupName: null,
  schoolName: null,
  mentorBackground: 'postgraduate',
  mentorInstitution: 'University of Sydney',
  mentorReason: 'Support students',
  mentorMaxGroupCount: 2,
  yearLevel: null,
  guardianFirstName: null,
  guardianLastName: null,
  guardianEmail: null,
  joinPermissionReceived: false,
  joinpermResponseId: null,
  joinPermissionGrantedAt: null,
  pendingGuardian: null,
  mediaConsent: null,
  consentRequestSentAt: null,
  interests: ['Biomedical Innovations'],
  isAdmin: false,
  isActive: true,
  hasLoggedIn: false,
  lastLogin: null,
  accountStatus: 'active',
  invitedAt: null,
  activatedAt: null,
  supervisorName: null,
  supervisorEmail: null,
  supervisees: [],
  ...overrides
})

async function openForm(user?: AdminUser) {
  const wrapper = mount(AdminUserFormSheet, {
    props: {
      modelValue: false,
      userNoun: 'Mentor',
      user,
      fixedRole: 'mentor',
      isSupervisorMode: false,
      countries: [{ id: 1, countryName: 'Australia' }],
      states: [],
      supervisors: []
    },
    global: { stubs: { teleport: true } }
  })
  // The form fills itself in when the sheet opens.
  await wrapper.setProps({ modelValue: true })
  return wrapper
}

async function submit(wrapper: Awaited<ReturnType<typeof openForm>>) {
  await wrapper.find('form').trigger('submit')
  await flushPromises()
}

const lastUpdate = () =>
  vi.mocked(updateAdminUser).mock.calls.at(-1)?.[1] as Record<string, unknown> | undefined

const optionTexts = (wrapper: Awaited<ReturnType<typeof openForm>>) =>
  wrapper.findAll('#f-mbg option').map((option) => option.text())

describe('mentor background', () => {
  beforeEach(() => {
    vi.mocked(updateAdminUser).mockClear()
    vi.mocked(createAdminUser).mockClear()
  })

  describe('form', () => {
    it('offers "Not set" and exactly the five categories, in order', async () => {
      const wrapper = await openForm(mentor())

      expect(wrapper.find('#f-mbg').element.tagName).toBe('SELECT')
      expect(optionTexts(wrapper)).toEqual([
        'Not set',
        'Academic',
        'Industry',
        'Undergraduate',
        'Postgraduate',
        'HDR'
      ])
      expect(wrapper.findAll('#f-mbg option').map((option) => option.attributes('value'))).toEqual([
        '',
        'academic',
        'industry',
        'undergraduate',
        'postgraduate',
        'hdr'
      ])
    })

    it('preselects the stored category', async () => {
      const wrapper = await openForm(mentor({ mentorBackground: 'hdr' }))
      expect((wrapper.find('#f-mbg').element as HTMLSelectElement).value).toBe('hdr')
    })

    it('sends a changed category', async () => {
      const wrapper = await openForm(mentor())
      await wrapper.find('#f-mbg').setValue('academic')
      await submit(wrapper)
      expect(lastUpdate()).toMatchObject({ mentorBackground: 'academic' })
    })

    it('sends null when the background is cleared to "Not set"', async () => {
      const wrapper = await openForm(mentor())
      await wrapper.find('#f-mbg').setValue('')
      await submit(wrapper)
      expect(lastUpdate()).toMatchObject({ mentorBackground: null })
    })

    it('does not send the background on an unrelated edit', async () => {
      const wrapper = await openForm(mentor())
      await wrapper.find('#f-minst').setValue('UNSW')
      await submit(wrapper)
      expect(lastUpdate()).toMatchObject({ mentorInstitution: 'UNSW' })
      expect(lastUpdate()).not.toHaveProperty('mentorBackground')
    })

    it('creates a mentor with the chosen category', async () => {
      const wrapper = await openForm()
      await wrapper.find('#f-first').setValue('Ada')
      await wrapper.find('#f-last').setValue('Lovelace')
      await wrapper.find('#f-email').setValue('ada@example.edu')
      await pickAppSelect(wrapper, '#f-country', 'Australia')
      await wrapper.find('#f-minst').setValue('Lab One')
      await wrapper.find('#f-mreason').setValue('Help students')
      await wrapper.find('input[type="checkbox"][value="Biomedical Innovations"]').setValue(true)
      await wrapper.find('#f-mbg').setValue('industry')
      await submit(wrapper)

      expect(wrapper.find('[role="alert"]').exists()).toBe(false)
      expect(vi.mocked(createAdminUser).mock.calls.at(-1)?.[0]).toMatchObject({
        role: 'mentor',
        mentorBackground: 'industry'
      })
    })
  })

  describe('older free-text values', () => {
    it('shows the stored value instead of pretending it is not set', async () => {
      const wrapper = await openForm(mentor({ mentorBackground: 'Seed mentor background.' }))

      const select = wrapper.find('#f-mbg')
      expect((select.element as HTMLSelectElement).value).toBe('Seed mentor background.')
      expect(optionTexts(wrapper)).toEqual([
        'Not set',
        'Seed mentor background. (not a category)',
        'Academic',
        'Industry',
        'Undergraduate',
        'Postgraduate',
        'HDR'
      ])
      expect(select.attributes('aria-describedby')).toBe('f-mbg-legacy')
      expect(wrapper.find('#f-mbg-legacy').text()).toContain("isn't one of the five categories")
    })

    it('keeps it on an unrelated edit', async () => {
      const wrapper = await openForm(mentor({ mentorBackground: 'Research' }))
      await wrapper.find('#f-mreason').setValue('Updated reason')
      await submit(wrapper)

      expect(lastUpdate()).toMatchObject({ mentorReason: 'Updated reason' })
      expect(lastUpdate()).not.toHaveProperty('mentorBackground')
    })

    it('can be replaced by a category', async () => {
      const wrapper = await openForm(mentor({ mentorBackground: 'Research' }))
      await wrapper.find('#f-mbg').setValue('academic')
      await submit(wrapper)
      expect(lastUpdate()).toMatchObject({ mentorBackground: 'academic' })
    })

    it('is not offered for a mentor with a category or none', async () => {
      for (const stored of ['industry', null]) {
        const wrapper = await openForm(mentor({ mentorBackground: stored }))
        expect(wrapper.find('#f-mbg-legacy').exists()).toBe(false)
        expect(optionTexts(wrapper)).toHaveLength(6)
      }
    })
  })

  describe('detail view', () => {
    const backgroundShown = (user: AdminUser) => {
      const wrapper = mount(AdminUserDetailSheet, {
        props: { open: true, user },
        global: { stubs: { teleport: true } }
      })
      const item = wrapper
        .findAll('.admin-users-detail__item')
        .find((row) => row.find('dt').text() === 'Background')
      return item?.find('dd').text()
    }

    it('shows the category label rather than the stored key', () => {
      expect(backgroundShown(mentor({ mentorBackground: 'hdr' }))).toBe('HDR')
      expect(backgroundShown(mentor({ mentorBackground: 'undergraduate' }))).toBe('Undergraduate')
    })

    it('shows an older value as stored, and a dash when unset', () => {
      expect(backgroundShown(mentor({ mentorBackground: 'Research' }))).toBe('Research')
      expect(backgroundShown(mentor({ mentorBackground: null }))).toBe('—')
    })
  })

  it('labels every category', () => {
    expect(
      ['academic', 'industry', 'undergraduate', 'postgraduate', 'hdr'].map(mentorBackgroundLabel)
    ).toEqual(['Academic', 'Industry', 'Undergraduate', 'Postgraduate', 'HDR'])
    expect(mentorBackgroundLabel(undefined)).toBe('—')
    expect(mentorBackgroundLabel('')).toBe('—')
  })
})
