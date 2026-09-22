import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import MarkingCategories from '@/components/grading/MarkingCategories.vue'
import { fetchGroupCategories, saveGroupCategories } from '@/utils/gradingAPI'

vi.mock('@/utils/gradingAPI', () => ({
  fetchGroupCategories: vi.fn(),
  saveGroupCategories: vi.fn()
}))
const fetchMock = vi.mocked(fetchGroupCategories)
const saveMock = vi.mocked(saveGroupCategories)

const stored = (over: Partial<Parameters<typeof saveMock>[1]> = {}) => ({
  product_categories: ['Health and Medicine'],
  product_category_other: '',
  solution_category: 'Treatment',
  solution_category_other: '',
  ...over
})

const mountCategories = async (groupId = 7) => {
  const wrapper = mount(MarkingCategories, { props: { groupId } })
  await flushPromises()
  return wrapper
}

const lastStatus = (wrapper: Awaited<ReturnType<typeof mountCategories>>) =>
  wrapper.emitted('status')?.at(-1)?.[0] ?? null

beforeEach(() => {
  vi.useFakeTimers()
  fetchMock.mockReset()
  saveMock.mockReset()
  fetchMock.mockResolvedValue(stored())
  saveMock.mockImplementation(async (_id, data) => ({ ...data }))
})

afterEach(() => {
  vi.useRealTimers()
})

describe('loading', () => {
  it('shows the stored selections for the group', async () => {
    const wrapper = await mountCategories()
    expect(fetchMock).toHaveBeenCalledWith(7)
    const checked = wrapper
      .findAll('input[type="checkbox"]')
      .filter((c) => (c.element as HTMLInputElement).checked)
    expect(checked).toHaveLength(1)
    const radios = wrapper.findAll('input[type="radio"]')
    const picked = radios.filter((r) => (r.element as HTMLInputElement).checked)
    expect(picked).toHaveLength(1)
  })

  it('reports a failed load on the status line', async () => {
    fetchMock.mockRejectedValueOnce(new Error('not allowed'))
    const wrapper = await mountCategories()
    expect(lastStatus(wrapper)).toMatchObject({ error: true })
  })

  it('does not try to save changes made before the load finished', async () => {
    fetchMock.mockRejectedValueOnce(new Error('not allowed'))
    const wrapper = await mountCategories()
    await wrapper.find('input[type="checkbox"]').trigger('change')
    await vi.advanceTimersByTimeAsync(2000)
    expect(saveMock).not.toHaveBeenCalled()
  })
})

describe('autosave', () => {
  it('saves shortly after a checkbox change and says so briefly', async () => {
    const wrapper = await mountCategories()
    await wrapper.find('input[type="checkbox"]').trigger('change') // untick Health
    expect(saveMock).not.toHaveBeenCalled() // debounced, not instant

    await vi.advanceTimersByTimeAsync(600)
    await flushPromises()
    expect(saveMock).toHaveBeenCalledWith(7, expect.objectContaining({ product_categories: [] }))
    expect(lastStatus(wrapper)).toEqual({ text: 'Saved.', error: false })

    await vi.advanceTimersByTimeAsync(1500)
    expect(lastStatus(wrapper)).toBeNull() // the notice clears itself
  })

  it('collapses rapid changes into one save', async () => {
    const wrapper = await mountCategories()
    const boxes = wrapper.findAll('input[type="checkbox"]')
    await boxes[1]!.trigger('change')
    await vi.advanceTimersByTimeAsync(300)
    await boxes[2]!.trigger('change')
    await vi.advanceTimersByTimeAsync(600)
    await flushPromises()
    expect(saveMock).toHaveBeenCalledTimes(1)
  })

  it('picking a solution saves it', async () => {
    const wrapper = await mountCategories()
    await wrapper.find('input[type="radio"]').trigger('change') // Product/Device
    await vi.advanceTimersByTimeAsync(600)
    await flushPromises()
    expect(saveMock).toHaveBeenCalledWith(
      7,
      expect.objectContaining({ solution_category: 'Product/Device' })
    )
  })

  it('the Other text boxes stay disabled until Other is selected', async () => {
    const wrapper = await mountCategories()
    const otherProduct = wrapper.find('input[aria-label="Other product category"]')
    expect(otherProduct.attributes('disabled')).toBeDefined()

    const boxes = wrapper.findAll('input[type="checkbox"]')
    await boxes.at(-1)!.trigger('change') // tick Other
    expect(
      wrapper.find('input[aria-label="Other product category"]').attributes('disabled')
    ).toBeUndefined()

    await wrapper.find('input[aria-label="Other product category"]').setValue('Bioinformatics')
    await vi.advanceTimersByTimeAsync(600)
    await flushPromises()
    expect(saveMock).toHaveBeenLastCalledWith(
      7,
      expect.objectContaining({ product_category_other: 'Bioinformatics' })
    )
  })

  it('a failed save is reported and stays visible', async () => {
    saveMock.mockRejectedValueOnce(new Error('refused'))
    const wrapper = await mountCategories()
    await wrapper.find('input[type="checkbox"]').trigger('change')
    await vi.advanceTimersByTimeAsync(600)
    await flushPromises()
    expect(lastStatus(wrapper)).toMatchObject({ error: true })
    expect((lastStatus(wrapper) as { text: string }).text).toContain('Save failed:')
    await vi.advanceTimersByTimeAsync(5000)
    expect(lastStatus(wrapper)).toMatchObject({ error: true }) // no auto-clear on errors
  })
})

describe('switching groups', () => {
  it('reloads for the new group and clears the status line', async () => {
    const wrapper = await mountCategories()
    fetchMock.mockResolvedValueOnce(stored({ solution_category: 'Product/Device' }))
    await wrapper.setProps({ groupId: 8 })
    await flushPromises()
    expect(fetchMock).toHaveBeenLastCalledWith(8)
    expect(wrapper.emitted('status')!.some(([v]) => v === null)).toBe(true)
  })
})
