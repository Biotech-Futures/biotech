<template>
  <div class="mini-calendar-shell" :class="`mini-calendar-shell--${placement}`">
    <div class="mini-calendar">
      <div class="mini-calendar-topbar">
        <button
          class="calendar-nav-button"
          :disabled="!canGoPrevMonth"
          @click="goPrevMonth"
          aria-label="Previous month"
        >
          <i class="fas fa-chevron-left"></i>
        </button>

        <div class="mini-calendar-heading">
          <div class="mini-calendar-title">{{ calendarTitle }}</div>
          <div class="mini-calendar-subtitle">{{ todayLabel }}</div>
        </div>

        <button
          class="calendar-nav-button"
          :disabled="!canGoNextMonth"
          @click="goNextMonth"
          aria-label="Next month"
        >
          <i class="fas fa-chevron-right"></i>
        </button>
      </div>

      <div class="mini-calendar-toolbar">
        <button
          class="calendar-current-button"
          :disabled="isCurrentMonth"
          @click="goToCurrentMonth"
        >
          Current
        </button>
        <span class="range-hint">Prev / Current / Next</span>
      </div>

      <div class="mini-calendar-weekdays">
        <span v-for="label in weekdayLabels" :key="label">{{ label }}</span>
      </div>

      <div class="mini-calendar-grid">
        <button
          v-for="cell in calendarDays"
          :key="cell.key"
          class="mini-calendar-cell"
          :class="{
            'is-empty': !cell.day,
            'is-today': cell.isToday,
            'is-holiday': cell.hasHoliday,
            'is-event': cell.hasEvent,
            'is-clickable': cell.clickable,
          }"
          :disabled="!cell.day"
          @click="openDayDetails(cell.dateKey)"
        >
          <span class="cell-num">{{ cell.day ?? '' }}</span>
          <span v-if="cell.day && (cell.hasEvent || cell.hasHoliday)" class="cell-dots">
            <span v-if="cell.hasEvent" class="cell-dot dot-event"></span>
            <span v-if="cell.hasHoliday" class="cell-dot dot-holiday"></span>
          </span>
        </button>
      </div>

      <div class="mini-calendar-legend">
        <span class="legend-item">
          <span class="legend-dot legend-today"></span>
          Today
        </span>
        <span class="legend-item">
          <span class="legend-dot legend-event"></span>
          Event
        </span>
        <span class="legend-item">
          <span class="legend-dot legend-holiday"></span>
          Holiday
        </span>
      </div>
    </div>

    <transition name="calendar-fade">
      <div v-if="showCalendarOverlay" class="calendar-overlay">
        <div class="calendar-overlay-header">
          <div class="calendar-overlay-title">{{ selectedOverlayTitle }}</div>
          <button class="calendar-close-button" @click="closeCalendarOverlay" aria-label="Close">
            <i class="fas fa-times"></i>
          </button>
        </div>

        <div v-if="overlayMode === 'details'" class="calendar-overlay-body">
          <template v-if="selectedItems.length">
            <div
              v-for="item in selectedItems"
              :key="item.id"
              class="overlay-card"
              :class="item.type === 'holiday' ? 'holiday-card' : 'event-card'"
            >
              <div class="overlay-card-type">
                {{ item.type === 'holiday' ? 'Holiday' : 'Event' }}
              </div>
              <div class="overlay-card-title">{{ item.title }}</div>
            </div>
          </template>

          <div v-else class="overlay-empty-state">No special information for this date.</div>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

import { fetchEvents, type BackendEvent } from '@/utils/eventsAPI'
import {
  formatEventTimeRange,
  formatTimeZoneLabel,
  getTimeZoneDateParts,
  toTimeZoneDateKey,
} from '@/utils/date'
import { useAuthStore } from '@/stores/auth'

withDefaults(
  defineProps<{
    placement?: 'sidebar' | 'hero'
  }>(),
  {
    placement: 'sidebar',
  },
)

type ItemType = 'holiday' | 'event'

interface CalendarItem {
  id: number
  date: string
  type: ItemType
  title: string
}

const auth = useAuthStore()
const currentTimeZone = computed(() => auth.timeZone)
const currentDateParts = getTimeZoneDateParts(new Date(), currentTimeZone.value) ?? {
  year: new Date().getUTCFullYear(),
  month: new Date().getUTCMonth() + 1,
  day: new Date().getUTCDate(),
}
const today = new Date(Date.UTC(currentDateParts.year, currentDateParts.month - 1, currentDateParts.day))
const weekdayLabels = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

const pad = (value: number) => String(value).padStart(2, '0')

const toDateKey = (year: number, month: number, day: number) => {
  return `${year}-${pad(month + 1)}-${pad(day)}`
}

const parseDateKey = (dateKey: string) => {
  const [year, month, day] = dateKey.split('-').map(Number)
  return new Date(Date.UTC(year, month - 1, day))
}

const monthStart = (date: Date) => new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), 1))

const addMonths = (date: Date, delta: number) => {
  return new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth() + delta, 1))
}

const currentMonthStart = monthStart(today)
const minAllowedMonth = addMonths(currentMonthStart, -1)
const maxAllowedMonth = addMonths(currentMonthStart, 1)

const minAllowedDate = computed(() =>
  toDateKey(minAllowedMonth.getUTCFullYear(), minAllowedMonth.getUTCMonth(), 1),
)

const maxAllowedDate = computed(() => {
  const lastDay = new Date(
    Date.UTC(maxAllowedMonth.getUTCFullYear(), maxAllowedMonth.getUTCMonth() + 1, 0),
  )

  return toDateKey(lastDay.getUTCFullYear(), lastDay.getUTCMonth(), lastDay.getUTCDate())
})

const calendarYear = ref(today.getUTCFullYear())
const calendarMonth = ref(today.getUTCMonth())

const calendarMonthStart = computed(
  () => new Date(Date.UTC(calendarYear.value, calendarMonth.value, 1)),
)

const canGoPrevMonth = computed(() => {
  return calendarMonthStart.value.getTime() > minAllowedMonth.getTime()
})

const canGoNextMonth = computed(() => {
  return calendarMonthStart.value.getTime() < maxAllowedMonth.getTime()
})

const isCurrentMonth = computed(() => {
  return (
    calendarYear.value === currentMonthStart.getUTCFullYear() &&
    calendarMonth.value === currentMonthStart.getUTCMonth()
  )
})

const calendarTitle = computed(() => {
  return new Intl.DateTimeFormat('en-AU', {
    timeZone: 'UTC',
    month: 'long',
    year: 'numeric',
  }).format(calendarMonthStart.value)
})

const todayLabel = computed(() => {
  const label = new Intl.DateTimeFormat('en-AU', {
    timeZone: 'UTC',
    weekday: 'short',
    day: '2-digit',
    month: 'short',
  }).format(today)
  return `${label} ${formatTimeZoneLabel(currentTimeZone.value)}`
})

const eventSource = ref<CalendarItem[]>([])
let calendarLoadHandle: number | null = null

type IdleSchedulerWindow = Window & {
  requestIdleCallback?: (callback: () => void, options?: { timeout?: number }) => number
  cancelIdleCallback?: (handle: number) => void
}

const isDateWithinAllowedWindow = (dateKey: string) => {
  return dateKey >= minAllowedDate.value && dateKey <= maxAllowedDate.value
}

const visibleHolidays = computed(() => {
  const items: CalendarItem[] = []
  const cursor = parseDateKey(minAllowedDate.value)
  const end = parseDateKey(maxAllowedDate.value)

  while (cursor.getTime() <= end.getTime()) {
    const weekday = cursor.getUTCDay()
    if (weekday === 0 || weekday === 6) {
      const date = toDateKey(cursor.getUTCFullYear(), cursor.getUTCMonth(), cursor.getUTCDate())
      items.push({
        id: -Number(date.replace(/-/g, '')),
        date,
        type: 'holiday',
        title: weekday === 6 ? 'Saturday' : 'Sunday',
      })
    }
    cursor.setUTCDate(cursor.getUTCDate() + 1)
  }

  return items
})

const visibleEvents = computed(() => {
  return eventSource.value.filter((item) => isDateWithinAllowedWindow(item.date))
})

const itemMap = computed(() => {
  const map = new Map<string, CalendarItem[]>()

  for (const item of [...visibleHolidays.value, ...visibleEvents.value]) {
    if (!map.has(item.date)) map.set(item.date, [])
    map.get(item.date)!.push(item)
  }

  return map
})

const calendarDays = computed(() => {
  const year = calendarYear.value
  const month = calendarMonth.value
  const firstDay = new Date(Date.UTC(year, month, 1))
  const daysInMonth = new Date(Date.UTC(year, month + 1, 0)).getUTCDate()
  const firstWeekday = (firstDay.getUTCDay() + 6) % 7

  const cells: Array<{
    key: string
    day: number | null
    dateKey: string | null
    isToday: boolean
    hasHoliday: boolean
    hasEvent: boolean
    clickable: boolean
  }> = []

  for (let i = 0; i < firstWeekday; i++) {
    cells.push({
      key: `empty-start-${i}`,
      day: null,
      dateKey: null,
      isToday: false,
      hasHoliday: false,
      hasEvent: false,
      clickable: false,
    })
  }

  for (let day = 1; day <= daysInMonth; day++) {
    const dateKey = toDateKey(year, month, day)
    const items = itemMap.value.get(dateKey) ?? []

    cells.push({
      key: `day-${dateKey}`,
      day,
      dateKey,
      isToday:
        year === today.getUTCFullYear() &&
        month === today.getUTCMonth() &&
        day === today.getUTCDate(),
      hasHoliday: items.some((item) => item.type === 'holiday'),
      hasEvent: items.some((item) => item.type === 'event'),
      clickable: items.length > 0,
    })
  }

  while (cells.length < 42) {
    cells.push({
      key: `empty-end-${cells.length}`,
      day: null,
      dateKey: null,
      isToday: false,
      hasHoliday: false,
      hasEvent: false,
      clickable: false,
    })
  }

  return cells
})

const selectedDateKey = ref<string | null>(null)
const showCalendarOverlay = ref(false)
const overlayMode = ref<'details'>('details')

const selectedItems = computed(() => {
  if (!selectedDateKey.value) return []
  return itemMap.value.get(selectedDateKey.value) ?? []
})

const selectedOverlayTitle = computed(() => {
  if (!selectedDateKey.value) return 'Date details'
  const selectedDate = parseDateKey(selectedDateKey.value)
  return new Intl.DateTimeFormat('en-AU', {
    timeZone: 'UTC',
    weekday: 'short',
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  }).format(selectedDate)
})

const closeCalendarOverlay = () => {
  showCalendarOverlay.value = false
}

const openDayDetails = (dateKey: string | null) => {
  if (!dateKey) return
  const items = itemMap.value.get(dateKey) ?? []
  if (!items.length) return

  selectedDateKey.value = dateKey
  overlayMode.value = 'details'
  showCalendarOverlay.value = true
}

const goPrevMonth = () => {
  if (!canGoPrevMonth.value) return
  const prev = addMonths(calendarMonthStart.value, -1)
  calendarYear.value = prev.getUTCFullYear()
  calendarMonth.value = prev.getUTCMonth()
  closeCalendarOverlay()
}

const goNextMonth = () => {
  if (!canGoNextMonth.value) return
  const next = addMonths(calendarMonthStart.value, 1)
  calendarYear.value = next.getUTCFullYear()
  calendarMonth.value = next.getUTCMonth()
  closeCalendarOverlay()
}

const goToCurrentMonth = () => {
  calendarYear.value = currentMonthStart.getUTCFullYear()
  calendarMonth.value = currentMonthStart.getUTCMonth()
  closeCalendarOverlay()
}

const extractEventItems = (data: BackendEvent[] | { results?: BackendEvent[] }) => {
  if (Array.isArray(data)) return data
  if (Array.isArray(data?.results)) return data.results
  return []
}

const formatEventTime = (event: BackendEvent) => {
  return formatEventTimeRange(event.start_datetime, event.ends_datetime, currentTimeZone.value)
}

const normalizeCalendarEvent = (event: BackendEvent): CalendarItem | null => {
  if (!event.start_datetime) return null
  const dateKey = toTimeZoneDateKey(event.start_datetime, currentTimeZone.value)
  if (!dateKey) return null
  const time = formatEventTime(event)
  const name = event.event_name || 'Untitled event'

  return {
    id: event.id,
    date: dateKey,
    type: 'event',
    title: time ? `${name} ${time}` : name,
  }
}

async function loadCalendarEvents() {
  try {
    const data = await fetchEvents({ when: 'upcoming', page_size: 30, ordering: 'start_datetime' })
    eventSource.value = extractEventItems(data)
      .map(normalizeCalendarEvent)
      .filter((item): item is CalendarItem => item !== null)
  } catch (error) {
    console.error('Failed to load mini-calendar events:', error)
    eventSource.value = []
  }
}

const scheduleCalendarEventLoad = () => {
  if (typeof window === 'undefined') {
    void loadCalendarEvents()
    return
  }

  const idleWindow = window as IdleSchedulerWindow
  if (idleWindow.requestIdleCallback) {
    calendarLoadHandle = idleWindow.requestIdleCallback(
      () => {
        calendarLoadHandle = null
        void loadCalendarEvents()
      },
      { timeout: 1200 },
    )
    return
  }

  calendarLoadHandle = window.setTimeout(() => {
    calendarLoadHandle = null
    void loadCalendarEvents()
  }, 250)
}

onMounted(scheduleCalendarEventLoad)

onBeforeUnmount(() => {
  if (calendarLoadHandle === null || typeof window === 'undefined') return

  const idleWindow = window as IdleSchedulerWindow
  if (idleWindow.cancelIdleCallback) {
    idleWindow.cancelIdleCallback(calendarLoadHandle)
  } else {
    window.clearTimeout(calendarLoadHandle)
  }
  calendarLoadHandle = null
})
</script>

<style scoped>
.mini-calendar-shell {
  width: 100%;
  margin-top: 0.9rem;
  position: relative;
  --calendar-text-strong: var(--text-strong, #10201b);
  --calendar-text-main: var(--text-main, #253730);
  --calendar-text-soft: var(--text-soft, #66756f);
}

.mini-calendar {
  border-radius: 8px;
  padding: 0.95rem;
  background: var(--white);
  border: 1px solid var(--border-light);
  box-shadow: 0 2px 4px var(--shadow);
}

.mini-calendar-shell--hero {
  height: 100%;
  margin-top: 0;
  display: flex;
}

.mini-calendar-shell--hero .mini-calendar {
  flex: 1;
  min-height: 100%;
}

.mini-calendar-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.6rem;
}

.calendar-nav-button {
  width: 34px;
  height: 34px;
  border: none;
  border-radius: 12px;
  background: #f8f9fa;
  color: var(--calendar-text-main);
  cursor: pointer;
  transition:
    transform 180ms ease,
    background 180ms ease,
    color 180ms ease;
}

.calendar-nav-button:hover:not(:disabled) {
  transform: translateY(-1px);
  background: #eef1f3;
}

.calendar-nav-button:disabled {
  opacity: 0.42;
  cursor: not-allowed;
}

.mini-calendar-heading {
  flex: 1;
  min-width: 0;
  text-align: center;
}

.mini-calendar-title {
  font-size: 0.94rem;
  font-weight: 760;
  color: var(--calendar-text-strong);
}

.mini-calendar-subtitle {
  margin-top: 0.16rem;
  font-size: 0.72rem;
  color: var(--calendar-text-soft);
}

.mini-calendar-toolbar {
  margin-top: 0.8rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.6rem;
}

.calendar-current-button {
  border: none;
  border-radius: 999px;
  padding: 0.44rem 0.78rem;
  background: #f8f9fa;
  color: var(--calendar-text-main);
  font-size: 0.74rem;
  font-weight: 700;
  cursor: pointer;
}

.calendar-current-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.range-hint {
  font-size: 0.72rem;
  color: var(--calendar-text-soft);
}

.mini-calendar-weekdays {
  margin-top: 0.85rem;
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 0.25rem;
  text-align: center;
}

.mini-calendar-weekdays span {
  font-size: 0.68rem;
  font-weight: 700;
  color: #6e7d77;
}

.mini-calendar-grid {
  margin-top: 0.45rem;
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 0.28rem;
}

.mini-calendar-cell {
  height: 40px;
  border: none;
  border-radius: 12px;
  background: #ffffff;
  color: var(--calendar-text-main);
  font-size: 0.76rem;
  font-weight: 700;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 2px;
  padding: 3px 0 2px;
  transition:
    transform 180ms ease,
    box-shadow 180ms ease,
    background 180ms ease,
    color 180ms ease;
}

.cell-num {
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  line-height: 1;
  transition:
    background 180ms ease,
    color 180ms ease,
    outline-color 180ms ease;
}

.cell-dots {
  display: flex;
  align-items: center;
  gap: 3px;
  height: 6px;
}

.cell-dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  flex-shrink: 0;
}

.dot-event {
  background: #22c55e;
}

.dot-holiday {
  background: #ef4444;
}

.mini-calendar-cell:not(.is-empty):hover {
  transform: translateY(-1px);
  box-shadow: 0 2px 4px var(--shadow);
}

.mini-calendar-cell.is-empty {
  visibility: hidden;
  pointer-events: none;
}

.mini-calendar-cell.is-clickable {
  background: #ffffff;
}

.mini-calendar-cell.is-today .cell-num {
  background: rgba(59, 130, 246, 0.15);
  outline: 2px solid #3b82f6;
  color: #1d4ed8;
  font-weight: 800;
}

.mini-calendar-legend {
  margin-top: 0.85rem;
  display: flex;
  flex-wrap: wrap;
  gap: 0.6rem 0.8rem;
}

.legend-item {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.7rem;
  color: var(--calendar-text-soft);
}

.legend-dot {
  width: 8px;
  height: 8px;
  border-radius: 999px;
}

.legend-today {
  background: #3b82f6;
  outline: 2px solid #3b82f6;
  outline-offset: 1px;
  width: 6px;
  height: 6px;
}

.legend-event {
  background: #22c55e;
}

.legend-holiday {
  background: #ef4444;
}

.calendar-overlay {
  position: absolute;
  left: 0;
  right: 0;
  top: 0;
  margin-top: 0.2rem;
  border-radius: 8px;
  background: var(--white);
  border: 1px solid var(--border-light);
  box-shadow: 0 4px 12px var(--shadow);
  backdrop-filter: none;
  -webkit-backdrop-filter: none;
  z-index: 6;
}

.calendar-overlay-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.8rem;
  padding: 0.9rem 0.95rem 0.7rem;
  border-bottom: 1px solid var(--border-light);
}

.calendar-overlay-title {
  font-size: 0.9rem;
  font-weight: 760;
  color: var(--calendar-text-strong);
}

.calendar-close-button {
  width: 32px;
  height: 32px;
  border: none;
  border-radius: 12px;
  background: #f8f9fa;
  color: var(--calendar-text-main);
  cursor: pointer;
  transition:
    transform 180ms ease,
    background 180ms ease;
}

.calendar-close-button:hover {
  transform: translateY(-1px);
  background: #eef1f3;
}

.calendar-overlay-body {
  padding: 0.85rem 0.95rem 0.95rem;
}

.overlay-card {
  padding: 0.8rem 0.85rem;
  border-radius: 8px;
  border: 1px solid var(--border-light);
  background: #ffffff;
}

.overlay-card + .overlay-card {
  margin-top: 0.55rem;
}

.holiday-card {
  border-color: rgba(212, 134, 145, 0.18);
}

.event-card {
  border-color: var(--border-light);
}

.overlay-card-type {
  font-size: 0.68rem;
  font-weight: 760;
  color: var(--calendar-text-soft);
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

.overlay-card-title {
  margin-top: 0.32rem;
  font-size: 0.82rem;
  font-weight: 700;
  color: var(--calendar-text-strong);
}

.overlay-empty-state {
  border-radius: 8px;
  padding: 1rem;
  background: #f8f9fa;
  color: var(--calendar-text-soft);
  text-align: center;
  font-size: 0.78rem;
}

.calendar-fade-enter-active,
.calendar-fade-leave-active {
  transition:
    opacity 180ms ease,
    transform 180ms ease;
}

.calendar-fade-enter-from,
.calendar-fade-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}

@media (max-width: 768px) {
  .mini-calendar-shell {
    margin-top: 0.5rem;
  }
}
</style>
