import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'

import AdminUserFormSheet from '../AdminUserFormSheet.vue'
import { appSelectLabels, appSelectText, pickAppSelect } from '@/__tests__/appSelect'
import { createAdminUser, setAdminUserActive, updateAdminUser } from '@/utils/adminAPI'
import { apiErrorFromResponse } from '@/utils/apiError'

/**
 * The People editor and the support role (U5 PE-01, PE-02, PE-04; U6 C1..C9).
 *
 * Since main's Add user rework (20 October 2026) no role has to give a
 * country: the form shows country and state as optional fields for every role
 * but admin, support included, and sends whatever is picked. What stays the
 * support role's own is tested here: it is offered, an agent can be made and
 * then saved without a country (the defect adminweb paid for: the editor
 * insisted on one and the save was refused), and moving an agent off the role
 * says what the save takes away (C9).
 */
vi.mock('@/utils/adminAPI', async () => ({
  ...(await vi.importActual<typeof import('@/utils/adminAPI')>('@/utils/adminAPI')),
  createAdminUser: vi.fn(),
  checkAdminUserEmails: vi.fn(async () => ({})),
  updateAdminUser: vi.fn(),
  setAdminUserActive: vi.fn()
}))

const AUSTRALIA = { id: 1, countryName: 'Australia' }
const NSW = { id: 5, stateName: 'NSW', countryName: 'Australia' }

// Shaped like a row from GET /api/v1/admin/user/, the way the People page
// hands one to the editor.
const agentRow = (overrides: Record<string, unknown> = {}) =>
  ({
    id: 21,
    firstName: 'Sam',
    lastName: 'Reid',
    email: 'sam@example.com',
    role: 'support',
    country: null,
    state: null,
    groupId: null,
    groupName: null,
    schoolName: null,
    mentorBackground: null,
    mentorInstitution: null,
    mentorReason: null,
    mentorMaxGroupCount: null,
    yearLevel: null,
    joinPermissionReceived: false,
    interests: [],
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
  }) as never

let wrapper: VueWrapper | null = null

async function openSheet(user: unknown = null) {
  wrapper = mount(AdminUserFormSheet, {
    props: {
      modelValue: false,
      userNoun: 'user',
      user: user as never,
      isSupervisorMode: false,
      countries: [AUSTRALIA],
      states: [NSW],
      supervisors: []
    },
    global: { stubs: { Teleport: true } }
  })
  // The sheet fills its form when it opens, not when it mounts.
  await wrapper.setProps({ modelValue: true })
  await flushPromises()
  return wrapper
}

const sheet = () => wrapper!
// The create form and the edit form each have their own role dropdown.
const roleField = () => (sheet().find('#f-role').exists() ? '#f-role' : '#f-role-edit')
const pickRole = (label: string) => pickAppSelect(sheet(), roleField(), label)

async function fill(fields: Record<string, string>) {
  for (const [selector, value] of Object.entries(fields)) {
    await sheet().find(selector).setValue(value)
  }
}

async function submit() {
  await sheet().find('form').trigger('submit')
  await flushPromises()
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(createAdminUser).mockResolvedValue({ msg: 'ok', data: agentRow() })
  vi.mocked(updateAdminUser).mockResolvedValue({ msg: 'ok', data: agentRow() })
  vi.mocked(setAdminUserActive).mockResolvedValue(undefined as never)
})

afterEach(() => {
  wrapper?.unmount()
  wrapper = null
})

describe('the role list (C1)', () => {
  it('offers Support when creating an account', async () => {
    await openSheet()

    expect(await appSelectLabels(sheet(), '#f-role')).toEqual(['Student', 'Mentor', 'Supervisor', 'Admin', 'Support'])
  })

  it('shows an existing support agent’s role instead of a blank box', async () => {
    // Before the role was in the list, the edit form had no choice matching
    // "support" and showed the role empty.
    await openSheet(agentRow())

    expect(appSelectText(sheet(), '#f-role-edit')).toBe('Support')
  })
})

describe('an agent without a country (C5, C6)', () => {
  it('creates a support agent with no country, and sends none', async () => {
    await openSheet()
    await fill({ '#f-first': 'Sam', '#f-last': 'Reid', '#f-email': 'sam@example.com' })
    await pickRole('Support')
    ;(sheet().vm as unknown as { form: { role: string } }).form.role = 'support'
    await submit()

    expect(sheet().find('[role="alert"]').exists()).toBe(false)
    expect(createAdminUser).toHaveBeenCalledTimes(1)
    const sent = vi.mocked(createAdminUser).mock.calls[0][0] as unknown as Record<string, unknown>
    expect(sent).toMatchObject({
      email: 'sam@example.com',
      firstName: 'Sam',
      lastName: 'Reid',
      role: 'support',
      active: true
    })
    expect(sent).not.toHaveProperty('country')
    expect(sent).not.toHaveProperty('state')
  })

  it('saves a surname change for an agent with no country, and leaves the country alone', async () => {
    // Before the port: "Country is required for non-admin users." and no
    // request at all, so an agent created elsewhere could not be edited here.
    await openSheet(agentRow())
    await sheet().find('#f-last').setValue('Reid-Smith')
    await submit()

    expect(updateAdminUser).toHaveBeenCalledTimes(1)
    const [id, sent] = vi.mocked(updateAdminUser).mock.calls[0] as unknown as [number, Record<string, unknown>]
    expect(id).toBe(21)
    expect(sent).toMatchObject({ firstName: 'Sam', lastName: 'Reid-Smith', role: 'support' })
    // Not null: undefined is left out of the request body, so the server keeps
    // the country as it is rather than being asked to clear it.
    expect(sent.countryId).toBeUndefined()
    expect(sent.stateId).toBeUndefined()
  })

  it('saves an agent who kept a country and state from an earlier role, with both', async () => {
    // An account that was a mentor in NSW before it became an agent. The form
    // shows both, so a save sends them back unchanged.
    await openSheet(agentRow({ country: AUSTRALIA, state: NSW }))
    await sheet().find('#f-last').setValue('Reid-Smith')
    await submit()

    expect(updateAdminUser).toHaveBeenCalledTimes(1)
    expect(vi.mocked(updateAdminUser).mock.calls[0][1]).toMatchObject({
      role: 'support',
      countryId: 1,
      stateId: 5
    })
  })

  it('shows the server’s own reason when it refuses the save (PE-04)', async () => {
    // A 400 carrying "Country cannot be cleared" is what the old update path
    // produced for an agent. It reaches the form as the server's words.
    vi.mocked(updateAdminUser).mockRejectedValue(
      await apiErrorFromResponse(
        new Response(JSON.stringify({ msg: 'Country cannot be cleared', data: null }), {
          status: 400,
          headers: { 'Content-Type': 'application/json' }
        })
      )
    )
    vi.spyOn(console, 'warn').mockImplementation(() => {})
    await openSheet(agentRow())
    await submit()

    expect(sheet().find('[role="alert"]').text()).toBe('Country cannot be cleared')
  })
})

describe('moving an agent off the support role (C9)', () => {
  const note = () => sheet().find('#f-role-support-note')

  it('says that saving will take away their queue access', async () => {
    await openSheet(agentRow())
    await pickRole('Mentor')

    expect(note().text().replace(/\s+/g, ' ')).toBe(
      'Saving with this role removes their access to the support queue. Tickets they own stay in ' +
        'their name until somebody reassigns them.'
    )
    // On the field itself: AppSelect hands aria-* to its input.
    expect(sheet().find('#f-role-edit').attributes('aria-describedby')).toBe('f-role-support-note')
  })

  it('says nothing while the role stays support', async () => {
    await openSheet(agentRow())

    expect(note().exists()).toBe(false)
  })

  it('says nothing for a stored "Support" saved as "support", which the server does not count as a move', async () => {
    await openSheet(agentRow({ role: 'Support' }))
    await pickRole('Support')

    expect(note().exists()).toBe(false)
  })

  it('still warns about a stored "Support" moved to mentor', async () => {
    // The other direction of the case-fold. The server folds both names
    // before it decides, so a row stored as "Support" loses the queue on
    // this save like any other agent.
    await openSheet(agentRow({ role: 'Support' }))
    await pickRole('Mentor')

    expect(note().exists()).toBe(true)
  })

  it('says nothing when an agent is made an administrator, who keeps the queue', async () => {
    // The save deletes the SupportScope row and creates an AdminScope row, and
    // is_support() is true for every admin (backend tickets/permissions.py).
    // A note saying they lose the queue would be false.
    await openSheet(agentRow())
    await pickRole('Admin')

    expect(note().exists()).toBe(false)
    expect(sheet().find('#f-role-edit').attributes('aria-describedby')).toBeUndefined()
  })

  it('says nothing when somebody who is not an agent changes role', async () => {
    // Load-bearing: a note shown on every role change passes the first test.
    await openSheet(agentRow({ role: 'mentor', country: AUSTRALIA }))
    await pickRole('Student')

    expect(note().exists()).toBe(false)
  })
})
