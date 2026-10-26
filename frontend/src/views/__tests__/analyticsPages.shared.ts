// Mounting and CSV helpers shared by the Overview, Email Monitoring and
// Registration analytics page specs, matching those in
// analyticsPartialData.spec.ts. Each spec still mocks @/utils/liveAnalyticsApi,
// vue-router and useAnalyticsRefreshState itself, because vi.mock is per file.
import { expect, vi } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import type { AdminUser } from '@/utils/liveAnalyticsApi'

const mounted: VueWrapper[] = []

// `attach` mounts into the document, for pages that find their own sections by id.
export async function show(component: Parameters<typeof mount>[0], { attach = false } = {}) {
  const wrapper = mount(component, {
    attachTo: attach ? document.body : undefined,
    global: { stubs: { RouterLink: true, AnalyticsDatePicker: true, ChartTooltip: true } },
  })
  mounted.push(wrapper)
  await flushPromises()
  await flushPromises()
  return wrapper
}

export function unmountPages() {
  mounted.splice(0).forEach((wrapper) => wrapper.unmount())
}

// Catches the next CSV the page downloads; call the result to read it.
export function captureCsv() {
  let captured: Blob | undefined
  const BrowserURL = URL
  vi.stubGlobal('URL', class extends BrowserURL {
    static createObjectURL = vi.fn((blob: Blob) => { captured = blob; return 'blob:analytics' })
    static revokeObjectURL = vi.fn()
  })
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
  return () => {
    expect(captured).toBeInstanceOf(Blob)
    return new Promise<string>((resolve, reject) => {
      const reader = new FileReader()
      reader.onload = () => resolve(String(reader.result))
      reader.onerror = () => reject(reader.error)
      reader.readAsText(captured!)
    })
  }
}

// Opens the Export CSV menu, picks the option whose label starts with
// `option` (or exports directly when the page offers one file) and returns the CSV.
export async function downloadedCsv(wrapper: VueWrapper, option = 'Summary') {
  const csv = captureCsv()
  expect(wrapper.get('.export-button').attributes('disabled')).toBeUndefined()
  await wrapper.get('.export-button').trigger('click')
  const item = wrapper.findAll('[role="menuitem"]').find((node) => node.text().startsWith(option))
  if (item) await item.trigger('click')
  return csv()
}

export const student: AdminUser = {
  id: 1, firstName: 'Sample', lastName: 'Student', email: 'student@example.test', role: 'student',
  country: null, state: null, groupId: 7, groupName: 'Sample group', schoolName: null,
  mentorBackground: null, mentorInstitution: null, mentorReason: null, mentorMaxGroupCount: null,
  yearLevel: null, joinPermissionReceived: true, guardianEmail: 'guardian@example.test', interests: [],
  isAdmin: false, isActive: true, hasLoggedIn: true, lastLogin: '2026-10-15T00:00:00Z',
  accountStatus: 'active', createdAt: '2026-08-01T00:00:00Z',
  invitedAt: '2026-08-01T00:00:00Z', activatedAt: '2026-08-01T00:00:00Z',
  supervisorName: null, supervisorEmail: null,
}

/** A user registered (createdAt, the API's date_joined) at `registered`, otherwise like the sample student. */
export const registeredUser = (id: number, role: string, registered: string, overrides: Partial<AdminUser> = {}): AdminUser => ({
  ...student,
  id,
  role,
  firstName: role.charAt(0).toUpperCase() + role.slice(1),
  lastName: String(id),
  email: `${role}${id}@example.test`,
  createdAt: registered,
  invitedAt: registered,
  activatedAt: registered,
  lastLogin: null,
  hasLoggedIn: false,
  ...overrides,
})
