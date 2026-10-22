// A date or time picker (AppDateTimePicker, and AppDatePicker and
// AppTimePicker built on it) in a spec: what it holds, what its box shows,
// and setting it as picking in its panel (or its ×) would.
import { flushPromises, type VueWrapper } from '@vue/test-utils'
import AppDateTimePicker from '@/components/AppDateTimePicker.vue'

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Root = VueWrapper<any>

/** The picker whose box is, holds or is within what `selector` finds. */
const pickerAt = (root: Root, selector: string) => {
  const found = root.find(selector)
  if (!found.exists()) throw new Error(`No picker at ${selector}`)
  const element = found.element as HTMLElement
  const box = element.closest('.app-picker') ?? element.querySelector('.app-picker')
  if (!box) throw new Error(`${selector} is not a date or time picker`)
  const picker = root.findAllComponents(AppDateTimePicker).find((candidate) => candidate.element === box)
  if (!picker) throw new Error(`No picker component at ${selector}`)
  return picker
}

/** What it holds: "YYYY-MM-DDTHH:MM", "YYYY-MM-DD" or "HH:MM"; '' for none. */
export function pickerValue(root: Root, selector: string): string {
  return String(pickerAt(root, selector).props('modelValue') ?? '')
}

/** What its box shows: the date or time picked, or its placeholder. */
export function pickerText(root: Root, selector: string): string {
  return pickerAt(root, selector).find('[data-test="app-picker-field"]').text()
}

/** The earliest it can be, as the page gave it. */
export function pickerMin(root: Root, selector: string): string {
  return String(pickerAt(root, selector).props('min') ?? '')
}

/** Sets it to `value` ('' empties it), as picking it does. */
export async function setPicker(root: Root, selector: string, value: string): Promise<void> {
  const picker = pickerAt(root, selector)
  picker.vm.$emit('update:modelValue', value)
  picker.vm.$emit('change', value)
  await flushPromises()
}
