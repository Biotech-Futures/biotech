<template>
  <div class="app-date-picker-wrapper" ref="wrapperRef">
    <div
      class="app-date-picker-input"
      :class="{ 'is-focused': isOpen, 'is-disabled': disabled, 'has-value': !!modelValue }"
      @click="togglePopover"
      tabindex="0"
      @keydown.enter.prevent="togglePopover"
      @keydown.space.prevent="togglePopover"
      @keydown.esc="closePopover"
    >
      <i class="fas fa-calendar date-input-icon" aria-hidden="true"></i>
      <span class="date-input-text" :class="{ 'is-placeholder': !modelValue }">
        {{ formattedDisplayValue || placeholder }}
      </span>
      <button
        v-if="clearable && modelValue && !disabled"
        type="button"
        class="date-input-clear"
        @click.stop="clearDate"
        aria-label="Clear date"
      >
        <i class="fas fa-times" aria-hidden="true"></i>
      </button>
    </div>

    <transition name="calendar-fade">
      <div
        v-if="isOpen && !disabled"
        ref="popoverRef"
        class="app-date-picker-popover"
        :class="[
          `placement-v-${placementVertical}`,
          `placement-h-${placementHorizontal}`
        ]"
        @click.stop
      >
        <div class="mini-calendar-topbar">
          <button
            type="button"
            class="calendar-nav-button"
            @click.stop="goPrevMonth"
            aria-label="Previous month"
          >
            <i class="fas fa-chevron-left" aria-hidden="true"></i>
          </button>

          <div class="mini-calendar-heading" @click.stop>
            <div class="mini-calendar-title">{{ calendarTitle }}</div>
          </div>

          <button
            type="button"
            class="calendar-nav-button"
            @click.stop="goNextMonth"
            aria-label="Next month"
          >
            <i class="fas fa-chevron-right" aria-hidden="true"></i>
          </button>
        </div>

        <div class="mini-calendar-toolbar">
          <button
            type="button"
            class="calendar-current-button"
            :disabled="isCurrentMonth"
            @click.stop="goToCurrentMonth"
          >
            Today
          </button>
          <span v-if="modelValue" class="selected-hint">{{ formattedDisplayValue }}</span>
        </div>

        <div class="mini-calendar-weekdays">
          <span v-for="label in weekdayLabels" :key="label">{{ label }}</span>
        </div>

        <div class="mini-calendar-grid">
          <button
            v-for="cell in calendarDays"
            :key="cell.key"
            type="button"
            class="mini-calendar-cell"
            :class="{
              'is-empty': !cell.day,
              'is-today': cell.isToday,
              'is-selected': cell.isSelected,
              'other-month': !cell.isCurrentMonth
            }"
            :disabled="!cell.day"
            @click.stop="selectCell(cell)"
          >
            <span class="cell-num">{{ cell.day ?? '' }}</span>
          </button>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'

const props = withDefaults(
  defineProps<{
    modelValue?: string
    placeholder?: string
    clearable?: boolean
    disabled?: boolean
  }>(),
  {
    modelValue: '',
    placeholder: 'Select date',
    clearable: true,
    disabled: false
  }
)

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void
}>()

const wrapperRef = ref<HTMLElement | null>(null)
const popoverRef = ref<HTMLElement | null>(null)
const isOpen = ref(false)

const placementVertical = ref<'bottom' | 'top'>('bottom')
const placementHorizontal = ref<'left' | 'right'>('left')

const pad = (n: number) => String(n).padStart(2, '0')

const parseToDateParts = (str?: string): { year: number; month: number; day: number } | null => {
  if (!str) return null
  const match = String(str).match(/^(\d{4})-(\d{2})-(\d{2})/)
  if (match) {
    const year = parseInt(match[1], 10)
    const month = parseInt(match[2], 10)
    const day = parseInt(match[3], 10)
    if (year >= 1000 && month >= 1 && month <= 12 && day >= 1 && day <= 31) {
      return { year, month: month - 1, day }
    }
  }
  return null
}

const todayDate = new Date()
const todayKey = `${todayDate.getFullYear()}-${pad(todayDate.getMonth() + 1)}-${pad(todayDate.getDate())}`

const calendarYear = ref(todayDate.getFullYear())
const calendarMonth = ref(todayDate.getMonth())

const weekdayLabels = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

const syncCalendarToValue = () => {
  const parts = parseToDateParts(props.modelValue)
  if (parts) {
    calendarYear.value = parts.year
    calendarMonth.value = parts.month
  } else {
    const now = new Date()
    calendarYear.value = now.getFullYear()
    calendarMonth.value = now.getMonth()
  }
}

watch(() => props.modelValue, syncCalendarToValue, { immediate: true })

const formattedDisplayValue = computed(() => {
  const parts = parseToDateParts(props.modelValue)
  if (!parts) return ''
  const dt = new Date(parts.year, parts.month, parts.day)
  return new Intl.DateTimeFormat('en-AU', {
    day: '2-digit',
    month: 'short',
    year: 'numeric'
  }).format(dt)
})

const calendarTitle = computed(() => {
  const dt = new Date(calendarYear.value, calendarMonth.value, 1)
  return new Intl.DateTimeFormat('en-AU', {
    month: 'long',
    year: 'numeric'
  }).format(dt)
})

const isCurrentMonth = computed(() => {
  const now = new Date()
  return (
    calendarYear.value === now.getFullYear() &&
    calendarMonth.value === now.getMonth()
  )
})

interface DayCell {
  key: string
  day: number | null
  dateKey: string | null
  isToday: boolean
  isSelected: boolean
  isCurrentMonth: boolean
}

const calendarDays = computed(() => {
  const year = calendarYear.value
  const month = calendarMonth.value

  const firstDay = new Date(year, month, 1)
  const daysInMonth = new Date(year, month + 1, 0).getDate()
  const firstWeekday = (firstDay.getDay() + 6) % 7 // Monday = 0

  const now = new Date()
  const todayKey = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`

  const cells: DayCell[] = []

  // Previous month padding
  const prevMonthLastDay = new Date(year, month, 0).getDate()
  for (let i = firstWeekday - 1; i >= 0; i--) {
    const day = prevMonthLastDay - i
    const prevMonth = month === 0 ? 11 : month - 1
    const prevYear = month === 0 ? year - 1 : year
    const dateKey = `${prevYear}-${pad(prevMonth + 1)}-${pad(day)}`
    cells.push({
      key: `prev-${dateKey}`,
      day,
      dateKey,
      isToday: dateKey === todayKey,
      isSelected: dateKey === props.modelValue,
      isCurrentMonth: false
    })
  }

  // Current month days
  for (let day = 1; day <= daysInMonth; day++) {
    const dateKey = `${year}-${pad(month + 1)}-${pad(day)}`
    cells.push({
      key: `curr-${dateKey}`,
      day,
      dateKey,
      isToday: dateKey === todayKey,
      isSelected: dateKey === props.modelValue,
      isCurrentMonth: true
    })
  }

  // Always pad next month to fill exactly 42 cells (6 full rows of 7 days)
  const totalNeeded = 42
  const remaining = totalNeeded - cells.length
  const nextMonth = month === 11 ? 0 : month + 1
  const nextYear = month === 11 ? year + 1 : year

  for (let day = 1; day <= remaining; day++) {
    const dateKey = `${nextYear}-${pad(nextMonth + 1)}-${pad(day)}`
    cells.push({
      key: `next-${dateKey}`,
      day,
      dateKey,
      isToday: dateKey === todayKey,
      isSelected: dateKey === props.modelValue,
      isCurrentMonth: false
    })
  }

  return cells
})

const computePlacement = () => {
  if (!wrapperRef.value) return
  const rect = wrapperRef.value.getBoundingClientRect()
  const viewportHeight = window.innerHeight
  const viewportWidth = window.innerWidth

  const spaceBelow = viewportHeight - rect.bottom
  const spaceAbove = rect.top

  const popoverHeight = popoverRef.value ? popoverRef.value.offsetHeight : 320

  if (spaceBelow < popoverHeight && spaceAbove > spaceBelow) {
    placementVertical.value = 'top'
  } else {
    placementVertical.value = 'bottom'
  }

  const spaceRight = viewportWidth - rect.left
  const popoverWidth = popoverRef.value ? popoverRef.value.offsetWidth : 280

  if (spaceRight < popoverWidth && rect.right > popoverWidth) {
    placementHorizontal.value = 'right'
  } else {
    placementHorizontal.value = 'left'
  }
}

let openTimestamp = 0

const togglePopover = () => {
  if (props.disabled) return
  if (!isOpen.value) {
    openTimestamp = Date.now()
    syncCalendarToValue()
    computePlacement()
    isOpen.value = true
    nextTick(() => {
      computePlacement()
    })
  } else {
    isOpen.value = false
  }
}

const closePopover = () => {
  isOpen.value = false
}

const isRecentOpen = () => {
  return Date.now() - openTimestamp < 300
}

const selectCell = (cell: DayCell) => {
  if (!cell.dateKey) return
  emit('update:modelValue', cell.dateKey)
  closePopover()
}

const clearDate = () => {
  emit('update:modelValue', '')
  closePopover()
}

const goPrevMonth = () => {
  if (isRecentOpen()) return
  if (calendarMonth.value === 0) {
    calendarMonth.value = 11
    calendarYear.value -= 1
  } else {
    calendarMonth.value -= 1
  }
  nextTick(computePlacement)
}

const goNextMonth = () => {
  if (isRecentOpen()) return
  if (calendarMonth.value === 11) {
    calendarMonth.value = 0
    calendarYear.value += 1
  } else {
    calendarMonth.value += 1
  }
  nextTick(computePlacement)
}

const goToCurrentMonth = () => {
  const now = new Date()
  calendarYear.value = now.getFullYear()
  calendarMonth.value = now.getMonth()
  nextTick(computePlacement)
}

const handleDocumentClick = (e: MouseEvent) => {
  if (wrapperRef.value && !wrapperRef.value.contains(e.target as Node)) {
    closePopover()
  }
}

const handleWindowScrollOrResize = () => {
  if (isOpen.value) {
    computePlacement()
  }
}

onMounted(() => {
  document.addEventListener('click', handleDocumentClick)
  window.addEventListener('resize', handleWindowScrollOrResize)
  window.addEventListener('scroll', handleWindowScrollOrResize, true)
})

onBeforeUnmount(() => {
  document.removeEventListener('click', handleDocumentClick)
  window.removeEventListener('resize', handleWindowScrollOrResize)
  window.removeEventListener('scroll', handleWindowScrollOrResize, true)
})
</script>

<style scoped>
.app-date-picker-wrapper {
  position: relative;
  display: inline-block;
  width: 100%;
  --calendar-text-strong: var(--text-strong, #10201b);
  --calendar-text-main: var(--text-main, #253730);
  --calendar-text-soft: var(--charcoal);
}

.app-date-picker-input {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  width: 100%;
  height: 38px;
  padding: 0 0.75rem;
  background-color: var(--white, #ffffff);
  border: 1px solid var(--border-light, #e2e8f0);
  border-radius: 8px;
  font-size: 0.85rem;
  color: var(--calendar-text-main);
  cursor: pointer;
  user-select: none;
  transition: border-color 0.18s ease, box-shadow 0.18s ease;
  box-sizing: border-box;
}

.app-date-picker-input:hover:not(.is-disabled) {
  border-color: #39687b;
}

.app-date-picker-input.is-focused {
  border-color: #39687b;
  box-shadow: 0 0 0 3px rgba(57, 104, 123, 0.18);
  outline: none;
}

.app-date-picker-input.is-disabled {
  opacity: 0.6;
  cursor: not-allowed;
  background-color: #f8f9fa;
}

.date-input-icon {
  color: var(--charcoal);
  font-size: 0.85rem;
  flex-shrink: 0;
}

.date-input-text {
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.date-input-text.is-placeholder {
  color: var(--calendar-text-soft);
}

.date-input-clear {
  border: none;
  background: transparent;
  color: var(--calendar-text-soft);
  padding: 0.2rem;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  font-size: 0.75rem;
  transition: color 0.15s ease, background-color 0.15s ease;
}

.date-input-clear:hover {
  color: #e11d48;
  background-color: #ffe4e6;
}

/* Popover Overlay - exact MiniCalendar design with Smart Positioning */
.app-date-picker-popover {
  position: absolute;
  z-index: 100;
  min-width: 270px;
  max-width: 320px;
  width: max-content;
  border-radius: 8px;
  padding: 0.9rem;
  background: var(--white, #ffffff);
  border: 1px solid var(--border-light, #e2e8f0);
  box-shadow: 0 4px 16px var(--shadow, rgba(0, 0, 0, 0.12));
}

.app-date-picker-popover.placement-v-bottom {
  top: calc(100% + 4px);
  bottom: auto;
}

.app-date-picker-popover.placement-v-top {
  bottom: calc(100% + 4px);
  top: auto;
}

.app-date-picker-popover.placement-h-left {
  left: 0;
  right: auto;
}

.app-date-picker-popover.placement-h-right {
  right: 0;
  left: auto;
}

.mini-calendar-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
}

.calendar-nav-button {
  width: 32px;
  height: 32px;
  border: none;
  border-radius: 8px;
  background: #f8f9fa;
  color: var(--calendar-text-main);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: transform 180ms ease, background 180ms ease;
}

.calendar-nav-button:hover {
  transform: translateY(-1px);
  background: #eef1f3;
}

.mini-calendar-heading {
  flex: 1;
  text-align: center;
  user-select: none;
}

.mini-calendar-title {
  font-size: 0.9rem;
  font-weight: 760;
  color: var(--calendar-text-strong);
}

.mini-calendar-toolbar {
  margin-top: 0.6rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
}

.calendar-current-button {
  border: none;
  border-radius: 999px;
  padding: 0.3rem 0.7rem;
  background: #f8f9fa;
  color: var(--calendar-text-main);
  font-size: 0.72rem;
  font-weight: 700;
  cursor: pointer;
}

.calendar-current-button:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.selected-hint {
  font-size: 0.72rem;
  font-weight: 600;
  color: #39687b;
}

.mini-calendar-weekdays {
  margin-top: 0.75rem;
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 0.2rem;
  text-align: center;
}

.mini-calendar-weekdays span {
  font-size: 0.68rem;
  font-weight: 700;
  color: #6e7d77;
}

.mini-calendar-grid {
  margin-top: 0.4rem;
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 0.25rem;
}

.mini-calendar-cell {
  height: 34px;
  border: none;
  border-radius: 8px;
  background: #ffffff;
  color: var(--calendar-text-main);
  font-size: 0.76rem;
  font-weight: 700;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  transition: transform 180ms ease, box-shadow 180ms ease, background 180ms ease, color 180ms ease;
}

.mini-calendar-cell.other-month {
  opacity: 0.38;
}

.cell-num {
  width: 26px;
  height: 26px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  line-height: 1;
}

.mini-calendar-cell:hover {
  transform: translateY(-1px);
  background: #f8f9fa;
}

.mini-calendar-cell.is-today .cell-num {
  background: rgba(57, 104, 123, 0.16);
  outline: 2px solid #39687b;
  color: #39687b;
  font-weight: 800;
}

.mini-calendar-cell.is-selected {
  background: #39687b !important;
  color: #ffffff !important;
}

.mini-calendar-cell.is-selected .cell-num {
  color: #ffffff !important;
  background: transparent !important;
  outline: none !important;
}

/* Transition Animations per Placement */
.calendar-fade-enter-active,
.calendar-fade-leave-active {
  transition: opacity 180ms ease, transform 180ms ease;
}

.calendar-fade-enter-from.placement-v-bottom,
.calendar-fade-leave-to.placement-v-bottom {
  opacity: 0;
  transform: translateY(-6px);
}

.calendar-fade-enter-from.placement-v-top,
.calendar-fade-leave-to.placement-v-top {
  opacity: 0;
  transform: translateY(6px);
}
</style>
