import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import { defineComponent, ref } from 'vue'

import AppDatePicker from '@/components/AppDatePicker.vue'
import SydneyDateTimeFields from '@/components/management/SydneyDateTimeFields.vue'
import { pickerText, pickerValue, setPicker } from '@/__tests__/appPicker'

// The fields as a page holds them: its value, bound both ways.
const mountFields = (start = '', props: Record<string, unknown> = {}) => {
  const value = ref(start)
  const Host = defineComponent({
    components: { SydneyDateTimeFields },
    setup: () => ({ value, props }),
    template: '<SydneyDateTimeFields v-model="value" date-label="Opening Date" v-bind="props" />'
  })
  return { wrapper: mount(Host), value }
}

const DATE = '.sydney-date-time__date'
const TIME = '.sydney-date-time__time'

describe('SydneyDateTimeFields', () => {
  it('shows its default time before there is a date, 23:59 unless the page gives another', () => {
    expect(pickerValue(mountFields().wrapper, TIME)).toBe('23:59')
    const { wrapper } = mountFields('', { defaultTime: '00:01' })
    expect(pickerValue(wrapper, TIME)).toBe('00:01')
    expect(pickerText(wrapper, DATE)).toBe('Select date')
    // No × to empty it.
    expect(wrapper.findComponent(AppDatePicker).props('clearable')).toBe(false)
  })

  it('a date picked takes the time shown, picked first or not', async () => {
    const { wrapper, value } = mountFields('', { defaultTime: '00:01' })
    await setPicker(wrapper, DATE, '2026-10-20')
    expect(value.value).toBe('2026-10-20T00:01')

    const other = mountFields()
    await setPicker(other.wrapper, TIME, '09:30')
    expect(other.value.value).toBe('')
    await setPicker(other.wrapper, DATE, '2026-10-20')
    expect(other.value.value).toBe('2026-10-20T09:30')
  })

  it('cleared, both empty and the time is the default again', async () => {
    const { wrapper, value } = mountFields('2026-10-20T09:30', { defaultTime: '00:01' })
    value.value = ''
    await wrapper.vm.$nextTick()
    expect(pickerText(wrapper, DATE)).toBe('Select date')
    expect(pickerValue(wrapper, TIME)).toBe('00:01')
  })

  it("names Sydney's clock on the day picked", async () => {
    const { wrapper } = mountFields('2026-07-27T23:59')
    const labels = () => wrapper.findAll('.sydney-date-time__field > span').map((label) => label.text())
    expect(labels()).toEqual(['Opening Date', 'Time (AEST)'])
    await setPicker(wrapper, DATE, '2026-12-01')
    expect(labels()).toEqual(['Opening Date', 'Time (AEDT)'])
  })
})
