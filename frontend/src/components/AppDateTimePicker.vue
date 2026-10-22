<template>
  <div
    ref="boxRef"
    v-bind="boxAttrs"
    class="app-picker"
    :class="{ 'is-open': open, 'is-disabled': disabled, 'has-clear': showClear, 'is-large': size === 'large' }"
    @mousedown.prevent
    @click="onBoxClick"
  >
    <!-- The app's one date and time picker: a date and a time
         ("YYYY-MM-DDTHH:MM", as a datetime-local input has it, no time
         zone), a date alone ("YYYY-MM-DD", mode date: AppDatePicker) or a
         time alone ("HH:MM", mode time: AppTimePicker). This is its box: the
         page's classes, styles and data-test land here, so it's drawn as the
         page's other boxes are. The month and the hours and minutes open side
         by side in a panel over the page, where nothing can cut them off.
         Their sizes are the --picker settings in main.css. -->
    <button
      :id="id"
      ref="fieldRef"
      v-bind="fieldAttrs"
      type="button"
      class="app-picker__field"
      :class="{ 'is-empty': !shown }"
      aria-haspopup="dialog"
      :aria-expanded="open"
      :aria-controls="panelId"
      :aria-required="required || undefined"
      :disabled="disabled"
      data-test="app-picker-field"
      @keydown="onKeydown"
      @blur="close"
    >
      {{ shown || placeholderText }}
    </button>
    <!-- Clearable: a × that empties it, while there's something to empty. -->
    <button
      v-if="showClear"
      type="button"
      class="app-picker__clear"
      aria-label="Clear"
      data-test="app-picker-clear"
      @click.stop="clear"
    >
      <i class="fas fa-xmark" aria-hidden="true"></i>
    </button>
    <i :class="['far', hasDate ? 'fa-calendar' : 'fa-clock', 'app-picker__icon']" aria-hidden="true"></i>
    <!-- Keeps a form from saving without one when it's needed, or with one
         out of range, as the browser's own date and time fields do. -->
    <input
      v-if="required || min || max"
      ref="validatorRef"
      class="app-picker__validator"
      tabindex="-1"
      aria-hidden="true"
      :value="modelValue || ''"
      @focus="fieldRef?.focus()"
    />
    <Teleport to="body">
      <div
        v-if="open"
        :id="panelId"
        ref="panelRef"
        class="app-picker__panel"
        role="dialog"
        :aria-label="panelLabel"
        :style="panelStyle"
        @mousedown.prevent.stop
        @click.stop
      >
        <!-- The month: a week to a row, from Monday. -->
        <div v-if="hasDate" class="app-picker__calendar">
          <div class="app-picker__top">
            <button type="button" class="app-picker__nav" aria-label="Previous month" @click="showMonth(-1)">
              <i class="fas fa-chevron-left" aria-hidden="true"></i>
            </button>
            <span class="app-picker__month">{{ MONTHS[view.month] }} {{ view.year }}</span>
            <button type="button" class="app-picker__nav" aria-label="Next month" @click="showMonth(1)">
              <i class="fas fa-chevron-right" aria-hidden="true"></i>
            </button>
          </div>
          <div class="app-picker__weekdays" aria-hidden="true">
            <span v-for="day in WEEKDAYS" :key="day">{{ day }}</span>
          </div>
          <div class="app-picker__days">
            <button
              v-for="cell in cells"
              :key="cell.date"
              type="button"
              tabindex="-1"
              class="app-picker__day"
              :class="{
                'is-other': !cell.inMonth,
                'is-today': cell.date === today,
                'is-selected': cell.date === parts.date,
                'is-active': column === 'date' && cell.date === activeDate
              }"
              :aria-label="longDate(cell.date)"
              :aria-pressed="cell.date === parts.date"
              :disabled="dayOutside(cell.date)"
              :data-date="cell.date"
              @click="pickDate(cell.date)"
            >
              {{ cell.day }}
            </button>
          </div>
        </div>

        <!-- The time: hours and minutes (with a date, once there is one). -->
        <div v-if="hasTime" class="app-picker__time" :class="{ 'has-date': hasDate, 'is-waiting': !canPickTime }">
          <div class="app-picker__column">
            <span class="app-picker__heading">Hour</span>
            <ul ref="hourListRef" class="app-picker__list" role="listbox" aria-label="Hour">
              <li
                v-for="(hour, index) in HOURS"
                :key="hour"
                role="option"
                class="app-picker__option"
                :class="{
                  'is-selected': hour === parts.hour,
                  'is-active': column === 'hour' && index === activeHour,
                  'is-disabled': hourOutside(hour)
                }"
                :aria-selected="hour === parts.hour"
                :aria-disabled="!canPickTime || hourOutside(hour) || undefined"
                :data-hour="hour"
                @click="pickHour(hour)"
              >
                {{ hour }}
              </li>
            </ul>
          </div>
          <span class="app-picker__colon" aria-hidden="true">:</span>
          <div class="app-picker__column">
            <span class="app-picker__heading">Min</span>
            <ul ref="minuteListRef" class="app-picker__list" role="listbox" aria-label="Minutes">
              <li
                v-for="(minute, index) in minutes"
                :key="minute"
                role="option"
                class="app-picker__option"
                :class="{
                  'is-selected': Boolean(parts.hour) && minute === parts.minute,
                  'is-active': column === 'minute' && index === activeMinute,
                  'is-disabled': !parts.hour || minuteOutside(minute)
                }"
                :aria-selected="Boolean(parts.hour) && minute === parts.minute"
                :aria-disabled="!canPickTime || !parts.hour || minuteOutside(minute) || undefined"
                :data-minute="minute"
                @click="pickMinute(minute)"
              >
                {{ minute }}
              </li>
            </ul>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script lang="ts">
// Each panel its own id, across every app on the page.
let lastPanelId = 0
const nextPanelId = () => `app-picker-${++lastPanelId}`

export type PickerMode = 'datetime' | 'date' | 'time'

/** The minutes each kind offers, in steps of this many: every minute with a
 *  date (deadlines at 23:59), every 5 for a time alone (weekly availability,
 *  presentation times). A page can give its own with ``step``. */
export const MINUTE_STEPS: Record<PickerMode, number> = { datetime: 1, date: 1, time: 5 }
</script>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, reactive, ref, useAttrs, watch, watchEffect } from 'vue'

defineOptions({ inheritAttrs: false })

const props = withDefaults(
  defineProps<{
    /** "YYYY-MM-DDTHH:MM", "YYYY-MM-DD" or "HH:MM" as its mode has it;
     *  empty (or null) for none yet. */
    modelValue?: string | null
    /** A date and a time, a date alone, or a time alone. */
    mode?: PickerMode
    id?: string
    /** Shown while it's empty: by default "Select date and time", "Select
     *  date" or "--:--". */
    placeholder?: string
    disabled?: boolean
    /** A × in the box, to empty it. */
    clearable?: boolean
    /** A form with it can't be saved while it's empty. */
    required?: boolean
    /** The earliest and latest it can be, written as its value is (a date
     *  alone limits only the days). */
    min?: string | null
    max?: string | null
    /** The time a date picked into an empty box starts at (Management's
     *  pages give 23:59, the end of the day). */
    defaultTime?: string
    /** The minutes offered, in steps of this many: MINUTE_STEPS by default. */
    step?: number
    /** Small, as tall as a select (the default); large, as tall as the
     *  page's text boxes beside it, as AppSelect's sizes. */
    size?: 'small' | 'large'
  }>(),
  {
    modelValue: '',
    mode: 'datetime',
    id: undefined,
    placeholder: undefined,
    disabled: false,
    clearable: false,
    required: false,
    min: undefined,
    max: undefined,
    defaultTime: '00:00',
    step: undefined,
    size: 'small'
  }
)

const emit = defineEmits<{
  'update:modelValue': [value: string]
  /** After something is picked or cleared, as an input's change event. */
  change: [value: string]
}>()

// The page's classes, styles and data-test draw and name the box; the rest
// (aria-label, title) go to the field.
const attrs = useAttrs()
const isBoxAttr = (key: string) => key === 'class' || key === 'style' || key.startsWith('data-')
const boxAttrs = computed(() => Object.fromEntries(Object.entries(attrs).filter(([key]) => isBoxAttr(key))))
const fieldAttrs = computed(() => Object.fromEntries(Object.entries(attrs).filter(([key]) => !isBoxAttr(key))))

const panelId = nextPanelId()
const boxRef = ref<HTMLElement | null>(null)
const fieldRef = ref<HTMLButtonElement | null>(null)
const panelRef = ref<HTMLElement | null>(null)
const validatorRef = ref<HTMLInputElement | null>(null)
const hourListRef = ref<HTMLElement | null>(null)
const minuteListRef = ref<HTMLElement | null>(null)
const open = ref(false)

const hasDate = computed(() => props.mode !== 'time')
const hasTime = computed(() => props.mode !== 'date')

const MONTHS = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December'
]
const WEEKDAYS = ['Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa', 'Su']
const twoDigits = (count: number) => String(count).padStart(2, '0')
const HOURS = Array.from({ length: 24 }, (_, hour) => twoDigits(hour))

// --- dates, as "YYYY-MM-DD" ------------------------------------------------------

// Counted in UTC, so a day is always a day, whatever the clocks do.
const dateOf = (year: number, month: number, day: number) =>
  new Date(Date.UTC(year, month, day)).toISOString().slice(0, 10)
const addDays = (date: string, days: number) => {
  const [year, month, day] = date.split('-').map(Number)
  return dateOf(year!, month! - 1, day! + days)
}
const now = new Date()
const today = dateOf(now.getFullYear(), now.getMonth(), now.getDate())

/** "15 October 2026", for a day's name. */
const longDate = (date: string) => {
  const [year, month, day] = date.split('-').map(Number)
  return `${day} ${MONTHS[month! - 1]} ${year}`
}

/** "15 Oct 2026". */
const shortDate = (date: string) => {
  const [year, month, day] = date.split('-').map(Number)
  return `${day} ${MONTHS[month! - 1]!.slice(0, 3)} ${year}`
}

// --- the value: its date, hour and minutes ------------------------------------------

type Parts = { date: string; hour: string; minute: string }
const NONE: Parts = { date: '', hour: '', minute: '' }

/** A value of this mode as its parts; seconds, if any came with it, are dropped. */
const partsOf = (value: string | null | undefined): Parts => {
  const text = value || ''
  if (props.mode === 'date') {
    const match = /^(\d{4}-\d{2}-\d{2})/.exec(text)
    return match ? { date: match[1]!, hour: '', minute: '' } : NONE
  }
  if (props.mode === 'time') {
    const match = /^(\d{1,2}):(\d{2})/.exec(text)
    return match ? { date: '', hour: twoDigits(Number(match[1])), minute: match[2]! } : NONE
  }
  const match = /^(\d{4}-\d{2}-\d{2})T(\d{2}):(\d{2})/.exec(text)
  return match ? { date: match[1]!, hour: match[2]!, minute: match[3]! } : NONE
}

/** Parts put back together as this mode writes them. */
const valueOf = ({ date, hour, minute }: Parts) =>
  props.mode === 'date' ? date : props.mode === 'time' ? `${hour}:${minute}` : `${date}T${hour}:${minute}`

/** Parts as the box shows them: "15 Oct 2026, 23:59", "15 Oct 2026" or "23:59". */
const textOf = ({ date, hour, minute }: Parts) =>
  props.mode === 'date' ? shortDate(date) : props.mode === 'time' ? `${hour}:${minute}` : `${shortDate(date)}, ${hour}:${minute}`

const parts = computed(() => partsOf(props.modelValue))
const hasValue = computed(() => Boolean(hasDate.value ? parts.value.date : parts.value.hour))
const shown = computed(() => (hasValue.value ? textOf(parts.value) : ''))

const placeholderText = computed(
  () => props.placeholder ?? { datetime: 'Select date and time', date: 'Select date', time: '--:--' }[props.mode]
)
const panelLabel = computed(
  () => ({ datetime: 'Pick a date and time', date: 'Pick a date', time: 'Pick a time' })[props.mode]
)

// Every step's minutes, and only those: a time saved between them shows in
// the box, with no minute picked in the list.
const minutes = computed(() => {
  const step = Math.max(1, Math.min(60, Math.floor(props.step ?? MINUTE_STEPS[props.mode])))
  return Array.from({ length: Math.ceil(60 / step) }, (_, index) => twoDigits(index * step))
})

// --- the earliest and latest it can be ------------------------------------------------

const minParts = computed(() => partsOf(props.min))
const maxParts = computed(() => partsOf(props.max))
const hasMin = computed(() => Boolean(hasDate.value ? minParts.value.date : minParts.value.hour))
const hasMax = computed(() => Boolean(hasDate.value ? maxParts.value.date : maxParts.value.hour))

/** A day before the earliest or after the latest. */
const dayOutside = (date: string) =>
  (hasMin.value && date < minParts.value.date) || (hasMax.value && date > maxParts.value.date)

/** A time on the day picked (or a time alone) before the earliest or after the latest. */
const timeOutside = (hour: string, minute: string) => {
  const value = valueOf({ date: parts.value.date, hour, minute })
  return (hasMin.value && value < valueOf(minParts.value)) || (hasMax.value && value > valueOf(maxParts.value))
}
// An hour none of whose minutes can be picked.
const hourOutside = (hour: string) => timeOutside(hour, '59') && timeOutside(hour, '00')
const minuteOutside = (minute: string) => Boolean(parts.value.hour) && timeOutside(parts.value.hour, minute)

// What a form saving it is told: nothing, or why it can't be saved yet.
const invalidReason = computed(() => {
  if (!hasValue.value) return props.required ? { datetime: 'Pick a date and time.', date: 'Pick a date.', time: 'Pick a time.' }[props.mode] : ''
  const value = valueOf(parts.value)
  if (hasMin.value && value < valueOf(minParts.value)) return `Pick one on or after ${textOf(minParts.value)}.`
  if (hasMax.value && value > valueOf(maxParts.value)) return `Pick one on or before ${textOf(maxParts.value)}.`
  return ''
})

watchEffect(() => validatorRef.value?.setCustomValidity?.(invalidReason.value))

// --- the month shown ----------------------------------------------------------------

const view = reactive({ year: now.getFullYear(), month: now.getMonth() })

const showMonthOf = (date: string) => {
  const [year, month] = date.split('-').map(Number)
  view.year = year!
  view.month = month! - 1
}

const showMonth = (by: number) => {
  const first = new Date(Date.UTC(view.year, view.month + by, 1))
  view.year = first.getUTCFullYear()
  view.month = first.getUTCMonth()
}

// Six weeks from the Monday on or before the 1st, so the month never jumps
// in height.
const cells = computed(() => {
  const first = dateOf(view.year, view.month, 1)
  const weekday = (new Date(`${first}T00:00:00Z`).getUTCDay() + 6) % 7
  const start = addDays(first, -weekday)
  return Array.from({ length: 42 }, (_, index) => {
    const date = addDays(start, index)
    return { date, day: Number(date.slice(8)), inMonth: Number(date.slice(5, 7)) === view.month + 1 }
  })
})

// --- where the keyboard is: the month, the hours or the minutes ----------------------

const column = ref<'date' | 'hour' | 'minute'>('date')
const activeDate = ref(today)
const activeHour = ref(0)
const activeMinute = ref(0)

// With a date, the time waits for one.
const canPickTime = computed(() => !hasDate.value || Boolean(parts.value.date))

// The row in the middle of its list, so the ones either side show too.
const centre = (list: HTMLElement | null, index: number) => {
  const row = list?.children[index] as HTMLElement | undefined
  if (list && row) list.scrollTop = row.offsetTop - (list.clientHeight - row.offsetHeight) / 2
}

const centreTimes = () =>
  nextTick(() => {
    centre(hourListRef.value, activeHour.value)
    centre(minuteListRef.value, activeMinute.value)
  })

// --- where the panel goes: under the box, or over it with no room below ------

const panelStyle = ref<Record<string, string>>({})

const place = () => {
  const box = boxRef.value
  if (!box || !open.value) return
  const rect = box.getBoundingClientRect()
  const panel = panelRef.value
  const height = panel?.offsetHeight ?? 0
  const width = panel?.offsetWidth ?? rect.width
  const below = window.innerHeight - rect.bottom
  const upward = height + 8 > below && rect.top > below
  const left = Math.max(8, Math.min(rect.left, window.innerWidth - 8 - width))
  panelStyle.value = {
    left: `${left}px`,
    top: upward ? 'auto' : `${rect.bottom + 4}px`,
    bottom: upward ? `${window.innerHeight - rect.top + 4}px` : 'auto'
  }
}

const follow = () => place()
watch(open, (isOpen) => {
  if (isOpen) {
    window.addEventListener('scroll', follow, true)
    window.addEventListener('resize', follow)
    nextTick(() => {
      place()
      centreTimes()
      // Measured once drawn, so it can open upward or keep on screen.
      nextTick(place)
    })
  } else {
    window.removeEventListener('scroll', follow, true)
    window.removeEventListener('resize', follow)
  }
})
onBeforeUnmount(() => {
  window.removeEventListener('scroll', follow, true)
  window.removeEventListener('resize', follow)
})

// --- opening, picking, closing ----------------------------------------------------

// The hours and minutes on the time it has, or the one a new date starts at
// (9 am for a time alone).
const showTime = () => {
  const [hour, minute] = parts.value.hour
    ? [parts.value.hour, parts.value.minute]
    : hasDate.value
      ? props.defaultTime.split(':')
      : ['09', '00']
  activeHour.value = Math.max(0, HOURS.indexOf(hour!))
  activeMinute.value = Math.max(0, minutes.value.indexOf(minute!))
}

const openPanel = () => {
  if (open.value || props.disabled) return
  if (hasDate.value) {
    // The day it has, or today, or the earliest it can be when that's later.
    activeDate.value = parts.value.date || (hasMin.value && today < minParts.value.date ? minParts.value.date : today)
    showMonthOf(activeDate.value)
  }
  column.value = hasDate.value ? 'date' : 'hour'
  showTime()
  open.value = true
}

const close = () => {
  open.value = false
}

// A click anywhere on the box (or its label) opens or closes it.
const onBoxClick = (event: MouseEvent) => {
  if (props.disabled || panelRef.value?.contains(event.target as Node)) return
  fieldRef.value?.focus()
  if (open.value) close()
  else openPanel()
}

const set = (value: string) => {
  if (value === (props.modelValue || '')) return
  emit('update:modelValue', value)
  emit('change', value)
}

// A day alone finishes it. With a time, the day keeps its time (or takes the
// default), kept within the earliest and latest it can be, and the hours are
// next.
const pickDate = (date: string) => {
  if (dayOutside(date)) return
  if (!hasTime.value) {
    set(date)
    close()
    return
  }
  const [hour, minute] = parts.value.hour ? [parts.value.hour, parts.value.minute] : props.defaultTime.split(':')
  let value = valueOf({ date, hour: hour!, minute: minute! })
  if (hasMin.value && value < valueOf(minParts.value)) value = valueOf({ ...minParts.value, date })
  if (hasMax.value && value > valueOf(maxParts.value)) value = valueOf({ ...maxParts.value, date })
  set(value)
  activeDate.value = date
  showMonthOf(date)
  column.value = 'hour'
  nextTick(() => {
    showTime()
    centreTimes()
  })
}

// An hour keeps its minutes, or takes :00, and the minutes are next.
const pickHour = (hour: string) => {
  if (!canPickTime.value || hourOutside(hour)) return
  set(valueOf({ date: parts.value.date, hour, minute: parts.value.minute || '00' }))
  activeHour.value = HOURS.indexOf(hour)
  column.value = 'minute'
  activeMinute.value = Math.max(0, minutes.value.indexOf(parts.value.minute || '00'))
}

// The minutes finish it, once there's an hour.
const pickMinute = (minute: string) => {
  if (!canPickTime.value || !parts.value.hour || minuteOutside(minute)) return
  set(valueOf({ ...parts.value, minute }))
  close()
}

const showClear = computed(() => props.clearable && hasValue.value && !props.disabled)

const clear = () => {
  set('')
  close()
  fieldRef.value?.focus()
}

const moveDate = (days: number) => {
  activeDate.value = addDays(activeDate.value, days)
  showMonthOf(activeDate.value)
}

const moveTime = (by: number) => {
  if (column.value === 'hour') {
    activeHour.value = (activeHour.value + by + HOURS.length) % HOURS.length
    centre(hourListRef.value, activeHour.value)
  } else {
    activeMinute.value = (activeMinute.value + by + minutes.value.length) % minutes.value.length
    centre(minuteListRef.value, activeMinute.value)
  }
}

// Arrows move through the month a day or a week at a time, and through the
// hours or minutes; Enter picks; from the hours, left goes back to the month.
const DAY_STEPS: Record<string, number> = { ArrowDown: 7, ArrowUp: -7, ArrowLeft: -1, ArrowRight: 1 }

const onKeydown = (event: KeyboardEvent) => {
  if (!open.value) {
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault()
      openPanel()
    }
    return
  }
  const key = event.key
  if (key === 'Escape') {
    // Closes the panel, not the sheet or dialog it's in.
    event.preventDefault()
    event.stopPropagation()
    close()
    return
  }
  if (!['ArrowDown', 'ArrowUp', 'ArrowLeft', 'ArrowRight', 'Enter'].includes(key)) return
  event.preventDefault()
  if (column.value === 'date') {
    if (key === 'Enter') pickDate(activeDate.value)
    else moveDate(DAY_STEPS[key]!)
    return
  }
  if (key === 'Enter') {
    if (column.value === 'hour') pickHour(HOURS[activeHour.value]!)
    else pickMinute(minutes.value[activeMinute.value]!)
  } else if (key === 'ArrowLeft') {
    if (column.value === 'minute') column.value = 'hour'
    else if (hasDate.value) column.value = 'date'
  } else if (key === 'ArrowRight') {
    if (parts.value.hour) column.value = 'minute'
  } else {
    moveTime(key === 'ArrowDown' ? 1 : -1)
  }
}
</script>

<style scoped>
/* The box as a text box is drawn when the page doesn't draw it. No
   specificity, so a page's own classes and styles win. */
:where(.app-picker) {
  display: inline-block;
  padding: 0.4rem 0.6rem;
  border: 1px solid var(--border-light);
  border-radius: 6px;
  background: var(--surface-elevated);
  color: var(--teal);
  font: inherit;
  vertical-align: middle;
}

.app-picker {
  position: relative;
  box-sizing: border-box;
  /* The text in the middle of a box given a fixed height. */
  align-content: center;
  cursor: pointer;
}

.app-picker.is-disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

.app-picker:has(.app-picker__field:focus-visible),
.app-picker.is-open {
  outline: 2px solid var(--dark-green);
  outline-offset: 2px;
}

/* What's picked, with room on the right for the icon. */
.app-picker__field {
  display: block;
  box-sizing: border-box;
  width: 100%;
  margin: 0;
  padding: 0 1.6rem 0 0;
  border: 0;
  outline: none;
  background: transparent;
  color: inherit;
  font: inherit;
  line-height: normal;
  text-align: left;
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
  cursor: inherit;
}

/* Large, or the shared text box (app-input): the page's line height, as
   the text boxes beside it have, so it's as tall as they are. */
.app-picker.is-large .app-picker__field,
.app-picker.app-input .app-picker__field {
  line-height: inherit;
}

.app-picker__field.is-empty {
  color: var(--text-muted);
}

/* The clear button, left of the icon, and the room the text leaves for it. */
.app-picker.has-clear .app-picker__field {
  padding-right: 3rem;
}

.app-picker__clear {
  position: absolute;
  top: 50%;
  right: 1.9rem;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1.3rem;
  height: 1.3rem;
  padding: 0;
  border: none;
  border-radius: 50%;
  background: transparent;
  color: var(--text-muted);
  font-size: 0.75em;
  cursor: pointer;
  transform: translateY(-50%);
}

.app-picker__clear:hover,
.app-picker__clear:focus-visible {
  background: var(--bg-light);
  color: var(--teal);
}

.app-picker__icon {
  position: absolute;
  top: 50%;
  right: 0.6rem;
  color: var(--text-muted);
  font-size: 0.85em;
  pointer-events: none;
  transform: translateY(-50%);
}

.app-picker.is-open .app-picker__icon {
  color: var(--dark-green);
}

.app-picker__validator {
  position: absolute;
  bottom: 0;
  left: 50%;
  width: 1px;
  height: 1px;
  padding: 0;
  border: 0;
  opacity: 0;
  pointer-events: none;
}

/* The panel: the month, a line, then the hours and minutes. The same size
   wherever it opens, whatever the box's own text size (--picker-text). */
.app-picker__panel {
  position: fixed;
  font-size: var(--picker-text, 1rem);
  z-index: 2200;
  display: flex;
  align-items: stretch;
  box-sizing: border-box;
  padding: 0.6rem;
  border: 1px solid var(--border-light);
  border-radius: 10px;
  background: var(--surface-elevated);
  box-shadow: 0 8px 24px var(--shadow, rgba(0, 0, 0, 0.14));
  color: var(--teal);
}

.app-picker__calendar {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.app-picker__top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  padding-bottom: 0.15rem;
}

.app-picker__month {
  font-size: 1em;
  font-weight: 600;
}

.app-picker__nav {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1.9em;
  height: 1.9em;
  padding: 0;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: var(--teal);
  font-size: 0.85em;
  cursor: pointer;
}

.app-picker__nav:hover {
  background: var(--light-green);
}

.app-picker__weekdays,
.app-picker__days {
  display: grid;
  grid-template-columns: repeat(7, var(--picker-day-width, 1.65em));
  gap: 0.1em;
}

.app-picker__weekdays span {
  color: var(--text-muted);
  font-size: 0.75em;
  font-weight: 700;
  text-align: center;
}

.app-picker__day {
  height: var(--picker-day-height, 1.7em);
  padding: 0;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: var(--teal);
  font: inherit;
  font-size: 0.9em;
  font-variant-numeric: tabular-nums;
  cursor: pointer;
}

.app-picker__day:hover:not(:disabled),
.app-picker__day.is-active {
  background: var(--light-green);
}

.app-picker__day.is-other {
  color: var(--text-muted);
  opacity: 0.6;
}

.app-picker__day.is-today {
  box-shadow: inset 0 0 0 1px var(--dark-green);
  font-weight: 700;
}

.app-picker__day.is-selected {
  background: var(--dark-green);
  box-shadow: none;
  color: var(--white, #ffffff);
  font-weight: 600;
  opacity: 1;
}

/* Before the earliest or after the latest it can be. */
.app-picker__day:disabled {
  color: var(--text-muted);
  opacity: 0.35;
  cursor: not-allowed;
}

/* Each column scrolling on its own: beside a month, as tall as it. */
.app-picker__time {
  display: flex;
  gap: 0.1rem;
}

.app-picker__time.has-date {
  margin-left: 0.45rem;
  padding-left: 0.45rem;
  border-left: 1px solid var(--border-light);
}

.app-picker__time.is-waiting {
  opacity: 0.45;
}

.app-picker__time.is-waiting .app-picker__option {
  cursor: not-allowed;
}

.app-picker__column {
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.app-picker__heading {
  padding: 0.35rem 0 0.4rem;
  color: var(--text-muted);
  font-size: 0.7em;
  font-weight: 700;
  letter-spacing: 0.05em;
  text-align: center;
  text-transform: uppercase;
}

.app-picker__list {
  position: relative;
  margin: 0;
  padding: 0 0.15rem;
  overflow-y: auto;
  list-style: none;
  /* Scrolled with the wheel, a finger or the arrow keys: no scrollbar. */
  scrollbar-width: none;
}

.app-picker__list::-webkit-scrollbar {
  display: none;
}

/* Beside a month, as tall as it; alone, about seven rows. */
.app-picker__time.has-date .app-picker__list {
  flex: 1 1 0;
  min-height: 0;
}

.app-picker__time:not(.has-date) .app-picker__list {
  height: 12em;
}

.app-picker__colon {
  align-self: center;
  color: var(--text-muted);
  font-weight: 700;
}

.app-picker__option {
  padding: var(--picker-option-padding, 0.1rem 0.4rem);
  border-radius: 6px;
  font-size: 0.9em;
  font-variant-numeric: tabular-nums;
  line-height: var(--picker-option-line-height, 1.35);
  text-align: center;
  cursor: pointer;
}

.app-picker__option:hover,
.app-picker__option.is-active {
  background: var(--light-green);
}

.app-picker__option.is-selected {
  background: var(--dark-green);
  color: var(--white, #ffffff);
  font-weight: 600;
}

.app-picker__option.is-disabled:not(.is-selected) {
  background: transparent;
  color: var(--text-muted);
  cursor: not-allowed;
}
</style>
