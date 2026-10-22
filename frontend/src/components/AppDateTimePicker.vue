<template>
  <!-- A date and a time, "YYYY-MM-DDTHH:MM" as a datetime-local input has
       it (no time zone). This is its box: the page's classes, styles and
       data-test land here, so it's drawn as the page's other boxes are. The
       month and the hours and minutes open side by side in a panel over the
       page, where nothing can cut them off. -->
  <div
    ref="boxRef"
    v-bind="boxAttrs"
    class="app-datetime"
    :class="{ 'is-open': open, 'is-disabled': disabled, 'has-clear': showClear }"
    @mousedown.prevent
    @click="onBoxClick"
  >
    <button
      :id="id"
      ref="fieldRef"
      v-bind="fieldAttrs"
      type="button"
      class="app-datetime__field"
      :class="{ 'is-empty': !parts.date }"
      aria-haspopup="dialog"
      :aria-expanded="open"
      :aria-controls="panelId"
      :disabled="disabled"
      @keydown="onKeydown"
      @blur="close"
    >
      {{ shown || placeholder }}
    </button>
    <!-- Clearable: a × that empties it, while there's a date to empty. -->
    <button
      v-if="showClear"
      type="button"
      class="app-datetime__clear"
      aria-label="Clear"
      data-test="app-datetime-clear"
      @click.stop="clear"
    >
      <i class="fas fa-xmark" aria-hidden="true"></i>
    </button>
    <i class="far fa-calendar app-datetime__icon" aria-hidden="true"></i>
    <Teleport to="body">
      <div
        v-if="open"
        :id="panelId"
        ref="panelRef"
        class="app-datetime__panel"
        role="dialog"
        aria-label="Pick a date and time"
        :style="panelStyle"
        @mousedown.prevent.stop
        @click.stop
      >
        <!-- The month: a week to a row, from Monday. -->
        <div class="app-datetime__calendar">
          <div class="app-datetime__top">
            <button type="button" class="app-datetime__nav" aria-label="Previous month" @click="showMonth(-1)">
              <i class="fas fa-chevron-left" aria-hidden="true"></i>
            </button>
            <span class="app-datetime__month">{{ MONTHS[view.month] }} {{ view.year }}</span>
            <button type="button" class="app-datetime__nav" aria-label="Next month" @click="showMonth(1)">
              <i class="fas fa-chevron-right" aria-hidden="true"></i>
            </button>
          </div>
          <div class="app-datetime__weekdays" aria-hidden="true">
            <span v-for="day in WEEKDAYS" :key="day">{{ day }}</span>
          </div>
          <div class="app-datetime__days">
            <button
              v-for="cell in cells"
              :key="cell.date"
              type="button"
              tabindex="-1"
              class="app-datetime__day"
              :class="{
                'is-other': !cell.inMonth,
                'is-today': cell.date === today,
                'is-selected': cell.date === parts.date,
                'is-active': column === 'date' && cell.date === activeDate
              }"
              :aria-label="longDate(cell.date)"
              :aria-pressed="cell.date === parts.date"
              :data-date="cell.date"
              @click="pickDate(cell.date)"
            >
              {{ cell.day }}
            </button>
          </div>
        </div>

        <!-- The time: hours and minutes, once there's a date. -->
        <div class="app-datetime__time" :class="{ 'is-waiting': !parts.date }">
          <div class="app-datetime__column">
            <span class="app-datetime__heading">Hour</span>
            <ul ref="hourListRef" class="app-datetime__list" role="listbox" aria-label="Hour">
              <li
                v-for="(hour, index) in HOURS"
                :key="hour"
                role="option"
                class="app-datetime__option"
                :class="{
                  'is-selected': hour === parts.hour,
                  'is-active': column === 'hour' && index === activeHour
                }"
                :aria-selected="hour === parts.hour"
                :aria-disabled="!parts.date || undefined"
                :data-hour="hour"
                @click="pickHour(hour)"
              >
                {{ hour }}
              </li>
            </ul>
          </div>
          <span class="app-datetime__colon" aria-hidden="true">:</span>
          <div class="app-datetime__column">
            <span class="app-datetime__heading">Min</span>
            <ul ref="minuteListRef" class="app-datetime__list" role="listbox" aria-label="Minutes">
              <li
                v-for="(minute, index) in minutes"
                :key="minute"
                role="option"
                class="app-datetime__option"
                :class="{
                  'is-selected': minute === parts.minute,
                  'is-active': column === 'minute' && index === activeMinute
                }"
                :aria-selected="minute === parts.minute"
                :aria-disabled="!parts.date || undefined"
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
const nextPanelId = () => `app-datetime-${++lastPanelId}`
</script>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, reactive, ref, useAttrs, watch } from 'vue'

defineOptions({ inheritAttrs: false })

const props = withDefaults(
  defineProps<{
    /** "YYYY-MM-DDTHH:MM", or empty for none yet. */
    modelValue?: string
    id?: string
    /** Shown while there's no date. */
    placeholder?: string
    disabled?: boolean
    /** A × in the box, to empty it. */
    clearable?: boolean
    /** The time a date picked into an empty box starts at. */
    defaultTime?: string
    /** The minutes offered, in steps of this many: every one by default. */
    step?: number
  }>(),
  {
    modelValue: '',
    id: undefined,
    placeholder: 'Select date and time',
    disabled: false,
    clearable: false,
    defaultTime: '00:00',
    step: 1
  }
)

const emit = defineEmits<{
  'update:modelValue': [value: string]
  /** After a date or time is picked, as an input's change event. */
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
const hourListRef = ref<HTMLElement | null>(null)
const minuteListRef = ref<HTMLElement | null>(null)
const open = ref(false)

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

// The value as its date, hour and minutes.
const parts = computed(() => {
  const match = /^(\d{4}-\d{2}-\d{2})T(\d{2}):(\d{2})/.exec(props.modelValue || '')
  return match ? { date: match[1]!, hour: match[2]!, minute: match[3]! } : { date: '', hour: '', minute: '' }
})

// "15 Oct 2026, 23:59".
const shown = computed(() => {
  if (!parts.value.date) return ''
  const [year, month, day] = parts.value.date.split('-').map(Number)
  return `${day} ${MONTHS[month! - 1]!.slice(0, 3)} ${year}, ${parts.value.hour}:${parts.value.minute}`
})

// Every step's minutes, and one saved between them, so it can still be seen.
const minutes = computed(() => {
  const step = Math.max(1, Math.min(60, Math.floor(props.step)))
  const list = Array.from({ length: Math.ceil(60 / step) }, (_, index) => twoDigits(index * step))
  const saved = parts.value.minute
  return saved && !list.includes(saved) ? [...list, saved].sort() : list
})

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
    bottom: upward ? `${window.innerHeight - rect.top + 4}px` : 'auto',
    fontSize: getComputedStyle(box).fontSize
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

// The hours and minutes on the time it has, or the one a new date starts at.
const showTime = () => {
  const [hour, minute] = (parts.value.date ? `${parts.value.hour}:${parts.value.minute}` : props.defaultTime).split(':')
  activeHour.value = Math.max(0, HOURS.indexOf(hour!))
  activeMinute.value = Math.max(0, minutes.value.indexOf(minute!))
}

const openPanel = () => {
  if (open.value || props.disabled) return
  activeDate.value = parts.value.date || today
  showMonthOf(activeDate.value)
  column.value = 'date'
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
  if (value === props.modelValue) return
  emit('update:modelValue', value)
  emit('change', value)
}

// A day keeps its time, or takes the default, and the hours are next.
const pickDate = (date: string) => {
  const time = parts.value.date ? `${parts.value.hour}:${parts.value.minute}` : props.defaultTime
  set(`${date}T${time}`)
  activeDate.value = date
  showMonthOf(date)
  column.value = 'hour'
  nextTick(() => {
    showTime()
    centreTimes()
  })
}

const pickHour = (hour: string) => {
  if (!parts.value.date) return
  set(`${parts.value.date}T${hour}:${parts.value.minute}`)
  activeHour.value = HOURS.indexOf(hour)
  column.value = 'minute'
}

// The minutes finish it.
const pickMinute = (minute: string) => {
  if (!parts.value.date) return
  set(`${parts.value.date}T${parts.value.hour}:${minute}`)
  close()
}

const showClear = computed(() => props.clearable && Boolean(parts.value.date) && !props.disabled)

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
    column.value = column.value === 'minute' ? 'hour' : 'date'
  } else if (key === 'ArrowRight') {
    column.value = 'minute'
  } else {
    moveTime(key === 'ArrowDown' ? 1 : -1)
  }
}
</script>

<style scoped>
/* The box as a text box is drawn when the page doesn't draw it. No
   specificity, so a page's own classes and styles win. */
:where(.app-datetime) {
  display: inline-block;
  padding: 0.4rem 0.6rem;
  border: 1px solid var(--border-light);
  border-radius: 6px;
  background: var(--surface-elevated);
  color: var(--teal);
  font: inherit;
  vertical-align: middle;
}

.app-datetime {
  position: relative;
  box-sizing: border-box;
  /* The text in the middle of a box given a fixed height. */
  align-content: center;
  cursor: pointer;
}

.app-datetime.is-disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

.app-datetime:has(.app-datetime__field:focus-visible),
.app-datetime.is-open {
  outline: 2px solid var(--dark-green);
  outline-offset: 2px;
}

/* What's picked, with room on the right for the calendar icon. */
.app-datetime__field {
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

.app-datetime.app-input .app-datetime__field {
  line-height: inherit;
}

.app-datetime__field.is-empty {
  color: var(--text-muted);
}

/* The clear button, left of the icon, and the room the text leaves for it. */
.app-datetime.has-clear .app-datetime__field {
  padding-right: 3rem;
}

.app-datetime__clear {
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

.app-datetime__clear:hover,
.app-datetime__clear:focus-visible {
  background: var(--bg-light);
  color: var(--teal);
}

.app-datetime__icon {
  position: absolute;
  top: 50%;
  right: 0.6rem;
  color: var(--text-muted);
  font-size: 0.85em;
  pointer-events: none;
  transform: translateY(-50%);
}

.app-datetime.is-open .app-datetime__icon {
  color: var(--dark-green);
}

/* The panel: the month, a line, then the hours and minutes. */
.app-datetime__panel {
  position: fixed;
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

.app-datetime__calendar {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  padding-right: 0.45rem;
}

.app-datetime__top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  padding-bottom: 0.15rem;
}

.app-datetime__month {
  font-weight: 700;
}

.app-datetime__nav {
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

.app-datetime__nav:hover {
  background: var(--light-green);
}

.app-datetime__weekdays,
.app-datetime__days {
  display: grid;
  grid-template-columns: repeat(7, 1.65em);
  gap: 0.1em;
}

.app-datetime__weekdays span {
  color: var(--text-muted);
  font-size: 0.75em;
  font-weight: 700;
  text-align: center;
}

.app-datetime__day {
  height: 1.7em;
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

.app-datetime__day:hover,
.app-datetime__day.is-active {
  background: var(--light-green);
}

.app-datetime__day.is-other {
  color: var(--text-muted);
  opacity: 0.6;
}

.app-datetime__day.is-today {
  box-shadow: inset 0 0 0 1px var(--dark-green);
  font-weight: 700;
}

.app-datetime__day.is-selected {
  background: var(--dark-green);
  box-shadow: none;
  color: var(--white, #ffffff);
  font-weight: 600;
  opacity: 1;
}

/* As tall as the month beside it, each column scrolling on its own. */
.app-datetime__time {
  display: flex;
  gap: 0.1rem;
  padding-left: 0.45rem;
  border-left: 1px solid var(--border-light);
}

.app-datetime__time.is-waiting {
  opacity: 0.45;
}

.app-datetime__time.is-waiting .app-datetime__option {
  cursor: not-allowed;
}

.app-datetime__column {
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.app-datetime__heading {
  padding: 0.35rem 0 0.4rem;
  color: var(--text-muted);
  font-size: 0.7em;
  font-weight: 700;
  letter-spacing: 0.05em;
  text-align: center;
  text-transform: uppercase;
}

.app-datetime__list {
  position: relative;
  flex: 1 1 0;
  min-height: 0;
  margin: 0;
  padding: 0 0.15rem;
  overflow-y: auto;
  list-style: none;
  /* Scrolled with the wheel, a finger or the arrow keys: no scrollbar. */
  scrollbar-width: none;
}

.app-datetime__list::-webkit-scrollbar {
  display: none;
}

.app-datetime__colon {
  align-self: center;
  color: var(--text-muted);
  font-weight: 700;
}

.app-datetime__option {
  padding: 0.1rem 0.4rem;
  line-height: 1.35;
  border-radius: 6px;
  font-size: 0.9em;
  font-variant-numeric: tabular-nums;
  text-align: center;
  cursor: pointer;
}

.app-datetime__option:hover,
.app-datetime__option.is-active {
  background: var(--light-green);
}

.app-datetime__option.is-selected {
  background: var(--dark-green);
  color: var(--white, #ffffff);
  font-weight: 600;
}
</style>
