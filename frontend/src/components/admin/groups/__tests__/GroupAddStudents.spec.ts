import { afterEach, describe, expect, it, vi } from 'vitest'
import { mount, flushPromises, type VueWrapper } from '@vue/test-utils'
import GroupAddStudents from '@/components/admin/groups/GroupAddStudents.vue'
import type { AdminGroupDetail } from '@/utils/adminAPI'

const group: AdminGroupDetail = {
  id: 7,
  name: 'BTF7',
  members: [],
  mentor: null,
  createdAt: '2026-01-01T00:00:00Z',
  updatedAt: '2026-01-01T00:00:00Z'
}

const student = (id: number, firstName: string | null, lastName: string | null, email: string) => ({
  id,
  firstName,
  lastName,
  email,
  role: 'student',
  groupId: null,
  groupName: null
})

const ada = student(30, 'Ada', 'Lovelace', 'ada@example.com')
const alan = student(31, 'Alan', 'Turing', 'alan@example.com')
const noName = student(32, null, null, 'anon@example.com')

const json = (body: unknown, status = 200) =>
  Promise.resolve(new Response(JSON.stringify(body), { status }))

const userList = (items: unknown[]) =>
  json({ msg: 'ok', data: { items, total: items.length, page: 1, limit: 100, hasMore: false } })

/**
 * Default fetch mock: GET /user/ returns `students`, POST /match/confirm/
 * succeeds (or fails with `confirmError`). Individual tests override it when
 * they need to control response timing.
 */
const fetchMockFor = (opts: { students?: unknown[]; confirmError?: string; loadError?: string } = {}) =>
  vi.fn().mockImplementation((url: string, init?: RequestInit) => {
    const method = (init?.method || 'GET').toUpperCase()
    const u = String(url)
    if (u.includes('/services/csrf/')) return json({ csrfToken: 'csrf-test' })
    if (method === 'GET' && u.includes('/user/')) {
      if (opts.loadError) return json({ error: opts.loadError, code: 'server_error' }, 500)
      return userList(opts.students ?? [])
    }
    if (method === 'POST' && u.includes('/match/confirm/')) {
      if (opts.confirmError) return json({ error: opts.confirmError, code: 'validation_error' }, 400)
      const body = JSON.parse(String(init?.body ?? '{}'))
      return json({ msg: 'ok', data: { assigned_count: body.assignments?.length ?? 0 } })
    }
    return json({})
  })

const userCalls = (fetchMock: ReturnType<typeof vi.fn>) =>
  fetchMock.mock.calls.filter(
    ([u, i]) => String(u).includes('/user/') && ((i as RequestInit | undefined)?.method ?? 'GET') === 'GET'
  )

const confirmCalls = (fetchMock: ReturnType<typeof vi.fn>) =>
  fetchMock.mock.calls.filter(
    ([u, i]) => String(u).includes('/match/confirm/') && (i as RequestInit | undefined)?.method === 'POST'
  )

let wrapper: VueWrapper | null = null

const mountPicker = async (fetchMock: ReturnType<typeof vi.fn>, remaining = 5) => {
  vi.stubGlobal('fetch', fetchMock)
  wrapper = mount(GroupAddStudents, { props: { group, remaining } })
  await flushPromises()
  return wrapper
}

const addButton = () => wrapper!.findAll('.group-add__actions button')[1]
const cancelButton = () => wrapper!.findAll('.group-add__actions button')[0]

const setChecked = async (name: string, checked = true) => {
  const label = wrapper!.findAll('label').find((l) => l.text().includes(name))
  if (!label) throw new Error(`student "${name}" not listed`)
  await label.find('input[type="checkbox"]').setValue(checked)
}

afterEach(() => {
  wrapper?.unmount()
  wrapper = null
  vi.useRealTimers()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('GroupAddStudents', () => {
  // --- Normal behaviour ------------------------------------------------------

  it('loads only ungrouped students on open', async () => {
    const fetchMock = fetchMockFor({ students: [ada, alan] })
    await mountPicker(fetchMock)

    expect(userCalls(fetchMock)).toHaveLength(1)
    const url = String(userCalls(fetchMock)[0][0])
    expect(url).toContain('role=student')
    expect(url).toContain('inGroup=no')
    expect(url).toContain('limit=100')
    expect(url).not.toContain('search=')

    expect(wrapper!.text()).toContain('Ada Lovelace')
    expect(wrapper!.text()).toContain('alan@example.com')
  })

  it('shows the email as the name when a student has no first or last name', async () => {
    await mountPicker(fetchMockFor({ students: [noName] }))

    expect(wrapper!.find('.group-add__option-name').text()).toBe('anon@example.com')
  })

  it('adds the selected students and emits them', async () => {
    const fetchMock = fetchMockFor({ students: [ada, alan] })
    await mountPicker(fetchMock)

    await setChecked('Ada Lovelace')
    await setChecked('Alan Turing')
    expect(addButton().text()).toBe('Add (2)')

    await addButton().trigger('click')
    await flushPromises()

    expect(confirmCalls(fetchMock)).toHaveLength(1)
    expect(JSON.parse(String((confirmCalls(fetchMock)[0][1] as RequestInit).body))).toEqual({
      assignments: [
        { studentId: 30, groupId: 7 },
        { studentId: 31, groupId: 7 }
      ]
    })
    const added = wrapper!.emitted('added')![0][0] as { id: number }[]
    expect(added.map((s) => s.id)).toEqual([30, 31])
  })

  it('unticking a student removes them from the selection', async () => {
    await mountPicker(fetchMockFor({ students: [ada, alan] }))

    await setChecked('Ada Lovelace')
    await setChecked('Alan Turing')
    await setChecked('Ada Lovelace', false)

    expect(addButton().text()).toBe('Add (1)')
  })

  it('cancel emits cancel without adding anyone', async () => {
    const fetchMock = fetchMockFor({ students: [ada] })
    await mountPicker(fetchMock)

    await setChecked('Ada Lovelace')
    await cancelButton().trigger('click')

    expect(wrapper!.emitted('cancel')).toHaveLength(1)
    expect(confirmCalls(fetchMock)).toHaveLength(0)
  })

  it('uses singular and plural seat wording', async () => {
    await mountPicker(fetchMockFor(), 1)
    expect(wrapper!.text()).toContain('1 seat left.')
    wrapper!.unmount()

    await mountPicker(fetchMockFor(), 3)
    expect(wrapper!.text()).toContain('3 seats left.')
  })

  // --- Empty / error states --------------------------------------------------

  it('says so when there are no ungrouped students, and Add stays disabled', async () => {
    await mountPicker(fetchMockFor({ students: [] }))

    expect(wrapper!.text()).toContain('No ungrouped students found.')
    expect(addButton().attributes('disabled')).toBeDefined()
  })

  it('shows a load failure inline', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    await mountPicker(fetchMockFor({ loadError: 'Server exploded' }))

    expect(wrapper!.find('[role="alert"]').text()).toContain('Server exploded')
    expect(wrapper!.findAll('label')).toHaveLength(0)
  })

  it('Add is disabled until something is selected', async () => {
    await mountPicker(fetchMockFor({ students: [ada] }))

    expect(addButton().text()).toBe('Add')
    expect(addButton().attributes('disabled')).toBeDefined()
  })

  // --- Capacity --------------------------------------------------------------

  it('blocks adding to a full group even with a selection', async () => {
    const fetchMock = fetchMockFor({ students: [ada] })
    await mountPicker(fetchMock, 0)

    expect(wrapper!.text()).toContain('This group is full.')
    await setChecked('Ada Lovelace')
    expect(addButton().attributes('disabled')).toBeDefined()

    await addButton().trigger('click')
    await flushPromises()
    expect(confirmCalls(fetchMock)).toHaveLength(0)
  })

  it('warns and blocks when more students are picked than there are seats, until one is unticked', async () => {
    await mountPicker(fetchMockFor({ students: [ada, alan] }), 1)

    await setChecked('Ada Lovelace')
    await setChecked('Alan Turing')
    expect(wrapper!.find('.group-add__overflow').text()).toContain('Only 1 seat left. Deselect 1 student.')
    expect(addButton().attributes('disabled')).toBeDefined()

    await setChecked('Alan Turing', false)
    expect(wrapper!.find('.group-add__overflow').exists()).toBe(false)
    expect(addButton().attributes('disabled')).toBeUndefined()
  })

  it('allows filling the group exactly to capacity', async () => {
    const fetchMock = fetchMockFor({ students: [ada, alan] })
    await mountPicker(fetchMock, 2)

    await setChecked('Ada Lovelace')
    await setChecked('Alan Turing')
    expect(wrapper!.find('.group-add__overflow').exists()).toBe(false)

    await addButton().trigger('click')
    await flushPromises()
    expect(confirmCalls(fetchMock)).toHaveLength(1)
  })

  // --- Search ----------------------------------------------------------------

  it('debounces search so fast typing sends a single request', async () => {
    vi.useFakeTimers()
    const fetchMock = fetchMockFor({ students: [ada] })
    await mountPicker(fetchMock)

    const input = wrapper!.find('input[type="search"]')
    await input.setValue('A')
    await input.setValue('Ad')
    await input.setValue('Ada')
    vi.advanceTimersByTime(299)
    await flushPromises()
    expect(userCalls(fetchMock)).toHaveLength(1) // just the initial load

    vi.advanceTimersByTime(1)
    await flushPromises()
    expect(userCalls(fetchMock)).toHaveLength(2)
    expect(String(userCalls(fetchMock)[1][0])).toContain('search=Ada')
  })

  it('trims the search and drops it entirely when only whitespace', async () => {
    vi.useFakeTimers()
    const fetchMock = fetchMockFor({ students: [ada] })
    await mountPicker(fetchMock)
    const input = wrapper!.find('input[type="search"]')

    await input.setValue('  Ada  ')
    vi.advanceTimersByTime(300)
    await flushPromises()
    expect(String(userCalls(fetchMock)[1][0])).toContain('search=Ada')
    expect(String(userCalls(fetchMock)[1][0])).not.toContain('search=+')

    await input.setValue('   ')
    vi.advanceTimersByTime(300)
    await flushPromises()
    expect(String(userCalls(fetchMock)[2][0])).not.toContain('search=')
  })

  it('ignores a slow earlier response that lands after a newer search', async () => {
    vi.useFakeTimers()
    // Hold each /user/ response until the test releases it.
    const pending: ((r: Response) => void)[] = []
    const fetchMock = vi.fn().mockImplementation((url: string) => {
      if (String(url).includes('/user/')) return new Promise<Response>((resolve) => pending.push(resolve))
      return json({})
    })
    vi.stubGlobal('fetch', fetchMock)
    wrapper = mount(GroupAddStudents, { props: { group, remaining: 5 } })
    await flushPromises()

    await wrapper.find('input[type="search"]').setValue('Ada')
    vi.advanceTimersByTime(300)
    await flushPromises()
    expect(pending).toHaveLength(2)

    // Newer search answers first, then the stale initial load arrives.
    pending[1](await userList([ada]))
    await flushPromises()
    pending[0](await userList([alan, noName]))
    await flushPromises()

    expect(wrapper.text()).toContain('Ada Lovelace')
    expect(wrapper.text()).not.toContain('Alan Turing')
    expect(wrapper.text()).not.toContain('Loading students...')
  })

  it('keeps a selection when a new search hides that student', async () => {
    vi.useFakeTimers()
    let results: unknown[] = [ada, alan]
    const base = fetchMockFor()
    const fetchMock = vi.fn().mockImplementation((url: string, init?: RequestInit) =>
      String(url).includes('/user/') && (init?.method ?? 'GET') === 'GET' ? userList(results) : base(url, init)
    )
    await mountPicker(fetchMock)

    await setChecked('Ada Lovelace')
    results = [alan]
    await wrapper!.find('input[type="search"]').setValue('Alan')
    vi.advanceTimersByTime(300)
    await flushPromises()
    await setChecked('Alan Turing')

    expect(wrapper!.text()).not.toContain('Ada Lovelace')
    expect(addButton().text()).toBe('Add (2)')

    await addButton().trigger('click')
    await flushPromises()
    const body = JSON.parse(String((confirmCalls(fetchMock)[0][1] as RequestInit).body))
    expect(body.assignments.map((a: { studentId: number }) => a.studentId)).toEqual([30, 31])
  })

  // --- Submitting ------------------------------------------------------------

  it('shows a submit failure inline, emits nothing, and lets the admin retry', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    const fetchMock = fetchMockFor({ students: [ada], confirmError: 'Student is already in a group.' })
    await mountPicker(fetchMock)

    await setChecked('Ada Lovelace')
    await addButton().trigger('click')
    await flushPromises()

    expect(wrapper!.find('[role="alert"]').text()).toContain('Student is already in a group.')
    expect(wrapper!.emitted('added')).toBeFalsy()
    expect(addButton().text()).toBe('Add (1)')
    expect(addButton().attributes('disabled')).toBeUndefined()
  })

  it('locks the form while the add is in flight so a double-click sends one request', async () => {
    let release!: (r: Response) => void
    const base = fetchMockFor({ students: [ada] })
    const fetchMock = vi.fn().mockImplementation((url: string, init?: RequestInit) =>
      String(url).includes('/match/confirm/')
        ? new Promise<Response>((resolve) => (release = resolve))
        : base(url, init)
    )
    await mountPicker(fetchMock)

    await setChecked('Ada Lovelace')
    await addButton().trigger('click')
    await flushPromises()

    expect(addButton().text()).toBe('Adding...')
    expect(addButton().attributes('disabled')).toBeDefined()
    expect(cancelButton().attributes('disabled')).toBeDefined()
    expect(wrapper!.find('input[type="checkbox"]').attributes('disabled')).toBeDefined()

    await addButton().trigger('click')
    await flushPromises()
    expect(confirmCalls(fetchMock)).toHaveLength(1)

    release(await json({ msg: 'ok', data: { assigned_count: 1 } }))
    await flushPromises()
    expect(wrapper!.emitted('added')).toHaveLength(1)
  })
})
