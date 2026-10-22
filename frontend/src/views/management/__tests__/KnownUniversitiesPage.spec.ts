import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

import KnownUniversitiesPage from '@/views/management/KnownUniversitiesPage.vue'
import {
  addKnownUniversity,
  deleteKnownUniversity,
  fetchKnownUniversities,
  renameKnownUniversity,
  uploadKnownUniversities,
} from '@/utils/adminAPI'
import { ApiError } from '@/utils/apiError'
import { appSelectLabels, appSelectText, pickAppSelect } from '@/__tests__/appSelect'

vi.mock('@/utils/adminAPI', () => ({
  fetchKnownUniversities: vi.fn(),
  addKnownUniversity: vi.fn(),
  renameKnownUniversity: vi.fn(),
  deleteKnownUniversity: vi.fn(),
  uploadKnownUniversities: vi.fn(),
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
    vi.mocked(uploadKnownUniversities).mockReset()
  })

  it('lists every name, and finds them by part of one in any casing', async () => {
    const wrapper = await mountPage()
    expect(wrapper.text()).toContain('Registration asks a student to confirm their school is a school')
    expect(names(wrapper)).toEqual(['UNSW', 'USYD'])

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

  it('deletes those ticked together once confirmed', async () => {
    vi.mocked(deleteKnownUniversity).mockResolvedValue('ok')
    const wrapper = await mountPage()

    for (const box of wrapper.findAll('tbody .data-table-check-col input[type="checkbox"]')) {
      await box.setValue(true)
    }
    await wrapper.get('[data-test="university-delete-selected"]').trigger('click')
    const dialog = wrapper.get('.admin-modal--confirm')
    expect(dialog.text()).toContain('Take these 2 universities off the list?')
    await dialog.findAll('button').find((button) => button.text() === 'Delete')!.trigger('click')
    await flushPromises()

    expect(vi.mocked(deleteKnownUniversity).mock.calls.map(([id]) => id).sort()).toEqual([1, 2])
    expect(names(wrapper)).toEqual([])
  })

  it('previews a file of universities, then applies it and says what it did', async () => {
    const checked = (summary: { added: number; filled: number; skipped: number }, applied?: boolean) => ({
      checks: { missing_headers: [], header_order: '', conflicts: [] },
      summary: { ...summary, errors: 0 },
      filled_rows: summary.filled ? [{ row: 2, name: 'Monash University' }] : [],
      listed_rows: [{ row: 4, name: 'University of Sydney' }],
      repeated_rows: [{ rows: [5, 9], name: 'Deakin University' }, { rows: [6, 8], name: 'RMIT' }],
      invalid_rows: [12],
      ...(applied ? { applied } : {}),
    })
    vi.mocked(uploadKnownUniversities)
      .mockResolvedValueOnce(checked({ added: 3, filled: 1, skipped: 2 }))
      .mockResolvedValueOnce(checked({ added: 3, filled: 1, skipped: 2 }, true))
    const wrapper = await mountPage()

    await wrapper.get('[data-test="university-upload-open"]').trigger('click')
    const dialog = wrapper.get('[data-test="university-upload-form"]')
    expect(dialog.text()).toContain('Upload universities')
    expect(dialog.text()).toContain('Column headers must match exactly and need to be in order.')
    expect(dialog.text()).toContain('No file selected.')
    expect(wrapper.get('[data-test="university-upload-submit"]').attributes('disabled')).toBeDefined()

    // Picking a file previews it.
    const file = new File(['name,acronym,country\nDeakin University,,\n'], 'universities.csv', { type: 'text/csv' })
    const input = dialog.get('[data-test="university-upload-file"]')
    Object.defineProperty(input.element, 'files', { value: [file] })
    await input.trigger('change')
    await flushPromises()
    expect(uploadKnownUniversities).toHaveBeenLastCalledWith(file, true)
    const checks = wrapper.get('[data-test="university-upload-checks"]').text()
    expect(checks).toContain('Missing Column Header(s): None')
    expect(checks).toContain('Filling In Existing Records: 1 (2 - Monash University)')
    expect(checks).toContain('Writing New Records: 3')
    expect(checks).toContain('Already Exists: 1 (Cannot be Added) (4 - University of Sydney)')
    expect(wrapper.get('[data-test="university-upload-checks"] .bulk-upload__check--bad').text()).toBe('(Cannot be Added)')
    expect(checks).toContain('Repeated Names: 2 (row 5, 9 Deakin University, row 6, 8 RMIT)')
    expect(checks).toContain('Blank or Too Long: 1 (row 12)')

    // Apply loads it.
    await wrapper.get('[data-test="university-upload-submit"]').trigger('click')
    await flushPromises()
    expect(uploadKnownUniversities).toHaveBeenLastCalledWith(file, false)
    expect(fetchKnownUniversities).toHaveBeenCalledTimes(2)
    expect(wrapper.find('[data-test="university-upload-form"]').exists()).toBe(false)
    expect(wrapper.get('[data-test="university-upload-summary"]').text()).toBe(
      'Added 3 universities, filled in details for 1, skipped 2 already listed or blank.',
    )
  })

  it("won't apply a file whose headers are wrong", async () => {
    vi.mocked(uploadKnownUniversities).mockResolvedValueOnce({
      checks: { missing_headers: ['country'], header_order: '', conflicts: [] },
      summary: { added: 0, filled: 0, skipped: 0, errors: 1 },
      filled_rows: [],
      listed_rows: [],
      repeated_rows: [],
      invalid_rows: [],
    })
    const wrapper = await mountPage()
    await wrapper.get('[data-test="university-upload-open"]').trigger('click')
    const input = wrapper.get('[data-test="university-upload-file"]')
    Object.defineProperty(input.element, 'files', { value: [new File(['name,acronym\n'], 'list.csv')] })
    await input.trigger('change')
    await flushPromises()

    expect(wrapper.get('[data-test="university-upload-checks"]').text()).toBe('Missing Column Header(s): country')
    expect(wrapper.get('[data-test="university-upload-submit"]').attributes('disabled')).toBeDefined()
  })
})

describe('Known Universities: the Country filter', () => {
  const day = '2026-10-18T03:00:00Z'
  const list = [
    { id: 1, name: 'Monash University', country: 'Australia', createdAt: day },
    { id: 2, name: 'University of Auckland', country: 'New Zealand', createdAt: day },
    // The same country, typed differently.
    { id: 3, name: 'UNSW', country: ' australia ', createdAt: day },
    { id: 4, name: 'USYD', createdAt: day },
  ]
  const filter = '[data-test="university-country-filter"]'

  beforeEach(() => {
    vi.mocked(fetchKnownUniversities).mockReset().mockResolvedValue(list)
    vi.mocked(deleteKnownUniversity).mockReset()
  })

  it('offers each country once, A to Z, then No country', async () => {
    const wrapper = await mountPage()
    expect(await appSelectLabels(wrapper, filter)).toEqual(['All countries', 'Australia', 'New Zealand', 'No country'])
  })

  it("shows the chosen country's alone, in any casing, and searches within it", async () => {
    const wrapper = await mountPage()

    await pickAppSelect(wrapper, filter, 'Australia')
    expect(names(wrapper)).toEqual(['Monash University', 'UNSW'])

    await wrapper.get('.data-table-search-input').setValue('unsw')
    expect(names(wrapper)).toEqual(['UNSW'])
    await wrapper.get('.data-table-search-input').setValue('auckland')
    expect(wrapper.text()).toContain('No university matches.')

    await wrapper.get('.data-table-search-input').setValue('')
    await pickAppSelect(wrapper, filter, 'No country')
    expect(names(wrapper)).toEqual(['USYD'])
  })

  it('goes back to All countries once no university has the chosen one', async () => {
    vi.mocked(deleteKnownUniversity).mockResolvedValue('ok')
    const wrapper = await mountPage()
    await pickAppSelect(wrapper, filter, 'New Zealand')
    expect(names(wrapper)).toEqual(['University of Auckland'])

    await wrapper.get('[data-test="university-delete-2"]').trigger('click')
    const dialog = wrapper.get('.admin-modal--confirm')
    await dialog.findAll('button').find((button) => button.text() === 'Delete')!.trigger('click')
    await flushPromises()

    expect(appSelectText(wrapper, filter)).toBe('All countries')
    expect(names(wrapper)).toEqual(['Monash University', 'UNSW', 'USYD'])
  })
})
