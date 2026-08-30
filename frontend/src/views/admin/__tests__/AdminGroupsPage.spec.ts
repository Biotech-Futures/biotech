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
