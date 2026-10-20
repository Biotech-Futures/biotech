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
    expect(wrapper.text()).toContain('No name matches.')
  })

  it('adds a name in its place by name', async () => {
    vi.mocked(addKnownUniversity).mockResolvedValue({ id: 3, name: 'Monash', createdAt: '2026-10-20T00:00:00Z' })
    const wrapper = await mountPage()

    await wrapper.get('[data-test="university-new-name"]').setValue(' Monash ')
    await wrapper.get('[data-test="university-add"]').trigger('submit')
    await flushPromises()

    expect(addKnownUniversity).toHaveBeenCalledWith(' Monash ')
    expect(names(wrapper)).toEqual(['Monash', 'UNSW', 'USYD'])
    expect((wrapper.get('[data-test="university-new-name"]').element as HTMLInputElement).value).toBe('')
  })

  it("says why an add was refused, keeping what's typed", async () => {
    vi.mocked(addKnownUniversity).mockRejectedValue(refused("'USYD' is already on the list"))
    const wrapper = await mountPage()

    await wrapper.get('[data-test="university-new-name"]').setValue('usyd')
    await wrapper.get('[data-test="university-add"]').trigger('submit')
    await flushPromises()

    expect(wrapper.get('[role="alert"]').text()).toBe("'USYD' is already on the list")
    expect((wrapper.get('[data-test="university-new-name"]').element as HTMLInputElement).value).toBe('usyd')
  })

  it('renames one in its row', async () => {
    vi.mocked(renameKnownUniversity).mockResolvedValue({ ...usyd, name: 'Sydney Uni' })
    const wrapper = await mountPage()

    await wrapper.get('[data-test="university-edit-1"]').trigger('click')
    await wrapper.get('[data-test="university-edit-name"]').setValue('Sydney Uni')
    await wrapper.get('[data-test="university-save"]').trigger('click')
    await flushPromises()

    expect(renameKnownUniversity).toHaveBeenCalledWith(1, 'Sydney Uni')
    expect(names(wrapper)).toEqual(['Sydney Uni', 'UNSW'])
    expect(wrapper.find('[data-test="university-edit-name"]').exists()).toBe(false)
  })

  it('keeps the box open with the reason when a rename is refused', async () => {
    vi.mocked(renameKnownUniversity).mockRejectedValue(refused("'UNSW' is already on the list"))
    const wrapper = await mountPage()

    await wrapper.get('[data-test="university-edit-1"]').trigger('click')
    await wrapper.get('[data-test="university-edit-name"]').setValue('unsw')
    await wrapper.get('[data-test="university-save"]').trigger('click')
    await flushPromises()

    expect(wrapper.get('[role="alert"]').text()).toBe("'UNSW' is already on the list")
    expect(wrapper.find('[data-test="university-edit-name"]').exists()).toBe(true)
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
