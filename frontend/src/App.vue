<template>
  <div class="app-container">
    <header
      class="header"
      v-if="!isLoginPage"
      @pointermove="handleHeaderPointerMove"
      @pointerleave="resetHeaderPointer"
    >
      <div class="header-ribbon-stage" aria-hidden="true">
        <svg
          class="header-ribbon-svg"
          viewBox="0 0 1200 160"
          preserveAspectRatio="none"
        >
          <defs>
            <linearGradient id="headerRibbonGradient" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stop-color="rgba(255,255,255,0)" />
              <stop offset="18%" stop-color="rgba(182, 240, 214, 0.18)" />
              <stop offset="36%" stop-color="rgba(162, 204, 255, 0.30)" />
              <stop offset="52%" stop-color="rgba(235, 241, 255, 0.38)" />
              <stop offset="70%" stop-color="rgba(163, 225, 199, 0.26)" />
              <stop offset="100%" stop-color="rgba(255,255,255,0)" />
            </linearGradient>

            <filter id="headerRibbonBlur" x="-10%" y="-40%" width="120%" height="180%">
              <feGaussianBlur stdDeviation="2.6" />
            </filter>
          </defs>

          <path
            class="header-ribbon-path ribbon-back"
            d="M -80 92 C 70 18, 220 18, 372 88 S 668 154, 824 88 S 1110 18, 1280 90"
          />
          <path
            class="header-ribbon-path ribbon-front"
            d="M -80 86 C 70 154, 220 154, 372 92 S 668 24, 824 90 S 1110 156, 1280 84"
          />
        </svg>
      </div>

      <div class="header-content">
        <div class="header-left">
          <div class="logo-section">
            <RouterLink to="/dashboard" class="logo">
              <div class="logo-icon">
                <img :src="logo" alt="BIOTech Futures" />
              </div>

              <div class="logo-copy">
                <span class="logo-text">BIOTech Futures Hub</span>
                <span class="logo-subtext">Program workspace</span>
              </div>
            </RouterLink>
          </div>
        </div>

        <div class="header-right">
          <form class="search-shell" @submit.prevent="submitSearch">
            <div class="search-scope-wrap">
              <select v-model="searchScope" class="search-scope" aria-label="Search scope">
                <option value="all">All</option>
                <option value="groups">Groups</option>
                <option value="events">Events</option>
                <option value="announcements">Announcements</option>
                <option value="resources">Resources</option>
              </select>
            </div>

            <div
              class="search-input-wrap"
              :class="{ 'is-focused': isSearchFocused, 'has-value': !!searchQuery }"
            >
              <i class="fas fa-search search-icon"></i>

              <input
                ref="searchInputRef"
                v-model="searchQuery"
                type="text"
                class="search-bar"
                placeholder="Search program content"
                @focus="isSearchFocused = true"
                @blur="isSearchFocused = false"
              />

              <button
                v-if="searchQuery"
                type="button"
                class="search-clear-button"
                aria-label="Clear search"
                @click="clearSearch"
              >
                <i class="fas fa-times"></i>
              </button>
            </div>

            <button
              class="search-submit-button"
              type="submit"
              :disabled="isSearching || !searchQuery.trim()"
            >
              <i class="fas" :class="isSearching ? 'fa-spinner fa-spin' : 'fa-arrow-right'"></i>
            </button>
          </form>

          <div class="header-actions">
            <div class="user-menu">
              <button
                class="user-avatar"
                ref="avatarRef"
                @click="toggleUserMenu"
                type="button"
                aria-label="Open account menu"
              >
                <span class="user-avatar-text">{{ auth.initials }}</span>
                <span v-if="hasUserMenuBadge" class="notification-badge"></span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </header>

    <div class="main-layout" v-if="!isLoginPage">
      <aside class="sidebar">
        <nav class="sidebar-nav">
          <ul class="sidebar-list">
            <li class="sidebar-item">
              <RouterLink
                to="/dashboard"
                class="sidebar-link"
                :class="{ active: route.path === '/dashboard' }"
                @pointermove="handleSidebarLinkPointerMove"
                @pointerleave="resetSidebarLinkPointer"
              >
                <span class="sidebar-link-indicator"></span>
                <span class="sidebar-link-sheen"></span>
                <i class="fas fa-home sidebar-icon"></i>
                <span class="sidebar-label">Home</span>
              </RouterLink>
            </li>

            <li class="sidebar-item">
              <RouterLink
                to="/groups"
                class="sidebar-link"
                :class="{ active: route.path.includes('/groups') }"
                @pointermove="handleSidebarLinkPointerMove"
                @pointerleave="resetSidebarLinkPointer"
              >
                <span class="sidebar-link-indicator"></span>
                <span class="sidebar-link-sheen"></span>
                <i class="fas fa-users sidebar-icon"></i>
                <span class="sidebar-label">Groups</span>
              </RouterLink>
            </li>

            <li class="sidebar-item">
              <RouterLink
                to="/events"
                class="sidebar-link"
                :class="{ active: route.path === '/events' }"
                @pointermove="handleSidebarLinkPointerMove"
                @pointerleave="resetSidebarLinkPointer"
              >
                <span class="sidebar-link-indicator"></span>
                <span class="sidebar-link-sheen"></span>
                <i class="fas fa-calendar sidebar-icon"></i>
                <span class="sidebar-label">Events</span>
              </RouterLink>
            </li>

            <li class="sidebar-item">
              <RouterLink
                to="/announcements"
                class="sidebar-link"
                :class="{ active: route.path === '/announcements' }"
                @pointermove="handleSidebarLinkPointerMove"
                @pointerleave="resetSidebarLinkPointer"
              >
                <span class="sidebar-link-indicator"></span>
                <span class="sidebar-link-sheen"></span>
                <i class="fas fa-bullhorn sidebar-icon"></i>
                <span class="sidebar-label">Announcements</span>
              </RouterLink>
            </li>

            <li class="sidebar-item">
              <RouterLink
                to="/resources"
                class="sidebar-link"
                :class="{ active: route.path === '/resources' }"
                @pointermove="handleSidebarLinkPointerMove"
                @pointerleave="resetSidebarLinkPointer"
              >
                <span class="sidebar-link-indicator"></span>
                <span class="sidebar-link-sheen"></span>
                <i class="fas fa-book sidebar-icon"></i>
                <span class="sidebar-label">Resources</span>
              </RouterLink>
            </li>

            <li class="sidebar-item" v-if="auth.isAdmin">
              <RouterLink
                to="/admin"
                class="sidebar-link"
                :class="{ active: route.path === '/admin' }"
                @pointermove="handleSidebarLinkPointerMove"
                @pointerleave="resetSidebarLinkPointer"
              >
                <span class="sidebar-link-indicator"></span>
                <span class="sidebar-link-sheen"></span>
                <i class="fas fa-cog sidebar-icon"></i>
                <span class="sidebar-label">Admin Panel</span>
              </RouterLink>
            </li>
          </ul>
        </nav>

        <div class="mini-calendar-shell">
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
              <span class="range-hint">Prev • Current • Next</span>
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
                  'is-clickable': cell.clickable
                }"
                :disabled="!cell.day"
                @click="openDayDetails(cell.dateKey)"
              >
                {{ cell.day ?? '' }}
              </button>
            </div>

            <div class="mini-calendar-legend">
              <span class="legend-item">
                <span class="legend-dot legend-today"></span>
                Today
              </span>
              <span class="legend-item">
                <span class="legend-dot legend-holiday"></span>
                Holiday
              </span>
              <span class="legend-item">
                <span class="legend-dot legend-event"></span>
                Event
              </span>
            </div>

            <div class="mini-calendar-footer" v-if="auth.isAdmin">
              <button class="calendar-edit-button" @click="openEditor">
                <i class="fas fa-pen"></i>
                <span>Edit Events</span>
              </button>
            </div>
          </div>

          <transition name="calendar-fade">
            <div v-if="showCalendarOverlay" class="calendar-overlay">
              <div class="calendar-overlay-header">
                <div class="calendar-overlay-title">
                  {{ overlayMode === 'details' ? selectedOverlayTitle : 'Manage events' }}
                </div>
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

                <div v-else class="overlay-empty-state">
                  No special information for this date.
                </div>
              </div>

              <div v-else class="calendar-overlay-body editor-body">
                <div class="editor-readonly-note">
                  Public holidays are read-only. Only events can be edited here.
                </div>

                <div class="editor-form">
                  <div class="form-row">
                    <label class="form-label">Date</label>
                    <input
                      v-model="editForm.date"
                      type="date"
                      class="form-input"
                      :min="minAllowedDate"
                      :max="maxAllowedDate"
                    />
                  </div>

                  <div class="form-row">
                    <label class="form-label">Event title</label>
                    <input
                      v-model="editForm.title"
                      type="text"
                      class="form-input"
                      placeholder="Enter event title and time"
                    />
                  </div>

                  <div class="editor-actions">
                    <button class="editor-primary-button" @click="saveEvent">
                      {{ editForm.id ? 'Update' : 'Add' }}
                    </button>
                    <button class="editor-secondary-button" @click="startNewEvent">
                      New
                    </button>
                  </div>
                </div>

                <div class="editor-list">
                  <div class="editor-list-title">Existing events</div>

                  <div v-if="sortedEvents.length" class="editor-list-scroll">
                    <div v-for="item in sortedEvents" :key="item.id" class="editor-item">
                      <div class="editor-item-main">
                        <span class="editor-type-chip chip-event">Event</span>
                        <div class="editor-item-date">{{ item.date }}</div>
                        <div class="editor-item-title">{{ item.title }}</div>
                      </div>

                      <div class="editor-item-actions">
                        <button class="mini-action-button" @click="editExistingEvent(item)">
                          Edit
                        </button>
                        <button class="mini-action-button danger" @click="deleteEvent(item.id)">
                          Delete
                        </button>
                      </div>
                    </div>
                  </div>

                  <div v-else class="overlay-empty-state">No events yet.</div>
                </div>
              </div>
            </div>
          </transition>
        </div>
      </aside>

      <main class="main-content">
        <RouterView />
      </main>
    </div>

    <RouterView v-else />

    <transition name="menu-fade">
      <div
        ref="userMenuPanelRef"
        :class="['notification-panel', { show: showUserMenu }]"
        v-if="!isLoginPage && showUserMenu"
      >
        <div class="notification-header">
          <div class="account-summary">
            <div class="account-avatar">{{ auth.initials }}</div>

            <div class="account-copy">
              <h4 class="notification-title">My account</h4>
              <p class="account-subtitle">
                {{ auth.isAdmin ? 'Administrator access' : 'Standard member access' }}
              </p>
            </div>
          </div>

          <button @click="showUserMenu = false" class="close-button account-close-button" aria-label="Close">
            <i class="fas fa-times"></i>
          </button>
        </div>

        <div class="notification-panel-section">
          <button class="panel-quick-link" type="button" @click="go('/profile')">
            <span class="panel-quick-icon"><i class="fas fa-user"></i></span>
            <span class="panel-quick-copy">
              <strong>Profile</strong>
              <small>Update your account details</small>
            </span>
          </button>

          <button class="panel-quick-link" type="button" @click="go('/contact')">
            <span class="panel-quick-icon"><i class="fas fa-headset"></i></span>
            <span class="panel-quick-copy">
              <strong>Support</strong>
              <small>Contact an administrator</small>
            </span>
          </button>

          <button class="panel-quick-link" type="button" @click="go('/events')">
            <span class="panel-quick-icon"><i class="fas fa-calendar-alt"></i></span>
            <span class="panel-quick-copy">
              <strong>Upcoming events</strong>
              <small>Open the events workspace</small>
            </span>
          </button>
        </div>

        <div class="notification-panel-footer">
          <button
            class="logout-button"
            type="button"
            @click="handleLogout"
          >
            <i class="fas fa-sign-out-alt"></i>
            <span>Log out</span>
          </button>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter, RouterLink, RouterView } from 'vue-router'
import { useAuthStore } from './stores/auth'
import logo from '@/assets/btf-logo.png'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const handleLogout = async () => {
  await auth.logout()
  go('/login')
}

type ItemType = 'holiday' | 'event'

interface CalendarItem {
  id: number
  date: string
  type: ItemType
  title: string
}

interface SearchPayload {
  query: string
  scope: 'all' | 'groups' | 'events' | 'announcements' | 'resources'
}

const isLoginPage = computed(() => route.path === '/login')

const showUserMenu = ref(false)
const hasUserMenuBadge = ref(true)
const userMenuPanelRef = ref<HTMLElement | null>(null)
const avatarRef = ref<HTMLElement | null>(null)
const searchInputRef = ref<HTMLInputElement | null>(null)

const toggleUserMenu = () => {
  showUserMenu.value = !showUserMenu.value
  if (showUserMenu.value) hasUserMenuBadge.value = false
}

const go = (path: string) => {
  showUserMenu.value = false
  router.push(path)
}

const searchQuery = ref('')
const searchScope = ref<SearchPayload['scope']>('all')
const isSearchFocused = ref(false)
const isSearching = ref(false)

const focusSearch = () => {
  searchInputRef.value?.focus()
}

const buildSearchPayload = (): SearchPayload => {
  return {
    query: searchQuery.value.trim(),
    scope: searchScope.value
  }
}

const requestGlobalSearch = async (_payload: SearchPayload) => {
  return Promise.resolve()
}

const submitSearch = async () => {
  const payload = buildSearchPayload()
  if (!payload.query) return

  isSearching.value = true

  try {
    await requestGlobalSearch(payload)

    router.push({
      path: '/resources',
      query: {
        q: payload.query,
        scope: payload.scope
      }
    })
  } finally {
    isSearching.value = false
  }
}

const clearSearch = () => {
  searchQuery.value = ''
  focusSearch()
}

const handleHeaderPointerMove = (event: PointerEvent) => {
  const target = event.currentTarget as HTMLElement | null
  if (!target) return

  const rect = target.getBoundingClientRect()
  const x = (event.clientX - rect.left) / rect.width
  const y = (event.clientY - rect.top) / rect.height

  target.style.setProperty('--header-pointer-x', `${x}`)
  target.style.setProperty('--header-pointer-y', `${y}`)
  target.style.setProperty('--header-glow-x', `${event.clientX - rect.left}px`)
  target.style.setProperty('--header-glow-y', `${event.clientY - rect.top}px`)
}

const resetHeaderPointer = (event: PointerEvent) => {
  const target = event.currentTarget as HTMLElement | null
  if (!target) return

  target.style.setProperty('--header-pointer-x', '0.5')
  target.style.setProperty('--header-pointer-y', '0.5')
  target.style.setProperty('--header-glow-x', '50%')
  target.style.setProperty('--header-glow-y', '50%')
}

const handleSidebarLinkPointerMove = (event: PointerEvent) => {
  const target = event.currentTarget as HTMLElement | null
  if (!target) return

  const rect = target.getBoundingClientRect()
  target.style.setProperty('--link-pointer-x', `${event.clientX - rect.left}px`)
  target.style.setProperty('--link-pointer-y', `${event.clientY - rect.top}px`)
}

const resetSidebarLinkPointer = (event: PointerEvent) => {
  const target = event.currentTarget as HTMLElement | null
  if (!target) return

  target.style.removeProperty('--link-pointer-x')
  target.style.removeProperty('--link-pointer-y')
}

const handleClickOutside = (event: MouseEvent) => {
  if (!showUserMenu.value) return

  const target = event.target as Node | null
  if (!target) return

  const clickedInsidePanel = userMenuPanelRef.value?.contains(target)
  const clickedAvatar = avatarRef.value?.contains(target)

  if (!clickedInsidePanel && !clickedAvatar) {
    showUserMenu.value = false
  }
}

const handleKeydown = (event: KeyboardEvent) => {
  if (event.key === 'Escape' && showUserMenu.value) {
    showUserMenu.value = false
    avatarRef.value?.focus?.()
  }
}

watch(
  () => route.fullPath,
  () => {
    showUserMenu.value = false
  }
)

onMounted(() => {
  document.addEventListener('click', handleClickOutside)
  document.addEventListener('keydown', handleKeydown)
})

onBeforeUnmount(() => {
  document.removeEventListener('click', handleClickOutside)
  document.removeEventListener('keydown', handleKeydown)
})

const today = new Date()
const weekdayLabels = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

const pad = (value: number) => String(value).padStart(2, '0')

const toDateKey = (year: number, month: number, day: number) => {
  return `${year}-${pad(month + 1)}-${pad(day)}`
}

const parseDateKey = (dateKey: string) => {
  const [year, month, day] = dateKey.split('-').map(Number)
  return new Date(year, month - 1, day)
}

const monthStart = (date: Date) => new Date(date.getFullYear(), date.getMonth(), 1)

const addMonths = (date: Date, delta: number) => {
  return new Date(date.getFullYear(), date.getMonth() + delta, 1)
}

const currentMonthStart = monthStart(today)
const minAllowedMonth = addMonths(currentMonthStart, -1)
const maxAllowedMonth = addMonths(currentMonthStart, 1)

const minAllowedDate = computed(() =>
  toDateKey(minAllowedMonth.getFullYear(), minAllowedMonth.getMonth(), 1)
)

const maxAllowedDate = computed(() => {
  const lastDay = new Date(
    maxAllowedMonth.getFullYear(),
    maxAllowedMonth.getMonth() + 1,
    0
  )

  return toDateKey(
    lastDay.getFullYear(),
    lastDay.getMonth(),
    lastDay.getDate()
  )
})

const calendarYear = ref(today.getFullYear())
const calendarMonth = ref(today.getMonth())

const calendarMonthStart = computed(() => new Date(calendarYear.value, calendarMonth.value, 1))

const canGoPrevMonth = computed(() => {
  return calendarMonthStart.value.getTime() > minAllowedMonth.getTime()
})

const canGoNextMonth = computed(() => {
  return calendarMonthStart.value.getTime() < maxAllowedMonth.getTime()
})

const isCurrentMonth = computed(() => {
  return (
    calendarYear.value === currentMonthStart.getFullYear() &&
    calendarMonth.value === currentMonthStart.getMonth()
  )
})

const calendarTitle = computed(() => {
  return new Intl.DateTimeFormat('en-AU', {
    month: 'long',
    year: 'numeric'
  }).format(calendarMonthStart.value)
})

const todayLabel = computed(() => {
  return new Intl.DateTimeFormat('en-AU', {
    weekday: 'short',
    day: '2-digit',
    month: 'short'
  }).format(today)
})

const holidaySource = ref<CalendarItem[]>([
  { id: 1001, date: '2026-01-01', type: 'holiday', title: 'New Year’s Day' },
  { id: 1002, date: '2026-01-26', type: 'holiday', title: 'Australia Day' },
  { id: 1003, date: '2026-04-03', type: 'holiday', title: 'Good Friday' },
  { id: 1004, date: '2026-04-04', type: 'holiday', title: 'Easter Saturday' },
  { id: 1005, date: '2026-04-05', type: 'holiday', title: 'Easter Sunday' },
  { id: 1006, date: '2026-04-06', type: 'holiday', title: 'Easter Monday' },
  { id: 1007, date: '2026-04-25', type: 'holiday', title: 'Anzac Day' },
  { id: 1008, date: '2026-04-27', type: 'holiday', title: 'Additional Day for Anzac Day' },
  { id: 1009, date: '2026-06-08', type: 'holiday', title: 'King’s Birthday' },
  { id: 1010, date: '2026-10-05', type: 'holiday', title: 'Labour Day' },
  { id: 1011, date: '2026-12-25', type: 'holiday', title: 'Christmas Day' },
  { id: 1012, date: '2026-12-26', type: 'holiday', title: 'Boxing Day' },
  { id: 1013, date: '2026-12-28', type: 'holiday', title: 'Additional Day for Boxing Day' },
  { id: 1014, date: '2027-01-01', type: 'holiday', title: 'New Year’s Day' },
  { id: 1015, date: '2027-01-26', type: 'holiday', title: 'Australia Day' },
  { id: 1016, date: '2027-03-26', type: 'holiday', title: 'Good Friday' },
  { id: 1017, date: '2027-03-27', type: 'holiday', title: 'Easter Saturday' },
  { id: 1018, date: '2027-03-28', type: 'holiday', title: 'Easter Sunday' },
  { id: 1019, date: '2027-03-29', type: 'holiday', title: 'Easter Monday' },
  { id: 1020, date: '2027-04-25', type: 'holiday', title: 'Anzac Day' },
  { id: 1021, date: '2027-04-26', type: 'holiday', title: 'Additional Day for Anzac Day' },
  { id: 1022, date: '2027-06-14', type: 'holiday', title: 'King’s Birthday' }
])

const eventSource = ref<CalendarItem[]>([
  {
    id: 1,
    date: toDateKey(today.getFullYear(), today.getMonth(), today.getDate()),
    type: 'event',
    title: 'Team Check-in 2:30 PM'
  },
  {
    id: 2,
    date: toDateKey(today.getFullYear(), today.getMonth(), Math.min(today.getDate() + 3, 28)),
    type: 'event',
    title: 'Client Demo 10:00 AM'
  }
])

const isDateWithinAllowedWindow = (dateKey: string) => {
  return dateKey >= minAllowedDate.value && dateKey <= maxAllowedDate.value
}

const visibleHolidays = computed(() => {
  return holidaySource.value.filter(item => isDateWithinAllowedWindow(item.date))
})

const visibleEvents = computed(() => {
  return eventSource.value.filter(item => isDateWithinAllowedWindow(item.date))
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
  const firstDay = new Date(year, month, 1)
  const daysInMonth = new Date(year, month + 1, 0).getDate()
  const firstWeekday = (firstDay.getDay() + 6) % 7

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
      clickable: false
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
        year === today.getFullYear() &&
        month === today.getMonth() &&
        day === today.getDate(),
      hasHoliday: items.some(item => item.type === 'holiday'),
      hasEvent: items.some(item => item.type === 'event'),
      clickable: items.length > 0
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
      clickable: false
    })
  }

  return cells
})

const selectedDateKey = ref<string | null>(null)
const showCalendarOverlay = ref(false)
const overlayMode = ref<'details' | 'edit'>('details')

const selectedItems = computed(() => {
  if (!selectedDateKey.value) return []
  return itemMap.value.get(selectedDateKey.value) ?? []
})

const selectedOverlayTitle = computed(() => {
  if (!selectedDateKey.value) return 'Date details'
  const selectedDate = parseDateKey(selectedDateKey.value)
  return new Intl.DateTimeFormat('en-AU', {
    weekday: 'short',
    day: '2-digit',
    month: 'short',
    year: 'numeric'
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
  calendarYear.value = prev.getFullYear()
  calendarMonth.value = prev.getMonth()
  closeCalendarOverlay()
}

const goNextMonth = () => {
  if (!canGoNextMonth.value) return
  const next = addMonths(calendarMonthStart.value, 1)
  calendarYear.value = next.getFullYear()
  calendarMonth.value = next.getMonth()
  closeCalendarOverlay()
}

const goToCurrentMonth = () => {
  calendarYear.value = currentMonthStart.getFullYear()
  calendarMonth.value = currentMonthStart.getMonth()
  closeCalendarOverlay()
}

const editForm = ref<CalendarItem>({
  id: 0,
  date: minAllowedDate.value,
  type: 'event',
  title: ''
})

const sortedEvents = computed(() => {
  return [...visibleEvents.value].sort((a, b) => a.date.localeCompare(b.date))
})

const startNewEvent = () => {
  const defaultDate =
    selectedDateKey.value && isDateWithinAllowedWindow(selectedDateKey.value)
      ? selectedDateKey.value
      : toDateKey(calendarYear.value, calendarMonth.value, 1)

  editForm.value = {
    id: 0,
    date: defaultDate,
    type: 'event',
    title: ''
  }
}

const openEditor = () => {
  overlayMode.value = 'edit'
  showCalendarOverlay.value = true
  startNewEvent()
}

const editExistingEvent = (item: CalendarItem) => {
  editForm.value = { ...item, type: 'event' }
}

const saveCalendarEventRequest = async (_event: CalendarItem) => {
  return Promise.resolve()
}

const deleteCalendarEventRequest = async (_id: number) => {
  return Promise.resolve()
}

const saveEvent = async () => {
  const title = editForm.value.title.trim()
  const date = editForm.value.date

  if (!title || !date) return
  if (!isDateWithinAllowedWindow(date)) return

  const payload: CalendarItem = {
    id: editForm.value.id || Date.now(),
    date,
    type: 'event',
    title
  }

  await saveCalendarEventRequest(payload)

  if (editForm.value.id) {
    const index = eventSource.value.findIndex(item => item.id === editForm.value.id)
    if (index !== -1) {
      eventSource.value[index] = payload
    }
  } else {
    eventSource.value.push(payload)
  }

  selectedDateKey.value = date
  startNewEvent()
}

const deleteEvent = async (id: number) => {
  await deleteCalendarEventRequest(id)
  eventSource.value = eventSource.value.filter(item => item.id !== id)

  if (editForm.value.id === id) {
    startNewEvent()
  }
}

watch(showCalendarOverlay, value => {
  if (value && overlayMode.value === 'edit') {
    startNewEvent()
  }
})
</script>

<style scoped>
:global(html),
:global(body),
:global(#app) {
  width: 100%;
  max-width: none;
  margin: 0;
  padding: 0;
}

:global(body) {
  overflow-x: hidden;
  background: #f5f7f6;
}

:deep(:root) {
  --surface-0: #f7f9f8;
  --surface-1: #eef2f0;
  --surface-2: #e5ebe8;
  --surface-3: #d9e2de;

  --text-strong: #10201b;
  --text-main: #253730;
  --text-soft: #66756f;

  --line-soft: rgba(14, 31, 25, 0.08);
  --line-mid: rgba(14, 31, 25, 0.14);

  --brand-950: #07110f;
  --brand-900: #0c1815;
  --brand-850: #11211c;
  --brand-800: #173029;
  --brand-700: #23463b;
  --brand-600: #3d6a5b;
  --brand-500: #5f8c7c;
  --brand-400: #88aea0;

  --shadow-soft: 0 12px 28px rgba(7, 17, 15, 0.06);
  --shadow-panel: 0 24px 60px rgba(7, 17, 15, 0.16);
}

* {
  box-sizing: border-box;
}

button,
input,
select {
  font: inherit;
}

.app-container {
  width: 100%;
  max-width: none;
  min-height: 100vh;
  margin: 0;
  background:
    radial-gradient(circle at top left, rgba(130, 160, 145, 0.07), transparent 24%),
    radial-gradient(circle at right top, rgba(160, 182, 210, 0.08), transparent 20%),
    linear-gradient(180deg, #f7f9f8 0%, #f2f5f3 100%);
}

.header {
  --header-pointer-x: 0.5;
  --header-pointer-y: 0.5;
  --header-glow-x: 50%;
  --header-glow-y: 50%;
  position: sticky;
  top: 0;
  z-index: 24;
  overflow: hidden;
  backdrop-filter: blur(20px) saturate(135%);
  -webkit-backdrop-filter: blur(20px) saturate(135%);
  background:
    radial-gradient(
      440px circle at var(--header-glow-x) var(--header-glow-y),
      rgba(214, 229, 255, 0.12) 0%,
      rgba(182, 229, 208, 0.08) 18%,
      transparent 58%
    ),
    linear-gradient(
      180deg,
      rgba(14, 23, 20, 0.96) 0%,
      rgba(11, 19, 17, 0.96) 100%
    );
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  box-shadow:
    0 18px 44px rgba(7, 13, 12, 0.18),
    inset 0 1px 0 rgba(255, 255, 255, 0.06);
}

.header::before {
  content: '';
  position: absolute;
  inset: 0;
  background:
    linear-gradient(
      90deg,
      transparent 0%,
      rgba(255, 255, 255, 0.03) 22%,
      rgba(255, 255, 255, 0.01) 34%,
      transparent 52%
    );
  pointer-events: none;
}

.header::after {
  content: '';
  position: absolute;
  inset: auto 0 0 0;
  height: 1px;
  background:
    linear-gradient(
      90deg,
      transparent 0%,
      rgba(188, 212, 202, 0.2) 18%,
      rgba(160, 190, 220, 0.28) 50%,
      rgba(188, 212, 202, 0.2) 82%,
      transparent 100%
    );
  pointer-events: none;
}

.header-ribbon-stage {
  position: absolute;
  inset: 0;
  pointer-events: none;
  z-index: 1;
  opacity: 0.92;
}

.header-ribbon-svg {
  position: absolute;
  left: 18%;
  right: 18%;
  top: 6px;
  height: 100%;
  width: auto;
  min-width: 48%;
  transform:
    translateX(calc((var(--header-pointer-x) - 0.5) * 26px))
    translateY(calc((var(--header-pointer-y) - 0.5) * 12px));
  transition: transform 220ms ease;
  overflow: visible;
}

.header-ribbon-path {
  fill: none;
  stroke: url(#headerRibbonGradient);
  stroke-linecap: round;
  stroke-linejoin: round;
}

.ribbon-back {
  stroke-width: 12;
  opacity: 0.34;
  filter: url(#headerRibbonBlur);
  stroke-dasharray: 320 40 180 54;
  animation: ribbonDriftA 18s linear infinite;
}

.ribbon-front {
  stroke-width: 6.5;
  opacity: 0.82;
  stroke-dasharray: 220 32 120 28;
  animation: ribbonDriftB 14s linear infinite;
}

.header-content {
  position: relative;
  z-index: 2;
  width: 100%;
  max-width: none;
  min-height: 78px;
  padding: 0 1.25rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1.1rem;
}

.header-left,
.header-right {
  display: flex;
  align-items: center;
  position: relative;
  z-index: 2;
}

.header-left {
  gap: 1rem;
  min-width: 0;
}

.header-right {
  margin-left: auto;
  gap: 0.8rem;
  flex: 0 1 auto;
  min-width: 0;
}

.logo-section {
  min-width: 0;
}

.logo {
  display: inline-flex;
  align-items: center;
  gap: 0.85rem;
  text-decoration: none;
}

.logo-icon {
  width: 44px;
  height: 44px;
  border-radius: 14px;
  overflow: hidden;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.96) 0%, rgba(226, 232, 228, 0.92) 100%);
  border: 1px solid rgba(255, 255, 255, 0.28);
  box-shadow:
    0 10px 24px rgba(0, 0, 0, 0.16),
    inset 0 1px 0 rgba(255, 255, 255, 0.8);
}

.logo-icon img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.logo-copy {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.logo-text {
  color: rgba(246, 249, 248, 0.96);
  font-size: 0.98rem;
  font-weight: 760;
  letter-spacing: 0.01em;
  white-space: nowrap;
}

.logo-subtext {
  color: rgba(197, 207, 202, 0.78);
  font-size: 0.72rem;
  font-weight: 560;
  white-space: nowrap;
}

.search-shell {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  width: min(100%, 720px);
  min-width: 0;
  padding: 0.48rem;
  border-radius: 20px;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.06) 0%, rgba(255, 255, 255, 0.03) 100%);
  border: 1px solid rgba(255, 255, 255, 0.08);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.06),
    0 8px 24px rgba(0, 0, 0, 0.1);
}

.search-scope-wrap,
.search-input-wrap {
  display: flex;
  align-items: center;
  min-width: 0;
  border-radius: 14px;
  background:
    linear-gradient(180deg, rgba(245, 248, 247, 0.96) 0%, rgba(233, 238, 235, 0.92) 100%);
  border: 1px solid rgba(17, 30, 25, 0.08);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.8);
}

.search-scope-wrap {
  flex: 0 0 114px;
  padding: 0 0.5rem;
}

.search-scope {
  width: 100%;
  border: none;
  background: transparent;
  color: #16241f;
  font-size: 0.82rem;
  font-weight: 650;
  outline: none;
  padding: 0.55rem 0.3rem;
  cursor: pointer;
}

.search-input-wrap {
  flex: 1 1 auto;
  gap: 0.45rem;
  padding: 0 0.72rem;
  transition: border-color 180ms ease, box-shadow 180ms ease, transform 180ms ease;
}

.search-input-wrap.is-focused {
  border-color: rgba(126, 157, 197, 0.46);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.86),
    0 0 0 4px rgba(146, 177, 214, 0.12);
}

.search-icon {
  color: #61736c;
  font-size: 0.82rem;
  flex-shrink: 0;
}

.search-bar {
  flex: 1 1 auto;
  min-width: 0;
  border: none;
  background: transparent;
  color: #16241f;
  padding: 0.68rem 0;
  outline: none;
  font-size: 0.88rem;
}

.search-bar::placeholder {
  color: #7a8a84;
}

.search-clear-button {
  border: none;
  background: transparent;
  color: #677873;
  cursor: pointer;
  padding: 0.18rem;
  border-radius: 8px;
  transition: background 180ms ease, color 180ms ease;
}

.search-clear-button:hover {
  background: rgba(16, 32, 27, 0.08);
  color: #1a2d27;
}

.search-submit-button {
  width: 42px;
  height: 42px;
  flex: 0 0 42px;
  border: none;
  border-radius: 14px;
  background:
    linear-gradient(180deg, #2e4a40 0%, #22362f 100%);
  color: #ffffff;
  cursor: pointer;
  box-shadow:
    0 10px 22px rgba(10, 19, 16, 0.22),
    inset 0 1px 0 rgba(255, 255, 255, 0.08);
  transition: transform 180ms ease, box-shadow 180ms ease, opacity 180ms ease;
}

.search-submit-button:hover:not(:disabled) {
  transform: translateY(-1px) scale(1.02);
  box-shadow:
    0 14px 28px rgba(10, 19, 16, 0.28),
    0 0 18px rgba(147, 181, 220, 0.14);
}

.search-submit-button:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

.header-actions {
  display: flex;
  align-items: center;
}

.user-menu {
  display: flex;
  align-items: center;
}

.user-avatar {
  position: relative;
  width: 44px;
  height: 44px;
  border-radius: 14px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background:
    radial-gradient(circle at 30% 28%, rgba(255, 255, 255, 0.1), transparent 38%),
    linear-gradient(180deg, #314e43 0%, #22362f 100%);
  color: #ffffff;
  cursor: pointer;
  box-shadow:
    0 10px 24px rgba(8, 14, 13, 0.22),
    inset 0 1px 0 rgba(255, 255, 255, 0.08);
  transition: transform 180ms ease, box-shadow 180ms ease;
}

.user-avatar:hover {
  transform: translateY(-1px) scale(1.02);
  box-shadow:
    0 14px 30px rgba(8, 14, 13, 0.3),
    0 0 16px rgba(151, 177, 209, 0.12);
}

.user-avatar-text {
  font-size: 0.9rem;
  font-weight: 800;
  letter-spacing: 0.03em;
}

.notification-badge {
  position: absolute;
  top: 4px;
  right: 4px;
  width: 10px;
  height: 10px;
  border-radius: 999px;
  background: #ff5d62;
  border: 2px solid rgba(12, 24, 21, 0.92);
  box-shadow: 0 4px 10px rgba(255, 93, 98, 0.35);
}

.main-layout {
  display: flex;
  align-items: flex-start;
  width: 100%;
  max-width: none;
  min-height: calc(100vh - 78px);
}

.sidebar {
  position: sticky;
  top: 78px;
  align-self: flex-start;
  height: calc(100vh - 78px);
  overflow-y: auto;
  flex-shrink: 0;
  width: 272px;
  min-width: 272px;
  padding: 0.85rem 0.72rem 1rem;
  background:
    linear-gradient(180deg, rgba(244, 247, 245, 0.82) 0%, rgba(237, 242, 239, 0.92) 100%);
  border-right: 1px solid rgba(19, 33, 28, 0.08);
  box-shadow:
    inset -1px 0 0 rgba(255, 255, 255, 0.56),
    12px 0 32px rgba(12, 18, 16, 0.04);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  display: flex;
  flex-direction: column;
}

.sidebar-nav {
  flex: 0 0 auto;
  padding: 0;
}

.sidebar-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 0.32rem;
}

.sidebar-item + .sidebar-item {
  margin-top: 0;
}

.sidebar-link {
  --link-pointer-x: 50%;
  --link-pointer-y: 50%;
  position: relative;
  display: flex;
  align-items: center;
  gap: 0.82rem;
  min-height: 46px;
  padding: 0.82rem 0.9rem 0.82rem 1rem;
  border-radius: 16px;
  color: var(--text-main);
  text-decoration: none;
  overflow: hidden;
  border: 1px solid transparent;
  background:
    radial-gradient(
      120px circle at var(--link-pointer-x) var(--link-pointer-y),
      rgba(210, 226, 255, 0.34) 0%,
      rgba(210, 226, 255, 0.12) 26%,
      transparent 62%
    ),
    linear-gradient(180deg, rgba(255, 255, 255, 0.42) 0%, rgba(255, 255, 255, 0.18) 100%);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.42),
    0 1px 0 rgba(14, 31, 25, 0.02);
  transition:
    transform 220ms cubic-bezier(0.22, 1, 0.36, 1),
    border-color 220ms ease,
    box-shadow 220ms ease,
    color 220ms ease,
    background 220ms ease;
}

.sidebar-link-indicator {
  position: absolute;
  left: 8px;
  top: 50%;
  width: 3px;
  height: 22px;
  border-radius: 999px;
  background:
    linear-gradient(180deg, rgba(88, 122, 111, 0.18) 0%, rgba(88, 122, 111, 0.52) 100%);
  transform: translateY(-50%) scaleY(0.42);
  transform-origin: center;
  transition: transform 220ms ease, opacity 220ms ease, background 220ms ease;
  opacity: 0.55;
}

.sidebar-link-sheen {
  position: absolute;
  inset: 1px;
  border-radius: inherit;
  background:
    linear-gradient(
      118deg,
      transparent 0%,
      transparent 26%,
      rgba(255, 255, 255, 0.42) 40%,
      rgba(215, 231, 255, 0.18) 48%,
      transparent 62%,
      transparent 100%
    );
  transform: translateX(-34%);
  opacity: 0;
  pointer-events: none;
  transition: transform 380ms ease, opacity 240ms ease;
}

.sidebar-icon {
  position: relative;
  z-index: 2;
  width: 18px;
  text-align: center;
  font-size: 0.9rem;
  color: #546861;
  transition: color 220ms ease, transform 220ms ease;
}

.sidebar-label {
  position: relative;
  z-index: 2;
  font-size: 0.9rem;
  font-weight: 650;
  letter-spacing: 0.01em;
}

.sidebar-link:hover {
  transform: translateX(4px);
  border-color: rgba(126, 157, 197, 0.18);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.58),
    0 10px 18px rgba(22, 34, 30, 0.06);
}

.sidebar-link:hover .sidebar-link-sheen {
  opacity: 1;
  transform: translateX(0);
}

.sidebar-link:hover .sidebar-link-indicator {
  transform: translateY(-50%) scaleY(0.9);
}

.sidebar-link:hover .sidebar-icon {
  color: #37584c;
  transform: translateX(1px);
}

.sidebar-link.active {
  color: #13241f;
  border-color: rgba(87, 110, 160, 0.14);
  background:
    radial-gradient(
      140px circle at var(--link-pointer-x) var(--link-pointer-y),
      rgba(214, 226, 255, 0.42) 0%,
      rgba(214, 226, 255, 0.18) 28%,
      transparent 64%
    ),
    linear-gradient(180deg, rgba(255, 255, 255, 0.72) 0%, rgba(242, 246, 244, 0.94) 100%);
  box-shadow:
    0 12px 24px rgba(22, 34, 30, 0.08),
    inset 0 1px 0 rgba(255, 255, 255, 0.76);
}

.sidebar-link.active .sidebar-link-indicator {
  opacity: 1;
  transform: translateY(-50%) scaleY(1);
  background:
    linear-gradient(180deg, rgba(76, 104, 96, 0.86) 0%, rgba(112, 141, 198, 0.88) 100%);
}

.sidebar-link.active .sidebar-icon {
  color: #2a433a;
}

.main-content {
  flex: 1;
  min-width: 0;
  padding: 1rem;
}

.mini-calendar-shell {
  margin-top: 0.9rem;
  position: relative;
}

.mini-calendar {
  border-radius: 22px;
  padding: 0.95rem;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.68) 0%, rgba(246, 249, 247, 0.9) 100%);
  border: 1px solid rgba(19, 33, 28, 0.08);
  box-shadow:
    0 12px 34px rgba(17, 24, 22, 0.05),
    inset 0 1px 0 rgba(255, 255, 255, 0.66);
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
  background: rgba(17, 30, 25, 0.04);
  color: var(--text-main);
  cursor: pointer;
  transition: transform 180ms ease, background 180ms ease, color 180ms ease;
}

.calendar-nav-button:hover:not(:disabled) {
  transform: translateY(-1px);
  background: rgba(17, 30, 25, 0.08);
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
  color: var(--text-strong);
}

.mini-calendar-subtitle {
  margin-top: 0.16rem;
  font-size: 0.72rem;
  color: var(--text-soft);
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
  background: rgba(17, 30, 25, 0.06);
  color: var(--text-main);
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
  color: var(--text-soft);
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
  height: 34px;
  border: none;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.58);
  color: var(--text-main);
  font-size: 0.76rem;
  font-weight: 700;
  cursor: pointer;
  transition:
    transform 180ms ease,
    box-shadow 180ms ease,
    background 180ms ease,
    color 180ms ease;
}

.mini-calendar-cell:not(.is-empty):hover {
  transform: translateY(-1px);
  box-shadow: 0 8px 18px rgba(12, 18, 16, 0.06);
}

.mini-calendar-cell.is-empty {
  visibility: hidden;
  pointer-events: none;
}

.mini-calendar-cell.is-clickable {
  background: rgba(255, 255, 255, 0.92);
}

.mini-calendar-cell.is-today {
  outline: 2px solid rgba(87, 110, 160, 0.28);
  outline-offset: -2px;
}

.mini-calendar-cell.is-holiday {
  color: #9d4f57;
}

.mini-calendar-cell.is-event {
  box-shadow: inset 0 -2px 0 rgba(76, 104, 96, 0.34);
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
  color: var(--text-soft);
}

.legend-dot {
  width: 8px;
  height: 8px;
  border-radius: 999px;
}

.legend-today {
  background: #7a95c2;
}

.legend-holiday {
  background: #d48691;
}

.legend-event {
  background: #5f8c7c;
}

.mini-calendar-footer {
  margin-top: 0.9rem;
}

.calendar-edit-button {
  width: 100%;
  border: none;
  border-radius: 16px;
  padding: 0.82rem 0.95rem;
  background: linear-gradient(180deg, #274039 0%, #1b2d28 100%);
  color: #ffffff;
  font-weight: 760;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.48rem;
  box-shadow: 0 12px 28px rgba(16, 26, 23, 0.18);
  transition: transform 0.18s ease, box-shadow 0.18s ease;
}

.calendar-edit-button:hover {
  transform: translateY(-1px);
  box-shadow: 0 14px 30px rgba(16, 26, 23, 0.24);
}

.calendar-overlay {
  position: absolute;
  left: 0;
  right: 0;
  top: 0;
  margin-top: 0.2rem;
  border-radius: 22px;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.82) 0%, rgba(245, 248, 247, 0.96) 100%);
  border: 1px solid rgba(17, 30, 25, 0.08);
  box-shadow: 0 24px 48px rgba(7, 17, 15, 0.12);
  backdrop-filter: blur(18px);
  -webkit-backdrop-filter: blur(18px);
  z-index: 6;
}

.calendar-overlay-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.8rem;
  padding: 0.9rem 0.95rem 0.7rem;
  border-bottom: 1px solid rgba(17, 30, 25, 0.06);
}

.calendar-overlay-title {
  font-size: 0.9rem;
  font-weight: 760;
  color: var(--text-strong);
}

.calendar-close-button,
.close-button {
  width: 32px;
  height: 32px;
  border: none;
  border-radius: 12px;
  background: rgba(17, 30, 25, 0.05);
  color: var(--text-main);
  cursor: pointer;
  transition: transform 180ms ease, background 180ms ease;
}

.calendar-close-button:hover,
.close-button:hover {
  transform: translateY(-1px);
  background: rgba(17, 30, 25, 0.08);
}

.calendar-overlay-body {
  padding: 0.85rem 0.95rem 0.95rem;
}

.overlay-card {
  padding: 0.8rem 0.85rem;
  border-radius: 16px;
  border: 1px solid rgba(17, 30, 25, 0.06);
  background: rgba(255, 255, 255, 0.84);
}

.overlay-card + .overlay-card {
  margin-top: 0.55rem;
}

.holiday-card {
  border-color: rgba(212, 134, 145, 0.18);
}

.event-card {
  border-color: rgba(95, 140, 124, 0.18);
}

.overlay-card-type {
  font-size: 0.68rem;
  font-weight: 760;
  color: var(--text-soft);
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

.overlay-card-title {
  margin-top: 0.32rem;
  font-size: 0.82rem;
  font-weight: 700;
  color: var(--text-strong);
}

.overlay-empty-state {
  border-radius: 16px;
  padding: 1rem;
  background: rgba(255, 255, 255, 0.72);
  color: var(--text-soft);
  text-align: center;
  font-size: 0.78rem;
}

.editor-body {
  display: grid;
  gap: 0.9rem;
}

.editor-readonly-note {
  border-radius: 14px;
  padding: 0.72rem 0.8rem;
  background: rgba(87, 110, 160, 0.08);
  color: #4d5f83;
  font-size: 0.74rem;
  line-height: 1.45;
}

.editor-form {
  display: grid;
  gap: 0.7rem;
}

.form-row {
  display: grid;
  gap: 0.34rem;
}

.form-label {
  font-size: 0.75rem;
  font-weight: 700;
  color: var(--text-main);
}

.form-input {
  width: 100%;
  border: 1px solid rgba(17, 30, 25, 0.1);
  border-radius: 14px;
  padding: 0.72rem 0.8rem;
  background: rgba(255, 255, 255, 0.9);
  color: var(--text-strong);
  outline: none;
  transition: border-color 180ms ease, box-shadow 180ms ease;
}

.form-input:focus {
  border-color: rgba(126, 157, 197, 0.46);
  box-shadow: 0 0 0 4px rgba(146, 177, 214, 0.12);
}

.editor-actions {
  display: flex;
  gap: 0.55rem;
}

.editor-primary-button,
.editor-secondary-button,
.mini-action-button {
  border: none;
  border-radius: 14px;
  padding: 0.72rem 0.9rem;
  cursor: pointer;
  font-weight: 760;
  transition: transform 180ms ease, box-shadow 180ms ease, background 180ms ease;
}

.editor-primary-button {
  background: linear-gradient(180deg, #274039 0%, #1b2d28 100%);
  color: #ffffff;
  box-shadow: 0 10px 22px rgba(16, 26, 23, 0.16);
}

.editor-secondary-button,
.mini-action-button {
  background: rgba(17, 30, 25, 0.06);
  color: var(--text-main);
}

.editor-primary-button:hover,
.editor-secondary-button:hover,
.mini-action-button:hover {
  transform: translateY(-1px);
}

.editor-list {
  display: grid;
  gap: 0.7rem;
}

.editor-list-title {
  font-size: 0.8rem;
  font-weight: 760;
  color: var(--text-strong);
}

.editor-list-scroll {
  display: grid;
  gap: 0.55rem;
  max-height: 240px;
  overflow-y: auto;
  padding-right: 0.2rem;
}

.editor-item {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.75rem;
  padding: 0.8rem;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.82);
  border: 1px solid rgba(17, 30, 25, 0.06);
}

.editor-item-main {
  min-width: 0;
  display: grid;
  gap: 0.2rem;
}

.editor-type-chip {
  display: inline-flex;
  width: fit-content;
  border-radius: 999px;
  padding: 0.22rem 0.52rem;
  font-size: 0.64rem;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

.chip-event {
  background: rgba(95, 140, 124, 0.12);
  color: #45675b;
}

.editor-item-date {
  font-size: 0.72rem;
  color: var(--text-soft);
}

.editor-item-title {
  font-size: 0.8rem;
  font-weight: 700;
  color: var(--text-strong);
  line-height: 1.35;
}

.editor-item-actions {
  display: flex;
  gap: 0.45rem;
  flex-shrink: 0;
}

.mini-action-button.danger {
  background: rgba(208, 92, 101, 0.12);
  color: #8f3d46;
}

.notification-panel {
  position: fixed;
  top: 88px;
  right: 18px;
  width: 320px;
  max-width: calc(100vw - 36px);
  border-radius: 22px;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.72) 0%, rgba(245, 248, 247, 0.94) 100%);
  border: 1px solid rgba(17, 30, 25, 0.08);
  backdrop-filter: blur(18px);
  -webkit-backdrop-filter: blur(18px);
  box-shadow: 0 24px 48px rgba(7, 17, 15, 0.12);
  overflow: hidden;
  z-index: 40;
}

.notification-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.8rem;
  padding: 0.95rem 0.95rem 0.75rem;
  border-bottom: 1px solid rgba(17, 30, 25, 0.06);
}

.account-summary {
  display: flex;
  align-items: center;
  gap: 0.7rem;
  min-width: 0;
}

.account-avatar {
  width: 42px;
  height: 42px;
  border-radius: 14px;
  display: grid;
  place-items: center;
  background: linear-gradient(180deg, #314e43 0%, #22362f 100%);
  color: #ffffff;
  font-size: 0.9rem;
  font-weight: 800;
  box-shadow: 0 10px 24px rgba(8, 14, 13, 0.16);
}

.account-copy {
  min-width: 0;
}

.notification-title {
  margin: 0;
  font-size: 0.9rem;
  color: var(--text-strong);
}

.account-subtitle {
  margin: 0.16rem 0 0;
  font-size: 0.74rem;
  color: var(--text-soft);
  line-height: 1.4;
}

.account-close-button {
  flex-shrink: 0;
}

.notification-panel-section {
  padding: 0.85rem 0.85rem 0.4rem;
  display: grid;
  gap: 0.55rem;
}

.panel-quick-link {
  width: 100%;
  border: none;
  border-radius: 18px;
  padding: 0.76rem 0.8rem;
  background: rgba(255, 255, 255, 0.78);
  border: 1px solid rgba(17, 30, 25, 0.05);
  display: flex;
  align-items: center;
  gap: 0.7rem;
  cursor: pointer;
  text-align: left;
  transition: transform 180ms ease, box-shadow 180ms ease, background 180ms ease;
}

.panel-quick-link:hover {
  transform: translateY(-1px);
  box-shadow: 0 12px 24px rgba(12, 18, 16, 0.06);
}

.panel-quick-icon {
  width: 38px;
  height: 38px;
  border-radius: 14px;
  background: rgba(17, 30, 25, 0.05);
  display: grid;
  place-items: center;
  color: var(--brand-700);
  flex-shrink: 0;
}

.panel-quick-copy {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.panel-quick-copy strong {
  font-size: 0.82rem;
  color: var(--text-strong);
  line-height: 1.2;
}

.panel-quick-copy small {
  margin-top: 0.16rem;
  font-size: 0.7rem;
  color: var(--text-soft);
  line-height: 1.3;
}

.notification-panel-footer {
  padding: 0 0.8rem 0.9rem;
}

.logout-button {
  width: 100%;
  border: none;
  border-radius: 16px;
  padding: 0.82rem 0.95rem;
  background: linear-gradient(180deg, #274039 0%, #1b2d28 100%);
  color: #ffffff;
  font-weight: 800;
  font-size: 0.78rem;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.48rem;
  box-shadow: 0 12px 28px rgba(16, 26, 23, 0.18);
  transition: transform 0.18s ease, box-shadow 0.18s ease;
}

.logout-button:hover {
  transform: translateY(-1px);
  box-shadow: 0 14px 30px rgba(16, 26, 23, 0.24);
}

.calendar-fade-enter-active,
.calendar-fade-leave-active,
.menu-fade-enter-active,
.menu-fade-leave-active {
  transition: opacity 0.18s ease, transform 0.18s ease;
}

.calendar-fade-enter-from,
.calendar-fade-leave-to,
.menu-fade-enter-from,
.menu-fade-leave-to {
  opacity: 0;
  transform: translateY(4px) scale(0.985);
}

@keyframes ribbonDriftA {
  0% {
    stroke-dashoffset: 0;
    transform: translateX(0);
  }
  50% {
    stroke-dashoffset: -180;
    transform: translateX(-10px);
  }
  100% {
    stroke-dashoffset: -360;
    transform: translateX(0);
  }
}

@keyframes ribbonDriftB {
  0% {
    stroke-dashoffset: 0;
    transform: translateX(0);
  }
  50% {
    stroke-dashoffset: 160;
    transform: translateX(12px);
  }
  100% {
    stroke-dashoffset: 320;
    transform: translateX(0);
  }
}

@media (max-width: 1024px) {
  .header-ribbon-svg {
    left: 24%;
    right: 10%;
    opacity: 0.72;
  }

  .search-shell {
    max-width: 560px;
  }

  .search-input-wrap {
    max-width: 260px;
  }

  .logo-subtext {
    display: none;
  }

  .sidebar {
    width: 256px;
    min-width: 256px;
  }
}

@media (max-width: 768px) {
  .header-ribbon-stage {
    display: none;
  }

  .header-content {
    flex-wrap: wrap;
    padding: 0.75rem 0.85rem;
    min-height: auto;
  }

  .header-right {
    width: 100%;
    margin-left: 0;
    justify-content: space-between;
    gap: 0.6rem;
  }

  .search-shell {
    flex: 1 1 auto;
    width: 100%;
    max-width: none;
    min-width: 0;
  }

  .search-scope-wrap {
    flex: 0 0 82px;
  }

  .search-input-wrap {
    flex: 1 1 auto;
    width: auto;
    min-width: 0;
    max-width: none;
  }

  .main-layout {
    flex-direction: column;
    min-height: auto;
  }

  .sidebar {
    position: static;
    top: auto;
    align-self: auto;
    height: auto;
    width: 100%;
    min-width: 100%;
    overflow-y: visible;
    padding: 0.75rem;
  }

  .main-content {
    width: 100%;
    padding: 0.85rem;
  }

  .mini-calendar-shell {
    margin-top: 0.5rem;
  }

  .notification-panel {
    top: 88px;
    right: 12px;
    left: 12px;
    width: auto;
    max-width: none;
  }
}
</style>