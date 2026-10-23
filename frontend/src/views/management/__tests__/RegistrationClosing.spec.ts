import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

import LateLinksPage from '@/views/management/LateLinksPage.vue'
import RegistrationDatesPage from '@/views/management/RegistrationDatesPage.vue'
import SupervisorsAfterClosePage from '@/views/management/SupervisorsAfterClosePage.vue'
import {
  createLateLink,
  fetchRegistrationManagement,
  fetchRegistrationSupervisors,
  revokeLateLink,
  saveRegistrationSupervisor,
  saveRegistrationWindow,
  type LateLink,
  type RegistrationManagement,
} from '@/utils/managementAPI'

vi.mock('@/utils/managementAPI', () => ({
  fetchRegistrationManagement: vi.fn(),
  saveRegistrationWindow: vi.fn(),
  createLateLink: vi.fn(),
  revokeLateLink: vi.fn(),
  fetchRegistrationSupervisors: vi.fn(),
  saveRegistrationSupervisor: vi.fn(),
  fetchRegistrationOpen: vi.fn().mockResolvedValue({ open_now: true, opens_at: null, closes_at: null }),
}))

const link = (over: Partial<LateLink> = {}): LateLink => ({
  id: 1,
  email: '',
  created_at: '2026-10-01T00:00:00Z',
  expires_at: '2026-10-08T00:00:00Z',
  revoked_at: null,
  used_at: null,
  status: 'active',
  url: 'https://portal.test/#/register?invite=abc',
  ...over,
})

const management = (over: Partial<RegistrationManagement> = {}): RegistrationManagement => ({
  window: { year: 2026, opens_at: null, closes_at: null },
  count: 0,
  page: 1,
  invitations: [],
  ...over,
})

beforeEach(() => {
  vi.clearAllMocks()
})

describe('Registration Dates', () => {
  it('shows where the dates leave registration, and saves or clears them', async () => {
    vi.mocked(fetchRegistrationManagement).mockResolvedValue(
      management({
        window: {
          year: 2026,
          opens_at: null,
          closes_at: '2000-01-01T00:00:00Z',
          set_by: 'Test Admin',
          updated_at: '2026-10-04T01:25:00Z',
        },
      }),
    )
    vi.mocked(saveRegistrationWindow).mockResolvedValue({
      window: { year: 2026, opens_at: null, closes_at: null },
    })
    const wrapper = mount(RegistrationDatesPage)
    await flushPromises()

    expect(wrapper.get('[data-test="registration-dates-state"]').text()).toContain('Registration has closed')
    expect(wrapper.get('[data-test="registration-dates-set-by"]').text()).toMatch(/^Set by Test Admin on /)
    expect(wrapper.get('[data-test="registration-closes"]').text()).not.toBe('Select date and time')

    await wrapper.findAll('button').find((button) => button.text() === 'Clear Dates')!.trigger('click')
    await flushPromises()
    expect(saveRegistrationWindow).toHaveBeenCalledWith({ opens_at: null, closes_at: null })
    expect(wrapper.get('[data-test="registration-dates-state"]').text()).toContain('No dates set')
  })

  it('says a year Start new year began is closed until its start is set', async () => {
    vi.mocked(fetchRegistrationManagement).mockResolvedValue(
      management({ window: { year: 2027, opens_at: null, closes_at: null, closed_until_set: true } }),
    )
    const wrapper = mount(RegistrationDatesPage)
    await flushPromises()
    expect(wrapper.get('[data-test="registration-dates-state"]').text()).toContain(
      'No start date set: registration is closed',
    )
  })
})

describe('Late Links', () => {
  it('creates a link to copy, lists them newest first, and revokes an active one', async () => {
    vi.mocked(fetchRegistrationManagement).mockResolvedValue(
      management({ invitations: [link(), link({ id: 2, status: 'used', url: null, email: 'late@student.test' })] }),
    )
    vi.mocked(createLateLink).mockResolvedValue(link({ id: 3, url: 'https://portal.test/#/register?invite=new' }))
    vi.mocked(revokeLateLink).mockResolvedValue(link({ status: 'revoked' }))
    const wrapper = mount(LateLinksPage)
    await flushPromises()

    expect(wrapper.text()).toContain('Active')
    expect(wrapper.text()).toContain('Used')
    // Who registered with the used one.
    expect(wrapper.text()).toContain('late@student.test')

    const before = Date.now()
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(createLateLink).toHaveBeenCalledOnce()
    // Works for 3 days.
    const expires = Date.parse(vi.mocked(createLateLink).mock.calls[0]![0])
    expect(Math.round((expires - before) / (24 * 60 * 60 * 1000))).toBe(3)
    expect(wrapper.get('[data-test="late-link-created"]').text()).toContain('invite=new')

    // Revoke the first active one in the list: the new link.
    const revoke = wrapper.findAll('button').filter((button) => button.text() === 'Revoke')
    expect(revoke).toHaveLength(2)
    await revoke[1]!.trigger('click')
    await flushPromises()
    expect(revokeLateLink).toHaveBeenCalledWith(1)
    expect(wrapper.text()).toContain('Revoked')
  })
})

describe('Supervisors After Close', () => {
  it('lists every supervisor, and switches one on straight away', async () => {
    const sam = {
      user_id: 7,
      name: 'Sam Lee',
      email: 'sam@school.test',
      school: 'Example High',
      students: 12,
      register_after_close: false,
    }
    vi.mocked(fetchRegistrationSupervisors).mockResolvedValue([sam])
    vi.mocked(saveRegistrationSupervisor).mockResolvedValue({ ...sam, register_after_close: true })
    const wrapper = mount(SupervisorsAfterClosePage)
    await flushPromises()

    const row = wrapper.get('tbody tr.data-table-row')
    expect(row.text()).toContain('Sam Lee')
    expect(row.text()).toContain('12')
    const toggle = row.get('input[role="switch"]')
    expect((toggle.element as HTMLInputElement).checked).toBe(false)

    ;(toggle.element as HTMLInputElement).checked = true
    await toggle.trigger('change')
    await flushPromises()
    expect(saveRegistrationSupervisor).toHaveBeenCalledWith(7, true)
    expect((wrapper.get('input[role="switch"]').element as HTMLInputElement).checked).toBe(true)
  })

  it('lists the supervisors with the most students first', async () => {
    const supervisor = (user_id: number, name: string, students: number) => ({
      user_id, name, email: `${user_id}@school.test`, school: '', students, register_after_close: false,
    })
    vi.mocked(fetchRegistrationSupervisors).mockResolvedValue([
      supervisor(1, 'Few Students', 2),
      supervisor(2, 'Most Students', 30),
      supervisor(3, 'Some Students', 9),
    ])
    const wrapper = mount(SupervisorsAfterClosePage)
    await flushPromises()

    const names = wrapper.findAll('tbody tr.data-table-row').map((row) => row.text())
    expect(names.map((text) => text.match(/\w+ Students/)![0])).toEqual([
      'Most Students',
      'Some Students',
      'Few Students',
    ])
  })
})
