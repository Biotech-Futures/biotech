<!--
  Shell for the /admin route tree: sectioned sidebar (Overview / People /
  Groups & Matching / Content), breadcrumbs, and route-driven tab strips on
  the People and Groups hubs. Rendered inside App.vue's header; App.vue hides
  its student sidebar while an /admin route is active.

  Installing Vuetify here covers every admin child route.
-->
<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useAdminVuetify } from '@/admin/vuetify'

useAdminVuetify()

const route = useRoute()

interface NavLink {
  label: string
  to: string
  icon: string
}

interface NavSection {
  title: string
  links: NavLink[]
}

const sections: NavSection[] = [
  {
    title: 'Overview',
    links: [{ label: 'Dashboard', to: '/admin', icon: 'fas fa-gauge' }],
  },
  {
    title: 'People',
    links: [
      { label: 'Users', to: '/admin/people', icon: 'fas fa-user' },
      { label: 'Students', to: '/admin/people/students', icon: 'fas fa-user-graduate' },
      { label: 'Mentors', to: '/admin/people/mentors', icon: 'fas fa-chalkboard-user' },
      { label: 'Supervisors', to: '/admin/people/supervisors', icon: 'fas fa-user-tie' },
    ],
  },
  {
    title: 'Groups & Matching',
    links: [
      { label: 'Groups', to: '/admin/groups', icon: 'fas fa-users' },
      { label: 'Student Matching', to: '/admin/groups/student-matching', icon: 'fas fa-people-arrows' },
      { label: 'Mentor Matching', to: '/admin/groups/mentor-matching', icon: 'fas fa-handshake' },
      { label: 'Matched Groups', to: '/admin/groups/matched-groups', icon: 'fas fa-link' },
    ],
  },
  {
    title: 'Content',
    links: [
      { label: 'Events', to: '/admin/events', icon: 'fas fa-calendar' },
      { label: 'Resources', to: '/admin/resources', icon: 'fas fa-book' },
      { label: 'Announcements', to: '/admin/announcements', icon: 'fas fa-bullhorn' },
      { label: 'Tasks', to: '/admin/tasks', icon: 'fas fa-list-check' },
    ],
  },
]

const isActive = (to: string) => route.path === to

// Hub tab strips mirror the sidebar's People / Groups sections.
const activeHubTabs = computed(() => {
  if (route.path.startsWith('/admin/people')) return sections[1].links
  if (route.path.startsWith('/admin/groups')) return sections[2].links
  return null
})

// Breadcrumbs derived from the nav structure: Admin / <section> / <page>.
const breadcrumbs = computed(() => {
  for (const section of sections) {
    const link = section.links.find((item) => item.to === route.path)
    if (link) {
      const crumbs = ['Admin']
      if (section.title !== 'Overview') crumbs.push(section.title)
      crumbs.push(link.label)
      return crumbs
    }
  }
  return ['Admin']
})
</script>

<template>
  <v-app class="admin-app">
    <div class="admin-shell">
      <aside class="admin-nav" aria-label="Admin navigation">
        <section v-for="section in sections" :key="section.title" class="admin-nav-section">
          <h2 class="admin-nav-title">{{ section.title }}</h2>
          <RouterLink
            v-for="link in section.links"
            :key="link.to"
            :to="link.to"
            class="admin-nav-link"
            :class="{ active: isActive(link.to) }"
          >
            <i :class="link.icon" class="admin-nav-icon" aria-hidden="true"></i>
            <span>{{ link.label }}</span>
          </RouterLink>
        </section>
      </aside>

      <div class="admin-content">
        <nav class="admin-breadcrumbs" aria-label="Breadcrumb">
          <template v-for="(crumb, index) in breadcrumbs" :key="`${index}-${crumb}`">
            <span v-if="index > 0" class="admin-breadcrumb-sep" aria-hidden="true">/</span>
            <span class="admin-breadcrumb" :class="{ current: index === breadcrumbs.length - 1 }">
              {{ crumb }}
            </span>
          </template>
        </nav>

        <v-tabs v-if="activeHubTabs" class="admin-hub-tabs" color="primary" density="comfortable">
          <v-tab v-for="tab in activeHubTabs" :key="tab.to" :to="tab.to">{{ tab.label }}</v-tab>
        </v-tabs>

        <div class="admin-page">
          <router-view />
        </div>
      </div>
    </div>
  </v-app>
</template>

<style scoped>
.admin-app {
  /* Let App.vue's page background show through; theme colors still apply to
     Vuetify components inside. */
  background: transparent;
}

.admin-shell {
  display: flex;
  min-height: 100%;
}

.admin-nav {
  width: 230px;
  min-width: 230px;
  padding: 1.25rem 0.75rem;
  border-right: 1px solid var(--border-light);
  background-color: var(--surface-elevated);
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.admin-nav-section {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}

.admin-nav-title {
  font-size: 0.72rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--text-muted);
  margin: 0 0 0.35rem 0.65rem;
}

.admin-nav-link {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  padding: 0.45rem 0.65rem;
  border-radius: 8px;
  color: var(--charcoal);
  text-decoration: none;
  font-size: 0.92rem;
}

.admin-nav-link:hover {
  background-color: var(--accent-green-soft);
}

.admin-nav-link.active {
  background-color: var(--accent-green-soft);
  color: var(--dark-green);
  font-weight: 600;
}

.admin-nav-icon {
  width: 1.1rem;
  text-align: center;
  font-size: 0.85rem;
}

.admin-content {
  flex: 1;
  min-width: 0;
  padding: 1.25rem 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 0.9rem;
}

.admin-breadcrumbs {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  font-size: 0.85rem;
  color: var(--text-muted);
}

.admin-breadcrumb.current {
  color: var(--charcoal);
  font-weight: 600;
}

.admin-breadcrumb-sep {
  color: var(--border-light);
}

.admin-hub-tabs {
  border-bottom: 1px solid var(--border-light);
}

.admin-page {
  flex: 1;
  min-width: 0;
}

@media (max-width: 900px) {
  .admin-shell {
    flex-direction: column;
  }

  .admin-nav {
    width: 100%;
    min-width: 0;
    flex-direction: row;
    flex-wrap: wrap;
    gap: 1rem;
    border-right: none;
    border-bottom: 1px solid var(--border-light);
  }
}
</style>
