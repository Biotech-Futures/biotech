<script setup>
import { ref, computed } from 'vue'
import { useRouter, RouterLink } from 'vue-router'
import { storeToRefs } from 'pinia'
import { useAuthStore } from '@/stores/auth' // Pinia Auth
import { mockGroups, mockResources, mockAnnouncements } from '../data/mock.js'

const router = useRouter()
const auth = useAuthStore()

// Get the current user and admin status from Pinia
const { user, isAdmin } = storeToRefs(auth)
// Fallback to role check if isAdmin getter is missing
const effectiveIsAdmin = computed(() => (isAdmin?.value ?? (user.value?.role === 'admin')))

const groups = ref(mockGroups)
const resources = ref(mockResources)
const announcements = ref(mockAnnouncements)
const announcementsCount = computed(() => announcements.value.length)

const getCurrentDate = () =>
  new Date().toLocaleDateString('en-AU', {
    weekday: 'long',
    year: 'numeric',
    month: 'long',
    day: 'numeric'
  })

const getResourceIcon = (type) => {
  const icons = { document: 'fas fa-file-alt', video: 'fas fa-video', link: 'fas fa-link' }
  return icons[type] || 'fas fa-file'
}
</script>

<template>
  <div class="content-area">
    <div style="margin-bottom: 2rem;">
      <h1>Welcome back, {{ user?.name || 'User' }}!</h1>
      <p style="color:#6c757d;">
        {{ getCurrentDate() }} - Track: {{ user?.track || '—' }}
      </p>
    </div>

    <div class="grid grid-3" style="margin-bottom: 2rem;">
      <!-- Active Groups: admins only -->
      <div class="widget" v-if="effectiveIsAdmin">
        <div class="widget-header">
          <span class="widget-title">Active Groups</span>
          <i class="fas fa-users" style="color: var(--eucalypt);"></i>
        </div>
        <div class="widget-value">{{ groups.length }}</div>
        <div class="widget-footer">
          <RouterLink to="/groups" style="color: var(--dark-green);">View all groups →</RouterLink>
        </div>
      </div>

      <div class="widget">
        <div class="widget-header">
          <span class="widget-title">Upcoming Events</span>
          <i class="fas fa-calendar" style="color: var(--mint-green);"></i>
        </div>
        <div class="widget-value">3</div>
        <div class="widget-footer">
          <RouterLink to="/events" style="color: var(--dark-green);">View calendar →</RouterLink>
        </div>
      </div>

      <!-- Resources -> Recent Announcements -->
      <div class="widget">
        <div class="widget-header">
          <span class="widget-title">Recent Announcements</span>
          <i class="fas fa-bullhorn" style="color: var(--air-force-blue);"></i>
        </div>
        <div class="widget-value">{{ announcementsCount }}</div>
        <div class="widget-footer">
          <RouterLink to="/announcements" style="color: var(--dark-green);">
            View announcements 鈫?          </RouterLink>
        </div>
      </div>
    </div>

    <!-- My Active Groups: visible to all users -->
    <div class="card" v-if="groups.length">
      <div class="card-header">
        <h3 class="card-title">My Active Groups ({{ groups.length }})</h3>
        <RouterLink to="/groups" style="color: var(--dark-green);">View all</RouterLink>
      </div>

      <div class="grid grid-2">
        <div
          v-for="group in groups"
          :key="group.id"
          class="group-card"
          @click="router.push('/groups/' + group.id)"
        >
          <div class="group-header">
            <div class="group-avatars">
              <div class="group-avatar">AP</div>
              <div class="group-avatar" style="background-color: var(--mint-green);">YG</div>
              <div class="group-avatar" style="background-color: var(--air-force-blue);">
                +{{ group.members - 2 }}
              </div>
            </div>
            <div class="group-info">
              <div class="group-name">{{ group.name }}</div>
              <!-- Capsule-style action tag; .stop prevents card navigation -->
              <!-- <button type="button" class="chip-action" @click.stop>
                {{ group.status }}
              </button> -->
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Resources section (visible to all users) -->
    <div class="card">
      <div class="card-header">
        <h3 class="card-title">Learn more with resources</h3>
        <RouterLink to="/resources" style="color: var(--dark-green);">View all</RouterLink>
      </div>

      <div class="resource-grid">
        <div
          v-for="resource in resources.slice(0, 6)"
          :key="resource.id"
          class="resource-card"
          @click="router.push('/resources/' + resource.id)"
        >
          <div class="resource-icon">
            <i :class="getResourceIcon(resource.type)"></i>
          </div>
          <div class="resource-content">
            <div class="resource-title">{{ resource.title }}</div>
            <div class="resource-meta">Updated {{ resource.updated }}</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* Refined "Schedule Workshop" pill button */
.chip-action {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.35rem 0.65rem;
  font-size: 0.8125rem;
  font-weight: 600;
  line-height: 1;
  border-radius: 999px;
  background-color: var(--light-green);
  color: var(--dark-green);
  border: 1px solid var(--dark-green);
  cursor: pointer;
  transition: all 0.2s ease;
}
.chip-action:hover {
  background-color: var(--dark-green);
  color: var(--white);
  transform: translateY(-1px);
  box-shadow: 0 2px 4px var(--shadow);
}
</style>
