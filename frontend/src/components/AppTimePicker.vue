<template>
  <!-- A time of day, "HH:MM" in 24 hours, picked from an hour and its
       minutes. This is its box: the page's classes, styles and data-test land
       here, so it's drawn as the page's other boxes are. The hours and minutes
       open in a panel over the page, where nothing can cut them off. -->
  <div
    ref="boxRef"
    v-bind="boxAttrs"
    class="app-time"
    :class="{ 'is-open': open, 'is-disabled': disabled }"
    @mousedown.prevent
    @click="onBoxClick"
  >
    <button
      :id="id"
      ref="fieldRef"
      v-bind="fieldAttrs"
      type="button"
      class="app-time__field"
      :class="{ 'is-empty': !parts.hour }"
      aria-haspopup="dialog"
      :aria-expanded="open"
      :aria-controls="panelId"
      :disabled="disabled"
      data-test="app-time-field"
      @keydown="onKeydown"
      @blur="close"
    >
      {{ parts.hour ? `${parts.hour}:${parts.minute}` : placeholder }}
    </button>
    <i class="far fa-clock app-time__icon" aria-hidden="true"></i>
    <Teleport to="body">
      <div
        v-if="open"
        :id="panelId"
        ref="panelRef"
        class="app-time__panel"
        role="dialog"
        aria-label="Pick a time"
        :style="panelStyle"
        @mousedown.prevent.stop
        @click.stop
      >
        <div class="app-time__column">
          <span class="app-time__heading">Hour</span>
          <ul ref="hourListRef" class="app-time__list" role="listbox" aria-label="Hour">
            <li
              v-for="(hour, index) in HOURS"
              :key="hour"
              role="option"
              class="app-time__option"
              :class="{ 'is-selected': hour === parts.hour, 'is-active': column === 'hour' && index === activeHour }"
              :aria-selected="hour === parts.hour"
              :data-hour="hour"
              @mousedown.prevent="pickHour(hour)"
            >
              {{ hour }}
            </li>
          </ul>
        </div>
        <span class="app-time__colon" aria-hidden="true">:</span>
        <div class="app-time__column">
          <span class="app-time__heading">Min</span>
          <ul ref="minuteListRef" class="app-time__list" role="listbox" aria-label="Minutes">
            <li
              v-for="(minute, index) in minutes"
              :key="minute"
              role="option"
              class="app-time__option"
              :class="{
                'is-selected': parts.hour && minute === parts.minute,
                'is-active': column === 'minute' && index === activeMinute,
                'is-disabled': !parts.hour
              }"
              :aria-selected="Boolean(parts.hour) && minute === parts.minute"
              :aria-disabled="!parts.hour || undefined"
              :data-minute="minute"
              @mousedown.prevent="pickMinute(minute)"
            >
              {{ minute }}
            </li>
          </ul>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script lang="ts">
// Each panel its own id, across every app on the page.
let lastPanelId = 0
const nextPanelId = () => `app-time-${++lastPanelId}`
</script>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, useAttrs, watch } from 'vue'

defineOptions({ inheritAttrs: false })

const props = withDefaults(
  defineProps<{
    /** "HH:MM", or empty for none yet. */
    modelValue?: string
    id?: string
    /** Shown while there's no time. */
    placeholder?: string
    disabled?: boolean
    /** The minutes offered, in steps of this many. */
    step?: number
  }>(),
  {
    modelValue: '',
    id: undefined,
    placeholder: '--:--',
    disabled: false,
    step: 5
  }
)

const emit = defineEmits<{
  'update:modelValue': [value: string]
  /** After a time is picked, as an input's change event. */
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

const twoDigits = (count: number) => String(count).padStart(2, '0')
const HOURS = Array.from({ length: 24 }, (_, hour) => twoDigits(hour))

// The time as its hour and minutes; seconds, if any came with it, are dropped.
const parts = computed(() => {
  const match = /^(\d{1,2}):(\d{2})/.exec(props.modelValue || '')
  return match ? { hour: twoDigits(Number(match[1])), minute: match[2]! } : { hour: '', minute: '' }
})

// Every step's minutes, and one saved between them, so it can still be seen.
const minutes = computed(() => {
  const step = Math.max(1, Math.min(60, Math.floor(props.step)))
  const list = Array.from({ length: Math.ceil(60 / step) }, (_, index) => twoDigits(index * step))
  const saved = parts.value.minute
  return saved && !list.includes(saved) ? [...list, saved].sort() : list
})

// --- where the keyboard is: a column, and a row in each -----------------------

const column = ref<'hour' | 'minute'>('hour')
const activeHour = ref(0)
const activeMinute = ref(0)

// The row in the middle of its list, so the ones either side show too.
const centre = (list: HTMLElement | null, index: number) => {
  const row = list?.children[index] as HTMLElement | undefined
  if (list && row) list.scrollTop = row.offsetTop - (list.clientHeight - row.offsetHeight) / 2
}

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
      centre(hourListRef.value, activeHour.value)
      centre(minuteListRef.value, activeMinute.value)
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

const openPanel = () => {
  if (open.value || props.disabled) return
  column.value = 'hour'
  // The time it has, or 9 am to start from.
  activeHour.value = parts.value.hour ? HOURS.indexOf(parts.value.hour) : 9
  activeMinute.value = Math.max(0, minutes.value.indexOf(parts.value.minute))
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

// An hour keeps its minutes, or takes :00, and the minutes are next.
const pickHour = (hour: string) => {
  set(`${hour}:${parts.value.minute || '00'}`)
  activeHour.value = HOURS.indexOf(hour)
  column.value = 'minute'
  activeMinute.value = Math.max(0, minutes.value.indexOf(parts.value.minute || '00'))
}

// The minutes finish it, once there's an hour.
const pickMinute = (minute: string) => {
  if (!parts.value.hour) return
  set(`${parts.value.hour}:${minute}`)
  close()
}

const move = (by: number) => {
  if (column.value === 'hour') {
    activeHour.value = (activeHour.value + by + HOURS.length) % HOURS.length
    centre(hourListRef.value, activeHour.value)
  } else {
    activeMinute.value = (activeMinute.value + by + minutes.value.length) % minutes.value.length
    centre(minuteListRef.value, activeMinute.value)
  }
}

const onKeydown = (event: KeyboardEvent) => {
  if (!open.value) {
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault()
      openPanel()
    }
    return
  }
  switch (event.key) {
    case 'ArrowDown':
    case 'ArrowUp':
      event.preventDefault()
      move(event.key === 'ArrowDown' ? 1 : -1)
      break
    case 'ArrowLeft':
      event.preventDefault()
      column.value = 'hour'
      break
    case 'ArrowRight':
      event.preventDefault()
      if (parts.value.hour) column.value = 'minute'
      break
    case 'Enter':
      event.preventDefault()
      if (column.value === 'hour') pickHour(HOURS[activeHour.value]!)
      else pickMinute(minutes.value[activeMinute.value]!)
      break
    case 'Escape':
      // Closes the panel, not the sheet or dialog it's in.
      event.preventDefault()
      event.stopPropagation()
      close()
      break
  }
}
</script>

<style scoped>
/* The box as a text box is drawn when the page doesn't draw it. No
   specificity, so a page's own classes and styles win. */
:where(.app-time) {
  display: inline-block;
  padding: 0.4rem 0.6rem;
  border: 1px solid var(--border-light);
  border-radius: 6px;
  background: var(--surface-elevated);
  color: var(--teal);
  font: inherit;
  vertical-align: middle;
}

.app-time {
  position: relative;
  box-sizing: border-box;
  /* The time in the middle of a box given a fixed height. */
  align-content: center;
  cursor: pointer;
}

.app-time.is-disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

.app-time:has(.app-time__field:focus-visible),
.app-time.is-open {
  outline: 2px solid var(--dark-green);
  outline-offset: 2px;
}

/* The time shown, with room on the right for the clock. */
.app-time__field {
  display: block;
  box-sizing: border-box;
  width: 100%;
  margin: 0;
  padding: 0 1.5rem 0 0;
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

.app-time.app-input .app-time__field {
  line-height: inherit;
}

.app-time__field.is-empty {
  color: var(--text-muted);
}

.app-time__icon {
  position: absolute;
  top: 50%;
  right: 0.6rem;
  color: var(--text-muted);
  font-size: 0.85em;
  pointer-events: none;
  transform: translateY(-50%);
}

.app-time.is-open .app-time__icon {
  color: var(--teal);
}

/* The panel: the hours, a colon, the minutes. */
.app-time__panel {
  position: fixed;
  z-index: 2200;
  display: flex;
  align-items: stretch;
  gap: 0.15rem;
  box-sizing: border-box;
  padding: 0.4rem;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  background: var(--surface-elevated);
  box-shadow: 0 6px 18px var(--shadow, rgba(0, 0, 0, 0.12));
}

.app-time__column {
  display: flex;
  flex-direction: column;
}

.app-time__heading {
  padding: 0.1rem 0 0.35rem;
  color: var(--text-muted);
  font-size: 0.7em;
  font-weight: 700;
  letter-spacing: 0.05em;
  text-align: center;
  text-transform: uppercase;
}

.app-time__list {
  position: relative;
  height: 12em;
  margin: 0;
  padding: 0 0.15rem;
  overflow-y: auto;
  list-style: none;
  /* Scrolled with the wheel, a finger or the arrow keys: no scrollbar. */
  scrollbar-width: none;
}

.app-time__list::-webkit-scrollbar {
  display: none;
}

.app-time__colon {
  align-self: center;
  padding-top: 1.2em;
  color: var(--text-muted);
  font-weight: 700;
}

.app-time__option {
  padding: 0.1rem 0.4rem;
  line-height: 1.35;
  border-radius: 6px;
  color: var(--teal);
  font-variant-numeric: tabular-nums;
  text-align: center;
  cursor: pointer;
}

.app-time__option:hover,
.app-time__option.is-active {
  background: var(--light-green);
}

.app-time__option.is-selected {
  background: var(--dark-green);
  color: var(--white, #ffffff);
  font-weight: 600;
}

.app-time__option.is-disabled {
  background: transparent;
  color: var(--text-muted);
  cursor: not-allowed;
}
</style>
