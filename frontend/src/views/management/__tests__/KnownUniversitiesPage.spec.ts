import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

import KnownUniversitiesPage from '@/views/management/KnownUniversitiesPage.vue'
import {
  addKnownUniversity,
  deleteKnownUniversity,
  fetchKnownUniversities,
  renameKnownUniversity,
} from '@/utils/adminAPI'
import { ApiError } from '@/utils/apiError'

vi.mock('@/utils/adminAPI', () => ({
  fetchKnownUniversities: vi.fn(),
  addKnownUniversity: vi.fn(),
  renameKnownUniversity: vi.fn(),
  deleteKnownUniversity: vi.fn(),
}))

const usyd = { id: 1, name: 'USYD', createdAt: '2026-10-18T03:00:00Z' }
const unsw = { id: 2, name: 'UNSW', createdAt: '2026-10-18T04:00:00Z' }

const refused = (msg: string) => new ApiError({ error: msg, code: 'http_400', request_id: 'x' }, 400)

const mountPage = async () => {
  const wrapper = mount(KnownUniversitiesPage, { global: { stubs: { teleport: true } } })
  await flushPromises()
  return wrapper
}

// The names the table shows, in its order.
const names = (wrapper: Awaited<ReturnType<typeof mountPage>>) =>
  wrapper.findAll('tbody tr .data-table-cell--primary').map((cell) => cell.text())

describe('Known Universities', () => {
  beforeEach(() => {
    vi.mocked(fetchKnownUniversities).mockReset().mockResolvedValue([unsw, usyd])
    vi.mocked(addKnownUniversity).mockReset()
    vi.mocked(renameKnownUniversity).mockReset()
    vi.mocked(deleteKnownUniversity).mockReset()
  })

  it('lists every name, and finds them by part of one in any casing', async () => {
    const wrapper = await mountPage()
    expect(wrapper.text()).toContain('Registration asks a student to confirm their school is a school')
    expect(names(wrapper)).toEqual(['UNSW', 'USYD'])

    expect(wrapper.text()).toContain('2 universities listed')
    await wrapper.get('.data-table-search-input').setValue('sy')
    expect(names(wrapper)).toEqual(['USYD'])
    await wrapper.get('.data-table-search-input').setValue('monash')
    expect(wrapper.text()).toContain('No university matches.')
  })

  it('adds one from its popup, with its acronym and country, in its place by name', async () => {
    vi.mocked(addKnownUniversity).mockResolvedValue({
      id: 3, name: 'Monash University', acronym: 'MU', country: 'Australia', createdAt: '2026-10-20T00:00:00Z',
    })
    const wrapper = await mountPage()

    await wrapper.get('[data-test="university-add-open"]').trigger('click')
    await wrapper.get('[data-test="university-name"]').setValue(' Monash University ')
    await wrapper.get('[data-test="university-acronym"]').setValue('MU')
    await wrapper.get('[data-test="university-country"]').setValue('Australia')
    await wrapper.get('[data-test="university-form"]').trigger('submit')
    await flushPromises()

    expect(addKnownUniversity).toHaveBeenCalledWith({ name: ' Monash University ', acronym: 'MU', country: 'Australia' })
    expect(names(wrapper)).toEqual(['Monash University', 'UNSW', 'USYD'])
    // The popup closes once it's added.
    expect(wrapper.find('[data-test="university-form"]').exists()).toBe(false)
  })

  it("says in the popup why an add was refused, keeping what's typed", async () => {
    vi.mocked(addKnownUniversity).mockRejectedValue(refused("'USYD' is already on the list"))
    const wrapper = await mountPage()

    await wrapper.get('[data-test="university-add-open"]').trigger('click')
    await wrapper.get('[data-test="university-name"]').setValue('usyd')
    await wrapper.get('[data-test="university-form"]').trigger('submit')
    await flushPromises()

    expect(wrapper.get('[role="alert"]').text()).toBe("'USYD' is already on the list")
    expect((wrapper.get('[data-test="university-name"]').element as HTMLInputElement).value).toBe('usyd')
  })

  it('edits one in its popup: its name, acronym and country', async () => {
    vi.mocked(renameKnownUniversity).mockResolvedValue({ ...usyd, name: 'Sydney Uni', acronym: 'USYD', country: 'Australia' })
    const wrapper = await mountPage()

    await wrapper.get('[data-test="university-edit-1"]').trigger('click')
    expect((wrapper.get('[data-test="university-name"]').element as HTMLInputElement).value).toBe('USYD')
    await wrapper.get('[data-test="university-name"]').setValue('Sydney Uni')
    await wrapper.get('[data-test="university-acronym"]').setValue('USYD')
    await wrapper.get('[data-test="university-country"]').setValue('Australia')
    await wrapper.get('[data-test="university-form"]').trigger('submit')
    await flushPromises()

    expect(renameKnownUniversity).toHaveBeenCalledWith(1, { name: 'Sydney Uni', acronym: 'USYD', country: 'Australia' })
    expect(names(wrapper)).toEqual(['Sydney Uni', 'UNSW'])
    expect(wrapper.find('[data-test="university-form"]').exists()).toBe(false)
  })

  it('keeps the popup open with the reason when an edit is refused', async () => {
    vi.mocked(renameKnownUniversity).mockRejectedValue(refused("'UNSW' is already on the list"))
    const wrapper = await mountPage()

    await wrapper.get('[data-test="university-edit-1"]').trigger('click')
    await wrapper.get('[data-test="university-name"]').setValue('unsw')
    await wrapper.get('[data-test="university-form"]').trigger('submit')
    await flushPromises()

    expect(wrapper.get('[role="alert"]').text()).toBe("'UNSW' is already on the list")
    expect((wrapper.get('[data-test="university-name"]').element as HTMLInputElement).value).toBe('unsw')
  })

  it('deletes one once confirmed', async () => {
    vi.mocked(deleteKnownUniversity).mockResolvedValue('ok')
    const wrapper = await mountPage()

    await wrapper.get('[data-test="university-delete-2"]').trigger('click')
    const dialog = wrapper.get('.admin-modal--confirm')
    expect(dialog.text()).toContain('Take UNSW off the list?')
    await dialog.findAll('button').find((button) => button.text() === 'Delete')!.trigger('click')
    await flushPromises()

    expect(deleteKnownUniversity).toHaveBeenCalledWith(2)
    expect(names(wrapper)).toEqual(['USYD'])
    expect(wrapper.find('.admin-modal--confirm').exists()).toBe(false)
  })
})
