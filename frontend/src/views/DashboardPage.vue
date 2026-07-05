<template>
  <!-- Dashboard shell -->
  <div
    ref="dashboardShellRef"
    class="content-area dashboard-page-shell"
    :style="dashboardThemeStyle"
  >
    <div class="dashboard-page-inner">
      <div class="dashboard-backdrop-grid" aria-hidden="true"></div>

      <div v-if="isLoading" class="dashboard-loading-skeleton" role="status" aria-live="polite">
        <span class="sr-only">Loading dashboard...</span>

        <section class="dashboard-hero-shell">
          <div class="dashboard-hero-card dashboard-skeleton-hero">
            <div class="dashboard-skeleton-hero-copy">
              <div class="dashboard-skeleton-block dashboard-skeleton-eyebrow"></div>
              <div class="dashboard-skeleton-block dashboard-skeleton-title"></div>
              <div class="dashboard-skeleton-chip-row">
                <div
                  v-for="item in 3"
                  :key="`hero-chip-${item}`"
                  class="dashboard-skeleton-block dashboard-skeleton-chip"
                ></div>
              </div>
              <div class="dashboard-skeleton-block dashboard-skeleton-line"></div>
              <div
                class="dashboard-skeleton-block dashboard-skeleton-line dashboard-skeleton-line--short"
              ></div>
            </div>

            <div class="dashboard-skeleton-calendar">
              <div class="dashboard-skeleton-calendar-head">
                <div class="dashboard-skeleton-block dashboard-skeleton-calendar-title"></div>
                <div class="dashboard-skeleton-block dashboard-skeleton-calendar-nav"></div>
              </div>
              <div class="dashboard-skeleton-calendar-grid">
                <div
                  v-for="item in 35"
                  :key="`calendar-day-${item}`"
                  class="dashboard-skeleton-block dashboard-skeleton-calendar-day"
                ></div>
              </div>
            </div>
          </div>
        </section>

        <section class="dashboard-section">
          <div class="dashboard-section-grid summary-grid">
            <article
              v-for="item in 4"
              :key="`summary-${item}`"
              class="summary-card dashboard-skeleton-card"
            >
              <div class="dashboard-skeleton-card-top">
                <div class="dashboard-skeleton-block dashboard-skeleton-icon"></div>
                <div class="dashboard-skeleton-block dashboard-skeleton-label"></div>
              </div>
              <div class="dashboard-skeleton-block dashboard-skeleton-metric"></div>
              <div
                class="dashboard-skeleton-block dashboard-skeleton-line dashboard-skeleton-line--tiny"
              ></div>
            </article>
          </div>
        </section>

        <section class="dashboard-section">
          <article class="surface-card dashboard-skeleton-progress">
            <div class="dashboard-skeleton-section-head">
              <div>
                <div class="dashboard-skeleton-block dashboard-skeleton-kicker"></div>
                <div class="dashboard-skeleton-block dashboard-skeleton-heading"></div>
              </div>
              <div class="dashboard-skeleton-block dashboard-skeleton-select"></div>
            </div>
            <div class="dashboard-skeleton-progress-body">
              <div class="dashboard-skeleton-block dashboard-skeleton-ring"></div>
              <div class="dashboard-skeleton-progress-rows">
                <div
                  v-for="item in 4"
                  :key="`progress-row-${item}`"
                  class="dashboard-skeleton-progress-row"
                >
                  <div class="dashboard-skeleton-block dashboard-skeleton-row-label"></div>
                  <div class="dashboard-skeleton-block dashboard-skeleton-row-value"></div>
                </div>
              </div>
            </div>
          </article>
        </section>

        <section class="dashboard-section">
          <div class="dashboard-section-grid two-col-layout">
            <article
              v-for="panel in 2"
              :key="`panel-${panel}`"
              class="surface-card dashboard-skeleton-panel"
            >
              <div class="dashboard-skeleton-section-head">
                <div>
                  <div class="dashboard-skeleton-block dashboard-skeleton-kicker"></div>
                  <div class="dashboard-skeleton-block dashboard-skeleton-heading"></div>
                </div>
                <div class="dashboard-skeleton-block dashboard-skeleton-link"></div>
              </div>
              <div class="dashboard-skeleton-list">
                <div
                  v-for="row in 3"
                  :key="`panel-${panel}-row-${row}`"
                  class="dashboard-skeleton-list-row"
                >
                  <div class="dashboard-skeleton-block dashboard-skeleton-icon"></div>
                  <div class="dashboard-skeleton-list-copy">
                    <div class="dashboard-skeleton-block dashboard-skeleton-line"></div>
                    <div
                      class="dashboard-skeleton-block dashboard-skeleton-line dashboard-skeleton-line--short"
                    ></div>
                  </div>
                </div>
              </div>
            </article>
          </div>
        </section>
      </div>

      <template v-else>
        <section class="dashboard-welcome-header">
          <h1 class="hero-title">Welcome back, {{ displayName }}</h1>
        </section>

        <section class="dashboard-hero-shell">
          <div class="dashboard-hero-card interactive-surface">
            <div class="dashboard-hero-main">
              <div class="dashboard-hero-copy">
                <p class="dashboard-hero-message">
                  Welcome to {{ BRAND_CONNECT }} — your central hub for the {{ BRAND_NAME }} Challenge.
                  Connect with your team, collaborate and share ideas, access program-wide
                  resources, register for events, and stay up to date with the latest announcements
                  and opportunities across the program.
                </p>

                <div class="hero-highlight-wrap">
                  <span v-for="item in headerHighlights" :key="item.key" class="status-pill">
                    {{ item.label }}
                  </span>
                </div>
              </div>
              <MiniCalendar class="dashboard-hero-calendar" placement="hero" />
            </div>

          <div class="dashboard-hero-groups">
            <div class="surface-card-header">
              <div>
                <p class="surface-kicker">Groups</p>
                <h3 class="surface-card-title">{{ groupsSectionTitle }}</h3>
              </div>
              <button
                v-if="shouldBlockGroupsNavigation"
                type="button"
                class="surface-link surface-link-button"
                @click="showNoMembershipPopup"
              >
                View all
              </button>
              <RouterLink v-else to="/groups" class="surface-link">View all</RouterLink>
            </div>

            <div v-if="groupsPreview.length" class="groups-grid dashboard-hero-groups-grid">
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

                  <div class="group-meta">
                    {{ getGroupMemberCount(group) }} members · Lead: {{ getGroupLead(group) }}
                  </div>
                </div>
              </RouterLink>
            </div>

            <div v-else class="empty-state">
              <i class="fas fa-users-slash"></i>
              <p>No group is available yet.</p>
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
                    <span
                      ><i class="fas fa-location-dot"></i
                      >{{ nextEvent.location || 'Location TBC' }}</span
                    >
                  </div>

                  <div class="event-actions">
                    <RouterLink to="/events" class="primary-chip">
                      {{ isAdmin ? 'Manage event' : isMentor ? 'Open session' : 'View event' }}
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

                    <div class="list-row-meta">
                      {{ formatAnnouncementDateAU(getAnnouncementMeta(announcement)) }}
                    </div>

                    <div
                      class="list-row-description dashboard-announcement-body"
                      v-html="getAnnouncementPreviewHtml(announcement)"
                    ></div>
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
          <div class="dashboard-section-grid library-layout">
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
                        {{ getResourceCategory(resource) }} · Updated
                        {{ getResourceMeta(resource) }}
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
      </template>
    </div>

    <div
      v-if="showNoMembershipNotice"
      class="dashboard-modal-backdrop"
      role="presentation"
      @click.self="closeNoMembershipPopup"
    >
      <div class="dashboard-modal" role="dialog" aria-modal="true" aria-labelledby="no-membership-title">
        <button
          type="button"
          class="dashboard-modal-close"
          aria-label="Close"
          @click="closeNoMembershipPopup"
        >
          <i class="fas fa-times"></i>
        </button>

        <div class="dashboard-modal-icon">
          <i class="fas fa-users-slash"></i>
        </div>
        <h3 id="no-membership-title">No group membership</h3>
        <p>Please contact the administrator via {{ SUPPORT_EMAIL }}</p>
        <button type="button" class="btn btn-primary" @click="closeNoMembershipPopup">
          Got it
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
// Dashboard page
// Core imports
import { ref, computed, onMounted } from 'vue'

import { RouterLink } from 'vue-router'

import { storeToRefs } from 'pinia'

import { useAuthStore } from '@/stores/auth'
import { BRAND_CONNECT, BRAND_NAME, SUPPORT_EMAIL } from '@/constants/brand'

import {
  formatAnnouncementDateAU,
  formatEventDate,
  formatEventTimeRange,
} from '@/utils/date'
import { getResourceIcon } from '@/utils/resource'
import { getInitials } from '@/utils/string'
import { buildSessionHeaders } from '@/utils/csrf'
import { apiErrorFromResponse } from '@/utils/apiError'
import { getAccentClass } from '@/utils/ui'
import MiniCalendar from '@/components/MiniCalendar.vue'

const auth = useAuthStore()
const { isAdmin, isMentor, isSupervisor, displayName, user, timeZone } = storeToRefs(auth)
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
const EVENTS_API_BASE = `${API_BASE_URL}/events/v1`
const DASHBOARD_ENDPOINTS = {
  groupsPreview: (mine = false) =>
    `${API_BASE_URL}/dashboard/v1/groups-preview/?page_size=20${mine ? '&mine=true' : ''}`,
  groups: `${API_BASE_URL}/groups/groups/?page_size=20`,
  groupsMine: `${API_BASE_URL}/groups/groups/?page_size=20&mine=true`,
  tracks: `${API_BASE_URL}/groups/tracks/?page_size=100`,
  resources: `${API_BASE_URL}/resources/resource-files/?page_size=20`,
  announcements: `${API_BASE_URL}/announcements/v1/?page_size=10`,
  nextEvent: `${API_BASE_URL}/dashboard/v1/next-event/`,
  personalizedEvents: `${EVENTS_API_BASE}/?rsvp_status=accepted,tentative,pending&page_size=1&ordering=start_datetime`,
  eventsCount: `${EVENTS_API_BASE}/?when=upcoming&page_size=1`,
  events: `${EVENTS_API_BASE}/?page_size=10`,
  progress: `${API_BASE_URL}/dashboard/v1/progress/`,
  adminSummary: `${API_BASE_URL}/api/v1/admin/summary/`,
}

const isLoading = ref(true)
const loadError = ref('')

const groups = ref([])
const resources = ref([])
const announcements = ref([])
const events = ref([])
const upcomingEventsCount = ref(0)
const showNoMembershipNotice = ref(false)

const dashboardSummary = ref({
  activeGroups: groups.value.length,
  upcomingEvents: events.value.length,
  resources: resources.value.length,
  announcements: announcements.value.length,
})

const isMentoringRole = computed(() => isMentor.value || isSupervisor.value)

const adminWorkflow = ref({
  pendingMatches: 0,
  pendingReassignments: 0,
  pendingApprovals: 0,
  draftBulkMessages: 0,
})

const adminOperationsSummary = ref(null)

const progressSnapshot = ref({
  completionRate: 0,
  completedTasks: 0,
  totalTasks: 0,
  currentWeek: 'No tasks yet',
  nextTask: 'TBC',
  nextTaskDate: '',
})
const selectedProgressGroupId = ref('')

const nextEventDateParts = computed(() => {
  const formatted = formatEventDate(
    nextEvent.value?.date || '',
    nextEvent.value?.eventTimezone || timeZone.value,
  ) || 'TBC'
  const parts = formatted.split(' ')
  return {
    day: parts[0] || 'TBC',
    rest: parts.slice(1).join(' '),
  }
})

const dashboardShellRef = ref(null)

const dashboardPalette = {
  textPrimary: '#174243',
  textSecondary: '#6c757d',
  textMuted: '#8a949e',
  textLink: '#4f5f6f',
  surfaceBase: '#ffffff',
  surfaceElevated: '#ffffff',
  surfaceSoft: '#f8f9fa',
  borderDefault: '#e0e0e0',
  borderStrong: '#cfd6dc',
  accentBlue: '#5f6f7f',
  accentTeal: '#6f7c83',
  accentViolet: '#70747c',
  accentAmber: '#7a7568',
  accentRose: '#7a6970',
  shadowLg: '0 4px 12px rgba(0, 0, 0, 0.1)',
  shadowMd: '0 2px 4px rgba(0, 0, 0, 0.1)',
  heroOverlayA: '#ffffff',
  heroOverlayB: '#ffffff',
  shellBackdrop: '#f8f9fa',
  pageGlowOne: 'transparent',
  pageGlowTwo: 'transparent',
  pageGlowThree: 'transparent',
  fxOpacity: '0',
}

const dashboardThemeStyle = computed(() => {
  return {
    '--text-primary': dashboardPalette.textPrimary,
    '--text-secondary': dashboardPalette.textSecondary,
    '--text-muted': dashboardPalette.textMuted,
    '--text-link': dashboardPalette.textLink,
    '--surface-base': dashboardPalette.surfaceBase,
    '--surface-elevated': dashboardPalette.surfaceElevated,
    '--surface-soft': dashboardPalette.surfaceSoft,
    '--border-default': dashboardPalette.borderDefault,
    '--border-strong': dashboardPalette.borderStrong,
    '--accent-blue': dashboardPalette.accentBlue,
    '--accent-teal': dashboardPalette.accentTeal,
    '--accent-violet': dashboardPalette.accentViolet,
    '--accent-amber': dashboardPalette.accentAmber,
    '--accent-rose': dashboardPalette.accentRose,
    '--shadow-lg': dashboardPalette.shadowLg,
    '--shadow-md': dashboardPalette.shadowMd,
    '--hero-overlay-a': dashboardPalette.heroOverlayA,
    '--hero-overlay-b': dashboardPalette.heroOverlayB,
    '--dashboard-shell-backdrop': dashboardPalette.shellBackdrop,
    '--page-glow-one': dashboardPalette.pageGlowOne,
    '--page-glow-two': dashboardPalette.pageGlowTwo,
    '--page-glow-three': dashboardPalette.pageGlowThree,
    '--dashboard-fx-opacity': dashboardPalette.fxOpacity,
  }
})

const headerHighlights = computed(() => {
  if (isAdmin.value) {
    return [
      { key: 'groups', label: `${dashboardSummary.value.activeGroups} active groups` },
      { key: 'matches', label: `${adminWorkflow.value.pendingMatches} pending matches` },
      { key: 'approvals', label: `${adminWorkflow.value.pendingApprovals} approvals` },
    ]
  }

  if (isMentoringRole.value) {
    return [
      { key: 'groups', label: `${dashboardSummary.value.activeGroups} mentoring groups` },
      { key: 'events', label: `${dashboardSummary.value.upcomingEvents} upcoming sessions` },
      { key: 'progress', label: `${progressSnapshot.value.completionRate}% progress` },
    ]
  }

  return [
    { key: 'groups', label: `${dashboardSummary.value.activeGroups} active groups` },
    { key: 'events', label: `${dashboardSummary.value.upcomingEvents} upcoming events` },
    {
      key: 'tasks',
      label: `${progressSnapshot.value.completedTasks}/${progressSnapshot.value.totalTasks} tasks done`,
    },
  ]
})

const announcementsCount = computed(() => announcements.value.length)
const resourcesCount = computed(() => resources.value.length)
const groupsCount = computed(() => groups.value.length)
const shouldBlockGroupsNavigation = computed(() => !isAdmin.value && groupsCount.value === 0)
const hasNoAssignedMembership = computed(() => !isAdmin.value && groupsCount.value === 0)

const nextEvent = computed(() => {
  return events.value[0] || null
})

const announcementsPreview = computed(() => {
  return announcements.value.slice(0, 3)
})

const resourcesPreview = computed(() => {
  return resources.value.slice(0, 12)
})

const groupsPreview = computed(() => {
  return groups.value.slice(0, isAdmin.value ? 4 : 3)
})

const progressGroupOptions = computed(() => {
  return groups.value
    .map((group) => ({
      id: String(group?.id || ''),
      label: getGroupName(group),
    }))
    .filter((group) => group.id)
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
        accent: 'blue',
      },
      {
        key: 'events',
        title: 'Upcoming Events',
        value: dashboardSummary.value.upcomingEvents,
        subtext: nextEvent.value ? `Next: ${nextEvent.value.title}` : 'No upcoming event',
        icon: 'fas fa-calendar-days',
        accent: 'violet',
      },
      {
        key: 'matches',
        title: 'Pending Matches',
        value: adminWorkflow.value.pendingMatches,
        subtext: 'Items waiting for mentor allocation review',
        icon: 'fas fa-arrows-rotate',
        accent: 'teal',
      },
      {
        key: 'approvals',
        title: 'Open Approvals',
        value: adminWorkflow.value.pendingApprovals,
        subtext: 'Requests that need admin action',
        icon: 'fas fa-badge-check',
        accent: 'amber',
      },
    ]
  }

  if (isMentoringRole.value) {
    return [
      {
        key: 'groups',
        title: 'My Groups',
        value: dashboardSummary.value.activeGroups,
        subtext: 'Groups currently assigned to you',
        icon: 'fas fa-users',
        accent: 'blue',
      },
      {
        key: 'events',
        title: 'Upcoming Sessions',
        value: dashboardSummary.value.upcomingEvents,
        subtext: nextEvent.value ? `Next: ${nextEvent.value.title}` : 'No upcoming session',
        icon: 'fas fa-calendar-check',
        accent: 'violet',
      },
      {
        key: 'resources',
        title: isSupervisor.value ? 'Supervisor Resources' : 'Mentor Resources',
        value: resourcesCount.value,
        subtext: 'Guides, rubrics, and support materials',
        icon: 'fas fa-book-open',
        accent: 'teal',
      },
      {
        key: 'updates',
        title: 'Announcements',
        value: announcementsCount.value,
        subtext: 'Latest program communication',
        icon: 'fas fa-bullhorn',
        accent: 'rose',
      },
    ]
  }

  return [
    {
      key: 'groups',
      title: 'My Groups',
      value: dashboardSummary.value.activeGroups,
      subtext: 'Your current mentoring spaces',
      icon: 'fas fa-users',
      accent: 'blue',
    },
    {
      key: 'events',
      title: 'Upcoming Events',
      value: dashboardSummary.value.upcomingEvents,
      subtext: nextEvent.value ? `Next: ${nextEvent.value.title}` : 'No upcoming event',
      icon: 'fas fa-calendar-check',
      accent: 'violet',
    },
    {
      key: 'tasks',
      title: 'Tasks Completed',
      value: `${progressSnapshot.value.completedTasks}/${progressSnapshot.value.totalTasks}`,
      subtext: hasNoAssignedMembership.value
        ? `Please contact the administrator via ${SUPPORT_EMAIL}`
        : 'Your progress in the current program cycle',
      icon: 'fas fa-circle-check',
      accent: 'teal',
    },
    {
      key: 'resources',
      title: 'Resources',
      value: resourcesCount.value,
      subtext: 'Materials available to you',
      icon: 'fas fa-book',
      accent: 'amber',
    },
  ]
})

const groupsSectionTitle = computed(() => {
  if (isAdmin.value) return `Active Mentoring Groups (${groupsCount.value})`
  if (isMentor.value) return `My Mentoring Groups (${groupsCount.value})`
  if (isSupervisor.value) return `Supervised Groups (${groupsCount.value})`
  return `My Active Groups (${groupsCount.value})`
})

function showNoMembershipPopup() {
  showNoMembershipNotice.value = true
}

function closeNoMembershipPopup() {
  showNoMembershipNotice.value = false
}

const resourcesSectionTitle = computed(() => {
  if (isAdmin.value) return 'Resource Library Snapshot'
  if (isMentor.value) return 'Mentor Resources'
  if (isSupervisor.value) return 'Supervisor Resources'
  return 'Learning Resources'
})

const announcementsSectionTitle = computed(() => {
  if (isAdmin.value) return 'Latest Broadcasts'
  if (isMentoringRole.value) return 'Program Updates'
  return 'Recent Announcements'
})

function getEmptyProgressSnapshot() {
  return {
    completionRate: 0,
    completedTasks: 0,
    totalTasks: 0,
    currentWeek: 'No tasks yet',
    nextTask: 'TBC',
    nextTaskDate: '',
  }
}

function extractCollectionItems(data) {
  if (Array.isArray(data)) return data
  if (Array.isArray(data?.results)) return data.results
  return []
}

function truncateText(value, maxLength = 160) {
  const text = String(value || '')
    .replace(/\s+/g, ' ')
    .trim()

  if (text.length <= maxLength) return text
  return `${text.slice(0, maxLength - 1).trim()}...`
}

function stripHtml(value) {
  const source = String(value || '')
  if (typeof document !== 'undefined') {
    const template = document.createElement('template')
    template.innerHTML = source
    return (template.content.textContent || '').replace(/\s+/g, ' ').trim()
  }

  return source
    .replace(/<[^>]*>/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
}

function escapeHtml(value) {
  return String(value || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

function plainTextToHtml(value) {
  return String(value || '')
    .split(/\n{2,}/)
    .map((paragraph) => paragraph.trim())
    .filter(Boolean)
    .map((paragraph) => `<p>${escapeHtml(paragraph).replace(/\n/g, '<br>')}</p>`)
    .join('')
}

function sanitizeDashboardAnnouncementRichText(value) {
  const source = String(value || '').trim()
  const fallbackHtml = '<p>Open the announcement to read more details.</p>'
  if (!source) return fallbackHtml

  const rawHtml = /<\/?[a-z][\s\S]*>/i.test(source) ? source : plainTextToHtml(source)
  if (typeof document === 'undefined') return rawHtml

  const allowedTags = new Set([
    'B',
    'BLOCKQUOTE',
    'BR',
    'CODE',
    'DIV',
    'EM',
    'H1',
    'H2',
    'H3',
    'H4',
    'H5',
    'H6',
    'I',
    'LI',
    'OL',
    'P',
    'S',
    'SPAN',
    'STRONG',
    'U',
    'UL',
  ])
  const removedTags = new Set([
    'AUDIO',
    'CANVAS',
    'EMBED',
    'IFRAME',
    'IMG',
    'OBJECT',
    'PICTURE',
    'SCRIPT',
    'STYLE',
    'SVG',
    'TABLE',
    'TBODY',
    'TD',
    'TFOOT',
    'TH',
    'THEAD',
    'TR',
    'VIDEO',
  ])

  const template = document.createElement('template')
  template.innerHTML = rawHtml

  const cleanNode = (node) => {
    if (node.nodeType !== Node.ELEMENT_NODE) return

    const element = node
    if (removedTags.has(element.tagName)) {
      element.remove()
      return
    }

    if (!allowedTags.has(element.tagName)) {
      Array.from(element.childNodes).forEach(cleanNode)
      element.replaceWith(...Array.from(element.childNodes))
      return
    }

    for (const attribute of Array.from(element.attributes)) {
      element.removeAttribute(attribute.name)
    }

    Array.from(element.childNodes).forEach(cleanNode)
  }

  Array.from(template.content.childNodes).forEach(cleanNode)
  return template.innerHTML || fallbackHtml
}

function getAnnouncementBody(announcement) {
  return (
    announcement?.body ||
    announcement?.content ||
    announcement?.summary ||
    announcement?.description ||
    announcement?.excerpt ||
    ''
  )
}

function formatEventTime(startValue, endValue) {
  return formatEventTimeRange(startValue, endValue, timeZone.value)
}

function normalizeEventFormat(event) {
  const format = event?.event_format || event?.eventFormat
  if (format === 'virtual' || format === 'hybrid') return format
  return 'in_person'
}

function getEventModeLabel(format) {
  if (format === 'virtual') return 'Virtual event'
  if (format === 'hybrid') return 'Hybrid event'
  return 'In-person event'
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
  const role = String(value || '')
    .trim()
    .toLowerCase()

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
  const matchingMemberships = memberships.filter((item) => String(item?.group) === String(groupId))
  const activeMentors = matchingMemberships.filter((item) => {
    const role = String(item?.membership_role || '').toLowerCase()
    return role.includes('mentor') || role.includes('supervisor')
  })
  const leadName =
    group?.lead_name || group?.lead_user
      ? [group?.lead_user?.first_name, group?.lead_user?.last_name]
          .filter(Boolean)
          .join(' ')
          .trim() ||
        group?.lead_user?.email ||
        group?.lead_name
      : ''
  const trackLabel =
    group?.track_name ||
    trackById.get(Number(group?.track)) ||
    (group?.track ? `Track ${group.track}` : group?.category)
  const memberCount = Number(
    group?.member_count ?? group?.memberCount ?? group?.members ?? matchingMemberships.length ?? 0,
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
    track: trackLabel || 'General',
  }
}

function normalizeResource(resource) {
  const typeLabel =
    resource?.resource_type_detail?.type_name || resource?.category || resource?.type || 'General'
  const visibleRoles = Array.isArray(resource?.visible_roles)
    ? resource.visible_roles.map((role) => role?.role_name)
    : []
  const audienceRoles = Array.isArray(resource?.audiences)
    ? resource.audiences.map((rule) => rule?.role_name)
    : []
  const roles = [...visibleRoles, ...audienceRoles].map(normalizeRoleName).filter(Boolean)
  const scope = String(resource?.visibility_scope || '').toLowerCase()
  const normalizedRoles =
    scope === 'public' || roles.length === 0 ? ['all'] : Array.from(new Set(roles))

  return {
    ...resource,
    id: resource?.id,
    title: resource?.resource_name || resource?.title || resource?.name || 'Untitled resource',
    name: resource?.resource_name || resource?.name || resource?.title || 'Untitled resource',
    type: resolveResourceIconType(typeLabel),
    category: typeLabel,
    updated:
      resource?.upload_datetime || resource?.updated || resource?.date || resource?.created_at,
    role: normalizedRoles[0] || 'all',
    roles: normalizedRoles,
  }
}

function normalizeAnnouncement(announcement) {
  const body = getAnnouncementBody(announcement)
  const bodyText = stripHtml(body)
  const audienceRoles = Array.isArray(announcement?.audiences)
    ? announcement.audiences.map((rule) => rule?.role_name)
    : []
  const normalizedRoles = audienceRoles.map(normalizeRoleName).filter(Boolean)
  const visibilityScope = normalizeRoleName(announcement?.visibility_scope)
  const audience =
    visibilityScope === 'public' ? 'all' : normalizedRoles[0] || visibilityScope || 'all'

  return {
    ...announcement,
    id: announcement?.id,
    title: announcement?.title || announcement?.name || 'Untitled announcement',
    summary: truncateText(bodyText),
    description: body,
    content: body,
    bodyText,
    bodyHtml: sanitizeDashboardAnnouncementRichText(body),
    date: announcement?.published_at || announcement?.date || announcement?.created_at,
    updated: announcement?.published_at || announcement?.updated || announcement?.created_at,
    author: announcement?.sender_name || 'Administrator',
    audience,
  }
}

function normalizeEvent(event) {
  const start = event?.start_datetime || event?.date || ''
  const end = event?.ends_datetime || event?.end_datetime || event?.end || ''
  const format = normalizeEventFormat(event)
  const eventTimezone = event?.event_timezone || event?.eventTimezone || timeZone.value
  const hasPhysicalPlace = format !== 'virtual' && Boolean(event?.location)

  return {
    ...event,
    id: event?.id,
    title: event?.event_name || event?.title || event?.name || 'Untitled event',
    date: start,
    time: formatEventTimeRange(start, end, eventTimezone) || event?.time || '',
    location: hasPhysicalPlace ? event.location : format === 'virtual' ? 'Online' : 'Location TBC',
    mode: getEventModeLabel(format),
    link: format === 'virtual' || format === 'hybrid' ? event?.location_link || event?.link : '',
    eventFormat: format,
    eventTimezone,
  }
}

function deriveDashboardSummary() {
  if (isAdmin.value && adminOperationsSummary.value) {
    dashboardSummary.value = {
      activeGroups: Number(adminOperationsSummary.value.active_groups || groups.value.length),
      upcomingEvents: Number(adminOperationsSummary.value.upcoming_events ?? upcomingEventsCount.value),
      resources: resources.value.length,
      announcements: announcements.value.length,
    }
    return
  }

  dashboardSummary.value = {
    activeGroups: groups.value.length,
    upcomingEvents: upcomingEventsCount.value,
    resources: resources.value.length,
    announcements: announcements.value.length,
  }
}

function normalizeProgressSnapshot(payload) {
  const fallback = getEmptyProgressSnapshot()

  if (!payload || typeof payload !== 'object') {
    return fallback
  }

  return {
    completionRate: Number(
      payload?.completionRate ?? payload?.completion_rate ?? fallback.completionRate,
    ),
    completedTasks: Number(
      payload?.completedTasks ?? payload?.completed_tasks ?? fallback.completedTasks,
    ),
    totalTasks: Number(payload?.totalTasks ?? payload?.total_tasks ?? fallback.totalTasks),
    currentWeek: payload?.currentWeek ?? payload?.current_stage ?? fallback.currentWeek,
    nextTask: payload?.nextTask ?? payload?.next_task?.name ?? fallback.nextTask,
    nextTaskDate: payload?.nextTaskDate ?? payload?.next_task?.due_date ?? fallback.nextTaskDate,
  }
}

function ensureSelectedProgressGroup() {
  const options = progressGroupOptions.value
  if (!options.length) {
    selectedProgressGroupId.value = ''
    return
  }

  const hasSelectedGroup = options.some((group) => group.id === selectedProgressGroupId.value)
  if (!hasSelectedGroup) {
    selectedProgressGroupId.value = options[0].id
  }
}

function getProgressEndpoint() {
  ensureSelectedProgressGroup()
  if (!selectedProgressGroupId.value) return DASHBOARD_ENDPOINTS.progress
  return `${DASHBOARD_ENDPOINTS.progress}?group_id=${encodeURIComponent(selectedProgressGroupId.value)}`
}

function hasGroupPreviewShape(items) {
  return (
    Array.isArray(items) &&
    items.some(
      (item) =>
        item &&
        ('track_name' in item ||
          'member_count' in item ||
          'lead_name' in item ||
          'lead_user' in item),
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
        Accept: 'application/json',
      },
    }),
  })

  if (allowNoContent && response.status === 204) {
    return null
  }

  if (!response.ok) {
    throw await apiErrorFromResponse(response)
  }

  const text = await response.text()
  let data = null
  try {
    data = text ? JSON.parse(text) : null
  } catch {
    data = null
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
      loadAdminWorkflow(),
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
    // For non-admin users we rely on the server's ?mine=true filter (added to
    // GroupViewSet) — no more pulling every group + every membership row just
    // to filter client-side. Admins still get the full list.
    const primaryGroupUrl = isAdmin.value
      ? DASHBOARD_ENDPOINTS.groupsPreview(false)
      : DASHBOARD_ENDPOINTS.groupsPreview(true)
    const fallbackGroupUrls = isAdmin.value
      ? [DASHBOARD_ENDPOINTS.groups]
      : [DASHBOARD_ENDPOINTS.groupsMine]
    const data = await fetchFirstAvailable([primaryGroupUrl, ...fallbackGroupUrls])
    const groupItems = extractCollectionItems(data)

    if (
      Array.isArray(groupItems) &&
      groupItems.length === 0 &&
      String(primaryGroupUrl).includes('/dashboard/v1/groups-preview/')
    ) {
      groups.value = []
      return
    }

    if (hasGroupPreviewShape(groupItems)) {
      groups.value = groupItems.map((group) => normalizeGroup(group))
      return
    }

    let trackById = new Map()
    try {
      const tracks = extractCollectionItems(await fetchJson(DASHBOARD_ENDPOINTS.tracks))
      trackById = new Map(
        tracks.map((track) => [Number(track?.id), track?.track_name]).filter((item) => item[1]),
      )
    } catch {
      trackById = new Map()
    }

    groups.value = groupItems.map((group) => normalizeGroup(group, [], trackById))
  } catch {
    groups.value = []
  }
}

async function loadResources() {
  try {
    const data = await fetchJson(DASHBOARD_ENDPOINTS.resources)
    const liveResources = extractCollectionItems(data)
    resources.value = liveResources.map(normalizeResource)
  } catch {
    resources.value = []
  }
}

async function loadAnnouncements() {
  try {
    const data = await fetchJson(DASHBOARD_ENDPOINTS.announcements)
    const liveAnnouncements = extractCollectionItems(data)
    announcements.value = liveAnnouncements.map(normalizeAnnouncement)
  } catch {
    announcements.value = []
  }
}

async function loadEvents() {
  try {
    const countData = await fetchJson(DASHBOARD_ENDPOINTS.eventsCount)
    upcomingEventsCount.value = Number(countData?.count ?? 0)

    const nextEventData = await fetchJson(DASHBOARD_ENDPOINTS.nextEvent, {
      allowNoContent: true,
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
      DASHBOARD_ENDPOINTS.events,
    ])
    const liveEvents = extractCollectionItems(fallbackEvents)
    events.value = liveEvents.map(normalizeEvent)
  } catch {
    try {
      const fallbackEvents = await fetchFirstAvailable([
        DASHBOARD_ENDPOINTS.personalizedEvents,
        DASHBOARD_ENDPOINTS.events,
      ])
      const liveEvents = extractCollectionItems(fallbackEvents)
      upcomingEventsCount.value = Number(fallbackEvents?.count ?? liveEvents.length)
      events.value = liveEvents.length ? liveEvents.map(normalizeEvent) : []
    } catch {
      upcomingEventsCount.value = 0
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
      draftBulkMessages: 0,
    }
  } catch {
    adminOperationsSummary.value = null
    adminWorkflow.value = {
      pendingMatches: 0,
      pendingReassignments: 0,
      pendingApprovals: 0,
      draftBulkMessages: 0,
    }
  }
}

async function loadProgress() {
  if (hasNoAssignedMembership.value) {
    progressSnapshot.value = getEmptyProgressSnapshot()
    return
  }

  try {
    const data = await fetchJson(getProgressEndpoint())
    progressSnapshot.value = normalizeProgressSnapshot(data)
  } catch {
    progressSnapshot.value = getEmptyProgressSnapshot()
  }
}

function getAnnouncementTitle(item) {
  return item?.title || item?.name || item?.subject || 'Untitled announcement'
}

function getAnnouncementMeta(item) {
  return item?.updated || item?.date || item?.created_at || 'Recently posted'
}

function getAnnouncementSnippet(item) {
  return (
    item?.summary ||
    item?.description ||
    item?.content ||
    item?.excerpt ||
    'Open the announcement to read more details.'
  )
}

function getAnnouncementPreviewHtml(item) {
  if (item?.bodyHtml) return item.bodyHtml
  return sanitizeDashboardAnnouncementRichText(getAnnouncementSnippet(item))
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

onMounted(async () => {
  await loadDashboardData()
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
  --text-primary: #eef5ff;
  --text-secondary: #94b8d8;
  --text-muted: #5c7a9a;
  --text-link: #7ec8ff;

  --surface-base: rgba(6, 18, 12, 0.82);
  --surface-elevated: rgba(8, 22, 16, 0.9);

  --border-default: rgba(255, 255, 255, 0.09);
  --border-strong: rgba(255, 255, 255, 0.16);

  --accent-blue: #60a5fa;
  --accent-teal: #2dd4bf;
  --accent-violet: #a78bfa;
  --accent-amber: #fbbf24;
  --accent-rose: #f87171;

  --shadow-lg: 0 24px 64px rgba(0, 6, 2, 0.52);
  --shadow-md: 0 14px 38px rgba(0, 6, 2, 0.4);
  --shadow-sm: 0 8px 22px rgba(0, 6, 2, 0.3);

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

/* ──────────────────────────────────────────────────────────────
   § 4  SECTION LAYOUT
   ────────────────────────────────────────────────────────────── */
.dashboard-section {
  margin-bottom: 1.6rem;
}

.dashboard-section-grid {
  display: grid;
  gap: 1.2rem;
}

.two-col-layout {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}
.library-layout {
  grid-template-columns: 1fr;
}
.summary-grid {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

/* ──────────────────────────────────────────────────────────────
   § 5  HERO CARD
   ────────────────────────────────────────────────────────────── */
.dashboard-hero-shell {
  margin-bottom: 1.5rem;
}

.dashboard-welcome-header {
  margin-bottom: 2rem;
}

.dashboard-welcome-header .hero-title {
  margin: 0;
}

.dashboard-hero-card {
  position: relative;
  overflow: hidden;
  border-radius: var(--radius-hero);
  padding: 1.6rem;
  border: 1px solid rgba(255, 255, 255, 0.13);
  background: linear-gradient(145deg, rgba(6, 18, 12, 0.92), rgba(7, 16, 11, 0.78));
  box-shadow:
    var(--shadow-lg),
    inset 0 1px 0 rgba(255, 255, 255, 0.07);
  backdrop-filter: blur(28px);
  -webkit-backdrop-filter: blur(28px);
  transition:
    transform var(--t-base) var(--ease-out),
    box-shadow var(--t-base);
}

/* Blue aurora top-left */
.dashboard-hero-card::before {
  content: '';
  position: absolute;
  top: -35%;
  left: -6%;
  width: 52%;
  height: 72%;
  border-radius: 999px;
  background: radial-gradient(circle, rgba(96, 165, 250, 0.22), transparent 66%);
  filter: blur(22px);
  pointer-events: none;
}

/* Teal aurora bottom-right */
.dashboard-hero-card::after {
  content: '';
  position: absolute;
  bottom: -32%;
  right: -8%;
  width: 46%;
  height: 72%;
  border-radius: 999px;
  background: radial-gradient(circle, rgba(45, 212, 191, 0.18), transparent 68%);
  filter: blur(22px);
  pointer-events: none;
}

/* ──────────────────────────────────────────────────────────────
   § 6  THEME RAIL
   ────────────────────────────────────────────────────────────── */

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
.dashboard-hero-calendar {
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
  background: var(--white);
  border: 1px solid var(--border-light);
  box-shadow: 0 2px 4px var(--shadow);
  overflow: hidden;
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
  backdrop-filter: none;
  -webkit-backdrop-filter: none;
}

.hero-eyebrow {
  color: #6c757d;
  border-radius: 8px;
  border: 1px solid var(--border-light);
  background: #f8f9fa;
  box-shadow: none;
}

.hero-title {
  margin: 0;
  font-size: clamp(2rem, 3vw, 3.08rem);
  line-height: 0.98;
  font-weight: 850;
  letter-spacing: -0.05em;
  color: var(--charcoal);
  text-wrap: balance;
  text-shadow: none;
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
  border: 1px solid rgba(255, 255, 255, 0.1);
  color: var(--text-primary);
  overflow: hidden;
  isolation: isolate;
  transition:
    transform var(--t-base) var(--ease-out),
    border-color var(--t-fast),
    box-shadow var(--t-fast),
    background var(--t-fast);
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
  background: linear-gradient(
    115deg,
    transparent 10%,
    rgba(255, 255, 255, 0.14) 30%,
    transparent 48%,
    transparent 70%,
    rgba(255, 255, 255, 0.08) 88%,
    transparent
  );
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
  background:
    radial-gradient(circle at top left, rgba(255, 255, 255, 0.1), transparent 42%),
    linear-gradient(145deg, rgba(140, 200, 170, 0.12), rgba(8, 22, 12, 0.08));
}

.hero-meta-chip--cyan {
  border-radius: 20px 20px 20px 12px;
  background: linear-gradient(135deg, rgba(20, 80, 50, 0.34), rgba(6, 18, 11, 0.72));
  border-color: rgba(34, 211, 180, 0.28);
}

.hero-meta-chip--cyan::after {
  background:
    radial-gradient(circle at top left, rgba(34, 211, 180, 0.24), transparent 38%),
    linear-gradient(135deg, rgba(34, 211, 180, 0.1), rgba(6, 18, 11, 0.02));
}

.hero-meta-chip--violet {
  border-radius: 16px 22px 16px 22px;
  background: linear-gradient(135deg, rgba(91, 33, 182, 0.26), rgba(8, 20, 12, 0.74));
  border-color: rgba(167, 139, 250, 0.3);
}

.hero-meta-chip--violet::after {
  background:
    radial-gradient(circle at top left, rgba(192, 132, 252, 0.22), transparent 38%),
    linear-gradient(135deg, rgba(167, 139, 250, 0.1), rgba(6, 18, 11, 0.02));
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
  box-shadow:
    0 0 0 4px color-mix(in srgb, currentColor 18%, transparent),
    0 0 18px color-mix(in srgb, currentColor 30%, transparent);
}

.status-pill:nth-child(1) {
  border: 1px solid rgba(96, 165, 250, 0.24);
  color: #bfdbfe;
}
.status-pill:nth-child(2) {
  border: 1px solid rgba(45, 212, 191, 0.24);
  color: #99f6e4;
}
.status-pill:nth-child(3) {
  border: 1px solid rgba(244, 114, 182, 0.24);
  color: #fbcfe8;
}

/* ──────────────────────────────────────────────────────────────
   § 8  SHOWCASE CAROUSEL
   ────────────────────────────────────────────────────────────── */
.dashboard-hero-calendar {
  align-self: stretch;
  margin-top: 0;
}

.dashboard-hero-calendar :deep(.mini-calendar) {
  min-height: 100%;
}

.summary-card {
  position: relative;
  overflow: hidden;
  min-height: 170px;
  padding: 1.25rem 1.2rem 1.1rem;
  border-radius: var(--radius-card);
  border: 1px solid rgba(255, 255, 255, 0.09);
  background: linear-gradient(160deg, rgba(6, 18, 12, 0.9), rgba(7, 16, 10, 0.76));
  box-shadow: var(--shadow-md);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  transition:
    transform var(--t-base) var(--ease-out),
    box-shadow var(--t-base),
    border-color var(--t-fast);
}

.summary-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 2.5px;
  border-radius: var(--radius-card) var(--radius-card) 0 0;
}

.summary-card::after {
  content: '';
  position: absolute;
  right: -24px;
  top: -28px;
  width: 130px;
  height: 130px;
  border-radius: 999px;
  opacity: 0.32;
  pointer-events: none;
}

.summary-card:hover {
  transform: translateY(-7px) scale(1.014);
  box-shadow: var(--shadow-lg);
}
.summary-card:hover .summary-icon-wrap {
  transform: translateY(-4px) rotate(-8deg);
}

.accent-blue::before {
  background: linear-gradient(90deg, transparent, #60a5fa, #38bdf8, transparent);
}
.accent-blue::after {
  background: radial-gradient(circle, rgba(96, 165, 250, 0.9), transparent 70%);
}
.accent-blue:hover {
  border-color: rgba(96, 165, 250, 0.26);
}
.accent-blue .summary-icon-wrap {
  color: #93c5fd;
}

.accent-violet::before {
  background: linear-gradient(90deg, transparent, #a78bfa, #c084fc, transparent);
}
.accent-violet::after {
  background: radial-gradient(circle, rgba(167, 139, 250, 0.88), transparent 70%);
}
.accent-violet:hover {
  border-color: rgba(167, 139, 250, 0.26);
}
.accent-violet .summary-icon-wrap {
  color: #c4b5fd;
}

.accent-teal::before {
  background: linear-gradient(90deg, transparent, #2dd4bf, #5eead4, transparent);
}
.accent-teal::after {
  background: radial-gradient(circle, rgba(45, 212, 191, 0.9), transparent 70%);
}
.accent-teal:hover {
  border-color: rgba(45, 212, 191, 0.26);
}
.accent-teal .summary-icon-wrap {
  color: #5eead4;
}

.accent-amber::before {
  background: linear-gradient(90deg, transparent, #fbbf24, #fcd34d, transparent);
}
.accent-amber::after {
  background: radial-gradient(circle, rgba(251, 191, 36, 0.88), transparent 70%);
}
.accent-amber:hover {
  border-color: rgba(251, 191, 36, 0.26);
}
.accent-amber .summary-icon-wrap {
  color: #fcd34d;
}

.accent-rose::before {
  background: linear-gradient(90deg, transparent, #f87171, #fb7185, transparent);
}
.accent-rose::after {
  background: radial-gradient(circle, rgba(248, 113, 113, 0.86), transparent 70%);
}
.accent-rose:hover {
  border-color: rgba(248, 113, 113, 0.26);
}
.accent-rose .summary-icon-wrap {
  color: #fca5a5;
}

.summary-card-top {
  display: flex;
  align-items: center;
  gap: 0.8rem;
}

.summary-icon-wrap {
  width: 46px;
  height: 46px;
  border-radius: 14px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.07);
  border: 1px solid rgba(255, 255, 255, 0.1);
  font-size: 0.96rem;
  transition:
    transform var(--t-base) var(--ease-out),
    box-shadow var(--t-fast);
}

.summary-label {
  color: var(--text-secondary);
  font-size: 0.91rem;
  font-weight: 700;
}
.summary-card-value {
  margin-top: 1rem;
  font-size: clamp(2rem, 3vw, 2.5rem);
  line-height: 1;
  font-weight: 800;
  color: var(--text-primary);
  letter-spacing: -0.05em;
}
.summary-card-subtext {
  margin-top: 0.65rem;
  max-width: 26ch;
  color: var(--text-muted);
  font-size: 0.87rem;
  line-height: 1.55;
}

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

.feature-card {
  min-height: 100%;
}

.surface-card-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 1.1rem;
}

.surface-kicker {
  margin: 0 0 0.22rem;
  font-size: 0.72rem;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: #3cc87a;
  display: flex;
  align-items: center;
  gap: 0.42rem;
}

.surface-kicker::before {
  content: '';
  display: inline-block;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #3cc87a;
  box-shadow: 0 0 8px rgba(60, 200, 110, 0.85);
  flex-shrink: 0;
}

.surface-card-title {
  margin: 0;
  color: var(--text-primary);
  font-size: 1.12rem;
  font-weight: 800;
  letter-spacing: -0.02em;
}

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
  transition:
    transform var(--t-fast),
    border-color var(--t-fast),
    background var(--t-fast);
}

.surface-link:hover {
  transform: translateY(-1px);
  border-color: rgba(60, 200, 120, 0.32);
  background: rgba(60, 200, 120, 0.09);
}

.surface-link-button {
  border: 1px solid rgba(60, 200, 120, 0.16);
  cursor: pointer;
  font-family: inherit;
}

/* ──────────────────────────────────────────────────────────────
   § 12  ACTION CENTER  (cyberpunk terminal aesthetic)
   ────────────────────────────────────────────────────────────── */
/* ──────────────────────────────────────────────────────────────
   § 13  PROGRESS CARD  (orbital ring display)
   ────────────────────────────────────────────────────────────── */
.progress-card {
  border-color: rgba(167, 139, 250, 0.16);
}

.progress-group-select {
  min-width: 180px;
  max-width: 260px;
  min-height: 34px;
  padding: 0.36rem 0.72rem;
  border-radius: var(--radius-chip);
  border: 1px solid rgba(167, 139, 250, 0.22);
  background: rgba(255, 255, 255, 0.05);
  color: var(--text-primary);
  font-size: 0.82rem;
  font-weight: 700;
  outline: none;
}

.progress-group-select:focus {
  border-color: rgba(167, 139, 250, 0.48);
  box-shadow: 0 0 0 3px rgba(167, 139, 250, 0.12);
}

.progress-card::after {
  content: '';
  position: absolute;
  bottom: -20%;
  right: -10%;
  width: 38%;
  aspect-ratio: 1;
  border-radius: 999px;
  background: radial-gradient(circle, rgba(103, 232, 249, 0.1), transparent 70%);
  pointer-events: none;
  filter: blur(16px);
}

.progress-layout {
  display: flex;
  gap: 1.1rem;
  align-items: center;
  flex-wrap: wrap;
}

.progress-ring-shell {
  flex: 0 0 148px;
  display: flex;
  justify-content: center;
  position: relative;
  isolation: isolate;
}

.progress-ring {
  position: relative;
  width: 130px;
  height: 130px;
  border-radius: 999px;
  padding: 10px;
  box-shadow:
    0 24px 52px rgba(0, 3, 18, 0.4),
    inset 0 0 0 1px rgba(255, 255, 255, 0.04);
}

.progress-ring-inner {
  width: 100%;
  height: 100%;
  border-radius: 999px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: linear-gradient(180deg, rgba(5, 16, 10, 0.97), rgba(5, 14, 9, 0.97));
  border: 1px solid rgba(255, 255, 255, 0.05);
}

.progress-value {
  font-size: 1.85rem;
  font-weight: 800;
  color: var(--text-primary);
  letter-spacing: -0.04em;
}
.progress-label {
  margin-top: 0.14rem;
  color: var(--text-muted);
  font-size: 0.78rem;
  font-weight: 700;
}

.progress-details {
  flex: 1;
  min-width: 220px;
}

.progress-detail-row {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.7rem 0.82rem;
  border-radius: 12px;
  color: var(--text-secondary);
  transition:
    transform var(--t-fast),
    background var(--t-fast);
}

.progress-detail-row:hover {
  transform: translateX(4px);
  background: rgba(255, 255, 255, 0.04);
}
.progress-detail-row strong {
  color: var(--text-primary);
  font-weight: 800;
}

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
  transition:
    transform var(--t-base) var(--ease-out),
    box-shadow var(--t-fast);
}

.event-detail-card:hover .event-date-badge {
  transform: rotate(-4deg) translateY(-4px);
  box-shadow: 0 0 34px rgba(56, 189, 248, 0.24);
}

.event-date-day {
  color: #f0f8ff;
  font-size: 1.5rem;
  font-weight: 800;
  line-height: 1;
}
.event-date-rest {
  margin-top: 0.34rem;
  color: rgba(186, 230, 255, 0.88);
  font-size: 0.8rem;
  line-height: 1.3;
}

.event-content {
  flex: 1;
  min-width: 0;
  transition: transform var(--t-base);
}
.event-detail-card:hover .event-content {
  transform: translateX(3px);
}

.event-title {
  font-size: 1.08rem;
  font-weight: 800;
  color: var(--text-primary);
}

.event-meta-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.88rem;
  margin-top: 0.62rem;
  color: var(--text-secondary);
  font-size: 0.9rem;
}
.event-meta-row span {
  display: inline-flex;
  align-items: center;
  gap: 0.42rem;
}
.location-row {
  margin-top: 0.42rem;
}
.event-actions {
  margin-top: 0.82rem;
}

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
  transition:
    transform var(--t-fast),
    background var(--t-fast),
    box-shadow var(--t-fast);
}

.primary-chip:hover {
  transform: translateY(-2px);
  background: linear-gradient(135deg, rgba(37, 99, 235, 0.34), rgba(45, 212, 191, 0.26));
  box-shadow: 0 12px 28px rgba(37, 99, 235, 0.22);
}

/* ──────────────────────────────────────────────────────────────
   § 15  LISTS  (announcements)
   ────────────────────────────────────────────────────────────── */
.list-stack {
  display: flex;
  flex-direction: column;
  gap: 0.7rem;
}

.list-row {
  display: flex;
  align-items: flex-start;
  gap: 0.82rem;
  text-decoration: none;
  color: inherit;
}

.premium-row {
  padding: 0.85rem 0.95rem;
  border-radius: 16px;
  border: 1px solid rgba(255, 255, 255, 0.07);
  background: rgba(255, 255, 255, 0.03);
  transition:
    transform var(--t-base) var(--ease-out),
    border-color var(--t-fast),
    background var(--t-fast);
}

.premium-row:hover {
  transform: translateX(5px);
  border-color: rgba(251, 191, 36, 0.22);
  background: rgba(251, 191, 36, 0.05);
}

.list-row-icon {
  width: 40px;
  height: 40px;
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 12px;
  font-size: 0.9rem;
  border: 1px solid rgba(255, 255, 255, 0.08);
  transition:
    transform var(--t-fast),
    box-shadow var(--t-fast);
}

.announcement-icon {
  background: rgba(251, 191, 36, 0.12);
  color: #fcd34d;
}

.premium-row:hover .announcement-icon {
  transform: scale(1.08) rotate(-8deg);
  box-shadow: 0 10px 22px rgba(251, 191, 36, 0.22);
}

.list-row-content {
  min-width: 0;
  flex: 1;
}
.list-row-title {
  color: var(--text-primary);
  font-weight: 800;
  line-height: 1.45;
}
.list-row-meta {
  margin-top: 0.14rem;
  color: var(--text-muted);
  font-size: 0.84rem;
}
.list-row-description {
  margin-top: 0.24rem;
  color: var(--text-secondary);
  font-size: 0.87rem;
  line-height: 1.55;
}
.list-row-tail {
  color: var(--text-muted);
  padding-top: 0.18rem;
  transition:
    transform var(--t-fast),
    color var(--t-fast);
}
.premium-row:hover .list-row-tail {
  transform: translateX(3px);
  color: var(--text-secondary);
}

/* ──────────────────────────────────────────────────────────────
   § 16  GROUPS GRID  (identity cards — distinct per card)
   ────────────────────────────────────────────────────────────── */
.groups-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 1.1rem;
}

.group-card-link,
.resource-card-link {
  display: block;
  text-decoration: none;
  color: inherit;
}

.group-card-surface {
  position: relative;
  overflow: hidden;
  height: 100%;
  padding: 1rem;
  border-radius: 20px;
  border: 1px solid rgba(255, 255, 255, 0.09);
  transition:
    transform var(--t-slow) var(--ease-out),
    box-shadow var(--t-base),
    border-color var(--t-fast);
}

.group-card-link:nth-child(1) .group-card-surface {
  background: linear-gradient(150deg, rgba(20, 100, 50, 0.28), rgba(5, 15, 9, 0.84) 50%);
  border-color: rgba(60, 200, 120, 0.18);
}
.group-card-link:nth-child(2) .group-card-surface {
  background: linear-gradient(150deg, rgba(91, 33, 182, 0.28), rgba(5, 15, 9, 0.84) 50%);
  border-color: rgba(167, 139, 250, 0.18);
}
.group-card-link:nth-child(3) .group-card-surface {
  background: linear-gradient(150deg, rgba(13, 148, 100, 0.28), rgba(5, 15, 9, 0.84) 50%);
  border-color: rgba(45, 212, 170, 0.18);
}
.group-card-link:nth-child(4) .group-card-surface {
  background: linear-gradient(150deg, rgba(234, 88, 12, 0.26), rgba(5, 15, 9, 0.84) 50%);
  border-color: rgba(251, 146, 60, 0.18);
}

/* Bottom shine sweep */
.group-card-surface::after {
  content: '';
  position: absolute;
  inset: auto 16px 14px;
  height: 2px;
  border-radius: 999px;
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.72), transparent);
  transform: scaleX(0.26);
  transform-origin: center;
  opacity: 0;
  transition:
    opacity var(--t-fast),
    transform var(--t-base) var(--ease-out);
}

.group-card-link:hover .group-card-surface {
  transform: translateY(-10px) rotateX(2deg) rotateY(-2deg);
  box-shadow: 0 28px 60px rgba(0, 3, 18, 0.38);
}
.group-card-link:hover .group-card-surface::after {
  opacity: 1;
  transform: scaleX(1);
}

.group-card-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.72rem;
}
.group-avatars {
  display: flex;
  align-items: center;
  flex-shrink: 0;
}

.group-avatar {
  width: 2.35rem;
  height: 2.35rem;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 2px solid rgba(7, 13, 28, 0.82);
  margin-left: -0.3rem;
  font-size: 0.74rem;
  font-weight: 800;
  box-shadow: 0 8px 20px rgba(0, 3, 18, 0.26);
  transition: transform var(--t-base) var(--ease-out);
}

.group-avatar:first-child {
  margin-left: 0;
}

.group-card-link:nth-child(1) .primary-avatar {
  background: linear-gradient(135deg, #60a5fa, #22d3ee);
  color: #0c4a6e;
}
.group-card-link:nth-child(2) .primary-avatar {
  background: linear-gradient(135deg, #a78bfa, #f472b6);
  color: #2e1065;
}
.group-card-link:nth-child(3) .primary-avatar {
  background: linear-gradient(135deg, #34d399, #38bdf8);
  color: #064e3b;
}
.group-card-link:nth-child(4) .primary-avatar {
  background: linear-gradient(135deg, #fb923c, #facc15);
  color: #431407;
}

.secondary-avatar {
  background: linear-gradient(135deg, #0f766e, #14b8a6);
  color: #ccfbf1;
}
.tertiary-avatar {
  background: linear-gradient(135deg, #7c3aed, #a78bfa);
  color: #ede9fe;
}

.group-card-link:hover .primary-avatar {
  transform: translateX(-8px) translateY(-2px) scale(1.08);
}
.group-card-link:hover .secondary-avatar {
  transform: translateX(2px) translateY(3px);
}
.group-card-link:hover .tertiary-avatar {
  transform: translateX(10px) translateY(-2px);
}

.group-open-indicator {
  width: 32px;
  height: 32px;
  border-radius: 10px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.07);
  color: #7ec8ff;
  border: 1px solid rgba(255, 255, 255, 0.1);
  transition: transform var(--t-fast);
}

.group-card-link:hover .group-open-indicator {
  transform: translateY(-2px) scale(1.08);
}

.group-name {
  margin-top: 0.9rem;
  color: var(--text-primary);
  font-size: 0.98rem;
  font-weight: 800;
}
.group-meta {
  margin-top: 0.26rem;
  color: var(--text-secondary);
  font-size: 0.86rem;
  line-height: 1.5;
}

/* ──────────────────────────────────────────────────────────────
   § 17  RESOURCES GRID  (color-coded left accent bar)
   ────────────────────────────────────────────────────────────── */
.resource-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 1.15rem;
}

.resource-card-surface {
  position: relative;
  overflow: hidden;
  height: 100%;
  display: flex;
  align-items: flex-start;
  gap: 0.85rem;
  min-height: 154px;
  padding: 1.18rem;
  border-radius: 18px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  transition:
    transform var(--t-base) var(--ease-out),
    box-shadow var(--t-base),
    border-color var(--t-fast);
}

/* Left accent bar */
.resource-card-surface::before {
  content: '';
  position: absolute;
  left: 0;
  top: 12px;
  bottom: 12px;
  width: 4px;
  border-radius: 0 3px 3px 0;
  opacity: 0.72;
  transition:
    width var(--t-fast),
    opacity var(--t-fast);
}

.resource-card-link:nth-child(1) .resource-card-surface {
  background: linear-gradient(155deg, rgba(40, 140, 70, 0.16), rgba(5, 15, 9, 0.8) 50%);
  border-color: rgba(60, 200, 110, 0.16);
}
.resource-card-link:nth-child(1) .resource-card-surface::before {
  background: #3cc87a;
}
.resource-card-link:nth-child(2) .resource-card-surface {
  background: linear-gradient(155deg, rgba(168, 85, 247, 0.16), rgba(5, 15, 9, 0.8) 50%);
  border-color: rgba(167, 139, 250, 0.16);
}
.resource-card-link:nth-child(2) .resource-card-surface::before {
  background: #a78bfa;
}
.resource-card-link:nth-child(3) .resource-card-surface {
  background: linear-gradient(155deg, rgba(45, 212, 170, 0.16), rgba(5, 15, 9, 0.8) 50%);
  border-color: rgba(45, 212, 170, 0.16);
}
.resource-card-link:nth-child(3) .resource-card-surface::before {
  background: #2dd4aa;
}
.resource-card-link:nth-child(4) .resource-card-surface {
  background: linear-gradient(155deg, rgba(244, 114, 182, 0.16), rgba(5, 15, 9, 0.8) 50%);
  border-color: rgba(244, 114, 182, 0.16);
}
.resource-card-link:nth-child(4) .resource-card-surface::before {
  background: #f472b6;
}
.resource-card-link:nth-child(5) .resource-card-surface {
  background: linear-gradient(155deg, rgba(251, 191, 36, 0.16), rgba(5, 15, 9, 0.8) 50%);
  border-color: rgba(251, 191, 36, 0.16);
}
.resource-card-link:nth-child(5) .resource-card-surface::before {
  background: #fbbf24;
}
.resource-card-link:nth-child(6) .resource-card-surface {
  background: linear-gradient(155deg, rgba(16, 185, 100, 0.16), rgba(5, 15, 9, 0.8) 50%);
  border-color: rgba(52, 200, 140, 0.16);
}
.resource-card-link:nth-child(6) .resource-card-surface::before {
  background: #34d399;
}

.resource-card-link:hover .resource-card-surface {
  transform: translateY(-6px) rotateZ(-0.4deg);
  box-shadow: 0 24px 52px rgba(0, 3, 18, 0.34);
}
.resource-card-link:hover .resource-card-surface::before {
  width: 7px;
  opacity: 1;
}

.resource-icon {
  width: 44px;
  height: 44px;
  flex-shrink: 0;
  border-radius: 13px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.07);
  color: #93c5fd;
  border: 1px solid rgba(255, 255, 255, 0.08);
  transition:
    transform var(--t-base) var(--ease-out),
    box-shadow var(--t-fast);
}

.resource-card-link:hover .resource-icon {
  transform: translateY(-3px) rotate(8deg);
  box-shadow: 0 14px 28px rgba(96, 165, 250, 0.22);
}

.resource-content {
  min-width: 0;
}
.resource-title {
  color: var(--text-primary);
  font-weight: 800;
  line-height: 1.45;
}
.resource-meta {
  margin-top: 0.22rem;
  color: var(--text-secondary);
  font-size: 0.84rem;
  line-height: 1.5;
}

/* ──────────────────────────────────────────────────────────────
   § 18  TIMELINE  (sci-fi roadmap with connecting line)
   ────────────────────────────────────────────────────────────── */
/* ──────────────────────────────────────────────────────────────
   § 19  ALERT, LOADING, EMPTY STATE
   ────────────────────────────────────────────────────────────── */
.dashboard-alert {
  display: flex;
  align-items: center;
  gap: 0.65rem;
  padding: 0.9rem 1rem;
  margin-bottom: 1.25rem;
  border-radius: 16px;
  background: rgba(251, 191, 36, 0.08);
  border: 1px solid rgba(251, 191, 36, 0.2);
  color: #fcd34d;
  box-shadow: var(--shadow-sm);
  backdrop-filter: blur(16px);
}

.dashboard-skeleton-hero {
  display: grid;
  grid-template-columns: minmax(0, 1.25fr) minmax(320px, 0.75fr);
  gap: 1.4rem;
  padding: 1.5rem;
}

.dashboard-skeleton-hero-copy,
.dashboard-skeleton-calendar,
.dashboard-skeleton-card,
.dashboard-skeleton-progress,
.dashboard-skeleton-panel {
  min-width: 0;
}

.dashboard-skeleton-hero-copy {
  display: flex;
  flex-direction: column;
  justify-content: center;
  min-height: 280px;
}

.dashboard-skeleton-chip-row,
.dashboard-skeleton-card-top,
.dashboard-skeleton-section-head,
.dashboard-skeleton-progress-body,
.dashboard-skeleton-progress-row,
.dashboard-skeleton-list-row,
.dashboard-skeleton-calendar-head {
  display: flex;
  align-items: center;
}

.dashboard-skeleton-chip-row {
  flex-wrap: wrap;
  gap: 0.7rem;
  margin: 1.1rem 0;
}

.dashboard-skeleton-card,
.dashboard-skeleton-progress,
.dashboard-skeleton-panel,
.dashboard-skeleton-calendar {
  padding: 1.25rem;
}

.dashboard-skeleton-card-top,
.dashboard-skeleton-section-head,
.dashboard-skeleton-calendar-head {
  justify-content: space-between;
  gap: 1rem;
}

.dashboard-skeleton-progress-body {
  gap: 2rem;
  padding-top: 1.5rem;
}

.dashboard-skeleton-progress-rows {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 0.9rem;
  min-width: 0;
}

.dashboard-skeleton-progress-row {
  justify-content: space-between;
  gap: 1rem;
  padding: 0.75rem 0;
  border-bottom: 1px solid var(--border-default);
}

.dashboard-skeleton-list {
  display: flex;
  flex-direction: column;
  gap: 0.95rem;
  margin-top: 1.25rem;
}

.dashboard-skeleton-list-row {
  gap: 0.85rem;
}

.dashboard-skeleton-list-copy {
  flex: 1;
  min-width: 0;
}

.dashboard-skeleton-calendar {
  border: 1px solid var(--border-default);
  border-radius: 8px;
  background: var(--surface-base);
}

.dashboard-skeleton-calendar-grid {
  display: grid;
  grid-template-columns: repeat(7, minmax(0, 1fr));
  gap: 0.45rem;
  margin-top: 1rem;
}

.dashboard-skeleton-block {
  position: relative;
  overflow: hidden;
  border-radius: 6px;
  background: #e8edf1;
}

.dashboard-skeleton-eyebrow {
  width: 116px;
  height: 1.15rem;
}

.dashboard-skeleton-title {
  width: min(540px, 82%);
  height: 3rem;
  margin-top: 1rem;
}

.dashboard-skeleton-chip {
  width: 142px;
  height: 2.35rem;
  border-radius: 999px;
}

.dashboard-skeleton-line {
  width: 100%;
  height: 1rem;
  margin-top: 0.7rem;
}

.dashboard-skeleton-line--short {
  width: 58%;
}

.dashboard-skeleton-line--tiny {
  width: 44%;
}

.dashboard-skeleton-calendar-title {
  width: 128px;
  height: 1.3rem;
}

.dashboard-skeleton-calendar-nav {
  width: 72px;
  height: 1.8rem;
}

.dashboard-skeleton-calendar-day {
  aspect-ratio: 1;
}

.dashboard-skeleton-icon {
  width: 44px;
  height: 44px;
  flex: 0 0 44px;
  border-radius: 50%;
}

.dashboard-skeleton-label {
  width: 112px;
  height: 1rem;
}

.dashboard-skeleton-metric {
  width: 92px;
  height: 2.6rem;
  margin-top: 1.3rem;
}

.dashboard-skeleton-kicker {
  width: 86px;
  height: 0.85rem;
}

.dashboard-skeleton-heading {
  width: 176px;
  height: 1.45rem;
  margin-top: 0.55rem;
}

.dashboard-skeleton-select {
  width: 180px;
  height: 2.35rem;
}

.dashboard-skeleton-ring {
  width: 172px;
  height: 172px;
  flex: 0 0 172px;
  border-radius: 50%;
}

.dashboard-skeleton-row-label {
  width: 120px;
  height: 1rem;
}

.dashboard-skeleton-row-value {
  width: 160px;
  height: 1rem;
}

.dashboard-skeleton-link {
  width: 84px;
  height: 1.8rem;
}

.empty-state {
  min-height: 140px;
  border-radius: 18px;
  border: 1px dashed rgba(255, 255, 255, 0.1);
  background: rgba(255, 255, 255, 0.02);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.62rem;
  flex-direction: column;
  color: var(--text-secondary);
  text-align: center;
  padding: 1.5rem;
}

.empty-state i {
  font-size: 1.4rem;
  color: var(--text-muted);
}

.dashboard-modal-backdrop {
  position: fixed;
  inset: 0;
  z-index: 2000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1rem;
  background: rgba(10, 18, 22, 0.58);
  backdrop-filter: blur(8px);
}

.dashboard-modal {
  position: relative;
  width: min(420px, 100%);
  padding: 2rem;
  border: 1px solid rgba(60, 200, 120, 0.18);
  border-radius: 8px;
  background: var(--white);
  box-shadow: 0 18px 48px rgba(0, 0, 0, 0.24);
  color: var(--charcoal);
  text-align: center;
}

.dashboard-modal-close {
  position: absolute;
  top: 0.85rem;
  right: 0.85rem;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  background: #f8f9fa;
  color: var(--charcoal);
  cursor: pointer;
}

.dashboard-modal-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 56px;
  height: 56px;
  margin-bottom: 1rem;
  border-radius: 50%;
  background: rgba(60, 200, 120, 0.12);
  color: #218f58;
  font-size: 1.35rem;
}

.dashboard-modal h3 {
  margin: 0 0 0.65rem;
  color: var(--charcoal);
  font-size: 1.2rem;
  font-weight: 800;
}

.dashboard-modal p {
  margin: 0 0 1.35rem;
  color: #6c757d;
  line-height: 1.5;
}

/* ──────────────────────────────────────────────────────────────
   § 20  INTERACTIVE SURFACE  (legacy compat stub)
   ────────────────────────────────────────────────────────────── */
.interactive-surface {
  position: relative;
  isolation: isolate;
}

/* ──────────────────────────────────────────────────────────────
   § 21  RESPONSIVE
   ────────────────────────────────────────────────────────────── */
@media (max-width: 1400px) {
  .summary-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .groups-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 1180px) {
  .dashboard-hero-main {
    grid-template-columns: 1fr;
    padding-top: 3rem;
  }
  .dashboard-hero-copy {
    padding: 1.2rem 1.15rem 1.22rem;
  }
  .two-col-layout {
    grid-template-columns: 1fr;
  }
  .dashboard-skeleton-hero {
    grid-template-columns: 1fr;
  }
  .dashboard-skeleton-progress-body {
    align-items: flex-start;
    flex-direction: column;
  }
}

@media (max-width: 880px) {
  .dashboard-page-shell {
    padding: 1rem 0.8rem 2rem;
  }
  .summary-grid,
  .groups-grid,
  .resource-grid {
    grid-template-columns: 1fr;
  }
  .event-detail-card {
    flex-direction: column;
  }
  .event-date-badge {
    width: 100%;
    min-height: 72px;
    flex-direction: row;
    justify-content: flex-start;
    align-items: center;
    gap: 0.72rem;
  }
  .dashboard-hero-main {
    padding-top: 0;
  }
  .dashboard-hero-copy,
  .dashboard-hero-calendar {
    display: block;
  }
  .dashboard-skeleton-hero,
  .dashboard-skeleton-card,
  .dashboard-skeleton-progress,
  .dashboard-skeleton-panel,
  .dashboard-skeleton-calendar {
    padding: 1rem;
  }
  .dashboard-skeleton-section-head,
  .dashboard-skeleton-calendar-head {
    align-items: flex-start;
    flex-direction: column;
  }
  .dashboard-skeleton-select,
  .dashboard-skeleton-link {
    width: 100%;
  }
}

@media (max-width: 560px) {
  .dashboard-hero-card,
  .surface-card,
  .summary-card {
    border-radius: 20px;
  }
  .hero-title {
    font-size: 1.75rem;
  }
  .dashboard-subtext,
  .dashboard-hero-message {
    font-size: 0.9rem;
  }
  .summary-card-value {
    font-size: 1.9rem;
  }
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
  .event-detail-card:hover .event-content {
    transform: none;
  }
}

@media (prefers-reduced-motion: reduce) {
  .surface-kicker::before {
    animation: none !important;
  }
  .group-card-link:hover .group-card-surface,
  .resource-card-link:hover .resource-card-surface,
  .summary-card:hover,
  .hero-meta-chip:hover,
  .event-detail-card:hover .event-date-badge,
  .event-detail-card:hover .event-content {
    transform: none !important;
  }
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
  box-shadow:
    var(--shadow-lg),
    inset 0 1px 0 rgba(255, 255, 255, 0.07);
}
.surface-card,
.summary-card,
.dashboard-alert {
  box-shadow: var(--shadow-md);
}
.hero-title,
.surface-card-title,
.group-name,
.resource-title,
.summary-card-value,
.event-title,
.progress-value,
.hero-meta-chip-value {
  color: var(--text-primary);
}
.dashboard-subtext,
.dashboard-hero-message,
.summary-card-subtext,
.progress-detail-row span,
.progress-label,
.resource-meta,
.group-meta,
.list-row-meta,
.list-row-description,
.surface-link,
.event-meta-row,
.empty-state,
.dashboard-alert,
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
.group-card-surface,
.resource-card-surface,
.list-row {
  border-color: var(--border-default);
}
.surface-card,
.summary-card,
.group-card-surface,
.resource-card-surface,
.list-row,
.hero-meta-chip,
.status-pill,
.hero-eyebrow {
  background: linear-gradient(
    165deg,
    color-mix(in srgb, var(--surface-elevated) 88%, transparent),
    color-mix(in srgb, var(--surface-base) 94%, transparent)
  );
  backdrop-filter: blur(24px);
  -webkit-backdrop-filter: blur(24px);
}
.hero-meta-chip:hover,
.status-pill:hover,
.summary-card:hover,
.surface-card:hover,
.group-card-link:hover .group-card-surface,
.resource-card-link:hover .resource-card-surface,
.list-row:hover {
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

.progress-ring {
  width: 172px;
  height: 172px;
  border-radius: 50%;
  padding: 13px;
  box-shadow:
    inset 0 0 0 1px color-mix(in srgb, var(--accent-blue) 18%, transparent),
    0 18px 42px rgba(0, 4, 20, 0.24);
}

.progress-ring-inner {
  width: 100%;
  height: 100%;
  border-radius: 50%;
  background: linear-gradient(
    160deg,
    color-mix(in srgb, var(--surface-elevated) 98%, transparent),
    color-mix(in srgb, var(--surface-base) 98%, transparent)
  );
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

.summary-card:nth-child(1) {
  border-radius: 28px 18px 24px 18px;
}
.summary-card:nth-child(2) {
  border-radius: 18px 30px 18px 24px;
}
.summary-card:nth-child(3) {
  border-radius: 24px 18px 30px 18px;
}
.summary-card:nth-child(4) {
  border-radius: 18px 24px 18px 30px;
}
.progress-card {
  border-radius: 22px 34px 22px 34px;
}
.event-detail-card {
  border-radius: 26px 22px 30px 22px;
}
.list-row {
  border-radius: 18px 14px 18px 14px;
}
.group-card-surface {
  border-radius: 26px 20px 32px 18px;
}
.resource-card-surface {
  border-radius: 20px 28px 18px 28px;
}

.hero-meta-chip--neutral {
  box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--text-primary) 8%, transparent);
}
.hero-meta-chip--cyan {
  box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--accent-teal) 18%, transparent);
}
.hero-meta-chip--violet {
  box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--accent-violet) 18%, transparent);
}

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
  --font-display:
    'Aptos Display', 'Segoe UI Variable Display', 'Inter', 'SF Pro Display', 'Helvetica Neue',
    Arial, sans-serif;
  --font-body:
    'Aptos', 'Segoe UI Variable Text', 'Inter', 'SF Pro Text', system-ui, -apple-system,
    BlinkMacSystemFont, sans-serif;
  --font-label: 'JetBrains Mono', 'SFMono-Regular', 'Cascadia Mono', Consolas, monospace;
  --font-number: 'Bahnschrift', 'Inter', 'Segoe UI', sans-serif;
  font-family: var(--font-body);
}

.dashboard-page-shell,
.dashboard-page-shell * {
  font-variant-ligatures: common-ligatures;
}
.hero-title,
.surface-card-title,
.group-name,
.resource-title,
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
.summary-label,
.hero-meta-chip-label,
.progress-label,
.status-pill,
.list-row-meta,
.event-date-rest {
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
.summary-card-subtext,
.list-row-description,
.resource-meta,
.group-meta,
.event-meta-row,
.empty-state,
.dashboard-alert {
  color: var(--text-secondary);
  font-family: var(--font-body);
  line-height: 1.7;
}

.hero-eyebrow {
  color: var(--text-hero-accent);
}
.surface-kicker {
  color: var(--accent-blue);
}
.hero-meta-chip,
.status-pill,
.summary-card,
.surface-card,
.group-card-surface,
.resource-card-surface,
.list-row,
.event-detail-card,
.dashboard-alert {
  border-color: var(--border-default);
  background: linear-gradient(
    165deg,
    color-mix(in srgb, var(--surface-elevated) 92%, transparent),
    color-mix(in srgb, var(--surface-base) 96%, transparent)
  );
}

.dashboard-hero-card {
  background: linear-gradient(145deg, var(--hero-overlay-a), var(--hero-overlay-b));
  border-color: var(--border-strong);
}
.primary-chip,
.surface-link {
  color: var(--text-link);
  font-family: var(--font-display);
  font-weight: 720;
}
.primary-chip {
  border-color: color-mix(in srgb, var(--accent-blue) 18%, var(--border-default));
}
.list-row-meta,
.progress-label,
.event-date-rest,
.summary-label {
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

/* Clean white/grey dashboard palette, aligned with Events and Resources pages. */
.dashboard-page-shell {
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
.dashboard-backdrop-grid,
.dashboard-page-inner {
  position: relative;
  z-index: 1;
}
.dashboard-hero-card,
.dashboard-hero-copy,
.surface-card,
.summary-card,
.group-card-surface,
.resource-card-surface,
.list-row,
.hero-meta-chip,
.hero-eyebrow,
.status-pill,
.event-detail-card,
.dashboard-alert {
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
.group-card-surface,
.resource-card-surface {
  overflow: hidden;
}
.dashboard-hero-card:hover,
.surface-card:hover,
.summary-card:hover,
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
.primary-chip,
.surface-link {
  color: #4f5f6f !important;
  background: #f8f9fa !important;
  border: 1px solid var(--border-light) !important;
  box-shadow: none !important;
}
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
.summary-card-subtext,
.list-row-description,
.resource-meta,
.group-meta,
.event-meta-row,
.empty-state,
.hero-meta-chip-label,
.summary-label,
.status-pill,
.list-row-meta,
.progress-detail-row span,
.progress-label,
.event-date-rest,
.dashboard-alert {
  color: #6c757d !important;
}
.surface-kicker,
.hero-eyebrow {
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
  box-shadow:
    inset 0 0 0 1px var(--border-light),
    0 2px 4px var(--shadow) !important;
}

@media (max-width: 880px) {
  .dashboard-page-shell {
    padding: 1.25rem;
  }

  .dashboard-hero-main {
    padding-top: 0;
  }
}
.dashboard-hero-card:hover,
.surface-card:hover,
.summary-card:hover,
.hero-meta-chip:hover,
.premium-row:hover,
.group-card-link:hover .group-card-surface,
.resource-card-link:hover .resource-card-surface,
.list-row:hover {
  transform: none !important;
  box-shadow: 0 2px 4px var(--shadow) !important;
}
.summary-card:hover .summary-icon-wrap,
.event-detail-card:hover .event-date-badge,
.event-detail-card:hover .event-content,
.premium-row:hover .announcement-icon,
.premium-row:hover .list-row-tail,
.group-card-link:hover .primary-avatar,
.group-card-link:hover .secondary-avatar,
.group-card-link:hover .tertiary-avatar,
.group-card-link:hover .group-open-indicator,
.resource-card-link:hover .resource-icon {
  transform: none !important;
}

.dashboard-announcement-body {
  display: block;
  max-height: 4.8rem;
  overflow: hidden;
  position: relative;
}

.dashboard-announcement-body :deep(*) {
  max-width: 100%;
  color: inherit;
  font-size: inherit;
  line-height: inherit;
}

.dashboard-announcement-body :deep(p),
.dashboard-announcement-body :deep(ul),
.dashboard-announcement-body :deep(ol),
.dashboard-announcement-body :deep(blockquote) {
  margin: 0 0 0.36rem;
}

.dashboard-announcement-body :deep(p:last-child),
.dashboard-announcement-body :deep(ul:last-child),
.dashboard-announcement-body :deep(ol:last-child),
.dashboard-announcement-body :deep(blockquote:last-child) {
  margin-bottom: 0;
}

.dashboard-announcement-body :deep(h1),
.dashboard-announcement-body :deep(h2),
.dashboard-announcement-body :deep(h3),
.dashboard-announcement-body :deep(h4),
.dashboard-announcement-body :deep(h5),
.dashboard-announcement-body :deep(h6) {
  margin: 0 0 0.28rem;
  color: var(--charcoal) !important;
  font-size: 0.9rem;
  font-weight: 800;
  line-height: 1.35;
}

.dashboard-announcement-body :deep(ul),
.dashboard-announcement-body :deep(ol) {
  padding-left: 1rem;
}

.dashboard-announcement-body :deep(li + li) {
  margin-top: 0.12rem;
}

.dashboard-announcement-body :deep(blockquote) {
  padding: 0.32rem 0.55rem;
  border-left: 2px solid #cfd6dc;
  background: #f8f9fa;
  border-radius: 0 6px 6px 0;
}

.dashboard-announcement-body :deep(code) {
  padding: 0.04rem 0.22rem;
  background: #eef1f3;
  border-radius: 4px;
  color: var(--charcoal);
  font-size: 0.84rem;
}

.dashboard-announcement-body :deep(img),
.dashboard-announcement-body :deep(table),
.dashboard-announcement-body :deep(figure),
.dashboard-announcement-body :deep(pre) {
  display: none !important;
}

.dashboard-hero-groups {
  margin-top: 1.35rem;
  padding: 1.25rem 0 0.1rem;
  border-top: 1px solid var(--border-light);
}

.dashboard-hero-groups .surface-card-header {
  margin-bottom: 1rem;
}

.dashboard-hero-groups .surface-card-title {
  font-size: clamp(1.35rem, 2vw, 1.72rem);
}

.dashboard-hero-groups-grid {
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 1.15rem;
}

.dashboard-hero-groups .group-card-surface {
  min-height: 154px;
  padding: 1.18rem;
  border: 1px solid var(--border-light) !important;
  box-shadow: 0 2px 4px var(--shadow) !important;
}

@media (max-width: 1400px) {
  .dashboard-hero-groups-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 880px) {
  .dashboard-hero-groups-grid {
    grid-template-columns: 1fr;
  }
}
</style>
