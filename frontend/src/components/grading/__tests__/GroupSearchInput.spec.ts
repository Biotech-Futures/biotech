import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import GroupSearchInput from '@/components/grading/GroupSearchInput.vue'
import { fetchFinalistCandidates } from '@/utils/gradingAPI'

vi.mock('@/utils/gradingAPI', () => ({
  fetchFinalistCandidates: vi.fn()
}))
const candidatesMock = vi.mocked(fetchFinalistCandidates)

// The component caches the group directory at module level, so every test
// works against the same dataset — the first successful mount fills it.
const row = (group_id: number, group_name: string) => ({
  group_id,
  group_name,
  is_late: false,
  late_by: null,
  marks: {},
  total: null,
  markers: [],
  criterion_markers: [],
  is_finalist: false,
  has_submission: true
})

const DIRECTORY = [row(1, 'Group 1'), row(12, 'Group 12'), row(3, 'Alpha Team')]

const mountInput = async (props: Record<string, unknown> = {}) => {
  const wrapper = mount(GroupSearchInput, {
    props: { modelValue: '', ...props }
  })
  await flushPromises()
  return wrapper
}

beforeEach(() => {
  candidatesMock.mockReset()
  candidatesMock.mockResolvedValue({ components: [], rows: DIRECTORY })
})

describe('typing and suggestions', () => {
  it('emits the typed value and opens matching suggestions', async () => {
    const wrapper = await mountInput()
    await wrapper.find('input').setValue('alpha')
    expect(wrapper.emitted('update:modelValue')!.at(-1)).toEqual(['alpha'])

    await wrapper.setProps({ modelValue: 'alpha' })
    await wrapper.find('input').trigger('focus')
    const options = wrapper.findAll('.group-search__option')
    expect(options).toHaveLength(1)
    expect(options[0]!.text()).toContain('Alpha Team')
    // Group ids are not exposed anywhere in the dropdown.
    expect(options[0]!.text()).not.toContain('ID')
  })

  it('matches digits against names only, never ids', async () => {
    const wrapper = await mountInput({ modelValue: '1' })
    await wrapper.find('input').trigger('focus')
    const names = wrapper.findAll('.group-search__name').map((n) => n.text())
    expect(names).toEqual(['Group 1', 'Group 12'])
  })

  it('shows nothing for a blank value and closes on blur', async () => {
    const wrapper = await mountInput({ modelValue: '' })
    await wrapper.find('input').trigger('focus')
    expect(wrapper.find('.group-search__list').exists()).toBe(false)

    await wrapper.setProps({ modelValue: 'group' })
    await wrapper.find('input').trigger('focus')
    expect(wrapper.find('.group-search__list').exists()).toBe(true)
    await wrapper.find('input').trigger('blur')
    expect(wrapper.find('.group-search__list').exists()).toBe(false)
  })

  it('can run without the dropdown for pages that filter their own table', async () => {
    const wrapper = await mountInput({ modelValue: 'group', showSuggestions: false })
    await wrapper.find('input').trigger('focus')
    expect(wrapper.find('.group-search__list').exists()).toBe(false)
  })

  it('picking a suggestion fills the input and announces the group', async () => {
    const wrapper = await mountInput({ modelValue: 'alpha' })
    await wrapper.find('input').trigger('focus')
    await wrapper.find('.group-search__option').trigger('mousedown')
    expect(wrapper.emitted('update:modelValue')!.at(-1)).toEqual(['Alpha Team'])
    expect(wrapper.emitted('select')!.at(-1)).toEqual([{ id: 3, name: 'Alpha Team' }])
  })
})

describe('resolveId', () => {
  const resolve = async (modelValue: string) => {
    const wrapper = await mountInput({ modelValue })
    return (wrapper.vm as unknown as { resolveId: () => number | null }).resolveId()
  }

  it('digits resolve through names, never as a literal id', async () => {
    // "12" matches the name "Group 12"; "3" matches no NAME even though
    // a group with id 3 exists — id lookup is gone.
    expect(await resolve('12')).toBe(12)
    expect(await resolve('3')).toBeNull()
  })

  it('rejects a blank or unmatched value', async () => {
    expect(await resolve('0')).toBeNull()
    expect(await resolve('   ')).toBeNull()
  })

  it('resolves a unique exact name, case-insensitively', async () => {
    expect(await resolve('ALPHA TEAM')).toBe(3)
  })

  it('resolves a unique partial name', async () => {
    expect(await resolve('alpha')).toBe(3)
  })

  it('refuses an ambiguous name rather than guessing', async () => {
    expect(await resolve('group')).toBeNull()
  })
})
