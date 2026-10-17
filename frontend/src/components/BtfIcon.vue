<template>
  <svg
    class="btf-icon"
    :class="{ 'btf-icon--spin': isSpinner }"
    :width="size"
    :height="size"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    :stroke-width="strokeWidth"
    stroke-linecap="round"
    stroke-linejoin="round"
    :role="title ? 'img' : undefined"
    :aria-hidden="title ? undefined : 'true'"
    focusable="false"
  >
    <title v-if="title">{{ title }}</title>
    <g v-html="iconMarkup"></g>
  </svg>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    name: string
    size?: number | string
    strokeWidth?: number | string
    title?: string
  }>(),
  { size: 20, strokeWidth: 1.75, title: '' },
)

const icons: Record<string, string> = {
  home: '<path d="m3 11 9-8 9 8"/><path d="M5 10v10h14V10"/><path d="M9 20v-6h6v6"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.93 4.93l1.42 1.42M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.42-1.42M17.66 6.34l1.41-1.41"/>',
  moon: '<path d="M20.5 14.5A8 8 0 0 1 9.5 3.5 8.5 8.5 0 1 0 20.5 14.5Z"/>',
  chart: '<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>',
  pie: '<path d="M21 12a9 9 0 1 1-9-9v9Z"/><path d="M12 3a9 9 0 0 1 9 9h-9Z"/>',
  trend: '<path d="m3 17 6-6 4 4 8-9"/><path d="M15 6h6v6"/>',
  user: '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
  users: '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/>',
  'user-plus': '<path d="M15 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="8" cy="7" r="4"/><path d="M19 8v6M22 11h-6"/>',
  mentor: '<circle cx="9" cy="7" r="4"/><path d="M2 21a7 7 0 0 1 14 0M17 11l2 2 4-4"/>',
  activity: '<path d="M3 12h4l2-7 4 14 2-7h6"/>',
  message: '<path d="M21 15a4 4 0 0 1-4 4H8l-5 3V7a4 4 0 0 1 4-4h10a4 4 0 0 1 4 4Z"/><path d="M8 10h.01M12 10h.01M16 10h.01"/>',
  book: '<path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2Z"/>',
  mail: '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 7 9 6 9-6"/>',
  'mail-check': '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 7 9 6 9-6M15.5 16l1.5 1.5 3-3"/>',
  calendar: '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M16 3v4M8 3v4M3 10h18"/>',
  download: '<path d="M12 3v12M7 10l5 5 5-5M5 21h14"/>',
  cursor: '<path d="m5 3 14 9-6 2-3 6Z"/><path d="m13 14 4 6"/>',
  shield: '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Z"/><path d="m9 12 2 2 4-4"/>',
  scale: '<path d="M12 3v18M6 6h12M5 6l-3 6h6ZM19 6l-3 6h6ZM7 21h10"/>',
  trophy: '<path d="M8 3h8v4a4 4 0 0 1-8 0ZM6 5H3v2a4 4 0 0 0 4 4M18 5h3v2a4 4 0 0 1-4 4M12 11v6M8 21h8M9 17h6"/>',
  warning: '<path d="M10.3 3.7 2.4 18a2 2 0 0 0 1.8 3h15.6a2 2 0 0 0 1.8-3L13.7 3.7a2 2 0 0 0-3.4 0Z"/><path d="M12 9v4M12 17h.01"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7h.01"/>',
  lightbulb: '<path d="M9 18h6M10 22h4M8.5 15.5A7 7 0 1 1 15.5 15.5c-.9.7-1.3 1.4-1.5 2.5h-4c-.2-1.1-.6-1.8-1.5-2.5Z"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  send: '<path d="m22 2-7 20-4-9-9-4Z"/><path d="M22 2 11 13"/>',
  refresh: '<path d="M20 6v5h-5M4 18v-5h5"/><path d="M18 9a7 7 0 0 0-12-3L4 8M6 15a7 7 0 0 0 12 3l2-2"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  minus: '<path d="M5 12h14"/>',
  expand: '<path d="M8 3H3v5M16 3h5v5M8 21H3v-5M16 21h5v-5"/>',
  compress: '<path d="M8 8H3V3M16 8h5V3M8 16H3v5M16 16h5v5"/>',
  sort: '<path d="m8 9 4-4 4 4M16 15l-4 4-4-4"/>',
  'sort-up': '<path d="m7 14 5-5 5 5"/>',
  'sort-down': '<path d="m7 10 5 5 5-5"/>',
  chevronLeft: '<path d="m15 18-6-6 6-6"/>',
  chevronRight: '<path d="m9 18 6-6-6-6"/>',
  close: '<path d="M18 6 6 18M6 6l12 12"/>',
  settings: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1-2.8 2.8-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.6v.2h-4V21a1.7 1.7 0 0 0-1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1L4.2 17l.1-.1a1.7 1.7 0 0 0 .3-1.9A1.7 1.7 0 0 0 3 14H2.8v-4H3a1.7 1.7 0 0 0 1.6-1 1.7 1.7 0 0 0-.3-1.9L4.2 7 7 4.2l.1.1A1.7 1.7 0 0 0 9 4.6a1.7 1.7 0 0 0 1-1.6v-.2h4V3a1.7 1.7 0 0 0 1 1.6 1.7 1.7 0 0 0 1.9-.3l.1-.1L19.8 7l-.1.1a1.7 1.7 0 0 0-.3 1.9 1.7 1.7 0 0 0 1.6 1h.2v4H21a1.7 1.7 0 0 0-1.6 1Z"/>',
  bullhorn: '<path d="m3 11 16-6v14L3 13Z"/><path d="M11.5 16.2 13 21H7l-1.5-6"/>',
  logout: '<path d="M10 17l5-5-5-5M15 12H3M15 4h4a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-4"/>',
  spinner: '<circle cx="12" cy="12" r="9" stroke-opacity=".25"/><path d="M21 12a9 9 0 0 0-9-9"/>',
}

const aliases: Record<string, string> = {
  'chart-column': 'chart', 'chart-simple': 'chart', 'chart-line': 'trend', 'chart-pie': 'pie',
  'arrow-trend-up': 'trend', 'arrow-down': 'trend', 'wave-square': 'activity',
  'user-group': 'users', 'people-group': 'users', 'user-friends': 'users', 'users-slash': 'users',
  'people-roof': 'users', 'user-tie': 'mentor', 'user-graduate': 'mentor', 'user-clock': 'user',
  'graduation-cap': 'mentor', comments: 'message', envelope: 'mail', 'envelope-open-text': 'mail',
  'envelope-circle-check': 'mail-check', 'book-open': 'book', 'arrow-pointer': 'cursor',
  'shield-halved': 'shield', 'scale-balanced': 'scale', 'triangle-exclamation': 'warning',
  'circle-info': 'info', 'paper-plane': 'send', 'rotate-left': 'refresh', 'rotate-right': 'refresh',
  'undo-alt': 'refresh', 'calendar-alt': 'calendar', 'sign-out-alt': 'logout', times: 'close', cog: 'settings',
  'chevron-left': 'chevronLeft', 'chevron-right': 'chevronRight', 'circle-notch': 'spinner',
  'file-circle-exclamation': 'warning', 'file-signature': 'mail-check',
}

const normalizedName = computed(() => {
  const faName = props.name.match(/fa-([\w-]+)/)?.[1]
  const rawName = faName || props.name
  return aliases[rawName] || rawName
})

const iconMarkup = computed(() => icons[normalizedName.value] || icons.info)
const isSpinner = computed(() => normalizedName.value === 'spinner')
</script>

<style scoped>
.btf-icon {
  display: inline-block;
  flex: 0 0 auto;
  vertical-align: -0.15em;
}

.btf-icon--spin {
  animation: btf-icon-spin 0.9s linear infinite;
}

@keyframes btf-icon-spin {
  to { transform: rotate(360deg); }
}
</style>
