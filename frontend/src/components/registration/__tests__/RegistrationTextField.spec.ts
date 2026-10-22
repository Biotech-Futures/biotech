import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import RegistrationTextField from '../RegistrationTextField.vue'

const withSuggestions = (modelValue = '') =>
  mount(RegistrationTextField, {
    props: {
      id: 'member-school',
      modelValue,
      label: 'School',
      autocomplete: 'organization',
      suggestions: ['Test High', 'Cardinal College', 'University of Sydney'],
      'onUpdate:modelValue': () => {},
    },
  })

const shown = (wrapper: ReturnType<typeof withSuggestions>) =>
  wrapper.findAll('.registration-field__suggestion').map((option) => option.text())

describe('RegistrationTextField suggestions', () => {
  it('drops the suggestions down on focus, without the browser filling it in', async () => {
    const wrapper = withSuggestions()
    const input = wrapper.get('input')
    expect(input.attributes('autocomplete')).toBe('off')
    expect(wrapper.find('[role="listbox"]').exists()).toBe(false)

    await input.trigger('focus')
    expect(shown(wrapper)).toEqual(['Test High', 'Cardinal College', 'University of Sydney'])

    await input.trigger('blur')
    expect(wrapper.find('[role="listbox"]').exists()).toBe(false)
  })

  it('narrows to those holding what is typed, and picks one by click or the keys', async () => {
    const wrapper = withSuggestions('uni')
    const input = wrapper.get('input')
    await input.trigger('focus')
    expect(shown(wrapper)).toEqual(['University of Sydney'])

    await wrapper.get('.registration-field__suggestion').trigger('mousedown')
    expect(wrapper.emitted('update:modelValue')!.at(-1)).toEqual(['University of Sydney'])

    await input.trigger('focus')
    await input.trigger('keydown', { key: 'ArrowDown' })
    expect(wrapper.get('.registration-field__suggestion').classes()).toContain('is-active')
    await input.trigger('keydown', { key: 'Enter' })
    expect(wrapper.emitted('update:modelValue')!.length).toBe(2)
  })

  it('has no list without suggestions', async () => {
    const wrapper = mount(RegistrationTextField, {
      props: { id: 'school', modelValue: '', label: 'School', autocomplete: 'organization' },
    })
    await wrapper.get('input').trigger('focus')
    expect(wrapper.get('input').attributes('autocomplete')).toBe('organization')
    expect(wrapper.find('[role="listbox"]').exists()).toBe(false)
  })
})
