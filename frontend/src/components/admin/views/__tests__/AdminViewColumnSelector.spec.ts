import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import AdminViewColumnSelector from '../AdminViewColumnSelector.vue'

const mountSelector = (modelValue: string[] = []) =>
  mount(AdminViewColumnSelector, { props: { modelValue } })

describe('AdminViewColumnSelector.vue', () => {
  it('offers "Group Number" and "Number of Groups" as two different fields', () => {
    const wrapper = mountSelector()
    const labels = wrapper.findAll('.column-selector__name').map((el) => el.text())

    expect(labels).toContain('Group Number')
    expect(labels).toContain('Number of Groups')
  })

  it('toggles "Group Number" on and off', async () => {
    const wrapper = mountSelector(['name'])
    const groupNumberCheckbox = () =>
      wrapper
        .findAll('.column-selector__checkbox-label')
        .find((label) => label.text() === 'Group Number')!
        .find('input')

    expect(groupNumberCheckbox()).toBeDefined()
    await groupNumberCheckbox().trigger('change')
    expect(wrapper.emitted('update:modelValue')?.at(-1)).toEqual([['name', 'group_number']])

    // The parent feeds the new selection back in, as v-model does.
    await wrapper.setProps({ modelValue: ['name', 'group_number'] })
    await groupNumberCheckbox().trigger('change')
    expect(wrapper.emitted('update:modelValue')?.at(-1)).toEqual([['name']])
  })

  it('offers the role-specific columns', () => {
    const wrapper = mountSelector()
    const labels = wrapper.findAll('.column-selector__name').map((el) => el.text())

    expect(labels).toContain('Pronouns')
    expect(labels).toContain('Group Capacity')
    expect(labels).toContain('Mentor Background')
    expect(labels).toContain('Mentor Year of Study')
    expect(labels).toContain('Mentor Field of Study')
    expect(labels).toContain('Supervisor Email')
    expect(labels).toContain('Guardian Email')
    expect(labels).toContain('Guardian Permission')
  })

  it('selects a role-specific column', async () => {
    const wrapper = mountSelector(['name'])
    const guardianEmailCheckbox = () =>
      wrapper
        .findAll('.column-selector__checkbox-label')
        .find((label) => label.text() === 'Guardian Email')!
        .find('input')

    await guardianEmailCheckbox().trigger('change')
    expect(wrapper.emitted('update:modelValue')?.at(-1)).toEqual([['name', 'guardian_email']])
  })
})
