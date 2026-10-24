import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

import { useRoute } from 'vue-router'
import ReleaseResourcesPage from '@/views/management/ReleaseResourcesPage.vue'
import { fetchAdminResource } from '@/utils/adminAPI'
import { fetchResourceReleases, saveResourceRelease, type ResourceReleaseRow } from '@/utils/managementAPI'

vi.mock('@/utils/managementAPI', () => ({
  fetchResourceReleases: vi.fn(),
  saveResourceRelease: vi.fn(),
}))
vi.mock('vue-router', async (importOriginal) => ({
  ...(await importOriginal<typeof import('vue-router')>()),
  useRoute: vi.fn(() => ({ query: {} })),
}))
vi.mock('@/utils/adminAPI', () => ({
  fetchAdminResource: vi.fn(),
  deleteAdminResource: vi.fn(),
}))

// Release times at midday Sydney: the same date in Sydney and in UTC (as CI
// runs), so each shows one way wherever the specs run.
const row = (id: number, name: string, extra: Partial<ResourceReleaseRow> = {}): ResourceReleaseRow => ({
  id, name, shown: true, release_on: null, released: true, last_released_at: null, ...extra,
})

const mountPage = async () => {
  const wrapper = mount(ReleaseResourcesPage, {
    global: {
      stubs: {
        AdminResourceFormSheet: true,
        teleport: true,
        // A name's link, its place as the href.
        RouterLink: { props: ['to'], template: '<a :href="JSON.stringify(to)"><slot /></a>' },
      },
    },
  })
  await flushPromises()
  return wrapper
}

const names = (wrapper: Awaited<ReturnType<typeof mountPage>>) =>
  wrapper.findAll('tbody tr .data-table-cell--primary').map((cell) => cell.text())

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(fetchResourceReleases).mockResolvedValue([
    row(1, 'Zebra notes', { last_released_at: '2025-03-10T12:00:00+11:00' }),
    row(2, 'Alpha guide'),
    row(3, 'Ethics primer', { last_released_at: '2025-02-12T12:00:00+11:00' }),
  ])
})

describe('Release Resources (Challenge Start)', () => {
  it('lists each resource by when it was released last year, those never released last', async () => {
    const wrapper = await mountPage()
    // Headed as Pages Visibility is: a plain title.
    expect(wrapper.get('.release-resources__title').text()).toBe('Release Resources')
    expect(wrapper.text()).toContain('from the start of that day, Sydney time')
    expect(wrapper.findAll('thead th').map((th) => th.text())).toEqual(
      expect.arrayContaining(['Name', 'Edit', 'Show/Hide', 'Release at', 'Last released']),
    )
    expect(names(wrapper)).toEqual(['Ethics primer', 'Zebra notes', 'Alpha guide'])
    // Each name opens its resource, whose Back comes back here.
    const link = wrapper.findAll('tbody tr')[0]!.get('a')
    expect(link.text()).toBe('Ethics primer')
    expect(JSON.parse(link.attributes('href')!)).toEqual({
      name: 'resource-detail', params: { id: '3' }, query: { from: 'release-resources' },
    })
    // As the other admin tables write a date.
    expect(wrapper.text()).toContain('12/02/25')
  })

  it("shows each resource's icon before its name, as the Resources page does", async () => {
    vi.mocked(fetchResourceReleases).mockResolvedValue([
      row(1, 'Page', { kind: 'page' }),
      row(2, 'Handbook', { kind: 'file', file_mime_type: 'application/pdf' }),
    ])
    const wrapper = await mountPage()
    const icons = wrapper.findAll('tbody tr .release-resources__icon').map((icon) => icon.classes())
    expect(icons[0]).toContain('fa-globe')
    expect(icons[1]).toContain('fa-file-pdf')
  })

  it('back from a resource, turns to the page with its row and brings it into view', async () => {
    const scrollIntoView = vi.fn()
    Element.prototype.scrollIntoView = scrollIntoView
    vi.mocked(fetchResourceReleases).mockResolvedValue(
      Array.from({ length: 20 }, (_, i) => row(i + 1, `Resource ${String(i + 1).padStart(2, '0')}`)),
    )
    vi.mocked(useRoute).mockReturnValueOnce({ query: { resource: '16' } } as never)
    const wrapper = await mountPage()
    await flushPromises()

    // 11 rows a page (the window jsdom has): the 16th is on the second.
    expect(wrapper.find('.data-table-summary').text()).toBe('12 - 20 out of 20')
    const focused = wrapper.get('tr.data-table-row--focused')
    expect(focused.attributes('data-row-key')).toBe('16')
    expect(scrollIntoView).toHaveBeenCalledWith({ block: 'center' })
  })

  it('hides one and sets its release date, each saved as it changes', async () => {
    vi.mocked(saveResourceRelease)
      .mockResolvedValueOnce(row(3, 'Ethics primer', { shown: false, released: false, last_released_at: '2025-02-12T12:00:00+11:00' }))
      .mockResolvedValueOnce(row(3, 'Ethics primer', { shown: false, released: false, release_on: '2026-11-30', last_released_at: '2025-02-12T12:00:00+11:00' }))
      .mockResolvedValueOnce(row(3, 'Ethics primer', { shown: false, released: false, last_released_at: '2025-02-12T12:00:00+11:00' }))
    const wrapper = await mountPage()

    wrapper.findAllComponents({ name: 'HideShowSwitch' })[0]!.vm.$emit('change', false)
    await flushPromises()
    expect(saveResourceRelease).toHaveBeenLastCalledWith(3, { shown: false })

    // No × on the date.
    expect(wrapper.findAllComponents({ name: 'AppDatePicker' })[0]!.props('clearable')).toBe(false)
    wrapper.findAllComponents({ name: 'AppDatePicker' })[0]!.vm.$emit('update:modelValue', '2026-11-30')
    await flushPromises()
    expect(saveResourceRelease).toHaveBeenLastCalledWith(3, { release_on: '2026-11-30' })

    wrapper.findAllComponents({ name: 'AppDatePicker' })[0]!.vm.$emit('update:modelValue', '')
    await flushPromises()
    expect(saveResourceRelease).toHaveBeenLastCalledWith(3, { release_on: null })
  })

  it("opens a resource's Edit in the Resources page's panel", async () => {
    vi.mocked(fetchAdminResource).mockResolvedValue({ id: 2, name: 'Alpha guide' } as never)
    const wrapper = await mountPage()
    await wrapper.get('[data-test="release-edit-2"]').trigger('click')
    await flushPromises()
    expect(fetchAdminResource).toHaveBeenCalledWith(2)
    const sheet = wrapper.findComponent({ name: 'AdminResourceFormSheet' })
    expect(sheet.props('modelValue')).toBe(true)
  })
})
