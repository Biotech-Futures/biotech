import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createRouter, createWebHashHistory } from 'vue-router'

import routes from '@/router/routes'
import AdminUsersView from '@/views/admin/AdminUsersView.vue'

/**
 * The two People-page changes the support work makes to AdminUsersView:
 *
 *  - Both force-delete dialogs say what the purge really destroys, support
 *    tickets included, through the one ForceDeleteNotice (U5 PE-03, U6 C10).
 *    They used to list four kinds of content while the purge deleted five.
 *  - ?role=<role> opens the Users tab filtered to that role, which is what
 *    the roster's "Create a support agent on the People page" link relies on
 *    (RO-08).
 *
 * Team 1's pattern: fetch is stubbed and the real adminAPI.ts transport runs,
 * so the assertions read the URL the list request actually went out with.
 */
const country = { id: 1, countryName: 'Australia' }
const state = { id: 1, stateName: 'NSW', countryName: 'Australia' }

const user = {
  id: 1,
  firstName: 'Ada',
  lastName: 'Lovelace',
  email: 'ada@example.com',
  role: 'student',
  country,
  state,
  groupId: null,
  groupName: null,
  schoolName: 'State High',
  mentorBackground: null,
  mentorInstitution: null,
  mentorReason: null,
  mentorMaxGroupCount: null,
  yearLevel: 10,
  joinPermissionReceived: false,
  interests: ['Science'],
  isAdmin: false,
  isActive: true,
  hasLoggedIn: true,
  lastLogin: null,
  accountStatus: 'active',
  invitedAt: null,
  activatedAt: null,
  supervisorName: null,
  supervisorEmail: null,
  supervisees: []
}

const fetchMock = () =>
  vi.fn().mockImplementation((url: string) => {
    let payload: Record<string, unknown>
    if (url.includes('/services/csrf/')) payload = { csrfToken: 'csrf-test' }
    else if (url.includes('/user/countries/')) payload = { msg: 'ok', data: [country] }
    else if (url.includes('/user/states/')) payload = { msg: 'ok', data: [state] }
    else if (url.includes('/user/'))
      payload = { msg: 'ok', data: { items: [user], total: 1, page: 1, limit: 25, hasMore: false } }
    else payload = {}
    return Promise.resolve(
      new Response(JSON.stringify(payload), { status: 200, headers: { 'Content-Type': 'application/json' } })
    )
  })

// The main list request only: the supervisor picker (limit=200) and the
// country and state lookups also hit /user/.
const listCalls = (mock: ReturnType<typeof vi.fn>) =>
  mock.mock.calls
    .map((call) => String(call[0]))
    .filter(
      (url) =>
        url.includes('/user/') &&
        !url.includes('/user/countries/') &&
        !url.includes('/user/states/') &&
        !url.includes('limit=200')
    )

const dialogs = () => Array.from(document.body.querySelectorAll('[role="dialog"]'))
const squash = (text: string | null | undefined) => (text ?? '').replace(/\s+/g, ' ').trim()

let wrapper: VueWrapper | null = null

afterEach(() => {
  wrapper?.unmount()
  wrapper = null
  document.body.innerHTML = ''
  vi.unstubAllGlobals()
})

async function mountAt(path: string, props: Record<string, string>) {
  const router = createRouter({ history: createWebHashHistory(), routes })
  await router.push(path)
  await router.isReady()
  wrapper = mount(AdminUsersView, { props: props as never, global: { plugins: [router] } })
  await flushPromises()
  return wrapper
}

describe('force delete names support tickets (PE-03)', () => {
  it('in the bulk delete dialog', async () => {
    vi.stubGlobal('fetch', fetchMock())
    wrapper = mount(AdminUsersView, { props: { title: 'Users', noun: 'user' } })
    await flushPromises()

    await wrapper.find<HTMLInputElement>('input[type="checkbox"]').setValue(true)
    await flushPromises()
    const deleteButton = wrapper
      .find('[role="toolbar"]')
      .findAll('button')
      .find((b) => b.text().trim() === 'Delete')
    await deleteButton!.trigger('click')
    await flushPromises()

    const dialog = dialogs().find((d) => d.textContent!.includes('Delete users'))!
    const notice = squash(dialog.querySelector('.admin-users__force-toggle')!.textContent)
    expect(notice).toBe(
      "Force delete: also permanently delete each user's chat messages, uploaded resources, " +
        'workshops, match runs, and any support ticket they raised, including the replies and ' +
        'internal notes support staff wrote on it. Required to remove accounts that have any activity.'
    )
  })

  it('in the single delete dialog opened from the editor', async () => {
    vi.stubGlobal('fetch', fetchMock())
    wrapper = mount(AdminUsersView, { props: { title: 'Users', noun: 'user' } })
    await flushPromises()

    await wrapper.findAll('button').find((b) => b.text().trim() === 'Edit')!.trigger('click')
    await flushPromises()
    const editor = dialogs().find((d) => d.textContent!.includes('Edit user'))!
    Array.from(editor.querySelectorAll('button'))
      .find((b) => b.textContent!.trim() === 'Delete')!
      .click()
    await flushPromises()

    const confirm = dialogs().find((d) => d.textContent!.includes('Delete user'))!
    const notice = squash(confirm.querySelector('.admin-users__force-toggle')!.textContent)
    expect(notice).toContain("each user's chat messages")
    expect(notice).toContain('any support ticket they raised')
    expect(notice).toContain('internal notes support staff wrote on it')
  })

  // No Students or Supervisors case here: in the portal only the Users tab
  // offers delete at all (AdminUsersBulkBar hides it in student and
  // supervisor mode, and the editor's Delete is hidden for supervisors, while
  // student mode has no Edit). The noun still comes from the tab, so the
  // sentence stays right if that changes; ForceDeleteNotice.spec.ts covers
  // the three nouns.
})

describe('?role= on arrival (RO-08 link target)', () => {
  it('filters the Users tab to support, in the first and only list request', async () => {
    const mock = fetchMock()
    vi.stubGlobal('fetch', mock)
    await mountAt('/admin/users?role=support', { title: 'Users', noun: 'user' })

    const lists = listCalls(mock)
    expect(lists).toHaveLength(1)
    expect(new URL(lists[0]).searchParams.get('role')).toBe('support')
    // And the filter control says so, so the admin can see why the list is short.
    expect(wrapper!.find<HTMLSelectElement>('#role-filter').element.value).toBe('support')
  })

  it('ignores a role the page does not offer', async () => {
    const mock = fetchMock()
    vi.stubGlobal('fetch', mock)
    await mountAt('/admin/users?role=superuser', { title: 'Users', noun: 'user' })

    expect(new URL(listCalls(mock)[0]).searchParams.has('role')).toBe(false)
    expect(wrapper!.find<HTMLSelectElement>('#role-filter').element.value).toBe('all')
  })

  it('does not override a tab that fixes its own role', async () => {
    const mock = fetchMock()
    vi.stubGlobal('fetch', mock)
    await mountAt('/admin/users?role=support', {
      title: 'Students',
      noun: 'student',
      roleFilter: 'student'
    })

    for (const url of listCalls(mock)) {
      expect(new URL(url).searchParams.get('role')).toBe('student')
    }
  })
})
