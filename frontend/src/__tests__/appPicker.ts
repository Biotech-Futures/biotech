// A date or time picker (AppDateTimePicker, and AppDatePicker and
// AppTimePicker built on it) in a spec: what it holds, what its box shows,
// and setting it as picking in its panel (or its ×) would.
import { flushPromises, type VueWrapper } from '@vue/test-utils'
import AppDateTimePicker from '@/components/AppDateTimePicker.vue'
import SydneyDateTimeFields from '@/components/management/SydneyDateTimeFields.vue'

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

/** The latest it can be, as the page gave it. */
export function pickerMax(root: Root, selector: string): string {
  return String(pickerAt(root, selector).props('max') ?? '')
}

/** Sets it to `value` ('' empties it), as picking it does. */
export async function setPicker(root: Root, selector: string, value: string): Promise<void> {
  const picker = pickerAt(root, selector)
  picker.vm.$emit('update:modelValue', value)
  picker.vm.$emit('change', value)
  await flushPromises()
}

/** A Management date and time (SydneyDateTimeFields) at `selector`. */
const dateTimeFieldsAt = (root: Root, selector: string) => {
  const found = root.find(selector)
  if (!found.exists()) throw new Error(`No date and time at ${selector}`)
  const fields = root.findAllComponents(SydneyDateTimeFields).find((candidate) => candidate.element === found.element)
  if (!fields) throw new Error(`${selector} is not a Management date and time`)
  return fields
}

/** What it holds: Sydney's "YYYY-MM-DDTHH:MM"; '' for none. */
export function dateTimeFieldsValue(root: Root, selector: string): string {
  return String(dateTimeFieldsAt(root, selector).props('modelValue') ?? '')
}

/** The earliest or latest it can be, as the page gave it. */
export function dateTimeFieldsLimit(root: Root, selector: string, limit: 'min' | 'max'): string {
  return String(dateTimeFieldsAt(root, selector).props(limit) ?? '')
}

/** Picks its date, then its time, as an admin does ('' empties it). */
export async function setDateTimeFields(root: Root, selector: string, value: string): Promise<void> {
  await setPicker(root, `${selector} .sydney-date-time__date`, value.slice(0, 10))
  if (value) await setPicker(root, `${selector} .sydney-date-time__time`, value.slice(11, 16))
}
