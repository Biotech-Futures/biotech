import { afterEach, describe, expect, it, vi } from 'vitest'
import { mount, flushPromises, type VueWrapper } from '@vue/test-utils'
import MatchedGroupsPanel from '@/components/admin/groups/MatchedGroupsPanel.vue'
import { appSelectLabels, pickAppSelect } from '@/__tests__/appSelect'
import { setIdleDays } from '@/composables/admin/useIdleThreshold'
import { DEFAULT_IDLE_DAYS } from '@/utils/mentorFormat'

// Old enough that the join-date grace never applies, so these fixtures are
// judged on their messages alone. `joinedRecently` is the opposite case.
const longAgo = '2019-01-01T00:00:00Z'
const joinedRecently = new Date(Date.now() - 5 * 86_400_000).toISOString()

const activeGroup = {
  membershipId: 100,
  groupId: 1,
  groupName: 'BTF1',
  countryName: 'Australia',
  studentCount: 2,
  students: [
    { id: 10, name: 'Ada Lovelace', hasLoggedIn: true, interests: ['Genomics'] },
    { id: 11, name: 'Grace Hopper', hasLoggedIn: false, interests: [] }
  ],
  mentor: {
    mentorId: 20,
    name: 'Marie Curie',
    isActive: true,
    // Recent enough not to count as idle.
    lastMessageAt: new Date().toISOString(),
    dateJoined: longAgo,
    countryName: 'Australia',
    institution: 'USYD'
  }
}

const inactiveGroup = {
  membershipId: 101,
  groupId: 2,
  groupName: 'BTF2',
  countryName: 'Singapore',
  studentCount: 0,
  students: [],
  mentor: {
    mentorId: 21,
    name: 'Nikola Tesla',
    isActive: false,
    lastMessageAt: null,
    dateJoined: longAgo,
    countryName: 'Singapore',
    institution: null
  }
}

// Enabled account, but has not posted in years: idle, not inactive. The two
// used to render identically as "Active", since only `isActive` was consulted.
const idleGroup = {
  membershipId: 102,
  groupId: 3,
  groupName: 'BTF3',
  countryName: 'Australia',
  studentCount: 0,
  students: [],
  mentor: {
    mentorId: 24,
    name: 'Quiet Mentor',
    isActive: true,
    lastMessageAt: '2020-01-01T00:00:00Z',
    dateJoined: longAgo,
    countryName: 'Australia',
    institution: 'UTS'
  }
}

// Joined five days ago and has not posted. Silent, but not idle: the matcher
// gives a newcomer the benefit of the doubt and this screen now reads it the
// same way, so the row should say Active.
const gracedGroup = {
  membershipId: 103,
  groupId: 4,
  groupName: 'BTF4',
  countryName: 'Australia',
  studentCount: 0,
  students: [],
  mentor: {
    mentorId: 26,
    name: 'New Mentor',
    isActive: true,
    lastMessageAt: null,
    dateJoined: joinedRecently,
    countryName: 'Australia',
    institution: 'UOW'
  }
}

// Replacements are only offered from mentors who are active and not idle, so
// the pool carries a recent message. `quiet` and `deactivated` are the two
// that must never be offered.
const spokeToday = new Date().toISOString()

const mentorPool = [
  { mentorId: 20, name: 'Marie Curie', countryName: 'Australia', institution: 'USYD', interests: [], maxGroupCount: 4, currentAssignedCount: 1, remainingCapacity: 3, isActive: true, lastMessageAt: spokeToday, dateJoined: longAgo },
  { mentorId: 22, name: 'Ada King', countryName: 'Australia', institution: 'UNSW', interests: [], maxGroupCount: 2, currentAssignedCount: 2, remainingCapacity: 0, isActive: true, lastMessageAt: spokeToday, dateJoined: longAgo },
  { mentorId: 23, name: 'Rosalind Franklin', countryName: 'Australia', institution: 'ANU', interests: [], maxGroupCount: 3, currentAssignedCount: 1, remainingCapacity: 2, isActive: true, lastMessageAt: spokeToday, dateJoined: longAgo },
  { mentorId: 24, name: 'Quiet Mentor', countryName: 'Australia', institution: 'UTS', interests: [], maxGroupCount: 3, currentAssignedCount: 1, remainingCapacity: 2, isActive: true, lastMessageAt: '2020-01-01T00:00:00Z', dateJoined: longAgo },
  { mentorId: 25, name: 'Deactivated Mentor', countryName: 'Australia', institution: 'UOW', interests: [], maxGroupCount: 3, currentAssignedCount: 1, remainingCapacity: 2, isActive: false, lastMessageAt: spokeToday, dateJoined: longAgo },
  // Never posted, but too new to judge: offerable, unlike Quiet Mentor above.
  { mentorId: 26, name: 'New Mentor', countryName: 'Australia', institution: 'UOW', interests: [], maxGroupCount: 3, currentAssignedCount: 1, remainingCapacity: 2, isActive: true, lastMessageAt: null, dateJoined: joinedRecently }
]

const fetchMockFor = (
  groups: unknown[],
  opts: {
    replaceStatus?: number
    replaceBody?: unknown
    failGroupsRefetch?: boolean
    studentUser?: unknown
    studentError?: string
    suggestions?: unknown[]
  } = {}
) => {
  let matchedGroupsGets = 0
  return vi.fn().mockImplementation((url: string, init?: RequestInit) => {
    const method = (init?.method || 'GET').toUpperCase()
    const u = String(url)

    if (u.includes('/services/csrf/')) {
      return Promise.resolve(new Response(JSON.stringify({ csrfToken: 'csrf-test' }), { status: 200 }))
    }
    if (method === 'POST' && u.includes('/mentor-match/unassign/')) {
      return Promise.resolve(
        new Response(JSON.stringify({ msg: 'ok', data: { unassignedCount: 1 } }), { status: 200 })
      )
    }
    if (method === 'POST' && u.includes('/mentor-match/replace/')) {
      return Promise.resolve(
        new Response(JSON.stringify(opts.replaceBody ?? { msg: 'ok', data: { replaced: 1 } }), {
          status: opts.replaceStatus ?? 200
        })
      )
    }
    if (method === 'POST' && u.includes('/mentor-match/confirm/')) {
      return Promise.resolve(
        new Response(JSON.stringify({ msg: 'ok', data: { confirmedCount: 1 } }), { status: 200 })
      )
    }
    if (method === 'GET' && u.includes('/mentor-match/replace-suggestions/')) {
      return Promise.resolve(
        new Response(
          JSON.stringify({
            msg: 'ok',
            data: {
              groupId: 2,
              groupName: 'BTF2',
              suggestions: opts.suggestions ?? [
                { mentorUserId: 23, name: 'Rosalind Franklin', institution: 'ANU', remainingCapacity: 2, atCapacity: false, score: 90, reason: 'Great fit' }
              ]
            }
          }),
          { status: 200 }
        )
      )
    }
    const singleUserMatch = u.match(/\/user\/(\d+)\/?$/)
    if (method === 'GET' && singleUserMatch) {
      if (opts.studentError) {
        return Promise.resolve(
          new Response(JSON.stringify({ error: opts.studentError, code: 'not_found' }), { status: 404 })
        )
      }
      const userId = Number(singleUserMatch[1])
      const user = opts.studentUser ?? {
        id: userId,
        firstName: 'Ada',
        lastName: 'Lovelace',
        email: 'ada@example.com',
        role: 'student',
        country: 'Australia',
        state: 'NSW',
        isActive: true,
        hasLoggedIn: true,
        lastLogin: '2026-01-02T10:00:00Z',
        lastEditedBy: null,
        lastEditedAt: null,
        schoolName: 'Science High',
        yearLevel: 11,
        interests: ['Genetics', 'Genomics'],
        groupName: 'BTF1',
        guardianFirstName: 'Lord',
        guardianLastName: 'Byron',
        guardianEmail: 'byron@example.com',
        joinPermissionReceived: true,
        joinpermResponseId: 'BTF-10',
        mediaConsent: true
      }
      return Promise.resolve(
        new Response(JSON.stringify({ msg: 'ok', data: user }), { status: 200 })
      )
    }
    if (method === 'GET' && u.includes('/user/')) {
      return Promise.resolve(
        new Response(
          JSON.stringify({
            msg: 'ok',
            data: {
              items: [
                { id: 10, firstName: 'Ada', lastName: 'Lovelace', email: 'ada@example.com', role: 'student' }
              ],
              total: 1,
              page: 1,
              limit: 10,
              hasMore: false
            }
          }),
          { status: 200 }
        )
      )
    }
    if (method === 'GET' && u.includes('/mentor-match/matched-groups/')) {
      matchedGroupsGets += 1
      // First GET is the initial load; a later one is a post-action refresh.
      if (opts.failGroupsRefetch && matchedGroupsGets > 1) {
        return Promise.resolve(new Response(JSON.stringify({ msg: 'Server error', data: null }), { status: 500 }))
      }
      return Promise.resolve(new Response(JSON.stringify({ msg: 'ok', data: groups }), { status: 200 }))
    }
    if (method === 'GET' && u.includes('/mentor-match/mentors/')) {
      return Promise.resolve(new Response(JSON.stringify({ msg: 'ok', data: mentorPool }), { status: 200 }))
    }
    return Promise.resolve(new Response(JSON.stringify({}), { status: 200 }))
  })
}

let wrapper: VueWrapper | null = null

afterEach(() => {
  // The threshold is module-level, so it would otherwise leak between tests.
  setIdleDays(DEFAULT_IDLE_DAYS)
  wrapper?.unmount()
  wrapper = null
  vi.unstubAllGlobals()
})

describe('MatchedGroupsPanel', () => {
  it('loads and renders matched groups with the inactive badge', async () => {
    const fetchMock = fetchMockFor([activeGroup, inactiveGroup])
    vi.stubGlobal('fetch', fetchMock)
    wrapper = mount(MatchedGroupsPanel)
    await flushPromises()

    expect(wrapper.text()).toContain('BTF1')
    expect(wrapper.text()).toContain('Marie Curie')
    // Capacity is looked up from the separately-fetched mentor pool (Marie
    // Curie is mentorId 20 there: currentAssignedCount 1, maxGroupCount 4).
    expect(wrapper.text()).toContain('1/4')
    expect(wrapper.text()).toContain('BTF2')
    expect(wrapper.text()).toContain('1 to replace')
    const replaceInactiveButton = wrapper.findAll('button').find((b) => b.text().includes('Replace Idle Mentors'))
    expect(replaceInactiveButton).toBeDefined()
  })

  it('disables the "Replace Idle Mentors" button when no mentor needs replacing', async () => {
    const fetchMock = fetchMockFor([activeGroup])
    vi.stubGlobal('fetch', fetchMock)
    wrapper = mount(MatchedGroupsPanel)
    await flushPromises()

    expect(wrapper.text()).not.toContain('to replace')
    const replaceInactiveButton = wrapper.findAll('button').find((b) => b.text().includes('Replace Idle Mentors'))
    expect(replaceInactiveButton).toBeDefined()
    expect(replaceInactiveButton!.attributes('disabled')).toBeDefined()
  })

  it('counts by the threshold the Mentors page set, not a fixed 30 days', async () => {
    // Active, and quiet for 20 days: not idle while the threshold is 30.
    const quietGroup = {
      ...activeGroup,
      mentor: {
        ...activeGroup.mentor,
        lastMessageAt: new Date(Date.now() - 20 * 24 * 60 * 60 * 1000).toISOString()
      }
    }
    vi.stubGlobal('fetch', fetchMockFor([quietGroup]))
    wrapper = mount(MatchedGroupsPanel)
    await flushPromises()

    expect(wrapper.text()).not.toContain('to replace')

    // The Mentors page drops it to a fortnight; this panel follows, instead of
    // staying on its own hardcoded 30 and disagreeing about the count.
    setIdleDays(14)
    await flushPromises()

    expect(wrapper.text()).toContain('1 to replace')
    const button = wrapper.findAll('button').find((b) => b.text().includes('Replace Idle Mentors'))
    expect(button!.attributes('disabled')).toBeUndefined()
  })

  it('expands a row to show its students', async () => {
    const fetchMock = fetchMockFor([activeGroup])
    vi.stubGlobal('fetch', fetchMock)
    wrapper = mount(MatchedGroupsPanel)
    await flushPromises()

    expect(wrapper.text()).not.toContain('Never signed in')

    await wrapper.find('tbody tr').trigger('click')

    expect(wrapper.text()).toContain('Ada Lovelace')
    expect(wrapper.text()).toContain('Grace Hopper')
    expect(wrapper.text()).toContain('Never signed in')
  })

  it('unassigns a mentor via the per-row replace control', async () => {
    const fetchMock = fetchMockFor([activeGroup])
    vi.stubGlobal('fetch', fetchMock)
    wrapper = mount(MatchedGroupsPanel)
    await flushPromises()

    const replaceButton = wrapper.findAll('button').find((b) => b.text().trim() === 'Replace Mentor')
    expect(replaceButton).toBeDefined()
    await replaceButton!.trigger('click')

    expect(wrapper.find('.matched-groups__replace-select').exists()).toBe(true)
    await pickAppSelect(wrapper, '.matched-groups__replace-select', '— Unassign (leave unmatched)')

    const confirmButton = wrapper.findAll('button').find((b) => b.text().trim() === 'Confirm')
    await confirmButton!.trigger('click')
    await flushPromises()

    const call = fetchMock.mock.calls.find(
      ([u, i]) => String(u).includes('/mentor-match/unassign/') && (i as RequestInit | undefined)?.method === 'POST'
    ) as [string, RequestInit]
    expect(call).toBeDefined()
    // Nobody arrives on an unassign, so only the departing flag is sent,
    // and it defaults to on.
    expect(JSON.parse(String(call[1].body))).toEqual({
      groupIds: [1],
      notifyDeparting: true
    })
  })

  it('does not offer the mentor already on the group', async () => {
    // Picking them would be a replacement that replaces nothing, and the
    // bulk dialog leaves them out server-side for the same reason.
    vi.stubGlobal('fetch', fetchMockFor([activeGroup]))
    wrapper = mount(MatchedGroupsPanel)
    await flushPromises()

    const replaceButton = wrapper.findAll('button').find((b) => b.text().trim() === 'Replace Mentor')
    await replaceButton!.trigger('click')

    const labels = await appSelectLabels(wrapper, '.matched-groups__replace-select')
    expect(labels).not.toContain('Marie Curie')
    expect(labels).toContain('Rosalind Franklin')
  })

  it('does not offer an idle or deactivated mentor as a replacement', async () => {
    // The whole point of the screen is replacing mentors who have gone quiet,
    // so offering another one of those just moves the problem to a new group.
    vi.stubGlobal('fetch', fetchMockFor([activeGroup]))
    wrapper = mount(MatchedGroupsPanel)
    await flushPromises()

    const replaceButton = wrapper.findAll('button').find((b) => b.text().trim() === 'Replace Mentor')
    await replaceButton!.trigger('click')

    const labels = await appSelectLabels(wrapper, '.matched-groups__replace-select')
    expect(labels).not.toContain('Quiet Mentor')
    expect(labels).not.toContain('Deactivated Mentor')
    expect(labels).toContain('Rosalind Franklin')
  })


  it('replaces a mentor via the per-row replace control', async () => {
    const fetchMock = fetchMockFor([activeGroup])
    vi.stubGlobal('fetch', fetchMock)
    wrapper = mount(MatchedGroupsPanel)
    await flushPromises()

    const replaceButton = wrapper.findAll('button').find((b) => b.text().trim() === 'Replace Mentor')
    await replaceButton!.trigger('click')

    await pickAppSelect(wrapper, '.matched-groups__replace-select', 'Rosalind Franklin')

    const confirmButton = wrapper.findAll('button').find((b) => b.text().trim() === 'Confirm')
    await confirmButton!.trigger('click')
    await flushPromises()

    const call = fetchMock.mock.calls.find(
      ([u, i]) => String(u).includes('/mentor-match/replace/') && (i as RequestInit | undefined)?.method === 'POST'
    ) as [string, RequestInit]
    expect(call).toBeDefined()
    expect(JSON.parse(String(call[1].body))).toEqual({
      membershipId: 100,
      groupId: 1,
      newMentorUserId: 23,
      // Both notifications are opt-out, so an untouched form sends true.
      notifyDeparting: true,
      notifyIncoming: true
    })
  })

  it('sends notifyIncoming false when the admin unticks it', async () => {
    const fetchMock = fetchMockFor([activeGroup])
    vi.stubGlobal('fetch', fetchMock)
    wrapper = mount(MatchedGroupsPanel)
    await flushPromises()

    const replaceButton = wrapper.findAll('button').find((b) => b.text().trim() === 'Replace Mentor')
    await replaceButton!.trigger('click')
    await pickAppSelect(wrapper, '.matched-groups__replace-select', 'Rosalind Franklin')

    const boxes = wrapper.findAll('.matched-groups__notify input')
    expect(boxes).toHaveLength(2)
    // Both start ticked - the admin opts out rather than in.
    expect(boxes.every((box) => (box.element as HTMLInputElement).checked)).toBe(true)

    await boxes[1].setValue(false)

    const confirmButton = wrapper.findAll('button').find((b) => b.text().trim() === 'Confirm')
    await confirmButton!.trigger('click')
    await flushPromises()

    const call = fetchMock.mock.calls.find(
      ([u, i]) =>
        String(u).includes('/mentor-match/replace/') &&
        (i as RequestInit | undefined)?.method === 'POST'
    ) as [string, RequestInit]
    const body = JSON.parse(String(call[1].body))
    expect(body.notifyDeparting).toBe(true)
    expect(body.notifyIncoming).toBe(false)
  })

  it('reports a post-replace refresh failure as a stale list, not a failed replace', async () => {
    const fetchMock = fetchMockFor([activeGroup], { failGroupsRefetch: true })
    vi.stubGlobal('fetch', fetchMock)
    wrapper = mount(MatchedGroupsPanel)
    await flushPromises()

    await wrapper.findAll('button').find((b) => b.text().trim() === 'Replace Mentor')!.trigger('click')
    await pickAppSelect(wrapper, '.matched-groups__replace-select', 'Rosalind Franklin')
    await wrapper.findAll('button').find((b) => b.text().trim() === 'Confirm')!.trigger('click')
    await flushPromises()

    // The replace POST did go through...
    expect(
      fetchMock.mock.calls.some(
        ([u, i]) => String(u).includes('/mentor-match/replace/') && (i as RequestInit | undefined)?.method === 'POST'
      )
    ).toBe(true)
    // ...so the message must not blame the replace.
    expect(wrapper.text()).toContain('Mentor updated, but the list could not be refreshed')
    expect(wrapper.text()).not.toContain('Action failed')
  })

  it('sorts by clicking a column header', async () => {
    const fetchMock = fetchMockFor([activeGroup, inactiveGroup])
    vi.stubGlobal('fetch', fetchMock)
    wrapper = mount(MatchedGroupsPanel)
    await flushPromises()

    // Default sort is Group asc: BTF1 before BTF2.
    const namesBefore = wrapper.findAll('.matched-groups__name').map((n) => n.text())
    expect(namesBefore).toEqual(['BTF1', 'BTF2'])

    const groupHeader = wrapper.findAll('button').find((b) => b.text().trim() === 'Group')
    await groupHeader!.trigger('click')

    const namesAfter = wrapper.findAll('.matched-groups__name').map((n) => n.text())
    expect(namesAfter).toEqual(['BTF2', 'BTF1'])
  })

  it('shows the backend rejection when replacing with a mentor at capacity', async () => {
    const fetchMock = fetchMockFor([activeGroup], {
      replaceStatus: 400,
      replaceBody: { msg: 'Mentor is at capacity (2/2).', data: null }
    })
    vi.stubGlobal('fetch', fetchMock)
    wrapper = mount(MatchedGroupsPanel)
    await flushPromises()

    const replaceButton = wrapper.findAll('button').find((b) => b.text().trim() === 'Replace Mentor')
    await replaceButton!.trigger('click')

    // Full mentors are hidden by default — reveal Ada King (mentorId 22, 2/2).
    await wrapper.find('input[type="checkbox"]').setValue(true)
    await pickAppSelect(wrapper, '.matched-groups__replace-select', 'Ada King (full)')

    const confirmButton = wrapper.findAll('button').find((b) => b.text().trim() === 'Confirm')
    await confirmButton!.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('Mentor is at capacity (2/2).')
    // The inline form must stay open on failure so the admin can pick again,
    // not silently reset as if nothing happened.
    expect(wrapper.find('.matched-groups__replace-select').exists()).toBe(true)
  })

  it('sends the unticked flag from the bulk dialog', async () => {
    // The dialog's own checkboxes, not the per-row ones: a mis-wired v-model
    // here would still pass the defaults test above and silently ignore an
    // admin who unticks a box.
    const fetchMock = fetchMockFor([activeGroup, inactiveGroup])
    vi.stubGlobal('fetch', fetchMock)
    wrapper = mount(MatchedGroupsPanel)
    await flushPromises()

    const bulkButton = wrapper.findAll('button').find((b) => b.text().includes('Replace Idle Mentors'))
    await bulkButton!.trigger('click')
    await flushPromises()

    const dialog = document.body.querySelector('[role="dialog"]') as HTMLElement
    const boxes = Array.from(
      dialog.querySelectorAll('.replace-dialog__notify input')
    ) as HTMLInputElement[]
    expect(boxes).toHaveLength(2)
    expect(boxes.every((box) => box.checked)).toBe(true)

    boxes[0].checked = false
    boxes[0].dispatchEvent(new Event('change', { bubbles: true }))
    await flushPromises()

    const confirmButton = Array.from(dialog.querySelectorAll('button')).find(
      (b) => b.textContent?.trim().startsWith('Confirm')
    ) as HTMLButtonElement
    confirmButton.dispatchEvent(new Event('click', { bubbles: true }))
    await flushPromises()

    const call = fetchMock.mock.calls.find(
      ([u, i]) =>
        String(u).includes('/mentor-match/confirm/') &&
        (i as RequestInit | undefined)?.method === 'POST'
    ) as [string, RequestInit]
    const body = JSON.parse(String(call[1].body))
    expect(body.notifyDeparting).toBe(false)
    expect(body.notifyIncoming).toBe(true)
  })

  it('replaces an inactive mentor via the bulk "Replace Idle Mentors" dialog', async () => {
    const fetchMock = fetchMockFor([activeGroup, inactiveGroup])
    vi.stubGlobal('fetch', fetchMock)
    wrapper = mount(MatchedGroupsPanel)
    await flushPromises()

    const bulkButton = wrapper.findAll('button').find((b) => b.text().includes('Replace Idle Mentors'))
    expect(bulkButton).toBeDefined()
    await bulkButton!.trigger('click')
    await flushPromises()

    const dialog = document.body.querySelector('[role="dialog"]') as HTMLElement
    expect(dialog).toBeTruthy()
    expect(dialog.textContent).toContain('BTF2')
    // The top scored (non-full) suggestion is pre-selected automatically.
    expect(dialog.textContent).toContain('Rosalind Franklin')

    const confirmButton = Array.from(dialog.querySelectorAll('button')).find(
      (b) => b.textContent?.trim().startsWith('Confirm')
    ) as HTMLButtonElement
    expect(confirmButton.disabled).toBe(false)
    confirmButton.dispatchEvent(new Event('click', { bubbles: true }))
    await flushPromises()

    const call = fetchMock.mock.calls.find(
      ([u, i]) => String(u).includes('/mentor-match/confirm/') && (i as RequestInit | undefined)?.method === 'POST'
    ) as [string, RequestInit]
    expect(call).toBeDefined()
    expect(JSON.parse(String(call[1].body))).toEqual({
      assignments: [{ groupId: 2, mentorUserId: 23 }],
      notifyDeparting: true,
      notifyIncoming: true
    })
    expect(document.body.querySelector('[role="dialog"]')).toBeNull()
  })

  it('shows an enabled but quiet mentor as Idle rather than Active', async () => {
    // The panel already counted them under "Replace Idle Mentors"; the status
    // column said "Active" in the same row, because it only read isActive.
    vi.stubGlobal('fetch', fetchMockFor([activeGroup, idleGroup, inactiveGroup]))
    wrapper = mount(MatchedGroupsPanel)
    await flushPromises()

    const statusOf = (groupName: string) => {
      const row = wrapper.findAll('tbody tr').find((r) => r.text().includes(groupName))
      return row?.find('.matched-groups__status').text()
    }

    expect(statusOf('BTF3')).toBe('Idle')
    // The other two readings are unchanged.
    expect(statusOf('BTF1')).toBe('Active')
    expect(statusOf('BTF2')).toBe('Inactive')
  })

  it('treats a mentor still inside the join-date grace as active', async () => {
    // Same reading the matcher uses, so a mentor it is happy to assign is not
    // flagged here, and is offered as a replacement rather than filtered out.
    vi.stubGlobal('fetch', fetchMockFor([activeGroup, gracedGroup, idleGroup]))
    wrapper = mount(MatchedGroupsPanel)
    await flushPromises()

    const rowFor = (groupName: string) =>
      wrapper.findAll('tbody tr').find((r) => r.text().includes(groupName))

    expect(rowFor('BTF4')?.find('.matched-groups__status').text()).toBe('Active')
    // The genuinely quiet mentor is still flagged, so the grace has not simply
    // switched the check off.
    expect(rowFor('BTF3')?.find('.matched-groups__status').text()).toBe('Idle')

    const replaceButton = wrapper
      .findAll('button')
      .find((b) => b.text().trim() === 'Replace Mentor')
    await replaceButton!.trigger('click')

    const labels = await appSelectLabels(wrapper, '.matched-groups__replace-select')
    expect(labels).toContain('New Mentor')
    expect(labels).not.toContain('Quiet Mentor')
  })

  it('does not offer an idle mentor the backend scored as a suggestion', async () => {
    // Matching is more forgiving than this screen: it forgives a recent join
    // date, so it will happily score a mentor the row beside it flags as idle.
    // The top score would normally be pre-selected, which is how an idle
    // mentor could be confirmed as a replacement in one click.
    const fetchMock = fetchMockFor([activeGroup, inactiveGroup], {
      suggestions: [
        { mentorUserId: 24, name: 'Quiet Mentor', institution: 'UTS', remainingCapacity: 2, atCapacity: false, score: 150, reason: 'Top scorer' },
        { mentorUserId: 25, name: 'Deactivated Mentor', institution: 'UOW', remainingCapacity: 2, atCapacity: false, score: 140, reason: 'Also scored' },
        { mentorUserId: 23, name: 'Rosalind Franklin', institution: 'ANU', remainingCapacity: 2, atCapacity: false, score: 90, reason: 'Great fit' }
      ]
    })
    vi.stubGlobal('fetch', fetchMock)
    wrapper = mount(MatchedGroupsPanel)
    await flushPromises()

    const bulkButton = wrapper.findAll('button').find((b) => b.text().includes('Replace Idle Mentors'))
    await bulkButton!.trigger('click')
    await flushPromises()

    const dialog = document.body.querySelector('[role="dialog"]') as HTMLElement
    expect(dialog).toBeTruthy()

    // Pre-selection takes the top of the list, so what it landed on says which
    // mentors survived the filter. Were either of the first two still there,
    // Confirm would replace an idle mentor with an idle mentor.
    expect(dialog.textContent).not.toContain('Quiet Mentor')
    expect(dialog.textContent).not.toContain('Deactivated Mentor')
    expect(dialog.textContent).toContain('Rosalind Franklin')

    const confirmButton = Array.from(dialog.querySelectorAll('button')).find(
      (b) => b.textContent?.trim().startsWith('Confirm')
    ) as HTMLButtonElement
    confirmButton.dispatchEvent(new Event('click', { bubbles: true }))
    await flushPromises()

    const call = fetchMock.mock.calls.find(
      ([u, i]) => String(u).includes('/mentor-match/confirm/') && (i as RequestInit | undefined)?.method === 'POST'
    ) as [string, RequestInit]
    expect(JSON.parse(String(call[1].body)).assignments).toEqual([
      { groupId: 2, mentorUserId: 23 }
    ])
  })

  it('clicking on a student opens their details sheet matching AdminUserDetailSheet and close returns to matched groups', async () => {
    const fetchMock = fetchMockFor([activeGroup])
    vi.stubGlobal('fetch', fetchMock)
    wrapper = mount(MatchedGroupsPanel, { attachTo: document.body })
    await flushPromises()

    // Expand the row
    await wrapper.find('tbody tr').trigger('click')

    // Find and click Ada Lovelace student button
    const studentBtn = wrapper.findAll('.matched-groups__student-btn').find(
      (b) => b.text().includes('Ada Lovelace')
    )
    expect(studentBtn).toBeDefined()
    await studentBtn!.trigger('click')
    await flushPromises()

    const dialog = document.body.querySelector('[role="dialog"]') as HTMLElement
    expect(dialog).toBeTruthy()

    // Title and description update to student details
    expect(dialog.querySelector('.admin-sheet__title')?.textContent).toBe('Ada Lovelace')
    expect(dialog.querySelector('.admin-sheet__description')?.textContent).toBe('Account details')

    // Contains Account, Student Details, Guardian Details, and Supervisor and Group
    expect(dialog.textContent).toContain('Account')
    expect(dialog.textContent).toContain('ada@example.com')
    expect(dialog.textContent).toContain('Student Details')
    expect(dialog.textContent).toContain('Science High')
    expect(dialog.textContent).toContain('Guardian Details')
    expect(dialog.textContent).toContain('Supervisor and Group')
    expect(dialog.textContent).toContain('Lord Byron')
    expect(dialog.textContent).toContain('byron@example.com')

    // Matched Groups only views a student: no Edit, and no buttons at the bottom
    expect(Array.from(dialog.querySelectorAll('button')).map((b) => b.textContent?.trim())).not.toContain('Edit')
    expect(dialog.querySelector('.admin-users-detail__footer')).toBeNull()

    // Close the sheet with its x
    const closeBtn = dialog.querySelector('.admin-sheet__close') as HTMLButtonElement
    expect(closeBtn).toBeTruthy()
    closeBtn.click()
    await flushPromises()

    expect(document.body.querySelector('[role="dialog"]')).toBeNull()
    // The matched groups table is still expanded and visible
    expect(wrapper.text()).toContain('Students (2)')
  })

  it('shows an error message in the sheet when loading student details fails', async () => {
    const fetchMock = fetchMockFor([activeGroup], { studentError: 'Student not found in database' })
    vi.stubGlobal('fetch', fetchMock)
    wrapper = mount(MatchedGroupsPanel, { attachTo: document.body })
    await flushPromises()

    await wrapper.find('tbody tr').trigger('click')
    const studentBtn = wrapper.find('.matched-groups__student-btn')
    await studentBtn.trigger('click')
    await flushPromises()

    const dialog = document.body.querySelector('[role="dialog"]') as HTMLElement
    expect(dialog).toBeTruthy()
    expect(dialog.textContent).toContain('Student not found in database')
  })

  it('shows an error and does not search or fall back to unrelated users when student id is missing', async () => {
    const groupWithStudentWithoutId = {
      ...activeGroup,
      students: [
        { name: 'Unknown Student', hasLoggedIn: false, interests: [] } as unknown as { id: number; name: string; hasLoggedIn: boolean; interests: string[] }
      ]
    }
    const fetchMock = fetchMockFor([groupWithStudentWithoutId])
    vi.stubGlobal('fetch', fetchMock)
    wrapper = mount(MatchedGroupsPanel, { attachTo: document.body })
    await flushPromises()

    await wrapper.find('tbody tr').trigger('click')
    const studentBtn = wrapper.find('.matched-groups__student-btn')
    await studentBtn.trigger('click')
    await flushPromises()

    const dialog = document.body.querySelector('[role="dialog"]') as HTMLElement
    expect(dialog).toBeTruthy()
    expect(dialog.textContent).toContain('Could not find details for this student.')
    // Verify no user list search endpoint was called to search by name or fall back to res.items[0]
    expect(
      fetchMock.mock.calls.some(([u]) => String(u).includes('/user/?') || String(u).includes('/user?'))
    ).toBe(false)
  })
})
