import { beforeEach, describe, expect, it, vi } from 'vitest'
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

type Wrapper = Awaited<ReturnType<typeof mountCategories>>

const lastStatus = (wrapper: Wrapper) => wrapper.emitted('status')?.at(-1)?.[0] ?? null

// The page reads isDirty and calls save() through a template ref.
const exposed = (wrapper: Wrapper) =>
  wrapper.vm as unknown as { isDirty: boolean; save: () => Promise<void> }

beforeEach(() => {
  fetchMock.mockReset()
  saveMock.mockReset()
  fetchMock.mockResolvedValue(stored())
  saveMock.mockImplementation(async (_id, data) => ({ ...data }))
})

describe('loading', () => {
  it('shows the stored selections for the group, with nothing unsaved', async () => {
    const wrapper = await mountCategories()
    expect(fetchMock).toHaveBeenCalledWith(7)
    const checked = wrapper
      .findAll('input[type="checkbox"]')
      .filter((c) => (c.element as HTMLInputElement).checked)
    expect(checked).toHaveLength(1)
    const radios = wrapper.findAll('input[type="radio"]')
    const picked = radios.filter((r) => (r.element as HTMLInputElement).checked)
    expect(picked).toHaveLength(1)
    expect(exposed(wrapper).isDirty).toBe(false)
  })

  it('reports a failed load', async () => {
    fetchMock.mockRejectedValueOnce(new Error('not allowed'))
    const wrapper = await mountCategories()
    expect(lastStatus(wrapper)).toEqual({ text: 'Category load failed: not allowed', error: true })
  })

  it('changes made after a failed load never count as unsaved', async () => {
    fetchMock.mockRejectedValueOnce(new Error('not allowed'))
    const wrapper = await mountCategories()
    await wrapper.find('input[type="checkbox"]').trigger('change')
    expect(exposed(wrapper).isDirty).toBe(false)
    await exposed(wrapper).save()
    expect(saveMock).not.toHaveBeenCalled()
  })
})

describe('saving with the Save button', () => {
  it('a change is held as unsaved, never saved on its own', async () => {
    const wrapper = await mountCategories()
    await wrapper.find('input[type="checkbox"]').trigger('change') // untick Health
    await flushPromises()
    expect(saveMock).not.toHaveBeenCalled()
    expect(exposed(wrapper).isDirty).toBe(true)
  })

  it('save() stores the selections and clears the unsaved state', async () => {
    const wrapper = await mountCategories()
    await wrapper.find('input[type="radio"]').trigger('change') // Product/Device
    await exposed(wrapper).save()
    expect(saveMock).toHaveBeenCalledWith(
      7,
      expect.objectContaining({ solution_category: 'Product/Device' })
    )
    expect(exposed(wrapper).isDirty).toBe(false)
  })

  it('save() does nothing when nothing changed', async () => {
    const wrapper = await mountCategories()
    await exposed(wrapper).save()
    expect(saveMock).not.toHaveBeenCalled()
  })

  it('undoing a change counts as clean again', async () => {
    const wrapper = await mountCategories()
    const box = wrapper.find('input[type="checkbox"]')
    await box.trigger('change') // untick Health
    await box.trigger('change') // tick it back
    expect(exposed(wrapper).isDirty).toBe(false)
  })

  it('the Other text boxes stay disabled until Other is selected, and save their text', async () => {
    const wrapper = await mountCategories()
    const otherProduct = wrapper.find('input[aria-label="Other product category"]')
    expect(otherProduct.attributes('disabled')).toBeDefined()

    const boxes = wrapper.findAll('input[type="checkbox"]')
    await boxes.at(-1)!.trigger('change') // tick Other
    expect(
      wrapper.find('input[aria-label="Other product category"]').attributes('disabled')
    ).toBeUndefined()

    await wrapper.find('input[aria-label="Other product category"]').setValue('Bioinformatics')
    expect(saveMock).not.toHaveBeenCalled()
    await exposed(wrapper).save()
    expect(saveMock).toHaveBeenLastCalledWith(
      7,
      expect.objectContaining({ product_category_other: 'Bioinformatics' })
    )
  })

  it('a failed save throws for the page and keeps the edits unsaved', async () => {
    saveMock.mockRejectedValueOnce(new Error('refused'))
    const wrapper = await mountCategories()
    await wrapper.find('input[type="checkbox"]').trigger('change')
    await expect(exposed(wrapper).save()).rejects.toThrow('refused')
    expect(exposed(wrapper).isDirty).toBe(true)
  })
})

describe('switching groups', () => {
  it('reloads for the new group and clears any load error', async () => {
    const wrapper = await mountCategories()
    fetchMock.mockResolvedValueOnce(stored({ solution_category: 'Product/Device' }))
    await wrapper.setProps({ groupId: 8 })
    await flushPromises()
    expect(fetchMock).toHaveBeenLastCalledWith(8)
    expect(wrapper.emitted('status')!.some(([v]) => v === null)).toBe(true)
    expect(exposed(wrapper).isDirty).toBe(false)
  })
})
