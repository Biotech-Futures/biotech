import { afterEach, describe, expect, it, vi } from 'vitest'
import { ref } from 'vue'
import {
  canonicalColumnKey,
  columnLabel,
  useAdminViewExecuted,
  type ViewResultRow
} from '@/composables/admin/useAdminViewExecuted'
import type { AdminView } from '@/utils/adminAPI'

const country = { id: 1, countryName: 'Australia' }
const state = { id: 1, stateName: 'NSW', countryName: 'Australia' }

const baseRow = {
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
  interests: [],
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

const buildRow = (overrides: Partial<ViewResultRow> = {}): ViewResultRow =>
  ({ ...baseRow, ...overrides }) as ViewResultRow

const buildView = (overrides: Partial<AdminView> = {}): AdminView => ({
  id: 5,
  name: 'Test Student View',
  description: '',
  isDefault: false,
  targetRoles: ['student'],
  accountStatus: 'all',
  engagementStatus: 'all',
  advancedConditions: [],
  visibleColumns: ['name', 'email', 'role', 'school', 'status'],
  ...overrides
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.useRealTimers()
})

describe('canonicalColumnKey / columnLabel', () => {
  it('maps known aliases to their canonical key and label', () => {
    expect(canonicalColumnKey('last_login')).toBe('lastlogin')
    expect(columnLabel('last_login')).toBe('Last Login')

    expect(canonicalColumnKey('institution')).toBe('school')
    expect(columnLabel('institution')).toBe('School / Institution')

    expect(canonicalColumnKey('Year Level')).toBe('yearlevel')
    expect(columnLabel('year_lvl')).toBe('Year Level')
  })

  it('falls back to a title-cased label for an unrecognized key', () => {
    expect(columnLabel('custom_field')).toBe('Custom Field')
  })
})

describe('useAdminViewExecuted: columns', () => {
  it('derives columns from the loaded view, in order, with a trailing actions column', () => {
    const { view, columns } = useAdminViewExecuted(ref(5))
    view.value = buildView({ visibleColumns: ['name', 'email', 'role'] })

    expect(columns.value.map((c) => c.key)).toEqual(['name', 'email', 'role', 'actions'])
    expect(columns.value.at(-1)).toMatchObject({ key: 'actions', label: 'Actions', align: 'right' })
  })

  it('reflects a different view definition with different columns', () => {
    const { view, columns } = useAdminViewExecuted(ref(5))
    view.value = buildView({ visibleColumns: ['name', 'school', 'status'] })

    expect(columns.value.map((c) => c.key)).toEqual(['name', 'school', 'status', 'actions'])
  })
})

describe('useAdminViewExecuted: canAssignToGroup', () => {
  it('is false when nothing is selected', () => {
    const { canAssignToGroup } = useAdminViewExecuted(ref(5))
    expect(canAssignToGroup.value).toBe(false)
  })

  it('is true when every selected row is a student', () => {
    const { rows, onSelectedChange, canAssignToGroup } = useAdminViewExecuted(ref(5))
    rows.value = [
      buildRow({ id: 1, role: 'student' }),
      buildRow({ id: 2, role: 'student' })
    ]
    onSelectedChange([1, 2])

    expect(canAssignToGroup.value).toBe(true)
  })

  it('is false when the selection mixes a non-student in', () => {
    const { rows, onSelectedChange, canAssignToGroup } = useAdminViewExecuted(ref(5))
    rows.value = [
      buildRow({ id: 1, role: 'student' }),
      buildRow({ id: 2, role: 'mentor' })
    ]
    onSelectedChange([1, 2])

    expect(canAssignToGroup.value).toBe(false)
  })
})

describe('useAdminViewExecuted: openBatchAssign defense-in-depth guard', () => {
  it('does not open the assign dialog for a mixed selection even if called directly', () => {
    const { rows, onSelectedChange, canAssignToGroup, openBatchAssign, assignOpen, assignStudents } =
      useAdminViewExecuted(ref(5))
    rows.value = [
      buildRow({ id: 1, role: 'student' }),
      buildRow({ id: 2, role: 'mentor' })
    ]
    onSelectedChange([1, 2])
    expect(canAssignToGroup.value).toBe(false)

    openBatchAssign()

    expect(assignOpen.value).toBe(false)
    expect(assignStudents.value).toEqual([])
  })

  it('opens the assign dialog with the selected rows for an all-student selection', () => {
    const { rows, onSelectedChange, openBatchAssign, assignOpen, assignStudents } =
      useAdminViewExecuted(ref(5))
    rows.value = [buildRow({ id: 1, role: 'student' }), buildRow({ id: 2, role: 'student' })]
    onSelectedChange([1, 2])

    openBatchAssign()

    expect(assignOpen.value).toBe(true)
    expect(assignStudents.value.map((u) => u.id)).toEqual([1, 2])
  })
})

const jsonResponse = (data: unknown) =>
  new Response(JSON.stringify({ msg: 'ok', data }), {
    status: 200,
    headers: { 'Content-Type': 'application/json' }
  })

const fetchMockFor = (view: AdminView) =>
  vi.fn().mockImplementation((url: string) => {
    if (String(url).includes('/run/')) {
      return Promise.resolve(
        jsonResponse({ items: [], total: 0, page: 1, limit: 25, hasMore: false, view })
      )
    }
    if (String(url).includes('/export-csv/')) {
      return Promise.resolve(new Response('name,email\nAda,ada@example.com', { status: 200 }))
    }
    return Promise.resolve(jsonResponse({}))
  })

/** jsdom doesn't implement Blob URLs or anchor-download navigation; stub both so
 *  exportCsv()'s blob-download idiom runs cleanly, and capture the anchor it
 *  creates so tests can inspect the derived filename. */
const stubBlobDownload = () => {
  window.URL.createObjectURL = vi.fn(() => 'blob:mock-url')
  window.URL.revokeObjectURL = vi.fn()
  let capturedAnchor: HTMLAnchorElement | undefined
  const realCreateElement = document.createElement.bind(document)
  vi.spyOn(document, 'createElement').mockImplementation((tag: string) => {
    const el = realCreateElement(tag)
    if (tag === 'a') {
      capturedAnchor = el as HTMLAnchorElement
      el.click = vi.fn()
    }
    return el
  })
  return { getAnchor: () => capturedAnchor }
}

describe('useAdminViewExecuted: CSV export', () => {
  it('sanitizes the view name into a filename, falling back to view_export.csv', async () => {
    const view = buildView({ name: 'Test Student View' })
    const fetchMock = fetchMockFor(view)
    vi.stubGlobal('fetch', fetchMock)
    const { getAnchor } = stubBlobDownload()

    const composable = useAdminViewExecuted(ref(5))
    composable.view.value = view
    await composable.exportCsv()

    expect(getAnchor()?.download).toBe('test_student_view_export.csv')

    // A blank/whitespace-only name sanitizes to an empty slug, falling back to the generic name.
    composable.view.value = buildView({ name: '   ' })
    await composable.exportCsv()
    expect(getAnchor()?.download).toBe('view_export.csv')
  })

  it('requests the export with session credentials and the currently applied search', async () => {
    vi.useFakeTimers()
    const view = buildView()
    const fetchMock = fetchMockFor(view)
    vi.stubGlobal('fetch', fetchMock)
    stubBlobDownload()

    const composable = useAdminViewExecuted(ref(5))
    composable.view.value = view
    composable.searchInput.value = 'Ada'
    await vi.advanceTimersByTimeAsync(350)

    await composable.exportCsv()

    const exportCall = fetchMock.mock.calls.find((call) => String(call[0]).includes('/export-csv/'))
    expect(exportCall).toBeDefined()
    expect(String(exportCall![0])).toContain('search=Ada')
    expect(exportCall![1]).toMatchObject({ method: 'GET', credentials: 'include' })
  })

  it('tracks its own exporting state without touching the shared busy flag', async () => {
    const view = buildView()
    vi.stubGlobal('fetch', fetchMockFor(view))
    stubBlobDownload()

    const composable = useAdminViewExecuted(ref(5))
    composable.view.value = view

    expect(composable.exporting.value).toBe(false)
    expect(composable.busy.value).toBe(false)

    const pending = composable.exportCsv()
    expect(composable.exporting.value).toBe(true)
    expect(composable.busy.value).toBe(false)

    await pending

    expect(composable.exporting.value).toBe(false)
    expect(composable.busy.value).toBe(false)
  })
})
