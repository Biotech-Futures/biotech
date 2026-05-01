<template>
  <!-- Dashboard shell -->
  <div
    ref="dashboardShellRef"
    class="content-area dashboard-page-shell"
    :class="[isDayMode ? 'is-day-mode' : 'is-night-mode', { 'is-fx-disabled': !isDashboardFxRunningAllowed }]"
    :style="dashboardThemeStyle"
  >


    <div class="dashboard-page-inner">
      <canvas ref="dashboardFxCanvasRef" class="dashboard-fx-canvas" aria-hidden="true"></canvas>

      <div class="dashboard-backdrop-orb orb-one" aria-hidden="true"></div>
      <div class="dashboard-backdrop-orb orb-two" aria-hidden="true"></div>
      <div class="dashboard-backdrop-grid" aria-hidden="true"></div>


      <section class="dashboard-hero-shell">


        <div class="dashboard-hero-card interactive-surface">


          <div class="dashboard-theme-rail">
            <button
              type="button"
              class="theme-rail-trigger"
              :aria-pressed="isDayMode"
              :title="isDayMode ? 'Switch to night mode' : 'Switch to day mode'"
              @click.stop="toggleSurfaceMode"
            >
              <i :class="isDayMode ? 'fas fa-sun' : 'fas fa-moon'"></i>
              <span>{{ currentSurfaceModeLabel }}</span>
            </button>
            <button
              type="button"
              class="theme-rail-trigger fx-rail-trigger"
              :class="{ 'is-muted': !isDashboardFxRunningAllowed }"
              :aria-pressed="isDashboardFxRunningAllowed"
              :title="dashboardFxToggleTitle"
              @click.stop="toggleDashboardFx"
            >
              <i :class="isDashboardFxRunningAllowed ? 'fas fa-bolt' : 'fas fa-battery-half'"></i>
              <span>{{ dashboardFxToggleLabel }}</span>
            </button>
          </div>


          <div class="dashboard-hero-main">


            <div class="dashboard-hero-copy">


              <div class="hero-eyebrow-row">


                <span class="hero-eyebrow">{{ heroEyebrow }}</span>


              </div>


              <h1 class="hero-title">Welcome back, {{ displayName }}</h1>


              <div class="hero-meta-row">
                <span
                  v-for="chip in heroMetaChips"
                  :key="chip.key"
                  class="hero-meta-chip"
                  :class="`hero-meta-chip--${chip.tone}`"
                >
                  <span class="hero-meta-chip-label">{{ chip.label }}</span>
                  <strong class="hero-meta-chip-value">{{ chip.value }}</strong>
                </span>
              </div>

              <p class="dashboard-subtext">
                Curated overview for {{ roleLabel.toLowerCase() }} workflow, current milestones, and the next best actions.
              </p>

              <p class="dashboard-hero-message">
                {{ heroMessage }}
              </p>


              <div class="hero-highlight-wrap">
                <span
                  v-for="item in headerHighlights"
                  :key="item.key"
                  class="status-pill"
                >
                  {{ item.label }}
                </span>
              </div>


            </div>


            <div class="dashboard-hero-aside">


              <div
                v-if="activeShowcaseItem"
                class="showcase-card interactive-surface"
                @mouseenter="stopShowcaseAutoplay"
                @mouseleave="startShowcaseAutoplay"
              >



                <div class="showcase-heading-row">
                  <div>

                    <div class="showcase-kicker">BIOTECH HIGHLIGHTS</div>


                    <div class="showcase-mini-label">Official-style image and info rotation</div>
                  </div>


                  <div class="showcase-controls">
                    <button type="button" class="showcase-nav-btn" @click="goToPrevShowcase">
                      <i class="fas fa-chevron-left"></i>
                    </button>
                    <button type="button" class="showcase-nav-btn" @click="goToNextShowcase">
                      <i class="fas fa-chevron-right"></i>
                    </button>
                  </div>
                </div>


                <transition name="showcase-fade" mode="out-in">


                  <div :key="activeShowcaseItem.id" class="showcase-body">


                    <div
                      class="showcase-image"
                      :style="{ backgroundImage: `url(${activeShowcaseItem.image})` }"
                    >

                      <div class="showcase-image-overlay"></div>
                    </div>


                    <div class="showcase-copy">


                      <h3 class="showcase-title">{{ activeShowcaseItem.title }}</h3>


                      <p class="showcase-summary">{{ activeShowcaseItem.summary }}</p>

                      <div class="showcase-footer">


                        <div class="showcase-dots">
                          <button
                            v-for="(item, index) in biotechShowcaseItems"
                            :key="item.id || index"
                            type="button"
                            class="showcase-dot"
                            :class="{ active: index === activeShowcaseIndex }"
                            @click="goToShowcase(index)"
                          ></button>
                        </div>


                        <button
                          type="button"
                          class="showcase-link-btn"
                          @click="openShowcaseLink(activeShowcaseItem)"
                        >
                          Explore
                          <i class="fas fa-arrow-right"></i>
                        </button>
                      </div>
                    </div>
                  </div>
                </transition>
              </div>
            </div>
          </div>

        </div>
      </section>


      <div v-if="loadError" class="dashboard-alert">
        <i class="fas fa-circle-info"></i>
        <span>{{ loadError }}</span>
      </div>


      <section class="dashboard-section">
        <div class="dashboard-section-grid summary-grid">


          <article
            v-for="item in summaryWidgets"
            :key="item.key"
            class="summary-card interactive-surface"
            :class="getAccentClass(item.accent)"
          >
            <div class="summary-card-top">
              <div class="summary-icon-wrap">
                <i :class="item.icon"></i>
              </div>
              <span class="summary-label">{{ item.title }}</span>
            </div>

            <div class="summary-card-value">{{ item.value }}</div>
            <div class="summary-card-subtext">{{ item.subtext }}</div>
          </article>
        </div>
      </section>


      <section class="dashboard-section">
          <article class="surface-card feature-card progress-card">
            <div class="surface-card-header">
              <div>
                <p class="surface-kicker">Overview</p>
                <h3 class="surface-card-title">Progress Snapshot</h3>
              </div>
            </div>

            <div class="progress-layout">


              <div class="progress-ring-shell">
                <div class="progress-ring-aura"></div>
                <div class="progress-ring-track"></div>
                <div class="progress-ring-orbit progress-ring-orbit--outer"></div>
                <div class="progress-ring-orbit progress-ring-orbit--inner"></div>
                <span class="progress-ring-marker" :style="progressMarkerStyle"></span>
                <span class="progress-ring-spark progress-ring-spark--one"></span>
                <span class="progress-ring-spark progress-ring-spark--two"></span>
                <div class="progress-ring" :style="progressCircleStyle">
                  <div class="progress-ring-inner">


                    <div class="progress-value">{{ progressSnapshot.completionRate }}%</div>


                    <div class="progress-label">Completion</div>
                    <div class="progress-caption">{{ progressStatusCaption }}</div>
                  </div>
                </div>
              </div>


              <div class="progress-details">


                <div class="progress-detail-row">
                  <span>Tasks</span>
                  <strong>{{ progressSnapshot.completedTasks }}/{{ progressSnapshot.totalTasks }}</strong>
                </div>


                <div class="progress-detail-row">
                  <span>Current stage</span>
                  <strong>{{ progressSnapshot.currentWeek }}</strong>
                </div>


                <div class="progress-detail-row">
                  <span>Next milestone</span>
                  <strong>{{ progressSnapshot.nextMilestone }}</strong>
                </div>


                <div class="progress-detail-row">
                  <span>Due</span>
                  <strong>{{ formatDateAU(progressSnapshot.nextMilestoneDate) || 'TBC' }}</strong>
                </div>


                <div class="progress-bar-shell">
                  <div class="progress-bar-fill" :style="progressPercentStyle"></div>
                </div>
              </div>
            </div>
          </article>
      </section>


      <section class="dashboard-section">
        <div class="dashboard-section-grid two-col-layout">

          <article class="surface-card interactive-surface">
            <div class="surface-card-header">
              <div>
                <p class="surface-kicker">Calendar</p>
                <h3 class="surface-card-title">Next Event</h3>
              </div>


              <RouterLink to="/events" class="surface-link">Open calendar</RouterLink>
            </div>


            <div v-if="nextEvent" class="event-detail-card">


              <div class="event-date-badge">
                <span class="event-date-day">{{ nextEventDateParts.day }}</span>
                <span class="event-date-rest">{{ nextEventDateParts.rest }}</span>
              </div>

              <div class="event-content">

                <div class="event-title">{{ nextEvent.title }}</div>


                <div class="event-meta-row">
                  <span><i class="fas fa-clock"></i>{{ nextEvent.time || 'Time TBC' }}</span>
                  <span><i class="fas fa-layer-group"></i>{{ nextEvent.mode || 'Hybrid' }}</span>
                </div>


                <div class="event-meta-row location-row">
                  <span><i class="fas fa-location-dot"></i>{{ nextEvent.location || 'Location TBC' }}</span>
                </div>


                <div class="event-actions">
                  <RouterLink to="/events" class="primary-chip">
                    {{ isAdmin ? 'Manage event' : isTeacher ? 'Open session' : 'View event' }}
                  </RouterLink>
                </div>
              </div>
            </div>


            <div v-else class="empty-state">
              <i class="fas fa-calendar-xmark"></i>
              <p>No upcoming event is available yet.</p>
            </div>
          </article>


          <article class="surface-card interactive-surface">
            <div class="surface-card-header">
              <div>
                <p class="surface-kicker">Updates</p>


                <h3 class="surface-card-title">{{ announcementsSectionTitle }}</h3>
              </div>
              <RouterLink to="/announcements" class="surface-link">View all</RouterLink>
            </div>


            <div v-if="announcementsPreview.length" class="list-stack">
              <RouterLink
                v-for="announcement in announcementsPreview"
                :key="announcement.id || getAnnouncementTitle(announcement)"
                to="/announcements"
                class="list-row premium-row"
              >
                <div class="list-row-icon announcement-icon">
                  <i class="fas fa-bullhorn"></i>
                </div>

                <div class="list-row-content">

                  <div class="list-row-title">{{ getAnnouncementTitle(announcement) }}</div>


                  <div class="list-row-meta">{{ formatAnnouncementDateAU(getAnnouncementMeta(announcement)) }}</div>


                  <div class="list-row-description">{{ getAnnouncementSnippet(announcement) }}</div>
                </div>

                <div class="list-row-tail">
                  <i class="fas fa-chevron-right"></i>
                </div>
              </RouterLink>
            </div>


            <div v-else class="empty-state">
              <i class="fas fa-bell-slash"></i>
              <p>No recent announcements are available yet.</p>
            </div>
          </article>
        </div>
      </section>


      <section class="dashboard-section">
        <article class="surface-card interactive-surface">
          <div class="surface-card-header">
            <div>
              <p class="surface-kicker">Groups</p>
              <h3 class="surface-card-title">{{ groupsSectionTitle }}</h3>
            </div>
            <RouterLink to="/groups" class="surface-link">View all</RouterLink>
          </div>


          <div v-if="groupsPreview.length" class="groups-grid">
            <RouterLink
              v-for="group in groupsPreview"
              :key="group.id || getGroupName(group)"
              :to="group.id ? '/groups/' + group.id : '/groups'"
              class="group-card-link"
            >
              <div class="group-card-surface interactive-surface">


                <div class="group-card-top">
                  <div class="group-avatars">


                    <div class="group-avatar primary-avatar">
                      {{ getInitials(getGroupName(group)) }}
                    </div>


                    <div class="group-avatar secondary-avatar">
                      {{ getGroupSecondaryLabel(group) }}
                    </div>


                    <div class="group-avatar tertiary-avatar">
                      +{{ Math.max(getGroupMemberCount(group) - 2, 0) }}
                    </div>
                  </div>

                  <span class="group-open-indicator">
                    <i class="fas fa-arrow-up-right-from-square"></i>
                  </span>
                </div>


                <div class="group-name">{{ getGroupName(group) }}</div>


                <div class="group-meta">{{ getGroupMemberCount(group) }} members · Lead: {{ getGroupLead(group) }}</div>
              </div>
            </RouterLink>
          </div>


          <div v-else class="empty-state">
            <i class="fas fa-users-slash"></i>
            <p>No group is available yet.</p>
          </div>
        </article>
      </section>


      <section class="dashboard-section">
        <div class="dashboard-section-grid two-col-layout">


          <article class="surface-card interactive-surface">
            <div class="surface-card-header">
              <div>
                <p class="surface-kicker">Library</p>
                <h3 class="surface-card-title">{{ resourcesSectionTitle }}</h3>
              </div>
              <RouterLink to="/resources" class="surface-link">View all</RouterLink>
            </div>


            <div v-if="resourcesPreview.length" class="resource-grid">
              <RouterLink
                v-for="resource in resourcesPreview"
                :key="resource.id || getResourceTitle(resource)"
                :to="resource.id ? '/resources/' + resource.id : '/resources'"
                class="resource-card-link"
              >
                <div class="resource-card-surface interactive-surface">


                  <div class="resource-icon">
                    <i :class="getResourceIcon(resource.type)"></i>
                  </div>

                  <div class="resource-content">

                    <div class="resource-title">{{ getResourceTitle(resource) }}</div>


                    <div class="resource-meta">
                      {{ getResourceCategory(resource) }} · Updated {{ getResourceMeta(resource) }}
                    </div>
                  </div>
                </div>
              </RouterLink>
            </div>


            <div v-else class="empty-state">
              <i class="fas fa-folder-open"></i>
              <p>No resource is available yet.</p>
            </div>
          </article>
        </div>
      </section>

      <div v-if="isLoading" class="dashboard-loading">
        <div class="loading-ring"></div>
        <span>Loading dashboard...</span>
      </div>
    </div>
  </div>
</template>

<script setup>
// Dashboard page
// Core imports
import { ref, computed, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'

import { RouterLink, useRouter } from 'vue-router'

import { storeToRefs } from 'pinia'

import { useAuthStore } from '@/stores/auth'
import * as THREE from 'three'

import { mockBiotechShowcaseItems } from '@/data/mock'

import { formatDateAU, formatLongDateAU, formatAnnouncementDateAU } from '@/utils/date'
import { getResourceIcon } from '@/utils/resource'
import { getInitials } from '@/utils/string'
import { buildSessionHeaders } from '@/utils/csrf'
import { safeLocalStorageGet, safeLocalStorageSet } from '@/utils/storage'
import { useThemeStore } from '@/stores/theme'
import { getAccentClass } from '@/utils/ui'

const router = useRouter()
const auth = useAuthStore()
const {
  isAdmin,
  isTeacher,
  displayName,
  displayTrack,
  organizationLabel,
  roleLabel,
  normalizedRole,
  user
} = storeToRefs(auth)
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
const DASHBOARD_FX_ENABLED_KEY = 'dashboard-fx-enabled'
const DASHBOARD_ENDPOINTS = {
  groupsPreview: (mine = false) => `${API_BASE_URL}/dashboard/v1/groups-preview/?page_size=20${mine ? '&mine=true' : ''}`,
  groups: `${API_BASE_URL}/groups/groups/?page_size=20`,
  groupsMine: `${API_BASE_URL}/groups/groups/?page_size=20&mine=true`,
  groupMembers: `${API_BASE_URL}/groups/group-members/?page_size=100`,
  tracks: `${API_BASE_URL}/groups/tracks/?page_size=100`,
  resources: `${API_BASE_URL}/resources/resource-files/?page_size=20`,
  announcements: `${API_BASE_URL}/announcements/v1/?page_size=10`,
  nextEvent: `${API_BASE_URL}/dashboard/v1/next-event/`,
  personalizedEvents: `${API_BASE_URL}/events/v1/?audience=me&page_size=1&ordering=start_datetime`,
  events: `${API_BASE_URL}/events/v1/?page_size=10`,
  tasksPreferred: `${API_BASE_URL}/tasks/api/v1/tasks/?page_size=100&deleted=false`,
  tasks: `${API_BASE_URL}/tasks/api/v1/tasks/?page_size=100&deleted=False`,
  milestones: `${API_BASE_URL}/tasks/api/v1/milestones/?page_size=100`,
  adminSummary: `${API_BASE_URL}/api/v1/admin/summary/`
}

const isLoading = ref(false)
const loadError = ref('')

const groups = ref([])
const resources = ref([])
const announcements = ref([])
const events = ref([])

const dashboardSummary = ref({
  activeGroups: groups.value.length,
  upcomingEvents: events.value.length,
  resources: resources.value.length,
  announcements: announcements.value.length
})

const adminWorkflow = ref({
  pendingMatches: 0,
  pendingReassignments: 0,
  pendingApprovals: 0,
  draftBulkMessages: 0
})

const adminOperationsSummary = ref(null)

const progressSnapshot = ref({
  completionRate: 0,
  completedTasks: 0,
  totalTasks: 0,
  currentWeek: 'No milestones yet',
  nextMilestone: 'TBC',
  nextMilestoneDate: ''
})

const nextEventDateParts = computed(() => {
  const formatted = formatDateAU(nextEvent.value?.date || '') || 'TBC'
  const parts = formatted.split(' ')
  return {
    day: parts[0] || 'TBC',
    rest: parts.slice(1).join(' ')
  }
})

const themeStore = useThemeStore()
const isDayMode = computed(() => themeStore.isDayMode)
const currentSurfaceModeLabel = computed(() => themeStore.isDayMode ? 'Day' : 'Night')

function toggleSurfaceMode() {
  themeStore.toggleMode()
}

const dashboardShellRef = ref(null)
const dashboardFxCanvasRef = ref(null)
const prefersReducedMotion = ref(false)
const isDashboardFxEnabled = ref(safeLocalStorageGet(DASHBOARD_FX_ENABLED_KEY, 'true') !== 'false')
const isDashboardFxRunningAllowed = computed(() => isDashboardFxEnabled.value && !prefersReducedMotion.value)
const dashboardFxToggleLabel = computed(() => isDashboardFxRunningAllowed.value ? 'FX On' : 'FX Off')
const dashboardFxToggleTitle = computed(() => {
  if (prefersReducedMotion.value) return 'Animated background is disabled by system reduced-motion preference'
  return isDashboardFxEnabled.value ? 'Turn off animated background' : 'Turn on animated background'
})

let reduceMotionQuery = null
let dashboardResizeRaf = null

const dashboardFxState = {
  renderer: null,
  scene: null,
  camera: null,
  material: null,
  clock: null,
  animationId: null
}

const nightPalette = {
  textPrimary: '#edfff5',
  textSecondary: '#9ac8b0',
  textMuted: '#6a9a82',
  textLink: '#7adfc8',
  surfaceBase: 'rgba(6, 18, 12, 0.84)',
  surfaceElevated: 'rgba(8, 22, 16, 0.92)',
  surfaceSoft: 'rgba(255, 255, 255, 0.06)',
  borderDefault: 'rgba(255, 255, 255, 0.10)',
  borderStrong: 'rgba(255, 255, 255, 0.18)',
  accentBlue: '#6cb6ff',
  accentTeal: '#41d9c6',
  accentViolet: '#b197ff',
  accentAmber: '#ffc56e',
  accentRose: '#ff8cab',
  shadowLg: '0 24px 70px rgba(0, 6, 2, 0.48)',
  shadowMd: '0 16px 40px rgba(0, 6, 2, 0.34)',
  heroOverlayA: 'rgba(7, 22, 14, 0.86)',
  heroOverlayB: 'rgba(6, 18, 11, 0.74)',
  shellBackdrop: 'linear-gradient(180deg, #071410 0%, #091e17 55%, #0b2318 100%)',
  pageGlowOne: 'rgba(48, 200, 120, 0.08)',
  pageGlowTwo: 'rgba(168, 85, 247, 0.07)',
  pageGlowThree: 'rgba(48, 200, 150, 0.06)',
  fxOpacity: '0.90'
}

const dayPalette = {
  textPrimary: '#1a3818',
  textSecondary: '#3a5e2c',
  textMuted: '#5e8040',
  textLink: '#265c3c',
  surfaceBase: 'rgba(182, 214, 142, 0.84)',
  surfaceElevated: 'rgba(196, 226, 158, 0.94)',
  surfaceSoft: 'rgba(80, 140, 40, 0.08)',
  borderDefault: 'rgba(70, 120, 30, 0.16)',
  borderStrong: 'rgba(70, 120, 30, 0.24)',
  accentBlue: '#2a6048',
  accentTeal: '#1f8a6a',
  accentViolet: '#7450c6',
  accentAmber: '#6a9820',
  accentRose: '#b74d7e',
  shadowLg: '0 26px 72px rgba(30, 70, 14, 0.16)',
  shadowMd: '0 18px 42px rgba(30, 70, 14, 0.12)',
  heroOverlayA: 'rgba(196, 222, 162, 0.96)',
  heroOverlayB: 'rgba(180, 210, 144, 0.84)',
  shellBackdrop: 'linear-gradient(180deg, #d4eac0 0%, #c8e0b2 52%, #bcd6a4 100%)',
  pageGlowOne: 'rgba(80, 180, 50, 0.13)',
  pageGlowTwo: 'rgba(100, 180, 80, 0.09)',
  pageGlowThree: 'rgba(60, 160, 80, 0.08)',
  fxOpacity: '0.12'
}

const dashboardPalette = computed(() => {
  return isDayMode.value ? dayPalette : nightPalette
})

const dashboardThemeStyle = computed(() => {
  return {
    '--text-primary': dashboardPalette.value.textPrimary,
    '--text-secondary': dashboardPalette.value.textSecondary,
    '--text-muted': dashboardPalette.value.textMuted,
    '--text-link': dashboardPalette.value.textLink,
    '--surface-base': dashboardPalette.value.surfaceBase,
    '--surface-elevated': dashboardPalette.value.surfaceElevated,
    '--surface-soft': dashboardPalette.value.surfaceSoft,
    '--border-default': dashboardPalette.value.borderDefault,
    '--border-strong': dashboardPalette.value.borderStrong,
    '--accent-blue': dashboardPalette.value.accentBlue,
    '--accent-teal': dashboardPalette.value.accentTeal,
    '--accent-violet': dashboardPalette.value.accentViolet,
    '--accent-amber': dashboardPalette.value.accentAmber,
    '--accent-rose': dashboardPalette.value.accentRose,
    '--shadow-lg': dashboardPalette.value.shadowLg,
    '--shadow-md': dashboardPalette.value.shadowMd,
    '--hero-overlay-a': dashboardPalette.value.heroOverlayA,
    '--hero-overlay-b': dashboardPalette.value.heroOverlayB,
    '--dashboard-shell-backdrop': dashboardPalette.value.shellBackdrop,
    '--page-glow-one': dashboardPalette.value.pageGlowOne,
    '--page-glow-two': dashboardPalette.value.pageGlowTwo,
    '--page-glow-three': dashboardPalette.value.pageGlowThree,
    '--dashboard-fx-opacity': dashboardPalette.value.fxOpacity
  }
})

const biotechShowcaseItems = ref(
  Array.isArray(mockBiotechShowcaseItems) ? [...mockBiotechShowcaseItems] : []
)

const activeShowcaseIndex = ref(0)
let showcaseInterval = null

const activeShowcaseItem = computed(() => {
  if (!biotechShowcaseItems.value.length) return null
  return biotechShowcaseItems.value[activeShowcaseIndex.value] || biotechShowcaseItems.value[0]
})

const currentDateText = computed(() => {
  return formatLongDateAU(new Date(), true)
})

const heroMetaChips = computed(() => {
  return [
    { key: 'date', label: 'Today', value: currentDateText.value, tone: 'neutral' },
    { key: 'track', label: 'Track', value: displayTrack.value || 'General', tone: 'cyan' },
    { key: 'role', label: 'Role', value: roleLabel.value || 'Member', tone: 'violet' }
  ]
})

const heroMessage = computed(() => {
  if (isAdmin.value) {
    return 'Review operational workload, monitor matching, and process critical platform actions from one unified dashboard.'
  }

  if (isTeacher.value) {
    return 'Track mentoring sessions, group activity, and support materials through a cleaner and more practical workspace.'
  }

  return 'Stay focused on your next event, active group, and current milestones with a dashboard designed for fast decisions.'
})

const heroShowcaseFacts = computed(() => {
  return [
    { key: 'groups', label: `${groupsCount.value} groups` },
    { key: 'resources', label: `${resourcesCount.value} resources` },
    { key: 'updates', label: `${announcementsCount.value} updates` }
  ]
})

const headerHighlights = computed(() => {
  if (isAdmin.value) {
    return [
      { key: 'groups', label: `${dashboardSummary.value.activeGroups} active groups` },
      { key: 'matches', label: `${adminWorkflow.value.pendingMatches} pending matches` },
      { key: 'approvals', label: `${adminWorkflow.value.pendingApprovals} approvals` }
    ]
  }

  if (isTeacher.value) {
    return [
      { key: 'groups', label: `${dashboardSummary.value.activeGroups} mentoring groups` },
      { key: 'events', label: `${dashboardSummary.value.upcomingEvents} upcoming sessions` },
      { key: 'progress', label: `${progressSnapshot.value.completionRate}% progress` }
    ]
  }

  return [
    { key: 'groups', label: `${dashboardSummary.value.activeGroups} active groups` },
    { key: 'events', label: `${dashboardSummary.value.upcomingEvents} upcoming events` },
    { key: 'tasks', label: `${progressSnapshot.value.completedTasks}/${progressSnapshot.value.totalTasks} tasks done` }
  ]
})

const heroEyebrow = computed(() => {
  if (isAdmin.value) return 'Platform Operations'
  if (isTeacher.value) return 'Mentor Workspace'
  return 'Student Workspace'
})

const announcementsCount = computed(() => announcements.value.length)
const resourcesCount = computed(() => resources.value.length)
const groupsCount = computed(() => groups.value.length)

const nextEvent = computed(() => {
  return events.value[0] || null
})

const announcementsPreview = computed(() => {
  return announcements.value.slice(0, 3)
})

const resourcesPreview = computed(() => {
  return filterResourcesByRole(resources.value).slice(0, 6)
})

const groupsPreview = computed(() => {
  return groups.value.slice(0, isAdmin.value ? 4 : 3)
})

const progressPercentStyle = computed(() => {
  const value = Math.max(0, Math.min(100, Number(progressSnapshot.value.completionRate || 0)))
  return {
    width: `${value}%`
  }
})

const progressCircleStyle = computed(() => {
  const value = Math.max(0, Math.min(100, Number(progressSnapshot.value.completionRate || 0)))
  return {
    background: `conic-gradient(var(--accent-blue) 0deg ${value * 2.2}deg, var(--accent-teal) ${value * 2.2}deg ${value * 3.1}deg, var(--accent-violet) ${value * 3.1}deg ${value * 3.6}deg, rgba(148, 163, 184, 0.14) ${value * 3.6}deg 360deg)`
  }
})

const progressMarkerStyle = computed(() => {
  const value = Math.max(0, Math.min(100, Number(progressSnapshot.value.completionRate || 0)))
  const angle = (value / 100) * Math.PI * 2 - Math.PI / 2
  const radius = 86
  const x = Math.cos(angle) * radius
  const y = Math.sin(angle) * radius

  return {
    transform: `translate(${x}px, ${y}px)`
  }
})

const progressStatusCaption = computed(() => {
  if (progressSnapshot.value.completionRate >= 80) return 'Strong momentum'
  if (progressSnapshot.value.completionRate >= 45) return 'On track'
  return 'Early cycle'
})

const summaryWidgets = computed(() => {
  if (isAdmin.value) {
    return [
      {
        key: 'groups',
        title: 'Active Groups',
        value: dashboardSummary.value.activeGroups,
        subtext: 'Current mentoring groups across the platform',
        icon: 'fas fa-users',
        accent: 'blue'
      },
      {
        key: 'events',
        title: 'Upcoming Events',
        value: dashboardSummary.value.upcomingEvents,
        subtext: nextEvent.value ? `Next: ${nextEvent.value.title}` : 'No upcoming event',
        icon: 'fas fa-calendar-days',
        accent: 'violet'
      },
      {
        key: 'matches',
        title: 'Pending Matches',
        value: adminWorkflow.value.pendingMatches,
        subtext: 'Items waiting for mentor allocation review',
        icon: 'fas fa-arrows-rotate',
        accent: 'teal'
      },
      {
        key: 'approvals',
        title: 'Open Approvals',
        value: adminWorkflow.value.pendingApprovals,
        subtext: 'Requests that need admin action',
        icon: 'fas fa-badge-check',
        accent: 'amber'
      }
    ]
  }

  if (isTeacher.value) {
    return [
      {
        key: 'groups',
        title: 'My Groups',
        value: dashboardSummary.value.activeGroups,
        subtext: 'Groups currently assigned to you',
        icon: 'fas fa-users',
        accent: 'blue'
      },
      {
        key: 'events',
        title: 'Upcoming Sessions',
        value: dashboardSummary.value.upcomingEvents,
        subtext: nextEvent.value ? `Next: ${nextEvent.value.title}` : 'No upcoming session',
        icon: 'fas fa-calendar-check',
        accent: 'violet'
      },
      {
        key: 'resources',
        title: 'Mentor Resources',
        value: resourcesCount.value,
        subtext: 'Guides, rubrics, and support materials',
        icon: 'fas fa-book-open',
        accent: 'teal'
      },
      {
        key: 'updates',
        title: 'Announcements',
        value: announcementsCount.value,
        subtext: 'Latest program communication',
        icon: 'fas fa-bullhorn',
        accent: 'rose'
      }
    ]
  }

  return [
    {
      key: 'groups',
      title: 'My Groups',
      value: dashboardSummary.value.activeGroups,
      subtext: 'Your current mentoring spaces',
      icon: 'fas fa-users',
      accent: 'blue'
    },
    {
      key: 'events',
      title: 'Upcoming Events',
      value: dashboardSummary.value.upcomingEvents,
      subtext: nextEvent.value ? `Next: ${nextEvent.value.title}` : 'No upcoming event',
      icon: 'fas fa-calendar-star',
      accent: 'violet'
    },
    {
      key: 'tasks',
      title: 'Tasks Completed',
      value: `${progressSnapshot.value.completedTasks}/${progressSnapshot.value.totalTasks}`,
      subtext: 'Your progress in the current program cycle',
      icon: 'fas fa-circle-check',
      accent: 'teal'
    },
    {
      key: 'resources',
      title: 'Resources',
      value: resourcesCount.value,
      subtext: 'Materials available to you',
      icon: 'fas fa-book',
      accent: 'amber'
    }
  ]
})

const groupsSectionTitle = computed(() => {
  if (isAdmin.value) return `Active Mentoring Groups (${groupsCount.value})`
  if (isTeacher.value) return `My Mentoring Groups (${groupsCount.value})`
  return `My Active Groups (${groupsCount.value})`
})

const resourcesSectionTitle = computed(() => {
  if (isAdmin.value) return 'Resource Library Snapshot'
  if (isTeacher.value) return 'Mentor Resources'
  return 'Learning Resources'
})

const announcementsSectionTitle = computed(() => {
  if (isAdmin.value) return 'Latest Broadcasts'
  if (isTeacher.value) return 'Program Updates'
  return 'Recent Announcements'
})

function getEmptyProgressSnapshot() {
  return {
    completionRate: 0,
    completedTasks: 0,
    totalTasks: 0,
    currentWeek: 'No milestones yet',
    nextMilestone: 'TBC',
    nextMilestoneDate: ''
  }
}

function extractCollectionItems(data) {
  if (Array.isArray(data)) return data
  if (Array.isArray(data?.results)) return data.results
  return []
}

function getCurrentUserId() {
  return user.value?.id ?? auth.user?.id ?? null
}

function toNumberSet(items) {
  return new Set(
    items
      .map(item => Number(item))
      .filter(item => Number.isFinite(item))
  )
}

function truncateText(value, maxLength = 160) {
  const text = String(value || '').replace(/\s+/g, ' ').trim()

  if (text.length <= maxLength) return text
  return `${text.slice(0, maxLength - 1).trim()}...`
}

function isValidDate(value) {
  if (!value) return false
  const date = value instanceof Date ? value : new Date(value)
  return !Number.isNaN(date.getTime())
}

function formatEventTime(startValue, endValue) {
  if (!isValidDate(startValue)) return ''

  const options = {
    hour: 'numeric',
    minute: '2-digit'
  }
  const start = new Date(startValue).toLocaleTimeString('en-AU', options)

  if (!isValidDate(endValue)) {
    return start
  }

  const end = new Date(endValue).toLocaleTimeString('en-AU', options)
  return `${start} - ${end}`
}

function resolveResourceIconType(value) {
  const text = String(value || '').toLowerCase()

  if (text.includes('pdf')) return 'pdf'
  if (text.includes('video') || text.includes('recording')) return 'video'
  if (text.includes('link') || text.includes('url')) return 'link'
  if (text.includes('article') || text.includes('news')) return 'article'
  return 'document'
}

function normalizeRoleName(value) {
  const role = String(value || '').trim().toLowerCase()

  if (!role) return ''
  if (['all', 'public', 'everyone'].includes(role)) return 'all'
  if (['administrator', 'admin', 'global_admin', 'local_admin'].includes(role)) return 'admin'
  if (['teacher', 'mentor'].includes(role)) return 'mentor'
  if (role === 'supervisor') return 'supervisor'
  if (role === 'student') return 'student'
  return role
}

function normalizeGroup(group, memberships = [], trackById = new Map()) {
  const groupId = group?.id
  const matchingMemberships = memberships.filter(item => String(item?.group) === String(groupId))
  const activeMentors = matchingMemberships.filter(item => {
    const role = String(item?.membership_role || '').toLowerCase()
    return role.includes('mentor') || role.includes('supervisor')
  })
  const leadName = group?.lead_name || group?.lead_user
    ? [
        group?.lead_user?.first_name,
        group?.lead_user?.last_name
      ].filter(Boolean).join(' ').trim() || group?.lead_user?.email || group?.lead_name
    : ''
  const trackLabel =
    group?.track_name ||
    trackById.get(Number(group?.track)) ||
    (group?.track ? `Track ${group.track}` : group?.category)
  const memberCount = Number(
    group?.member_count ??
    group?.memberCount ??
    group?.members ??
    matchingMemberships.length ??
    0
  )

  return {
    ...group,
    id: groupId,
    name: group?.group_name || group?.name || group?.title || 'Untitled group',
    title: group?.group_name || group?.title || group?.name || 'Untitled group',
    members: memberCount,
    memberCount,
    status: group?.deleted_at ? 'archived' : group?.status || 'active',
    mentor:
      leadName ||
      group?.mentor ||
      group?.lead ||
      (activeMentors[0]?.user ? `Mentor #${activeMentors[0].user}` : 'Mentor team'),
    track: trackLabel || 'General'
  }
}

function filterGroupsForDashboard(items, memberships = []) {
  if (isAdmin.value) return items

  const currentUserId = getCurrentUserId()
  if (!currentUserId || !Array.isArray(memberships)) return items

  const groupIds = toNumberSet(
    memberships
      .filter(item => String(item?.user) === String(currentUserId))
      .map(item => item?.group)
  )

  return items.filter(group => groupIds.has(Number(group?.id)))
}

function normalizeResource(resource) {
  const typeLabel =
    resource?.resource_type_detail?.type_name ||
    resource?.category ||
    resource?.type ||
    'General'
  const visibleRoles = Array.isArray(resource?.visible_roles)
    ? resource.visible_roles.map(role => role?.role_name)
    : []
  const audienceRoles = Array.isArray(resource?.audiences)
    ? resource.audiences.map(rule => rule?.role_name)
    : []
  const roles = [...visibleRoles, ...audienceRoles]
    .map(normalizeRoleName)
    .filter(Boolean)
  const scope = String(resource?.visibility_scope || '').toLowerCase()
  const normalizedRoles = scope === 'public' || roles.length === 0 ? ['all'] : Array.from(new Set(roles))

  return {
    ...resource,
    id: resource?.id,
    title: resource?.resource_name || resource?.title || resource?.name || 'Untitled resource',
    name: resource?.resource_name || resource?.name || resource?.title || 'Untitled resource',
    type: resolveResourceIconType(typeLabel),
    category: typeLabel,
    updated: resource?.upload_datetime || resource?.updated || resource?.date || resource?.created_at,
    role: normalizedRoles[0] || 'all',
    roles: normalizedRoles
  }
}

function normalizeAnnouncement(announcement) {
  const body = announcement?.body || announcement?.summary || announcement?.description || ''
  const audienceRoles = Array.isArray(announcement?.audiences)
    ? announcement.audiences.map(rule => rule?.role_name)
    : []
  const normalizedRoles = audienceRoles.map(normalizeRoleName).filter(Boolean)
  const visibilityScope = normalizeRoleName(announcement?.visibility_scope)
  const audience = visibilityScope === 'public'
    ? 'all'
    : (normalizedRoles[0] || visibilityScope || 'all')

  return {
    ...announcement,
    id: announcement?.id,
    title: announcement?.title || announcement?.name || 'Untitled announcement',
    summary: truncateText(body),
    description: body,
    content: body,
    date: announcement?.published_at || announcement?.date || announcement?.created_at,
    updated: announcement?.published_at || announcement?.updated || announcement?.created_at,
    author: announcement?.author_email || announcement?.author || 'Program Team',
    audience
  }
}

function normalizeEvent(event) {
  const start = event?.start_datetime || event?.date || ''
  const end = event?.ends_datetime || event?.end_datetime || event?.end || ''
  const isVirtual = event?.is_virtual === true

  return {
    ...event,
    id: event?.id,
    title: event?.event_name || event?.title || event?.name || 'Untitled event',
    date: start,
    time: formatEventTime(start, end) || event?.time || '',
    location: isVirtual ? 'Online' : event?.location || 'Location TBC',
    mode: isVirtual ? 'Virtual event' : event?.mode || 'In-person event',
    link: event?.humanitix_link || event?.link
  }
}

function deriveDashboardSummary() {
  if (isAdmin.value && adminOperationsSummary.value) {
    dashboardSummary.value = {
      activeGroups: Number(adminOperationsSummary.value.active_groups || groups.value.length),
      upcomingEvents: Number(adminOperationsSummary.value.upcoming_events || events.value.length),
      resources: resources.value.length,
      announcements: announcements.value.length
    }
    return
  }

  dashboardSummary.value = {
    activeGroups: groups.value.length,
    upcomingEvents: events.value.length,
    resources: resources.value.length,
    announcements: announcements.value.length
  }
}

function deriveProgressSnapshot(tasksData, milestonesData) {
  const fallback = getEmptyProgressSnapshot()
  const visibleGroupIds = toNumberSet(groups.value.map(group => group?.id))
  let activeMilestones = extractCollectionItems(milestonesData).filter(milestone => milestone?.deleted_flag !== true)

  if (!isAdmin.value && !visibleGroupIds.size) {
    return fallback
  }

  if (visibleGroupIds.size) {
    activeMilestones = activeMilestones.filter(milestone => visibleGroupIds.has(Number(milestone?.group)))
  }

  const visibleMilestoneIds = toNumberSet(activeMilestones.map(milestone => milestone?.id))
  let activeTasks = extractCollectionItems(tasksData).filter(task => task?.deleted_flag !== true)

  if (visibleMilestoneIds.size) {
    activeTasks = activeTasks.filter(task => visibleMilestoneIds.has(Number(task?.milestone)))
  }

  if (!activeTasks.length && !activeMilestones.length) {
    return fallback
  }

  const completedMilestoneIds = new Set(
    activeMilestones
      .filter(milestone => milestone?.completed === true)
      .map(milestone => Number(milestone?.id))
  )
  const completedTasks = activeTasks.filter(task => completedMilestoneIds.has(Number(task?.milestone))).length
  const fallbackCompleted = activeMilestones.filter(milestone => milestone?.completed === true).length
  const totalTasks = activeTasks.length || activeMilestones.length || fallback.totalTasks
  const doneTasks = activeTasks.length ? completedTasks : fallbackCompleted
  const completionRate = totalTasks > 0 ? Math.round((doneTasks / totalTasks) * 100) : fallback.completionRate
  const nextMilestone =
    activeMilestones.find(milestone => milestone?.completed !== true) ||
    activeMilestones[0] ||
    null
  const nextTask =
    activeTasks.find(task => Number(task?.milestone) === Number(nextMilestone?.id)) ||
    [...activeTasks].sort((a, b) => new Date(a?.due_date || 0) - new Date(b?.due_date || 0))[0] ||
    null

  return {
    completionRate,
    completedTasks: doneTasks,
    totalTasks,
    currentWeek: activeMilestones.length
      ? `${fallbackCompleted}/${activeMilestones.length} milestones`
      : fallback.currentWeek,
    nextMilestone: nextMilestone?.milestone_name || nextTask?.task_name || fallback.nextMilestone,
    nextMilestoneDate: nextTask?.due_date || fallback.nextMilestoneDate
  }
}

function normalizeProgressSnapshot(payload) {
  const fallback = getEmptyProgressSnapshot()

  if (!payload || typeof payload !== 'object') {
    return fallback
  }

  return {
    completionRate: Number(payload?.completion_rate ?? fallback.completionRate),
    completedTasks: Number(payload?.completed_tasks ?? fallback.completedTasks),
    totalTasks: Number(payload?.total_tasks ?? fallback.totalTasks),
    currentWeek: payload?.current_stage || fallback.currentWeek,
    nextMilestone: payload?.next_milestone?.name || fallback.nextMilestone,
    nextMilestoneDate: payload?.next_milestone?.due_date || fallback.nextMilestoneDate
  }
}

function hasGroupPreviewShape(items) {
  return Array.isArray(items) && items.some(item =>
    item &&
    (
      'track_name' in item ||
      'member_count' in item ||
      'lead_name' in item ||
      'lead_user' in item
    )
  )
}

async function fetchJson(url, options = {}) {
  const { allowNoContent = false } = options
  const response = await fetch(url, {
    method: 'GET',
    credentials: 'include',
    headers: buildSessionHeaders({
      headers: {
        Accept: 'application/json'
      }
    })
  })

  if (allowNoContent && response.status === 204) {
    return null
  }

  const text = await response.text()
  let data = null
  try {
    data = text ? JSON.parse(text) : null
  } catch {
    data = null
  }

  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`)
  }

  return data
}

async function fetchFirstAvailable(urls, options = {}) {
  let lastError = null

  for (const url of urls) {
    try {
      return await fetchJson(url, options)
    } catch (error) {
      lastError = error
    }
  }

  if (lastError) {
    throw lastError
  }

  return null
}

async function loadDashboardData() {
  isLoading.value = true
  loadError.value = ''

  try {
    await Promise.allSettled([
      loadGroups(),
      loadResources(),
      loadAnnouncements(),
      loadEvents(),
      loadAdminWorkflow()
    ])
    await loadProgress()
    loadSummary()
  } catch (error) {
    console.error('Dashboard loading error:', error)
    loadError.value = 'Some live dashboard data could not be loaded.'
  } finally {
    isLoading.value = false
  }
}

function loadSummary() {
  deriveDashboardSummary()
}

async function loadGroups() {
  try {
    const primaryGroupUrl = isAdmin.value
      ? DASHBOARD_ENDPOINTS.groupsPreview(false)
      : DASHBOARD_ENDPOINTS.groupsPreview(true)
    const fallbackGroupUrls = isAdmin.value
      ? [DASHBOARD_ENDPOINTS.groups]
      : [DASHBOARD_ENDPOINTS.groupsMine, DASHBOARD_ENDPOINTS.groups]
    const data = await fetchFirstAvailable([primaryGroupUrl, ...fallbackGroupUrls])
    const groupItems = extractCollectionItems(data)

    if (Array.isArray(groupItems) && groupItems.length === 0 && String(primaryGroupUrl).includes('/dashboard/v1/groups-preview/')) {
      groups.value = []
      return
    }

    if (hasGroupPreviewShape(groupItems)) {
      groups.value = groupItems.map(group => normalizeGroup(group))
      return
    }

    let memberships = null
    let trackById = new Map()

    try {
      memberships = extractCollectionItems(await fetchJson(DASHBOARD_ENDPOINTS.groupMembers))
    } catch (error) {
      memberships = null
    }

    try {
      const tracks = extractCollectionItems(await fetchJson(DASHBOARD_ENDPOINTS.tracks))
      trackById = new Map(tracks.map(track => [Number(track?.id), track?.track_name]).filter(item => item[1]))
    } catch (error) {
      trackById = new Map()
    }

    if (!isAdmin.value && memberships === null) {
      throw new Error('Group memberships unavailable')
    }

    const liveGroups = filterGroupsForDashboard(groupItems, memberships || [])
    groups.value = liveGroups.map(group => normalizeGroup(group, memberships || [], trackById))
  } catch (error) {
    groups.value = []
  }
}

async function loadResources() {
  try {
    const data = await fetchJson(DASHBOARD_ENDPOINTS.resources)
    const liveResources = extractCollectionItems(data)
    resources.value = liveResources.map(normalizeResource)
  } catch (error) {
    resources.value = []
  }
}

async function loadAnnouncements() {
  try {
    const data = await fetchJson(DASHBOARD_ENDPOINTS.announcements)
    const liveAnnouncements = extractCollectionItems(data)
    announcements.value = liveAnnouncements.map(normalizeAnnouncement)
  } catch (error) {
    announcements.value = []
  }
}

async function loadEvents() {
  try {
    const nextEventData = await fetchJson(DASHBOARD_ENDPOINTS.nextEvent, {
      allowNoContent: true
    })

    if (nextEventData) {
      events.value = [normalizeEvent(nextEventData)]
      return
    }

    if (nextEventData === null) {
      events.value = []
      return
    }

    const fallbackEvents = await fetchFirstAvailable([
      DASHBOARD_ENDPOINTS.personalizedEvents,
      DASHBOARD_ENDPOINTS.events
    ])
    const liveEvents = extractCollectionItems(fallbackEvents)
    events.value = liveEvents.map(normalizeEvent)
  } catch (error) {
    try {
      const fallbackEvents = await fetchFirstAvailable([
        DASHBOARD_ENDPOINTS.personalizedEvents,
        DASHBOARD_ENDPOINTS.events
      ])
      const liveEvents = extractCollectionItems(fallbackEvents)
      events.value = liveEvents.length ? liveEvents.map(normalizeEvent) : []
    } catch {
      events.value = []
    }
  }
}

async function loadAdminWorkflow() {
  if (!isAdmin.value) return

  try {
    const data = await fetchJson(DASHBOARD_ENDPOINTS.adminSummary)
    adminOperationsSummary.value = data
    adminWorkflow.value = {
      pendingMatches: Number(data?.unassigned_match_recommendations || 0),
      pendingReassignments: Number(data?.groups_without_mentor || 0),
      pendingApprovals: Number(data?.invited_or_pending_users || 0),
      draftBulkMessages: 0
    }
  } catch (error) {
    adminOperationsSummary.value = null
    adminWorkflow.value = {
      pendingMatches: 0,
      pendingReassignments: 0,
      pendingApprovals: 0,
      draftBulkMessages: 0
    }
  }
}

async function loadProgress() {
  try {
    const [tasksData, milestonesData] = await Promise.all([
      fetchFirstAvailable([DASHBOARD_ENDPOINTS.tasksPreferred, DASHBOARD_ENDPOINTS.tasks]),
      fetchJson(DASHBOARD_ENDPOINTS.milestones)
    ])

    progressSnapshot.value = deriveProgressSnapshot(tasksData, milestonesData)
  } catch {
    progressSnapshot.value = getEmptyProgressSnapshot()
  }
}

async function loadBiotechShowcase() {
  restartShowcaseAutoplay()
}


function goToNextShowcase() {
  if (!biotechShowcaseItems.value.length) return
  activeShowcaseIndex.value = (activeShowcaseIndex.value + 1) % biotechShowcaseItems.value.length
}

function goToPrevShowcase() {
  if (!biotechShowcaseItems.value.length) return
  activeShowcaseIndex.value =
    (activeShowcaseIndex.value - 1 + biotechShowcaseItems.value.length) % biotechShowcaseItems.value.length
}

function goToShowcase(index) {
  if (index < 0 || index >= biotechShowcaseItems.value.length) return
  activeShowcaseIndex.value = index
  restartShowcaseAutoplay()
}

function startShowcaseAutoplay() {
  stopShowcaseAutoplay()

  if (biotechShowcaseItems.value.length <= 1) return

  showcaseInterval = window.setInterval(() => {
    goToNextShowcase()
  }, 5000)
}

function stopShowcaseAutoplay() {
  if (showcaseInterval) {
    window.clearInterval(showcaseInterval)
    showcaseInterval = null
  }
}

function restartShowcaseAutoplay() {
  stopShowcaseAutoplay()
  startShowcaseAutoplay()
}


function openShowcaseLink(item) {
  if (!item) return

  if (typeof item.link === 'string' && item.link.startsWith('http')) {
    window.open(item.link, '_blank', 'noopener')
    return
  }

  if (typeof item.link === 'string' && item.link.startsWith('/')) {
    router.push(item.link)
  }
}

function filterResourcesByRole(items) {
  const role = normalizedRole.value

  return items.filter(item => {
    const resourceRoles = Array.isArray(item?.roles) && item.roles.length
      ? item.roles.map(normalizeRoleName)
      : [normalizeRoleName(item?.role || 'all')]

    if (resourceRoles.includes('all')) return true
    if (role === 'teacher' && resourceRoles.some(resourceRole => ['mentor', 'supervisor'].includes(resourceRole))) return true
    if (role === 'admin' && resourceRoles.includes('admin')) return true
    if (role === 'student' && resourceRoles.includes('student')) return true
    if (role === 'admin') return true

    return false
  })
}

function getAnnouncementTitle(item) {
  return item?.title || item?.name || item?.subject || 'Untitled announcement'
}

function getAnnouncementMeta(item) {
  return item?.updated || item?.date || item?.created_at || 'Recently posted'
}

function getAnnouncementSnippet(item) {
  return item?.summary || item?.description || item?.content || item?.excerpt || 'Open the announcement to read more details.'
}

function getResourceTitle(item) {
  return item?.title || item?.name || 'Untitled resource'
}

function getResourceMeta(item) {
  return item?.updated || item?.date || item?.created_at || 'Recently updated'
}

function getResourceCategory(item) {
  return item?.category || item?.typeLabel || item?.tag || item?.type || 'General'
}

function getGroupName(group) {
  return group?.name || group?.title || 'Untitled group'
}

function getGroupMemberCount(group) {
  return Number(group?.members || group?.memberCount || 0)
}

function getGroupLead(group) {
  return group?.mentor || group?.lead || group?.supervisor || group?.owner || 'Mentor team'
}

function getGroupSecondaryLabel(group) {
  const source = group?.track || group?.category || group?.status || 'BF'
  return String(source).slice(0, 2).toUpperCase()
}

const DASHBOARD_FX_VERT = `
varying vec2 vUv;

void main() {
  vUv = uv;
  gl_Position = vec4(position.xy, 0.0, 1.0);
}
`

const DASHBOARD_FX_FRAG = `
precision highp float;

varying vec2 vUv;

uniform float uTime;
uniform vec2 uResolution;

mat2 rotate2d(float angle) {
  float s = sin(angle);
  float c = cos(angle);
  return mat2(c, -s, s, c);
}

float hash12(vec2 p) {
  vec3 p3 = fract(vec3(p.xyx) * 0.1031);
  p3 += dot(p3, p3.yzx + 33.33);
  return fract((p3.x + p3.y) * p3.z);
}

vec2 hash22(vec2 p) {
  float n = hash12(p);
  return vec2(n, hash12(p + n + 19.19));
}

float noise(vec2 p) {
  vec2 i = floor(p);
  vec2 f = fract(p);
  vec2 u = f * f * (3.0 - 2.0 * f);

  float a = hash12(i);
  float b = hash12(i + vec2(1.0, 0.0));
  float c = hash12(i + vec2(0.0, 1.0));
  float d = hash12(i + vec2(1.0, 1.0));

  return mix(mix(a, b, u.x), mix(c, d, u.x), u.y);
}

float fbm(vec2 p) {
  float value = 0.0;
  float amplitude = 0.56;

  for (int i = 0; i < 5; i++) {
    value += amplitude * noise(p);
    p = rotate2d(0.67) * p * 2.03 + vec2(4.81, 3.17);
    amplitude *= 0.52;
  }

  return value;
}

float voronoi(vec2 x) {
  vec2 n = floor(x);
  vec2 f = fract(x);
  float minDist = 10.0;

  for (int j = -1; j <= 1; j++) {
    for (int i = -1; i <= 1; i++) {
      vec2 g = vec2(float(i), float(j));
      vec2 o = hash22(n + g);
      o = 0.5 + 0.35 * sin(uTime * 0.22 + 6.283185 * o);
      vec2 r = g + o - f;
      minDist = min(minDist, dot(r, r));
    }
  }

  return sqrt(minDist);
}

void main() {
  vec2 uv = vUv;
  vec2 aspect = vec2(uResolution.x / max(uResolution.y, 1.0), 1.0);
  vec2 p = (uv - 0.5) * aspect;

  vec2 warpA = vec2(
    fbm(p * 1.25 + vec2(uTime * 0.032, -uTime * 0.018)),
    fbm(rotate2d(0.74) * p * 1.5 + vec2(-uTime * 0.024, uTime * 0.028))
  );

  vec2 warpB = vec2(
    fbm(rotate2d(-0.38) * p * 2.1 + warpA * 1.2 + vec2(uTime * 0.014, uTime * 0.018)),
    fbm(rotate2d(0.46) * p * 2.45 - warpA * 1.1 + vec2(-uTime * 0.016, uTime * 0.01))
  );

  vec2 q = p + (warpA - 0.5) * 0.42 + (warpB - 0.5) * 0.16;

  float fieldA = fbm(q * 1.45 + vec2(0.0, uTime * 0.022));
  float fieldB = fbm(rotate2d(0.85) * q * 2.25 - vec2(uTime * 0.018, 0.0));
  float fieldC = fbm(rotate2d(-0.52) * q * 3.15 + vec2(uTime * 0.011, uTime * 0.014));

  float membraneDistance = voronoi(q * 3.25 + warpA * 1.6);
  float membrane = 1.0 - smoothstep(0.13, 0.24, abs(membraneDistance - 0.22));

  float nebula = smoothstep(0.42, 0.98, fieldA * 0.82 + fieldB * 0.28);
  float stream = smoothstep(0.5, 1.05, fieldB * 0.86 + fieldC * 0.24);
  float bloom = smoothstep(0.58, 1.08, fieldC * 0.92 + fieldA * 0.18);

  float pulseA = exp(-pow((q.y + 0.18 + sin(uTime * 0.34 + q.x * 2.7) * 0.09) / 0.34, 2.0));
  float pulseB = exp(-pow((q.y - 0.24 + cos(uTime * 0.26 - q.x * 2.2) * 0.07) / 0.28, 2.0));

  float spores = smoothstep(0.88, 0.995, noise(q * 16.0 + vec2(uTime * 0.08, -uTime * 0.05)));
  spores *= 0.16 + membrane * 0.12;

  vec3 base = vec3(0.018, 0.028, 0.064);
  vec3 teal = vec3(0.08, 0.82, 0.72);
  vec3 azure = vec3(0.21, 0.56, 0.98);
  vec3 violet = vec3(0.62, 0.38, 0.98);
  vec3 coral = vec3(0.97, 0.47, 0.66);
  vec3 amber = vec3(0.95, 0.72, 0.33);
  vec3 pearl = vec3(0.92, 0.98, 1.0);

  vec3 color = base;
  color += teal * nebula * 0.24;
  color += azure * stream * 0.26;
  color += violet * bloom * 0.18;
  color += coral * membrane * 0.12;
  color += amber * (pulseA * 0.035 + pulseB * 0.025);
  color += pearl * spores * 0.22;

  float vignette = smoothstep(1.22, 0.14, length((uv - 0.5) * vec2(1.02, 0.9)));
  float alpha = clamp((nebula * 0.18 + stream * 0.16 + bloom * 0.12 + membrane * 0.12 + spores * 0.12 + pulseA * 0.04 + pulseB * 0.03) * vignette, 0.0, 0.42);

  gl_FragColor = vec4(color, alpha);
}
`

function handleReduceMotionChange(event) {
  prefersReducedMotion.value = event.matches

  if (prefersReducedMotion.value) {
    disposeDashboardFx()
  } else {
    initDashboardFx()
  }
}

function toggleDashboardFx() {
  isDashboardFxEnabled.value = !isDashboardFxEnabled.value
  safeLocalStorageSet(DASHBOARD_FX_ENABLED_KEY, isDashboardFxEnabled.value ? 'true' : 'false')

  if (isDashboardFxEnabled.value) {
    nextTick(() => initDashboardFx())
  } else {
    disposeDashboardFx()
  }
}

function initDashboardFx() {
  if (!dashboardFxCanvasRef.value || !isDashboardFxEnabled.value || prefersReducedMotion.value || dashboardFxState.renderer) return

  const shell = dashboardShellRef.value
  if (!shell) return

  const rect = shell.getBoundingClientRect()

  dashboardFxState.renderer = new THREE.WebGLRenderer({
    canvas: dashboardFxCanvasRef.value,
    alpha: true,
    antialias: true,
    powerPreference: 'high-performance'
  })
  dashboardFxState.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.1))
  dashboardFxState.renderer.setSize(rect.width, rect.height, false)
  dashboardFxState.renderer.setClearColor(0x000000, 0)

  dashboardFxState.scene = new THREE.Scene()
  dashboardFxState.camera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0.1, 10)
  dashboardFxState.camera.position.z = 1
  dashboardFxState.clock = new THREE.Clock()

  dashboardFxState.material = new THREE.ShaderMaterial({
    vertexShader: DASHBOARD_FX_VERT,
    fragmentShader: DASHBOARD_FX_FRAG,
    transparent: true,
    depthWrite: false,
    depthTest: false,
    uniforms: {
      uTime: { value: 0 },
      uResolution: { value: new THREE.Vector2(rect.width, rect.height) }
    }
  })

  const plane = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), dashboardFxState.material)
  dashboardFxState.scene.add(plane)

  animateDashboardFx()
}

function resizeDashboardFx() {
  if (!dashboardFxState.renderer || !dashboardShellRef.value || !dashboardFxState.material) return

  if (dashboardResizeRaf) cancelAnimationFrame(dashboardResizeRaf)

  dashboardResizeRaf = requestAnimationFrame(() => {
    dashboardResizeRaf = null

    const rect = dashboardShellRef.value.getBoundingClientRect()
    dashboardFxState.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.1))
    dashboardFxState.renderer.setSize(rect.width, rect.height, false)
    dashboardFxState.material.uniforms.uResolution.value.set(rect.width, rect.height)
  })
}

function animateDashboardFx() {
  if (!dashboardFxState.renderer || !dashboardFxState.scene || !dashboardFxState.camera || !dashboardFxState.material || !dashboardFxState.clock) {
    return
  }

  dashboardFxState.animationId = requestAnimationFrame(animateDashboardFx)

  const elapsed = dashboardFxState.clock.getElapsedTime()

  dashboardFxState.material.uniforms.uTime.value = elapsed

  dashboardFxState.renderer.render(dashboardFxState.scene, dashboardFxState.camera)
}

function disposeDashboardFx() {
  if (dashboardResizeRaf) {
    cancelAnimationFrame(dashboardResizeRaf)
    dashboardResizeRaf = null
  }

  if (dashboardFxState.animationId) {
    cancelAnimationFrame(dashboardFxState.animationId)
    dashboardFxState.animationId = null
  }

  if (dashboardFxState.material) {
    dashboardFxState.material.dispose()
    dashboardFxState.material = null
  }

  if (dashboardFxState.scene) {
    dashboardFxState.scene.traverse((item) => {
      if (item.geometry) item.geometry.dispose()
    })
    dashboardFxState.scene = null
  }

  if (dashboardFxState.renderer) {
    dashboardFxState.renderer.dispose()
    dashboardFxState.renderer = null
  }

  dashboardFxState.camera = null
  dashboardFxState.clock = null
}

watch(
  () => biotechShowcaseItems.value.length,
  () => {
    if (activeShowcaseIndex.value >= biotechShowcaseItems.value.length) {
      activeShowcaseIndex.value = 0
    }
    restartShowcaseAutoplay()
  }
)

onMounted(async () => {
  await loadDashboardData()
  await loadBiotechShowcase()

  window.addEventListener('resize', resizeDashboardFx)

  reduceMotionQuery = window.matchMedia('(prefers-reduced-motion: reduce)')
  prefersReducedMotion.value = reduceMotionQuery.matches

  if (reduceMotionQuery.addEventListener) {
    reduceMotionQuery.addEventListener('change', handleReduceMotionChange)
  } else if (reduceMotionQuery.addListener) {
    reduceMotionQuery.addListener(handleReduceMotionChange)
  }

  await nextTick()
  initDashboardFx()
  startShowcaseAutoplay()
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', resizeDashboardFx)
  stopShowcaseAutoplay()
  disposeDashboardFx()

  if (reduceMotionQuery) {
    if (reduceMotionQuery.removeEventListener) {
      reduceMotionQuery.removeEventListener('change', handleReduceMotionChange)
    } else if (reduceMotionQuery.removeListener) {
      reduceMotionQuery.removeListener(handleReduceMotionChange)
    }

    reduceMotionQuery = null
  }
})
</script>

<style scoped>
/* ================================================================
   BIOTECH FUTURES HUB — DASHBOARD
   Design Language: Cyberpunk / Bioluminescent
   ================================================================ */

/* ──────────────────────────────────────────────────────────────
   § 1  DESIGN TOKENS
   ────────────────────────────────────────────────────────────── */
.dashboard-page-shell {
  --text-primary:   #eef5ff;
  --text-secondary: #94b8d8;
  --text-muted:     #5c7a9a;
  --text-link:      #7ec8ff;

  --surface-base:     rgba(6, 18, 12, 0.82);
  --surface-elevated: rgba(8, 22, 16, 0.90);

  --border-default: rgba(255, 255, 255, 0.09);
  --border-strong:  rgba(255, 255, 255, 0.16);

  --accent-blue:   #60a5fa;
  --accent-teal:   #2dd4bf;
  --accent-violet: #a78bfa;
  --accent-amber:  #fbbf24;
  --accent-rose:   #f87171;

  --shadow-lg: 0 24px 64px rgba(0, 6, 2, 0.52);
  --shadow-md: 0 14px 38px rgba(0, 6, 2, 0.40);
  --shadow-sm: 0 8px 22px rgba(0, 6, 2, 0.30);

  --radius-card: 24px;
  --radius-hero: 28px;
  --radius-chip: 999px;

  --ease-out: cubic-bezier(0.22, 1, 0.36, 1);
  --t-fast: 180ms;
  --t-base: 260ms;
  --t-slow: 400ms;

  position: relative;
  isolation: isolate;
  min-height: 100%;
  overflow: visible;
  padding: 1.5rem 1.2rem 3rem;
  color: var(--text-primary);
  background:
    radial-gradient(circle at 10% 8%, var(--page-glow-one), transparent 26%),
    radial-gradient(circle at 86% 12%, var(--page-glow-two), transparent 24%),
    radial-gradient(circle at 68% 84%, var(--page-glow-three), transparent 26%);
}


/* ──────────────────────────────────────────────────────────────
   § 2  PAGE SHELL & BACKGROUND
   ────────────────────────────────────────────────────────────── */
.dashboard-page-shell::before {
  content: '';
  position: absolute;
  inset: 0;
  z-index: -5;
  background: var(--dashboard-shell-backdrop, linear-gradient(135deg, #060c1a, #0a1224));
}

.dashboard-page-inner {
  position: relative;
  max-width: 1520px;
  margin: 0 auto;
}

/* ──────────────────────────────────────────────────────────────
   § 3  BACKGROUND EFFECTS
   ────────────────────────────────────────────────────────────── */
.dashboard-fx-canvas {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  z-index: -6;
  pointer-events: none;
  opacity: var(--dashboard-fx-opacity, 0.92);
}

.dashboard-page-shell.is-fx-disabled .dashboard-fx-canvas {
  opacity: 0;
  visibility: hidden;
}

.dashboard-backdrop-orb {
  position: absolute;
  border-radius: 999px;
  pointer-events: none;
  z-index: -3;
}

.orb-one {
  width: 520px;
  height: 520px;
  top: -60px;
  right: 1%;
  background: radial-gradient(circle, rgba(48, 200, 120, 0.28), rgba(40, 180, 100, 0.10) 52%, transparent 74%);
  filter: blur(56px);
  animation: orbFloat 18s ease-in-out infinite;
}

.orb-two {
  width: 440px;
  height: 440px;
  left: -2%;
  bottom: 60px;
  background: radial-gradient(circle, rgba(45, 212, 170, 0.24), rgba(16, 185, 110, 0.08) 52%, transparent 74%);
  filter: blur(56px);
  animation: orbFloat 22s ease-in-out infinite reverse;
}

.dashboard-backdrop-grid {
  position: absolute;
  inset: 0;
  z-index: -4;
  pointer-events: none;
  opacity: 0.13;
  background-image:
    linear-gradient(rgba(80, 200, 120, 0.32) 1px, transparent 1px),
    linear-gradient(90deg, rgba(80, 200, 120, 0.32) 1px, transparent 1px);
  background-size: 44px 44px;
  mask-image: radial-gradient(ellipse 95% 55% at 50% 0%, black 30%, transparent 78%);
  -webkit-mask-image: radial-gradient(ellipse 95% 55% at 50% 0%, black 30%, transparent 78%);
}

@keyframes orbFloat {
  0%, 100% { transform: translate3d(0, 0, 0) scale(1); }
  33%       { transform: translate3d(-22px, 20px, 0) scale(1.04); }
  66%       { transform: translate3d(18px, -16px, 0) scale(0.97); }
}

/* ──────────────────────────────────────────────────────────────
   § 4  SECTION LAYOUT
   ────────────────────────────────────────────────────────────── */
.dashboard-section { margin-bottom: 1.6rem; }

.dashboard-section-grid {
  display: grid;
  gap: 1.2rem;
}

.two-col-layout   { grid-template-columns: repeat(2, minmax(0, 1fr)); }
.summary-grid     { grid-template-columns: repeat(4, minmax(0, 1fr)); }

/* ──────────────────────────────────────────────────────────────
   § 5  HERO CARD
   ────────────────────────────────────────────────────────────── */
.dashboard-hero-shell { margin-bottom: 1.5rem; }

.dashboard-hero-card {
  position: relative;
  overflow: hidden;
  border-radius: var(--radius-hero);
  padding: 1.6rem;
  border: 1px solid rgba(255, 255, 255, 0.13);
  background: linear-gradient(145deg, rgba(6, 18, 12, 0.92), rgba(7, 16, 11, 0.78));
  box-shadow: var(--shadow-lg), inset 0 1px 0 rgba(255, 255, 255, 0.07);
  backdrop-filter: blur(28px);
  -webkit-backdrop-filter: blur(28px);
  transition: transform var(--t-base) var(--ease-out), box-shadow var(--t-base);
}

/* Blue aurora top-left */
.dashboard-hero-card::before {
  content: '';
  position: absolute;
  top: -35%; left: -6%;
  width: 52%; height: 72%;
  border-radius: 999px;
  background: radial-gradient(circle, rgba(96, 165, 250, 0.22), transparent 66%);
  filter: blur(22px);
  pointer-events: none;
}

/* Teal aurora bottom-right */
.dashboard-hero-card::after {
  content: '';
  position: absolute;
  bottom: -32%; right: -8%;
  width: 46%; height: 72%;
  border-radius: 999px;
  background: radial-gradient(circle, rgba(45, 212, 191, 0.18), transparent 68%);
  filter: blur(22px);
  pointer-events: none;
}

/* ──────────────────────────────────────────────────────────────
   § 6  THEME RAIL
   ────────────────────────────────────────────────────────────── */
.dashboard-theme-rail {
  position: absolute;
  top: 1.1rem; right: 1.1rem;
  z-index: 5;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 0.6rem;
}

.theme-rail-trigger {
  display: inline-flex;
  align-items: center;
  gap: 0.55rem;
  min-height: 40px;
  padding: 0.48rem 1rem;
  border-radius: var(--radius-chip);
  border: 1px solid rgba(255, 255, 255, 0.14);
  background: rgba(7, 13, 28, 0.76);
  color: var(--text-primary);
  cursor: pointer;
  font-size: 0.86rem;
  font-weight: 600;
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  transition: border-color var(--t-fast), transform var(--t-fast), background var(--t-fast);
}

.theme-rail-trigger:hover {
  transform: translateY(-2px);
  border-color: var(--border-strong);
  background: linear-gradient(165deg, color-mix(in srgb, var(--surface-elevated) 94%, transparent), color-mix(in srgb, var(--surface-base) 98%, transparent));
}

.fx-rail-trigger.is-muted {
  color: var(--text-muted);
  border-color: color-mix(in srgb, var(--accent-amber) 18%, var(--border-default));
}

/* ──────────────────────────────────────────────────────────────
   § 7  HERO CONTENT
   ────────────────────────────────────────────────────────────── */
.dashboard-hero-main {
  position: relative;
  z-index: 1;
  display: grid;
  grid-template-columns: minmax(0, 1.08fr) minmax(0, 0.92fr);
  gap: 1.4rem;
  align-items: stretch;
  padding-top: 2.6rem;
}

.dashboard-hero-copy,
.dashboard-hero-aside {
  min-width: 0;
  display: flex;
}

.dashboard-hero-copy {
  position: relative;
  flex-direction: column;
  justify-content: space-between;
  min-height: 100%;
  padding: 1.35rem 1.45rem 1.4rem;
  border-radius: 28px;
  background:
    linear-gradient(160deg, rgba(6, 20, 12, 0.62), rgba(5, 16, 10, 0.40)),
    radial-gradient(circle at top left, rgba(60, 200, 110, 0.12), transparent 44%);
  border: 1px solid rgba(255, 255, 255, 0.08);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.06);
  overflow: hidden;
}

.dashboard-hero-copy::before {
  content: '';
  position: absolute;
  inset: 1px;
  border-radius: inherit;
  pointer-events: none;
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.06), transparent 28%, transparent 72%, rgba(125, 211, 252, 0.06));
  mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
  mask-composite: exclude;
  -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
  -webkit-mask-composite: xor;
  padding: 1px;
}

.hero-eyebrow-row {
  display: flex;
  align-items: center;
  gap: 0.7rem;
  flex-wrap: wrap;
  margin-bottom: 0.95rem;
}

.hero-eyebrow {
  position: relative;
  display: inline-flex;
  align-items: center;
  min-height: 32px;
  padding: 0.3rem 0.88rem;
  font-size: 0.76rem;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  overflow: hidden;
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
}

.hero-eyebrow {
  color: #d9ffed;
  border-radius: 999px;
  border: 1px solid rgba(60, 190, 110, 0.26);
  background: linear-gradient(135deg, rgba(40, 150, 70, 0.18), rgba(10, 28, 16, 0.56));
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.04), 0 10px 24px rgba(30, 120, 60, 0.14);
}

.hero-eyebrow::after {
  content: '';
  position: absolute;
  inset: -30% auto -30% -24%;
  width: 42%;
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.28), transparent);
  transform: skewX(-18deg);
  animation: heroSheen 7s linear infinite;
}

.hero-title {
  margin: 0;
  font-size: clamp(2rem, 3vw, 3.08rem);
  line-height: 0.98;
  font-weight: 850;
  letter-spacing: -0.05em;
  color: #f5fbff;
  text-wrap: balance;
  text-shadow: 0 10px 34px rgba(0, 0, 0, 0.24), 0 0 54px rgba(60, 200, 110, 0.18);
}

.hero-meta-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.78rem;
  margin-top: 1.08rem;
}

.hero-meta-chip {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: 0.7rem;
  min-height: 58px;
  padding: 0.78rem 1.05rem;
  border: 1px solid rgba(255, 255, 255, 0.10);
  color: var(--text-primary);
  overflow: hidden;
  isolation: isolate;
  transition: transform var(--t-base) var(--ease-out), border-color var(--t-fast), box-shadow var(--t-fast), background var(--t-fast);
}

.hero-meta-chip:hover {
  transform: translateY(-4px);
  box-shadow: 0 20px 48px rgba(0, 3, 18, 0.26);
}

.hero-meta-chip::before,
.hero-meta-chip::after {
  content: '';
  position: absolute;
  pointer-events: none;
}

.hero-meta-chip::before {
  inset: -1px;
  opacity: 0.75;
  background: linear-gradient(115deg, transparent 10%, rgba(255, 255, 255, 0.14) 30%, transparent 48%, transparent 70%, rgba(255, 255, 255, 0.08) 88%, transparent);
  transform: translateX(-72%);
  transition: transform 0.9s var(--ease-out);
}

.hero-meta-chip:hover::before {
  transform: translateX(52%);
}

.hero-meta-chip::after {
  inset: 1px;
  border-radius: inherit;
  z-index: -1;
}

.hero-meta-chip--neutral {
  border-radius: 18px;
  background: linear-gradient(145deg, rgba(8, 22, 12, 0.82), rgba(5, 14, 9, 0.72));
  border-color: rgba(200, 240, 220, 0.14);
}

.hero-meta-chip--neutral::after {
  background: radial-gradient(circle at top left, rgba(255, 255, 255, 0.10), transparent 42%), linear-gradient(145deg, rgba(140, 200, 170, 0.12), rgba(8, 22, 12, 0.08));
}

.hero-meta-chip--cyan {
  border-radius: 20px 20px 20px 12px;
  background: linear-gradient(135deg, rgba(20, 80, 50, 0.34), rgba(6, 18, 11, 0.72));
  border-color: rgba(34, 211, 180, 0.28);
}

.hero-meta-chip--cyan::after {
  background: radial-gradient(circle at top left, rgba(34, 211, 180, 0.24), transparent 38%), linear-gradient(135deg, rgba(34, 211, 180, 0.10), rgba(6, 18, 11, 0.02));
}

.hero-meta-chip--violet {
  border-radius: 16px 22px 16px 22px;
  background: linear-gradient(135deg, rgba(91, 33, 182, 0.26), rgba(8, 20, 12, 0.74));
  border-color: rgba(167, 139, 250, 0.30);
}

.hero-meta-chip--violet::after {
  background: radial-gradient(circle at top left, rgba(192, 132, 252, 0.22), transparent 38%), linear-gradient(135deg, rgba(167, 139, 250, 0.10), rgba(6, 18, 11, 0.02));
}

.hero-meta-chip-label {
  position: relative;
  font-size: 0.68rem;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  color: color-mix(in srgb, var(--text-secondary) 78%, white);
}

.hero-meta-chip-value {
  position: relative;
  font-size: 0.9rem;
  font-weight: 800;
  color: var(--text-primary);
  text-shadow: 0 1px 0 rgba(255, 255, 255, 0.03);
}

.dashboard-subtext {
  margin-top: 0.95rem;
  font-size: 0.98rem;
  color: color-mix(in srgb, var(--text-secondary) 92%, white 8%);
  line-height: 1.72;
  max-width: 58ch;
}

.dashboard-hero-message {
  margin-top: 1rem;
  color: rgba(222, 234, 255, 0.94);
  line-height: 1.8;
  font-size: 1rem;
  max-width: 64ch;
}

.hero-highlight-wrap {
  display: flex;
  flex-wrap: wrap;
  gap: 0.7rem;
  margin-top: 1.18rem;
}

.status-pill {
  position: relative;
  display: inline-flex;
  align-items: center;
  min-height: 38px;
  padding: 0.42rem 0.94rem;
  border-radius: 999px;
  background: linear-gradient(145deg, rgba(255, 255, 255, 0.07), rgba(255, 255, 255, 0.03));
  color: var(--text-primary);
  font-size: 0.82rem;
  font-weight: 800;
  overflow: hidden;
  isolation: isolate;
}

.status-pill::before {
  content: '';
  width: 7px;
  height: 7px;
  margin-right: 0.56rem;
  border-radius: 999px;
  background: currentColor;
  box-shadow: 0 0 0 4px color-mix(in srgb, currentColor 18%, transparent), 0 0 18px color-mix(in srgb, currentColor 30%, transparent);
}

.status-pill:nth-child(1) { border: 1px solid rgba(96, 165, 250, 0.24); color: #bfdbfe; }
.status-pill:nth-child(2) { border: 1px solid rgba(45, 212, 191, 0.24); color: #99f6e4; }
.status-pill:nth-child(3) { border: 1px solid rgba(244, 114, 182, 0.24); color: #fbcfe8; }

/* ──────────────────────────────────────────────────────────────
   § 8  SHOWCASE CAROUSEL
   ────────────────────────────────────────────────────────────── */
.dashboard-hero-aside {
  align-self: stretch;
}

.showcase-card {
  position: relative;
  display: flex;
  flex-direction: column;
  width: 100%;
  min-height: 100%;
  padding: 1rem;
  border-radius: 28px;
  background:
    linear-gradient(160deg, rgba(5, 16, 10, 0.88), rgba(7, 20, 12, 0.78)),
    radial-gradient(circle at top right, rgba(60, 200, 110, 0.12), transparent 32%),
    radial-gradient(circle at bottom left, rgba(167, 139, 250, 0.10), transparent 28%);
  border: 1px solid rgba(255, 255, 255, 0.10);
  box-shadow: var(--shadow-md), inset 0 1px 0 rgba(255, 255, 255, 0.05);
  backdrop-filter: blur(22px);
  -webkit-backdrop-filter: blur(22px);
  overflow: hidden;
  isolation: isolate;
  transition: transform var(--t-base) var(--ease-out), box-shadow var(--t-base), border-color var(--t-fast);
}

.showcase-card::before {
  content: '';
  position: absolute;
  inset: -1px;
  border-radius: inherit;
  background: conic-gradient(from 0deg, transparent 0deg 40deg, rgba(60, 200, 110, 0.54) 78deg, transparent 126deg, transparent 185deg, rgba(167, 139, 250, 0.42) 230deg, transparent 286deg, rgba(45, 212, 170, 0.42) 326deg, transparent 360deg);
  opacity: 0.72;
  animation: showcaseBorderSpin 9s linear infinite;
  z-index: -2;
}

.showcase-card::after {
  content: '';
  position: absolute;
  inset: 1px;
  border-radius: calc(28px - 1px);
  background: linear-gradient(160deg, rgba(6, 18, 11, 0.94), rgba(8, 20, 12, 0.84));
  z-index: -1;
}

.showcase-card:hover {
  transform: translateY(-6px);
  border-color: rgba(125, 211, 252, 0.22);
  box-shadow: 0 36px 92px rgba(0, 3, 18, 0.50), 0 0 0 1px rgba(96, 165, 250, 0.06) inset;
}

.showcase-heading-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 0.8rem;
}

.showcase-kicker {
  font-size: 0.74rem;
  text-transform: uppercase;
  letter-spacing: 0.16em;
  font-weight: 900;
  color: #8fd4ff;
}

.showcase-mini-label {
  margin-top: 0.28rem;
  color: color-mix(in srgb, var(--text-secondary) 90%, white 10%);
  font-size: 0.82rem;
}

.showcase-controls {
  display: flex;
  gap: 0.4rem;
  padding: 0.26rem;
  border-radius: 16px;
  background: linear-gradient(145deg, rgba(255, 255, 255, 0.07), rgba(255, 255, 255, 0.03));
  border: 1px solid rgba(255, 255, 255, 0.08);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.04);
}

.showcase-nav-btn {
  width: 38px;
  height: 38px;
  border: none;
  border-radius: 13px;
  background: rgba(255, 255, 255, 0.06);
  color: var(--text-primary);
  cursor: pointer;
  transition: transform var(--t-fast), background var(--t-fast), box-shadow var(--t-fast);
}

.showcase-nav-btn:hover {
  background: rgba(255, 255, 255, 0.10);
  box-shadow: 0 10px 24px rgba(0, 3, 18, 0.22);
}

.showcase-nav-btn:first-child:hover { transform: translateX(-2px) translateY(-1px) scale(1.04); }
.showcase-nav-btn:last-child:hover  { transform: translateX(2px) translateY(-1px) scale(1.04); }

.showcase-body {
  display: flex;
  flex-direction: column;
  gap: 0.88rem;
  flex: 1;
}

.showcase-image {
  position: relative;
  aspect-ratio: 16 / 8;
  width: 100%;
  border-radius: 22px;
  overflow: hidden;
  background-size: cover;
  background-position: center;
  border: 1px solid rgba(255, 255, 255, 0.08);
  box-shadow: 0 22px 50px rgba(0, 3, 18, 0.26);
  transition: transform var(--t-slow) var(--ease-out), filter var(--t-slow), box-shadow var(--t-slow);
}

.showcase-image::before {
  content: '';
  position: absolute;
  inset: -35% auto auto -18%;
  width: 42%;
  height: 170%;
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.22), transparent);
  transform: skewX(-16deg);
  animation: showcaseImageSheen 10s ease-in-out infinite;
}

.showcase-card:hover .showcase-image {
  transform: translateY(-2px) scale(1.022);
  filter: saturate(1.12) contrast(1.02);
  box-shadow: 0 28px 62px rgba(0, 3, 18, 0.34);
}

.showcase-image-overlay {
  position: absolute;
  inset: 0;
  background:
    linear-gradient(180deg, rgba(0, 3, 18, 0.04), rgba(0, 3, 18, 0.38)),
    radial-gradient(circle at top right, rgba(255, 255, 255, 0.10), transparent 28%);
}

.showcase-copy {
  display: flex;
  flex-direction: column;
  flex: 1;
}

.showcase-title {
  margin: 0;
  color: var(--text-primary);
  font-size: 1.12rem;
  font-weight: 850;
  line-height: 1.35;
  letter-spacing: -0.02em;
}

.showcase-summary {
  margin: 0.4rem 0 0;
  color: color-mix(in srgb, var(--text-secondary) 90%, white 10%);
  font-size: 0.9rem;
  line-height: 1.72;
}

.showcase-footer {
  margin-top: auto;
  padding-top: 1rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
}

.showcase-dots {
  display: flex;
  align-items: center;
  gap: 0.42rem;
}

.showcase-dot {
  width: 8px;
  height: 8px;
  border: none;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.20);
  cursor: pointer;
  transition: background var(--t-fast), width var(--t-base), box-shadow var(--t-fast), transform var(--t-fast);
}

.showcase-dot:hover {
  transform: translateY(-1px) scale(1.08);
}

.showcase-dot.active {
  width: 22px;
  background: linear-gradient(90deg, #60a5fa, #7c3aed);
  box-shadow: 0 0 14px rgba(96, 165, 250, 0.45);
}

.showcase-link-btn {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: 0.52rem;
  min-height: 40px;
  padding: 0.5rem 0.96rem;
  border-radius: 999px;
  border: 1px solid rgba(60, 200, 110, 0.26);
  background: linear-gradient(145deg, rgba(40, 160, 80, 0.16), rgba(30, 130, 60, 0.08));
  color: #d6ffec;
  cursor: pointer;
  font-weight: 800;
  font-size: 0.84rem;
  overflow: hidden;
  transition: transform var(--t-fast), background var(--t-fast), border-color var(--t-fast), box-shadow var(--t-fast);
}

.showcase-link-btn::before {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(100deg, transparent 18%, rgba(255, 255, 255, 0.16) 50%, transparent 82%);
  transform: translateX(-110%);
  transition: transform 0.8s ease;
}

.showcase-link-btn:hover::before {
  transform: translateX(110%);
}

.showcase-link-btn:hover {
  transform: translateY(-2px);
  background: linear-gradient(145deg, rgba(40, 160, 80, 0.24), rgba(30, 130, 60, 0.12));
  border-color: rgba(80, 220, 140, 0.42);
  box-shadow: 0 14px 30px rgba(30, 130, 60, 0.18);
}

.showcase-fade-enter-active,
.showcase-fade-leave-active {
  transition: opacity 0.34s ease, transform 0.34s ease;
}

.showcase-fade-enter-from,
.showcase-fade-leave-to {
  opacity: 0;
  transform: translateY(10px) scale(0.99);
}

@keyframes showcaseBorderSpin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

@keyframes showcaseImageSheen {
  0%, 72%, 100% { transform: translateX(0) skewX(-16deg); opacity: 0; }
  10%, 42% { opacity: 1; }
  50% { transform: translateX(240%) skewX(-16deg); opacity: 0; }
}

@keyframes heroSheen {
  0%, 100% { transform: translateX(0) skewX(-18deg); opacity: 0; }
  14%, 34% { opacity: 1; }
  46% { transform: translateX(260%) skewX(-18deg); opacity: 0; }
}

/* ──────────────────────────────────────────────────────────────
   § 10  SUMMARY CARDS  (vivid neon top-border differentiates each)
   ────────────────────────────────────────────────────────────── */
.summary-card {
  position: relative;
  overflow: hidden;
  min-height: 170px;
  padding: 1.25rem 1.2rem 1.1rem;
  border-radius: var(--radius-card);
  border: 1px solid rgba(255, 255, 255, 0.09);
  background: linear-gradient(160deg, rgba(6, 18, 12, 0.90), rgba(7, 16, 10, 0.76));
  box-shadow: var(--shadow-md);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  transition: transform var(--t-base) var(--ease-out), box-shadow var(--t-base), border-color var(--t-fast);
}

.summary-card::before {
  content: '';
  position: absolute;
  top: 0; left: 0; right: 0;
  height: 2.5px;
  border-radius: var(--radius-card) var(--radius-card) 0 0;
}

.summary-card::after {
  content: '';
  position: absolute;
  right: -24px; top: -28px;
  width: 130px; height: 130px;
  border-radius: 999px;
  opacity: 0.32;
  pointer-events: none;
}

.summary-card:hover { transform: translateY(-7px) scale(1.014); box-shadow: var(--shadow-lg); }
.summary-card:hover .summary-icon-wrap { transform: translateY(-4px) rotate(-8deg); }

.accent-blue::before  { background: linear-gradient(90deg, transparent, #60a5fa, #38bdf8, transparent); }
.accent-blue::after   { background: radial-gradient(circle, rgba(96, 165, 250, 0.9), transparent 70%); }
.accent-blue:hover    { border-color: rgba(96, 165, 250, 0.26); }
.accent-blue .summary-icon-wrap { color: #93c5fd; }

.accent-violet::before { background: linear-gradient(90deg, transparent, #a78bfa, #c084fc, transparent); }
.accent-violet::after  { background: radial-gradient(circle, rgba(167, 139, 250, 0.88), transparent 70%); }
.accent-violet:hover   { border-color: rgba(167, 139, 250, 0.26); }
.accent-violet .summary-icon-wrap { color: #c4b5fd; }

.accent-teal::before { background: linear-gradient(90deg, transparent, #2dd4bf, #5eead4, transparent); }
.accent-teal::after  { background: radial-gradient(circle, rgba(45, 212, 191, 0.9), transparent 70%); }
.accent-teal:hover   { border-color: rgba(45, 212, 191, 0.26); }
.accent-teal .summary-icon-wrap { color: #5eead4; }

.accent-amber::before { background: linear-gradient(90deg, transparent, #fbbf24, #fcd34d, transparent); }
.accent-amber::after  { background: radial-gradient(circle, rgba(251, 191, 36, 0.88), transparent 70%); }
.accent-amber:hover   { border-color: rgba(251, 191, 36, 0.26); }
.accent-amber .summary-icon-wrap { color: #fcd34d; }

.accent-rose::before { background: linear-gradient(90deg, transparent, #f87171, #fb7185, transparent); }
.accent-rose::after  { background: radial-gradient(circle, rgba(248, 113, 113, 0.86), transparent 70%); }
.accent-rose:hover   { border-color: rgba(248, 113, 113, 0.26); }
.accent-rose .summary-icon-wrap { color: #fca5a5; }

.summary-card-top { display: flex; align-items: center; gap: 0.8rem; }

.summary-icon-wrap {
  width: 46px; height: 46px;
  border-radius: 14px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.07);
  border: 1px solid rgba(255, 255, 255, 0.10);
  font-size: 0.96rem;
  transition: transform var(--t-base) var(--ease-out), box-shadow var(--t-fast);
}

.summary-label   { color: var(--text-secondary); font-size: 0.91rem; font-weight: 700; }
.summary-card-value { margin-top: 1rem; font-size: clamp(2rem, 3vw, 2.5rem); line-height: 1; font-weight: 800; color: var(--text-primary); letter-spacing: -0.05em; }
.summary-card-subtext { margin-top: 0.65rem; max-width: 26ch; color: var(--text-muted); font-size: 0.87rem; line-height: 1.55; }

/* ──────────────────────────────────────────────────────────────
   § 11  SURFACE CARDS  (generic feature card base)
   ────────────────────────────────────────────────────────────── */
.surface-card {
  position: relative;
  overflow: hidden;
  border-radius: var(--radius-card);
  padding: 1.25rem;
  border: 1px solid rgba(255, 255, 255, 0.09);
  background: linear-gradient(160deg, rgba(6, 18, 12, 0.86), rgba(7, 16, 10, 0.72));
  box-shadow: var(--shadow-md);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
}

.feature-card { min-height: 100%; }

.surface-card-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 1rem; margin-bottom: 1.1rem; }

/* HUD-style kicker: animated dot + label */
.surface-kicker {
  margin: 0 0 0.22rem;
  font-size: 0.72rem;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.10em;
  color: #3cc87a;
  display: flex;
  align-items: center;
  gap: 0.42rem;
}

.surface-kicker::before {
  content: '';
  display: inline-block;
  width: 6px; height: 6px;
  border-radius: 50%;
  background: #3cc87a;
  box-shadow: 0 0 8px rgba(60, 200, 110, 0.85);
  flex-shrink: 0;
  animation: hud-pulse 2.2s ease-in-out infinite;
}

@keyframes hud-pulse {
  0%, 100% { opacity: 1; box-shadow: 0 0 8px rgba(60, 200, 110, 0.85); }
  50%       { opacity: 0.52; box-shadow: 0 0 4px rgba(60, 200, 110, 0.38); }
}

.surface-card-title { margin: 0; color: var(--text-primary); font-size: 1.12rem; font-weight: 800; letter-spacing: -0.02em; }

.surface-link {
  display: inline-flex;
  align-items: center;
  min-height: 34px;
  padding: 0.36rem 0.78rem;
  border-radius: var(--radius-chip);
  background: rgba(255, 255, 255, 0.04);
  color: #7adfc8;
  border: 1px solid rgba(60, 200, 120, 0.16);
  text-decoration: none;
  font-size: 0.82rem;
  font-weight: 700;
  transition: transform var(--t-fast), border-color var(--t-fast), background var(--t-fast);
}

.surface-link:hover { transform: translateY(-1px); border-color: rgba(60, 200, 120, 0.32); background: rgba(60, 200, 120, 0.09); }

/* ──────────────────────────────────────────────────────────────
   § 12  ACTION CENTER  (cyberpunk terminal aesthetic)
   ────────────────────────────────────────────────────────────── */
/* ──────────────────────────────────────────────────────────────
   § 13  PROGRESS CARD  (orbital ring display)
   ────────────────────────────────────────────────────────────── */
.progress-card { border-color: rgba(167, 139, 250, 0.16); }

.progress-card::after {
  content: '';
  position: absolute;
  bottom: -20%; right: -10%;
  width: 38%; aspect-ratio: 1;
  border-radius: 999px;
  background: radial-gradient(circle, rgba(103, 232, 249, 0.10), transparent 70%);
  pointer-events: none;
  filter: blur(16px);
}

.progress-layout { display: flex; gap: 1.1rem; align-items: center; flex-wrap: wrap; }

.progress-ring-shell { flex: 0 0 148px; display: flex; justify-content: center; position: relative; isolation: isolate; }

.progress-ring {
  position: relative;
  width: 130px; height: 130px;
  border-radius: 999px;
  padding: 10px;
  box-shadow: 0 24px 52px rgba(0, 3, 18, 0.40), inset 0 0 0 1px rgba(255, 255, 255, 0.04);
  transition: transform var(--t-slow) var(--ease-out), box-shadow var(--t-base);
}

/* Radial halo — breathing */
.progress-ring::before {
  content: '';
  position: absolute;
  inset: -16px;
  border-radius: 999px;
  background: radial-gradient(circle, rgba(60, 200, 110, 0.16), rgba(167, 139, 250, 0.12) 52%, transparent 74%);
  z-index: -1;
  animation: halo-breath 6s ease-in-out infinite;
}

/* Orbiting arc */
.progress-ring::after {
  content: '';
  position: absolute;
  inset: -8px;
  border-radius: 999px;
  background: conic-gradient(
    from 0deg,
    transparent 0deg, transparent 30deg,
    rgba(60, 200, 110, 0.85) 46deg,
    rgba(45, 212, 170, 0.70) 80deg,
    transparent 118deg, transparent 360deg
  );
  -webkit-mask: radial-gradient(circle, transparent 58%, black 64%, black 73%, transparent 78%);
  mask: radial-gradient(circle, transparent 58%, black 64%, black 73%, transparent 78%);
  animation: orbit-spin 6s linear infinite;
  opacity: 0.82;
}

.progress-ring-inner {
  width: 100%; height: 100%;
  border-radius: 999px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: linear-gradient(180deg, rgba(5, 16, 10, 0.97), rgba(5, 14, 9, 0.97));
  border: 1px solid rgba(255, 255, 255, 0.05);
}

.progress-card:hover .progress-ring { transform: scale(1.06); box-shadow: 0 32px 64px rgba(0, 3, 18, 0.46), 0 0 38px rgba(96, 165, 250, 0.12); }

.progress-value { font-size: 1.85rem; font-weight: 800; color: var(--text-primary); letter-spacing: -0.04em; }
.progress-label { margin-top: 0.14rem; color: var(--text-muted); font-size: 0.78rem; font-weight: 700; }

.progress-details { flex: 1; min-width: 220px; }

.progress-detail-row {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.70rem 0.82rem;
  border-radius: 12px;
  color: var(--text-secondary);
  transition: transform var(--t-fast), background var(--t-fast);
}

.progress-detail-row:hover { transform: translateX(4px); background: rgba(255, 255, 255, 0.04); }
.progress-detail-row strong { color: var(--text-primary); font-weight: 800; }

.progress-bar-shell { margin-top: 0.9rem; height: 8px; border-radius: 999px; background: rgba(255, 255, 255, 0.06); overflow: visible; }

.progress-bar-fill {
  position: relative;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #38bdf8 0%, #2dd4bf 36%, #818cf8 74%, #f472b6 100%);
  box-shadow: 0 0 16px rgba(96, 165, 250, 0.32);
}

/* Glowing end-dot */
.progress-bar-fill::after {
  content: '';
  position: absolute;
  right: -7px; top: 50%;
  width: 16px; height: 16px;
  border-radius: 50%;
  transform: translateY(-50%);
  background: radial-gradient(circle, white, rgba(255, 255, 255, 0.12));
  box-shadow: 0 0 12px rgba(103, 232, 249, 0.65), 0 0 4px rgba(255, 255, 255, 0.85);
}

@keyframes orbit-spin  { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
@keyframes halo-breath { 0%, 100% { transform: scale(0.95); opacity: 0.70; } 50% { transform: scale(1.07); opacity: 1; } }

/* ──────────────────────────────────────────────────────────────
   § 14  EVENTS CARD  (calendar badge style)
   ────────────────────────────────────────────────────────────── */
.event-detail-card {
  display: flex;
  gap: 1rem;
  align-items: stretch;
  padding: 0.88rem;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.07);
}

.event-date-badge {
  flex: 0 0 82px;
  min-height: 96px;
  border-radius: 16px;
  padding: 0.82rem 0.72rem;
  background: linear-gradient(145deg, rgba(56, 189, 248, 0.24), rgba(45, 212, 191, 0.12));
  border: 1px solid rgba(56, 189, 248, 0.26);
  display: flex;
  flex-direction: column;
  justify-content: center;
  text-align: center;
  box-shadow: 0 0 24px rgba(56, 189, 248, 0.14);
  transition: transform var(--t-base) var(--ease-out), box-shadow var(--t-fast);
}

.event-detail-card:hover .event-date-badge { transform: rotate(-4deg) translateY(-4px); box-shadow: 0 0 34px rgba(56, 189, 248, 0.24); }

.event-date-day  { color: #f0f8ff; font-size: 1.5rem; font-weight: 800; line-height: 1; }
.event-date-rest { margin-top: 0.34rem; color: rgba(186, 230, 255, 0.88); font-size: 0.80rem; line-height: 1.3; }

.event-content { flex: 1; min-width: 0; transition: transform var(--t-base); }
.event-detail-card:hover .event-content { transform: translateX(3px); }

.event-title { font-size: 1.08rem; font-weight: 800; color: var(--text-primary); }

.event-meta-row { display: flex; flex-wrap: wrap; gap: 0.88rem; margin-top: 0.62rem; color: var(--text-secondary); font-size: 0.90rem; }
.event-meta-row span { display: inline-flex; align-items: center; gap: 0.42rem; }
.location-row { margin-top: 0.42rem; }
.event-actions { margin-top: 0.82rem; }

.primary-chip {
  display: inline-flex;
  align-items: center;
  min-height: 38px;
  padding: 0.48rem 0.9rem;
  border-radius: var(--radius-chip);
  background: linear-gradient(135deg, rgba(37, 99, 235, 0.24), rgba(45, 212, 191, 0.16));
  color: #bfdbfe;
  text-decoration: none;
  font-size: 0.84rem;
  font-weight: 700;
  border: 1px solid rgba(96, 165, 250, 0.24);
  transition: transform var(--t-fast), background var(--t-fast), box-shadow var(--t-fast);
}

.primary-chip:hover {
  transform: translateY(-2px);
  background: linear-gradient(135deg, rgba(37, 99, 235, 0.34), rgba(45, 212, 191, 0.26));
  box-shadow: 0 12px 28px rgba(37, 99, 235, 0.22);
}

/* ──────────────────────────────────────────────────────────────
   § 15  LISTS  (announcements)
   ────────────────────────────────────────────────────────────── */
.list-stack { display: flex; flex-direction: column; gap: 0.70rem; }

.list-row { display: flex; align-items: flex-start; gap: 0.82rem; text-decoration: none; color: inherit; }

.premium-row {
  padding: 0.85rem 0.95rem;
  border-radius: 16px;
  border: 1px solid rgba(255, 255, 255, 0.07);
  background: rgba(255, 255, 255, 0.03);
  transition: transform var(--t-base) var(--ease-out), border-color var(--t-fast), background var(--t-fast);
}

.premium-row:hover { transform: translateX(5px); border-color: rgba(251, 191, 36, 0.22); background: rgba(251, 191, 36, 0.05); }

.list-row-icon {
  width: 40px; height: 40px;
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 12px;
  font-size: 0.90rem;
  border: 1px solid rgba(255, 255, 255, 0.08);
  transition: transform var(--t-fast), box-shadow var(--t-fast);
}

.announcement-icon { background: rgba(251, 191, 36, 0.12); color: #fcd34d; }

.premium-row:hover .announcement-icon { transform: scale(1.08) rotate(-8deg); box-shadow: 0 10px 22px rgba(251, 191, 36, 0.22); }

.list-row-content { min-width: 0; flex: 1; }
.list-row-title       { color: var(--text-primary); font-weight: 800; line-height: 1.45; }
.list-row-meta        { margin-top: 0.14rem; color: var(--text-muted); font-size: 0.84rem; }
.list-row-description { margin-top: 0.24rem; color: var(--text-secondary); font-size: 0.87rem; line-height: 1.55; }
.list-row-tail        { color: var(--text-muted); padding-top: 0.18rem; transition: transform var(--t-fast), color var(--t-fast); }
.premium-row:hover .list-row-tail { transform: translateX(3px); color: var(--text-secondary); }

/* ──────────────────────────────────────────────────────────────
   § 16  GROUPS GRID  (identity cards — distinct per card)
   ────────────────────────────────────────────────────────────── */
.groups-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 1.1rem; }

.group-card-link,
.resource-card-link { display: block; text-decoration: none; color: inherit; }

.group-card-surface {
  position: relative;
  overflow: hidden;
  height: 100%;
  padding: 1rem;
  border-radius: 20px;
  border: 1px solid rgba(255, 255, 255, 0.09);
  transition: transform var(--t-slow) var(--ease-out), box-shadow var(--t-base), border-color var(--t-fast);
}

.group-card-link:nth-child(1) .group-card-surface { background: linear-gradient(150deg, rgba(20, 100, 50, 0.28), rgba(5, 15, 9, 0.84) 50%); border-color: rgba(60, 200, 120, 0.18); }
.group-card-link:nth-child(2) .group-card-surface { background: linear-gradient(150deg, rgba(91, 33, 182, 0.28), rgba(5, 15, 9, 0.84) 50%); border-color: rgba(167, 139, 250, 0.18); }
.group-card-link:nth-child(3) .group-card-surface { background: linear-gradient(150deg, rgba(13, 148, 100, 0.28), rgba(5, 15, 9, 0.84) 50%); border-color: rgba(45, 212, 170, 0.18); }
.group-card-link:nth-child(4) .group-card-surface { background: linear-gradient(150deg, rgba(234, 88, 12, 0.26), rgba(5, 15, 9, 0.84) 50%); border-color: rgba(251, 146, 60, 0.18); }

/* Bottom shine sweep */
.group-card-surface::after {
  content: '';
  position: absolute;
  inset: auto 16px 14px;
  height: 2px; border-radius: 999px;
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.72), transparent);
  transform: scaleX(0.26); transform-origin: center;
  opacity: 0;
  transition: opacity var(--t-fast), transform var(--t-base) var(--ease-out);
}

.group-card-link:hover .group-card-surface { transform: translateY(-10px) rotateX(2deg) rotateY(-2deg); box-shadow: 0 28px 60px rgba(0, 3, 18, 0.38); }
.group-card-link:hover .group-card-surface::after { opacity: 1; transform: scaleX(1); }

.group-card-top { display: flex; align-items: center; justify-content: space-between; gap: 0.72rem; }
.group-avatars  { display: flex; align-items: center; flex-shrink: 0; }

.group-avatar {
  width: 2.35rem; height: 2.35rem;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 2px solid rgba(7, 13, 28, 0.82);
  margin-left: -0.30rem;
  font-size: 0.74rem; font-weight: 800;
  box-shadow: 0 8px 20px rgba(0, 3, 18, 0.26);
  transition: transform var(--t-base) var(--ease-out);
}

.group-avatar:first-child { margin-left: 0; }

.group-card-link:nth-child(1) .primary-avatar { background: linear-gradient(135deg, #60a5fa, #22d3ee); color: #0c4a6e; }
.group-card-link:nth-child(2) .primary-avatar { background: linear-gradient(135deg, #a78bfa, #f472b6); color: #2e1065; }
.group-card-link:nth-child(3) .primary-avatar { background: linear-gradient(135deg, #34d399, #38bdf8); color: #064e3b; }
.group-card-link:nth-child(4) .primary-avatar { background: linear-gradient(135deg, #fb923c, #facc15); color: #431407; }

.secondary-avatar { background: linear-gradient(135deg, #0f766e, #14b8a6); color: #ccfbf1; }
.tertiary-avatar  { background: linear-gradient(135deg, #7c3aed, #a78bfa); color: #ede9fe; }

.group-card-link:hover .primary-avatar   { transform: translateX(-8px) translateY(-2px) scale(1.08); }
.group-card-link:hover .secondary-avatar { transform: translateX(2px) translateY(3px); }
.group-card-link:hover .tertiary-avatar  { transform: translateX(10px) translateY(-2px); }

.group-open-indicator {
  width: 32px; height: 32px;
  border-radius: 10px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.07);
  color: #7ec8ff;
  border: 1px solid rgba(255, 255, 255, 0.10);
  transition: transform var(--t-fast);
}

.group-card-link:hover .group-open-indicator { transform: translateY(-2px) scale(1.08); }

.group-name { margin-top: 0.9rem; color: var(--text-primary); font-size: 0.98rem; font-weight: 800; }
.group-meta { margin-top: 0.26rem; color: var(--text-secondary); font-size: 0.86rem; line-height: 1.5; }

/* ──────────────────────────────────────────────────────────────
   § 17  RESOURCES GRID  (color-coded left accent bar)
   ────────────────────────────────────────────────────────────── */
.resource-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0.88rem; }

.resource-card-surface {
  position: relative;
  overflow: hidden;
  height: 100%;
  display: flex;
  align-items: flex-start;
  gap: 0.85rem;
  padding: 1rem;
  border-radius: 18px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  transition: transform var(--t-base) var(--ease-out), box-shadow var(--t-base), border-color var(--t-fast);
}

/* Left accent bar */
.resource-card-surface::before {
  content: '';
  position: absolute;
  left: 0; top: 12px; bottom: 12px;
  width: 4px; border-radius: 0 3px 3px 0;
  opacity: 0.72;
  transition: width var(--t-fast), opacity var(--t-fast);
}

.resource-card-link:nth-child(1) .resource-card-surface { background: linear-gradient(155deg, rgba(40, 140, 70, 0.16), rgba(5, 15, 9, 0.80) 50%); border-color: rgba(60, 200, 110, 0.16); }
.resource-card-link:nth-child(1) .resource-card-surface::before { background: #3cc87a; }
.resource-card-link:nth-child(2) .resource-card-surface { background: linear-gradient(155deg, rgba(168, 85, 247, 0.16), rgba(5, 15, 9, 0.80) 50%); border-color: rgba(167, 139, 250, 0.16); }
.resource-card-link:nth-child(2) .resource-card-surface::before { background: #a78bfa; }
.resource-card-link:nth-child(3) .resource-card-surface { background: linear-gradient(155deg, rgba(45, 212, 170, 0.16), rgba(5, 15, 9, 0.80) 50%); border-color: rgba(45, 212, 170, 0.16); }
.resource-card-link:nth-child(3) .resource-card-surface::before { background: #2dd4aa; }
.resource-card-link:nth-child(4) .resource-card-surface { background: linear-gradient(155deg, rgba(244, 114, 182, 0.16), rgba(5, 15, 9, 0.80) 50%); border-color: rgba(244, 114, 182, 0.16); }
.resource-card-link:nth-child(4) .resource-card-surface::before { background: #f472b6; }
.resource-card-link:nth-child(5) .resource-card-surface { background: linear-gradient(155deg, rgba(251, 191, 36, 0.16), rgba(5, 15, 9, 0.80) 50%); border-color: rgba(251, 191, 36, 0.16); }
.resource-card-link:nth-child(5) .resource-card-surface::before { background: #fbbf24; }
.resource-card-link:nth-child(6) .resource-card-surface { background: linear-gradient(155deg, rgba(16, 185, 100, 0.16), rgba(5, 15, 9, 0.80) 50%); border-color: rgba(52, 200, 140, 0.16); }
.resource-card-link:nth-child(6) .resource-card-surface::before { background: #34d399; }

.resource-card-link:hover .resource-card-surface { transform: translateY(-6px) rotateZ(-0.4deg); box-shadow: 0 24px 52px rgba(0, 3, 18, 0.34); }
.resource-card-link:hover .resource-card-surface::before { width: 7px; opacity: 1; }

.resource-icon {
  width: 44px; height: 44px;
  flex-shrink: 0; border-radius: 13px;
  display: inline-flex; align-items: center; justify-content: center;
  background: rgba(255, 255, 255, 0.07);
  color: #93c5fd;
  border: 1px solid rgba(255, 255, 255, 0.08);
  transition: transform var(--t-base) var(--ease-out), box-shadow var(--t-fast);
}

.resource-card-link:hover .resource-icon { transform: translateY(-3px) rotate(8deg); box-shadow: 0 14px 28px rgba(96, 165, 250, 0.22); }

.resource-content { min-width: 0; }
.resource-title { color: var(--text-primary); font-weight: 800; line-height: 1.45; }
.resource-meta  { margin-top: 0.22rem; color: var(--text-secondary); font-size: 0.84rem; line-height: 1.5; }

/* ──────────────────────────────────────────────────────────────
   § 18  TIMELINE  (sci-fi roadmap with connecting line)
   ────────────────────────────────────────────────────────────── */
/* ──────────────────────────────────────────────────────────────
   § 19  ALERT, LOADING, EMPTY STATE
   ────────────────────────────────────────────────────────────── */
.dashboard-alert {
  display: flex; align-items: center; gap: 0.65rem;
  padding: 0.9rem 1rem; margin-bottom: 1.25rem;
  border-radius: 16px;
  background: rgba(251, 191, 36, 0.08);
  border: 1px solid rgba(251, 191, 36, 0.20);
  color: #fcd34d;
  box-shadow: var(--shadow-sm);
  backdrop-filter: blur(16px);
}

.dashboard-loading {
  position: fixed; right: 1.35rem; bottom: 1.35rem; z-index: 20;
  display: inline-flex; align-items: center; gap: 0.65rem;
  padding: 0.72rem 1rem;
  border-radius: var(--radius-chip);
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: linear-gradient(160deg, rgba(6, 18, 12, 0.92), rgba(7, 16, 10, 0.86));
  color: var(--text-primary);
  box-shadow: var(--shadow-lg);
  backdrop-filter: blur(18px);
  -webkit-backdrop-filter: blur(18px);
}

.loading-ring {
  width: 16px; height: 16px;
  border-radius: 50%;
  border: 2px solid transparent;
  border-top-color: #38bdf8;
  border-right-color: #a78bfa;
  border-bottom-color: #2dd4bf;
  animation: spin 1s linear infinite;
}

@keyframes spin { to { transform: rotate(360deg); } }

.empty-state {
  min-height: 140px;
  border-radius: 18px;
  border: 1px dashed rgba(255, 255, 255, 0.10);
  background: rgba(255, 255, 255, 0.02);
  display: flex; align-items: center; justify-content: center;
  gap: 0.62rem; flex-direction: column;
  color: var(--text-secondary);
  text-align: center; padding: 1.5rem;
}

.empty-state i { font-size: 1.4rem; color: var(--text-muted); }

/* ──────────────────────────────────────────────────────────────
   § 20  INTERACTIVE SURFACE  (legacy compat stub)
   ────────────────────────────────────────────────────────────── */
.interactive-surface { position: relative; isolation: isolate; }

/* ──────────────────────────────────────────────────────────────
   § 21  RESPONSIVE
   ────────────────────────────────────────────────────────────── */
@media (max-width: 1400px) {
  .summary-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .groups-grid  { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}

.dashboard-page-shell.is-day-mode .dashboard-hero-message {
  color: rgba(74, 84, 100, 0.94);
}

.dashboard-page-shell.is-day-mode .dashboard-fx-canvas {
  opacity: 0.12;
}

.dashboard-page-shell.is-day-mode .orb-one {
  background: radial-gradient(circle, rgba(190, 154, 88, 0.24), rgba(190, 154, 88, 0.08) 52%, transparent 74%);
}

.dashboard-page-shell.is-day-mode .orb-two {
  background: radial-gradient(circle, rgba(92, 138, 128, 0.16), rgba(92, 138, 128, 0.06) 52%, transparent 74%);
}

.dashboard-page-shell.is-day-mode .hero-meta-chip::before,
.dashboard-page-shell.is-day-mode .showcase-card::before {
  opacity: 0.42;
}

.dashboard-page-shell.is-day-mode .showcase-card::after {
  background: linear-gradient(160deg, rgba(255, 248, 238, 0.94), rgba(246, 236, 216, 0.88));
}

.dashboard-page-shell.is-day-mode .showcase-controls,
.dashboard-page-shell.is-day-mode .showcase-nav-btn,
.dashboard-page-shell.is-day-mode .theme-rail-trigger,
.dashboard-page-shell.is-day-mode .group-open-indicator,
.dashboard-page-shell.is-day-mode .premium-row,
.dashboard-page-shell.is-day-mode .progress-ring-inner {
  box-shadow: 0 10px 26px rgba(137, 109, 53, 0.10);
}

.dashboard-page-shell.is-day-mode .group-avatar {
  border-color: rgba(250, 245, 236, 0.92);
  box-shadow: 0 10px 24px rgba(137, 109, 53, 0.16);
}

.dashboard-page-shell.is-day-mode .status-pill:nth-child(1) { color: #8a5f1f; }
.dashboard-page-shell.is-day-mode .status-pill:nth-child(2) { color: #1f7f70; }
.dashboard-page-shell.is-day-mode .status-pill:nth-child(3) { color: #7a4fc1; }

.dashboard-page-shell.is-day-mode .showcase-kicker {
  color: #8a5f1f;
}

.dashboard-page-shell.is-day-mode .announcement-icon { color: #a56418; }

.dashboard-page-shell.is-day-mode .primary-chip {
  color: #755019;
  border-color: rgba(130, 100, 40, 0.18);
  background: linear-gradient(135deg, rgba(175, 122, 22, 0.12), rgba(63, 108, 198, 0.08));
}

.dashboard-page-shell.is-day-mode .primary-chip:hover {
  background: linear-gradient(135deg, rgba(175, 122, 22, 0.16), rgba(63, 108, 198, 0.12));
  box-shadow: 0 12px 28px rgba(137, 109, 53, 0.14);
}

/* ──────────────────────────────────────────────────────────────
   § 22  DAY MODE — COMPREHENSIVE INTERACTIVE & EFFECT OVERRIDES
   Replaces neon / near-invisible dark-mode values with
   yellow-green equivalents readable on the lime-cream background.
   ────────────────────────────────────────────────────────────── */

/* --- 22.1  Design tokens ------------------------------------ */
.dashboard-page-shell.is-day-mode {
  --text-primary:   #1a3818;
  --text-secondary: #3a5e2c;
  --text-muted:     #5e8040;
  --text-link:      #265c3c;

  --surface-base:     rgba(180, 212, 140, 0.88);
  --surface-elevated: rgba(194, 224, 156, 0.94);

  --border-default: rgba(80, 130, 40, 0.18);
  --border-strong:  rgba(60, 110, 28, 0.28);

  --accent-blue:   #2a6048;
  --accent-teal:   #1f8a6a;
  --accent-violet: #7c5cb0;
  --accent-amber:  #6a9820;
  --accent-rose:   #b05060;

  --shadow-lg: 0 24px 64px rgba(30, 70, 14, 0.24);
  --shadow-md: 0 14px 38px rgba(30, 70, 14, 0.18);
  --shadow-sm: 0 8px  22px rgba(30, 70, 14, 0.12);
}

/* Backdrop grid — soften on yellow-green */
.dashboard-page-shell.is-day-mode .dashboard-backdrop-grid {
  opacity: 0.05;
  background-image:
    linear-gradient(rgba(60, 120, 30, 0.30) 1px, transparent 1px),
    linear-gradient(90deg, rgba(60, 120, 30, 0.30) 1px, transparent 1px);
}

/* --- 22.2  Hero card --------------------------------------- */
.dashboard-page-shell.is-day-mode .dashboard-hero-card {
  background: linear-gradient(145deg, rgba(210, 234, 174, 0.94), rgba(198, 222, 158, 0.82));
  border-color: rgba(90, 148, 50, 0.22);
  box-shadow: 0 24px 64px rgba(30, 70, 14, 0.18), inset 0 1px 0 rgba(240, 255, 220, 0.70);
}

.dashboard-page-shell.is-day-mode .hero-eyebrow {
  color: #1e4010;
  border-color: rgba(60, 110, 20, 0.24);
  background: linear-gradient(135deg, rgba(100, 160, 40, 0.16), rgba(188, 216, 158, 0.60));
  box-shadow: inset 0 0 0 1px rgba(120, 180, 60, 0.12), 0 8px 20px rgba(50, 100, 20, 0.12);
}

.dashboard-page-shell.is-day-mode .hero-title {
  color: #0e2c08;
  text-shadow: 0 6px 24px rgba(30, 70, 14, 0.12), 0 0 40px rgba(80, 180, 40, 0.10);
}

/* Hero meta chips — yellow-green variants */
.dashboard-page-shell.is-day-mode .hero-meta-chip {
  border-color: rgba(90, 140, 40, 0.18);
  color: var(--text-primary);
}

.dashboard-page-shell.is-day-mode .hero-meta-chip:hover {
  box-shadow: 0 18px 42px rgba(30, 70, 14, 0.18);
}

.dashboard-page-shell.is-day-mode .hero-meta-chip--neutral {
  background: linear-gradient(145deg, rgba(200, 228, 162, 0.86), rgba(186, 214, 146, 0.76));
  border-color: rgba(90, 140, 40, 0.20);
}

.dashboard-page-shell.is-day-mode .hero-meta-chip--neutral::after {
  background: radial-gradient(circle at top left, rgba(120, 180, 60, 0.12), transparent 42%),
              linear-gradient(145deg, rgba(100, 160, 50, 0.10), rgba(190, 220, 150, 0.06));
}

.dashboard-page-shell.is-day-mode .hero-meta-chip--cyan {
  background: linear-gradient(135deg, rgba(30, 110, 70, 0.18), rgba(186, 214, 158, 0.72));
  border-color: rgba(40, 150, 100, 0.28);
}

.dashboard-page-shell.is-day-mode .hero-meta-chip--cyan::after {
  background: radial-gradient(circle at top left, rgba(40, 150, 100, 0.18), transparent 38%),
              linear-gradient(135deg, rgba(40, 150, 100, 0.08), transparent);
}

.dashboard-page-shell.is-day-mode .hero-meta-chip--violet {
  background: linear-gradient(135deg, rgba(90, 60, 160, 0.16), rgba(186, 214, 158, 0.72));
  border-color: rgba(130, 100, 200, 0.28);
}

.dashboard-page-shell.is-day-mode .hero-meta-chip--violet::after {
  background: radial-gradient(circle at top left, rgba(140, 108, 210, 0.16), transparent 38%),
              linear-gradient(135deg, rgba(130, 100, 200, 0.08), transparent);
}

.dashboard-page-shell.is-day-mode .hero-meta-chip-label {
  color: var(--text-secondary);
}

.dashboard-page-shell.is-day-mode .hero-meta-chip-value {
  color: var(--text-primary);
}

/* Status pills on yellow-green */
.dashboard-page-shell.is-day-mode .status-pill {
  background: linear-gradient(145deg, rgba(140, 196, 90, 0.14), rgba(120, 180, 70, 0.08));
}

.dashboard-page-shell.is-day-mode .status-pill:nth-child(1) {
  border-color: rgba(40, 110, 60, 0.26);
  color: #1a5c2a;
}

.dashboard-page-shell.is-day-mode .status-pill:nth-child(2) {
  border-color: rgba(30, 140, 100, 0.26);
  color: #10603e;
}

.dashboard-page-shell.is-day-mode .status-pill:nth-child(3) {
  border-color: rgba(130, 80, 190, 0.22);
  color: #5e3498;
}

/* --- 22.3  Showcase card ----------------------------------- */
.dashboard-page-shell.is-day-mode .showcase-card {
  background:
    linear-gradient(160deg, rgba(206, 232, 168, 0.92), rgba(194, 220, 154, 0.82)),
    radial-gradient(circle at top right,  rgba(40, 120, 60, 0.10), transparent 32%),
    radial-gradient(circle at bottom left, rgba(124, 92, 176, 0.08), transparent 28%);
  border-color: rgba(90, 148, 40, 0.20);
  box-shadow: 0 14px 38px rgba(30, 70, 14, 0.14), inset 0 1px 0 rgba(230, 255, 200, 0.50);
}

.dashboard-page-shell.is-day-mode .showcase-card:hover {
  border-color: rgba(60, 160, 80, 0.28);
  box-shadow: 0 28px 70px rgba(30, 70, 14, 0.22), 0 0 0 1px rgba(60, 160, 80, 0.06) inset;
}

/* Spinning border — forest green/sage/teal */
.dashboard-page-shell.is-day-mode .showcase-card::before {
  background: conic-gradient(
    from 0deg,
    transparent 0deg 40deg,
    rgba(50, 140, 50, 0.50) 78deg,
    transparent 126deg, transparent 185deg,
    rgba(100, 60, 180, 0.38) 230deg,
    transparent 286deg,
    rgba(30, 140, 100, 0.38) 326deg,
    transparent 360deg
  );
  opacity: 0.60;
}

.dashboard-page-shell.is-day-mode .showcase-controls {
  background: linear-gradient(145deg, rgba(186, 216, 148, 0.70), rgba(172, 204, 132, 0.56));
  border-color: rgba(90, 148, 40, 0.18);
  box-shadow: inset 0 1px 0 rgba(220, 255, 190, 0.40);
}

.dashboard-page-shell.is-day-mode .showcase-nav-btn {
  background: rgba(100, 160, 50, 0.12);
  color: var(--text-primary);
}

.dashboard-page-shell.is-day-mode .showcase-nav-btn:hover {
  background: rgba(100, 160, 50, 0.20);
  box-shadow: 0 8px 20px rgba(30, 70, 14, 0.14);
}

.dashboard-page-shell.is-day-mode .showcase-dot {
  background: rgba(80, 140, 40, 0.28);
}

.dashboard-page-shell.is-day-mode .showcase-dot.active {
  background: linear-gradient(90deg, #2a6840, #7c5cb0);
  box-shadow: 0 0 10px rgba(42, 104, 64, 0.40);
}

.dashboard-page-shell.is-day-mode .showcase-link-btn {
  border-color: rgba(40, 120, 60, 0.30);
  background: linear-gradient(145deg, rgba(40, 120, 60, 0.14), rgba(30, 100, 48, 0.08));
  color: #1a5028;
}

.dashboard-page-shell.is-day-mode .showcase-link-btn:hover {
  background: linear-gradient(145deg, rgba(40, 120, 60, 0.22), rgba(30, 100, 48, 0.14));
  border-color: rgba(60, 160, 80, 0.46);
  box-shadow: 0 12px 26px rgba(30, 100, 48, 0.18);
}

.dashboard-page-shell.is-day-mode .showcase-image {
  border-color: rgba(80, 148, 40, 0.14);
  box-shadow: 0 16px 38px rgba(30, 70, 14, 0.18);
}

.dashboard-page-shell.is-day-mode .showcase-image-overlay {
  background:
    linear-gradient(180deg, rgba(120, 180, 70, 0.06), rgba(100, 160, 50, 0.24)),
    radial-gradient(circle at top right, rgba(220, 255, 190, 0.18), transparent 28%);
}

/* --- 22.4  Summary cards ----------------------------------- */
.dashboard-page-shell.is-day-mode .summary-card {
  background: linear-gradient(160deg, rgba(202, 232, 162, 0.92), rgba(190, 220, 148, 0.80));
  border-color: rgba(90, 148, 40, 0.16);
  box-shadow: 0 14px 38px rgba(30, 70, 14, 0.14);
}

.dashboard-page-shell.is-day-mode .summary-icon-wrap {
  background: rgba(100, 160, 50, 0.14);
  border-color: rgba(80, 148, 40, 0.20);
}

/* Muted accents readable on yellow-green */
.dashboard-page-shell.is-day-mode .accent-blue::before  { background: linear-gradient(90deg, transparent, #2a6848, #3a8860, transparent); opacity: 0.72; }
.dashboard-page-shell.is-day-mode .accent-blue::after   { background: radial-gradient(circle, rgba(42, 104, 72, 0.64), transparent 70%); }
.dashboard-page-shell.is-day-mode .accent-blue:hover    { border-color: rgba(42, 104, 72, 0.28); }
.dashboard-page-shell.is-day-mode .accent-blue .summary-icon-wrap { color: #1e5438; }

.dashboard-page-shell.is-day-mode .accent-violet::before { background: linear-gradient(90deg, transparent, #7c5cb0, #9058c0, transparent); opacity: 0.72; }
.dashboard-page-shell.is-day-mode .accent-violet::after  { background: radial-gradient(circle, rgba(124, 92, 176, 0.62), transparent 70%); }
.dashboard-page-shell.is-day-mode .accent-violet:hover   { border-color: rgba(124, 92, 176, 0.28); }
.dashboard-page-shell.is-day-mode .accent-violet .summary-icon-wrap { color: #6a48a0; }

.dashboard-page-shell.is-day-mode .accent-teal::before { background: linear-gradient(90deg, transparent, #1f8a6a, #2aaa82, transparent); opacity: 0.72; }
.dashboard-page-shell.is-day-mode .accent-teal::after  { background: radial-gradient(circle, rgba(31, 138, 106, 0.66), transparent 70%); }
.dashboard-page-shell.is-day-mode .accent-teal:hover   { border-color: rgba(31, 138, 106, 0.28); }
.dashboard-page-shell.is-day-mode .accent-teal .summary-icon-wrap { color: #145c46; }

.dashboard-page-shell.is-day-mode .accent-amber::before { background: linear-gradient(90deg, transparent, #6a9820, #88ba28, transparent); opacity: 0.72; }
.dashboard-page-shell.is-day-mode .accent-amber::after  { background: radial-gradient(circle, rgba(106, 152, 32, 0.64), transparent 70%); }
.dashboard-page-shell.is-day-mode .accent-amber:hover   { border-color: rgba(106, 152, 32, 0.28); }
.dashboard-page-shell.is-day-mode .accent-amber .summary-icon-wrap { color: #4e7010; }

.dashboard-page-shell.is-day-mode .accent-rose::before { background: linear-gradient(90deg, transparent, #b05060, #c06070, transparent); opacity: 0.72; }
.dashboard-page-shell.is-day-mode .accent-rose::after  { background: radial-gradient(circle, rgba(176, 80, 96, 0.62), transparent 70%); }
.dashboard-page-shell.is-day-mode .accent-rose:hover   { border-color: rgba(176, 80, 96, 0.28); }
.dashboard-page-shell.is-day-mode .accent-rose .summary-icon-wrap { color: #923848; }

/* --- 22.5  Surface cards ----------------------------------- */
.dashboard-page-shell.is-day-mode .surface-card {
  background: linear-gradient(160deg, rgba(196, 228, 156, 0.90), rgba(184, 216, 142, 0.76));
  border-color: rgba(90, 148, 40, 0.16);
  box-shadow: 0 14px 38px rgba(30, 70, 14, 0.14);
}

/* HUD kicker dot — forest green */
.dashboard-page-shell.is-day-mode .surface-kicker {
  color: #1e5c28;
}

.dashboard-page-shell.is-day-mode .surface-kicker::before {
  background: #2a8040;
  box-shadow: 0 0 6px rgba(42, 128, 64, 0.60);
}

@keyframes hud-pulse-day {
  0%, 100% { opacity: 1;    box-shadow: 0 0 6px rgba(42, 128, 64, 0.60); }
  50%       { opacity: 0.54; box-shadow: 0 0 3px rgba(42, 128, 64, 0.28); }
}

.dashboard-page-shell.is-day-mode .surface-kicker::before {
  animation: hud-pulse-day 2.2s ease-in-out infinite;
}

.dashboard-page-shell.is-day-mode .surface-link {
  background: rgba(100, 160, 50, 0.10);
  color: #1e5c28;
  border-color: rgba(60, 140, 40, 0.20);
}

.dashboard-page-shell.is-day-mode .surface-link:hover {
  border-color: rgba(60, 140, 40, 0.36);
  background: rgba(60, 140, 40, 0.12);
}

/* --- 22.7  Progress card ----------------------------------- */
.dashboard-page-shell.is-day-mode .progress-card {
  border-color: rgba(124, 92, 176, 0.18);
}

.dashboard-page-shell.is-day-mode .progress-ring-inner {
  background: linear-gradient(180deg, rgba(202, 232, 162, 0.98), rgba(188, 218, 146, 0.98));
  border-color: rgba(90, 148, 40, 0.16);
}

.dashboard-page-shell.is-day-mode .progress-ring {
  box-shadow: 0 20px 46px rgba(30, 70, 14, 0.22), inset 0 0 0 1px rgba(120, 200, 60, 0.12);
}

.dashboard-page-shell.is-day-mode .progress-ring::before {
  background: radial-gradient(circle,
    rgba(80, 180, 50, 0.18),
    rgba(124, 92, 176, 0.12) 52%,
    transparent 74%
  );
}

/* Orbiting arc — forest green/sage */
.dashboard-page-shell.is-day-mode .progress-ring::after {
  background: conic-gradient(
    from 0deg,
    transparent 0deg, transparent 30deg,
    rgba(50, 160, 60, 0.80) 46deg,
    rgba(30, 140, 100, 0.62) 80deg,
    transparent 118deg, transparent 360deg
  );
}

.dashboard-page-shell.is-day-mode .progress-detail-row:hover {
  background: rgba(100, 160, 50, 0.10);
  border-radius: 10px;
}

/* --- 22.8  Events / date badge ----------------------------- */
.dashboard-page-shell.is-day-mode .event-date-badge {
  background: linear-gradient(145deg, rgba(30, 140, 90, 0.22), rgba(30, 150, 100, 0.12));
  border-color: rgba(30, 150, 100, 0.28);
  box-shadow: 0 0 20px rgba(30, 140, 90, 0.14);
}

.dashboard-page-shell.is-day-mode .event-date-day  { color: #0a4020; }
.dashboard-page-shell.is-day-mode .event-date-rest { color: rgba(16, 70, 40, 0.82); }

/* --- 22.9  Lists (announcements) --------------------------- */
.dashboard-page-shell.is-day-mode .premium-row {
  border-color: rgba(90, 148, 40, 0.14);
  background: rgba(140, 196, 90, 0.08);
}

.dashboard-page-shell.is-day-mode .premium-row:hover {
  border-color: rgba(100, 160, 40, 0.28);
  background: rgba(100, 160, 40, 0.10);
}

.dashboard-page-shell.is-day-mode .announcement-icon {
  background: rgba(100, 160, 40, 0.14);
  color: #4a7010;
  border-color: rgba(80, 140, 30, 0.18);
}

.dashboard-page-shell.is-day-mode .premium-row:hover .announcement-icon {
  box-shadow: 0 8px 18px rgba(100, 160, 40, 0.22);
}

/* --- 22.10  Groups grid ------------------------------------ */
.dashboard-page-shell.is-day-mode .group-card-link:nth-child(1) .group-card-surface {
  background: linear-gradient(150deg, rgba(40, 130, 60, 0.22), rgba(194, 224, 158, 0.88) 50%);
  border-color: rgba(40, 130, 60, 0.22);
}

.dashboard-page-shell.is-day-mode .group-card-link:nth-child(2) .group-card-surface {
  background: linear-gradient(150deg, rgba(124, 92, 176, 0.22), rgba(194, 224, 158, 0.88) 50%);
  border-color: rgba(124, 92, 176, 0.20);
}

.dashboard-page-shell.is-day-mode .group-card-link:nth-child(3) .group-card-surface {
  background: linear-gradient(150deg, rgba(30, 140, 100, 0.22), rgba(194, 224, 158, 0.88) 50%);
  border-color: rgba(30, 140, 100, 0.20);
}

.dashboard-page-shell.is-day-mode .group-card-link:nth-child(4) .group-card-surface {
  background: linear-gradient(150deg, rgba(184, 90, 20, 0.18), rgba(194, 224, 158, 0.88) 50%);
  border-color: rgba(184, 90, 20, 0.18);
}

.dashboard-page-shell.is-day-mode .group-card-link:hover .group-card-surface {
  box-shadow: 0 24px 52px rgba(30, 70, 14, 0.22);
}

.dashboard-page-shell.is-day-mode .group-card-surface::after {
  background: linear-gradient(90deg, transparent, rgba(220, 255, 200, 0.82), transparent);
}

.dashboard-page-shell.is-day-mode .group-avatar {
  border-color: rgba(210, 240, 180, 0.92);
}

.dashboard-page-shell.is-day-mode .group-open-indicator {
  background: rgba(100, 160, 50, 0.14);
  color: #1e5828;
  border-color: rgba(80, 148, 40, 0.18);
}

/* --- 22.11  Resources grid --------------------------------- */
.dashboard-page-shell.is-day-mode .resource-card-link:nth-child(1) .resource-card-surface {
  background: linear-gradient(155deg, rgba(40, 130, 60, 0.16), rgba(188, 220, 152, 0.84) 50%);
  border-color: rgba(40, 130, 60, 0.18);
}

.dashboard-page-shell.is-day-mode .resource-card-link:nth-child(2) .resource-card-surface {
  background: linear-gradient(155deg, rgba(124, 92, 176, 0.16), rgba(188, 220, 152, 0.84) 50%);
  border-color: rgba(124, 92, 176, 0.16);
}

.dashboard-page-shell.is-day-mode .resource-card-link:nth-child(3) .resource-card-surface {
  background: linear-gradient(155deg, rgba(30, 140, 100, 0.16), rgba(188, 220, 152, 0.84) 50%);
  border-color: rgba(30, 140, 100, 0.16);
}

.dashboard-page-shell.is-day-mode .resource-card-link:nth-child(4) .resource-card-surface {
  background: linear-gradient(155deg, rgba(176, 80, 96, 0.14), rgba(188, 220, 152, 0.84) 50%);
  border-color: rgba(176, 80, 96, 0.16);
}

.dashboard-page-shell.is-day-mode .resource-card-link:nth-child(5) .resource-card-surface {
  background: linear-gradient(155deg, rgba(106, 152, 32, 0.16), rgba(188, 220, 152, 0.84) 50%);
  border-color: rgba(106, 152, 32, 0.16);
}

.dashboard-page-shell.is-day-mode .resource-card-link:nth-child(6) .resource-card-surface {
  background: linear-gradient(155deg, rgba(30, 150, 80, 0.16), rgba(188, 220, 152, 0.84) 50%);
  border-color: rgba(30, 150, 80, 0.16);
}

.dashboard-page-shell.is-day-mode .resource-card-link:hover .resource-card-surface {
  box-shadow: 0 20px 46px rgba(30, 70, 14, 0.22);
}

.dashboard-page-shell.is-day-mode .resource-icon {
  background: rgba(100, 160, 50, 0.14);
  color: #1e5828;
  border-color: rgba(80, 148, 40, 0.18);
}

.dashboard-page-shell.is-day-mode .resource-card-link:hover .resource-icon {
  box-shadow: 0 12px 24px rgba(40, 130, 60, 0.18);
}

/* --- 22.13  Alert / loading / empty state ------------------ */
.dashboard-page-shell.is-day-mode .dashboard-alert {
  background: rgba(100, 160, 40, 0.10);
  border-color: rgba(100, 160, 40, 0.28);
  color: #3a6010;
}

.dashboard-page-shell.is-day-mode .dashboard-loading {
  background: linear-gradient(160deg, rgba(200, 232, 160, 0.94), rgba(184, 218, 144, 0.90));
  border-color: rgba(80, 148, 40, 0.22);
  color: var(--text-primary);
  box-shadow: 0 20px 50px rgba(30, 70, 14, 0.18);
}

.dashboard-page-shell.is-day-mode .loading-ring {
  border-top-color:    #1f8a6a;
  border-right-color:  #7c5cb0;
  border-bottom-color: #6a9820;
}

.dashboard-page-shell.is-day-mode .empty-state {
  border-color: rgba(80, 148, 40, 0.22);
  background: rgba(120, 180, 70, 0.06);
  color: var(--text-secondary);
}

.dashboard-page-shell.is-day-mode .empty-state i {
  color: var(--text-muted);
}

/* Hero copy section overlay — yellow-green */
.dashboard-page-shell.is-day-mode .dashboard-hero-copy {
  background: linear-gradient(155deg, rgba(210, 238, 172, 0.90), rgba(196, 226, 156, 0.78));
  border-color: rgba(90, 148, 40, 0.18);
  box-shadow: inset 0 1px 0 rgba(220, 255, 190, 0.60);
}

.dashboard-page-shell.is-day-mode .dashboard-subtext {
  color: #2a5018;
}

.dashboard-page-shell.is-night-mode .showcase-card::after {
  background: linear-gradient(160deg, rgba(6, 18, 11, 0.96), rgba(7, 16, 10, 0.90));
}

.dashboard-page-shell.is-night-mode .theme-rail-trigger:hover,
.dashboard-page-shell.is-night-mode .showcase-nav-btn:hover,
.dashboard-page-shell.is-night-mode .showcase-link-btn:hover,
.dashboard-page-shell.is-night-mode .primary-chip:hover {
  box-shadow: 0 12px 28px rgba(60, 200, 120, 0.16);
}

.dashboard-page-shell.is-night-mode .status-pill:nth-child(1) { color: #8fffcc; }
.dashboard-page-shell.is-night-mode .status-pill:nth-child(2) { color: #41d9c6; }
.dashboard-page-shell.is-night-mode .status-pill:nth-child(3) { color: #ff8cab; }

@media (max-width: 1180px) {
  .dashboard-hero-main { grid-template-columns: 1fr; padding-top: 3rem; }
  .dashboard-hero-copy { padding: 1.2rem 1.15rem 1.22rem; }
  .showcase-card { min-height: 0; }
  .two-col-layout { grid-template-columns: 1fr; }
}

@media (max-width: 880px) {
  .dashboard-page-shell { padding: 1rem 0.8rem 2rem; }
  .summary-grid, .groups-grid, .resource-grid { grid-template-columns: 1fr; }
  .event-detail-card { flex-direction: column; }
  .event-date-badge { width: 100%; min-height: 72px; flex-direction: row; justify-content: flex-start; align-items: center; gap: 0.72rem; }
  .dashboard-theme-rail { position: static; flex-direction: column; align-items: stretch; margin-bottom: 1rem; }
  .theme-rail-trigger { width: 100%; justify-content: center; }
  .dashboard-hero-main { padding-top: 0; }
  .dashboard-hero-copy,
  .dashboard-hero-aside { display: block; }
  .showcase-footer { flex-direction: column; align-items: stretch; }
  .showcase-image { aspect-ratio: 16 / 9; }
}

@media (max-width: 560px) {
  .dashboard-hero-card, .surface-card, .summary-card { border-radius: 20px; }
  .hero-title { font-size: 1.75rem; }
  .dashboard-subtext, .dashboard-hero-message { font-size: 0.90rem; }
  .summary-card-value { font-size: 1.9rem; }
  .showcase-title { font-size: 1rem; }
}

/* ──────────────────────────────────────────────────────────────
   § 22  TOUCH & REDUCED-MOTION
   ────────────────────────────────────────────────────────────── */
@media (max-width: 1120px) {
  .group-card-link:hover .group-card-surface,
  .resource-card-link:hover .resource-card-surface,
  .summary-card:hover,
  .hero-meta-chip:hover,
  .event-detail-card:hover .event-date-badge,
  .event-detail-card:hover .event-content,
  .progress-card:hover .progress-ring { transform: none; }
}

@media (prefers-reduced-motion: reduce) {
  .orb-one, .orb-two,
  .progress-ring::before, .progress-ring::after,
  .surface-kicker::before { animation: none !important; }

  .group-card-link:hover .group-card-surface,
  .resource-card-link:hover .resource-card-surface,
  .summary-card:hover,
  .hero-meta-chip:hover,
  .event-detail-card:hover .event-date-badge,
  .event-detail-card:hover .event-content,
  .progress-card:hover .progress-ring,
  .showcase-card:hover { transform: none !important; }
}


/* ──────────────────────────────────────────────────────────────
   § 23  HERO ENRICHMENT & ADAPTIVE OVERRIDES
   ────────────────────────────────────────────────────────────── */
.dashboard-page-shell {
  color: var(--text-primary);
}

.dashboard-page-shell::before {
  background: var(--dashboard-shell-backdrop, linear-gradient(135deg, #060c1a, #0a1224));
}

.dashboard-hero-card {
  background: linear-gradient(145deg, var(--hero-overlay-a), var(--hero-overlay-b));
  border-color: var(--border-strong);
  box-shadow: var(--shadow-lg), inset 0 1px 0 rgba(255, 255, 255, 0.07);
}

.surface-card,
.summary-card,
.showcase-card,
.dashboard-loading,
.dashboard-alert {
  box-shadow: var(--shadow-md);
}

.hero-title,
.surface-card-title,
.group-name,
.resource-title,
.showcase-title,
.summary-card-value,
.event-title,
.progress-value,
.hero-meta-chip-value {
  color: var(--text-primary);
}

.dashboard-subtext,
.dashboard-hero-message,
.showcase-summary,
.summary-card-subtext,
.progress-detail-row span,
.progress-label,
.progress-caption,
.resource-meta,
.group-meta,
.list-row-meta,
.list-row-description,
.surface-link,
.theme-rail-trigger,
.showcase-mini-label,
.event-meta-row,
.empty-state,
.dashboard-alert,
.dashboard-loading,
.hero-meta-chip-label,
.summary-label,
.status-pill,
.hero-eyebrow {
  color: var(--text-secondary);
}

.hero-eyebrow,
.hero-meta-chip,
.status-pill,
.summary-card,
.surface-card,
.showcase-card,
.group-card-surface,
.resource-card-surface,
.list-row,
.theme-rail-trigger,
.dashboard-loading {
  border-color: var(--border-default);
}

.surface-card,
.summary-card,
.showcase-card,
.group-card-surface,
.resource-card-surface,
.list-row,
.hero-meta-chip,
.status-pill,
.theme-rail-trigger,
.hero-eyebrow {
  background: linear-gradient(165deg, color-mix(in srgb, var(--surface-elevated) 88%, transparent), color-mix(in srgb, var(--surface-base) 94%, transparent));
  backdrop-filter: blur(24px);
  -webkit-backdrop-filter: blur(24px);
}

.hero-meta-chip:hover,
.status-pill:hover,
.summary-card:hover,
.surface-card:hover,
.group-card-link:hover .group-card-surface,
.resource-card-link:hover .resource-card-surface,
.list-row:hover,
.showcase-card:hover {
  transform: translateY(-4px);
  border-color: var(--border-strong);
}

.progress-ring-shell {
  flex: 0 0 220px;
  min-height: 220px;
  display: grid;
  place-items: center;
  position: relative;
  isolation: isolate;
}

.progress-ring-aura,
.progress-ring-track,
.progress-ring-orbit,
.progress-ring-marker,
.progress-ring-spark {
  position: absolute;
  border-radius: 999px;
  pointer-events: none;
}

.progress-ring-aura {
  width: 198px;
  height: 198px;
  background: radial-gradient(circle, color-mix(in srgb, var(--accent-blue) 22%, transparent), transparent 66%);
  filter: blur(22px);
  opacity: 0.95;
}

.progress-ring-track {
  width: 192px;
  height: 192px;
  border: 1px dashed color-mix(in srgb, var(--text-link) 28%, transparent);
  opacity: 0.42;
}

.progress-ring-orbit {
  animation: orbitFloat 10s linear infinite;
}

.progress-ring-orbit--outer {
  width: 210px;
  height: 210px;
  border: 1px solid color-mix(in srgb, var(--accent-teal) 18%, transparent);
}

.progress-ring-orbit--inner {
  width: 160px;
  height: 160px;
  border: 1px solid color-mix(in srgb, var(--accent-violet) 16%, transparent);
  animation-direction: reverse;
  animation-duration: 12s;
}

.progress-ring-marker {
  left: calc(50% - 7px);
  top: calc(50% - 7px);
  width: 14px;
  height: 14px;
  background: linear-gradient(135deg, var(--accent-amber), var(--accent-violet));
  box-shadow: 0 0 0 5px color-mix(in srgb, var(--surface-elevated) 74%, transparent), 0 0 18px color-mix(in srgb, var(--accent-blue) 40%, transparent);
}

.progress-ring-spark {
  width: 8px;
  height: 8px;
  background: var(--text-link);
  opacity: 0.64;
  filter: blur(1px);
  animation: sparkleOrbit 7s ease-in-out infinite;
}

.progress-ring-spark--one { top: 32px; left: 42px; }
.progress-ring-spark--two { right: 34px; bottom: 42px; animation-delay: -2.6s; }

.progress-ring {
  width: 172px;
  height: 172px;
  border-radius: 50%;
  padding: 13px;
  box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--accent-blue) 18%, transparent), 0 18px 42px rgba(0, 4, 20, 0.24);
}

.progress-ring-inner {
  width: 100%;
  height: 100%;
  border-radius: 50%;
  background: linear-gradient(160deg, color-mix(in srgb, var(--surface-elevated) 98%, transparent), color-mix(in srgb, var(--surface-base) 98%, transparent));
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
}

.progress-value {
  font-size: 2rem;
  font-weight: 800;
}

.progress-label {
  margin-top: 0.14rem;
  font-size: 0.76rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  font-weight: 700;
}

.progress-caption {
  margin-top: 0.35rem;
  font-size: 0.82rem;
  color: var(--text-link);
  font-weight: 700;
}

@keyframes orbitFloat {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

@keyframes sparkleOrbit {
  0%, 100% { transform: translate3d(0, 0, 0) scale(1); opacity: 0.44; }
  50% { transform: translate3d(6px, -8px, 0) scale(1.5); opacity: 0.92; }
}

.summary-card:nth-child(1) { border-radius: 28px 18px 24px 18px; }
.summary-card:nth-child(2) { border-radius: 18px 30px 18px 24px; }
.summary-card:nth-child(3) { border-radius: 24px 18px 30px 18px; }
.summary-card:nth-child(4) { border-radius: 18px 24px 18px 30px; }
.progress-card { border-radius: 22px 34px 22px 34px; }
.event-detail-card { border-radius: 26px 22px 30px 22px; }
.list-row { border-radius: 18px 14px 18px 14px; }
.group-card-surface { border-radius: 26px 20px 32px 18px; }
.resource-card-surface { border-radius: 20px 28px 18px 28px; }

.hero-meta-chip--neutral { box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--text-primary) 8%, transparent); }
.hero-meta-chip--cyan { box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--accent-teal) 18%, transparent); }
.hero-meta-chip--violet { box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--accent-violet) 18%, transparent); }

@media (max-width: 1180px) {
  .progress-ring-shell {
    flex: 0 0 auto;
    margin-inline: auto;
  }
}

@media (max-width: 680px) {
  .hero-meta-row,
  .hero-highlight-wrap {
    gap: 0.55rem;
  }

  .progress-ring-shell {
    min-height: 192px;
  }
}



/* ================================================================
   Typography and text-color refinement override
   ================================================================ */
.dashboard-page-shell {
  --font-display: "Aptos Display", "Segoe UI Variable Display", "Inter", "SF Pro Display", "Helvetica Neue", Arial, sans-serif;
  --font-body: "Aptos", "Segoe UI Variable Text", "Inter", "SF Pro Text", system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
  --font-label: "JetBrains Mono", "SFMono-Regular", "Cascadia Mono", Consolas, monospace;
  --font-number: "Bahnschrift", "Inter", "Segoe UI", sans-serif;
  font-family: var(--font-body);
}

.dashboard-page-shell.is-night-mode {
  --text-primary: #f2fff7;
  --text-secondary: #b8d8c8;
  --text-muted: #84a997;
  --text-link: #8ee7c0;
  --text-hero-accent: #b6fff1;
  --text-card-accent: #f1ce82;
}

.dashboard-page-shell.is-day-mode {
  --text-primary: #18311e;
  --text-secondary: #496652;
  --text-muted: #708b78;
  --text-link: #305f48;
  --text-hero-accent: #214533;
  --text-card-accent: #7e6233;
}

.dashboard-page-shell,
.dashboard-page-shell * {
  font-variant-ligatures: common-ligatures;
}

.hero-title,
.surface-card-title,
.group-name,
.resource-title,
.showcase-title,
.summary-card-value,
.event-title,
.progress-value,
.hero-meta-chip-value,
.list-row-title {
  font-family: var(--font-display);
  letter-spacing: -0.03em;
}

.hero-title {
  color: var(--text-primary);
  font-size: clamp(2rem, 3.4vw, 2.95rem);
  font-weight: 820;
}

.surface-card-title,
.group-name,
.resource-title,
.showcase-title,
.event-title,
.list-row-title {
  color: var(--text-primary);
  font-weight: 780;
}

.summary-card-value,
.progress-value,
.event-date-day {
  font-family: var(--font-number);
  color: var(--text-primary);
  letter-spacing: -0.05em;
}

.surface-kicker,
.hero-eyebrow,
.showcase-kicker,
.summary-label,
.hero-meta-chip-label,
.progress-label,
.progress-caption,
.status-pill,
.showcase-mini-label,
.list-row-meta,
.event-date-rest,
.theme-rail-trigger {
  font-family: var(--font-label);
  letter-spacing: 0.1em;
  text-transform: uppercase;
}

.dashboard-subtext {
  color: var(--text-card-accent);
  font-size: 0.97rem;
  font-weight: 620;
  line-height: 1.65;
}

.dashboard-hero-message,
.showcase-summary,
.summary-card-subtext,
.list-row-description,
.resource-meta,
.group-meta,
.event-meta-row,
.empty-state,
.dashboard-alert,
.dashboard-loading {
  color: var(--text-secondary);
  font-family: var(--font-body);
  line-height: 1.7;
}

.hero-eyebrow {
  color: var(--text-hero-accent);
}

.surface-kicker,
.showcase-kicker {
  color: var(--accent-blue);
}

.hero-meta-chip,
.status-pill,
.summary-card,
.surface-card,
.showcase-card,
.group-card-surface,
.resource-card-surface,
.list-row,
.theme-rail-trigger,
.event-detail-card,
.dashboard-alert,
.dashboard-loading {
  border-color: var(--border-default);
  background: linear-gradient(165deg, color-mix(in srgb, var(--surface-elevated) 92%, transparent), color-mix(in srgb, var(--surface-base) 96%, transparent));
}

.dashboard-hero-card {
  background: linear-gradient(145deg, var(--hero-overlay-a), var(--hero-overlay-b));
  border-color: var(--border-strong);
}

.dashboard-page-shell.is-day-mode .dashboard-hero-copy {
  background: linear-gradient(155deg, rgba(243, 250, 236, 0.94), rgba(232, 243, 223, 0.90));
}

.dashboard-page-shell.is-night-mode .dashboard-hero-copy {
  background: linear-gradient(155deg, rgba(13, 30, 20, 0.94), rgba(9, 23, 16, 0.88));
}

.theme-rail-trigger,
.showcase-nav-btn,
.showcase-link-btn,
.primary-chip,
.surface-link {
  color: var(--text-link);
  font-family: var(--font-display);
  font-weight: 720;
}

.showcase-link-btn,
.primary-chip,
.theme-rail-trigger {
  border-color: color-mix(in srgb, var(--accent-blue) 18%, var(--border-default));
}

.list-row-meta,
.progress-label,
.progress-caption,
.event-date-rest,
.summary-label,
.showcase-mini-label {
  color: var(--text-muted);
}

.progress-detail-row strong,
.hero-meta-chip-value {
  color: var(--text-primary);
}

.progress-detail-row span,
.list-row-description,
.resource-meta,
.group-meta,
.event-meta-row {
  color: var(--text-secondary);
}

.showcase-dot.active {
  background: var(--accent-teal);
}

.dashboard-page-shell.is-night-mode .status-pill:nth-child(1) { color: #9df6cf; }
.dashboard-page-shell.is-night-mode .status-pill:nth-child(2) { color: #7db8ff; }
.dashboard-page-shell.is-night-mode .status-pill:nth-child(3) { color: #f3c977; }
.dashboard-page-shell.is-day-mode .status-pill:nth-child(1) { color: #3c6e54; }
.dashboard-page-shell.is-day-mode .status-pill:nth-child(2) { color: #587fbc; }
.dashboard-page-shell.is-day-mode .status-pill:nth-child(3) { color: #9f7240; }

.dashboard-page-shell.is-day-mode .event-date-badge {
  background: rgba(93, 131, 188, 0.08);
}

.dashboard-page-shell.is-night-mode .event-date-badge {
  background: rgba(125, 184, 255, 0.10);
}

.dashboard-page-shell.is-day-mode .summary-card,
.dashboard-page-shell.is-day-mode .surface-card,
.dashboard-page-shell.is-day-mode .showcase-card,
.dashboard-page-shell.is-day-mode .group-card-surface,
.dashboard-page-shell.is-day-mode .resource-card-surface,
.dashboard-page-shell.is-day-mode .list-row {
  box-shadow: 0 16px 36px rgba(18, 31, 21, 0.08);
}

.dashboard-page-shell.is-night-mode .summary-card,
.dashboard-page-shell.is-night-mode .surface-card,
.dashboard-page-shell.is-night-mode .showcase-card,
.dashboard-page-shell.is-night-mode .group-card-surface,
.dashboard-page-shell.is-night-mode .resource-card-surface,
.dashboard-page-shell.is-night-mode .list-row {
  box-shadow: 0 18px 42px rgba(0, 8, 3, 0.26);
}

/* Clean white/grey dashboard theme, aligned with Events and Resources pages. */
.dashboard-page-shell,
.dashboard-page-shell.is-day-mode,
.dashboard-page-shell.is-night-mode {
  --text-primary: var(--charcoal) !important;
  --text-secondary: #6c757d !important;
  --text-muted: #8a949e !important;
  --text-link: #4f5f6f !important;
  --text-hero-accent: #4f5f6f !important;
  --text-card-accent: #6c757d !important;
  --surface-base: var(--white) !important;
  --surface-elevated: var(--white) !important;
  --surface-soft: #f8f9fa !important;
  --border-default: var(--border-light) !important;
  --border-strong: #cfd6dc !important;
  --accent-blue: #5f6f7f !important;
  --accent-teal: #6f7c83 !important;
  --accent-violet: #70747c !important;
  --accent-amber: #7a7568 !important;
  --accent-rose: #7a6970 !important;
  --shadow-lg: 0 4px 12px var(--shadow) !important;
  --shadow-md: 0 2px 4px var(--shadow) !important;
  --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.08) !important;
  --hero-overlay-a: var(--white) !important;
  --hero-overlay-b: var(--white) !important;
  --dashboard-shell-backdrop: var(--bg-light) !important;
  --page-glow-one: transparent !important;
  --page-glow-two: transparent !important;
  --page-glow-three: transparent !important;
  color: var(--charcoal) !important;
  background: var(--bg-light) !important;
  padding: 2rem;
}

.dashboard-page-shell::before {
  background: var(--bg-light) !important;
}

.dashboard-fx-canvas,
.dashboard-backdrop-orb,
.dashboard-backdrop-grid,
.progress-ring-aura,
.progress-ring-orbit,
.progress-ring-marker,
.progress-ring-spark {
  display: none !important;
}

.dashboard-page-inner {
  position: relative;
  z-index: 1;
}

.dashboard-hero-card,
.dashboard-hero-copy,
.surface-card,
.summary-card,
.showcase-card,
.group-card-surface,
.resource-card-surface,
.list-row,
.hero-meta-chip,
.status-pill,
.event-detail-card,
.theme-rail-trigger,
.dashboard-alert,
.dashboard-loading {
  background: var(--white) !important;
  border: 1px solid var(--border-light) !important;
  border-radius: 8px !important;
  box-shadow: 0 2px 4px var(--shadow) !important;
  backdrop-filter: none !important;
  -webkit-backdrop-filter: none !important;
}

.dashboard-hero-card,
.surface-card,
.summary-card,
.showcase-card,
.group-card-surface,
.resource-card-surface {
  overflow: hidden;
}

.dashboard-hero-card:hover,
.surface-card:hover,
.summary-card:hover,
.showcase-card:hover,
.group-card-link:hover .group-card-surface,
.resource-card-link:hover .resource-card-surface,
.list-row:hover,
.hero-meta-chip:hover,
.status-pill:hover {
  transform: translateY(-2px) !important;
  border-color: var(--border-light) !important;
  box-shadow: 0 4px 12px var(--shadow) !important;
}

.dashboard-hero-card::before,
.dashboard-hero-card::after,
.dashboard-hero-copy::before,
.showcase-card::before,
.showcase-card::after,
.summary-card::before,
.summary-card::after,
.group-card-surface::after,
.resource-card-surface::before,
.hero-meta-chip::before,
.hero-meta-chip::after,
.status-pill::before,
.status-pill::after,
.progress-card::after {
  display: none !important;
  content: none !important;
  background: none !important;
}

.dashboard-hero-card {
  padding: 1.5rem;
}

.dashboard-hero-shell,
.dashboard-hero-main {
  background: transparent !important;
  box-shadow: none !important;
}

.dashboard-hero-main {
  padding-top: 3rem;
}

.dashboard-theme-rail {
  gap: 0.5rem;
}

.theme-rail-trigger,
.showcase-nav-btn,
.showcase-link-btn,
.primary-chip,
.surface-link {
  color: #4f5f6f !important;
  background: #f8f9fa !important;
  border: 1px solid var(--border-light) !important;
  box-shadow: none !important;
}

.theme-rail-trigger:hover,
.showcase-nav-btn:hover,
.showcase-link-btn:hover,
.primary-chip:hover,
.surface-link:hover {
  color: var(--charcoal) !important;
  background: #eef1f3 !important;
  border-color: #cfd6dc !important;
}

.hero-title,
.surface-card-title,
.group-name,
.resource-title,
.showcase-title,
.summary-card-value,
.event-title,
.progress-value,
.hero-meta-chip-value,
.list-row-title {
  color: var(--charcoal) !important;
  letter-spacing: 0 !important;
}

.dashboard-subtext,
.dashboard-hero-message,
.showcase-summary,
.summary-card-subtext,
.list-row-description,
.resource-meta,
.group-meta,
.event-meta-row,
.empty-state,
.hero-meta-chip-label,
.summary-label,
.status-pill,
.showcase-mini-label,
.list-row-meta,
.progress-detail-row span,
.progress-label,
.progress-caption,
.event-date-rest,
.dashboard-alert,
.dashboard-loading {
  color: #6c757d !important;
}

.surface-kicker,
.hero-eyebrow,
.showcase-kicker {
  color: #6c757d !important;
}

.summary-icon-wrap,
.list-row-icon,
.resource-icon,
.event-date-badge,
.progress-ring-inner {
  background: #f8f9fa !important;
  border: 1px solid var(--border-light) !important;
  color: #4f5f6f !important;
  box-shadow: none !important;
}

.primary-avatar,
.secondary-avatar,
.tertiary-avatar {
  background: #8a949e !important;
  color: var(--white) !important;
  border-color: var(--white) !important;
}

.progress-ring {
  background: #f8f9fa !important;
  box-shadow: inset 0 0 0 1px var(--border-light), 0 2px 4px var(--shadow) !important;
}

.progress-ring-track {
  border-color: var(--border-light) !important;
}

.progress-bar-shell {
  background: #eef1f3 !important;
}

.progress-bar-fill {
  background: #6c757d !important;
}

.showcase-image {
  border-radius: 8px;
  border-color: var(--border-light) !important;
  box-shadow: none !important;
}

.showcase-image::before,
.showcase-image-overlay {
  display: none !important;
}

.showcase-dot {
  background: #d7dde2 !important;
}

.showcase-dot.active {
  background: #6c757d !important;
  box-shadow: none !important;
}

.dashboard-page-shell.is-day-mode .resource-card-link:nth-child(n) .resource-card-surface,
.dashboard-page-shell.is-day-mode .group-card-link:nth-child(n) .group-card-surface,
.dashboard-page-shell.is-night-mode .resource-card-link:nth-child(n) .resource-card-surface,
.dashboard-page-shell.is-night-mode .group-card-link:nth-child(n) .group-card-surface {
  background: var(--white) !important;
  border-color: var(--border-light) !important;
}

.dashboard-page-shell.is-day-mode .status-pill:nth-child(n),
.dashboard-page-shell.is-night-mode .status-pill:nth-child(n) {
  color: #6c757d !important;
}

@media (max-width: 880px) {
  .dashboard-page-shell {
    padding: 1.25rem;
  }

  .dashboard-hero-main {
    padding-top: 0;
  }
}
</style>
