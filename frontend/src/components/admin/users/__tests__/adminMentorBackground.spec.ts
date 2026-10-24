import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import AdminUserFormSheet from '../AdminUserFormSheet.vue'
import AdminUserDetailSheet from '../AdminUserDetailSheet.vue'
import { createAdminUser, updateAdminUser } from '@/utils/adminAPI'
import type { AdminUser } from '@/utils/adminAPI'
import { mentorBackgroundLabel } from '@/utils/userFormat'
import { appSelectLabels, appSelectText, pickAppSelect } from '@/__tests__/appSelect'

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
  appSelectLabels(wrapper, '#f-mbg')

const UG = 'University Student – Undergraduate'
const PG = 'University Student – Postgraduate'
const HDR = 'University Student – HDR'
const CATEGORIES = ['Academic', 'Industry', UG, PG, HDR]

describe('mentor background', () => {
  beforeEach(() => {
    vi.mocked(updateAdminUser).mockClear()
    vi.mocked(createAdminUser).mockClear()
  })

  describe('form', () => {
    it('offers exactly the five categories, in order', async () => {
      const wrapper = await openForm(mentor())

      expect(await optionTexts(wrapper)).toEqual(CATEGORIES)
    })

    it('preselects the stored category', async () => {
      const wrapper = await openForm(mentor({ mentorBackground: 'hdr' }))
      expect(appSelectText(wrapper, '#f-mbg')).toBe(HDR)
    })

    it('sends a changed category', async () => {
      const wrapper = await openForm(mentor())
      await pickAppSelect(wrapper, '#f-mbg', 'Academic')
      await submit(wrapper)
      expect(lastUpdate()).toMatchObject({ mentorBackground: 'academic' })
    })

    it('sends the stored category back unchanged on an unrelated edit', async () => {
      // The form sends the whole mentor block, so the background travels with
      // every edit. What matters is that it goes back as it was.
      const wrapper = await openForm(mentor({ mentorBackground: 'hdr' }))
      await wrapper.find('#f-minst').setValue('UNSW')
      await submit(wrapper)
      expect(lastUpdate()).toMatchObject({
        mentorInstitution: 'UNSW',
        mentorBackground: 'hdr'
      })
    })

    it('creates a mentor with the chosen category', async () => {
      const wrapper = await openForm()
      await wrapper.find('#f-first').setValue('Ada')
      await wrapper.find('#f-last').setValue('Lovelace')
      await wrapper.find('#f-email').setValue('ada@example.edu')
      await pickAppSelect(wrapper, '#f-country', 'Australia')
      await wrapper.find('#f-minst').setValue('Lab One')
      await wrapper.find('input[type="checkbox"][value="Biomedical Innovations"]').setValue(true)
      await pickAppSelect(wrapper, '#f-mbg', 'Industry')
      await submit(wrapper)

      expect(wrapper.find('[role="alert"]').exists()).toBe(false)
      expect(vi.mocked(createAdminUser).mock.calls.at(-1)?.[0]).toMatchObject({
        role: 'mentor',
        mentorBackground: 'industry'
      })
    })
  })

  describe('older free-text values', () => {
    it('stays selectable instead of being shown as unset', async () => {
      const wrapper = await openForm(mentor({ mentorBackground: 'Seed mentor background.' }))

      expect(appSelectText(wrapper, '#f-mbg')).toBe('Seed mentor background.')
      expect(await optionTexts(wrapper)).toEqual([...CATEGORIES, 'Seed mentor background.'])
    })

    it('is sent back as it was stored on an unrelated edit', async () => {
      // The backend lets an unrecognised value through only when it is
      // unchanged, so sending it back exactly is what keeps the save working.
      const wrapper = await openForm(mentor({ mentorBackground: 'Research' }))
      await wrapper.find('#f-minst').setValue('UNSW')
      await submit(wrapper)

      expect(lastUpdate()).toMatchObject({
        mentorInstitution: 'UNSW',
        mentorBackground: 'Research'
      })
    })

    it('can be replaced by a category', async () => {
      const wrapper = await openForm(mentor({ mentorBackground: 'Research' }))
      await pickAppSelect(wrapper, '#f-mbg', 'Academic')
      await submit(wrapper)
      expect(lastUpdate()).toMatchObject({ mentorBackground: 'academic' })
    })

    it('is not offered for a mentor with a category or none', async () => {
      for (const stored of ['industry', null]) {
        const wrapper = await openForm(mentor({ mentorBackground: stored }))
        expect(await optionTexts(wrapper)).toEqual(CATEGORIES)
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
      expect(backgroundShown(mentor({ mentorBackground: 'hdr' }))).toBe(HDR)
      expect(backgroundShown(mentor({ mentorBackground: 'undergraduate' }))).toBe(UG)
    })

    it('shows an older value as stored, and a dash when unset', () => {
      expect(backgroundShown(mentor({ mentorBackground: 'Research' }))).toBe('Research')
      expect(backgroundShown(mentor({ mentorBackground: null }))).toBe('—')
    })
  })

  it('labels every category', () => {
    expect(
      ['academic', 'industry', 'undergraduate', 'postgraduate', 'hdr'].map(mentorBackgroundLabel)
    ).toEqual(CATEGORIES)
    expect(mentorBackgroundLabel(undefined)).toBe('—')
    expect(mentorBackgroundLabel('')).toBe('—')
  })
})
