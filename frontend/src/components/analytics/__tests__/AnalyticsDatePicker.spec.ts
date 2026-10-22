import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { nextTick } from 'vue'
import { mount, type VueWrapper } from '@vue/test-utils'
import AnalyticsDatePicker from '@/components/analytics/AnalyticsDatePicker.vue'

let wrapper: VueWrapper | undefined

// Synthetic jsdom events can occur in the same millisecond as Vue's listener
// attachment and be ignored by its timestamp guard. Model successive UI input
// with a deterministic clock rather than relying on machine execution speed.
beforeEach(() => { vi.useFakeTimers({ toFake: ['Date'] }) })
function nextInput() { vi.setSystemTime(Date.now() + 1) }

afterEach(() => {
  wrapper?.unmount()
  wrapper = undefined
  document.body.innerHTML = ''
  vi.useRealTimers()
})

async function openCalendar() {
  wrapper = mount(AnalyticsDatePicker, {
    attachTo: document.body,
    props: {
      modelValue: '2026-09-25',
      availableYears: [2026, 2027],
      label: 'Trend start date',
    },
  })
  nextInput()
  await wrapper.get('.analytics-date-picker-trigger').trigger('click')
  nextInput()
  return wrapper
}

describe('AnalyticsDatePicker accessible date names', () => {
  it('names every date with day, month and year while displaying only the day number', async () => {
    const calendar = await openCalendar()
    const dates = calendar.findAll('.analytics-date-picker-days button')
    expect(dates).toHaveLength(30)
    dates.forEach((button, index) => {
      expect(button.attributes('aria-label')).toBe(`${index + 1} September 2026`)
      expect(button.text()).toBe(String(index + 1))
    })
  })

  it('updates the date names when the month and year change', async () => {
    const calendar = await openCalendar()
    await calendar.get('select[aria-label="Select month"]').setValue('9')
    expect(calendar.get('button[aria-label="25 October 2026"]').text()).toBe('25')
    await calendar.get('select[aria-label="Select year"]').setValue('2027')
    expect(calendar.get('button[aria-label="25 October 2027"]').text()).toBe('25')
    expect(calendar.find('button[aria-label="25 September 2026"]').exists()).toBe(false)
    expect(calendar.emitted('update:modelValue')).toBeUndefined()
  })

  it('still emits a zero-padded ISO date and closes after selection', async () => {
    const calendar = await openCalendar()
    await calendar.get('button[aria-label="5 September 2026"]').trigger('click')
    expect(calendar.emitted('update:modelValue')).toEqual([['2026-09-05']])
    expect(calendar.find('.analytics-date-picker-popover').exists()).toBe(false)
  })

  it('keeps dates outside the bounds disabled and unselectable', async () => {
    const calendar = await openCalendar()
    await calendar.setProps({ min: '2026-09-10', max: '2026-09-25' })
    for (const day of [9, 26]) {
      const button = calendar.get<HTMLButtonElement>(`button[aria-label="${day} September 2026"]`)
      expect(button.element.disabled).toBe(true)
      await button.trigger('click')
    }
    expect(calendar.emitted('update:modelValue')).toBeUndefined()
    expect(calendar.find('.analytics-date-picker-popover').exists()).toBe(true)
    expect(calendar.get<HTMLButtonElement>('button[aria-label="10 September 2026"]').element.disabled).toBe(false)
  })
})

async function key(value: string) {
  nextInput()
  document.activeElement?.dispatchEvent(new KeyboardEvent('keydown', { key: value, bubbles: true, cancelable: true }))
  await nextTick()
  await nextTick()
}
function focused() { return document.activeElement?.getAttribute('data-date') }
async function reopen(props: Record<string, unknown>) {
  const calendar = await openCalendar()
  await key('Escape')
  await calendar.setProps(props)
  nextInput()
  await calendar.get('.analytics-date-picker-trigger').trigger('click')
  await nextTick()
  nextInput()
  return calendar
}

describe('AnalyticsDatePicker keyboard focus', () => {
  it('focuses the selection with one Tab target and selected gridcell', async () => {
    const calendar = await openCalendar()
    await nextTick()
    expect(focused()).toBe('2026-09-25')
    expect(calendar.findAll('[role="gridcell"][aria-selected="true"]')).toHaveLength(1)
    expect(calendar.get('[aria-selected="true"] button').attributes('data-date')).toBe('2026-09-25')
    expect(calendar.findAll('button[tabindex="0"]')).toHaveLength(1)
    expect(calendar.get('[role="dialog"]').attributes('aria-modal')).toBeUndefined()
  })

  it.each([
    ['ArrowLeft', '2026-09-24'], ['ArrowRight', '2026-09-26'],
    ['ArrowUp', '2026-09-18'], ['ArrowDown', '2026-10-02'],
    ['Home', '2026-09-20'], ['End', '2026-09-26'],
    ['PageUp', '2026-08-25'], ['PageDown', '2026-10-25'],
  ])('moves with %s without selecting', async (pressed, expected) => {
    const calendar = await openCalendar()
    await key(pressed)
    expect(focused()).toBe(expected)
    expect(calendar.findAll('button[tabindex="0"]')).toHaveLength(1)
    expect(calendar.emitted('update:modelValue')).toBeUndefined()
    expect(calendar.findAll('[aria-selected="true"]')).toHaveLength(expected.startsWith('2026-09') ? 1 : 0)
  })

  it.each([
    ['2026-09-30', 'ArrowRight', '2026-10-01'],
    ['2026-12-31', 'ArrowRight', '2027-01-01'],
    ['2027-01-01', 'ArrowLeft', '2026-12-31'],
    ['2026-01-31', 'PageDown', '2026-02-28'],
    ['2024-03-31', 'PageUp', '2024-02-29'],
  ])('navigates boundaries from %s', async (modelValue, pressed, expected) => {
    await reopen({ modelValue, availableYears: [2024, 2026, 2027] })
    await key(pressed)
    expect(focused()).toBe(expected)
  })

  it('restores trigger focus on Escape without emitting', async () => {
    const calendar = await openCalendar()
    await key('ArrowLeft')
    await key('Escape')
    expect(calendar.find('[role="dialog"]').exists()).toBe(false)
    expect(document.activeElement).toBe(calendar.get('.analytics-date-picker-trigger').element)
    expect(calendar.emitted('update:modelValue')).toBeUndefined()
  })

  it('preserves one mouse selection and restores focus', async () => {
    const calendar = await openCalendar()
    await calendar.get('button[data-date="2026-09-05"]').trigger('click')
    expect(calendar.emitted('update:modelValue')).toEqual([['2026-09-05']])
    expect(document.activeElement).toBe(calendar.get('.analytics-date-picker-trigger').element)
  })

  it('leaves Enter and Space to native activation without a second selection path', async () => {
    const calendar = await openCalendar()
    for (const pressed of ['Enter', ' ']) {
      const event = new KeyboardEvent('keydown', { key: pressed, bubbles: true, cancelable: true })
      document.activeElement?.dispatchEvent(event)
      expect(event.defaultPrevented).toBe(false)
    }
    // jsdom does not synthesise native button clicks from keyboard events.
    expect(calendar.emitted('update:modelValue')).toBeUndefined()
    await calendar.get('button[data-date="2026-09-25"]').trigger('click')
    expect(calendar.emitted('update:modelValue')).toEqual([['2026-09-25']])
  })

  it('clamps min/max and excludes disabled dates from Tab order', async () => {
    const calendar = await reopen({ min: '2026-09-24', max: '2026-09-26' })
    await key('ArrowUp')
    expect(focused()).toBe('2026-09-24')
    await key('ArrowLeft')
    expect(focused()).toBe('2026-09-24')
    await key('ArrowDown')
    expect(focused()).toBe('2026-09-26')
    await key('ArrowRight')
    expect(focused()).toBe('2026-09-26')
    expect(calendar.findAll('button:disabled[tabindex="0"]')).toHaveLength(0)
  })

  it('skips unavailable years', async () => {
    await reopen({ modelValue: '2026-12-31', availableYears: [2026, 2028] })
    await key('ArrowRight')
    expect(focused()).toBe('2028-01-01')
    await key('ArrowLeft')
    expect(focused()).toBe('2026-12-31')
  })

  it('falls back to today or its nearest permitted date', async () => {
    const today = new Date().toISOString().slice(0, 10)
    const year = Number(today.slice(0, 4))
    const calendar = await reopen({ modelValue: 'invalid', availableYears: [year, year + 1] })
    expect(focused()).toBe(today)
    await key('Escape')
    const later = new Date(`${today}T00:00:00Z`)
    later.setUTCDate(later.getUTCDate() + 10)
    const minimum = later.toISOString().slice(0, 10)
    await calendar.setProps({ min: minimum })
    await calendar.get('.analytics-date-picker-trigger').trigger('click')
    await nextTick()
    expect(focused()).toBe(minimum)
  })

  it('focuses a control when no dates are available', async () => {
    const calendar = await reopen({ availableYears: [] })
    expect(document.activeElement).toBe(calendar.get('select[aria-label="Select month"]').element)
    expect(calendar.findAll('button[tabindex="0"]')).toHaveLength(0)
  })

  it('keeps focus and native arrow handling in month controls', async () => {
    const calendar = await openCalendar()
    const month = calendar.get<HTMLSelectElement>('select[aria-label="Select month"]')
    month.element.focus()
    await month.setValue('9')
    expect(document.activeElement).toBe(month.element)
    expect(calendar.get('button[tabindex="0"]').attributes('data-date')).toBe('2026-10-25')
    const event = new KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true, cancelable: true })
    month.element.dispatchEvent(event)
    expect(event.defaultPrevented).toBe(false)
    expect(calendar.emitted('update:modelValue')).toBeUndefined()
  })

  it('allows browsing a fully disabled month without emitting or stealing focus', async () => {
    const calendar = await reopen({ min: '2026-09-01', max: '2026-09-30' })
    const month = calendar.get<HTMLSelectElement>('select[aria-label="Select month"]')
    month.element.focus()
    await month.setValue('10')
    expect(document.activeElement).toBe(month.element)
    expect(calendar.findAll('button[tabindex="0"]')).toHaveLength(0)
    expect(calendar.emitted('update:modelValue')).toBeUndefined()
  })

  it('repairs focus when constraints change', async () => {
    const calendar = await openCalendar()
    await calendar.setProps({ max: '2026-09-20' })
    await nextTick()
    expect(focused()).toBe('2026-09-20')
  })

  it('closes when focus leaves without stealing outside focus', async () => {
    const calendar = await openCalendar()
    const outside = document.createElement('button')
    document.body.append(outside)
    outside.focus()
    await nextTick()
    expect(calendar.find('[role="dialog"]').exists()).toBe(false)
    expect(document.activeElement).toBe(outside)
  })

  it('updates selection semantics and date focus when the controlled value changes', async () => {
    const calendar = await openCalendar()
    await calendar.setProps({ modelValue: '2026-09-18' })
    await nextTick()
    expect(focused()).toBe('2026-09-18')
    expect(calendar.get('[aria-selected="true"] button').attributes('data-date')).toBe('2026-09-18')
    expect(calendar.emitted('update:modelValue')).toBeUndefined()
  })

  it('preserves outside pointer focus and restores only when it would be lost', async () => {
    const calendar = await openCalendar()
    const outside = document.createElement('button')
    document.body.append(outside)
    outside.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }))
    outside.focus() // Simulate the browser default action, which jsdom does not perform.
    await nextTick()
    expect(document.activeElement).toBe(outside)
    expect(calendar.find('[role="dialog"]').exists()).toBe(false)
    await calendar.get('.analytics-date-picker-trigger').trigger('click')
    await nextTick()
    document.body.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }))
    await nextTick()
    expect(document.activeElement).toBe(calendar.get('.analytics-date-picker-trigger').element)
  })

  it('keeps Home and End within a partially disabled week', async () => {
    await reopen({ min: '2026-09-24', max: '2026-09-25' })
    await key('Home')
    expect(focused()).toBe('2026-09-24')
    await key('End')
    expect(focused()).toBe('2026-09-25')
  })

  it('cancels scheduled focus when the calendar closes before rendering', async () => {
    const calendar = await openCalendar()
    await key('Escape')
    const trigger = calendar.get<HTMLButtonElement>('.analytics-date-picker-trigger')
    trigger.element.click()
    trigger.element.click()
    await nextTick()
    expect(calendar.find('[role="dialog"]').exists()).toBe(false)
    expect(document.activeElement).toBe(trigger.element)
  })

  it('keeps multiple instances independent', async () => {
    wrapper = mount({ components: { AnalyticsDatePicker }, template: `
      <div><AnalyticsDatePicker model-value="2026-09-25" :available-years="[2026]" label="Start date" />
      <AnalyticsDatePicker model-value="2027-01-10" :available-years="[2027]" label="End date" /></div>` },
    { attachTo: document.body })
    const [first, second] = wrapper.findAllComponents(AnalyticsDatePicker)
    await first!.get('.analytics-date-picker-trigger').trigger('click')
    await nextTick()
    expect(focused()).toBe('2026-09-25')
    await second!.get('.analytics-date-picker-trigger').trigger('click')
    await nextTick()
    expect(first!.get('.analytics-date-picker-trigger').attributes('aria-controls'))
      .not.toBe(second!.get('.analytics-date-picker-trigger').attributes('aria-controls'))
    expect(focused()).toBe('2027-01-10')
    await key('Escape')
    expect(document.activeElement).toBe(second!.get('.analytics-date-picker-trigger').element)
    expect(first!.emitted('update:modelValue')).toBeUndefined()
  })
})
