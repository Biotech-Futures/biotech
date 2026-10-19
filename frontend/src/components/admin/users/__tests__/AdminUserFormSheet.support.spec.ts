import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'

import AdminUserFormSheet from '../AdminUserFormSheet.vue'
import { createAdminUser, setAdminUserActive, updateAdminUser } from '@/utils/adminAPI'
import { apiErrorFromResponse } from '@/utils/apiError'

/**
 * The People editor and the support role (U5 PE-01, PE-02, PE-04; U6 C1..C9).
 *
 * Adding "support" to the role list alone re-creates the defect adminweb
 * already paid for: an agent has no country, the editor insisted on one, and
 * the update call could not clear it. So the role and the geography rule are
 * tested together, at every place the form applies the rule: whether the
 * fields show, what a role change does to them, what validation asks for, and
 * what the create and update calls send.
 */
vi.mock('@/utils/adminAPI', async () => ({
  ...(await vi.importActual<typeof import('@/utils/adminAPI')>('@/utils/adminAPI')),
  createAdminUser: vi.fn(),
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
const roleSelect = () => sheet().find<HTMLSelectElement>(sheet().find('#f-role').exists() ? '#f-role' : '#f-role-edit')
const roleOptions = () => roleSelect().findAll('option').map((option) => option.attributes('value'))

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

    expect(roleOptions()).toEqual(['student', 'mentor', 'supervisor', 'admin', 'support'])
    expect(roleSelect().findAll('option').at(-1)!.text()).toBe('Support')
  })

  it('shows an existing support agent’s role instead of a blank select', async () => {
    // Before the role was in the list, the edit form had no option matching
    // "support" and rendered the select empty.
    await openSheet(agentRow())

    expect(roleSelect().element.value).toBe('support')
  })
})

describe('country and state for a role without geography (C3, C4)', () => {
  it('hides country and state for support', async () => {
    await openSheet()
    await roleSelect().setValue('support')

    expect(sheet().find('#f-country').exists()).toBe(false)
    expect(sheet().find('#f-state').exists()).toBe(false)
  })

  it('still asks a student for a country', async () => {
    // Load-bearing: hiding the fields for every role passes the test above.
    await openSheet()

    expect(sheet().find('#f-country').exists()).toBe(true)
  })

  it('drops a country picked earlier when the role moves to support', async () => {
    const pickedCountry = () =>
      sheet().find<HTMLSelectElement>('#f-country').element.selectedOptions[0]?.text
    await openSheet()
    await sheet().find('#f-country').setValue(1)
    expect(pickedCountry()).toBe('Australia')

    await roleSelect().setValue('support')
    await roleSelect().setValue('student')

    // Back on a role that has geography, the old pick is not waiting there.
    expect(pickedCountry()).toBe('Unassigned')
  })

  it('drops a stored country when an existing account is moved to support', async () => {
    // The edit form has its own role select (#f-role-edit), with its own
    // change listener. The test above only reaches the create one.
    const pickedCountry = () =>
      sheet().find<HTMLSelectElement>('#f-country').element.selectedOptions[0]?.text
    await openSheet(agentRow({ role: 'mentor', country: AUSTRALIA }))
    expect(pickedCountry()).toBe('Australia')

    await roleSelect().setValue('support')
    await roleSelect().setValue('mentor')

    expect(pickedCountry()).toBe('Unassigned')
  })
})

describe('validation (C5)', () => {
  it('creates a support agent with no country, and sends none', async () => {
    await openSheet()
    await fill({ '#f-first': 'Sam', '#f-last': 'Reid', '#f-email': 'sam@example.com' })
    await roleSelect().setValue('support')
    await submit()

    expect(sheet().text()).not.toContain('Country is required')
    expect(createAdminUser).toHaveBeenCalledTimes(1)
    expect(createAdminUser).toHaveBeenCalledWith({
      email: 'sam@example.com',
      firstName: 'Sam',
      lastName: 'Reid',
      role: 'support',
      active: true
    })
  })

  it('still refuses a mentor with no country, in words that fit every role', async () => {
    // "non-admin users" stopped being true of this rule when support joined
    // admin in it.
    await openSheet()
    await fill({ '#f-first': 'Maya', '#f-last': 'Chen', '#f-email': 'maya@example.com' })
    await roleSelect().setValue('mentor')
    await submit()

    expect(sheet().find('[role="alert"]').text()).toBe('Country is required for this role.')
    expect(createAdminUser).not.toHaveBeenCalled()
  })
})

describe('saving an existing support agent (C6, the defect this all guards)', () => {
  it('saves a surname change with country and state cleared, not refused', async () => {
    // Before this port: "Country is required for non-admin users." and no
    // request at all, so an agent created elsewhere could not be edited here.
    await openSheet(agentRow())
    await sheet().find('#f-last').setValue('Reid-Smith')
    await submit()

    expect(updateAdminUser).toHaveBeenCalledTimes(1)
    expect(updateAdminUser).toHaveBeenCalledWith(21, {
      firstName: 'Sam',
      lastName: 'Reid-Smith',
      role: 'support',
      countryId: null,
      stateId: null
    })
  })

  it('clears a country and state left over from an earlier role', async () => {
    // An account that was a mentor in NSW before it became an agent still
    // carries both on the server. The form hides them for support, so a save
    // must clear them rather than send the hidden values back.
    await openSheet(agentRow({ country: AUSTRALIA, state: NSW }))
    await sheet().find('#f-last').setValue('Reid-Smith')
    await submit()

    expect(updateAdminUser).toHaveBeenCalledTimes(1)
    expect(updateAdminUser).toHaveBeenCalledWith(21, {
      firstName: 'Sam',
      lastName: 'Reid-Smith',
      role: 'support',
      countryId: null,
      stateId: null
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
    await roleSelect().setValue('mentor')

    expect(note().text().replace(/\s+/g, ' ')).toBe(
      'Saving with this role removes their access to the support queue. Tickets they own stay in ' +
        'their name until somebody reassigns them.'
    )
    expect(roleSelect().attributes('aria-describedby')).toBe('f-role-support-note')
  })

  it('says nothing while the role stays support', async () => {
    await openSheet(agentRow())

    expect(note().exists()).toBe(false)
  })

  it('says nothing for a stored "Support" saved as "support", which the server does not count as a move', async () => {
    await openSheet(agentRow({ role: 'Support' }))
    await roleSelect().setValue('support')

    expect(note().exists()).toBe(false)
  })

  it('still warns about a stored "Support" moved to mentor', async () => {
    // The other direction of the case-fold. The server folds both names
    // before it decides, so a row stored as "Support" loses the queue on
    // this save like any other agent.
    await openSheet(agentRow({ role: 'Support' }))
    await roleSelect().setValue('mentor')

    expect(note().exists()).toBe(true)
  })

  it('says nothing when an agent is made an administrator, who keeps the queue', async () => {
    // The save deletes the SupportScope row and creates an AdminScope row, and
    // is_support() is true for every admin (backend tickets/permissions.py).
    // A note saying they lose the queue would be false.
    await openSheet(agentRow())
    await roleSelect().setValue('admin')

    expect(note().exists()).toBe(false)
    expect(roleSelect().attributes('aria-describedby')).toBeUndefined()
  })

  it('says nothing when somebody who is not an agent changes role', async () => {
    // Load-bearing: a note shown on every role change passes the first test.
    await openSheet(agentRow({ role: 'mentor', country: AUSTRALIA }))
    await roleSelect().setValue('student')

    expect(note().exists()).toBe(false)
  })
})
