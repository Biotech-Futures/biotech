import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import * as api from '@/utils/liveAnalyticsApi'
import { clearLiveAnalyticsCache } from '@/utils/liveAnalyticsData'
import UsersPage from '@/views/UsersAnalyticsPage.vue'

vi.mock('@/utils/liveAnalyticsApi', () => ({
  fetchAllUsers: vi.fn(), fetchAllGroups: vi.fn(), fetchMentors: vi.fn(),
  fetchGroupActivity: vi.fn(), fetchLoginActivity: vi.fn(),
  fetchResourceAnalytics: vi.fn(), fetchEmailDeliveryAnalytics: vi.fn(), fetchAllResources: vi.fn(),
}))
vi.mock('vue-router', () => ({
  useRoute: () => ({ query: {}, hash: '' }),
  useRouter: () => ({ push: vi.fn() }),
}))
vi.mock('@/composables/useAnalyticsRefreshState', () => ({ useAnalyticsRefreshState: vi.fn() }))

const baseUser: api.AdminUser = {
  id: 1, firstName: 'Sample', lastName: 'Student', email: 'student@example.test', role: 'student',
  country: null, state: null, groupId: null, groupName: null, schoolName: null,
  mentorBackground: null, mentorInstitution: null, mentorReason: null, mentorMaxGroupCount: null,
  yearLevel: null, joinPermissionReceived: true, guardianEmail: null, interests: [],
  isAdmin: false, isActive: true, hasLoggedIn: true, lastLogin: '2026-10-15T00:00:00Z',
  accountStatus: 'active', createdAt: '2026-08-01T00:00:00Z', invitedAt: '2026-08-01T00:00:00Z', activatedAt: '2026-08-01T00:00:00Z',
  supervisorName: null, supervisorEmail: null,
}
const from = (id: number, location: Pick<api.AdminUser, 'country' | 'state'>): api.AdminUser =>
  ({ ...baseUser, id, ...location })

let wrapper: VueWrapper | undefined

beforeEach(() => {
  vi.resetAllMocks()
  vi.useFakeTimers({ toFake: ['Date'] })
  vi.setSystemTime(new Date('2026-10-20T12:00:00Z'))
  clearLiveAnalyticsCache()
  vi.mocked(api.fetchAllGroups).mockResolvedValue([])
  vi.mocked(api.fetchLoginActivity).mockResolvedValue({
    by_day: [], by_year: [], active_users: { daily: 0, weekly: 0, monthly: 0 },
    latest_activity_date: '2026-10-15', query_range: { start: null, end: null },
  })
})

afterEach(() => {
  wrapper?.unmount()
  wrapper = undefined
  vi.useRealTimers()
})

async function showUsersPage(users: api.AdminUser[]) {
  vi.mocked(api.fetchAllUsers).mockResolvedValue(users)
  wrapper = mount(UsersPage, { global: { stubs: { RouterLink: true, AnalyticsDatePicker: true, ChartTooltip: true } } })
  await flushPromises()
  await flushPromises()
  return wrapper
}

async function openWorldMap(users: api.AdminUser[]) {
  const w = await showUsersPage(users)
  await w.get('[aria-label="Expand region card"]').trigger('click')
  return w
}

const regionCounts = (w: VueWrapper) => Object.fromEntries(
  w.findAll('.region-summary-card').map((card) => [
    card.get('.region-summary-name').text(),
    Number(card.get('.region-summary-value').text()),
  ]),
)

const mapContinentTotals = (w: VueWrapper) => Object.fromEntries(
  w.findAll('.map-summary-point').map((point) => [
    point.get('.large-map-summary-label').text(),
    Number(point.get('.large-map-summary-value').text()),
  ]),
)

describe('World Registration Map region totals', () => {
  it('counts users in Nigeria towards Africa', async () => {
    const w = await openWorldMap([1, 2, 3].map((id) => from(id, { country: { countryName: 'Nigeria' }, state: null })))

    expect(regionCounts(w)).toMatchObject({ International: 3, Africa: 3 })
    expect(mapContinentTotals(w).Africa).toBe(3)
  })

  it('adds every listed country to its region, so the regions add up to International', async () => {
    const w = await openWorldMap([
      from(1, { country: { countryName: 'Nigeria' }, state: null }),
      from(2, { country: { countryName: 'Kenya' }, state: null }),
      from(3, { country: { countryName: 'United States of America' }, state: null }),
      from(4, { country: { countryName: 'Mexico' }, state: null }),
      from(5, { country: { countryName: 'Argentina' }, state: null }),
      from(6, { country: { countryName: 'Spain' }, state: null }),
      from(7, { country: { countryName: 'Vietnam' }, state: null }),
      from(8, { country: { countryName: 'Fiji' }, state: null }),
      from(9, { country: { countryName: 'Australia' }, state: { stateName: 'NSW' } }),
      from(10, { country: null, state: null }),
    ])

    const counts = regionCounts(w)
    expect(counts).toEqual({
      International: 8,
      'North America': 2,
      'South America': 1,
      Europe: 1,
      Africa: 2,
      Asia: 1,
      // Fiji, plus the NSW user.
      Oceania: 2,
    })
    // A user with no location is in no region.
    const overseas = counts['North America'] + counts['South America'] + counts.Europe + counts.Africa + counts.Asia + (counts.Oceania - 1)
    expect(overseas).toBe(counts.International)
    expect(mapContinentTotals(w)).toEqual({
      'North America': 2, 'South America': 1, Europe: 1, Africa: 2, Asia: 1, Oceania: 2,
    })
  })

  it('counts Australian users without a state in Oceania, not International', async () => {
    const w = await openWorldMap([
      from(1, { country: { countryName: 'Australia' }, state: null }),
      from(2, { country: { countryName: 'Australia' }, state: null }),
      from(3, { country: { countryName: 'Australia' }, state: { stateName: 'VIC' } }),
      from(4, { country: { countryName: 'Nigeria' }, state: null }),
    ])

    expect(regionCounts(w)).toMatchObject({ International: 1, Africa: 1, Oceania: 3 })
    // The map's Australia total covers users with and without a state.
    expect(w.findAll('.small-map-value').map((label) => label.text())).toEqual(['3', '1'])
  })

  it('shows United States of America users on the map under the map\'s country name', async () => {
    const w = await openWorldMap([
      from(1, { country: { countryName: 'United States of America' }, state: null }),
      from(2, { country: { countryName: 'Nigeria' }, state: null }),
    ])

    const ranking = w.findAll('.region-ranking li').map((row) => row.get('.rank-name').text())
    expect(ranking).toEqual(['Nigeria', 'United States'])
    // One value label per country on the map: neither is dropped.
    expect(w.findAll('.small-map-value').map((label) => label.text())).toEqual(['1', '1'])
    expect(regionCounts(w)['North America']).toBe(1)
  })
})
