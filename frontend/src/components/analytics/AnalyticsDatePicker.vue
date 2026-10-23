<template>
  <div ref="root" class="analytics-date-picker" @focusout="closeOnFocusLeave">
    <input
      class="analytics-date-picker-native-proxy"
      type="date"
      :value="modelValue"
      :min="min"
      :max="max"
      :aria-label="label"
      @input="emitProxyValue"
    />
    <button
      type="button"
      ref="trigger"
      class="analytics-date-picker-trigger"
      aria-haspopup="dialog"
      :aria-controls="calendarId"
      :aria-label="label"
      :aria-expanded="open"
      @click="toggle"
    >
      <span>{{ displayValue }}</span>
      <i class="far fa-calendar-alt" aria-hidden="true"></i>
    </button>

    <div v-if="open" :id="calendarId" ref="popover" class="analytics-date-picker-popover"
      role="dialog" :aria-label="label" @keydown.esc.stop.prevent="close(true)">
      <div class="analytics-date-picker-heading">
        <select ref="yearSelect" v-model.number="visibleYear" aria-label="Select year">
          <option v-for="year in selectableYears" :key="year" :value="year">{{ year }}</option>
        </select>
        <select ref="monthSelect" v-model.number="visibleMonth" aria-label="Select month">
          <option v-for="month in 12" :key="month" :value="month - 1">
            {{ monthNames[month - 1] }}
          </option>
        </select>
      </div>

      <div role="grid" :aria-label="`${monthNames[visibleMonth]} ${visibleYear}`">
        <div class="analytics-date-picker-weekdays" role="row">
          <span v-for="(day, index) in weekdays" :key="day" role="columnheader" :aria-label="weekdayNames[index]">{{ day }}</span>
        </div>
        <div class="analytics-date-picker-days">
          <div v-for="(week, index) in weeks" :key="index" class="analytics-date-picker-week" role="row">
            <div v-for="(day, column) in week" :key="column" role="gridcell"
              :aria-selected="day ? isSelected(day) : undefined">
              <button v-if="day"
                type="button"
                :data-date="dateKey(day)"
                :aria-label="`${day} ${monthNames[visibleMonth]} ${visibleYear}`"
                :class="{ selected: isSelected(day) }"
                :disabled="!isSelectable(day)"
                :tabindex="isSelectable(day) && focusedDate === dateKey(day) ? 0 : -1"
                @focus="focusedDate = dateKey(day)"
                @keydown="navigate($event, day)"
                @click="selectDay(day)"
              >{{ day }}</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, useId, watch } from 'vue'

const props = defineProps<{
  modelValue: string
  min?: string
  max?: string
  availableYears: number[]
  label: string
}>()

const emit = defineEmits<{ 'update:modelValue': [value: string] }>()
const root = ref<HTMLElement | null>(null)
const trigger = ref<HTMLButtonElement | null>(null)
const popover = ref<HTMLElement | null>(null)
const yearSelect = ref<HTMLSelectElement | null>(null)
const monthSelect = ref<HTMLSelectElement | null>(null)
const calendarId = useId()
const focusedDate = ref('')
const open = ref(false)
const initial = computed(() => parseDate(props.modelValue) ?? new Date())
const visibleYear = ref(initial.value.getUTCFullYear())
const visibleMonth = ref(initial.value.getUTCMonth())
const monthNames = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
const weekdays = ['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa']
const weekdayNames = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']

const selectableYears = computed(() => [...new Set(props.availableYears)].sort((a, b) => a - b))
const displayValue = computed(() => props.modelValue ? props.modelValue.replace(/-/g, '/') : 'Select date')
const daysInVisibleMonth = computed(() => new Date(Date.UTC(visibleYear.value, visibleMonth.value + 1, 0)).getUTCDate())
const leadingBlanks = computed(() => new Date(Date.UTC(visibleYear.value, visibleMonth.value, 1)).getUTCDay())

const weeks = computed(() => {
  const cells: Array<number | null> = Array(leadingBlanks.value).fill(null)
  for (let day = 1; day <= daysInVisibleMonth.value; day++) cells.push(day)
  while (cells.length % 7) cells.push(null)
  return Array.from({ length: cells.length / 7 }, (_, i) => cells.slice(i * 7, i * 7 + 7))
})

function parseDate(value: string) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return null
  const date = new Date(`${value}T00:00:00Z`)
  return !Number.isNaN(date.getTime()) && date.toISOString().slice(0, 10) === value ? date : null
}

// At most one interval per allowed year; no scanning across missing years.
const allowedRanges = computed(() => selectableYears.value.flatMap((year) => {
  const start = `${year}-01-01`
  const end = `${year}-12-31`
  const lower = props.min && props.min > start ? props.min : start
  const upper = props.max && props.max < end ? props.max : end
  return lower <= upper ? [{ lower, upper }] : []
}))

function allowed(value: string) {
  return !!parseDate(value) && allowedRanges.value.some(({ lower, upper }) => value >= lower && value <= upper)
}

function nearest(value: string, direction = 0) {
  const candidates = allowedRanges.value.map(({ lower, upper }) => value < lower ? lower : value > upper ? upper : value)
    .filter((candidate) => !direction || (direction > 0 ? candidate >= value : candidate <= value))
  return candidates.sort((a, b) => Math.abs(parseDate(a)!.getTime() - parseDate(value)!.getTime())
    - Math.abs(parseDate(b)!.getTime() - parseDate(value)!.getTime()) || a.localeCompare(b))[0] ?? ''
}

function showDate(value: string) {
  const date = parseDate(value)
  if (!date) return
  visibleYear.value = date.getUTCFullYear()
  visibleMonth.value = date.getUTCMonth()
  focusedDate.value = value
}

async function focusDate() {
  await nextTick()
  if (!open.value || !root.value?.isConnected) return
  const button = popover.value?.querySelector<HTMLButtonElement>(`button[data-date="${focusedDate.value}"]:not(:disabled)`)
  if (button) button.focus()
  else (selectableYears.value.length ? yearSelect.value : monthSelect.value)?.focus()
}

function syncVisibleFocus() {
  const days = Array.from({ length: daysInVisibleMonth.value }, (_, i) => dateKey(i + 1)).filter(allowed)
  const preferredDay = parseDate(focusedDate.value)?.getUTCDate() ?? 1
  focusedDate.value = days.reduce((best, value) => !best
    || Math.abs(Number(value.slice(-2)) - preferredDay) < Math.abs(Number(best.slice(-2)) - preferredDay)
    ? value : best, '')
}

watch([visibleYear, visibleMonth, () => props.min, () => props.max, selectableYears], () => {
  const hadDateFocus = popover.value?.contains(document.activeElement)
    && document.activeElement?.hasAttribute('data-date')
  syncVisibleFocus()
  if (hadDateFocus && open.value) void focusDate()
})

watch(() => props.modelValue, (value) => {
  const hadDateFocus = popover.value?.contains(document.activeElement)
    && document.activeElement?.hasAttribute('data-date')
  if (parseDate(value)) showDate(value)
  syncVisibleFocus()
  if (hadDateFocus && open.value) void focusDate()
})

watch(selectableYears, (years) => {
  if (years.length && !years.includes(visibleYear.value)) visibleYear.value = years[years.length - 1]!
}, { immediate: true })

function close(restore = false) {
  open.value = false
  if (restore) trigger.value?.focus()
}

function closeOnFocusLeave(event: FocusEvent) {
  if (event.relatedTarget instanceof Node && !root.value?.contains(event.relatedTarget)) close()
}

function navigate(event: KeyboardEvent, day: number) {
  if (event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return
  const date = parseDate(dateKey(day))!
  const original = date.getTime()
  const offsets: Record<string, number> = { ArrowLeft: -1, ArrowRight: 1, ArrowUp: -7, ArrowDown: 7,
    Home: -date.getUTCDay(), End: 6 - date.getUTCDay() }
  if (event.key in offsets) date.setUTCDate(date.getUTCDate() + offsets[event.key]!)
  else if (event.key === 'PageUp' || event.key === 'PageDown') {
    date.setUTCDate(1)
    date.setUTCMonth(date.getUTCMonth() + (event.key === 'PageUp' ? -1 : 1))
    date.setUTCDate(Math.min(day, new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth() + 1, 0)).getUTCDate()))
  } else return // Native Enter/Space generate the single click/selection.
  event.preventDefault()
  const target = date.toISOString().slice(0, 10)
  const direction = Math.sign(date.getTime() - original)
  if (!direction) return
  let next = nearest(target, direction)
  if (!next) next = nearest(target)
  if (event.key === 'Home' || event.key === 'End') {
    // Keep week shortcuts inside this week, even when the endpoint is disabled.
    const candidates = Array.from({ length: 7 }, (_, offset) => {
      const candidate = new Date(original)
      candidate.setUTCDate(candidate.getUTCDate() - candidate.getUTCDay() + offset)
      return candidate.toISOString().slice(0, 10)
    }).filter(allowed)
    next = (event.key === 'Home' ? candidates[0] : candidates[candidates.length - 1]) ?? ''
  }
  if (next && allowed(next)) { showDate(next); void focusDate() }
}

function dateKey(day: number) {
  return `${visibleYear.value}-${String(visibleMonth.value + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`
}

function isSelectable(day: number) {
  const value = dateKey(day)
  return allowed(value)
}

function isSelected(day: number) {
  return props.modelValue === dateKey(day)
}

function selectDay(day: number) {
  if (!isSelectable(day)) return
  emit('update:modelValue', dateKey(day))
  close(true)
}

function toggle() {
  if (open.value) { close(true); return }
  const target = allowed(props.modelValue) ? props.modelValue : nearest(new Date().toISOString().slice(0, 10))
  if (target) showDate(target)
  else focusedDate.value = ''
  open.value = true
  void focusDate()
}

function emitProxyValue(event: Event) {
  const input = event.target as HTMLInputElement
  let value = input.value
  if (props.min && value < props.min) value = props.min
  if (props.max && value > props.max) value = props.max
  input.value = value
  emit('update:modelValue', value)
}

function closeOutside(event: MouseEvent) {
  if (!open.value || !root.value || root.value.contains(event.target as Node)) return
  const hadCalendarFocus = !!popover.value?.contains(document.activeElement)
  close()
  // Wait for the pointer's native focus action; do not override an outside target.
  void nextTick(() => {
    if (hadCalendarFocus && !open.value && root.value?.isConnected
      && document.activeElement === document.body) trigger.value?.focus()
  })
}

onMounted(() => document.addEventListener('mousedown', closeOutside))
onBeforeUnmount(() => document.removeEventListener('mousedown', closeOutside))
</script>

<style scoped>
.analytics-date-picker {
  position: relative;
  min-width: 0;
}
.analytics-date-picker-native-proxy {
  display: none !important;
}
.analytics-date-picker-trigger {
  display: flex;
  width: 100%;
  height: 42px;
  align-items: center;
  justify-content: space-between;
  padding: 0 12px;
  border: 1px solid var(--analytics-ui-control-border, #79bdb4);
  border-radius: 10px;
  background: var(--analytics-ui-surface, #fff);
  color: var(--analytics-ui-accent, #017151);
  font: inherit;
  font-size: 13px;
  cursor: pointer;
}
.analytics-date-picker-popover {
  position: absolute;
  top: calc(100% + 6px);
  left: 0;
  z-index: 500;
  width: 286px;
  padding: 14px;
  border: 1px solid var(--analytics-ui-border, #d7e3df);
  border-radius: 12px;
  background: var(--analytics-ui-surface, #fff);
  box-shadow: 0 12px 30px rgba(23, 66, 67, .18);
}
.analytics-date-picker-heading {
  display: grid;
  grid-template-columns: 1fr 1.35fr;
  gap: 8px;
  margin-bottom: 12px;
}
.analytics-date-picker-heading select {
  width: 100%;
  height: 36px;
  padding: 0 9px;
  border: 1px solid var(--analytics-ui-control-border, #79bdb4);
  border-radius: 8px;
  background: var(--analytics-ui-surface, #fff);
  color: var(--analytics-ui-text, #174243);
  font: inherit;
}
.analytics-date-picker-weekdays,
.analytics-date-picker-week {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 4px;
}
.analytics-date-picker-days {
  display: grid;
  gap: 4px;
}
.analytics-date-picker-week > [role="gridcell"] {
  display: flex;
}
.analytics-date-picker-days button:focus-visible {
  outline: 2px solid #174243;
  outline-offset: 1px;
}
.analytics-date-picker-weekdays {
  margin-bottom: 5px;
  color: var(--analytics-ui-muted, #748783);
  font-size: 11px;
  text-align: center;
}
.analytics-date-picker-days button {
  width: 34px;
  height: 32px;
  border: 0;
  border-radius: 7px;
  background: transparent;
  color: var(--analytics-ui-text, #174243);
  cursor: pointer;
}
.analytics-date-picker-days button:hover:not(:disabled) {
  background: var(--analytics-ui-selected, #e4f2ed);
}
.analytics-date-picker-days button.selected {
  background: #017151;
  color: #fff;
  font-weight: 700;
}
.analytics-date-picker-days button:disabled {
  color: var(--analytics-ui-muted, #c1cdca);
  cursor: not-allowed;
}
</style>
