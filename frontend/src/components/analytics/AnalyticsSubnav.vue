<template>
  <ul class="analytics-subnav" :class="{ 'analytics-subnav--collapsed': collapsed }">
    <li v-for="item in navItems" :key="item.to">
      <RouterLink :to="item.to" class="analytics-subnav-link" :class="{ active: route.path === item.to }">
        <BtfIcon :name="item.icon" :size="18" />
        <span>{{ item.label }}</span>
      </RouterLink>
    </li>
  </ul>
</template>

<script setup lang="ts">
import { RouterLink, useRoute } from 'vue-router'
import BtfIcon from '@/components/BtfIcon.vue'

defineProps<{ collapsed?: boolean }>()

const route = useRoute()
const navItems = [
  { to: '/analytics', label: 'Overview', icon: 'pie' },
  { to: '/analytics/users', label: 'Users', icon: 'user' },
  { to: '/analytics/registration', label: 'Registration', icon: 'user-plus' },
  { to: '/analytics/groups', label: 'Groups', icon: 'users' },
  { to: '/analytics/mentors', label: 'Mentors', icon: 'mentor' },
  { to: '/analytics/activity', label: 'Activity', icon: 'activity' },
  { to: '/analytics/messages', label: 'Messages', icon: 'message' },
  { to: '/analytics/resources', label: 'Resources', icon: 'book' },
  { to: '/analytics/email', label: 'Email Monitoring', icon: 'mail-check' },
]
</script>

<style scoped>
.analytics-subnav {
  margin: 4px 0 10px;
  padding: 0;
  list-style: none;
}

.analytics-subnav li {
  margin: 2px 0;
  padding: 0;
  list-style: none;
}

.analytics-subnav-link {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-left: 30px;
  padding: 10px 16px;
  border-left: 3px solid transparent;
  border-radius: 8px 0 0 8px;
  color: var(--analytics-ui-text, var(--btf-teal));
  font-size: 15px;
  font-weight: 400;
  text-decoration: none;
  transition: background-color 0.2s ease, color 0.2s ease, border-color 0.2s ease;
}

.analytics-subnav-link:hover,
.analytics-subnav-link.active {
  background: color-mix(in srgb, var(--analytics-ui-selected, var(--btf-light-green)) 45%, var(--analytics-ui-surface, var(--btf-white)));
  color: var(--analytics-ui-accent, var(--btf-dark-green));
  border-left-color: var(--btf-dark-green);
}

.analytics-subnav-link.active {
  font-weight: 600;
}

.analytics-subnav--collapsed .analytics-subnav-link {
  justify-content: center;
  gap: 0;
  margin-left: 0;
  padding: 10px 0;
  border-radius: 8px;
}

.analytics-subnav--collapsed .analytics-subnav-link span {
  display: none;
}
</style>
