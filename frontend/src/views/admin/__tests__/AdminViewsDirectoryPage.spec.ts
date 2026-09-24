import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { nextTick } from 'vue'
import { mount, flushPromises, type VueWrapper } from '@vue/test-utils'
import AdminViewsDirectoryPage from '@/views/admin/AdminViewsDirectoryPage.vue'
import * as adminAPI from '@/utils/adminAPI'
import { formatDateAU } from '@/utils/date'

const mockPush = vi.fn()

vi.mock('vue-router', () => ({
  useRouter: vi.fn(() => ({ push: mockPush }))
}))

vi.mock('@/utils/adminAPI', async (importOriginal) => {
  const actual = await importOriginal<typeof adminAPI>()
  return {
    ...actual,
    fetchAdminViews: vi.fn(),
    deleteAdminView: vi.fn(),
    bulkDeleteAdminViews: vi.fn(),
    getAdminViewExportUrl: vi.fn()
  }
})

const defaultView: adminAPI.AdminView = {
  id: 1,
  name: 'All Mentors',
  description: 'Active certified mentors across all domains',
  isDefault: true,
  targetRoles: ['mentor'],
  accountStatus: 'active',
  engagementStatus: 'all',
  advancedConditions: [],
  visibleColumns: ['name', 'email', 'role', 'status'],
  lastRunAt: '2026-09-20T00:00:00Z',
  createdAt: '2026-01-01T00:00:00Z',
  updatedAt: '2026-01-01T00:00:00Z'
}

const customView: adminAPI.AdminView = {
  id: 2,
  name: 'NSW Students',
  description: 'Students located in NSW',
  isDefault: false,
  targetRoles: ['student'],
  accountStatus: 'active',
  engagementStatus: 'all',
  advancedConditions: [{ field: 'state', operator: 'equals', value: 'NSW' }],
  visibleColumns: ['name', 'email'],
  lastRunAt: null,
  createdAt: '2026-02-01T00:00:00Z',
  updatedAt: '2026-02-05T00:00:00Z'
}

const allRolesView: adminAPI.AdminView = {
  id: 3,
  name: 'Everyone',
  description: '',
  isDefault: false,
  targetRoles: [],
  accountStatus: 'all',
  engagementStatus: 'all',
  advancedConditions: [],
  visibleColumns: ['name'],
  lastRunAt: null,
  createdAt: null,
  updatedAt: null
}

const multiRoleView: adminAPI.AdminView = {
  id: 4,
  name: 'Mentors and Students',
  description: 'Combined cohort',
  isDefault: false,
  targetRoles: ['mentor', 'student'],
  accountStatus: 'active',
  engagementStatus: 'all',
  advancedConditions: [],
  visibleColumns: ['name'],
  lastRunAt: '2026-03-01T00:00:00Z',
  createdAt: '2026-01-01T00:00:00Z',
  updatedAt: '2026-01-01T00:00:00Z'
}

// The real drawer (and its own network calls) is Person 1's territory and has
// its own spec; here we only need to see which props this page opens it with.
const drawerStub = {
  props: ['modelValue', 'view'],
  template:
    '<div class="drawer-stub" v-if="modelValue">{{ view ? `Edit View: ${view.name}` : \'Create View\' }}</div>'
}

const mountPage = () =>
  mount(AdminViewsDirectoryPage, {
    global: { stubs: { AdminViewQueryDrawer: drawerStub, Teleport: true } }
  })

const buttonByText = (wrapper: VueWrapper, text: string) =>
  wrapper.findAll('button').find((button) => button.text().trim() === text)

const lastButtonByText = (wrapper: VueWrapper, text: string) =>
  [...wrapper.findAll('button')].reverse().find((button) => button.text().trim() === text)

const rowButtonByText = (wrapper: VueWrapper, rowIndex: number, text: string) =>
  wrapper
    .findAll('.admin-table__row')[rowIndex]
    .findAll('button')
    .find((button) => button.text().trim() === text)

const mockViews = (items: adminAPI.AdminView[]) =>
  vi.mocked(adminAPI.fetchAdminViews).mockReset().mockResolvedValue({ items, total: items.length })

let wrapper: VueWrapper | null = null
// eslint-disable-next-line @typescript-eslint/no-explicit-any
let windowOpenSpy: any

beforeEach(() => {
  mockPush.mockClear()
  vi.mocked(adminAPI.fetchAdminViews)
    .mockReset()
    .mockResolvedValue({ items: [defaultView, customView], total: 2 })
  vi.mocked(adminAPI.deleteAdminView).mockReset().mockResolvedValue(true)
  vi.mocked(adminAPI.bulkDeleteAdminViews).mockReset().mockResolvedValue({ deletedCount: 1 })
  vi.mocked(adminAPI.getAdminViewExportUrl)
    .mockReset()
    .mockImplementation((id: number) => `/mock-export/${id}`)
  windowOpenSpy = vi.spyOn(window, 'open').mockImplementation(() => null)
})

afterEach(() => {
  wrapper?.unmount()
  wrapper = null
  vi.useRealTimers()
  windowOpenSpy.mockRestore()
})

describe('AdminViewsDirectoryPage', () => {
  it('loads views on mount and renders them with tab counts', async () => {
    wrapper = mountPage()
    await flushPromises()

    expect(adminAPI.fetchAdminViews).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).toContain('All Mentors')
    expect(wrapper.text()).toContain('NSW Students')
    expect(wrapper.text()).toContain('All Views (2)')
    expect(wrapper.text()).toContain('Default Views (1)')
    expect(wrapper.text()).toContain('Custom Views (1)')
  })

  it('filters displayed views by tab without refetching from the server', async () => {
    wrapper = mountPage()
    await flushPromises()

    const defaultTab = wrapper.findAll('[role="tab"]').find((tab) => tab.text().startsWith('Default Views'))
    await defaultTab!.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('All Mentors')
    expect(wrapper.text()).not.toContain('NSW Students')
    expect(adminAPI.fetchAdminViews).toHaveBeenCalledTimes(1)
  })

  it('keeps the Type dropdown in sync with the tabs', async () => {
    wrapper = mountPage()
    await flushPromises()

    await wrapper.find<HTMLSelectElement>('#view-type-filter').setValue('custom')
    await flushPromises()

    expect(wrapper.text()).not.toContain('All Mentors')
    expect(wrapper.text()).toContain('NSW Students')
    const customTab = wrapper.findAll('[role="tab"]').find((tab) => tab.text().startsWith('Custom Views'))
    expect(customTab?.classes()).toContain('active')
  })

  it('requests filtered views from the server after the search debounce', async () => {
    vi.useFakeTimers()
    wrapper = mountPage()
    await flushPromises()

    await wrapper.find('#view-search').setValue('mentor')
    vi.advanceTimersByTime(300)
    await flushPromises()

    expect(adminAPI.fetchAdminViews).toHaveBeenLastCalledWith(
      expect.objectContaining({ search: 'mentor' })
    )
  })

  it('requests filtered views from the server when the role filter changes', async () => {
    wrapper = mountPage()
    await flushPromises()

    await wrapper.find<HTMLSelectElement>('#view-role-filter').setValue('mentor')
    await flushPromises()

    expect(adminAPI.fetchAdminViews).toHaveBeenLastCalledWith(
      expect.objectContaining({ role: 'mentor' })
    )
  })

  it('opens the drawer in create mode from the toolbar button', async () => {
    wrapper = mountPage()
    await flushPromises()

    expect(wrapper.find('.drawer-stub').exists()).toBe(false)
    await buttonByText(wrapper, 'Create View')!.trigger('click')
    await flushPromises()

    expect(wrapper.find('.drawer-stub').text()).toBe('Create View')
  })

  it('opens the drawer in edit mode for a custom view', async () => {
    wrapper = mountPage()
    await flushPromises()

    await rowButtonByText(wrapper, 1, 'Edit')!.trigger('click')
    await flushPromises()

    expect(wrapper.find('.drawer-stub').text()).toBe('Edit View: NSW Students')
  })

  it('does not offer Edit or Delete on default views', async () => {
    wrapper = mountPage()
    await flushPromises()

    expect(rowButtonByText(wrapper, 0, 'Edit')).toBeUndefined()
    expect(rowButtonByText(wrapper, 0, 'Delete')).toBeUndefined()
    expect(rowButtonByText(wrapper, 0, 'Export')).toBeDefined()
  })

  it('navigates to the executed view when Run is clicked', async () => {
    wrapper = mountPage()
    await flushPromises()

    await rowButtonByText(wrapper, 1, 'Run')!.trigger('click')

    expect(mockPush).toHaveBeenCalledWith({ name: 'admin-view-detail', params: { id: 2 } })
  })

  it('exports a default view as CSV', async () => {
    wrapper = mountPage()
    await flushPromises()

    await rowButtonByText(wrapper, 0, 'Export')!.trigger('click')

    expect(adminAPI.getAdminViewExportUrl).toHaveBeenCalledWith(1)
    expect(windowOpenSpy).toHaveBeenCalledWith('/mock-export/1', '_blank')
  })

  it('deletes a single custom view after confirmation and reloads the list', async () => {
    wrapper = mountPage()
    await flushPromises()

    await rowButtonByText(wrapper, 1, 'Delete')!.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('Delete "NSW Students"? This cannot be undone.')
    await lastButtonByText(wrapper, 'Delete')!.trigger('click')
    await flushPromises()

    expect(adminAPI.deleteAdminView).toHaveBeenCalledWith(2)
    expect(adminAPI.fetchAdminViews).toHaveBeenCalledTimes(2)
  })

  it('shows the bulk actions bar once rows are selected and clears it', async () => {
    wrapper = mountPage()
    await flushPromises()

    const checkboxes = wrapper.findAll<HTMLInputElement>('input[type="checkbox"]')
    await checkboxes[1].setValue(true)
    await flushPromises()

    expect(wrapper.text()).toContain('1 view selected')

    await buttonByText(wrapper, 'Clear')!.trigger('click')
    await flushPromises()

    expect(wrapper.text()).not.toContain('view selected')
  })

  it('batch exports every selected view', async () => {
    wrapper = mountPage()
    await flushPromises()

    const checkboxes = wrapper.findAll<HTMLInputElement>('input[type="checkbox"]')
    await checkboxes[1].setValue(true)
    await checkboxes[2].setValue(true)
    await flushPromises()

    await buttonByText(wrapper, 'Batch export')!.trigger('click')

    expect(windowOpenSpy).toHaveBeenCalledWith('/mock-export/1', '_blank')
    expect(windowOpenSpy).toHaveBeenCalledWith('/mock-export/2', '_blank')
  })

  it('batch deletes selected views after confirmation and clears the selection', async () => {
    wrapper = mountPage()
    await flushPromises()

    const checkboxes = wrapper.findAll<HTMLInputElement>('input[type="checkbox"]')
    await checkboxes[1].setValue(true)
    await checkboxes[2].setValue(true)
    await flushPromises()

    await buttonByText(wrapper, 'Batch delete')!.trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('Delete 2 selected views? This cannot be undone.')

    await lastButtonByText(wrapper, 'Delete')!.trigger('click')
    await flushPromises()

    expect(adminAPI.bulkDeleteAdminViews).toHaveBeenCalledWith([1, 2])
    expect(wrapper.text()).not.toContain('view selected')
    expect(adminAPI.fetchAdminViews).toHaveBeenCalledTimes(2)
  })

  it('shows an error message when views fail to load', async () => {
    const consoleSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})
    vi.mocked(adminAPI.fetchAdminViews).mockReset().mockRejectedValue(new Error('Server exploded'))

    wrapper = mountPage()
    await flushPromises()

    expect(wrapper.find('[role="alert"]').text()).toContain('Server exploded')
    consoleSpy.mockRestore()
  })

  it('shows an empty state and zeroed tab counts when there are no views', async () => {
    vi.mocked(adminAPI.fetchAdminViews).mockReset().mockResolvedValue({ items: [], total: 0 })

    wrapper = mountPage()
    await flushPromises()

    expect(wrapper.text()).toContain('No views found.')
    expect(wrapper.text()).toContain('All Views (0)')
    expect(wrapper.text()).toContain('Default Views (0)')
    expect(wrapper.text()).toContain('Custom Views (0)')
  })

  it('shows a loading indicator while the initial fetch is in flight', async () => {
    let resolveFetch!: (value: adminAPI.ViewListData) => void
    vi.mocked(adminAPI.fetchAdminViews)
      .mockReset()
      .mockImplementation(() => new Promise((resolve) => { resolveFetch = resolve }))

    wrapper = mountPage()
    await nextTick()

    expect(wrapper.text()).toContain('Loading...')

    resolveFetch({ items: [defaultView, customView], total: 2 })
    await flushPromises()
    expect(wrapper.text()).not.toContain('Loading...')
  })

  it('cancels a single delete without calling the API or losing the row', async () => {
    wrapper = mountPage()
    await flushPromises()

    await rowButtonByText(wrapper, 1, 'Delete')!.trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('Delete "NSW Students"? This cannot be undone.')

    await buttonByText(wrapper, 'Cancel')!.trigger('click')
    await flushPromises()

    expect(adminAPI.deleteAdminView).not.toHaveBeenCalled()
    expect(wrapper.text()).not.toContain('This cannot be undone.')
    expect(wrapper.text()).toContain('NSW Students')
  })

  it('shows an inline error and keeps the row when a single delete fails', async () => {
    const consoleSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})
    vi.mocked(adminAPI.deleteAdminView).mockReset().mockRejectedValue(new Error('View is in use'))

    wrapper = mountPage()
    await flushPromises()

    await rowButtonByText(wrapper, 1, 'Delete')!.trigger('click')
    await flushPromises()
    await lastButtonByText(wrapper, 'Delete')!.trigger('click')
    await flushPromises()

    expect(wrapper.find('.admin-views-table__dialog-error').text()).toContain('View is in use')
    expect(wrapper.text()).toContain('NSW Students')
    expect(adminAPI.fetchAdminViews).toHaveBeenCalledTimes(1)
    consoleSpy.mockRestore()
  })

  it('cancels a batch delete without calling the API or clearing the selection', async () => {
    wrapper = mountPage()
    await flushPromises()

    const checkboxes = wrapper.findAll<HTMLInputElement>('input[type="checkbox"]')
    await checkboxes[1].setValue(true)
    await checkboxes[2].setValue(true)
    await flushPromises()

    await buttonByText(wrapper, 'Batch delete')!.trigger('click')
    await flushPromises()
    await buttonByText(wrapper, 'Cancel')!.trigger('click')
    await flushPromises()

    expect(adminAPI.bulkDeleteAdminViews).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('2 views selected')
  })

  it('shows an inline error and keeps the selection when a batch delete fails', async () => {
    const consoleSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})
    vi.mocked(adminAPI.bulkDeleteAdminViews).mockReset().mockRejectedValue(new Error('Bulk delete failed'))

    wrapper = mountPage()
    await flushPromises()

    const checkboxes = wrapper.findAll<HTMLInputElement>('input[type="checkbox"]')
    await checkboxes[1].setValue(true)
    await checkboxes[2].setValue(true)
    await flushPromises()

    await buttonByText(wrapper, 'Batch delete')!.trigger('click')
    await flushPromises()
    await lastButtonByText(wrapper, 'Delete')!.trigger('click')
    await flushPromises()

    expect(wrapper.find('.admin-views__dialog-error').text()).toContain('Bulk delete failed')
    expect(wrapper.text()).toContain('2 views selected')
    expect(adminAPI.fetchAdminViews).toHaveBeenCalledTimes(1)
    consoleSpy.mockRestore()
  })

  it('clears a stale selection when switching tabs so it cannot be batch-deleted invisibly', async () => {
    wrapper = mountPage()
    await flushPromises()

    const checkboxes = wrapper.findAll<HTMLInputElement>('input[type="checkbox"]')
    await checkboxes[2].setValue(true) // select the custom view, "NSW Students"
    await flushPromises()
    expect(wrapper.text()).toContain('1 view selected')

    const defaultTab = wrapper.findAll('[role="tab"]').find((tab) => tab.text().startsWith('Default Views'))
    await defaultTab!.trigger('click')
    await flushPromises()

    expect(wrapper.text()).not.toContain('view selected')
  })

  it('clears the selection when the search or role filter changes', async () => {
    wrapper = mountPage()
    await flushPromises()

    const checkboxes = wrapper.findAll<HTMLInputElement>('input[type="checkbox"]')
    await checkboxes[1].setValue(true)
    await flushPromises()
    expect(wrapper.text()).toContain('1 view selected')

    await wrapper.find<HTMLSelectElement>('#view-role-filter').setValue('mentor')
    await flushPromises()

    expect(wrapper.text()).not.toContain('view selected')
  })

  it('renders an "All roles" badge for a view with no specific target roles', async () => {
    mockViews([allRolesView])
    wrapper = mountPage()
    await flushPromises()

    expect(wrapper.find('.admin-views-table__badge').text()).toBe('All roles')
  })

  it('renders one badge per targeted role for a multi-role view', async () => {
    mockViews([multiRoleView])
    wrapper = mountPage()
    await flushPromises()

    const badges = wrapper.findAll('.admin-views-table__badge').map((badge) => badge.text())
    expect(badges).toEqual(['Mentor', 'Student'])
  })

  it('formats the Last Run / Updated column for run, updated-only, and never-touched views', async () => {
    const neverTouched = { ...customView, id: 5, lastRunAt: null, updatedAt: null }
    mockViews([defaultView, customView, neverTouched])
    wrapper = mountPage()
    await flushPromises()

    const rows = wrapper.findAll('.admin-table__row')
    expect(rows[0].text()).toContain(`Run ${formatDateAU(defaultView.lastRunAt!)}`)
    expect(rows[1].text()).toContain(`Updated ${formatDateAU(customView.updatedAt!)}`)
    expect(rows[2].text()).toContain('—')
  })

  it('navigates to the executed view when Run is clicked on a default view', async () => {
    wrapper = mountPage()
    await flushPromises()

    await rowButtonByText(wrapper, 0, 'Run')!.trigger('click')

    expect(mockPush).toHaveBeenCalledWith({ name: 'admin-view-detail', params: { id: 1 } })
  })

  it('selects only the rows visible under the active tab via select-all', async () => {
    wrapper = mountPage()
    await flushPromises()

    const defaultTab = wrapper.findAll('[role="tab"]').find((tab) => tab.text().startsWith('Default Views'))
    await defaultTab!.trigger('click')
    await flushPromises()

    const selectAllCheckbox = wrapper.find<HTMLInputElement>('input[type="checkbox"]')
    await selectAllCheckbox.setValue(true)
    await flushPromises()

    expect(wrapper.text()).toContain('1 view selected')
  })

  it('collapses rapid search keystrokes into a single request after the debounce', async () => {
    vi.useFakeTimers()
    wrapper = mountPage()
    await flushPromises()

    const callsBeforeTyping = vi.mocked(adminAPI.fetchAdminViews).mock.calls.length
    const searchInput = wrapper.find('#view-search')
    await searchInput.setValue('m')
    vi.advanceTimersByTime(100)
    await searchInput.setValue('me')
    vi.advanceTimersByTime(100)
    await searchInput.setValue('men')
    vi.advanceTimersByTime(300)
    await flushPromises()

    expect(adminAPI.fetchAdminViews).toHaveBeenCalledTimes(callsBeforeTyping + 1)
    expect(adminAPI.fetchAdminViews).toHaveBeenLastCalledWith(expect.objectContaining({ search: 'men' }))
  })

  it('drops the search param entirely once the search box is cleared', async () => {
    vi.useFakeTimers()
    wrapper = mountPage()
    await flushPromises()

    await wrapper.find('#view-search').setValue('mentor')
    vi.advanceTimersByTime(300)
    await flushPromises()
    expect(adminAPI.fetchAdminViews).toHaveBeenLastCalledWith(expect.objectContaining({ search: 'mentor' }))

    await wrapper.find('#view-search').setValue('')
    vi.advanceTimersByTime(300)
    await flushPromises()

    const lastCall = vi.mocked(adminAPI.fetchAdminViews).mock.calls.at(-1)?.[0]
    expect(lastCall?.search).toBeUndefined()
  })

  it('disables the confirm button while a single delete is in progress', async () => {
    let resolveDelete!: (value: boolean) => void
    vi.mocked(adminAPI.deleteAdminView)
      .mockReset()
      .mockImplementation(() => new Promise((resolve) => { resolveDelete = resolve }))

    wrapper = mountPage()
    await flushPromises()

    await rowButtonByText(wrapper, 1, 'Delete')!.trigger('click')
    await flushPromises()
    await lastButtonByText(wrapper, 'Delete')!.trigger('click')
    await nextTick()

    // The button's own text switches away from "Delete" while busy, so it must
    // be re-queried by structure rather than reusing the pre-click reference.
    const confirmButton = wrapper.findAll('.admin-modal__footer button').at(-1)
    expect(confirmButton?.attributes('disabled')).toBeDefined()

    resolveDelete(true)
    await flushPromises()
  })
})
