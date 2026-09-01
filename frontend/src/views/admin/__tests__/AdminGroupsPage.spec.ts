import { afterEach, describe, expect, it, vi } from 'vitest'
import { mount, flushPromises, type VueWrapper } from '@vue/test-utils'
import AdminGroupsPage from '@/views/admin/AdminGroupsPage.vue'

const groupA = {
  id: 1,
  name: 'BTF1',
  members: [{ id: '10', name: 'Ada Lovelace', email: 'ada@example.com', role: 'student', membershipId: 100 }],
  mentor: { id: '20', name: 'Grace Hopper', email: 'grace@example.com', role: 'mentor', membershipId: 200 },
  createdAt: '2026-01-01T00:00:00Z',
  updatedAt: '2026-01-01T00:00:00Z'
}

const groupB = {
  id: 2,
  name: 'BTF2',
  members: [],
  mentor: null,
  createdAt: '2026-01-02T00:00:00Z',
  updatedAt: '2026-01-02T00:00:00Z'
}

const createdGroup = {
  id: 99,
  name: 'BTF41',
  members: [],
  mentor: null,
  createdAt: '2026-01-03T00:00:00Z',
  updatedAt: '2026-01-03T00:00:00Z'
}

const renamedGroupA = { ...groupA, name: 'Renamed Group' }

const fetchMockFor = (groups: unknown[], totalCount = groups.length) =>
  vi.fn().mockImplementation((url: string, init?: RequestInit) => {
    const method = (init?.method || 'GET').toUpperCase()
    let payload: Record<string, unknown>
    let status = 200

    if (url.includes('/services/csrf/')) {
      payload = { csrfToken: 'csrf-test' }
    } else if (url.includes('/mentor-match/matched-groups/')) {
      payload = { msg: 'ok', data: [] }
    } else if (url.includes('/mentor-match/mentors/')) {
      payload = { msg: 'ok', data: [] }
    } else if (url.includes('/group/next-name/')) {
      payload = { msg: 'ok', data: { name: 'BTF41' } }
    } else if (method === 'POST' && url.includes('/group/')) {
      payload = { msg: 'Group created successfully', data: createdGroup }
      status = 201
    } else if (method === 'PUT' && url.includes('/group/')) {
      payload = { msg: 'Group updated successfully', data: renamedGroupA }
    } else if (method === 'GET' && url.includes('/group/')) {
      payload = { msg: 'ok', data: { items: groups, total: totalCount, page: 1, limit: 25, has_more: totalCount > groups.length } }
    } else {
      payload = {}
    }

    return Promise.resolve(
      new Response(JSON.stringify(payload), { status, headers: { 'Content-Type': 'application/json' } })
    )
  })

const listCall = (fetchMock: ReturnType<typeof vi.fn>) =>
  [...fetchMock.mock.calls]
    .reverse()
    .find((call) => {
      const [url, init] = call as [string, RequestInit?]
      const method = (init?.method || 'GET').toUpperCase()
      return method === 'GET' && String(url).includes('/group/') && !String(url).includes('/group/next-name/')
    })

const dialogs = () => Array.from(document.body.querySelectorAll('[role="dialog"]'))

let wrapper: VueWrapper | null = null

afterEach(() => {
  wrapper?.unmount()
  wrapper = null
  document.body.innerHTML = ''
  vi.unstubAllGlobals()
  vi.useRealTimers()
})

describe('AdminGroupsPage', () => {
  it('loads and renders group rows', async () => {
    vi.stubGlobal('fetch', fetchMockFor([groupA, groupB]))
    wrapper = mount(AdminGroupsPage)
    await flushPromises()

    expect(wrapper.text()).toContain('BTF1')
    expect(wrapper.text()).toContain('BTF2')
    expect(wrapper.text()).toContain('Grace Hopper')
    expect(wrapper.text()).toContain('Unassigned')
    expect(wrapper.text()).toContain('1 student')
  })

  it('switches to the Matched Groups tab and hides the groups list', async () => {
    vi.stubGlobal('fetch', fetchMockFor([groupA, groupB]))
    wrapper = mount(AdminGroupsPage)
    await flushPromises()

    const matchedTab = wrapper.findAll('button').find((b) => b.text().trim() === 'Matched Groups')
    expect(matchedTab).toBeDefined()
    await matchedTab!.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('No confirmed mentor assignments yet.')
    expect(wrapper.text()).not.toContain('BTF1')
    expect(wrapper.findAll('button').find((b) => b.text().trim().includes('New group'))).toBeUndefined()
  })

  it('searches by group name after the debounce', async () => {
    vi.useFakeTimers()
    const fetchMock = fetchMockFor([groupA])
    vi.stubGlobal('fetch', fetchMock)
    wrapper = mount(AdminGroupsPage)
    await flushPromises()

    await wrapper.find('input[type="search"]').setValue('BTF1')
    vi.advanceTimersByTime(300)
    await flushPromises()

    expect(String(listCall(fetchMock)?.[0])).toContain('searchGroup=BTF1')
  })

  it('filters by mentor status', async () => {
    const fetchMock = fetchMockFor([groupB])
    vi.stubGlobal('fetch', fetchMock)
    wrapper = mount(AdminGroupsPage)
    await flushPromises()

    await wrapper.find('select').setValue('unmatched')
    await flushPromises()

    expect(String(listCall(fetchMock)?.[0])).toContain('mentorStatus=unmatched')
  })

  it('sorts by clicking a sortable column header', async () => {
    const fetchMock = fetchMockFor([groupA, groupB])
    vi.stubGlobal('fetch', fetchMock)
    wrapper = mount(AdminGroupsPage)
    await flushPromises()

    const membersHeader = wrapper.findAll('button').find((b) => b.text().trim() === 'Members')
    expect(membersHeader).toBeDefined()
    await membersHeader!.trigger('click')
    await flushPromises()

    const calledUrl = String(listCall(fetchMock)?.[0])
    expect(calledUrl).toContain('sortBy=members')
    expect(calledUrl).toContain('sortOrder=asc')
  })

  it('requests the next page when the pager is used', async () => {
    const fetchMock = fetchMockFor([groupA, groupB], 60)
    vi.stubGlobal('fetch', fetchMock)
    wrapper = mount(AdminGroupsPage)
    await flushPromises()

    const nextButton = wrapper.find('[aria-label="Next page"]')
    expect(nextButton.exists()).toBe(true)
    await nextButton.trigger('click')
    await flushPromises()

    expect(String(listCall(fetchMock)?.[0])).toContain('page=2')
  })

  it('creates a group with an auto-generated name', async () => {
    const fetchMock = fetchMockFor([])
    vi.stubGlobal('fetch', fetchMock)
    wrapper = mount(AdminGroupsPage)
    await flushPromises()

    const newGroupButton = wrapper.findAll('button').find((b) => b.text().trim().includes('New group'))
    expect(newGroupButton).toBeDefined()
    await newGroupButton!.trigger('click')
    await flushPromises()

    const dialog = dialogs().find((d) => d.textContent!.includes('New group'))
    expect(dialog).toBeDefined()

    const createButton = Array.from(dialog!.querySelectorAll('button')).find((b) => b.textContent!.trim() === 'Create')
    expect(createButton).toBeDefined()
    createButton!.dispatchEvent(new Event('click', { bubbles: true }))
    await flushPromises()

    const [, init] = fetchMock.mock.calls.find(
      ([u, i]) => String(u).includes('/api/v1/admin/group/') && (i as RequestInit | undefined)?.method === 'POST'
    ) as [string, RequestInit]
    expect(JSON.parse(String(init.body)).name).toBeUndefined()
    expect(dialogs().find((d) => d.textContent!.includes('New group'))).toBeUndefined()
  })

  it('renames a group', async () => {
    const fetchMock = fetchMockFor([groupA])
    vi.stubGlobal('fetch', fetchMock)
    wrapper = mount(AdminGroupsPage)
    await flushPromises()

    const renameButton = wrapper.findAll('button').find((b) => b.text().trim() === 'Rename')
    expect(renameButton).toBeDefined()
    await renameButton!.trigger('click')
    await flushPromises()

    const dialog = dialogs().find((d) => d.textContent!.includes('Rename group'))
    expect(dialog).toBeDefined()

    const nameInput = dialog!.querySelector('input[type="text"]') as HTMLInputElement
    expect(nameInput.value).toBe('BTF1')

    nameInput.value = 'Renamed Group'
    nameInput.dispatchEvent(new Event('input', { bubbles: true }))
    await flushPromises()

    const saveButton = Array.from(dialog!.querySelectorAll('button')).find((b) => b.textContent!.trim() === 'Save')
    expect(saveButton).toBeDefined()
    saveButton!.dispatchEvent(new Event('click', { bubbles: true }))
    await flushPromises()

    const [, init] = fetchMock.mock.calls.find(([u, i]) => {
      const method = (i as RequestInit | undefined)?.method
      return String(u).includes('/group/1/') && method === 'PUT'
    }) as [string, RequestInit]
    expect(JSON.parse(String(init.body))).toEqual({ name: 'Renamed Group' })
    expect(dialogs().find((d) => d.textContent!.includes('Rename group'))).toBeUndefined()
  })
})

describe('AdminGroupsPage bulk delete', () => {
  const bulkDeleteMockFor = (opts: {
    groups: unknown[]
    totalCount: number
    chunks: Array<Record<string, unknown>>
  }) => {
    let bulkCall = 0
    return vi.fn().mockImplementation((url: string, init?: RequestInit) => {
      const method = (init?.method || 'GET').toUpperCase()
      const u = String(url)

      if (u.includes('/services/csrf/')) {
        return Promise.resolve(new Response(JSON.stringify({ csrfToken: 'csrf-test' }), { status: 200 }))
      }
      if (method === 'POST' && u.includes('/group/bulk-delete/')) {
        const data = opts.chunks[Math.min(bulkCall, opts.chunks.length - 1)]
        bulkCall += 1
        return Promise.resolve(new Response(JSON.stringify({ msg: 'ok', data }), { status: 200 }))
      }
      if (method === 'GET' && u.includes('/group/')) {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              msg: 'ok',
              data: {
                items: opts.groups,
                total: opts.totalCount,
                page: 1,
                limit: 25,
                has_more: opts.totalCount > opts.groups.length
              }
            }),
            { status: 200 }
          )
        )
      }
      return Promise.resolve(new Response(JSON.stringify({}), { status: 200 }))
    })
  }

  it('deletes explicitly selected rows without requiring the typed DELETE confirmation', async () => {
    const fetchMock = bulkDeleteMockFor({
      groups: [groupA, groupB],
      totalCount: 2,
      chunks: [{ deletedIds: [1], failedIds: [], notFoundIds: [] }]
    })
    vi.stubGlobal('fetch', fetchMock)
    wrapper = mount(AdminGroupsPage)
    await flushPromises()

    const rowCheckbox = wrapper.find('input[aria-label="Select BTF1"]')
    expect(rowCheckbox.exists()).toBe(true)
    await rowCheckbox.setValue(true)
    expect(wrapper.text()).toContain('1 group selected')

    const deleteButton = wrapper.findAll('button').find((b) => b.text().trim() === 'Delete')
    expect(deleteButton).toBeDefined()
    await deleteButton!.trigger('click')
    await flushPromises()

    const dialog = dialogs().find((d) => d.textContent!.includes('Delete groups'))!
    const confirmButton = Array.from(dialog.querySelectorAll('button')).find(
      (b) => b.textContent?.trim() === 'Delete'
    ) as HTMLButtonElement
    expect(confirmButton.disabled).toBe(false)
    confirmButton.dispatchEvent(new Event('click', { bubbles: true }))
    await flushPromises()

    const call = fetchMock.mock.calls.find(
      ([u, i]) => String(u).includes('/group/bulk-delete/') && (i as RequestInit | undefined)?.method === 'POST'
    ) as [string, RequestInit]
    expect(JSON.parse(String(call[1].body))).toEqual({ groupIds: [1], force: false })
    expect(dialogs().find((d) => d.textContent!.includes('Delete groups'))).toBeUndefined()
  })

  it('drops the selected count when a row is unchecked in select-all-matching mode', async () => {
    // Regression: select-all-matching tracked excluded ids as strings while
    // AdminDataTable's row keys (and the plain-selection path) are numbers,
    // so unchecking a row never actually registered — the count stayed frozen.
    const fetchMock = bulkDeleteMockFor({ groups: [groupA, groupB], totalCount: 10, chunks: [] })
    vi.stubGlobal('fetch', fetchMock)
    wrapper = mount(AdminGroupsPage)
    await flushPromises()

    const headerCheckbox = wrapper.find('thead input[type="checkbox"]')
    await headerCheckbox.setValue(true)
    const selectAllLink = wrapper.findAll('button').find((b) => b.text().includes('Select all 10 groups'))
    await selectAllLink!.trigger('click')
    expect(wrapper.text()).toContain('10 groups selected')

    const rowCheckbox = wrapper.find('input[aria-label="Select BTF1"]')
    await rowCheckbox.setValue(false)
    expect(wrapper.text()).toContain('9 groups selected')

    await rowCheckbox.setValue(true)
    expect(wrapper.text()).toContain('10 groups selected')
  })

  it('loops chunked requests for select-all-matching until nothing remains, requiring force + typed DELETE', async () => {
    const fetchMock = bulkDeleteMockFor({
      groups: [groupA, groupB],
      totalCount: 60,
      chunks: [
        { deletedIds: [101, 102], failedIds: [], notFoundIds: [], remaining: 35 },
        { deletedIds: [201, 202], failedIds: [], notFoundIds: [], remaining: 0 }
      ]
    })
    vi.stubGlobal('fetch', fetchMock)
    wrapper = mount(AdminGroupsPage)
    await flushPromises()

    const headerCheckbox = wrapper.find('thead input[type="checkbox"]')
    expect(headerCheckbox.exists()).toBe(true)
    await headerCheckbox.setValue(true)

    const selectAllLink = wrapper.findAll('button').find((b) => b.text().includes('Select all 60 groups'))
    expect(selectAllLink).toBeDefined()
    await selectAllLink!.trigger('click')
    expect(wrapper.text()).toContain('60 groups selected')

    const deleteButton = wrapper.findAll('button').find((b) => b.text().trim() === 'Delete')
    await deleteButton!.trigger('click')
    await flushPromises()

    const dialog = dialogs().find((d) => d.textContent!.includes('Delete groups'))!
    const confirmButton = Array.from(dialog.querySelectorAll('button')).find(
      (b) => b.textContent?.trim() === 'Delete'
    ) as HTMLButtonElement
    // Blocked until both force and the typed DELETE keyword are provided.
    expect(confirmButton.disabled).toBe(true)

    const forceCheckbox = dialog.querySelector('input[type="checkbox"]') as HTMLInputElement
    forceCheckbox.checked = true
    forceCheckbox.dispatchEvent(new Event('change', { bubbles: true }))

    const deleteInput = dialog.querySelector('#bulk-delete-confirm') as HTMLInputElement
    deleteInput.value = 'DELETE'
    deleteInput.dispatchEvent(new Event('input', { bubbles: true }))
    await flushPromises()
    expect(confirmButton.disabled).toBe(false)

    confirmButton.dispatchEvent(new Event('click', { bubbles: true }))
    await flushPromises()

    const bulkCalls = fetchMock.mock.calls.filter(
      ([u, i]) => String(u).includes('/group/bulk-delete/') && (i as RequestInit | undefined)?.method === 'POST'
    )
    expect(bulkCalls.length).toBe(2)

    const firstBody = JSON.parse(String((bulkCalls[0][1] as RequestInit).body))
    expect(firstBody).toMatchObject({
      selectAll: true,
      force: true,
      expectedCount: 60,
      limit: 25,
      excludeIds: []
    })

    const secondBody = JSON.parse(String((bulkCalls[1][1] as RequestInit).body))
    expect(secondBody.excludeIds).toEqual([101, 102])

    expect(dialogs().find((d) => d.textContent!.includes('Delete groups'))).toBeUndefined()
  })
})

// Cross-feature checks: does the whole page hold together across the seams
// between features, not just each feature in isolation (already covered by
// the describe blocks above).
describe('AdminGroupsPage integration', () => {
  it('shows a newly created group in the list without a manual reload', async () => {
    // Unlike fetchMockFor, the GET response here changes once the create
    // actually lands — the point is to prove the post-create reload really
    // renders the new row, not just that the POST call was made.
    let created = false
    const fetchMock = vi.fn().mockImplementation((url: string, init?: RequestInit) => {
      const method = (init?.method || 'GET').toUpperCase()
      const u = String(url)

      if (u.includes('/services/csrf/')) {
        return Promise.resolve(new Response(JSON.stringify({ csrfToken: 'csrf-test' }), { status: 200 }))
      }
      if (u.includes('/group/next-name/')) {
        return Promise.resolve(new Response(JSON.stringify({ msg: 'ok', data: { name: 'BTF41' } }), { status: 200 }))
      }
      if (method === 'POST' && u.includes('/group/')) {
        created = true
        return Promise.resolve(
          new Response(JSON.stringify({ msg: 'Group created successfully', data: createdGroup }), { status: 201 })
        )
      }
      if (method === 'GET' && u.includes('/group/')) {
        const items = created ? [createdGroup, groupA, groupB] : [groupA, groupB]
        return Promise.resolve(
          new Response(
            JSON.stringify({ msg: 'ok', data: { items, total: items.length, page: 1, limit: 25, has_more: false } }),
            { status: 200 }
          )
        )
      }
      return Promise.resolve(new Response(JSON.stringify({}), { status: 200 }))
    })
    vi.stubGlobal('fetch', fetchMock)
    wrapper = mount(AdminGroupsPage)
    await flushPromises()

    expect(wrapper.text()).not.toContain('BTF41')

    const newGroupButton = wrapper.findAll('button').find((b) => b.text().trim().includes('New group'))
    await newGroupButton!.trigger('click')
    await flushPromises()

    const dialog = dialogs().find((d) => d.textContent!.includes('New group'))!
    const createButton = Array.from(dialog.querySelectorAll('button')).find((b) => b.textContent!.trim() === 'Create')!
    createButton.dispatchEvent(new Event('click', { bubbles: true }))
    await flushPromises()

    expect(wrapper.text()).toContain('BTF41')
  })

  it('preserves loaded groups and search state when switching to Matched Groups and back', async () => {
    const fetchMock = fetchMockFor([groupA, groupB])
    vi.stubGlobal('fetch', fetchMock)
    wrapper = mount(AdminGroupsPage)
    await flushPromises()

    await wrapper.find('input[type="search"]').setValue('BTF')
    const groupListCallsBeforeSwitch = fetchMock.mock.calls.filter(
      ([u]) => String(u).includes('/group/') && !String(u).includes('/group/next-name/')
    ).length

    const matchedTab = wrapper.findAll('button').find((b) => b.text().trim() === 'Matched Groups')
    await matchedTab!.trigger('click')
    await flushPromises()
    expect(wrapper.text()).not.toContain('BTF1')

    const groupsTab = wrapper.findAll('button').find((b) => b.text().trim() === 'Groups')
    await groupsTab!.trigger('click')
    await flushPromises()

    // Switching tabs is a pure template toggle for the Groups list's own
    // state — the underlying refs live in AdminGroupsPage's own script scope
    // regardless of which tab is shown, so re-showing "Groups" must not
    // re-fetch or drop what's already loaded/typed. (Matched Groups itself
    // legitimately re-fetches every time it's shown — it's a separate
    // component behind v-if — so this only counts /group/ list calls.)
    const groupListCallsAfterSwitch = fetchMock.mock.calls.filter(
      ([u]) => String(u).includes('/group/') && !String(u).includes('/group/next-name/')
    ).length
    expect(groupListCallsAfterSwitch).toBe(groupListCallsBeforeSwitch)
    expect(wrapper.text()).toContain('BTF1')
    expect((wrapper.find('input[type="search"]').element as HTMLInputElement).value).toBe('BTF')
  })
})
